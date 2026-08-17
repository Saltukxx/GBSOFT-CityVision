#!/usr/bin/env python3
"""Prepare SVRDD (street-view road damage) → YOLO Model B road bootstrap.

Downloads ShuoZheLi/SVRDD_YOLO from Hugging Face and remaps:
  pothole              → 0 pothole
  * crack              → 1 road_crack
  manhole cover        → 2 manhole
  * patch              → hard-negative (image kept, boxes dropped)

Does not overwrite data/datasets/model_b_road (RoadEye).

Example:
  python scripts/prepare_svrdd.py
  python scripts/prepare_svrdd.py --max-train 800 --max-val 200
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.pipeline.svrdd import map_objects_to_yolo_lines

OUT = ROOT / "data" / "datasets" / "model_b_svrdd"
REPO = "ShuoZheLi/SVRDD_YOLO"
CFG = ROOT / "configs" / "model_b_svrdd.data.yaml"
SPLIT_ZIPS = {"train": "train.zip", "val": "validation.zip"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare SVRDD → YOLO Model B road")
    p.add_argument("--max-train", type=int, default=None)
    p.add_argument("--max-val", type=int, default=None)
    p.add_argument(
        "--skip-hard-negatives",
        action="store_true",
        help="Drop images that have no pothole/crack/manhole box after remap",
    )
    return p


def _load_token() -> str | None:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return token
    env_path = ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"} and v.strip():
            return v.strip().strip('"').strip("'")
    return None


def _safe_stem(row: dict, split_name: str, index: int) -> str:
    image_id = str(row.get("image_id") or "").strip()
    if image_id:
        return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in image_id)
    file_name = str(row.get("file_name") or "")
    if file_name:
        return Path(file_name).stem
    return f"{split_name}_{index:05d}"


def _download_zip(split_name: str) -> Path:
    name = SPLIT_ZIPS[split_name]
    print(f"Downloading {name} …", flush=True)
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(REPO, name, repo_type="dataset"))


def _member_for_row(row: dict, zip_names: set[str]) -> str | None:
    file_name = str(row.get("file_name") or "").lstrip("./")
    if file_name in zip_names:
        return file_name
    image_id = str(row.get("image_id") or "").strip()
    if image_id:
        hits = [n for n in zip_names if Path(n).stem == image_id]
        if len(hits) == 1:
            return hits[0]
    return None


def _export_split(
    ds,
    split_name: str,
    zip_path: Path,
    limit: int | None,
    keep_hard_neg: bool,
) -> dict[str, int]:
    img_dir = OUT / "images" / split_name
    lbl_dir = OUT / "labels" / split_name
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    counts = {
        "images": 0,
        "hard_neg_images": 0,
        "missing_image": 0,
        "pothole": 0,
        "road_crack": 0,
        "manhole": 0,
        "hard_negative": 0,
        "dropped": 0,
    }
    with ZipFile(zip_path) as zf:
        zip_names = set(zf.namelist())
        total = len(ds) if limit is None else min(limit, len(ds))
        for i in range(total):
            row = ds[i]
            width = float(row.get("width") or 1024)
            height = float(row.get("height") or 1024)
            lines, stats = map_objects_to_yolo_lines(
                row.get("objects") or {},
                img_w=width,
                img_h=height,
            )
            for key in ("pothole", "road_crack", "manhole", "hard_negative", "dropped"):
                counts[key] += stats[key]
            if not lines and not keep_hard_neg:
                continue
            member = _member_for_row(row, zip_names)
            if member is None:
                counts["missing_image"] += 1
                continue
            stem = _safe_stem(row, split_name, i)
            dest_img = img_dir / f"{stem}.jpg"
            if dest_img.exists():
                stem = f"{stem}_{i:05d}"
                dest_img = img_dir / f"{stem}.jpg"
            with zf.open(member) as src, open(dest_img, "wb") as out:
                shutil.copyfileobj(src, out)
            (lbl_dir / f"{stem}.txt").write_text(
                ("\n".join(lines) + "\n") if lines else "",
                encoding="utf-8",
            )
            counts["images"] += 1
            if not lines:
                counts["hard_neg_images"] += 1
            if counts["images"] % 200 == 0:
                print(f"  {split_name}: {counts['images']}", flush=True)
    return counts


def _write_yaml() -> None:
    CFG.write_text(
        "path: data/datasets/model_b_svrdd\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: pothole\n"
        "  1: road_crack\n"
        "  2: manhole\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = _load_token()
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token
        print("HF token: loaded", flush=True)
    else:
        print(
            "HF token yok — anonim denenecek (rate limit olabilir).\n"
            "Bağlamak için: export HF_TOKEN=hf_...  veya  .env içine HF_TOKEN=...",
            flush=True,
        )

    from datasets import load_dataset
    from huggingface_hub import login

    if token:
        try:
            login(token=token, add_to_git_credential=False)
        except Exception as exc:  # noqa: BLE001
            print(f"login warn: {exc}", flush=True)

    if OUT.exists():
        shutil.rmtree(OUT)

    print(f"Loading {REPO} metadata …", flush=True)
    train = load_dataset(REPO, split="train", token=token)
    val = load_dataset(REPO, split="validation", token=token)
    train_zip = _download_zip("train")
    val_zip = _download_zip("val")

    keep_hard_neg = not args.skip_hard_negatives
    print("Export train…", flush=True)
    train_stats = _export_split(train, "train", train_zip, args.max_train, keep_hard_neg)
    print("Export val…", flush=True)
    val_stats = _export_split(val, "val", val_zip, args.max_val, keep_hard_neg)

    (OUT / "SOURCE.txt").write_text(
        f"source=huggingface:{REPO}\n"
        "paper=https://doi.org/10.1038/s41597-024-03263-7\n"
        "zenodo=https://zenodo.org/records/10100129\n"
        "license=CC BY 4.0 (dataset card / annotations)\n"
        "note=Underlying Baidu street-view imagery is subject to Baidu Maps "
        "Open Platform Terms of Service. Review before commercial "
        "redistribution of trained weights.\n"
        "map=pothole→0; cracks→1 road_crack; manhole→2; patch→hard-negative\n",
        encoding="utf-8",
    )
    _write_yaml()
    (OUT / "README.md").write_text(
        "# Model B SVRDD bootstrap (YOLO)\n\n"
        "Kaynak: [ShuoZheLi/SVRDD_YOLO](https://huggingface.co/datasets/ShuoZheLi/SVRDD_YOLO)\n\n"
        "| id | class |\n| -- | ----- |\n| 0 | pothole |\n| 1 | road_crack |\n| 2 | manhole |\n\n"
        "Yama kutuları yazılmaz; görüntü hard-negative olarak kalır.\n\n"
        "```bash\npython scripts/prepare_svrdd.py\n```\n",
        encoding="utf-8",
    )

    print(f"Done → {OUT}", flush=True)
    print(
        f"  train images: {train_stats['images']} "
        f"(hard-neg only: {train_stats['hard_neg_images']}, missing: {train_stats['missing_image']})"
    )
    print(
        f"  val images:   {val_stats['images']} "
        f"(hard-neg only: {val_stats['hard_neg_images']}, missing: {val_stats['missing_image']})"
    )
    print(
        "  instances train: "
        f"pothole={train_stats['pothole']} crack={train_stats['road_crack']} "
        f"manhole={train_stats['manhole']} "
        f"hard-neg boxes dropped={train_stats['hard_negative']}"
    )
    print(
        "Train:\n"
        "  python scripts/train_model_b.py \\\n"
        "    --data configs/model_b_svrdd.data.yaml \\\n"
        "    --epochs 40 --device mps --name train_svrdd \\\n"
        "    --export-to models/infra-b-road-svrdd.pt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
