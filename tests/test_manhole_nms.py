from cityvision.pipeline.manhole import box_iou, suppress_potholes_under_manholes
from cityvision.pipeline.types import Detection


def _det(class_name: str, box: tuple[float, float, float, float]) -> Detection:
    return Detection(
        frame=0,
        timestamp_ms=0.0,
        class_name=class_name,
        confidence=0.9,
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


def test_pothole_kept_when_far_from_manhole():
    manhole = _det("manhole", (10.0, 10.0, 40.0, 40.0))
    pothole = _det("pothole", (200.0, 200.0, 240.0, 240.0))
    kept = suppress_potholes_under_manholes([manhole, pothole], iou_threshold=0.3)
    assert [d.class_name for d in kept] == ["manhole", "pothole"]


def test_suppress_noop_when_iou_disabled():
    manhole = _det("manhole", (10.0, 10.0, 50.0, 50.0))
    pothole = _det("pothole", (12.0, 12.0, 48.0, 48.0))
    kept = suppress_potholes_under_manholes([manhole, pothole], iou_threshold=0.0)
    assert len(kept) == 2
