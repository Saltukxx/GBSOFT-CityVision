"""Place a detection on the ground instead of under the drone (plan.md §6).

A ray from the camera through the box centre is intersected with flat ground
at the drone's height above take-off. Inputs: drone position, altitude above
ground, gimbal pitch and yaw (compass bearing of the camera), horizontal field
of view, and where the box sits in the image.

Flat ground is an approximation: on slopes, or when take-off height differs from
the ground under the object, the error grows — the accuracy radius reflects that.
When pose data is missing we keep the drone position and say so, with a radius
covering the whole camera footprint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

METHOD = "flat-ground-ray/v1"
GPS_ERROR_M = 3.0  # typical consumer GNSS horizontal error
MIN_DEPRESSION_DEG = 8.0  # rays flatter than this hit the ground too far away to trust
M_PER_DEG_LAT = 111_320.0


@dataclass
class CameraModel:
    hfov_deg: float = 82.0  # DJI Mini 4 Pro / Mavic 3E wide camera ≈ 82–84°
    # Used only when the log lacks them (e.g. no SRT): taken from the planned route.
    default_altitude_m: Optional[float] = None
    default_pitch_deg: Optional[float] = None


@dataclass
class GroundFix:
    lat: float
    lon: float
    accuracy_m: float
    source: str  # "projected" | "platform"


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> Tuple[float, float]:
    return (
        lat + north_m / M_PER_DEG_LAT,
        lon + east_m / (M_PER_DEG_LAT * math.cos(math.radians(lat))),
    )


def hfov_from_focal(focal_len_35mm: Optional[float], fallback: float) -> float:
    """35 mm-equivalent focal length → horizontal field of view (36 mm sensor width)."""
    if not focal_len_35mm or focal_len_35mm <= 0:
        return fallback
    return math.degrees(2 * math.atan(36.0 / (2 * focal_len_35mm)))


def project_to_ground(
    *,
    lat: float,
    lon: float,
    bbox_xyxy: Tuple[float, float, float, float],
    image_size: Tuple[int, int],
    altitude_m: Optional[float],
    pitch_deg: Optional[float],
    yaw_deg: Optional[float],
    hfov_deg: float,
) -> GroundFix:
    """Estimate where the box centre is on the ground. Angles in degrees."""
    w, h = image_size
    if not altitude_m or altitude_m <= 1 or pitch_deg is None or w <= 0 or h <= 0:
        return platform_only(lat, lon, altitude_m, hfov_deg, image_size)

    x1, y1, x2, y2 = bbox_xyxy
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    nx = (cx - w / 2.0) / (w / 2.0)  # -1 left … +1 right
    ny = (cy - h / 2.0) / (h / 2.0)  # -1 top … +1 bottom
    tan_h = math.tan(math.radians(hfov_deg) / 2.0)
    tan_v = tan_h * h / w
    off_right = math.atan(nx * tan_h)
    off_down = math.atan(ny * tan_v)

    # Depression below the horizon of the ray through the box centre.
    depression = math.radians(-pitch_deg) + off_down
    if depression >= math.radians(89.9):
        depression = math.radians(89.9)
    if math.degrees(depression) < MIN_DEPRESSION_DEG:
        return platform_only(lat, lon, altitude_m, hfov_deg, image_size)

    if yaw_deg is None:
        # Without a bearing only a nadir shot can be placed: the offset is small
        # and in an unknown direction, so fold it into the accuracy instead.
        if pitch_deg > -80:
            return platform_only(lat, lon, altitude_m, hfov_deg, image_size)
        spread = altitude_m * math.hypot(nx * tan_h, ny * tan_v)
        return GroundFix(lat, lon, round(GPS_ERROR_M + spread, 1), "platform")

    forward = altitude_m / math.tan(depression)
    slant = altitude_m / math.sin(depression)
    right = slant * math.tan(off_right)
    yaw = math.radians(yaw_deg)
    north = forward * math.cos(yaw) - right * math.sin(yaw)
    east = forward * math.sin(yaw) + right * math.cos(yaw)
    tlat, tlon = _offset(lat, lon, north, east)

    # Error budget: GNSS + 1° of pitch error (grows fast for shallow rays)
    # + 5 % altitude error (terrain, baro drift) along the ground distance.
    pitch_err = altitude_m / math.tan(max(depression - math.radians(1.0), math.radians(1.0))) - forward
    accuracy = GPS_ERROR_M + abs(pitch_err) + 0.05 * math.hypot(forward, right)
    return GroundFix(tlat, tlon, round(accuracy, 1), "projected")


def platform_only(
    lat: float, lon: float, altitude_m: Optional[float], hfov_deg: float, image_size: Tuple[int, int]
) -> GroundFix:
    """Drone position; the object is somewhere in the camera footprint."""
    w, h = image_size
    if altitude_m and altitude_m > 1 and w > 0 and h > 0:
        half_w = altitude_m * math.tan(math.radians(hfov_deg) / 2.0)
        radius = math.hypot(half_w, half_w * h / w)
    else:
        radius = 50.0  # unknown height: say so honestly
    return GroundFix(lat, lon, round(GPS_ERROR_M + radius, 1), "platform")
