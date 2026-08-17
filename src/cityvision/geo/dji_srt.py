from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from cityvision.pipeline.types import GpsFix

_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_LAT_RE = re.compile(
    r"latitude\s*[:=]\s*([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_LON_RE = re.compile(
    r"longitude\s*[:=]\s*([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_GPS_PAREN_RE = re.compile(
    r"GPS\s*\(\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_BLOCK_SPLIT_RE = re.compile(r"\n\s*\n+")


def _srt_time_to_ms(token: str) -> Optional[float]:
    match = _TIME_RE.search(token.strip())
    if not match:
        return None
    hours, minutes, seconds, frac = match.groups()
    millis = int(frac.ljust(3, "0")[:3])
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000.0 + millis


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _parse_lat_lon(body: str) -> Optional[tuple[float, float]]:
    cleaned = _strip_tags(body)
    lat_m = _LAT_RE.search(cleaned)
    lon_m = _LON_RE.search(cleaned)
    if lat_m and lon_m:
        return float(lat_m.group(1)), float(lon_m.group(1))
    gps_m = _GPS_PAREN_RE.search(cleaned)
    if gps_m:
        return float(gps_m.group(1)), float(gps_m.group(2))
    return None


def parse_dji_srt(path: str | Path) -> List[GpsFix]:
    """
    Parse DJI Fly / Dock subtitle GPS into GpsFix rows.

    Timestamp is the cue start (video clock). rel_alt is ignored (not heading).
    Zero/zero coordinates (no GPS lock) are skipped.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    fixes: List[GpsFix] = []
    for raw_block in _BLOCK_SPLIT_RE.split(text):
        block = raw_block.strip()
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 2:
            continue
        # Standard SRT: index, then timing line. Some DJI files omit the index.
        timing_line = lines[1] if "-->" in lines[1] else lines[0]
        if "-->" not in timing_line:
            continue
        start_token = timing_line.split("-->", 1)[0]
        timestamp_ms = _srt_time_to_ms(start_token)
        if timestamp_ms is None:
            continue
        body = "\n".join(lines[2:] if "-->" in lines[1] else lines[1:])
        coords = _parse_lat_lon(body)
        if coords is None:
            continue
        lat, lon = coords
        if lat == 0.0 and lon == 0.0:
            continue
        fixes.append(GpsFix(timestamp_ms=timestamp_ms, lat=lat, lon=lon))

    fixes.sort(key=lambda g: g.timestamp_ms)
    return fixes
