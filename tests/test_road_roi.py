"""Road ROI + class gate filters for event candidates."""

from cityvision.events.roi import filter_event_detections, in_road_roi
from cityvision.pipeline.types import Detection


def test_bush_outside_roi_rejected():
    # Left roadside bush (similar to false POT-00006)
    det = Detection(1, 0, "pothole", 0.93, (20, 300, 120, 520))
    cfg = {
        "road_roi": {
            "enabled": True,
            "x_min": 0.12,
            "x_max": 0.88,
            "y_min": 0.42,
            "y_max": 0.98,
            "apply_to": ["pothole"],
        },
        "class_min_confidence": {"pothole": 0.72},
    }
    assert not in_road_roi(det, 1280, 720, cfg["road_roi"])
    kept = filter_event_detections([det], width=1280, height=720, cfg=cfg)
    assert kept == []


def test_on_road_pothole_kept():
    det = Detection(1, 0, "pothole", 0.88, (500, 450, 620, 560))
    cfg = {
        "road_roi": {
            "enabled": True,
            "x_min": 0.12,
            "x_max": 0.88,
            "y_min": 0.42,
            "y_max": 0.98,
            "apply_to": ["pothole"],
        },
        "class_min_confidence": {"pothole": 0.72},
    }
    kept = filter_event_detections([det], width=1280, height=720, cfg=cfg)
    assert len(kept) == 1


def test_waste_below_floor_dropped():
    det = Detection(1, 0, "overflowing_container", 0.80, (600, 400, 700, 500))
    cfg = {
        "road_roi": {"enabled": False},
        "class_min_confidence": {"overflowing_container": 0.92},
    }
    kept = filter_event_detections([det], width=1280, height=720, cfg=cfg)
    assert kept == []
