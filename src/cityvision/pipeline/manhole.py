from __future__ import annotations

from typing import Iterable, List, Sequence

from cityvision.pipeline.types import Detection

DEFAULT_DISTRESS_CLASSES = ("pothole", "road_damage")


def box_area(box: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def box_intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def box_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    inter = box_intersection_area(a, b)
    if inter <= 0:
        return 0.0
    union = box_area(a) + box_area(b) - inter
    if union <= 0:
        return 0.0
    return inter / union


def box_containment(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> float:
    """Intersection over the inner box area (how much of inner sits in outer)."""
    area = box_area(inner)
    if area <= 0:
        return 0.0
    return box_intersection_area(inner, outer) / area


def center_inside(
    box: tuple[float, float, float, float],
    container: tuple[float, float, float, float],
) -> bool:
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    return container[0] <= cx <= container[2] and container[1] <= cy <= container[3]


def boxes_conflict(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    iou_threshold: float,
    containment_threshold: float = 0.45,
) -> bool:
    """True when two boxes likely describe the same surface object."""
    if iou_threshold > 0 and box_iou(a, b) >= iou_threshold:
        return True
    if containment_threshold > 0:
        if box_containment(a, b) >= containment_threshold:
            return True
        if box_containment(b, a) >= containment_threshold:
            return True
    return center_inside(a, b) or center_inside(b, a)


def suppress_potholes_under_manholes(
    detections: Sequence[Detection],
    *,
    iou_threshold: float = 0.15,
    containment_threshold: float = 0.45,
    pothole_classes: Iterable[str] = DEFAULT_DISTRESS_CLASSES,
    manhole_class: str = "manhole",
) -> List[Detection]:
    """Drop distress boxes that sit on a manhole (rögar is not a work-order)."""
    if iou_threshold <= 0 and containment_threshold <= 0:
        return list(detections)
    pothole_set = set(pothole_classes)
    manholes = [d for d in detections if d.class_name == manhole_class]
    if not manholes:
        return list(detections)
    kept: List[Detection] = []
    for det in detections:
        if det.class_name in pothole_set:
            if any(
                boxes_conflict(
                    det.bbox_xyxy,
                    hole.bbox_xyxy,
                    iou_threshold=iou_threshold,
                    containment_threshold=containment_threshold,
                )
                for hole in manholes
            ):
                continue
        kept.append(det)
    return kept


def suppress_overlapping_distress(
    detections: Sequence[Detection],
    *,
    iou_threshold: float = 0.3,
    containment_threshold: float = 0.45,
    classes: Iterable[str] = DEFAULT_DISTRESS_CLASSES,
) -> List[Detection]:
    """Keep one box when pothole and road_damage cover the same patch (higher conf wins)."""
    if iou_threshold <= 0 and containment_threshold <= 0:
        return list(detections)
    class_set = set(classes)
    others = [d for d in detections if d.class_name not in class_set]
    distress = [d for d in detections if d.class_name in class_set]
    distress.sort(key=lambda d: d.confidence, reverse=True)
    kept_distress: List[Detection] = []
    for det in distress:
        if any(
            boxes_conflict(
                det.bbox_xyxy,
                kept.bbox_xyxy,
                iou_threshold=iou_threshold,
                containment_threshold=containment_threshold,
            )
            for kept in kept_distress
        ):
            continue
        kept_distress.append(det)
    return others + kept_distress
