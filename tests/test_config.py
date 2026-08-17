from pathlib import Path

from cityvision.config import (
    coco_to_city_name,
    load_class_config,
    load_pipeline_config,
    resolve_class_name,
)


def test_class_config_loads():
    cfg = load_class_config()
    names = [c["name"] for c in cfg["classes"]]
    assert "pothole" in names
    assert "manhole" in names
    assert "car" in names


def test_coco_mapping_includes_vehicles():
    cfg = load_class_config()
    mapping = coco_to_city_name(cfg)
    assert mapping["car"] == "car"
    assert mapping["bus"] == "bus"


def test_pipeline_config_loads():
    cfg = load_pipeline_config()
    assert "detection" in cfg
    assert Path("configs/pipeline.yaml").exists()


def test_pipeline_city_overlay_erzurum():
    from cityvision.config import deep_merge

    assert deep_merge({"a": 1, "b": {"c": 1}}, {"b": {"d": 2}}) == {
        "a": 1,
        "b": {"c": 1, "d": 2},
    }
    cfg = load_pipeline_config(city_id="erzurum")
    assert cfg["run"].get("city_id") == "erzurum"
    assert cfg["run"].get("vehicle_id") == "DJI-ERZ-01"
    assert cfg["events"]["road_roi"]["enabled"] is False


def test_pipeline_drone_defaults():
    cfg = load_pipeline_config()
    assert cfg["run"]["vehicle_id"] == "DJI-01"
    assert cfg["run"]["camera_id"] == "AERIAL"
    assert cfg["traffic"]["enabled"] is False
    assert cfg["geofence"]["enabled"] is False
    assert cfg["events"]["road_roi"]["enabled"] is False
    assert "manhole" not in cfg["events"]["event_classes"]


def test_pipeline_profile_overlays():
    oblique = load_pipeline_config(profile="oblique")
    assert oblique["video"]["stride"] == 2
    assert oblique["detection"]["imgsz"] == 640
    assert oblique["detection"]["min_box_area"] == 400
    assert oblique["run"]["profile"] == "oblique"

    nadir = load_pipeline_config(profile="nadir")
    assert nadir["video"]["stride"] == 3
    assert nadir["detection"]["imgsz"] == 960
    assert nadir["detection"]["min_box_area"] == 150
    assert nadir["run"]["profile"] == "nadir"


def test_resolve_native_taxonomy_name():
    cfg = load_class_config()
    assert resolve_class_name("pothole", cfg, bootstrap_coco_only=True) == "pothole"
    assert resolve_class_name("car", cfg, bootstrap_coco_only=True) == "car"
    assert resolve_class_name("banana", cfg, bootstrap_coco_only=True) is None


def test_rdd_label_aliases_map_to_taxonomy():
    cfg = load_class_config()
    assert resolve_class_name("Longitudinal Crack", cfg, bootstrap_coco_only=False) == "road_crack"
    assert resolve_class_name("transverse_crack", cfg, bootstrap_coco_only=False) == "road_crack"
    assert resolve_class_name("Alligator Crack", cfg, bootstrap_coco_only=False) == "road_damage"
    assert resolve_class_name("Pothole", cfg, bootstrap_coco_only=False) == "pothole"
    assert resolve_class_name("Other", cfg, bootstrap_coco_only=False) is None
    assert resolve_class_name("D40", cfg, bootstrap_coco_only=False) == "pothole"
    assert resolve_class_name("manhole cover", cfg, bootstrap_coco_only=False) == "manhole"
    assert resolve_class_name("D20", cfg, bootstrap_coco_only=False) == "road_damage"
    # Alias drop still works under Model A bootstrap mode
    assert resolve_class_name("Other", cfg, bootstrap_coco_only=True) is None
