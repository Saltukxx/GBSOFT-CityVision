from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
from tqdm import tqdm

from cityvision.config import load_pipeline_config
from cityvision.events.engine import EventEngine
from cityvision.events.evidence import write_evidence_packs
from cityvision.events.rejected import write_rejected_samples
from cityvision.geo.geofence import GeofenceEngine, load_zones
from cityvision.geo.gps import attach_gps_to_detections, load_gps_sidecar
from cityvision.pipeline.annotate import draw_detections
from cityvision.pipeline.detector import DualModelDetector
from cityvision.pipeline.export_json import JsonlWriter
from cityvision.pipeline.model_resolve import describe_models, resolve_model_b_paths
from cityvision.pipeline.traffic import TrafficCounter
from cityvision.pipeline.types import Detection, RunMeta
from cityvision.pipeline.video_reader import VideoReader
from cityvision.report.html_report import write_html_report


def run_pipeline(
    source: str | Path,
    output_dir: str | Path,
    model: Optional[str] = None,
    model_b: Optional[str] = None,
    pipeline_cfg: Optional[Dict[str, Any]] = None,
    tracking: Optional[bool] = None,
    gps_path: Optional[str] = None,
    zones_path: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    city_id: Optional[str] = None,
    start_sec: Optional[float] = None,
    duration_sec: Optional[float] = None,
    stride: Optional[int] = None,
) -> Path:
    cfg = pipeline_cfg or load_pipeline_config(city_id=city_id)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    video_cfg = dict(cfg.get("video") or {})
    if start_sec is not None:
        video_cfg["start_sec"] = float(start_sec)
    if duration_sec is not None:
        video_cfg["duration_sec"] = float(duration_sec)
    if stride is not None:
        video_cfg["stride"] = int(stride)
    cfg["video"] = video_cfg
    det_cfg = cfg.get("detection", {})
    track_cfg = cfg.get("tracking", {})
    gps_cfg = cfg.get("gps", {})
    geo_cfg = cfg.get("geofence", {})
    traffic_cfg = cfg.get("traffic", {})
    events_cfg = cfg.get("events", {})
    conf_cfg = cfg.get("confidence", {})
    evidence_cfg = cfg.get("evidence", {})
    export_cfg = cfg.get("export", {})
    run_cfg = cfg.get("run", {})

    model_a = model or det_cfg.get("model_a") or "yolov8n.pt"
    model_b_paths = resolve_model_b_paths(det_cfg, cli_model_b=model_b)
    print(f"Model B loaded: {describe_models(model_b_paths)}")
    use_tracking = track_cfg.get("enabled", True) if tracking is None else tracking
    tracker_name = track_cfg.get("tracker", "bytetrack.yaml")

    vid = vehicle_id or run_cfg.get("vehicle_id", "BUS-DEMO")
    cam = camera_id or run_cfg.get("camera_id", "FRONT")
    model_tag = run_cfg.get("model_version_tag", "bootstrap-0.2.0")

    detector = DualModelDetector(
        model_a=model_a,
        model_b=model_b_paths,
        conf=float(det_cfg.get("conf", 0.35)),
        iou=float(det_cfg.get("iou", 0.45)),
        imgsz=int(det_cfg.get("imgsz", 640)),
        device=det_cfg.get("device"),
        allowed_classes=det_cfg.get("allowed_classes"),
        min_box_area=float(det_cfg.get("min_box_area", 0)),
        conf_discard=float(det_cfg.get("conf_discard", 0.55)),
        keep_low_conf=bool(det_cfg.get("keep_low_conf", False)),
    )

    gps_fixes = []
    gps_file = gps_path or gps_cfg.get("path")
    if gps_cfg.get("enabled", True) and gps_file:
        gps_fixes = load_gps_sidecar(gps_file)

    geofence: Optional[GeofenceEngine] = None
    zpath = zones_path or geo_cfg.get("path")
    if geo_cfg.get("enabled", True) and zpath:
        geofence = GeofenceEngine(
            zones=load_zones(zpath),
            vehicle_classes=geo_cfg.get("vehicle_classes") or ["car", "bus", "truck", "motorcycle"],
            min_dwell_frames=int(geo_cfg.get("min_dwell_frames", 3)),
            event_type=str(geo_cfg.get("event_type", "potential_bus_stop_obstruction")),
        )

    traffic: Optional[TrafficCounter] = None
    line_y_ratio = float(traffic_cfg.get("line_y_ratio", 0.55))
    if traffic_cfg.get("enabled", True):
        # line_y filled after we know height
        traffic = TrafficCounter(
            line_y=0,
            vehicle_classes=traffic_cfg.get("vehicle_classes")
            or ["car", "bus", "truck", "motorcycle"],
        )

    event_engine: Optional[EventEngine] = None
    if events_cfg.get("enabled", True):
        event_engine = EventEngine(events_cfg, conf_cfg, model_version=model_tag)

    writer: Optional[JsonlWriter] = None
    if export_cfg.get("write_json", True):
        writer = JsonlWriter(out / export_cfg.get("json_name", "detections.jsonl"))
        writer.open()

    video_writer: Optional[cv2.VideoWriter] = None
    class_counts: Counter = Counter()
    track_ids = set()
    det_total = 0
    all_dets: List[Detection] = []

    with VideoReader(
        source,
        stride=int(video_cfg.get("stride", 1)),
        max_frames=video_cfg.get("max_frames"),
        start_sec=float(video_cfg.get("start_sec") or 0),
        duration_sec=video_cfg.get("duration_sec"),
    ) as reader:
        if traffic is not None:
            traffic.line_y = reader.height * line_y_ratio

        meta = RunMeta(
            source=str(source),
            model_a=model_a,
            model_b=describe_models(model_b_paths) if model_b_paths else None,
            model_version=model_tag,
            fps=reader.fps,
            width=reader.width,
            height=reader.height,
            frame_count=reader.frame_count,
            vehicle_id=vid,
            camera_id=cam,
        )
        if writer:
            writer.write_meta(meta)

        if export_cfg.get("write_video", True):
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            video_path = out / export_cfg.get("video_name", "annotated.mp4")
            video_writer = cv2.VideoWriter(
                str(video_path),
                fourcc,
                max(reader.fps / max(1, int(video_cfg.get("stride", 1))), 1.0),
                (reader.width, reader.height),
            )

        total = reader.planned_emits()
        for batch in tqdm(reader, total=total, desc="frames"):
            dets = detector.infer(
                batch.image,
                batch.index,
                batch.timestamp_ms,
                tracking=use_tracking,
                tracker=tracker_name,
            )
            for det in dets:
                det.vehicle_id = vid
                det.camera_id = cam

            if gps_fixes:
                attach_gps_to_detections(
                    dets,
                    gps_fixes,
                    max_gap_ms=float(gps_cfg.get("max_interp_gap_ms", 2000)),
                )

            if geofence is not None:
                geofence.update(dets)
            if traffic is not None:
                traffic.update(dets)
            if event_engine is not None:
                event_engine.ingest(dets)

            for det in dets:
                class_counts[det.class_name] += 1
                det_total += 1
                if det.track_id is not None:
                    track_ids.add(det.track_id)
                all_dets.append(det)
                if writer:
                    writer.write_detection(det)

            if video_writer is not None:
                hud = [
                    f"{vid}/{cam}  f={batch.index}",
                    f"dets={len(dets)} tracks={len(track_ids)}",
                ]
                if dets and dets[0].lat is not None:
                    hud.append(f"gps={dets[0].lat:.5f},{dets[0].lon:.5f}")
                annotated = draw_detections(
                    batch.image,
                    dets,
                    line_y=traffic.line_y if traffic else None,
                    hud_lines=hud,
                )
                video_writer.write(annotated)

    if video_writer is not None:
        video_writer.release()

    traffic_stats = traffic.finalize().to_dict() if traffic is not None else {}
    geo_hits = geofence.finalized_hits() if geofence is not None else []

    events = []
    if event_engine is not None:
        events = event_engine.build(
            width=meta.width,
            height=meta.height,
            geofence_hits=geo_hits,
            geofence_event_type=str(
                geo_cfg.get("event_type", "potential_bus_stop_obstruction")
            ),
        )

    if evidence_cfg.get("enabled", True) and events:
        events = write_evidence_packs(
            source_video=source,
            events=events,
            output_dir=out,
            fps=meta.fps,
            seconds_before=float(evidence_cfg.get("seconds_before", 5)),
            seconds_after=float(evidence_cfg.get("seconds_after", 5)),
            save_full_frame=bool(evidence_cfg.get("save_full_frame", True)),
            save_crop=bool(evidence_cfg.get("save_crop", True)),
            save_clips=bool(evidence_cfg.get("save_clips", True)),
            max_events=int(evidence_cfg.get("max_events", 50)),
            draw_boxes=bool(evidence_cfg.get("draw_boxes", True)),
        )

    rejected_summary: Dict[str, Any] = {"count": 0, "written": 0, "reasons": {}}
    if events_cfg.get("dump_rejected", True) and event_engine is not None:
        rejected_summary = write_rejected_samples(
            source_video=source,
            rejected=event_engine.last_rejected,
            output_dir=out,
            max_samples=int(events_cfg.get("max_rejected", 200)),
        )

    event_dicts = [e.to_dict() for e in events]
    events_path = out / export_cfg.get("events_name", "events.json")
    events_path.write_text(
        json.dumps(event_dicts, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    traffic_path = out / export_cfg.get("traffic_name", "traffic.json")
    traffic_path.write_text(
        json.dumps(traffic_stats, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    review_queue = sum(1 for e in events if e.confidence_band == "manual_review")
    summary = {
        "detections": det_total,
        "class_counts": dict(class_counts),
        "unique_tracks": len(track_ids),
        "tracking": use_tracking,
        "events": len(events),
        "rejected": rejected_summary,
        "review_queue": review_queue,
        "gps_enabled": bool(gps_fixes),
        "geofence_hits": len(geo_hits),
        "model_a": model_a,
        "model_b": [str(p) for p in model_b_paths],
        "model_b_names": describe_models(model_b_paths),
        "model_version": model_tag,
        "vehicle_id": vid,
        "camera_id": cam,
        "city_id": run_cfg.get("city_id") or city_id,
    }
    if writer:
        writer.write_summary(summary)
        writer.close()

    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if export_cfg.get("write_report", True):
        write_html_report(
            path=out / export_cfg.get("report_name", "report.html"),
            meta=meta.to_dict(),
            summary=summary,
            events=event_dicts,
            traffic=traffic_stats,
        )

    return out
