#!/usr/bin/env python3
"""Plan A: Hugging Face GarbageOverflow → YOLO Model B waste bootstrap.

Maps all boxes to class: overflowing_container (id 0 in model_b_waste).

Auth (optional but recommended):
  export HF_TOKEN=hf_xxx
  # or: huggingface-cli login
  # or: put HF_TOKEN in .env and: set -a; source .env; set +a

Example:
  python scripts/prepare_garbage_overflow.py
  python scripts/prepare_garbage_overflow.py --max-train 3000
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "datasets" / "model_b_waste"
REPO = "jobayernayeem/GarbageOverflow"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare GarbageOverflow → YOLO waste dataset")
    p.add_argument("--max-train", type=int, default=None)
    p.add_argument("--max-val", type=int, default=None)
    return p


def _load_token() -> str | None:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return token
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"} and v.strip():
                return v.strip().strip('"').strip("'")
    return None


def _xyxy_to_yolo(x: float, y: float, w: float, h: float, img_w: float, img_h: float) -> str | None:
    if img_w <= 0 or img_h <= 0 or w <= 0 or h <= 0:
        return None
    xc = (x + w / 2.0) / img_w
    yc = (y + h / 2.0) / img_h
    bw = w / img_w
    bh = h / img_h
    if not (0 <= xc <= 1 and 0 <= yc <= 1 and 0 < bw <= 1 and 0 < bh <= 1):
        # clip gently
        xc = min(max(xc, 0.0), 1.0)
        yc = min(max(yc, 0.0), 1.0)
        bw = min(max(bw, 1e-6), 1.0)
        bh = min(max(bh, 1e-6), 1.0)
    return f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"


def _export_split(ds, split_name: str, limit: int | None) -> int:
    img_dir = OUT / "images" / split_name
    lbl_dir = OUT / "labels" / split_name
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    n = 0
    total = len(ds) if limit is None else min(limit, len(ds))
    for i in range(total):
        row = ds[i]
        image = row["image"]
        width = float(row["width"] or image.width)
        height = float(row["height"] or image.height)
        objects = row.get("objects") or {}
        bboxes = objects.get("bbox") or []
        lines = []
        for box in bboxes:
            if not box or len(box) < 4:
                continue
            x, y, w, h = (float(v) for v in box[:4])
            line = _xyxy_to_yolo(x, y, w, h, width, height)
            if line:
                lines.append(line)
        if not lines:
            continue
        stem = f"{split_name}_{i:05d}"
        image.save(img_dir / f"{stem}.jpg")
        (lbl_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        n += 1
        if n % 200 == 0:
            print(f"  {split_name}: {n}", flush=True)
    return n


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

    print(f"Loading {REPO} …", flush=True)
    train = load_dataset(REPO, split="train", token=token)
    val = load_dataset(REPO, split="validation", token=token)

    n_train = _export_split(train, "train", args.max_train)
    n_val = _export_split(val, "val", args.max_val)

    (OUT / "SOURCE.txt").write_text(
        f"source=huggingface:{REPO}\nclass=overflowing_container\n",
        encoding="utf-8",
    )
    cfg = ROOT / "configs" / "model_b_waste.data.yaml"
    cfg.write_text(
        "path: data/datasets/model_b_waste\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: overflowing_container\n",
        encoding="utf-8",
    )

    print(f"Done train={n_train} val={n_val} → {OUT}", flush=True)
    print(
        "Train:\n"
        "  python scripts/train_model_b.py \\\n"
        "    --data configs/model_b_waste.data.yaml \\\n"
        "    --epochs 40 --device mps --name train_waste_overflow \\\n"
        "    --export-to models/infra-b-waste.pt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
