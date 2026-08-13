#!/usr/bin/env python3
"""Train Model B (pothole / waste / road damage) with Ultralytics YOLO.

Examples:
  python scripts/train_model_b.py --data configs/model_b_road.data.yaml --epochs 40 --name train_road_rdd
  python scripts/train_model_b.py --epochs 80 --model yolov8n.pt
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.pipeline.train_utils import count_dataset_images, materialize_data_yaml

DEFAULT_DATA = ROOT / "configs" / "model_b.data.yaml"
DEFAULT_OUT = ROOT / "runs" / "model_b"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train City Vision Model B")
    p.add_argument("--data", default=str(DEFAULT_DATA), help="Ultralytics data YAML")
    p.add_argument("--model", default="yolov8n.pt", help="Base checkpoint to fine-tune")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default=None, help="cpu / 0 / mps")
    p.add_argument("--project", default=str(ROOT / "runs" / "model_b"))
    p.add_argument("--name", default="train")
    p.add_argument("--resume", default=None, help="Resume from last.pt / best.pt")
    p.add_argument(
        "--export-to",
        default=str(ROOT / "models" / "infra-b-v1.pt"),
        help="Copy best.pt here after training",
    )
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--patience", type=int, default=20)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_yaml = Path(args.data)
    if not data_yaml.is_absolute():
        cand = (ROOT / data_yaml).resolve()
        data_yaml = cand if cand.exists() else data_yaml.resolve()
    if not data_yaml.exists():
        raise SystemExit(f"Missing data yaml: {data_yaml}")

    n_img, n_lbl, ds_root = count_dataset_images(data_yaml)
    if n_img == 0 or n_lbl == 0:
        raise SystemExit(
            "Dataset boş.\n"
            f"  root: {ds_root}\n"
            f"  images/train: {n_img}\n"
            f"  labels/train: {n_lbl}\n"
            "Önce: python scripts/prepare_rdd2022.py --country Czech\n"
            "veya CVAT export → data/datasets/model_b/"
        )

    train_yaml = materialize_data_yaml(data_yaml)
    print(f"Dataset: {ds_root} (train images={n_img}, labels={n_lbl})")

    from ultralytics import YOLO

    if args.resume:
        model = YOLO(args.resume)
        results = model.train(resume=True)
    else:
        model = YOLO(args.model)
        results = model.train(
            data=str(train_yaml),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            project=args.project,
            name=args.name,
            workers=args.workers,
            patience=args.patience,
            exist_ok=True,
        )

    run_dir = Path(args.project) / args.name
    best = run_dir / "weights" / "best.pt"
    if not best.exists():
        save_dir = Path(getattr(results, "save_dir", run_dir))
        best = save_dir / "weights" / "best.pt"

    if best.exists() and args.export_to:
        dest = Path(args.export_to)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, dest)
        print(f"Best weights → {dest.resolve()}")
        print("Pipeline:")
        print(f"  detection.model_b: {dest.as_posix()}")
        print(
            "  python scripts/run_pipeline.py --source data/samples/demo.mp4 "
            f"--output outputs/demo_b --model-b {dest.as_posix()}"
        )
    else:
        print(f"Training finished. Check weights under {run_dir}")

    try:
        metrics = model.val(data=str(train_yaml))
        maps = getattr(metrics, "box", None)
        if maps is not None:
            print(f"mAP50: {getattr(maps, 'map50', 'n/a')}")
            print(f"mAP50-95: {getattr(maps, 'map', 'n/a')}")
    except Exception as exc:  # noqa: BLE001
        print(f"Val skipped: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
