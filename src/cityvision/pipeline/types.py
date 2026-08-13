from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GpsFix:
    timestamp_ms: float
    lat: float
    lon: float
    speed: Optional[float] = None
    heading: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_ms": round(self.timestamp_ms, 3),
            "lat": self.lat,
            "lon": self.lon,
            "speed": self.speed,
            "heading": self.heading,
        }


@dataclass
class Detection:
    frame: int
    timestamp_ms: float
    class_name: str
    confidence: float
    bbox_xyxy: Tuple[float, float, float, float]
    track_id: Optional[int] = None
    model_id: str = "A"
    lat: Optional[float] = None
    lon: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    vehicle_id: Optional[str] = None
    camera_id: Optional[str] = None
    discarded_low_conf: bool = False

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox_xyxy
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox_xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def to_dict(self) -> Dict[str, Any]:
        x1, y1, x2, y2 = self.bbox_xyxy
        cx, cy = self.center
        return {
            "frame": self.frame,
            "timestamp_ms": round(self.timestamp_ms, 3),
            "class": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "track_id": self.track_id,
            "model_id": self.model_id,
            "bbox_xyxy": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
            "center_xy": [round(cx, 2), round(cy, 2)],
            "area": round(self.area, 2),
            "lat": self.lat,
            "lon": self.lon,
            "speed": self.speed,
            "heading": self.heading,
            "vehicle_id": self.vehicle_id,
            "camera_id": self.camera_id,
            "discarded_low_conf": self.discarded_low_conf,
        }


@dataclass
class RunMeta:
    source: str
    model_a: str
    model_b: Optional[str]
    model_version: str
    fps: float
    width: int
    height: int
    frame_count: int
    vehicle_id: str
    camera_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MunicipalEvent:
    event_id: str
    type: str
    lat: Optional[float]
    lon: Optional[float]
    severity: str
    confidence: float
    confidence_band: str
    first_seen_ms: float
    last_seen_ms: float
    observations: int
    status: str
    model_version: str
    vehicle_ids: List[str] = field(default_factory=list)
    camera_ids: List[str] = field(default_factory=list)
    track_ids: List[int] = field(default_factory=list)
    zone_id: Optional[str] = None
    evidence_dir: Optional[str] = None
    norm_x: Optional[float] = None
    norm_y: Optional[float] = None
    sample_frame: Optional[int] = None
    sample_bbox: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
