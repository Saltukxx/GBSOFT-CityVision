from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from cityvision.pipeline.types import Detection


@dataclass
class Zone:
    zone_id: str
    name: str
    zone_type: str
    # polygon as list of (lon, lat) — GeoJSON order
    ring: List[Tuple[float, float]]

    def contains(self, lon: float, lat: float) -> bool:
        return _point_in_ring(lon, lat, self.ring)


def load_zones(path: str | Path) -> List[Zone]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    zones: List[Zone] = []
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Polygon":
            continue
        coords = geom.get("coordinates") or []
        if not coords:
            continue
        ring = [(float(x), float(y)) for x, y in coords[0]]
        zones.append(
            Zone(
                zone_id=str(props.get("zone_id") or props.get("id") or f"zone-{len(zones)}"),
                name=str(props.get("name") or ""),
                zone_type=str(props.get("type") or "bus_stop"),
                ring=ring,
            )
        )
    return zones


def _point_in_ring(x: float, y: float, ring: Sequence[Tuple[float, float]]) -> bool:
    # Ray casting; x=lon, y=lat
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


@dataclass
class ZoneHit:
    zone_id: str
    track_id: Optional[int]
    class_name: str
    frames: List[int]
    first_ms: float
    last_ms: float
    max_conf: float
    lat: float
    lon: float


class GeofenceEngine:
    """AI vehicle + GPS ∈ zone → potential obstruction candidate."""

    def __init__(
        self,
        zones: Sequence[Zone],
        vehicle_classes: Iterable[str],
        min_dwell_frames: int = 3,
        event_type: str = "potential_bus_stop_obstruction",
    ):
        self.zones = list(zones)
        self.vehicle_classes: Set[str] = set(vehicle_classes)
        self.min_dwell_frames = min_dwell_frames
        self.event_type = event_type
        # key: (zone_id, track_id or class_frame fallback)
        self._hits: Dict[Tuple[str, str], ZoneHit] = {}

    def update(self, detections: Sequence[Detection]) -> None:
        if not self.zones:
            return
        for det in detections:
            if det.class_name not in self.vehicle_classes:
                continue
            if det.lat is None or det.lon is None:
                continue
            for zone in self.zones:
                if not zone.contains(det.lon, det.lat):
                    continue
                key_id = str(det.track_id) if det.track_id is not None else f"f{det.frame}"
                key = (zone.zone_id, key_id)
                hit = self._hits.get(key)
                if hit is None:
                    self._hits[key] = ZoneHit(
                        zone_id=zone.zone_id,
                        track_id=det.track_id,
                        class_name=det.class_name,
                        frames=[det.frame],
                        first_ms=det.timestamp_ms,
                        last_ms=det.timestamp_ms,
                        max_conf=det.confidence,
                        lat=det.lat,
                        lon=det.lon,
                    )
                else:
                    hit.frames.append(det.frame)
                    hit.last_ms = det.timestamp_ms
                    hit.max_conf = max(hit.max_conf, det.confidence)
                    hit.lat = det.lat
                    hit.lon = det.lon

    def finalized_hits(self) -> List[ZoneHit]:
        return [h for h in self._hits.values() if len(h.frames) >= self.min_dwell_frames]
