#!/usr/bin/env python3
"""Score aerial weights on the hold-out clip and compare two checkpoints.

The hold-out split (`images/test`, clip3) never enters training, so this is the only
honest answer to "did it get better". Writes JSON next to the run for later diffs.

  .venv/bin/python scripts/eval_aerial.py --weights models/infra-b-road-aerial.pt
  .venv/bin/python scripts/eval_aerial.py --weights new.pt --baseline docs/eval/baseline.json
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
    p.add_argument("--weights", default=str(ROOT / "models" / "infra-b-road-aerial.pt"))
    p.add_argument("--data", default=str(DEFAULT_DATA))
    p.add_argument("--split", default="test", choices=["test", "val", "train"])
    p.add_argument("--device", default=None, help="cpu / mps / 0")
    p.add_argument("--imgsz", type=int, default=640)
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

    result = evaluate(
        weights=weights,
        data_yaml=resolved,
        split=args.split,
        device=args.device,
        imgsz=args.imgsz,
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
