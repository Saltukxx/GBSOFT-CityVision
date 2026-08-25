"""FlightHub flight trajectory → GPS sidecar for the existing pipeline.

`cityvision.geo.gps` already reads `.jsonl` fixes, so a trajectory only has to be
translated once and the pipeline needs no changes at all.

Two things make this less trivial than a field rename:

  * Trajectory timestamps are wall clock (epoch), but `GpsFix.timestamp_ms` is the
    *video clock* — `parse_dji_srt` stores subtitle cue offsets, and detections are
    timestamped from frame index. Absolute epochs would push every fix past
    `max_interp_gap_ms` and silently drop GPS from every detection, so we rebase onto
    the flight start.
  * DJI has not pinned the trajectory schema in the reference we could read, so key
    names are matched leniently rather than assumed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from cityvision.pipeline.types import GpsFix

_LAT_KEYS = ("latitude", "lat")
_LON_KEYS = ("longitude", "longtitude", "lon", "lng", "long")
_TIME_KEYS = (
    "timestamp_ms",
    "timestamp",
    "time",
    "ts",
    "create_time",
    "created_at",
    "record_time",
)
_SPEED_KEYS = ("speed", "horizontal_speed", "ground_speed")
_HEADING_KEYS = ("heading", "yaw", "direction", "course")
_POINT_CONTAINER_KEYS = ("list", "points", "trajectory", "items", "data")

# Epoch milliseconds passed this mark in 2001; epoch seconds will not reach it until
# the year 33658. Anything smaller is already a relative offset.
_EPOCH_MS_FLOOR = 1e12
_EPOCH_SEC_FLOOR = 1e9


def _first_number(row: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _to_millis(value: float) -> float:
    """Normalise epoch seconds / epoch millis / relative offsets to milliseconds."""
    if value >= _EPOCH_MS_FLOOR:
        return value
    if value >= _EPOCH_SEC_FLOOR:
        return value * 1000.0
    return value


def extract_points(payload: Any) -> List[Dict[str, Any]]:
    """Dig the point array out of whatever envelope the trajectory came in."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if not isinstance(payload, dict):
        return []
    for key in _POINT_CONTAINER_KEYS:
        if key not in payload:
            continue
        nested = payload[key]
        if isinstance(nested, list):
            rows = [p for p in nested if isinstance(p, dict)]
            if rows:
                return rows
        elif isinstance(nested, dict):
            rows = extract_points(nested)
            if rows:
                return rows
    return []


def parse_trajectory(payload: Any, *, start_ms: Optional[float] = None) -> List[GpsFix]:
    """
    Build video-clock GPS fixes from a FlightHub trajectory response.

    `start_ms` is the flight/video start in the same units the trajectory uses; when
    omitted the earliest point becomes t=0.
    """
    raw: List[tuple[float, float, float, Optional[float], Optional[float]]] = []
    for row in extract_points(payload):
        lat = _first_number(row, _LAT_KEYS)
        lon = _first_number(row, _LON_KEYS)
        stamp = _first_number(row, _TIME_KEYS)
        if lat is None or lon is None or stamp is None:
            continue
        if lat == 0.0 and lon == 0.0:
            continue
        raw.append(
            (
                _to_millis(stamp),
                lat,
                lon,
                _first_number(row, _SPEED_KEYS),
                _first_number(row, _HEADING_KEYS),
            )
        )
    if not raw:
        return []
    raw.sort(key=lambda r: r[0])
    origin = _to_millis(start_ms) if start_ms is not None else raw[0][0]
    fixes = [
        GpsFix(
            timestamp_ms=stamp - origin,
            lat=lat,
            lon=lon,
            speed=speed,
            heading=heading,
        )
        for stamp, lat, lon, speed, heading in raw
    ]
    return [f for f in fixes if f.timestamp_ms >= 0]


def write_gps_sidecar(fixes: Iterable[GpsFix], dest: Path) -> Path:
    """Write fixes as the `.jsonl` sidecar that `load_gps_sidecar` already understands."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as handle:
        for fix in fixes:
            row: Dict[str, Any] = {
                "timestamp_ms": fix.timestamp_ms,
                "lat": fix.lat,
                "lon": fix.lon,
            }
            if fix.speed is not None:
                row["speed"] = fix.speed
            if fix.heading is not None:
                row["heading"] = fix.heading
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return dest
