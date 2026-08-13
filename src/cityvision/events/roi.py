"""Road-surface ROI and class gates for municipal event candidates."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from cityvision.pipeline.types import Detection


def bbox_center_norm(
    bbox_xyxy: Sequence[float], width: int, height: int
) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox_xyxy
    cx = ((x1 + x2) / 2.0) / max(width, 1)
    cy = ((y1 + y2) / 2.0) / max(height, 1)
    return cx, cy


def in_road_roi(
    det: Detection,
    width: int,
    height: int,
    roi: Dict[str, Any],
) -> bool:
    """True if detection center lies in the configured road ROI (normalized)."""
    if not roi or not roi.get("enabled", True):
        return True
    cx, cy = bbox_center_norm(det.bbox_xyxy, width, height)
    x_min = float(roi.get("x_min", 0.0))
    x_max = float(roi.get("x_max", 1.0))
    y_min = float(roi.get("y_min", 0.0))
    y_max = float(roi.get("y_max", 1.0))
    return x_min <= cx <= x_max and y_min <= cy <= y_max


def passes_class_gates(
    det: Detection,
    *,
    class_min_confidence: Optional[Dict[str, float]] = None,
) -> bool:
    floors = class_min_confidence or {}
    floor = floors.get(det.class_name)
    if floor is None:
        return True
    return float(det.confidence) >= float(floor)


def filter_event_detections(
    detections: Sequence[Detection],
    *,
    width: int,
    height: int,
    cfg: Dict[str, Any],
) -> list[Detection]:
    """
    Apply road ROI + per-class confidence floors before fusion.

    Classes listed in road_roi.apply_to (default: road defect types) must fall
    in the ROI. Other event classes only need class_min_confidence.
    """
    roi = dict(cfg.get("road_roi") or {})
    apply_to = set(
        roi.get("apply_to")
        or [
            "pothole",
            "road_crack",
            "road_damage",
        ]
    )
    class_min = dict(cfg.get("class_min_confidence") or {})
    out: list[Detection] = []
    for det in detections:
        if not passes_class_gates(det, class_min_confidence=class_min):
            continue
        if det.class_name in apply_to and not in_road_roi(det, width, height, roi):
            continue
        out.append(det)
    return out
