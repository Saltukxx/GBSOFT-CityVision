from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from cityvision.geo.dji_srt import parse_dji_srt
from cityvision.geo.project import CameraModel, hfov_from_focal, project_to_ground
from cityvision.pipeline.types import GpsFix


def discover_gps_sidecar(source: str | Path) -> Optional[Path]:
    """Look next to a video for DJI .SRT / .srt (same stem)."""
    src = Path(source)
    for ext in (".SRT", ".srt"):
        cand = src.with_suffix(ext)
        if cand.is_file():
            return cand.resolve()
    return None


def load_gps_sidecar(path: str | Path) -> List[GpsFix]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return parse_dji_srt(path)
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".json":
        return _load_json(path)
    return _load_csv(path)


def _load_csv(path: Path) -> List[GpsFix]:
    fixes: List[GpsFix] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("timestamp_ms") or row.get("t_ms") or row.get("timestamp")
            if ts is None:
                continue
            fixes.append(
                GpsFix(
                    timestamp_ms=float(ts),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    speed=_opt_float(row.get("speed")),
                    heading=_opt_float(row.get("heading")),
                    rel_alt_m=_first_float(row, "rel_alt_m", "rel_alt", "altitude_m", "alt"),
                    gimbal_pitch=_first_float(row, "gimbal_pitch", "pitch"),
                    gimbal_yaw=_first_float(row, "gimbal_yaw", "yaw"),
                )
            )
    fixes.sort(key=lambda g: g.timestamp_ms)
    return fixes


def _load_jsonl(path: Path) -> List[GpsFix]:
    fixes: List[GpsFix] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            fixes.append(
                GpsFix(
                    timestamp_ms=float(obj["timestamp_ms"]),
                    lat=float(obj["lat"]),
                    lon=float(obj["lon"]),
                    speed=_opt_float(obj.get("speed")),
                    heading=_opt_float(obj.get("heading")),
                    rel_alt_m=_first_float(obj, "rel_alt_m", "rel_alt", "altitude_m", "alt"),
                    gimbal_pitch=_first_float(obj, "gimbal_pitch", "pitch"),
                    gimbal_yaw=_first_float(obj, "gimbal_yaw", "yaw"),
                )
            )
    fixes.sort(key=lambda g: g.timestamp_ms)
    return fixes


def _load_json(path: Path) -> List[GpsFix]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("fixes", [])
    fixes = [
        GpsFix(
            timestamp_ms=float(r["timestamp_ms"]),
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            speed=_opt_float(r.get("speed")),
            heading=_opt_float(r.get("heading")),
            rel_alt_m=_first_float(r, "rel_alt_m", "rel_alt", "altitude_m", "alt"),
            gimbal_pitch=_first_float(r, "gimbal_pitch", "pitch"),
            gimbal_yaw=_first_float(r, "gimbal_yaw", "yaw"),
        )
        for r in rows
    ]
    fixes.sort(key=lambda g: g.timestamp_ms)
    return fixes


def _first_float(row: dict, *keys: str) -> Optional[float]:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return float(v)
    return None


def _opt_float(v: object) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)  # type: ignore[arg-type]


def interpolate_gps(
    fixes: Sequence[GpsFix],
    timestamp_ms: float,
    max_gap_ms: float = 2000.0,
) -> Optional[GpsFix]:
    if not fixes:
        return None
    if timestamp_ms <= fixes[0].timestamp_ms:
        if abs(timestamp_ms - fixes[0].timestamp_ms) <= max_gap_ms:
            return fixes[0]
        return None
    if timestamp_ms >= fixes[-1].timestamp_ms:
        if abs(timestamp_ms - fixes[-1].timestamp_ms) <= max_gap_ms:
            return fixes[-1]
        return None

    lo, hi = 0, len(fixes) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if fixes[mid].timestamp_ms <= timestamp_ms:
            lo = mid
        else:
            hi = mid
    a, b = fixes[lo], fixes[hi]
    gap = b.timestamp_ms - a.timestamp_ms
    if gap <= 0 or gap > max_gap_ms:
        return None
    t = (timestamp_ms - a.timestamp_ms) / gap
    return GpsFix(
        timestamp_ms=timestamp_ms,
        lat=a.lat + (b.lat - a.lat) * t,
        lon=a.lon + (b.lon - a.lon) * t,
        speed=_lerp_opt(a.speed, b.speed, t),
        heading=_lerp_angle(a.heading, b.heading, t),
        rel_alt_m=_lerp_opt(a.rel_alt_m, b.rel_alt_m, t),
        gimbal_pitch=_lerp_opt(a.gimbal_pitch, b.gimbal_pitch, t),
        gimbal_yaw=_lerp_angle(a.gimbal_yaw, b.gimbal_yaw, t),
        focal_len_mm=a.focal_len_mm if a.focal_len_mm is not None else b.focal_len_mm,
    )


def _lerp_angle(a: Optional[float], b: Optional[float], t: float) -> Optional[float]:
    """Interpolate a compass angle the short way round (350° → 10° passes 0°)."""
    if a is None or b is None:
        return a if b is None else b
    d = ((b - a + 540.0) % 360.0) - 180.0
    return (a + d * t) % 360.0


def _lerp_opt(a: Optional[float], b: Optional[float], t: float) -> Optional[float]:
    if a is None or b is None:
        return a if b is None else b
    return a + (b - a) * t


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def attach_gps_to_detections(
    detections: List,
    fixes: Sequence[GpsFix],
    max_gap_ms: float,
    image_size: Optional[Tuple[int, int]] = None,
    camera: Optional[CameraModel] = None,
) -> None:
    """Give each detection a position.

    With the frame size, the detection is projected onto the ground from the
    camera pose (see geo.project); otherwise it gets the drone's position.
    """
    for det in detections:
        fix = interpolate_gps(fixes, det.timestamp_ms, max_gap_ms=max_gap_ms)
        if fix is None:
            continue
        det.platform_lat = fix.lat
        det.platform_lon = fix.lon
        det.speed = fix.speed
        det.heading = fix.heading
        if image_size is None:
            det.lat, det.lon = fix.lat, fix.lon
            continue
        cam = camera or CameraModel()
        ground = project_to_ground(
            lat=fix.lat,
            lon=fix.lon,
            bbox_xyxy=det.bbox_xyxy,
            image_size=image_size,
            altitude_m=fix.rel_alt_m if fix.rel_alt_m is not None else cam.default_altitude_m,
            pitch_deg=fix.gimbal_pitch if fix.gimbal_pitch is not None else cam.default_pitch_deg,
            # Gimbal yaw is the camera's bearing; fall back to the direction of travel.
            yaw_deg=fix.gimbal_yaw if fix.gimbal_yaw is not None else fix.heading,
            hfov_deg=hfov_from_focal(fix.focal_len_mm, cam.hfov_deg),
        )
        det.lat, det.lon = ground.lat, ground.lon
        det.location_accuracy_m = ground.accuracy_m
        det.location_source = ground.source
