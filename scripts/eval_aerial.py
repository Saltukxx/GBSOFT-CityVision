#!/usr/bin/env python3
"""Score aerial weights on the hold-out clip and compare two checkpoints.

The hold-out split (`images/test`, clip3) never enters training, so this is the only
honest answer to "did it get better". Writes JSON next to the run for later diffs.

Accepts either an Ultralytics `.pt` (YOLO) or an RF-DETR `.pth` checkpoint — the two
live in separate venvs with no package overlap (`.venv` has ultralytics, `.venv-rfdetr`
has rfdetr/torchmetrics/pycocotools), so run each weight type with its own interpreter:

  .venv/bin/python scripts/eval_aerial.py --weights models/infra-b-road-aerial.pt
  .venv/bin/python scripts/eval_aerial.py --weights new.pt --baseline docs/eval/baseline.json
  .venv-rfdetr/bin/python scripts/eval_aerial.py --weights models/rfdetr/v2.pth --imgsz 1280
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from cityvision.pipeline.dataset_split import split_manifest_sha
from cityvision.pipeline.eval_gate import (
    FAIL,
    MIN_SUPPORT,
    NOT_MEASURED,
    check_split_manifest,
    evaluate_gate,
    gate_verdict,
)
from cityvision.pipeline.train_utils import materialize_data_yaml

DEFAULT_DATA = ROOT / "configs" / "model_b_aerial.data.yaml"
OUT_DIR = ROOT / "docs" / "eval"


def evaluate(
    weights: Path,
    data_yaml: Path,
    split: str,
    device: Optional[str],
    imgsz: int,
    conf: float,
    iou: float,
) -> Dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(weights))
    metrics = model.val(
        data=str(data_yaml),
        split=split,
        device=device,
        imgsz=imgsz,
        conf=conf,
        iou=iou,
        plots=True,
        verbose=False,
    )
    box = metrics.box
    names = metrics.names if isinstance(metrics.names, dict) else dict(enumerate(metrics.names))

    per_class: Dict[str, Dict[str, float]] = {}
    for i, class_idx in enumerate(box.ap_class_index):
        p, r, ap50, ap = box.class_result(i)[:4]
        per_class[str(names.get(int(class_idx), class_idx))] = {
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "map50": round(float(ap50), 4),
            "map50_95": round(float(ap), 4),
        }

    return {
        "weights": str(weights),
        "split": split,
        "imgsz": imgsz,
        "conf": conf,
        "iou": iou,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall": {
            "precision": round(float(box.mp), 4),
            "recall": round(float(box.mr), 4),
            "map50": round(float(box.map50), 4),
            "map50_95": round(float(box.map), 4),
        },
        "per_class": per_class,
        "save_dir": str(getattr(metrics, "save_dir", "")),
    }


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_RFDETR_LOW_THRESH = 0.001  # collect (almost) everything so torchmetrics sees the full PR curve


def _rfdetr_load_gt(label_path: Path, w: int, h: int) -> List[Dict[str, Any]]:
    """YOLO-normalized `cls cx cy w h` -> pixel xyxy, same convention as rfdetr_tune_thresholds.py."""
    if not label_path.exists():
        return []
    out = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cls, cx, cy, bw, bh = line.split()
        cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
        out.append({"cls": int(cls), "box": [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]})
    return out


def _rfdetr_iou(a: List[float], b: List[float]) -> float:
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


def _rfdetr_precision_recall(
    per_image_preds: List[Dict[str, Any]],
    per_image_gts: List[List[Dict[str, Any]]],
    names: Dict[int, str],
    conf: float,
    iou_thresh: float,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    """Greedy IoU matching at a fixed confidence operating point (mirrors rfdetr_tune_thresholds.py).

    torchmetrics' AP is threshold-free by design, so it has no notion of "the precision
    at --conf" — that number only exists once you fix an operating point, same as
    Ultralytics reports P/R near its chosen point rather than at the raw --conf cut
    (docs/eval/README.md).
    """
    per_class: Dict[str, Dict[str, float]] = {}
    totals = {"tp": 0, "fp": 0, "fn": 0}
    for cls_id, cls_name in names.items():
        tp = fp = fn = 0
        for preds, gts in zip(per_image_preds, per_image_gts):
            gts_c = [dict(g, matched=False) for g in gts if g["cls"] == cls_id]
            preds_c = sorted(
                [p for p in preds if p["cls"] == cls_id and p["conf"] >= conf],
                key=lambda p: -p["conf"],
            )
            for p in preds_c:
                best_j, best_iou = None, iou_thresh
                for j, g in enumerate(gts_c):
                    if g["matched"]:
                        continue
                    v = _rfdetr_iou(p["box"], g["box"])
                    if v >= best_iou:
                        best_iou, best_j = v, j
                if best_j is not None:
                    gts_c[best_j]["matched"] = True
                    tp += 1
                else:
                    fp += 1
            fn += sum(1 for g in gts_c if not g["matched"])
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        per_class[cls_name] = {"precision": precision, "recall": recall}
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn
    overall_p = totals["tp"] / (totals["tp"] + totals["fp"]) if (totals["tp"] + totals["fp"]) else 0.0
    overall_r = totals["tp"] / (totals["tp"] + totals["fn"]) if (totals["tp"] + totals["fn"]) else 0.0
    return per_class, {"precision": overall_p, "recall": overall_r}


def _rfdetr_class_map(coco_result: Dict[str, Any]) -> Dict[int, float]:
    """Extract {class_id: AP} from a torchmetrics MeanAveragePrecision.compute() result.

    torchmetrics squeezes to a 0-d tensor (not a length-1 list) when exactly one class is
    present across the whole split — atleast_1d normalizes both shapes. A class with
    predictions but zero ground truth gets pycocotools' -1 sentinel; treated as 0.0 here
    since eval_gate.py's MIN_SUPPORT check is what actually decides "not measured", not
    this value.
    """
    import torch

    classes = torch.atleast_1d(coco_result.get("classes", torch.tensor([], dtype=torch.int64)))
    values = torch.atleast_1d(coco_result["map_per_class"])
    return {int(c): max(0.0, float(v)) for c, v in zip(classes.tolist(), values.tolist())}


def evaluate_rfdetr(
    weights: Path,
    data_yaml: Path,
    split: str,
    device: Optional[str],
    imgsz: int,
    conf: float,
    iou: float,
) -> Dict[str, Any]:
    """RF-DETR counterpart to `evaluate()` — same result shape, so eval_gate.py and the
    print/JSON tail of main() work unchanged regardless of which weight type ran.

    Runs under `.venv-rfdetr` (rfdetr / torchmetrics / pycocotools), not `.venv`
    (ultralytics) — the two environments do not overlap, see the module docstring.
    """
    import torch
    from PIL import Image
    from rfdetr import RFDETRMedium
    from torchmetrics.detection.mean_ap import MeanAveragePrecision

    raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = {int(k): str(v) for k, v in (raw.get("names") or {}).items()}
    root = Path(raw["path"])
    split_dir = root / raw[split]
    label_dir = split_dir.parent.parent / "labels" / split_dir.name

    # rfdetr_infer_local.py / rfdetr_tune_thresholds.py never pass `device` and rely on
    # RFDETRMedium's own auto-selection — matching that here rather than guessing at a
    # kwarg the constructor's `**kwargs` signature doesn't document.
    rfdetr_kwargs: Dict[str, Any] = {"pretrain_weights": str(weights), "resolution": imgsz}
    if device:
        rfdetr_kwargs["device"] = device
    model = RFDETRMedium(**rfdetr_kwargs)

    metric = MeanAveragePrecision(box_format="xyxy", class_metrics=True)
    per_image_preds: List[Dict[str, Any]] = []
    per_image_gts: List[List[Dict[str, Any]]] = []

    img_files = sorted(p for p in split_dir.iterdir() if p.suffix.lower() in _IMAGE_EXTS)
    for img_path in img_files:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        gts = _rfdetr_load_gt(label_dir / f"{img_path.stem}.txt", w, h)
        per_image_gts.append(gts)

        dets = model.predict(img, threshold=_RFDETR_LOW_THRESH)
        preds = [
            {"cls": int(c), "conf": float(s), "box": [float(v) for v in b]}
            for b, c, s in zip(dets.xyxy, dets.class_id, dets.confidence)
        ]
        per_image_preds.append(preds)

        metric.update(
            [
                {
                    "boxes": torch.tensor([p["box"] for p in preds], dtype=torch.float32).reshape(-1, 4),
                    "scores": torch.tensor([p["conf"] for p in preds], dtype=torch.float32),
                    "labels": torch.tensor([p["cls"] for p in preds], dtype=torch.int64),
                }
            ],
            [
                {
                    "boxes": torch.tensor([g["box"] for g in gts], dtype=torch.float32).reshape(-1, 4),
                    "labels": torch.tensor([g["cls"] for g in gts], dtype=torch.int64),
                }
            ],
        )

    coco = metric.compute()
    # torchmetrics reports mAP50-95 per class via `map_per_class` when iou_thresholds is
    # left at the COCO default (0.5:0.05:0.95); a per-class mAP50 needs a second instance
    # restricted to that single threshold — with only one threshold, its "map" collapses
    # to plain AP@0.5.
    metric50 = MeanAveragePrecision(box_format="xyxy", class_metrics=True, iou_thresholds=[0.5])
    for p, g in zip(per_image_preds, per_image_gts):
        metric50.update(
            [
                {
                    "boxes": torch.tensor([x["box"] for x in p], dtype=torch.float32).reshape(-1, 4),
                    "scores": torch.tensor([x["conf"] for x in p], dtype=torch.float32),
                    "labels": torch.tensor([x["cls"] for x in p], dtype=torch.int64),
                }
            ],
            [
                {
                    "boxes": torch.tensor([x["box"] for x in g], dtype=torch.float32).reshape(-1, 4),
                    "labels": torch.tensor([x["cls"] for x in g], dtype=torch.int64),
                }
            ],
        )
    coco50 = metric50.compute()

    map5095_by_cls = _rfdetr_class_map(coco)
    map50_by_cls = _rfdetr_class_map(coco50)

    pr_per_class, pr_overall = _rfdetr_precision_recall(per_image_preds, per_image_gts, names, conf, iou)

    per_class: Dict[str, Dict[str, float]] = {}
    for cls_id, cls_name in names.items():
        per_class[cls_name] = {
            "precision": round(pr_per_class.get(cls_name, {}).get("precision", 0.0), 4),
            "recall": round(pr_per_class.get(cls_name, {}).get("recall", 0.0), 4),
            "map50": round(map50_by_cls.get(cls_id, 0.0), 4),
            "map50_95": round(map5095_by_cls.get(cls_id, 0.0), 4),
        }

    return {
        "weights": str(weights),
        "split": split,
        "imgsz": imgsz,
        "conf": conf,
        "iou": iou,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall": {
            "precision": round(pr_overall["precision"], 4),
            "recall": round(pr_overall["recall"], 4),
            "map50": round(float(coco50["map"]), 4),
            "map50_95": round(float(coco["map"]), 4),
        },
        "per_class": per_class,
        "save_dir": "",
    }


def count_instances(split_dir: Path, names: Dict[int, str]) -> Dict[str, int]:
    """Ground-truth boxes per class in a split, so an absent class is not read as a zero score."""
    label_dir = split_dir.parent.parent / "labels" / split_dir.name
    counts = {name: 0 for name in names.values()}
    if not label_dir.exists():
        return counts
    for txt in label_dir.glob("*.txt"):
        for line in txt.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 5:
                name = names.get(int(parts[0]))
                if name:
                    counts[name] += 1
    return counts


def gate(result: Dict[str, Any]) -> Dict[str, Any]:
    return evaluate_gate(result["per_class"], result.get("support", {}))


def print_table(result: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> None:
    base_per = (baseline or {}).get("per_class", {})
    header = f"{'class':14s} {'P':>7s} {'R':>7s} {'mAP50':>8s} {'mAP50-95':>9s}"
    if baseline:
        header += f" {'ΔmAP50':>8s}"
    print("\n" + header)
    print("-" * len(header))
    for name, row in sorted(result["per_class"].items()):
        line = (
            f"{name:14s} {row['precision']:7.3f} {row['recall']:7.3f} "
            f"{row['map50']:8.3f} {row['map50_95']:9.3f}"
        )
        if baseline:
            prev = base_per.get(name, {}).get("map50")
            line += f" {row['map50'] - prev:+8.3f}" if prev is not None else f" {'-':>8s}"
        print(line)
    o = result["overall"]
    line = (
        f"{'ALL':14s} {o['precision']:7.3f} {o['recall']:7.3f} "
        f"{o['map50']:8.3f} {o['map50_95']:9.3f}"
    )
    if baseline:
        prev = baseline["overall"]["map50"]
        line += f" {o['map50'] - prev:+8.3f}"
    print(line)


def print_gate(checks: Dict[str, Any]) -> bool:
    print("\nKabul eşikleri:")
    for key, row in checks.items():
        mark = {"pass": "PASS", "fail": "FAIL", NOT_MEASURED: " -- "}[row["status"]]
        note = ""
        if row["status"] == NOT_MEASURED:
            if row["instances"] == 0:
                note = "  (bu split'te örnek yok, ölçülemedi)"
            else:
                note = f"  (n<{MIN_SUPPORT}, istatistiksel olarak ölçülemedi)"
        print(
            f"  [{mark}] {key:20s} {row['value']:.3f}  (>= {row['threshold']}, "
            f"n={row['instances']}){note}"
        )
    verdict = gate_verdict(checks)
    if verdict == FAIL:
        print(
            "\nSonuç: eşikler tutmadı — sınıf başına etiketli kutu sayısını artır "
            "(docs/aerial-data-collection.md). Sokak seviyesi setlerle birleştirme "
            "denendi ve bırakıldı, bkz. docs/training-model-b.md 0e."
        )
    elif verdict == NOT_MEASURED:
        missing = [k for k, r in checks.items() if r["status"] == NOT_MEASURED]
        print(
            "\nSonuç: karar verilemez — " + ", ".join(missing) + " bu split'te ölçülemiyor. "
            "Hold-out klibi tamamlanana kadar --split val ile bak."
        )
    else:
        print("\nSonuç: eşikler tuttu, aerial modelle devam.")
    return verdict == "pass"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate aerial Model B on the hold-out clip")
    p.add_argument(
        "--weights",
        default=str(ROOT / "models" / "infra-b-road-aerial.pt"),
        help="Ultralytics .pt (run under .venv) or RF-DETR .pth (run under .venv-rfdetr)",
    )
    p.add_argument("--data", default=str(DEFAULT_DATA))
    p.add_argument("--split", default="test", choices=["test", "val", "train"])
    p.add_argument("--device", default=None, help="cpu / mps / 0")
    p.add_argument(
        "--imgsz",
        type=int,
        default=None,
        help="default 1280 for RF-DETR .pth weights, 640 for Ultralytics .pt",
    )
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--iou", type=float, default=0.5)
    p.add_argument("--tag", default=None, help="Output name, default = weights stem")
    p.add_argument("--baseline", default=None, help="Earlier JSON to diff against")
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    weights = Path(args.weights)
    if not weights.exists():
        raise SystemExit(f"Missing weights: {weights}")

    data_yaml = Path(args.data)
    if not data_yaml.exists():
        raise SystemExit(f"Missing data yaml: {data_yaml}")
    raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    if args.split not in raw:
        raise SystemExit(
            f"data yaml has no '{args.split}' split — run: "
            "python scripts/label_aerial.py --export"
        )
    resolved = materialize_data_yaml(data_yaml)
    split_dir = Path(yaml.safe_load(resolved.read_text())["path"]) / raw[args.split]
    n_images = len(list(split_dir.glob("*"))) if split_dir.exists() else 0
    if not n_images:
        raise SystemExit(f"Split '{args.split}' is empty: {split_dir}")
    print(f"{weights.name} → split={args.split} ({n_images} images)")
    manifest = split_manifest_sha(split_dir)

    names = {int(k): str(v) for k, v in (raw.get("names") or {}).items()}

    baseline = None
    if args.baseline:
        base_path = Path(args.baseline)
        if base_path.exists():
            baseline = json.loads(base_path.read_text(encoding="utf-8"))
        else:
            print(f"(baseline yok, atlandı: {base_path})")
    try:
        warn = check_split_manifest(manifest, baseline)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if warn:
        print(f"({warn})")

    is_rfdetr = weights.suffix.lower() == ".pth"
    evaluate_fn = evaluate_rfdetr if is_rfdetr else evaluate
    imgsz = args.imgsz if args.imgsz is not None else (1280 if is_rfdetr else 640)
    result = evaluate_fn(
        weights=weights,
        data_yaml=resolved,
        split=args.split,
        device=args.device,
        imgsz=imgsz,
        conf=args.conf,
        iou=args.iou,
    )
    result["images"] = n_images
    result["support"] = count_instances(split_dir, names)
    result["split_manifest"] = manifest

    print_table(result, baseline)
    result["gate"] = gate(result)
    print_gate(result["gate"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = args.tag or weights.stem
    out = OUT_DIR / f"{tag}.{args.split}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nJSON → {out}")
    if result["save_dir"]:
        print(f"Confusion matrix → {result['save_dir']}/confusion_matrix_normalized.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
