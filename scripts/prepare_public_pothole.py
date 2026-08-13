#!/usr/bin/env python3
"""Download RoadEye pothole YOLO dataset from Hugging Face into model_b_road.

Example:
  python scripts/prepare_public_pothole.py --train-limit 1500 --val-limit 300
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "datasets" / "model_b_road"
REPO = "AkumaDachi/RoadEye_Yolo_Aug"
PREFIX = "RoadEyeUnified_SingleClass_Aug/"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--train-limit", type=int, default=1500)
    p.add_argument("--val-limit", type=int, default=300)
    p.add_argument("--seed", type=int, default=42)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from huggingface_hub import hf_hub_download, list_repo_files

    if OUT.exists():
        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)

    print("Listing HF files…", flush=True)
    files = set(list_repo_files(REPO, repo_type="dataset"))

    def collect(split_name: str, dest: str, limit: int) -> int:
        imgs = sorted(
            f
            for f in files
            if f.startswith(f"{PREFIX}images/{split_name}/")
            and Path(f).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        )
        print(f"{split_name}: {len(imgs)} available → take {min(limit, len(imgs))}", flush=True)
        n = 0
        for f in imgs[:limit]:
            stem = Path(f).stem
            lbl = f"{PREFIX}labels/{split_name}/{stem}.txt"
            if lbl not in files:
                continue
            img_local = Path(hf_hub_download(REPO, f, repo_type="dataset"))
            lbl_local = Path(hf_hub_download(REPO, lbl, repo_type="dataset"))
            text = lbl_local.read_text(encoding="utf-8").strip()
            if not text:
                continue
            lines = []
            for line in text.splitlines():
                parts = line.split()
                if len(parts) == 5:
                    parts[0] = "0"
                    lines.append(" ".join(parts))
            if not lines:
                continue
            shutil.copy2(img_local, OUT / "images" / dest / Path(f).name)
            (OUT / "labels" / dest / f"{stem}.txt").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            n += 1
            if n % 25 == 0:
                print(f"  {dest}: {n}", flush=True)
        return n

    n_train = collect("train", "train", args.train_limit)
    n_val = collect("val", "val", args.val_limit)
    if n_val == 0:
        n_val = collect("valid", "val", args.val_limit)
    if n_val == 0 and n_train > 10:
        # carve val from train
        imgs = list((OUT / "images" / "train").glob("*"))
        random.Random(args.seed).shuffle(imgs)
        move_n = max(1, int(len(imgs) * 0.2))
        for img in imgs[:move_n]:
            lbl = OUT / "labels" / "train" / f"{img.stem}.txt"
            if not lbl.exists():
                continue
            shutil.move(str(img), str(OUT / "images" / "val" / img.name))
            shutil.move(str(lbl), str(OUT / "labels" / "val" / f"{img.stem}.txt"))
            n_val += 1
            n_train -= 1

    (OUT / "SOURCE.txt").write_text(f"source=huggingface:{REPO}\n", encoding="utf-8")
    (ROOT / "configs" / "model_b_road.data.yaml").write_text(
        "path: data/datasets/model_b_road\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: pothole\n",
        encoding="utf-8",
    )
    print(f"Done train={n_train} val={n_val} → {OUT}", flush=True)
    print(
        "Train: python scripts/train_model_b.py --data configs/model_b_road.data.yaml "
        "--epochs 40 --device mps --name train_roadeye --export-to models/infra-b-road.pt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
