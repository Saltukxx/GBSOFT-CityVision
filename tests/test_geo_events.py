from cityvision.events.confidence import composite_confidence, confidence_band
from cityvision.events.fusion import fuse_detections
from cityvision.geo.geofence import Zone, load_zones
from cityvision.geo.gps import haversine_m, interpolate_gps, load_gps_sidecar
from cityvision.pipeline.traffic import TrafficCounter
from cityvision.pipeline.types import Detection


def test_gps_interpolate(tmp_path):
    p = tmp_path / "gps.csv"
    p.write_text(
        "timestamp_ms,lat,lon,speed,heading\n0,39.0,41.0,10,90\n1000,39.1,41.1,20,100\n",
        encoding="utf-8",
    )
    fixes = load_gps_sidecar(p)
    mid = interpolate_gps(fixes, 500)
    assert mid is not None
    assert 39.0 < mid.lat < 39.1
    assert mid.speed is not None and 10 < mid.speed < 20


def test_haversine_nearby():
    d = haversine_m(39.91814, 41.27318, 39.91816, 41.27313)
    assert d < 10


def test_point_in_zone():
    zone = Zone(
        zone_id="Z1",
        name="t",
        zone_type="bus_stop",
        ring=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)],
    )
    assert zone.contains(0.5, 0.5)
    assert not zone.contains(2.0, 2.0)


def test_load_example_zones():
    zones = load_zones("configs/zones.example.geojson")
    assert len(zones) == 1
    assert zones[0].zone_id == "BUS_STOP_187"


def test_traffic_crossing():
    counter = TrafficCounter(line_y=100, vehicle_classes=["car"])
    counter.update(
        [
            Detection(0, 0, "car", 0.9, (10, 50, 40, 80), track_id=1),
            Detection(1, 100, "car", 0.9, (10, 120, 40, 160), track_id=1),
        ]
    )
    stats = counter.finalize()
    assert stats.crossings_total == 1
    assert stats.unique_tracks["car"] == 1


def test_fusion_merges_nearby_potholes():
    dets = [
        Detection(1, 0, "pothole", 0.9, (100, 100, 140, 140), track_id=1, lat=39.91814, lon=41.27318),
        Detection(2, 1000, "pothole", 0.88, (105, 102, 145, 142), track_id=2, lat=39.91816, lon=41.27313),
        Detection(3, 2000, "pothole", 0.91, (110, 98, 150, 138), track_id=3, lat=39.91811, lon=41.27321),
    ]
    events = fuse_detections(
        detections=dets,
        event_classes=["pothole"],
        fusion_radius_m=15,
        fusion_radius_norm=0.05,
        fusion_window_ms=72 * 3600 * 1000,
        model_version="test",
        conf_bands={"discard": 0.7, "review": 0.85, "probable": 0.95},
        conf_bonuses={"repeat_bonus": 0.1, "multi_vehicle_bonus": 0.1, "gps_bonus": 0.05},
        width=640,
        height=480,
    )
    assert len(events) == 1
    assert events[0].observations == 3
    assert events[0].confidence > 0.9


def test_confidence_bands():
    assert confidence_band(0.5, {"discard": 0.7, "review": 0.85, "probable": 0.95}) == "discard"
    assert confidence_band(0.8, {"discard": 0.7, "review": 0.85, "probable": 0.95}) == "manual_review"
    score = composite_confidence(0.87, observations=3, has_gps=True, multi_vehicle=True)
    assert score > 0.95
