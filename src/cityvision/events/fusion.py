from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from cityvision.events.confidence import (
    composite_confidence,
    confidence_band,
    severity_from_class,
)
from cityvision.geo.gps import haversine_m
from cityvision.pipeline.types import Detection, MunicipalEvent


@dataclass
class _Cluster:
    event_type: str
    lat: Optional[float]
    lon: Optional[float]
    norm_x: Optional[float]
    norm_y: Optional[float]
    first_ms: float
    last_ms: float
    max_conf: float
    observations: int = 0
    vehicle_ids: Set[str] = field(default_factory=set)
    camera_ids: Set[str] = field(default_factory=set)
    track_ids: Set[int] = field(default_factory=set)
    sample_frame: Optional[int] = None
    sample_bbox: Optional[List[float]] = None
    zone_id: Optional[str] = None


def fuse_detections(
    detections: Sequence[Detection],
    event_classes: Sequence[str],
    fusion_radius_m: float,
    fusion_radius_norm: float,
    fusion_window_ms: float,
    model_version: str,
    conf_bands: Dict[str, float],
    conf_bonuses: Dict[str, float],
    width: int,
    height: int,
    min_observations: int = 1,
    id_prefix: str = "EVT",
    skipped_out: Optional[List[Detection]] = None,
) -> List[MunicipalEvent]:
    allowed = set(event_classes)
    clusters: List[_Cluster] = []

    # Prefer peak-confidence observation per track+class to reduce spam
    best: Dict[str, Detection] = {}
    for det in detections:
        if det.class_name not in allowed:
            continue
        key = f"{det.class_name}:{det.track_id if det.track_id is not None else det.frame}"
        prev = best.get(key)
        if prev is None or det.confidence > prev.confidence:
            best[key] = det

    for det in sorted(best.values(), key=lambda d: d.timestamp_ms):
        cx, cy = det.center
        nx = cx / max(width, 1)
        ny = cy / max(height, 1)
        matched: Optional[_Cluster] = None
        for cluster in clusters:
            if cluster.event_type != det.class_name:
                continue
            if abs(det.timestamp_ms - cluster.last_ms) > fusion_window_ms and abs(
                det.timestamp_ms - cluster.first_ms
            ) > fusion_window_ms:
                continue
            if (
                det.lat is not None
                and det.lon is not None
                and cluster.lat is not None
                and cluster.lon is not None
            ):
                if haversine_m(det.lat, det.lon, cluster.lat, cluster.lon) <= fusion_radius_m:
                    matched = cluster
                    break
            elif cluster.norm_x is not None and cluster.norm_y is not None:
                dist = ((nx - cluster.norm_x) ** 2 + (ny - cluster.norm_y) ** 2) ** 0.5
                if dist <= fusion_radius_norm:
                    matched = cluster
                    break

        if matched is None:
            clusters.append(
                _Cluster(
                    event_type=det.class_name,
                    lat=det.lat,
                    lon=det.lon,
                    norm_x=nx,
                    norm_y=ny,
                    first_ms=det.timestamp_ms,
                    last_ms=det.timestamp_ms,
                    max_conf=det.confidence,
                    observations=1,
                    vehicle_ids={det.vehicle_id} if det.vehicle_id else set(),
                    camera_ids={det.camera_id} if det.camera_id else set(),
                    track_ids={det.track_id} if det.track_id is not None else set(),
                    sample_frame=det.frame,
                    sample_bbox=list(det.bbox_xyxy),
                )
            )
            continue

        matched.observations += 1
        matched.last_ms = max(matched.last_ms, det.timestamp_ms)
        matched.first_ms = min(matched.first_ms, det.timestamp_ms)
        if det.confidence >= matched.max_conf:
            matched.max_conf = det.confidence
            matched.sample_frame = det.frame
            matched.sample_bbox = list(det.bbox_xyxy)
            matched.lat = det.lat if det.lat is not None else matched.lat
            matched.lon = det.lon if det.lon is not None else matched.lon
            matched.norm_x = nx
            matched.norm_y = ny
        if det.vehicle_id:
            matched.vehicle_ids.add(det.vehicle_id)
        if det.camera_id:
            matched.camera_ids.add(det.camera_id)
        if det.track_id is not None:
            matched.track_ids.add(det.track_id)

    events: List[MunicipalEvent] = []
    seq = 0
    for cluster in clusters:
        if cluster.observations < min_observations:
            if skipped_out is not None:
                sample = _cluster_to_detection(cluster)
                if sample is not None:
                    skipped_out.append(sample)
            continue
        seq += 1
        score = composite_confidence(
            ai_conf=cluster.max_conf,
            observations=cluster.observations,
            has_gps=cluster.lat is not None and cluster.lon is not None,
            multi_vehicle=len(cluster.vehicle_ids) > 1,
            repeat_bonus=float(conf_bonuses.get("repeat_bonus", 0.10)),
            multi_vehicle_bonus=float(conf_bonuses.get("multi_vehicle_bonus", 0.10)),
            gps_bonus=float(conf_bonuses.get("gps_bonus", 0.05)),
        )
        band = confidence_band(score, conf_bands)
        status = "archived" if band == "discard" else "under_review"
        prefix = {
            "pothole": "POT",
            "road_damage": "RDG",
            "road_crack": "RCK",
            "overflowing_container": "WST",
            "street_waste": "WST",
            "potential_bus_stop_obstruction": "BSO",
        }.get(cluster.event_type, id_prefix)
        events.append(
            MunicipalEvent(
                event_id=f"{prefix}-{seq:05d}",
                type=cluster.event_type,
                lat=cluster.lat,
                lon=cluster.lon,
                severity=severity_from_class(cluster.event_type, score),
                confidence=round(score, 4),
                confidence_band=band,
                first_seen_ms=cluster.first_ms,
                last_seen_ms=cluster.last_ms,
                observations=cluster.observations,
                status=status,
                model_version=model_version,
                vehicle_ids=sorted(cluster.vehicle_ids),
                camera_ids=sorted(cluster.camera_ids),
                track_ids=sorted(cluster.track_ids),
                zone_id=cluster.zone_id,
                norm_x=cluster.norm_x,
                norm_y=cluster.norm_y,
                sample_frame=cluster.sample_frame,
                sample_bbox=cluster.sample_bbox,
            )
        )
    return events


