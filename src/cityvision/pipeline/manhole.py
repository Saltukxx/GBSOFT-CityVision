from __future__ import annotations

from typing import Iterable, List, Sequence

from cityvision.pipeline.types import Detection


def box_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def suppress_potholes_under_manholes(
    detections: Sequence[Detection],
    *,
    iou_threshold: float = 0.3,
    pothole_classes: Iterable[str] = ("pothole",),
    manhole_class: str = "manhole",
) -> List[Detection]:
    """Drop pothole boxes that overlap a manhole (rögar is not a work-order pothole)."""
    if iou_threshold <= 0:
        return list(detections)
    pothole_set = set(pothole_classes)
    manholes = [d for d in detections if d.class_name == manhole_class]
    if not manholes:
        return list(detections)
    kept: List[Detection] = []
    for det in detections:
        if det.class_name in pothole_set:
            if any(
                box_iou(det.bbox_xyxy, hole.bbox_xyxy) >= iou_threshold
                for hole in manholes
            ):
                continue
        kept.append(det)
    return kept
