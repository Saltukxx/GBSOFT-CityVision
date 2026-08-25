#!/usr/bin/env python3
"""Export ONLY clip12-clip21 hand labels to a standalone YOLO dataset.

Deliberately excludes the pre-existing hand-labeled set (clip1-clip11, dji_fly_*)
-- that's the data that caused the road_crack collapse earlier this session, root
cause never identified, just excluded. This exports only the new clips, labeled
under the (already correct) labeling guide, specifically targeting the manhole/
paver false-positive fix found via real-footage testing.

Usage: .venv/bin/python export_new_clips.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if False else None  # unused, path is explicit below
REPO = Path("/Users/saltuk/Desktop/GBSOFT-CITYVISION")
sys.path.insert(0, str(REPO / "src"))

from cityvision.pipeline.dataset_split import assign_splits  # noqa: E402

DS = REPO / "data" / "datasets" / "model_b_aerial"
FRAMES = DS / "raw_frames"
LABELS_HAND = DS / "labels_hand"
BACKGROUND = DS / "background.txt"
OUT = REPO / "data" / "datasets" / "own_footage_new"

NEW_CLIP_PREFIXES = tuple(f"clip{n}_" for n in range(12, 22))
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}


def read_boxes(name: str) -> list[str]:
    p = LABELS_HAND / (Path(name).stem + ".txt")
    if not p.exists():
        return []
    return [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    clean = set()
    if BACKGROUND.exists():
        clean = {ln.strip() for ln in BACKGROUND.read_text(encoding="utf-8").splitlines() if ln.strip()}

    frames = sorted(
        p for p in FRAMES.iterdir()
        if p.suffix.lower() in EXTS and p.name.startswith(NEW_CLIP_PREFIXES)
    )
    usable = [f for f in frames if read_boxes(f.name) or f.name in clean]
    print(f"new-clip frames total: {len(frames)}  usable (labeled or clean): {len(usable)}")

    splits = assign_splits([f.name for f in usable], test_prefix="clip3", val_tail_frac=0.2, guard_frames=1)

    if OUT.exists():
        shutil.rmtree(OUT)

    counts = {"train": 0, "val": 0}
    stats = {n: 0 for n in NAMES.values()}
    bg_counts = {"train": 0, "val": 0}
    for f in usable:
        split = splits.get(f.name)
        if split not in ("train", "val"):
            continue
        img_dir = OUT / "images" / split
        lbl_dir = OUT / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / f.name).symlink_to(f.resolve())
        lines = read_boxes(f.name)
        (lbl_dir / (f.stem + ".txt")).write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        counts[split] += 1
        if not lines:
            bg_counts[split] += 1
        for line in lines:
            cls = int(line.split()[0])
            stats[NAMES[cls]] += 1

    data_yaml = OUT / "data.yaml"
    data_yaml.write_text(
        f"path: {OUT}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: pothole\n"
        "  1: road_crack\n"
        "  2: manhole\n"
        "  3: road_damage\n",
        encoding="utf-8",
    )
    print(f"train={counts['train']} (bg={bg_counts['train']})  val={counts['val']} (bg={bg_counts['val']})")
    print(f"boxes: {stats}")
    print(f"Wrote {data_yaml}")


if __name__ == "__main__":
    main()
