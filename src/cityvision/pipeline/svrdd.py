"""SVRDD class map → City Vision Model B road labels.

SVRDD native IDs (Scientific Data / HF card):
  0 longitudinal crack
  1 transverse crack
  2 alligator crack
  3 pothole
  4 manhole cover
  5 longitudinal patch
  6 transverse patch

Positives become YOLO boxes. Patch boxes are dropped so the image stays
as a hard-negative when nothing else remains.
"""

from __future__ import annotations

from typing import Any

# City Vision Model B road (SVRDD bootstrap)
OUT_POTHOLE = 0
OUT_CRACK = 1
OUT_MANHOLE = 2
OUT_NAMES = {
    OUT_POTHOLE: "pothole",
    OUT_CRACK: "road_crack",
    OUT_MANHOLE: "manhole",
}

SVRDD_ID_TO_OUT: dict[int, int | None] = {
    0: OUT_CRACK,
    1: OUT_CRACK,
    2: OUT_CRACK,
    3: OUT_POTHOLE,
    4: OUT_MANHOLE,
    5: None,
    6: None,
}

SVRDD_NAME_TO_OUT: dict[str, int | None] = {
    "longitudinal crack": OUT_CRACK,
    "transverse crack": OUT_CRACK,
    "alligator crack": OUT_CRACK,
    "pothole": OUT_POTHOLE,
    "manhole cover": OUT_MANHOLE,
    "manhole": OUT_MANHOLE,
    "longitudinal patch": None,
    "transverse patch": None,
}


def _norm_name(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").replace("-", " ").split())


def resolve_svrdd_class(category_id: int | None, category_name: str | None) -> int | None:
    """Return output class id, or None to drop (hard-negative / unknown)."""
    if category_name:
        key = _norm_name(category_name)
        if key in SVRDD_NAME_TO_OUT:
            return SVRDD_NAME_TO_OUT[key]
    if category_id is not None and category_id in SVRDD_ID_TO_OUT:
        return SVRDD_ID_TO_OUT[category_id]
    return None


def _clip_yolo(xc: float, yc: float, bw: float, bh: float) -> tuple[float, float, float, float] | None:
    if bw <= 0 or bh <= 0:
        return None
    xc = min(max(xc, 0.0), 1.0)
    yc = min(max(yc, 0.0), 1.0)
    bw = min(max(bw, 1e-6), 1.0)
    bh = min(max(bh, 1e-6), 1.0)
    if xc == 0.0 and yc == 0.0 and bw >= 1.0 and bh >= 1.0:
        return None
    return xc, yc, bw, bh


def _box_to_yolo(
    box: list[float] | tuple[float, ...],
    *,
    normalized: bool,
    img_w: float,
    img_h: float,
) -> tuple[float, float, float, float] | None:
    if not box or len(box) < 4:
        return None
    a, b, c, d = (float(v) for v in box[:4])
    if normalized:
        return _clip_yolo(a, b, c, d)
    if img_w <= 0 or img_h <= 0 or c <= 0 or d <= 0:
        return None
    xc = (a + c / 2.0) / img_w
    yc = (b + d / 2.0) / img_h
    return _clip_yolo(xc, yc, c / img_w, d / img_h)


def map_objects_to_yolo_lines(
    objects: dict[str, Any] | None,
    *,
    img_w: float = 1024.0,
    img_h: float = 1024.0,
) -> tuple[list[str], dict[str, int]]:
    """Convert one SVRDD `objects` dict to YOLO lines + instance counts.

    Counts keys: pothole, road_crack, manhole, hard_negative, dropped.
    """
    stats = {
        "pothole": 0,
        "road_crack": 0,
        "manhole": 0,
        "hard_negative": 0,
        "dropped": 0,
    }
    if not objects:
        return [], stats

    cats = list(objects.get("categories") or [])
    names = list(objects.get("category_names") or [])
    yolo_boxes = list(objects.get("bbox_yolo") or [])
    abs_boxes = list(objects.get("bbox") or [])
    n = max(len(cats), len(names), len(yolo_boxes), len(abs_boxes))
    lines: list[str] = []

    for i in range(n):
        cat_id = cats[i] if i < len(cats) else None
        if cat_id is not None:
            cat_id = int(cat_id)
        name = names[i] if i < len(names) else None
        out_id = resolve_svrdd_class(cat_id, name)
        if out_id is None:
            if (name and _norm_name(str(name)) in SVRDD_NAME_TO_OUT) or (
                cat_id is not None and cat_id in SVRDD_ID_TO_OUT
            ):
                stats["hard_negative"] += 1
            else:
                stats["dropped"] += 1
            continue

        yolo = None
        if i < len(yolo_boxes):
            yolo = _box_to_yolo(yolo_boxes[i], normalized=True, img_w=img_w, img_h=img_h)
        if yolo is None and i < len(abs_boxes):
            yolo = _box_to_yolo(abs_boxes[i], normalized=False, img_w=img_w, img_h=img_h)
        if yolo is None:
            stats["dropped"] += 1
            continue

        xc, yc, bw, bh = yolo
        lines.append(f"{out_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
        stats[OUT_NAMES[out_id]] += 1

    return lines, stats
