from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from cityvision.events.fusion import events_from_geofence_hits, fuse_detections
from cityvision.events.roi import partition_event_detections
from cityvision.geo.geofence import ZoneHit
from cityvision.pipeline.types import Detection, MunicipalEvent


class EventEngine:
    def __init__(self, cfg: Dict[str, Any], conf_cfg: Dict[str, Any], model_version: str):
        self.cfg = cfg
        self.conf_cfg = conf_cfg
        self.model_version = model_version
        self._buffer: List[Detection] = []
        self.last_rejected: List[tuple[Detection, str]] = []

    def ingest(self, detections: Sequence[Detection]) -> None:
        event_classes = set(self.cfg.get("event_classes") or [])
        for det in detections:
            if det.class_name in event_classes:
                self._buffer.append(det)

    def build(
        self,
        width: int,
        height: int,
        geofence_hits: Optional[Sequence[ZoneHit]] = None,
        geofence_event_type: str = "potential_bus_stop_obstruction",
    ) -> List[MunicipalEvent]:
        bonuses = {
            "repeat_bonus": float(self.conf_cfg.get("repeat_bonus", 0.10)),
            "multi_vehicle_bonus": float(self.conf_cfg.get("multi_vehicle_bonus", 0.10)),
            "gps_bonus": float(self.conf_cfg.get("gps_bonus", 0.05)),
        }
        bands = self.conf_cfg.get("bands") or {
            "discard": 0.70,
            "review": 0.85,
            "probable": 0.95,
        }
        window_h = float(self.cfg.get("fusion_window_hours", 72))
        gated, rejected = partition_event_detections(
            self._buffer,
            width=width,
            height=height,
            cfg=self.cfg,
        )
        skipped: List[Detection] = []
        events = fuse_detections(
            detections=gated,
            event_classes=self.cfg.get("event_classes") or [],
            fusion_radius_m=float(self.cfg.get("fusion_radius_m", 15)),
            fusion_radius_norm=float(self.cfg.get("fusion_radius_norm", 0.05)),
            fusion_window_ms=window_h * 3600 * 1000,
            model_version=self.model_version,
            conf_bands=bands,
            conf_bonuses=bonuses,
            width=width,
            height=height,
            min_observations=int(self.cfg.get("min_observations", 1)),
            skipped_out=skipped,
        )
        for sample in skipped:
            rejected.append((sample, "below_min_observations"))
        drop_bands = set(self.cfg.get("drop_confidence_bands") or [])
        if drop_bands:
            kept_events = []
            for event in events:
                if event.confidence_band in drop_bands:
                    if event.sample_frame is not None and event.sample_bbox:
                        x1, y1, x2, y2 = (float(v) for v in event.sample_bbox[:4])
                        rejected.append(
                            (
                                Detection(
                                    frame=int(event.sample_frame),
                                    timestamp_ms=event.last_seen_ms,
                                    class_name=event.type,
                                    confidence=float(event.confidence),
                                    bbox_xyxy=(x1, y1, x2, y2),
                                    lat=event.lat,
                                    lon=event.lon,
                                ),
                                "discard_band",
                            )
                        )
                    continue
                kept_events.append(event)
            events = kept_events
        self.last_rejected = rejected
        if geofence_hits:
            geo_events = events_from_geofence_hits(
                hits=geofence_hits,
                model_version=self.model_version,
                conf_bands=bands,
                conf_bonuses=bonuses,
                event_type=geofence_event_type,
                start_index=1,
            )
            events.extend(geo_events)
        return events
