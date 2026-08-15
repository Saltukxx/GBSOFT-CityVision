"""CLI: python -m cityvision.edge.agent upload|heartbeat|drain-outbox"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from cityvision.edge.agent.uploader import (
    drain_outbox,
    heartbeat,
    upload_video_file,
    upload_with_outbox,
)


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or default


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cityvision.edge.agent", description="Memphis thin uploader")
    p.add_argument("--api-base", default=_env("CITYVISION_API_BASE", "http://127.0.0.1:8088"))
    p.add_argument("--token", default=_env("CITYVISION_EDGE_TOKEN"))
    p.add_argument("--work-dir", default=_env("CITYVISION_EDGE_WORK_DIR", "outputs/edge_agent"))
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload", help="Upload video (+ optional GPS) to central analyze")
    up.add_argument("--video", required=True, type=Path)
    up.add_argument("--gps", type=Path, default=None)
    up.add_argument("--vehicle-id", default=None)
    up.add_argument("--city-id", default=None)
    up.add_argument("--route-id", default=None)
    up.add_argument("--run-name", default=None)
    up.add_argument("--camera-id", default="FRONT")
    up.add_argument("--outbox", action="store_true", help="Retry and queue to outbox on failure")

    hb = sub.add_parser("heartbeat", help="POST /api/edge/heartbeat")
    hb.add_argument("--disk-free-gb", type=float, default=None)

    sub.add_parser("drain-outbox", help="Retry failed uploads in work-dir/outbox")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.token:
        print("error: --token or CITYVISION_EDGE_TOKEN required", file=sys.stderr)
        return 2
    work = Path(args.work_dir)
    outbox = work / "outbox"

    if args.cmd == "heartbeat":
        props = {}
        if args.disk_free_gb is not None:
            props["disk_free_gb"] = args.disk_free_gb
        print(json.dumps(heartbeat(api_base=args.api_base, token=args.token, props=props), indent=2))
        return 0

    if args.cmd == "drain-outbox":
        results = drain_outbox(api_base=args.api_base, token=args.token, outbox_dir=outbox)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0 if all(r.get("ok") for r in results) or not results else 1

    if args.cmd == "upload":
        if not args.video.is_file():
            print(f"error: video not found: {args.video}", file=sys.stderr)
            return 2
        kwargs = dict(
            api_base=args.api_base,
            token=args.token,
            video_path=args.video,
            gps_path=args.gps,
            vehicle_id=args.vehicle_id,
            city_id=args.city_id,
            route_id=args.route_id,
            run_name=args.run_name,
            camera_id=args.camera_id,
        )
        if args.outbox:
            body = upload_with_outbox(outbox_dir=outbox, **kwargs)
        else:
            body = upload_video_file(**kwargs)
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
