#!/usr/bin/env python3
"""Prepare public road-damage datasets for Model B bootstrap.

Sources:
  - roadeye (default): Hugging Face YOLO pothole set (works when RDD S3 is blocked)
  - rdd: RDD2022 country zip (official S3; may 403)

Examples:
  python scripts/prepare_rdd2022.py
  python scripts/prepare_rdd2022.py --source roadeye --max-images 2000
  python scripts/prepare_rdd2022.py --source rdd --country Czech
"""

from __future__ import annotations

import argparse
import random
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "rdd2022"
OUT_DIR = ROOT / "data" / "datasets" / "model_b_road"
HF_REPO = "AkumaDachi/RoadEye_Yolo_Aug"
HF_SUBDIR = "RoadEyeUnified_SingleClass_Aug"

COUNTRY_URLS = {
    "Czech": "https://bigdatacup.s3.ap-northeast-1.amazonaws.com/2022/CRDDC2022/RDD2022/Country_Specific_Data_CRDDC2022/RDD2022_Czech.zip",
    "India": "https://bigdatacup.s3.ap-northeast-1.amazonaws.com/2022/CRDDC2022/RDD2022/Country_Specific_Data_CRDDC2022/RDD2022_India.zip",
    "Japan": "https://bigdatacup.s3.ap-northeast-1.amazonaws.com/2022/CRDDC2022/RDD2022/Country_Specific_Data_CRDDC2022/RDD2022_Japan.zip",
    "China_MotorBike": "https://bigdatacup.s3.ap-northeast-1.amazonaws.com/2022/CRDDC2022/RDD2022/Country_Specific_Data_CRDDC2022/RDD2022_China_MotorBike.zip",
    "United_States": "https://bigdatacup.s3.ap-northeast-1.amazonaws.com/2022/CRDDC2022/RDD2022/Country_Specific_Data_CRDDC2022/RDD2022_United_States.zip",
}

CLASS_MAP = {
    "D40": 0,  # pothole
    "D00": 1,  # road_crack
    "D10": 1,
    "D20": 2,  # road_damage
}

