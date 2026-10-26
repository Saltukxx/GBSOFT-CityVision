#!/usr/bin/env python3
"""Train Model B (aerial) with RF-DETR. Run under .venv-rfdetr, not .venv:

  .venv-rfdetr/bin/python scripts/train_rfdetr.py --epochs 60 --resolution 1280 \
      --export-to models/rfdetr/rfdetr-v3-1280-ema.pth

Continue fine-tuning from an existing checkpoint (fresh optimizer, not a true resume —
these are weights-only EMA exports with no optimizer/scheduler state):

  .venv-rfdetr/bin/python scripts/train_rfdetr.py --base-weights models/rfdetr/rfdetr-v2-1280-ema.pth \
      --export-to models/rfdetr/rfdetr-v3-1280-ema.pth
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.pipeline.dataset_split import split_manifest_sha

DEFAULT_DATA = ROOT / "configs" / "model_b_aerial.data.yaml"
DEFAULT_BASE = "rf-detr-medium.pth"
DEFAULT_PROJECT = ROOT / "runs" / "rfdetr"

_CKPT_FILENAMES = {
    "ema": "checkpoint_best_ema.pth",
    "regular": "checkpoint_best_regular.pth",
    "total": "checkpoint_best_total.pth",
}


def materialize_rfdetr_yaml(data_yaml: Path, dataset_root: Path) -> Path:
    """Write <dataset_root>/data.yaml so RF-DETR's YOLO loader can find it.

    RF-DETR's yolo.py looks for data.yaml INSIDE dataset_dir and guards against a `path:`
    that resolves outside it — unlike cityvision.pipeline.train_utils.materialize_data_yaml(),
    which is free to write into a tmp dir because Ultralytics takes an arbitrary yaml path.
    `path: .` keeps the resolved split dirs (images/train etc.) inside dataset_root.
    """
    raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    raw["path"] = "."
    out = dataset_root / "data.yaml"
    out.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train City Vision Model B (aerial) with RF-DETR")
    p.add_argument("--data", default=str(DEFAULT_DATA), help="Ultralytics-style data YAML")
    p.add_argument("--base-weights", default=DEFAULT_BASE, help="Weights to fine-tune from")
    p.add_argument(
        "--resume",
        default=None,
        help="Path to a trainer 'last.ckpt' (full optimizer/LR-scheduler/epoch state) to "
        "genuinely continue an interrupted run — NOT a checkpoint_best_*.pth (those are "
        "weights-only; pass those via --base-weights instead, which restarts the optimizer "
        "cold). --project/--name must match the run that wrote it, so its callback/best-score "
        "state resumes into the same output_dir instead of restarting fresh.",
    )
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--resolution", type=int, default=1280)
    p.add_argument("--batch-size", default="auto", help="int or 'auto'")
    p.add_argument("--device", default=None, help="cpu / mps / cuda / cuda:0")
    p.add_argument("--num-workers", type=int, default=4)
    p.add_argument("--checkpoint-interval", type=int, default=10)
    p.add_argument(
        "--no-early-stopping",
        action="store_true",
        help="Run the full --epochs regardless of val plateau (default: stop early once "
        "val mAP stops improving for --early-stopping-patience epochs — the 60-epoch scale "
        "was tuned for the old ~12-13k-image combined dataset, not our own-footage-only set)",
    )
    p.add_argument("--early-stopping-patience", type=int, default=10)
    p.add_argument("--variant", choices=sorted(_CKPT_FILENAMES), default="ema")
    p.add_argument("--project", default=str(DEFAULT_PROJECT))
    p.add_argument("--name", default="train")
    p.add_argument(
        "--export-to",
        default=None,
        help="Copy the chosen checkpoint here (default: models/rfdetr/rfdetr-<name>-<resolution>-<variant>.pth)",
    )
    p.add_argument("--notes", default=None, help="Free-text note embedded in the checkpoint")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    data_yaml = Path(args.data)
    if not data_yaml.exists():
        raise SystemExit(f"Missing data yaml: {data_yaml}")
    raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = {int(k): str(v) for k, v in (raw.get("names") or {}).items()}
    if not names:
        raise SystemExit(f"No 'names' in {data_yaml}")
    class_names = [names[i] for i in sorted(names)]
    print(f"Classes ({len(class_names)}): {class_names}")

    dataset_root = (ROOT / raw["path"]).resolve()
    rfdetr_yaml = materialize_rfdetr_yaml(data_yaml, dataset_root)

    train_dir = dataset_root / raw["train"]
    val_dir = dataset_root / raw["val"]
    manifest = {"train": split_manifest_sha(train_dir), "val": split_manifest_sha(val_dir)}

    batch_size = args.batch_size if args.batch_size == "auto" else int(args.batch_size)

    from rfdetr import RFDETRMedium

    model = RFDETRMedium(
        pretrain_weights=args.base_weights,
        resolution=args.resolution,
        num_classes=len(class_names),
    )

    output_dir = Path(args.project) / args.name
    model.train(
        dataset_dir=str(dataset_root),
        # Must be explicit: the "roboflow" default auto-detects COCO vs YOLO and can silently
        # prefer a stray COCO export sitting in dataset_dir over our real YOLO labels — the
        # leading hypothesis for why an earlier ad-hoc run's per-class metrics were missing
        # "manhole" entirely (coco.py's filter_parent_categories drops any category that only
        # ever appears as a supercategory with zero direct annotations).
        dataset_file="yolo",
        epochs=args.epochs,
        batch_size=batch_size,
        output_dir=str(output_dir),
        resume=args.resume,
        device=args.device,
        num_workers=args.num_workers,
        checkpoint_interval=args.checkpoint_interval,
        early_stopping=not args.no_early_stopping,
        early_stopping_patience=args.early_stopping_patience,
        # Watch the checkpoint variant we actually export, not the "regular" default —
        # otherwise early stopping can fire on the regular model's plateau while EMA
        # (what --variant ema ships) is still improving, or vice versa.
        early_stopping_use_ema=(args.variant == "ema"),
        class_names=class_names,
        notes={"data_yaml": str(rfdetr_yaml), "split_manifest": manifest, "notes": args.notes},
    )

    ckpt_src = output_dir / _CKPT_FILENAMES[args.variant]
    if not ckpt_src.exists():
        raise SystemExit(f"Expected checkpoint missing: {ckpt_src}")

    dest = Path(
        args.export_to
        or ROOT / "models" / "rfdetr" / f"rfdetr-{args.name}-{args.resolution}-{args.variant}.pth"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ckpt_src, dest)

    manifest_out = {
        "checkpoint": str(dest),
        "base_weights": args.base_weights,
        "epochs": args.epochs,
        "resolution": args.resolution,
        "batch_size": args.batch_size,
        "variant": args.variant,
        "data_yaml": str(data_yaml),
        "split_manifest": manifest,
        "output_dir": str(output_dir),
    }
    (dest.parent / f"{dest.stem}.train_manifest.json").write_text(
        json.dumps(manifest_out, indent=2), encoding="utf-8"
    )

    print(f"Weights -> {dest}")
    print(f"Training config -> {output_dir / 'training_config.json'}")
    print(f"Metrics -> {output_dir / 'metrics.csv'}")
    print(
        f"Eval: .venv-rfdetr/bin/python scripts/eval_aerial.py --weights {dest} "
        f"--imgsz {args.resolution}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
