from cityvision.pipeline.manhole import (
    box_iou,
    suppress_overlapping_distress,
    suppress_potholes_under_manholes,
)
from cityvision.pipeline.types import Detection


def _det(
    class_name: str,
    box: tuple[float, float, float, float],
    confidence: float = 0.9,
) -> Detection:
    return Detection(
        frame=0,
        timestamp_ms=0.0,
        class_name=class_name,
        confidence=confidence,
        bbox_xyxy=box,
    )


def test_identical_boxes_iou_is_one():
    box = (10.0, 10.0, 50.0, 50.0)
    assert box_iou(box, box) == 1.0


def test_pothole_dropped_when_overlapping_manhole():
    manhole = _det("manhole", (10.0, 10.0, 50.0, 50.0))
    pothole = _det("pothole", (12.0, 12.0, 48.0, 48.0))
    crack = _det("road_crack", (200.0, 200.0, 240.0, 240.0))
    kept = suppress_potholes_under_manholes([manhole, pothole, crack], iou_threshold=0.3)
    assert [d.class_name for d in kept] == ["manhole", "road_crack"]


def test_road_damage_dropped_when_overlapping_manhole():
    manhole = _det("manhole", (10.0, 10.0, 50.0, 50.0))
    damage = _det("road_damage", (12.0, 12.0, 48.0, 48.0))
    kept = suppress_potholes_under_manholes([manhole, damage])
    assert [d.class_name for d in kept] == ["manhole"]


def test_pothole_kept_when_far_from_manhole():
    manhole = _det("manhole", (10.0, 10.0, 40.0, 40.0))
    pothole = _det("pothole", (200.0, 200.0, 240.0, 240.0))
    kept = suppress_potholes_under_manholes([manhole, pothole], iou_threshold=0.3)
    assert [d.class_name for d in kept] == ["manhole", "pothole"]


def test_offset_pothole_on_cover_dropped_by_center():
    manhole = _det("manhole", (0.0, 0.0, 100.0, 100.0))
    pothole = _det("pothole", (40.0, 40.0, 55.0, 55.0))
    assert box_iou(manhole.bbox_xyxy, pothole.bbox_xyxy) < 0.15
    kept = suppress_potholes_under_manholes([manhole, pothole])
    assert [d.class_name for d in kept] == ["manhole"]


def test_large_pothole_wrapping_manhole_is_dropped():
    manhole = _det("manhole", (40.0, 40.0, 60.0, 60.0))
    pothole = _det("pothole", (0.0, 0.0, 100.0, 100.0))
    kept = suppress_potholes_under_manholes([manhole, pothole])
    assert [d.class_name for d in kept] == ["manhole"]


def test_suppress_noop_when_iou_disabled():
    manhole = _det("manhole", (10.0, 10.0, 50.0, 50.0))
    pothole = _det("pothole", (12.0, 12.0, 48.0, 48.0))
    kept = suppress_potholes_under_manholes(
        [manhole, pothole],
        iou_threshold=0.0,
        containment_threshold=0.0,
    )
    assert len(kept) == 2


def test_overlapping_pothole_and_damage_keeps_higher_confidence():
    pothole = _det("pothole", (10.0, 10.0, 50.0, 50.0), confidence=0.61)
    damage = _det("road_damage", (12.0, 12.0, 48.0, 48.0), confidence=0.88)
    car = _det("car", (200.0, 200.0, 240.0, 240.0))
    kept = suppress_overlapping_distress([pothole, damage, car])
    names = [d.class_name for d in kept]
    assert "car" in names
    assert names.count("road_damage") == 1
    assert "pothole" not in names


def test_adjacent_pothole_and_damage_both_kept():
    pothole = _det("pothole", (0.0, 0.0, 20.0, 20.0))
    damage = _det("road_damage", (80.0, 80.0, 100.0, 100.0))
    kept = suppress_overlapping_distress([pothole, damage])
    assert {d.class_name for d in kept} == {"pothole", "road_damage"}
