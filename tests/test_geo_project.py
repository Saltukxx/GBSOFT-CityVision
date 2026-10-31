"""Placing detections on the ground from the camera pose."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from cityvision.geo.dji_srt import parse_dji_srt
from cityvision.geo.gps import attach_gps_to_detections, interpolate_gps
from cityvision.geo.project import CameraModel, hfov_from_focal, project_to_ground
from cityvision.pipeline.types import Detection, GpsFix

LAT, LON = 39.9, 41.27
W, H = 4000, 3000
CENTER = (W / 2 - 10, H / 2 - 10, W / 2 + 10, H / 2 + 10)


def _metres(lat1, lon1, lat2, lon2):
    north = (lat2 - lat1) * 111_320
    east = (lon2 - lon1) * 111_320 * math.cos(math.radians(lat1))
    return north, east


def _proj(**kw):
    args = dict(lat=LAT, lon=LON, bbox_xyxy=CENTER, image_size=(W, H), altitude_m=50, pitch_deg=-90, yaw_deg=0, hfov_deg=82)
    args.update(kw)
    return project_to_ground(**args)


def test_nadir_centre_is_under_the_drone():
    g = _proj()
    n, e = _metres(LAT, LON, g.lat, g.lon)
    assert abs(n) < 0.5 and abs(e) < 0.5
    assert g.source == "projected" and g.accuracy_m < 8


@pytest.mark.parametrize("yaw,expect", [(0, (50, 0)), (90, (0, 50)), (180, (-50, 0)), (270, (0, -50))])
def test_oblique_45_lands_altitude_away_in_camera_direction(yaw, expect):
    g = _proj(pitch_deg=-45, yaw_deg=yaw)
    n, e = _metres(LAT, LON, g.lat, g.lon)
    assert n == pytest.approx(expect[0], abs=0.5) and e == pytest.approx(expect[1], abs=0.5)


def test_box_lower_in_frame_is_closer_and_right_side_is_to_the_right():
    near = _proj(pitch_deg=-45, bbox_xyxy=(W / 2 - 10, H - 200, W / 2 + 10, H - 180))
    n_near, _ = _metres(LAT, LON, near.lat, near.lon)
    assert 0 < n_near < 50
    right = _proj(pitch_deg=-45, bbox_xyxy=(W - 200, H / 2 - 10, W - 180, H / 2 + 10))
    _, e_right = _metres(LAT, LON, right.lat, right.lon)
    assert e_right > 20  # facing north, image right is east


def test_shallow_ray_and_missing_pose_fall_back_to_platform():
    flat = _proj(pitch_deg=-5)
    assert flat.source == "platform" and (flat.lat, flat.lon) == (LAT, LON)
    no_alt = _proj(altitude_m=None)
    assert no_alt.source == "platform" and no_alt.accuracy_m == pytest.approx(53.0)
    no_yaw_oblique = _proj(pitch_deg=-45, yaw_deg=None)
    assert no_yaw_oblique.source == "platform"
    # Footprint radius at 50 m with an 82° lens: wide but bounded.
    assert 40 < no_yaw_oblique.accuracy_m < 80


def test_accuracy_grows_for_shallower_views():
    steep = _proj(pitch_deg=-80, yaw_deg=0).accuracy_m
    shallow = _proj(pitch_deg=-30, yaw_deg=0).accuracy_m
    assert shallow > steep


def test_focal_length_to_fov():
    assert hfov_from_focal(24, 82) == pytest.approx(73.7, abs=0.1)
    assert hfov_from_focal(None, 82) == 82


def test_dji_srt_pose_is_parsed(tmp_path: Path):
    srt = tmp_path / "DJI_0001.SRT"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,033\n<font size=\"28\">FrameCnt: 1, DiffTime: 33ms\n"
        "[iso: 100] [shutter: 1/1000.0] [fnum: 2.8] [focal_len: 24.00] "
        "[latitude: 39.904200] [longitude: 41.267900] [rel_alt: 61.400 abs_alt: 1953.210] "
        "[gb_yaw: 359.0 gb_pitch: -89.9 gb_roll: 0.0] </font>\n\n"
        "2\n00:00:00,033 --> 00:00:00,066\n[latitude: 39.904300] [longitude: 41.267900] "
        "[rel_alt: 61.500 abs_alt: 1953.3] [gb_yaw : 1.0 gb_pitch : -89.8 gb_roll : 0.0]\n",
        encoding="utf-8",
    )
    fixes = parse_dji_srt(srt)
    assert len(fixes) == 2
    f = fixes[0]
    assert (f.rel_alt_m, f.gimbal_pitch, f.gimbal_yaw, f.focal_len_mm) == (61.4, -89.9, 359.0, 24.0)
    mid = interpolate_gps(fixes, 16.5)
    # Yaw interpolates across north, not through south.
    assert mid.gimbal_yaw == pytest.approx(0.0, abs=0.1) or mid.gimbal_yaw == pytest.approx(360.0, abs=0.1)


def test_attach_keeps_platform_and_projects_target():
    fixes = [GpsFix(0, LAT, LON, rel_alt_m=50, gimbal_pitch=-45, gimbal_yaw=90), GpsFix(1000, LAT, LON, rel_alt_m=50, gimbal_pitch=-45, gimbal_yaw=90)]
    det = Detection(frame=1, timestamp_ms=500, class_name="pothole", confidence=0.9, bbox_xyxy=CENTER)
    attach_gps_to_detections([det], fixes, max_gap_ms=2000, image_size=(W, H), camera=CameraModel(hfov_deg=82))
    assert (det.platform_lat, det.platform_lon) == (LAT, LON)
    _, e = _metres(LAT, LON, det.lat, det.lon)
    assert e == pytest.approx(50, abs=0.5) and det.location_source == "projected"

    # Route defaults fill in a log without pose data (e.g. a plain GPS csv).
    plain = [GpsFix(0, LAT, LON), GpsFix(1000, LAT, LON)]
    det2 = Detection(frame=1, timestamp_ms=500, class_name="pothole", confidence=0.9, bbox_xyxy=CENTER)
    attach_gps_to_detections([det2], plain, 2000, (W, H), CameraModel(default_altitude_m=50, default_pitch_deg=-90))
    # Straight down without a bearing: under the drone, tight radius, honestly not "projected".
    assert det2.location_source == "platform" and det2.location_accuracy_m < 8
