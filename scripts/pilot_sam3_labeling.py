#!/usr/bin/env python3
"""SAM3 pilot — does text-prompted open-vocabulary detection help our aerial marking speed?

Run with the isolated pilot env (needs Python >=3.10, not the project .venv):

  .venv-sam3-pilot/bin/python scripts/pilot_sam3_labeling.py [--n 15]

For each sampled hand-labeled frame in data/datasets/model_b_aerial, prompts SAM3
with a short text phrase per class (pothole / manhole / crack / damage) and matches
predicted boxes against our ground-truth boxes by IoU. The vision encoder runs once
per frame and the text encoder once per class prompt (both cached and reused), and
each frame's raw model output is post-processed at every threshold in THRESHOLDS
without re-running the model, to calibrate a score cutoff. Reports per-class
recall/precision/mean-IoU per threshold, per-frame latency, and basic instance-mask
stats — enough to tell whether SAM3 is worth wiring into scripts/label_aerial.py as
an accept-or-fix suggestion, before building any UI.

Note: ground truth here is bounding boxes only (no hand-labeled polygons), so mask
quality below is a presence/size sanity check, not a mask-IoU benchmark.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "datasets" / "model_b_aerial"
FRAMES = DS / "raw_frames"
LABELS = DS / "labels_hand"

NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
# One phrase per class, picked from a first pass over several wordings (see git history
# of this script / conversation).
PROMPTS = {
    0: "pothole",
    1: "crack in pavement",
    2: "manhole cover",
    3: "damaged road surface",
}
THRESHOLDS = [0.15, 0.3, 0.5, 0.7]


def read_boxes(name: str) -> list[tuple[int, float, float, float, float]]:
    path = LABELS / (Path(name).stem + ".txt")
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls, xc, yc, w, h = int(parts[0]), *map(float, parts[1:])
        out.append((cls, xc, yc, w, h))
    return out


def yolo_to_xyxy(box, img_w, img_h):
    _, xc, yc, w, h = box
    x1 = (xc - w / 2) * img_w
    y1 = (yc - h / 2) * img_h
    x2 = (xc + w / 2) * img_w
    y2 = (yc + h / 2) * img_h
    return x1, y1, x2, y2


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def sample_frames(n: int, seed: int) -> list[str]:
    """Stratified sample: up to half hard negatives (frames with no labels at all),
    so precision reflects false positives on empty frames too, not just recall on
    mostly-positive frames."""
    files = sorted(LABELS.glob("*.txt"))
    positives, negatives = [], []
    for f in files:
        (positives if read_boxes(f.name) else negatives).append(f.stem)
    random.seed(seed)
    random.shuffle(positives)
    random.shuffle(negatives)
    n_neg = min(len(negatives), n // 2)
    n_pos = min(len(positives), n - n_neg)
    picked = positives[:n_pos] + negatives[:n_neg]
    random.shuffle(picked)
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15, help="number of frames to sample")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--iou-match", type=float, default=0.3, help="IoU to count a prediction as a match")
    ap.add_argument("--mask-threshold", type=float, default=0.5, help="pixel mask binarization threshold")
    ap.add_argument("--model", default="facebook/sam3")
    ap.add_argument("--revision", default=None, help="pin a model revision/commit for a reproducible manifest")
    args = ap.parse_args()

    import torch
    from transformers import Sam3Model, Sam3Processor

    if torch.cuda.is_available():
        device, dtype = "cuda", torch.bfloat16
    elif torch.backends.mps.is_available():
        device, dtype = "mps", torch.float32
    else:
        device, dtype = "cpu", torch.float32

    print(f"loading {args.model}@{args.revision or 'main'} on {device} ({dtype}) ...")
    t0 = time.time()
    model = Sam3Model.from_pretrained(args.model, revision=args.revision, dtype=dtype).to(device).eval()
    processor = Sam3Processor.from_pretrained(args.model, revision=args.revision)
    resolved_revision = getattr(model.config, "_commit_hash", None) or args.revision or "main"
    print(f"loaded in {time.time() - t0:.1f}s (revision={resolved_revision})")

    # Text embedding depends only on the prompt, not the frame — compute each class's
    # prompt once and reuse it for every frame below.
    text_cache: dict[int, tuple] = {}
    for cls, phrase in PROMPTS.items():
        text_inputs = processor(text=phrase, return_tensors="pt").to(device)
        with torch.no_grad():
            text_embeds = model.get_text_features(
                input_ids=text_inputs["input_ids"],
                attention_mask=text_inputs["attention_mask"],
                return_dict=True,
            )
        text_cache[cls] = (text_embeds, text_inputs["attention_mask"])

    stems = sample_frames(args.n, args.seed)
    print(f"sampled {len(stems)} frames: {stems}\n")

    stats = {
        c: {t: {"gt": 0, "matched_gt": 0, "pred": 0, "matched_pred": 0, "iou_sum": 0.0} for t in THRESHOLDS}
        for c in NAMES
    }
    mask_stats = {c: {"frames": 0, "empty_masks": 0, "mean_mask_px": 0.0} for c in NAMES}
    latencies = []
    mid_threshold = THRESHOLDS[len(THRESHOLDS) // 2]

    for stem in stems:
        img_path = FRAMES / f"{stem}.jpg"
        if not img_path.exists():
            print(f"skip {stem}: no image")
            continue
        image = Image.open(img_path).convert("RGB")
        w, h = image.size
        gt_boxes = read_boxes(stem)
        gt_by_cls: dict[int, list] = {c: [] for c in NAMES}
        for b in gt_boxes:
            gt_by_cls[b[0]].append(yolo_to_xyxy(b, w, h))

        gt_summary = ", ".join(f"{NAMES[c]}={len(v)}" for c, v in gt_by_cls.items() if v)
        print(f"--- {stem} --- gt: {gt_summary or '(none, hard negative)'}")

        # Vision embedding depends only on the frame, not the prompt — encode once and
        # reuse it for every class prompt below instead of re-encoding per prompt.
        image_inputs = processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            vision_embeds = model.get_vision_features(pixel_values=image_inputs["pixel_values"])

        frame_t0 = time.time()
        for cls, phrase in PROMPTS.items():
            gts = gt_by_cls[cls]
            text_embeds, attention_mask = text_cache[cls]
            with torch.no_grad():
                outputs = model(vision_embeds=vision_embeds, text_embeds=text_embeds, attention_mask=attention_mask)

            mid_preds = None
            for thr in THRESHOLDS:
                result = processor.post_process_object_detection(outputs, threshold=thr, target_sizes=[(h, w)])[0]
                pred_boxes = result["boxes"].tolist()
                if thr == mid_threshold:
                    mid_preds = (pred_boxes, result["scores"].tolist())

                s = stats[cls][thr]
                s["pred"] += len(pred_boxes)
                matched_gt_idx = set()
                for pb in pred_boxes:
                    best_iou, best_j = 0.0, -1
                    for j, gb in enumerate(gts):
                        v = iou(pb, gb)
                        if v > best_iou:
                            best_iou, best_j = v, j
                    if best_iou >= args.iou_match and best_j not in matched_gt_idx:
                        matched_gt_idx.add(best_j)
                        s["matched_pred"] += 1
                        s["iou_sum"] += best_iou
                s["matched_gt"] += len(matched_gt_idx)

            # Instance masks reuse the same outputs — no extra forward pass.
            seg_result = processor.post_process_instance_segmentation(
                outputs, threshold=mid_threshold, mask_threshold=args.mask_threshold, target_sizes=[(h, w)]
            )[0]
            masks = seg_result["masks"]
            mask_stats[cls]["frames"] += 1
            if len(masks) == 0:
                mask_stats[cls]["empty_masks"] += 1
            else:
                mask_stats[cls]["mean_mask_px"] += sum(m.sum().item() for m in masks) / len(masks)

            pred_boxes, scores = mid_preds
            print(
                f"    '{phrase}' @thr={mid_threshold}: {len(pred_boxes)} preds "
                f"(scores {[round(sc, 2) for sc in scores[:5]]}), masks={len(masks)}, gt={len(gts)}"
            )

        for c in NAMES:
            n_gt = len(gt_by_cls[c])
            for thr in THRESHOLDS:
                stats[c][thr]["gt"] += n_gt
        latencies.append(time.time() - frame_t0)

    print("\n=== summary (per class, per threshold) ===")
    for c, name in NAMES.items():
        for thr in THRESHOLDS:
            s = stats[c][thr]
            recall = s["matched_gt"] / s["gt"] if s["gt"] else float("nan")
            precision = s["matched_pred"] / s["pred"] if s["pred"] else float("nan")
            mean_iou = s["iou_sum"] / s["matched_pred"] if s["matched_pred"] else float("nan")
            print(
                f"{name:12s} thr={thr:.2f} gt={s['gt']:4d} pred={s['pred']:4d} "
                f"recall={recall:.2f} precision={precision:.2f} mean_iou_on_match={mean_iou:.2f}"
            )
        ms = mask_stats[c]
        empty_rate = ms["empty_masks"] / ms["frames"] if ms["frames"] else float("nan")
        mean_px = ms["mean_mask_px"] / ms["frames"] if ms["frames"] else float("nan")
        print(
            f"{name:12s} mask@thr={mid_threshold}: empty_rate={empty_rate:.2f} mean_mask_px={mean_px:.0f} "
            "(no gt masks available — presence/size sanity check only)"
        )

    if latencies:
        print(
            f"\nper-frame time ({len(PROMPTS)} prompts, 1 vision encode + {len(PROMPTS)} text lookups from cache): "
            f"mean={sum(latencies) / len(latencies):.2f}s min={min(latencies):.2f}s max={max(latencies):.2f}s"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