CLASS_NAMES = {0: "pothole", 1: "road_crack", 2: "road_damage"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare public dataset → YOLO Model B road")
    p.add_argument("--source", choices=["roadeye", "rdd"], default="roadeye")
    p.add_argument("--country", default="Czech", choices=sorted(COUNTRY_URLS))
    p.add_argument("--val-ratio", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--max-images", type=int, default=None)
    return p


def _reset_out(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)


def prepare_roadeye(max_images: int | None) -> dict:
    from huggingface_hub import snapshot_download

    print(f"Downloading Hugging Face dataset: {HF_REPO}")
    cache = snapshot_download(
        repo_id=HF_REPO,
        repo_type="dataset",
        allow_patterns=[f"{HF_SUBDIR}/**", "roadeye.yaml", "README.md"],
    )
    src = Path(cache) / HF_SUBDIR
    if not (src / "images" / "train").exists():
        raise SystemExit(f"Unexpected HF layout under {src}")

    _reset_out(OUT_DIR)
    stats = {"pothole": 0}
    copied = {"train": 0, "val": 0}

    for split_src, split_dst in (("train", "train"), ("val", "val"), ("valid", "val"), ("test", "val")):
        img_dir = src / "images" / split_src
        lbl_dir = src / "labels" / split_src
        if not img_dir.exists():
            continue
        images = sorted(
            [
                p
                for p in img_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            ]
        )
        if max_images is not None and split_dst == "train":
            images = images[:max_images]
        elif max_images is not None and split_dst == "val":
            images = images[: max(1, max_images // 5)]

        for img in images:
            lbl = lbl_dir / f"{img.stem}.txt"
            if not lbl.exists():
                continue
            text = lbl.read_text(encoding="utf-8").strip()
            if not text:
                continue
            # ensure class id 0 (pothole)
            lines = []
            for line in text.splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                parts[0] = "0"
                lines.append(" ".join(parts))
                stats["pothole"] += 1
            if not lines:
                continue
            shutil.copy2(img, OUT_DIR / "images" / split_dst / img.name)
            (OUT_DIR / "labels" / split_dst / f"{img.stem}.txt").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            copied[split_dst] += 1

    # write data yaml companion note
    (OUT_DIR / "SOURCE.txt").write_text(
        f"source=huggingface:{HF_REPO}/{HF_SUBDIR}\nlicense=see HF README\n",
        encoding="utf-8",
    )
    return {
        "source": "roadeye",
        "train_images": copied["train"],
        "val_images": copied["val"],
        "class_instances": stats,
    }


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"Zip already present: {dest}")
        return
    print(f"Downloading {url}")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 CityVision/0.1"})
    with urlopen(req) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)


def _extract(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / ".extracted"
    if marker.exists():
        return
    print(f"Extracting {zip_path.name} …")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    marker.write_text("ok\n", encoding="utf-8")


def _find_pairs(root: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for xml in root.rglob("*.xml"):
        stem = xml.stem
        candidates = [
            xml.parent.parent / "images" / f"{stem}.jpg",
            xml.parent.parent / "images" / f"{stem}.JPG",
            xml.parent.parent / "images" / f"{stem}.jpeg",
            xml.parent.parent / "images" / f"{stem}.png",
        ]
        img = next((c for c in candidates if c.exists()), None)
        if img is None:
            hits = list(xml.parent.parent.rglob(f"{stem}.jp*g"))
            img = hits[0] if hits else None
        if img is not None:
            pairs.append((img, xml))
    return pairs


def _voc_to_yolo(xml_path: Path) -> list[str]:
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    if size is None:
        return []
    w = float(size.findtext("width") or 0)
    h = float(size.findtext("height") or 0)
    if w <= 0 or h <= 0:
        return []
    lines: list[str] = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip()
        if name not in CLASS_MAP:
            continue
        bb = obj.find("bndbox")
        if bb is None:
            continue
        xmin = float(bb.findtext("xmin") or 0)
        ymin = float(bb.findtext("ymin") or 0)
        xmax = float(bb.findtext("xmax") or 0)
        ymax = float(bb.findtext("ymax") or 0)
        xmin, ymin = max(0.0, xmin), max(0.0, ymin)
        xmax, ymax = min(w, xmax), min(h, ymax)
        if xmax <= xmin or ymax <= ymin:
            continue
        xc = ((xmin + xmax) / 2.0) / w
        yc = ((ymin + ymax) / 2.0) / h
        bw = (xmax - xmin) / w
        bh = (ymax - ymin) / h
        lines.append(f"{CLASS_MAP[name]} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    return lines


def prepare_rdd(country: str, val_ratio: float, seed: int, max_images: int | None, skip_download: bool) -> dict:
    url = COUNTRY_URLS[country]
    zip_path = RAW_DIR / f"RDD2022_{country}.zip"
    extract_dir = RAW_DIR / country
    if not skip_download:
        try:
            _download(url, zip_path)
        except HTTPError as exc:
            raise SystemExit(
                f"RDD S3 download failed ({exc.code}). "
                "Use default source instead:\n"
                "  python scripts/prepare_rdd2022.py --source roadeye"
            ) from exc
        _extract(zip_path, extract_dir)

    pairs = _find_pairs(extract_dir)
    if max_images:
        pairs = pairs[:max_images]
    if not pairs:
        raise SystemExit(f"No pairs under {extract_dir}")

    random.Random(seed).shuffle(pairs)
    n_val = max(1, int(len(pairs) * val_ratio)) if len(pairs) > 5 else max(0, len(pairs) // 5)
    val_set = set(pairs[:n_val])
    _reset_out(OUT_DIR)
    stats = {n: 0 for n in CLASS_NAMES.values()}
    kept = 0
    for img, xml in pairs:
        lines = _voc_to_yolo(xml)
        if not lines:
            continue
        split = "val" if (img, xml) in val_set else "train"
        dst_img = OUT_DIR / "images" / split / img.name
        dst_lbl = OUT_DIR / "labels" / split / f"{img.stem}.txt"
        shutil.copy2(img, dst_img)
        dst_lbl.write_text("\n".join(lines) + "\n", encoding="utf-8")
        kept += 1
        for line in lines:
            stats[CLASS_NAMES[int(line.split()[0])]] += 1
    return {
        "source": f"rdd:{country}",
        "images_with_labels": kept,
        "train_images": len(list((OUT_DIR / "images" / "train").glob("*"))),
        "val_images": len(list((OUT_DIR / "images" / "val").glob("*"))),
        "class_instances": stats,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source == "roadeye":
        summary = prepare_roadeye(args.max_images)
    else:
        summary = prepare_rdd(
            args.country, args.val_ratio, args.seed, args.max_images, args.skip_download
        )

    # keep config in sync for pothole-only bootstrap
    cfg = ROOT / "configs" / "model_b_road.data.yaml"
    cfg.write_text(
        "path: data/datasets/model_b_road\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: pothole\n",
        encoding="utf-8",
    )

    print("Done →", OUT_DIR.resolve())
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("Train:")
    print(
        "  python scripts/train_model_b.py --data configs/model_b_road.data.yaml "
        "--epochs 40 --name train_roadeye --export-to models/infra-b-road.pt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
