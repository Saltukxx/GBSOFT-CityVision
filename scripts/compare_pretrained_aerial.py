#!/usr/bin/env python3
"""Score off-the-shelf road-damage checkpoints on our hand-labelled drone frames.

Public models use RDD's 4 classes; we map them onto our 3 aerial classes and score
with the same matching/mAP code as eval_aerial.py, so numbers sit next to v2's.

RDD → ours: D00 longitudinal, D10 transverse → road_crack; D20 alligator → road_damage;
D40 pothole → pothole.

Two steps, because ultralytics and rfdetr live in separate venvs:

  # 1. predict (each model with its own interpreter)
  .venv-rfdetr/bin/python scripts/compare_pretrained_aerial.py predict --kind rfdetr-small \
      --weights models/external/rdd2022-rfdetr-small.pth --imgsz 512 --map 0:1,1:1,2:2,3:0 --tag rdd-rfdetr-small
  .venv/bin/python scripts/compare_pretrained_aerial.py predict --kind yolo \
      --weights models/external/YOLO26s_RDD_Base.pt --imgsz 640 --map 0:1,1:1,2:2,3:0 --tag yolo26s-rdd
  .venv-rfdetr/bin/python scripts/compare_pretrained_aerial.py predict --kind rfdetr-medium \
      --weights models/rfdetr/rfdetr-ownfootage-v2-1280-ema.pth --imgsz 1280 --tag v2

  # 2. score all of them (needs torchmetrics → .venv-rfdetr)
  .venv-rfdetr/bin/python scripts/compare_pretrained_aerial.py score --tags v2,rdd-rfdetr-small,yolo26s-rdd
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import yaml

DATA_YAML = ROOT / "configs" / "model_b_aerial.data.yaml"
OUT_DIR = ROOT / "docs" / "eval" / "pretrained-compare"
LOW_THRESH = 0.001
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def split_paths(split: str):
    raw = yaml.safe_load(DATA_YAML.read_text(encoding="utf-8"))
    root = ROOT / raw["path"]
    img_dir = root / raw[split]
    label_dir = img_dir.parent.parent / "labels" / img_dir.name
    names = {int(k): str(v) for k, v in raw["names"].items()}
    return img_dir, label_dir, names


def parse_map(spec: str | None) -> Dict[int, int] | None:
    if not spec:
        return None
    return {int(a): int(b) for a, b in (pair.split(":") for pair in spec.split(","))}


def run_tiled(img, run_one, n: int, overlap: float, nms_iou: float = 0.5):
    """Split the frame into an n×n grid of overlapping tiles, detect on each, merge with per-class NMS."""
    import torch
    from torchvision.ops import batched_nms

    W, H = img.size
    tw, th = W / (n - (n - 1) * overlap), H / (n - (n - 1) * overlap)
    sx, sy = tw * (1 - overlap), th * (1 - overlap)
    boxes, classes, confs = [], [], []
    for iy in range(n):
        for ix in range(n):
            x0, y0 = int(round(ix * sx)), int(round(iy * sy))
            x1, y1 = min(W, int(round(x0 + tw))), min(H, int(round(y0 + th)))
            b, c, s = run_one(img.crop((x0, y0, x1, y1)))
            boxes += [[bx0 + x0, by0 + y0, bx1 + x0, by1 + y0] for bx0, by0, bx1, by1 in b]
            classes += c
            confs += s
    if not boxes:
        return [], [], []
    bt, st, ct = torch.tensor(boxes), torch.tensor(confs), torch.tensor(classes)
    keep = batched_nms(bt, st, ct, nms_iou)
    return bt[keep].tolist(), ct[keep].tolist(), st[keep].tolist()


def predict(args) -> None:
    from PIL import Image

    img_dir, _, _ = split_paths(args.split)
    files = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    cls_map = parse_map(args.map)

    if args.kind == "yolo":
        from ultralytics import YOLO

        model = YOLO(args.weights)
        print("model classes:", model.names)

        def run(img):
            r = model.predict(img, imgsz=args.imgsz, conf=LOW_THRESH, verbose=False, device=args.device)[0]
            b = r.boxes
            return b.xyxy.tolist(), b.cls.int().tolist(), b.conf.tolist()
    else:
        import rfdetr

        cls = {"rfdetr-small": rfdetr.RFDETRSmall, "rfdetr-medium": rfdetr.RFDETRMedium}[args.kind]
        model = cls(pretrain_weights=args.weights, resolution=args.imgsz)

        def run_one(img):
            # rfdetr resizes internally with antialias=False; --prescale does that downscale
            # ourselves with a proper filter, then maps boxes back to source pixels.
            sx = sy = 1.0
            if args.prescale:
                filt = {"bilinear": Image.BILINEAR, "lanczos": Image.LANCZOS, "box": Image.BOX}[args.prescale]
                sx, sy = img.width / args.imgsz, img.height / args.imgsz
                img = img.resize((args.imgsz, args.imgsz), filt)
            d = model.predict(img, threshold=LOW_THRESH)
            boxes = [[x0 * sx, y0 * sy, x1 * sx, y1 * sy] for x0, y0, x1, y1 in d.xyxy.tolist()]
            return boxes, [int(c) for c in d.class_id], d.confidence.tolist()

        def run(img):
            if args.tiles <= 1:
                return run_one(img)
            return run_tiled(img, run_one, args.tiles, args.overlap)

    raw_counts: Counter = Counter()
    out: Dict[str, List[dict]] = {}
    t0 = time.time()
    for i, path in enumerate(files, 1):
        img = Image.open(path).convert("RGB")
        boxes, classes, confs = run(img)
        preds = []
        for box, c, s in zip(boxes, classes, confs):
            if s >= 0.25:
                raw_counts[c] += 1
            ours = cls_map.get(c) if cls_map is not None else c
            if ours is None:
                continue
            preds.append({"cls": ours, "conf": float(s), "box": [float(v) for v in box]})
        out[path.stem] = preds
        if i % 50 == 0:
            print(f"  {i}/{len(files)} images, {time.time() - t0:.0f}s", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{args.tag}.{args.split}.preds.json"
    meta = {
        "weights": args.weights, "kind": args.kind, "imgsz": args.imgsz, "map": args.map,
        "split": args.split, "tiles": args.tiles, "overlap": args.overlap, "prescale": args.prescale,
    }
    dest.write_text(json.dumps({"meta": meta, "preds": out}), encoding="utf-8")
    print(f"raw class ids at conf>=0.25: {dict(sorted(raw_counts.items()))}")
    print(f"{len(files)} images in {time.time() - t0:.0f}s → {dest}")


def score(args) -> None:
    import torch
    from PIL import Image
    from torchmetrics.detection.mean_ap import MeanAveragePrecision

    from eval_aerial import _rfdetr_class_map, _rfdetr_load_gt, _rfdetr_precision_recall

    img_dir, label_dir, names = split_paths(args.split)
    files = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    gts = []
    for p in files:
        w, h = Image.open(p).size
        gts.append(_rfdetr_load_gt(label_dir / f"{p.stem}.txt", w, h))
    support = Counter(names[g["cls"]] for gt in gts for g in gt)

    def t(items, with_scores):
        d = {
            "boxes": torch.tensor([x["box"] for x in items], dtype=torch.float32).reshape(-1, 4),
            "labels": torch.tensor([x["cls"] for x in items], dtype=torch.int64),
        }
        if with_scores:
            d["scores"] = torch.tensor([x["conf"] for x in items], dtype=torch.float32)
        return d

    results = {}
    for tag in args.tags.split(","):
        data = json.loads((OUT_DIR / f"{tag}.{args.split}.preds.json").read_text(encoding="utf-8"))
        preds = [data["preds"].get(p.stem, []) for p in files]
        m_all = MeanAveragePrecision(box_format="xyxy", class_metrics=True)
        m_50 = MeanAveragePrecision(box_format="xyxy", class_metrics=True, iou_thresholds=[0.5])
        # Area classes (road_damage) have fuzzy extents; mAP@0.3 shows how much of the
        # gap is box-boundary disagreement rather than missed damage.
        m_30 = MeanAveragePrecision(box_format="xyxy", class_metrics=True, iou_thresholds=[0.3])
        for p, g in zip(preds, gts):
            for m in (m_all, m_50, m_30):
                m.update([t(p, True)], [t(g, False)])
        coco, coco50, coco30 = m_all.compute(), m_50.compute(), m_30.compute()
        ap, ap50, ap30 = _rfdetr_class_map(coco), _rfdetr_class_map(coco50), _rfdetr_class_map(coco30)
        pr, pr_all = _rfdetr_precision_recall(preds, gts, names, args.conf, args.iou)
        results[tag] = {
            "meta": data["meta"],
            "overall": {
                "precision": round(pr_all["precision"], 4),
                "recall": round(pr_all["recall"], 4),
                "map30": round(float(coco30["map"]), 4),
                "map50": round(float(coco50["map"]), 4),
                "map50_95": round(float(coco["map"]), 4),
            },
            "per_class": {
                n: {
                    "precision": round(pr[n]["precision"], 4),
                    "recall": round(pr[n]["recall"], 4),
                    "map30": round(ap30.get(i, 0.0), 4),
                    "map50": round(ap50.get(i, 0.0), 4),
                    "map50_95": round(ap.get(i, 0.0), 4),
                }
                for i, n in names.items()
            },
        }

    print(f"\nsplit={args.split}  images={len(files)}  boxes={dict(support)}  P/R at conf={args.conf}")
    head = f"{'model':20s} {'class':12s} {'P':>6s} {'R':>6s} {'mAP30':>7s} {'mAP50':>7s} {'mAP50-95':>9s}"
    print(head + "\n" + "-" * len(head))
    for tag, r in results.items():
        for n, row in list(r["per_class"].items()) + [("ALL", r["overall"])]:
            print(f"{tag:20s} {n:12s} {row['precision']:6.3f} {row['recall']:6.3f} {row['map30']:7.3f} {row['map50']:7.3f} {row['map50_95']:9.3f}")
        print()
    dest = OUT_DIR / f"summary.{args.split}.json"
    dest.write_text(json.dumps({"support": dict(support), "conf": args.conf, "results": results}, indent=2), encoding="utf-8")
    print(f"→ {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--kind", required=True, choices=["yolo", "rfdetr-small", "rfdetr-medium"])
    p.add_argument("--weights", required=True)
    p.add_argument("--imgsz", type=int, required=True)
    p.add_argument("--map", default=None, help="external:ours class pairs, e.g. 0:1,1:1,2:2,3:0")
    p.add_argument("--tag", required=True)
    p.add_argument("--split", default="val")
    p.add_argument("--device", default=None)
    p.add_argument("--tiles", type=int, default=1, help="RF-DETR only: n×n tiled inference (1 = full frame)")
    p.add_argument("--overlap", type=float, default=0.15, help="tile overlap fraction")
    p.add_argument("--prescale", choices=["bilinear", "lanczos", "box"], default=None,
                   help="RF-DETR only: antialiased downscale to imgsz×imgsz before predict")
    s = sub.add_parser("score")
    s.add_argument("--tags", required=True)
    s.add_argument("--split", default="val")
    s.add_argument("--conf", type=float, default=0.25)
    s.add_argument("--iou", type=float, default=0.5)
    args = ap.parse_args()
    predict(args) if args.cmd == "predict" else score(args)


if __name__ == "__main__":
    main()
