#!/usr/bin/env python3
"""Sweep confidence thresholds per-class on the own-footage validation set to find
the F1-optimal threshold for each class, instead of using one flat threshold for
all classes at inference time.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
from PIL import Image
from rfdetr import RFDETRMedium

CKPT = "models/rfdetr/rfdetr-v2-1280-ema.pth"
NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
VAL_IMAGES = Path("data/datasets/own_footage_new/images/val")
VAL_LABELS = Path("data/datasets/own_footage_new/labels/val")
LOW_THRESH = 0.05  # collect everything above this, sweep thresholds post-hoc
IOU_MATCH = 0.5
THRESH_GRID = [round(0.05 + 0.05 * i, 2) for i in range(19)]  # 0.05..0.95


def load_gt(label_path: Path, w: int, h: int) -> list[dict]:
    if not label_path.exists():
        return []
    out = []
    for line in label_path.read_text().splitlines():
        if not line.strip():
            continue
        cls, cx, cy, bw, bh = line.split()
        cls = int(cls)
        cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
        out.append({"cls": NAMES[cls], "box": [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], "matched": False})
    return out


def iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / (area_a + area_b - inter)


def main() -> None:
    model = RFDETRMedium(pretrain_weights=CKPT, resolution=1280)

    all_preds = []  # (cls, conf, box, img_id)
    all_gts = {}  # img_id -> list of gt dicts
    img_files = sorted(VAL_IMAGES.iterdir())
    print(f"Running inference on {len(img_files)} val images at low threshold...")
    for i, img_path in enumerate(img_files):
        frame = cv2.imread(str(img_path))
        h, w = frame.shape[:2]
        gt = load_gt(VAL_LABELS / (img_path.stem + ".txt"), w, h)
        all_gts[img_path.stem] = gt
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        dets = model.predict(Image.fromarray(rgb), threshold=LOW_THRESH)
        for box, cls_id, conf in zip(dets.xyxy, dets.class_id, dets.confidence):
            cls = NAMES.get(int(cls_id), str(cls_id))
            all_preds.append({"img": img_path.stem, "cls": cls, "conf": float(conf), "box": [float(v) for v in box]})
        if (i + 1) % 40 == 0:
            print(f"  {i+1}/{len(img_files)}", flush=True)

    classes = ["pothole", "road_crack", "road_damage"]
    results = {}
    for cls in classes:
        best_f1, best_t, best_stats = -1.0, 0.3, None
        for t in THRESH_GRID:
            tp = fp = fn = 0
            gts_copy = {k: [dict(g) for g in v if g["cls"] == cls] for k, v in all_gts.items()}
            preds_c = sorted(
                [p for p in all_preds if p["cls"] == cls and p["conf"] >= t], key=lambda p: -p["conf"]
            )
            for p in preds_c:
                gts = gts_copy[p["img"]]
                best_j, best_iou = None, IOU_MATCH
                for j, g in enumerate(gts):
                    if g["matched"]:
                        continue
                    v = iou(p["box"], g["box"])
                    if v >= best_iou:
                        best_iou, best_j = v, j
                if best_j is not None:
                    gts[best_j]["matched"] = True
                    tp += 1
                else:
                    fp += 1
            for gts in gts_copy.values():
                fn += sum(1 for g in gts if not g["matched"])
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            rec = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
            if f1 > best_f1:
                best_f1, best_t, best_stats = f1, t, {"precision": prec, "recall": rec, "tp": tp, "fp": fp, "fn": fn}
        results[cls] = {"threshold": best_t, "f1": best_f1, **(best_stats or {})}
        print(f"{cls}: best_threshold={best_t} F1={best_f1:.3f} {best_stats}")

    out = Path("models/rfdetr/v2_per_class_thresholds.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
