"""Road ROI + class gate filters for event candidates."""

from cityvision.events.engine import EventEngine
from cityvision.events.roi import filter_event_detections, gate_reason, in_road_roi
from cityvision.pipeline.types import Detection

ROI_CFG = {
    "road_roi": {
        "enabled": True,
        "x_min": 0.12,
        "x_max": 0.88,
        "y_min": 0.42,
        "y_max": 0.98,
        "apply_to": ["pothole"],
    },
    "class_min_confidence": {"pothole": 0.72},
    "event_classes": ["pothole"],
    "fusion_radius_m": 15,
    "fusion_radius_norm": 0.05,
    "fusion_window_hours": 72,
    "min_observations": 2,
    "drop_confidence_bands": ["discard"],
}


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


def test_gate_reason_and_engine_rejected():
    bush = Detection(1, 0, "pothole", 0.93, (20, 300, 120, 520))
    weak = Detection(2, 100, "pothole", 0.40, (500, 450, 620, 560))
    once = Detection(3, 200, "pothole", 0.88, (500, 450, 620, 560), lat=39.9, lon=41.2)
    assert gate_reason(bush, width=1280, height=720, cfg=ROI_CFG) == "outside_roi"
    assert gate_reason(weak, width=1280, height=720, cfg=ROI_CFG) == "low_confidence"
    assert gate_reason(once, width=1280, height=720, cfg=ROI_CFG) is None

    engine = EventEngine(
        ROI_CFG,
        {"bands": {"discard": 0.7, "review": 0.85, "probable": 0.95}},
        "test",
    )
    engine.ingest([bush, weak, once])
    events = engine.build(1280, 720)
    assert events == []
    reasons = {r for _d, r in engine.last_rejected}
    assert "outside_roi" in reasons
    assert "low_confidence" in reasons
    assert "below_min_observations" in reasons
