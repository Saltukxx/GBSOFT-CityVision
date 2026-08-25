#!/usr/bin/env python3
"""Prepare UAV-PDD2023 (aerial pavement distress) → YOLO model_b_aerial classes.

Same-domain source as our own drone dataset (UAV imagery, ~30m altitude) — unlike
the street-level RDD2022/SVRDD bootstraps we deliberately keep separate
(docs/training-model-b.md §0e), this one is fair game to fold into training. Native
VOC categories remap onto the model_b_aerial class ids
(configs/model_b_aerial.data.yaml / scripts/label_aerial.py NAMES):

  longitudinal / transverse / oblique crack → 1 road_crack
  alligator crack                            → 3 road_damage
  pothole                                     → 0 pothole
  repair                                      → dropped (hard-negative candidate)

No manhole boxes in this dataset (class 2 never emitted). Output is train-only —
this is not part of our own clip-based val/test hold-out, so it always lands under
images/train, whatever split it originally had upstream.

Source: Yan & Zhang, "UAV-PDD2023: A benchmark dataset for pavement distress
detection based on UAV images" (Data in Brief, 2023).
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10630617/
  https://zenodo.org/records/8429208 — CC BY 4.0

Example:
  python scripts/prepare_uav_pdd.py
  python scripts/prepare_uav_pdd.py --max-images 200        # smoke test
  python scripts/prepare_uav_pdd.py --skip-download         # reuse cached zip

Zenodo does not support HTTP range requests on this file and the download has been
observed to run well under 1 MB/s from a home connection — 2.1 GB can take hours.
If that's the case, run this on the training host (e.g. the RunPod pod) instead,
where the link is typically much faster.
"""

from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

ZENODO_URL = "https://zenodo.org/records/8429208/files/UAV-PDD2023.zip?download=1"
RAW_DIR = ROOT / "data" / "raw" / "uav_pdd2023"
ZIP_PATH = RAW_DIR / "UAV-PDD2023.zip"
EXTRACT_DIR = RAW_DIR / "extracted"
OUT_DIR = ROOT / "data" / "datasets" / "uav_pdd2023"

# model_b_aerial class ids — must match configs/model_b_aerial.data.yaml
POTHOLE, ROAD_CRACK, MANHOLE, ROAD_DAMAGE = 0, 1, 2, 3
CLASS_NAMES = {
    POTHOLE: "pothole",
    ROAD_CRACK: "road_crack",
    MANHOLE: "manhole",
    ROAD_DAMAGE: "road_damage",
}

# Native UAV-PDD2023 categories → our class id, or None to drop (hard negative).
# Covers both the paper's abbreviations (LC/TC/OC/AC/RP/PH) and spelled-out variants,
# since the exact <name> tag text wasn't confirmed before writing this (no HTTP range
# support meant no cheap peek at the archive). Unmapped names are reported, not
# silently dropped — see `--peek` and the WARNING at the end of a run.
NAME_TO_CLASS: dict[str, int | None] = {
    "lc": ROAD_CRACK,
    "longitudinal crack": ROAD_CRACK,
    "tc": ROAD_CRACK,
    "transverse crack": ROAD_CRACK,
    "oc": ROAD_CRACK,
    "oblique crack": ROAD_CRACK,
    "ac": ROAD_DAMAGE,
    "alligator crack": ROAD_DAMAGE,
    "ph": POTHOLE,
    "pothole": POTHOLE,
    "rp": None,
    "repair": None,
}


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").replace("-", " ").split())


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"Zip already present: {dest} ({dest.stat().st_size / 1e6:.0f} MB)")
        return
    print(
        f"Downloading {url}\n"
        "(2.1 GB, no HTTP range support server-side — if this crawls, Ctrl+C and "
        "run --skip-download after fetching it somewhere faster, e.g. the training pod)"
    )
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 CityVision/0.1"})
    tmp = dest.with_suffix(".part")
    done = 0
    with urlopen(req) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
    print()
    tmp.rename(dest)


def _extract(zip_path: Path, out_dir: Path) -> None:
    marker = out_dir / ".extracted"
    if marker.exists():
        return
    print(f"Extracting {zip_path.name} …")
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    marker.write_text("ok\n", encoding="utf-8")


def _find_pairs(root: Path) -> list[tuple[Path, Path]]:
    """Match Annotations/*.xml to JPEGImages/* by stem (standard VOC layout)."""
    ann_dirs = [p for p in root.rglob("Annotations") if p.is_dir()]
    img_dirs = [p for p in root.rglob("JPEGImages") if p.is_dir()]
    exts = {".jpg", ".jpeg", ".png"}
    if ann_dirs and img_dirs:
        imgs = {p.stem: p for p in img_dirs[0].iterdir() if p.suffix.lower() in exts}
        return [
            (imgs[xml.stem], xml)
            for xml in sorted(ann_dirs[0].glob("*.xml"))
            if xml.stem in imgs
        ]
    # Fallback: pair by stem anywhere under root, in case the release layout differs.
    imgs = {p.stem: p for p in root.rglob("*") if p.suffix.lower() in exts}
    return [(imgs[xml.stem], xml) for xml in sorted(root.rglob("*.xml")) if xml.stem in imgs]


