from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from cityvision.pipeline.runner import run_pipeline
from cityvision.review.feedback import append_feedback, apply_feedback_to_events


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cityvision", description="GBSoft City Vision platform CLI")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Full video → detect → track → events → report pipeline")
    run.add_argument("--source", required=True, help="Path to MP4/video")
    run.add_argument("--output", required=True, help="Output directory")
    run.add_argument("--model", default=None, help="Model A weights (default from config)")
    run.add_argument("--model-b", default=None, help="Model B infrastructure weights")
    run.add_argument(
        "--gps",
        default=None,
        help="GPS sidecar: DJI SRT, CSV, JSON, or JSONL (else look next to --source)",
    )
    run.add_argument("--zones", default=None, help="GeoJSON zones for geofence")
    run.add_argument("--vehicle-id", default=None, help="Asset id (drone/dock); alias of --drone-id")
    run.add_argument(
        "--drone-id",
        default=None,
        help="Drone / dock asset id (writes vehicle_id)",
    )
    run.add_argument("--camera-id", default=None)
    run.add_argument(
        "--profile",
        default=None,
        choices=["nadir", "oblique"],
        help="Flight profile overlay (default: oblique)",
    )
    run.add_argument(
        "--city",
        default=None,
        help="City pack id (configs/cities/<id>/) — merges pipeline.overlay.yaml + default zones",
    )
    run.add_argument("--no-track", action="store_true", help="Disable tracking")
    run.add_argument("--config", default=None, help="Optional pipeline.yaml override")
    run.add_argument("--start-sec", type=float, default=None, help="Skip this many seconds from the start")
    run.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Only process this many seconds (wall-clock of the source video)",
    )
    run.add_argument("--stride", type=int, default=None, help="Keep every Nth frame (overrides config)")

    rev = sub.add_parser("review", help="Human-in-the-loop feedback on an event")
    rev.add_argument("--output", required=True, help="Run output directory")
    rev.add_argument("--event-id", required=True)
    rev.add_argument(
        "--label",
        required=True,
        choices=["correct", "wrong", "work_order", "resolved"],
    )
    rev.add_argument("--note", default="")
    rev.add_argument("--reviewer", default="operator")
    rev.add_argument(
        "--apply",
        action="store_true",
        help="Also update events.json statuses from all feedback",
    )
    rev.add_argument(
        "--db",
        action="store_true",
        help="Also write feedback to PostgreSQL and update event status",
    )
    rev.add_argument("--unit", default="ops", help="Work-order unit when --label work_order --db")

    show = sub.add_parser("summary", help="Print summary.json for a run")
    show.add_argument("--output", required=True)

    zones = sub.add_parser("ingest-zones", help="Load GeoJSON zones into PostGIS")
    zones.add_argument(
        "--geojson",
        default=None,
        help="Path to zones GeoJSON (default: configs/zones.example.geojson)",
    )

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        from cityvision.config import DEFAULT_PROFILE, load_pipeline_config

        city = args.city
        profile = args.profile or DEFAULT_PROFILE
        pipeline_cfg = load_pipeline_config(
            path=args.config,
            city_id=city,
            profile=profile,
        )
        vehicle_id = args.drone_id or args.vehicle_id

        out = run_pipeline(
            source=args.source,
            output_dir=args.output,
            model=args.model,
            model_b=args.model_b,
            pipeline_cfg=pipeline_cfg,
            tracking=not args.no_track,
            gps_path=args.gps,
            zones_path=args.zones,
            vehicle_id=vehicle_id,
            camera_id=args.camera_id,
            city_id=city,
            start_sec=args.start_sec,
            duration_sec=args.duration,
            stride=args.stride,
            profile=profile,
        )
        summary_path = Path(out) / "summary.json"
        print(f"Done → {Path(out).resolve()}")
        if summary_path.exists():
            print(summary_path.read_text(encoding="utf-8"))
        report = Path(out) / "report.html"
        if report.exists():
            print(f"Report → {report.resolve()}")
        return 0

    if args.command == "review":
        path = append_feedback(
            output_dir=args.output,
            event_id=args.event_id,
            label=args.label,
            note=args.note,
            reviewer=args.reviewer,
        )
        print(f"Feedback → {path}")
        if args.apply:
            updated = apply_feedback_to_events(Path(args.output) / "events.json", args.output)
            print(f"Updated events → {updated}")
        if args.db:
            from cityvision.review.feedback import apply_feedback_to_db

            result = apply_feedback_to_db(
                event_id=args.event_id,
                label=args.label,
                note=args.note,
                reviewer=args.reviewer,
                unit=args.unit,
            )
            print(f"DB → {result}")
        return 0

    if args.command == "summary":
        p = Path(args.output) / "summary.json"
        print(p.read_text(encoding="utf-8"))
        return 0

    if args.command == "ingest-zones":
        from cityvision.config import ROOT
        from cityvision.db.zones import ingest_zones_geojson

        geo = args.geojson or str(ROOT / "configs" / "zones.example.geojson")
        print(ingest_zones_geojson(geo))
        return 0

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
