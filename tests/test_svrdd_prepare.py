from cityvision.pipeline.svrdd import map_objects_to_yolo_lines, resolve_svrdd_class


def test_resolve_cracks_and_pothole():
    assert resolve_svrdd_class(0, None) == 1
    assert resolve_svrdd_class(3, "Pothole") == 0
    assert resolve_svrdd_class(None, "alligator_crack") == 1


def test_resolve_manhole_and_patch_hard_negatives():
    assert resolve_svrdd_class(4, "manhole cover") == 2
    assert resolve_svrdd_class(5, None) is None
    assert resolve_svrdd_class(6, "transverse patch") is None


def test_map_keeps_pothole_crack_and_manhole_drops_patch():
    objects = {
        "categories": [3, 0, 4, 5],
        "category_names": ["pothole", "longitudinal crack", "manhole cover", "longitudinal patch"],
        "bbox_yolo": [
            [0.5, 0.6, 0.1, 0.1],
            [0.2, 0.7, 0.3, 0.05],
            [0.8, 0.8, 0.1, 0.1],
            [0.4, 0.4, 0.2, 0.05],
        ],
    }
    lines, stats = map_objects_to_yolo_lines(objects)
    assert len(lines) == 3
    assert lines[0].startswith("0 ")
    assert lines[1].startswith("1 ")
    assert lines[2].startswith("2 ")
    assert stats["pothole"] == 1
    assert stats["road_crack"] == 1
    assert stats["manhole"] == 1
    assert stats["hard_negative"] == 1


def test_patch_only_image_has_empty_labels():
    objects = {
        "categories": [6],
        "category_names": ["transverse patch"],
        "bbox_yolo": [[0.3, 0.3, 0.2, 0.05]],
    }
    lines, stats = map_objects_to_yolo_lines(objects)
    assert lines == []
    assert stats["hard_negative"] == 1
    assert stats["pothole"] == 0
    assert stats["manhole"] == 0


def test_manhole_only_image_keeps_box():
    objects = {
        "categories": [4],
        "category_names": ["manhole cover"],
        "bbox_yolo": [[0.5, 0.5, 0.1, 0.1]],
    }
    lines, stats = map_objects_to_yolo_lines(objects)
    assert len(lines) == 1
    assert lines[0].startswith("2 ")
    assert stats["manhole"] == 1


def test_falls_back_to_absolute_xywh():
    objects = {
        "categories": [3],
        "category_names": ["pothole"],
        "bbox": [[100, 200, 50, 40]],
    }
    lines, stats = map_objects_to_yolo_lines(objects, img_w=1000, img_h=800)
    assert stats["pothole"] == 1
    parts = lines[0].split()
    assert parts[0] == "0"
    assert abs(float(parts[1]) - 0.125) < 1e-6
    assert abs(float(parts[2]) - 0.275) < 1e-6
