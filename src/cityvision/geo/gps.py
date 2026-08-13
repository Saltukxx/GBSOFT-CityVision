from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from cityvision.pipeline.types import GpsFix


def load_gps_sidecar(path: str | Path) -> List[GpsFix]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    if path.suffix.lower() == ".json":
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
        )
        for r in rows
    ]
    fixes.sort(key=lambda g: g.timestamp_ms)
    return fixes


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
        heading=_lerp_opt(a.heading, b.heading, t),
    )


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
) -> None:
    for det in detections:
        fix = interpolate_gps(fixes, det.timestamp_ms, max_gap_ms=max_gap_ms)
        if fix is None:
            continue
        det.lat = fix.lat
        det.lon = fix.lon
        det.speed = fix.speed
        det.heading = fix.heading