def _voc_to_yolo(xml_path: Path) -> tuple[list[str], dict[str, int], set[str]]:
    stats = {n: 0 for n in CLASS_NAMES.values()}
    stats["dropped_repair"] = 0
    unmapped: set[str] = set()
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    if size is None:
        return [], stats, unmapped
    w = float(size.findtext("width") or 0)
    h = float(size.findtext("height") or 0)
    if w <= 0 or h <= 0:
        return [], stats, unmapped

    lines: list[str] = []
    for obj in root.findall("object"):
        raw = (obj.findtext("name") or "").strip()
        key = _norm(raw)
        if key not in NAME_TO_CLASS:
            if raw:
                unmapped.add(raw)
            continue
        cls = NAME_TO_CLASS[key]
        if cls is None:
            stats["dropped_repair"] += 1
            continue
        bb = obj.find("bndbox")
        if bb is None:
            continue
        xmin = max(0.0, float(bb.findtext("xmin") or 0))
        ymin = max(0.0, float(bb.findtext("ymin") or 0))
        xmax = min(w, float(bb.findtext("xmax") or 0))
        ymax = min(h, float(bb.findtext("ymax") or 0))
        if xmax <= xmin or ymax <= ymin:
            continue
        xc = ((xmin + xmax) / 2.0) / w
        yc = ((ymin + ymax) / 2.0) / h
        bw = (xmax - xmin) / w
        bh = (ymax - ymin) / h
        lines.append(f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
        stats[CLASS_NAMES[cls]] += 1
    return lines, stats, unmapped


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare UAV-PDD2023 → YOLO model_b_aerial classes")
    p.add_argument("--max-images", type=int, default=None, help="Limit for a smoke test")
    p.add_argument("--skip-download", action="store_true", help="Reuse an already-downloaded zip")
    p.add_argument(
        "--peek",
        type=int,
        default=0,
        metavar="N",
        help="Parse only the first N annotation files and print every raw category "
        "name seen (mapped or not), then exit without writing images/labels. Use "
        "this to verify NAME_TO_CLASS against the real archive before a full run.",
    )
    p.add_argument(
        "--keep-empty",
        action="store_true",
        help="Also export images with zero mapped boxes (e.g. repair-only frames) as hard negatives",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.skip_download:
        _download(ZENODO_URL, ZIP_PATH)
    if not ZIP_PATH.exists():
        raise SystemExit(f"Missing {ZIP_PATH} — place it there manually or omit --skip-download")
    _extract(ZIP_PATH, EXTRACT_DIR)

    pairs = _find_pairs(EXTRACT_DIR)
    if not pairs:
        raise SystemExit(f"No image/annotation pairs found under {EXTRACT_DIR}")

    if args.peek:
        seen: dict[str, int] = {}
        for _, xml in pairs[: args.peek]:
            for obj in ET.parse(xml).getroot().findall("object"):
                raw = (obj.findtext("name") or "").strip()
                seen[raw] = seen.get(raw, 0) + 1
        print(f"Raw category names across first {min(args.peek, len(pairs))} annotations:")
        for name, count in sorted(seen.items(), key=lambda kv: -kv[1]):
            mapped = NAME_TO_CLASS.get(_norm(name), "UNMAPPED")
            label = CLASS_NAMES.get(mapped, "drop") if mapped != "UNMAPPED" else "UNMAPPED"
            print(f"  {name!r:24s} n={count:5d} → {label}")
        return 0

    if args.max_images:
        pairs = pairs[: args.max_images]
    print(f"Found {len(pairs)} annotated images")

    img_dir = OUT_DIR / "images" / "train"
    lbl_dir = OUT_DIR / "labels" / "train"
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    totals = {n: 0 for n in CLASS_NAMES.values()}
    totals["dropped_repair"] = 0
    all_unmapped: set[str] = set()
    kept = 0
    for img, xml in pairs:
        lines, stats, unmapped = _voc_to_yolo(xml)
        all_unmapped |= unmapped
        for k, v in stats.items():
            totals[k] += v
        if not lines and not args.keep_empty:
            continue
        stem = f"uavpdd_{img.stem}"
        dest_img = img_dir / f"{stem}{img.suffix.lower()}"
        shutil.copy2(img, dest_img)
        (lbl_dir / f"{stem}.txt").write_text(
            ("\n".join(lines) + "\n") if lines else "", encoding="utf-8"
        )
        kept += 1
        if kept % 200 == 0:
            print(f"  {kept}/{len(pairs)}", flush=True)

    (OUT_DIR / "SOURCE.txt").write_text(
        "source=zenodo:10.5281/zenodo.8429208 (UAV-PDD2023)\n"
        "paper=https://pmc.ncbi.nlm.nih.gov/articles/PMC10630617/\n"
        "license=CC BY 4.0\n"
        "note=UAV imagery, ~30m altitude — same domain as our own aerial captures, "
        "unlike the street-level RDD2022/SVRDD bootstraps (see "
        "docs/training-model-b.md §0e). Train-only: not part of our own "
        "clip-based val/test hold-out (src/cityvision/pipeline/dataset_split.py).\n"
        "map=longitudinal/transverse/oblique crack→road_crack; alligator crack→"
        "road_damage; pothole→pothole; repair→dropped hard-negative candidate\n",
        encoding="utf-8",
    )

    print(f"\nDone → {OUT_DIR}")
    print(f"  images exported: {kept}/{len(pairs)}")
    print(f"  instances: {totals}")
    if all_unmapped:
        print(
            f"  WARNING: {len(all_unmapped)} unmapped category name(s), boxes dropped: "
            f"{sorted(all_unmapped)}"
        )
        print("  → add these to NAME_TO_CLASS in this script and re-run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
