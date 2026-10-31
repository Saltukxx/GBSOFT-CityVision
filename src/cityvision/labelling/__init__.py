"""Turning reviewer decisions into training data (labels, splits, export)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterable, List, Optional

# Classes the aerial detector is trained on. Manhole covers are deliberately
# not a class: they are labelled as hard negatives (kind="negative").
TRAINING_CLASSES: List[str] = [
    "pothole",
    "road_crack",
    "road_damage",
    "overflowing_container",
    "street_waste",
]

# Share of non-held-out flights that go to validation.
VAL_PERCENT = 15


def validate_boxes(boxes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalise and check boxes: known class, inside the frame, not degenerate."""
    out: List[Dict[str, Any]] = []
    for b in boxes:
        cls = str(b.get("cls", ""))
        if cls not in TRAINING_CLASSES:
            raise ValueError(f"unknown class: {cls}")
        x, y, w, h = (float(b[k]) for k in ("x", "y", "w", "h"))
        # Clip to the frame; reject boxes that end up (almost) empty.
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(1.0, x + w), min(1.0, y + h)
        if x1 - x0 < 0.002 or y1 - y0 < 0.002:
            raise ValueError("box is too small or outside the image")
        out.append({"cls": cls, "x": round(x0, 6), "y": round(y0, 6), "w": round(x1 - x0, 6), "h": round(y1 - y0, 6)})
    return out


def split_for(row: Dict[str, Any]) -> str:
    """Whole flights stay together so neighbouring frames never leak across splits."""
    if row.get("holdout"):
        return "test"
    group = str(row.get("flight_id") or row.get("run_id") or row["event_id"])
    bucket = int(hashlib.sha256(group.encode()).hexdigest(), 16) % 100
    return "val" if bucket < VAL_PERCENT else "train"


def yolo_lines(boxes: List[Dict[str, Any]]) -> str:
    lines = []
    for b in boxes:
        cx = b["x"] + b["w"] / 2
        cy = b["y"] + b["h"] / 2
        lines.append(f"{TRAINING_CLASSES.index(b['cls'])} {cx:.6f} {cy:.6f} {b['w']:.6f} {b['h']:.6f}")
    return "\n".join(lines) + ("\n" if lines else "")


def evidence_folder(row: Dict[str, Any]) -> str:
    """The run folder a media row came from: local evidence dir, else storage prefix."""
    if row.get("path") and not str(row["path"]).startswith("evidence/"):
        return str(Path(str(row["path"])).parent)
    return str(Path(str(row.get("object_key") or row.get("path") or "")).parent)


def latest_evidence_set(media: List[Dict[str, Any]], needs: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Media of the newest run that has every type in `needs` (by folder)."""
    groups: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for m in sorted(media, key=lambda r: int(r.get("id") or 0)):
        groups.setdefault(evidence_folder(m), {})[str(m.get("media_type"))] = m
    for folder in reversed(list(groups)):
        g = groups[folder]
        if all(n in g for n in needs):
            return g
    return {}


def _open_media(row: Dict[str, Any]) -> Optional[BinaryIO]:
    from cityvision.storage import get_object_store

    if row.get("object_key"):
        try:
            return get_object_store().open_read(str(row["object_key"]))
        except (FileNotFoundError, ValueError, OSError):
            pass
    path = Path(str(row.get("path") or ""))
    if row.get("path") and path.is_file():
        return path.open("rb")
    return None


def build_export(rows: List[Dict[str, Any]], out: BinaryIO, *, city_id: Optional[str]) -> Dict[str, Any]:
    """Write a YOLO dataset zip (images/, labels/, data.yaml) to `out`.

    Same layout as data/datasets/* so scripts/train_rfdetr.py can combine it
    with the public datasets. Returns what was written and what was skipped.
    """
    counts = {"train": 0, "val": 0, "test": 0}
    negatives = {"train": 0, "val": 0, "test": 0}
    skipped: List[Dict[str, str]] = []
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as zf:
        for row in rows:
            if not row.get("media_id"):
                skipped.append({"event_id": row["event_id"], "reason": "no_clean_frame"})
                continue
            fh = _open_media(row)
            if fh is None:
                skipped.append({"event_id": row["event_id"], "reason": "image_missing"})
                continue
            split = split_for(row)
            boxes = row.get("boxes") or []
            if isinstance(boxes, str):
                boxes = json.loads(boxes)
            if row["kind"] == "negative":
                boxes = []
                negatives[split] += 1
            stem = row["event_id"]
            with fh:
                zf.writestr(f"images/{split}/{stem}.jpg", fh.read())
            zf.writestr(f"labels/{split}/{stem}.txt", yolo_lines(boxes))
            counts[split] += 1

        names = "\n".join(f"  {i}: {n}" for i, n in enumerate(TRAINING_CLASSES))
        zf.writestr(
            "data.yaml",
            "path: .\ntrain: images/train\nval: images/val\ntest: images/test\n\nnames:\n" + names + "\n",
        )
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "city_id": city_id,
            "classes": TRAINING_CLASSES,
            "images": counts,
            "hard_negatives": negatives,
            "skipped": skipped,
            "split_rule": f"held-out flights -> test; other flights hashed, {VAL_PERCENT}% -> val",
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return manifest
