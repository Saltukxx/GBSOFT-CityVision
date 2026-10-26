#!/usr/bin/env python3
"""Offline demo: synthetic detections → fusion → evidence → HTML report (no GPU/YOLO)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cv2
import numpy as np

from cityvision.events.engine import EventEngine
from cityvision.events.evidence import write_evidence_packs
from cityvision.pipeline.annotate import draw_detections
from cityvision.pipeline.export_json import JsonlWriter
from cityvision.pipeline.types import Detection, RunMeta
from cityvision.report.html_report import write_html_report


def _trail(n: int = 48) -> list[tuple[float, float]]:
    lat0, lon0 = 39.9055, 41.2650
    lat1, lon1 = 39.9220, 41.2780
    pts = []
    for i in range(n):
        t = i / max(n - 1, 1)
        pts.append((lat0 + (lat1 - lat0) * t, lon0 + (lon1 - lon0) * t))
    return pts


def _make_video(path: Path, frames: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (640, 480))
    for i in range(frames):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (45, 48, 52)
        cv2.rectangle(img, (200, 300), (280, 360), (30, 30, 30), -1)
        cv2.putText(img, f"sim {i}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        w.write(img)
    w.release()


def _write_annotated(src: Path, dest: Path, dets: list[Detection], frames: int, fps: float) -> None:
    cap = cv2.VideoCapture(str(src))
    writer = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 480))
    by_frame: dict[int, list[Detection]] = {}
    for det in dets:
        by_frame.setdefault(int(det.frame), []).append(det)
    for i in range(frames):
        ok, frame = cap.read()
        if not ok:
            break
        shown = by_frame.get(i, [])
        hud = [f"DJI-01/AERIAL  f={i}", f"dets={len(shown)}"]
        writer.write(draw_detections(frame, shown, hud_lines=hud))
    writer.release()
    cap.release()


def main() -> int:
    out = ROOT / "outputs" / "simulate_001"
    out.mkdir(parents=True, exist_ok=True)
    video = ROOT / "data" / "samples" / "simulate.mp4"
    frames = 90
    fps = 15.0
    _make_video(video, frames=frames)

    trail = _trail(48)
    dets: list[Detection] = []
    pit_lat, pit_lon = trail[20]
    dets.extend(
        [
            Detection(10, 666, "pothole", 0.91, (200, 300, 280, 360), track_id=1, lat=pit_lat, lon=pit_lon, vehicle_id="DJI-01", camera_id="AERIAL"),
            Detection(20, 1333, "pothole", 0.89, (205, 302, 285, 362), track_id=2, lat=pit_lat + 0.00002, lon=pit_lon - 0.00002, vehicle_id="DJI-01", camera_id="AERIAL"),
            Detection(30, 2000, "pothole", 0.93, (198, 298, 278, 358), track_id=3, lat=pit_lat - 0.00001, lon=pit_lon + 0.00001, vehicle_id="DJI-01", camera_id="AERIAL"),
            Detection(40, 2666, "street_waste", 0.84, (400, 200, 480, 280), track_id=4, lat=39.92180, lon=41.27195, vehicle_id="DJI-01", camera_id="AERIAL"),
        ]
    )

    conf_cfg = {
        "bands": {"discard": 0.70, "review": 0.85, "probable": 0.95},
        "repeat_bonus": 0.10,
        "multi_vehicle_bonus": 0.10,
        "gps_bonus": 0.05,
    }
    events_cfg = {
        "event_classes": ["pothole", "street_waste", "overflowing_container", "road_damage", "road_crack"],
        "fusion_radius_m": 15,
        "fusion_radius_norm": 0.05,
        "fusion_window_hours": 72,
        "min_observations": 1,
    }
    engine = EventEngine(events_cfg, conf_cfg, model_version="simulate-0.2.0")
    engine.ingest(dets)

    events = engine.build(640, 480)
    events = write_evidence_packs(video, events, out, fps=fps, max_events=20, draw_boxes=True)

    event_dicts = [e.to_dict() for e in events]
    (out / "events.json").write_text(
        json.dumps(event_dicts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = {
        "detections": len(dets),
        "events": len(events),
        "unique_tracks": 4,
        "review_queue": sum(1 for e in events if e.confidence_band == "manual_review"),
        "note": "offline simulation (no YOLO)",
        "vehicle_id": "DJI-01",
        "camera_id": "AERIAL",
        "city_id": "erzurum",
        "source": str(video),
        "model_a": "simulated",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    meta = RunMeta(
        source=str(video),
        model_a="simulated",
        model_b=None,
        model_version="simulate-0.2.0",
        fps=fps,
        width=640,
        height=480,
        frame_count=frames,
        vehicle_id="DJI-01",
        camera_id="AERIAL",
    )
    writer = JsonlWriter(out / "detections.jsonl")
    writer.open()
    writer.write_meta(meta)
    for det in dets:
        writer.write_detection(det)
    writer.write_summary(summary)
    writer.close()

    _write_annotated(video, out / "annotated.mp4", dets, frames, fps)
    write_html_report(
        out / "report.html",
        meta.to_dict(),
        summary,
        event_dicts,
        traffic={},
    )
    print(f"Simulated events → {out.resolve()}")
    print(json.dumps(summary, indent=2))
    for e in events:
        print(e.event_id, e.type, e.confidence, e.confidence_band, e.observations, e.zone_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
