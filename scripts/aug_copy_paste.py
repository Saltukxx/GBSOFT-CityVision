#!/usr/bin/env python3
"""Copy-paste augmentation for the aerial road-damage dataset.

Implements docs/model-upgrade-plan.md §2 ("Copy-paste augmentation — the
highest-leverage, lowest-cost option"): cut labeled defect crops (pothole,
road_crack, manhole) out of real hand-labeled frames and paste them, with
randomized scale/rotation and a feathered edge, onto real clean background
frames. The pasted box is recorded automatically since we know exactly what
we pasted and where. This multiplies the *rare* classes without any new
manual labeling minutes, and also grows manhole-in-varied-background
diversity to reinforce the manhole-is-not-road_damage distinction (see
docs/model-upgrade-plan.md and the manhole labeling policy).

  .venv/bin/python scripts/aug_copy_paste.py --count 300 --seed 0

Output is a *separate* dataset root, train split only:

  data/datasets/model_b_aerial_synthetic/images/train/synthcp_000000.jpg
  data/datasets/model_b_aerial_synthetic/labels/train/synthcp_000000.txt

Kept apart from data/datasets/model_b_aerial/ on purpose:
- src/cityvision/pipeline/dataset_split.py's clip_of()/timestamp_of() parse
  filenames as `clipN_TIMESTAMPms`; synthetic files use a `synthcp_NNNNNN`
  name precisely so they can never be swept into that clip-based split logic.
- Synthetic data must never reach val/test — only real hold-out frames may
  be used to decide whether a checkpoint is actually better (see
  docs/eval/README.md). Val/test contamination would make the eval gate lie.

This script does NOT wire its output into scripts/label_aerial.py's
EXTERNAL_TRAIN_SOURCES. That list is for fixed, already-vetted external
datasets (uav_pdd2023) folded into every real export automatically; this
output is regenerable/experimental synthetic data, and auto-folding it would
mean a bad synthetic batch silently entering every future export. To use it:
add its path to EXTERNAL_TRAIN_SOURCES in scripts/label_aerial.py yourself
(same shape as the uav_pdd2023 entry: images/train + labels/train), once
you've decided you trust a given batch — that should stay a visible,
deliberate step, not something this script does for you.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DS = ROOT / "data" / "datasets" / "model_b_aerial"
RAW_FRAMES = DS / "raw_frames"
LABELS_HAND = DS / "labels_hand"
BACKGROUND = DS / "background.txt"

NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
# Manhole already has more real boxes (524) than pothole (262) or road_crack
# (521 but many tiny/thin), so weight paste sampling toward the two rarer,
# harder classes rather than uniformly across --classes.
DEFAULT_CLASS_WEIGHTS = {0: 3.0, 1: 3.0, 2: 1.0, 3: 1.0}

MAX_PLACEMENT_ATTEMPTS = 20
PASTE_IOU_CAP = 0.1


def iou_xyxy(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class Crop:
    __slots__ = ("cls_id", "bgr", "alpha")

    def __init__(self, cls_id: int, bgr: np.ndarray, alpha: np.ndarray):
        self.cls_id = cls_id
        self.bgr = bgr  # HxWx3 uint8
        self.alpha = alpha  # HxW float32 0..1, feathered edge mask


def load_yolo_boxes(label_path: Path) -> List[Tuple[int, float, float, float, float]]:
    if not label_path.exists():
        return []
    out = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls_id, cx, cy, w, h = parts
        out.append((int(cls_id), float(cx), float(cy), float(w), float(h)))
    return out


def feathered_alpha(h: int, w: int, feather_frac: float = 0.08) -> np.ndarray:
    """Elliptical mask, 1.0 in the core, Gaussian-blurred to a soft 0 edge.

    An alpha-blended soft edge avoids the model latching onto a hard
    rectangular seam as its "defect" cue instead of the actual pasted
    texture (docs/model-upgrade-plan.md's explicit warning). The blur kernel
    is capped in absolute pixels: scaling it as a fraction of a large crop
    (e.g. a wide manhole) blurs away most of the interior detail, not just
    the rim, and on a small crop (a thin pothole) it can erase the pasted
    content almost entirely — visually confirmed on the first --count 20
    validation run before this cap was added.
    """
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(
        mask,
        center=(w // 2, h // 2),
        axes=(max(1, int(w * 0.5 * (1 - feather_frac))), max(1, int(h * 0.5 * (1 - feather_frac)))),
        angle=0,
        startAngle=0,
        endAngle=360,
        color=1.0,
        thickness=-1,
    )
    ksize = max(3, min(9, int(round(min(h, w) * feather_frac)) | 1))  # odd, capped
    mask = cv2.GaussianBlur(mask, (ksize, ksize), 0)
    if mask.max() > 0:
        mask = mask / mask.max()
    return mask


def match_color(patch_bgr: np.ndarray, alpha: np.ndarray, bg_region: np.ndarray) -> np.ndarray:
    """Shift the patch's per-channel mean toward the destination region's mean.

    Without this, a bright/reflective source crop (a manhole cover shot in
    different light) pasted onto a duller background reads as an obvious
    "flashlight" artifact rather than a plausible in-scene object — visually
    confirmed on the first validation run. Only core pixels (alpha > 0.5)
    count toward the patch mean so the already-transparent rim doesn't dilute
    the estimate. Shift is capped so it corrects lighting/exposure mismatch
    without washing out the crop's own texture (e.g. a crack's dark line).
    """
    core = alpha > 0.5
    if core.sum() < 4 or bg_region.size == 0:
        return patch_bgr
    patch_mean = patch_bgr[core].reshape(-1, 3).mean(axis=0)
    bg_mean = bg_region.reshape(-1, 3).mean(axis=0)
    shift = np.clip(bg_mean - patch_mean, -40.0, 40.0)
    out = patch_bgr.astype(np.float32) + shift
    return np.clip(out, 0, 255).astype(np.uint8)


def extract_crops(class_ids: set[int]) -> dict[int, List[Crop]]:
    crops: dict[int, List[Crop]] = {c: [] for c in class_ids}
    for label_path in sorted(LABELS_HAND.glob("*.txt")):
        boxes = load_yolo_boxes(label_path)
        if not boxes:
            continue
        img_path = RAW_FRAMES / f"{label_path.stem}.jpg"
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        H, W = img.shape[:2]
        for cls_id, cx, cy, w, h in boxes:
            if cls_id not in class_ids:
                continue
            bw, bh = w * W, h * H
            if bw < 4 or bh < 4:
                continue  # too thin/small to paste meaningfully (esp. hairline cracks)
            x1 = max(0, int((cx - w / 2) * W))
            y1 = max(0, int((cy - h / 2) * H))
            x2 = min(W, int((cx + w / 2) * W))
            y2 = min(H, int((cy + h / 2) * H))
            if x2 - x1 < 4 or y2 - y1 < 4:
                continue
            crop_bgr = img[y1:y2, x1:x2].copy()
            alpha = feathered_alpha(crop_bgr.shape[0], crop_bgr.shape[1])
            crops[cls_id].append(Crop(cls_id, crop_bgr, alpha))
    return crops


def load_backgrounds() -> List[str]:
    if not BACKGROUND.exists():
        return []
    return [ln.strip() for ln in BACKGROUND.read_text(encoding="utf-8").splitlines() if ln.strip()]


def rotate_scale(crop: Crop, angle_deg: float, scale: float) -> Tuple[np.ndarray, np.ndarray]:
    h, w = crop.bgr.shape[:2]
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
    bgr = cv2.resize(crop.bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    alpha = cv2.resize(crop.alpha, (nw, nh), interpolation=cv2.INTER_LINEAR)

    diag = int(np.ceil((nw**2 + nh**2) ** 0.5))
    M = cv2.getRotationMatrix2D((nw / 2, nh / 2), angle_deg, 1.0)
    M[0, 2] += (diag - nw) / 2
    M[1, 2] += (diag - nh) / 2
    bgr_r = cv2.warpAffine(bgr, M, (diag, diag), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    alpha_r = cv2.warpAffine(alpha, M, (diag, diag), borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)

    # Crop away the fully-transparent margin introduced by the rotation canvas so the
    # emitted box tightly bounds the actual pasted content, not the padded square.
    ys, xs = np.where(alpha_r > 0.02)
    if len(xs) == 0 or len(ys) == 0:
        return bgr_r, alpha_r
    x1, x2 = xs.min(), xs.max() + 1
    y1, y2 = ys.min(), ys.max() + 1
    return bgr_r[y1:y2, x1:x2], alpha_r[y1:y2, x1:x2]


def paste(
    bg: np.ndarray,
    patch_bgr: np.ndarray,
    patch_alpha: np.ndarray,
    x: int,
    y: int,
) -> None:
    h, w = patch_bgr.shape[:2]
    H, W = bg.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + w), min(H, y + h)
    if x2 <= x1 or y2 <= y1:
        return
    px1, py1 = x1 - x, y1 - y
    px2, py2 = px1 + (x2 - x1), py1 + (y2 - y1)
    region = bg[y1:y2, x1:x2].astype(np.float32)
    patch = patch_bgr[py1:py2, px1:px2].astype(np.float32)
    a = patch_alpha[py1:py2, px1:px2][..., None]
    bg[y1:y2, x1:x2] = (patch * a + region * (1 - a)).astype(np.uint8)


def weighted_choice(pool: dict[int, List[Crop]], weights: dict[int, float], rng: random.Random) -> int:
    eligible = [c for c, items in pool.items() if items]
    w = [weights.get(c, 1.0) for c in eligible]
    return rng.choices(eligible, weights=w, k=1)[0]


def generate(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    class_ids = {int(c) for c in args.classes.split(",")}
    crops_by_class = extract_crops(class_ids)
    for c in class_ids:
        print(f"  crops[{NAMES.get(c, c)}] = {len(crops_by_class.get(c, []))}")
    if not any(crops_by_class.values()):
        raise SystemExit("No crops extracted for the requested --classes; nothing to do.")

    backgrounds = load_backgrounds()
    if not backgrounds:
        raise SystemExit(f"No background frames listed in {BACKGROUND}")

    out_img_dir = Path(args.out) / "images" / "train"
    out_lbl_dir = Path(args.out) / "labels" / "train"
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    class_counts = {c: 0 for c in class_ids}
    made = 0
    for i in range(args.count):
        bg_name = rng.choice(backgrounds)
        bg_path = RAW_FRAMES / bg_name
        bg_img = cv2.imread(str(bg_path))
        if bg_img is None:
            continue
        bg_img = bg_img.copy()
        H, W = bg_img.shape[:2]

        n_crops = rng.randint(args.min_crops, args.max_crops)
        placed_boxes: List[Tuple[float, float, float, float]] = []
        lines: List[str] = []
        for _ in range(n_crops):
            cls_id = weighted_choice(crops_by_class, DEFAULT_CLASS_WEIGHTS, rng)
            crop = rng.choice(crops_by_class[cls_id])
            angle = rng.uniform(0, 360)
            scale = rng.uniform(args.scale_min, args.scale_max)
            patch_bgr, patch_alpha = rotate_scale(crop, angle, scale)
            ph, pw = patch_bgr.shape[:2]
            if ph >= H or pw >= W or ph < 2 or pw < 2:
                continue

            for _attempt in range(MAX_PLACEMENT_ATTEMPTS):
                x = rng.randint(0, W - pw)
                y = rng.randint(0, H - ph)
                box = (float(x), float(y), float(x + pw), float(y + ph))
                if all(iou_xyxy(box, b) <= PASTE_IOU_CAP for b in placed_boxes):
                    bg_region = bg_img[y : y + ph, x : x + pw]
                    matched_bgr = match_color(patch_bgr, patch_alpha, bg_region)
                    paste(bg_img, matched_bgr, patch_alpha, x, y)
                    placed_boxes.append(box)
                    cx = (x + pw / 2) / W
                    cy = (y + ph / 2) / H
                    nw = pw / W
                    nh = ph / H
                    lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                    class_counts[cls_id] += 1
                    break

        if not lines:
            continue  # every placement attempt collided; skip this sample rather than emit an empty file

        name = f"synthcp_{made:06d}"
        cv2.imwrite(str(out_img_dir / f"{name}.jpg"), bg_img)
        (out_lbl_dir / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        made += 1

    readme = f"""# Synthetic copy-paste augmentation