def _cluster_to_detection(cluster: _Cluster) -> Optional[Detection]:
    if cluster.sample_frame is None or not cluster.sample_bbox:
        return None
    x1, y1, x2, y2 = (float(v) for v in cluster.sample_bbox[:4])
    return Detection(
        frame=int(cluster.sample_frame),
        timestamp_ms=cluster.last_ms,
        class_name=cluster.event_type,
        confidence=float(cluster.max_conf),
        bbox_xyxy=(x1, y1, x2, y2),
        lat=cluster.lat,
        lon=cluster.lon,
    )


def events_from_geofence_hits(
    hits,
    model_version: str,
    conf_bands: Dict[str, float],
    conf_bonuses: Dict[str, float],
    event_type: str,
    start_index: int = 1,
) -> List[MunicipalEvent]:
    events: List[MunicipalEvent] = []
    for i, hit in enumerate(hits, start=start_index):
        score = composite_confidence(
            ai_conf=hit.max_conf,
            observations=len(hit.frames),
            has_gps=True,
            multi_vehicle=False,
            repeat_bonus=float(conf_bonuses.get("repeat_bonus", 0.10)),
            multi_vehicle_bonus=float(conf_bonuses.get("multi_vehicle_bonus", 0.10)),
            gps_bonus=float(conf_bonuses.get("gps_bonus", 0.05)),
        )
        band = confidence_band(score, conf_bands)
        events.append(
            MunicipalEvent(
                event_id=f"BSO-{i:05d}",
                type=event_type,
                lat=hit.lat,
                lon=hit.lon,
                severity=severity_from_class(event_type, score),
                confidence=round(score, 4),
                confidence_band=band,
                first_seen_ms=hit.first_ms,
                last_seen_ms=hit.last_ms,
                observations=len(hit.frames),
                status="archived" if band == "discard" else "under_review",
                model_version=model_version,
                track_ids=[hit.track_id] if hit.track_id is not None else [],
                zone_id=hit.zone_id,
                sample_frame=hit.frames[len(hit.frames) // 2],
            )
        )
    return events
