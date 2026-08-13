from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from cityvision.pipeline.types import Detection


@dataclass
class TrafficStats:
    line_y: float
    vehicle_classes: List[str]
    unique_tracks: Dict[str, int] = field(default_factory=dict)
    crossings: Dict[str, int] = field(default_factory=dict)
    crossings_total: int = 0
    duration_sec: float = 0.0
    vehicles_per_minute: float = 0.0
    vehicles_per_hour: float = 0.0
    class_share: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "line_y": self.line_y,
            "vehicle_classes": self.vehicle_classes,
            "unique_tracks": self.unique_tracks,
            "crossings": self.crossings,
            "crossings_total": self.crossings_total,
            "duration_sec": round(self.duration_sec, 3),
            "vehicles_per_minute": round(self.vehicles_per_minute, 3),
            "vehicles_per_hour": round(self.vehicles_per_hour, 3),
            "class_share": {k: round(v, 4) for k, v in self.class_share.items()},
        }


class TrafficCounter:
    """Count unique tracks and line crossings for vehicle classes."""

    def __init__(self, line_y: float, vehicle_classes: Iterable[str]):
        self.line_y = float(line_y)
        self.vehicle_classes: Set[str] = set(vehicle_classes)
        self._seen_tracks: Dict[str, Set[int]] = defaultdict(set)
        self._crossings: Dict[str, int] = defaultdict(int)
        self._last_side: Dict[int, int] = {}
        self._first_ms: Optional[float] = None
        self._last_ms: Optional[float] = None

    def update(self, detections: Iterable[Detection]) -> None:
        for det in detections:
            if det.class_name not in self.vehicle_classes:
                continue
            if self._first_ms is None:
                self._first_ms = det.timestamp_ms
            self._last_ms = det.timestamp_ms

            if det.track_id is not None:
                self._seen_tracks[det.class_name].add(det.track_id)
                cy = det.center[1]
                side = 1 if cy >= self.line_y else -1
                prev = self._last_side.get(det.track_id)
                if prev is not None and prev != side:
                    self._crossings[det.class_name] += 1
                self._last_side[det.track_id] = side

    def finalize(self) -> TrafficStats:
        unique = {k: len(v) for k, v in self._seen_tracks.items()}
        crossings = dict(self._crossings)
        total_cross = sum(crossings.values())
        duration = 0.0
        if self._first_ms is not None and self._last_ms is not None:
            duration = max(0.0, (self._last_ms - self._first_ms) / 1000.0)
        vpm = (total_cross / duration * 60.0) if duration > 0 else 0.0
        vph = vpm * 60.0
        share = {}
        denom = sum(unique.values()) or 1
        for k, v in unique.items():
            share[k] = v / denom
        return TrafficStats(
            line_y=self.line_y,
            vehicle_classes=sorted(self.vehicle_classes),
            unique_tracks=unique,
            crossings=crossings,
            crossings_total=total_cross,
            duration_sec=duration,
            vehicles_per_minute=vpm,
            vehicles_per_hour=vph,
            class_share=share,
        )