Generated by `scripts/aug_copy_paste.py`. Do **not** use for evaluation — this
is not real footage, only for supplementing the train split.

Command:
```
.venv/bin/python scripts/aug_copy_paste.py --count {args.count} --seed {args.seed} \\
    --classes {args.classes} --min-crops {args.min_crops} --max-crops {args.max_crops} \\
    --scale-min {args.scale_min} --scale-max {args.scale_max} --out {args.out}
```

{made} images generated, train split only. Class counts (pasted boxes):
{ {NAMES.get(c, c): n for c, n in class_counts.items()} }

Not wired into `scripts/label_aerial.py`'s `EXTERNAL_TRAIN_SOURCES` automatically —
see the module docstring in `aug_copy_paste.py` for how to fold this in deliberately.
"""
    (Path(args.out) / "README.md").write_text(readme, encoding="utf-8")

    print(f"\nWrote {made}/{args.count} synthetic images -> {out_img_dir}")
    print(f"Class counts (pasted boxes): { {NAMES.get(c, c): n for c, n in class_counts.items()} }")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--count", type=int, default=300, help="Number of synthetic images to generate")
    p.add_argument("--out", default=str(ROOT / "data" / "datasets" / "model_b_aerial_synthetic"))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--min-crops", type=int, default=1)
    p.add_argument("--max-crops", type=int, default=3)
    p.add_argument(
        "--classes",
        default="0,1,2",
        help="Comma-separated class ids eligible as paste sources (default: pothole,road_crack,manhole)",
    )
    p.add_argument("--scale-min", type=float, default=0.7)
    p.add_argument("--scale-max", type=float, default=1.3)
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    generate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
