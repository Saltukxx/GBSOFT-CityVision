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
from cityvision.geo.geofence import GeofenceEngine, load_zones
from cityvision.pipeline.types import Detection, RunMeta
from cityvision.report.html_report import write_html_report


def _make_video(path: Path, frames: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (640, 480))
    for i in range(frames):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (45, 48, 52)
        cv2.rectangle(img, (200, 300), (280, 360), (30, 30, 30), -1)  # fake pothole patch
        cv2.putText(img, f"sim {i}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        w.write(img)
    w.release()


def main() -> int:
    out = ROOT / "outputs" / "simulate_001"
    out.mkdir(parents=True, exist_ok=True)
    video = ROOT / "data" / "samples" / "simulate.mp4"
    _make_video(video)

    dets = [
        Detection(10, 666, "pothole", 0.91, (200, 300, 280, 360), track_id=1, lat=39.91814, lon=41.27318, vehicle_id="BUS-4", camera_id="FRONT"),
        Detection(20, 1333, "pothole", 0.89, (205, 302, 285, 362), track_id=2, lat=39.91816, lon=41.27313, vehicle_id="BUS-7", camera_id="FRONT"),
        Detection(30, 2000, "pothole", 0.93, (198, 298, 278, 358), track_id=3, lat=39.91811, lon=41.27321, vehicle_id="BUS-11", camera_id="FRONT"),
        Detection(40, 2666, "street_waste", 0.84, (400, 200, 480, 280), track_id=4, lat=39.92180, lon=41.27195, vehicle_id="BUS-7", camera_id="RIGHT"),
        Detection(45, 3000, "car", 0.95, (100, 180, 220, 300), track_id=9, lat=39.92182, lon=41.27195, vehicle_id="BUS-7", camera_id="RIGHT"),
        Detection(46, 3066, "car", 0.94, (100, 180, 220, 300), track_id=9, lat=39.92183, lon=41.27196, vehicle_id="BUS-7", camera_id="RIGHT"),
        Detection(47, 3133, "car", 0.96, (100, 180, 220, 300), track_id=9, lat=39.92184, lon=41.27197, vehicle_id="BUS-7", camera_id="RIGHT"),
    ]

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

    geo = GeofenceEngine(
        zones=load_zones(ROOT / "configs" / "zones.example.geojson"),
        vehicle_classes=["car", "bus", "truck", "motorcycle"],
        min_dwell_frames=3,
    )
    geo.update(dets)
    events = engine.build(640, 480, geofence_hits=geo.finalized_hits())
    events = write_evidence_packs(video, events, out, fps=15.0, max_events=20)

    event_dicts = [e.to_dict() for e in events]
    (out / "events.json").write_text(json.dumps(event_dicts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "detections": len(dets),
        "events": len(events),
        "unique_tracks": 5,
        "review_queue": sum(1 for e in events if e.confidence_band == "manual_review"),
        "note": "offline simulation (no YOLO)",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    meta = RunMeta(
        source=str(video),
        model_a="simulated",
        model_b=None,
        model_version="simulate-0.2.0",
        fps=15,
        width=640,
        height=480,
        frame_count=90,
        vehicle_id="BUS-7",
        camera_id="FRONT",
    )
    write_html_report(out / "report.html", meta.to_dict(), summary, event_dicts, traffic={"vehicles_per_minute": 12.5})
    print(f"Simulated events → {out.resolve()}")
    print(json.dumps(summary, indent=2))
    for e in events:
        print(e.event_id, e.type, e.confidence, e.confidence_band, e.observations, e.zone_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
