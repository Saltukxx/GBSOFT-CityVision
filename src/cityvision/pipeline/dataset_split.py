"""Clip-aware train/val/test split for video-sampled datasets.

Frames sampled from a flight are highly correlated second to second, so an
interleaved split (every Nth frame to val) reports a val score that is close to a
train score. Splitting on the timeline instead keeps the two blocks apart.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List

TRAIN = "train"
VAL = "val"
TEST = "test"
DROP = "drop"


def clip_of(name: str) -> str:
    """Clip id from `clip1_0012000ms.jpg` → `clip1`."""
    stem = Path(name).stem
    head, _, tail = stem.rpartition("_")
    return head if head and tail.endswith("ms") else stem


def timestamp_of(name: str) -> int:
    """Millisecond offset from `clip1_0012000ms.jpg` → 12000."""
    tail = Path(name).stem.rpartition("_")[2]
    digits = tail[:-2] if tail.endswith("ms") else tail
    return int(digits) if digits.isdigit() else 0


def assign_splits(
    names: Iterable[str],
    *,
    test_prefix: str = "clip3",
    val_tail_frac: float = 0.2,
    guard_frames: int = 1,
) -> Dict[str, str]:
    """
    Map each frame name to train / val / test / drop.

    Frames whose name starts with `test_prefix` become the hold-out test set. Every
    other clip is cut on its own timeline: the last `val_tail_frac` goes to val and
    `guard_frames` frames right before the cut are dropped, so no val frame borders a
    train frame. Each flight therefore appears in both train and val.
    """
    out: Dict[str, str] = {}
    clips: Dict[str, List[str]] = {}
    for name in names:
        if test_prefix and name.startswith(test_prefix):
            out[name] = TEST
        else:
            clips.setdefault(clip_of(name), []).append(name)

    for frames in clips.values():
        frames.sort(key=timestamp_of)
        n_val = int(len(frames) * val_tail_frac)
        cut = len(frames) - n_val
        if n_val < 1 or cut <= guard_frames:
            for name in frames:
                out[name] = TRAIN
            continue
        for i, name in enumerate(frames):
            if i >= cut:
                out[name] = VAL
            elif i >= cut - guard_frames:
                out[name] = DROP
            else:
                out[name] = TRAIN
    return out


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def split_manifest_sha(image_dir: Path) -> str:
    """SHA256 of the sorted image filenames in a split directory.

    Byte-identical copies share a name list with the originals they came from, so
    this hashes names, not file contents. Two exports of the same frames compare
    equal; adding or dropping a frame does not.
    """
    if not image_dir.exists():
        return ""
    names = sorted(
        p.name
        for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    )
    return hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest()
