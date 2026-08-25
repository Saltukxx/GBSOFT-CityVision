#!/usr/bin/env python3
"""
FlightHub 2 OpenAPI helper: probe the connection, list flights, pull one into the pipeline.

The dock binds to a single cloud platform, so FlightHub 2 keeps flight operations
(routes, schedule, dock health, live view) and CityVision pulls finished flights over
the OpenAPI. Detection stays local.

    # no hardware: run the mock in one shell, point the client at it in another
    python scripts/flighthub_sync.py mock --video data/samples/smoke.mp4
    CITYVISION_FH2_BASE_URL=http://127.0.0.1:8099 \
    CITYVISION_FH2_USER_TOKEN=mock-organization-key \
        python scripts/flighthub_sync.py tasks

    # real deployment
    python scripts/flighthub_sync.py projects
    python scripts/flighthub_sync.py pull <task_uuid>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.flighthub.client import FlightHubClient  # noqa: E402
from cityvision.flighthub.config import (  # noqa: E402
    PROVISIONAL_ENDPOINTS,
    load_flighthub_config,
)
from cityvision.flighthub.ingest import (  # noqa: E402
    pull_completed_tasks,
    pull_flight_task,
)
from cityvision.flighthub.mock import DEFAULT_USER_TOKEN, MockFlightHub  # noqa: E402


def _dump(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _cmd_status(args: argparse.Namespace) -> int:
    config = load_flighthub_config()
    client = FlightHubClient(config)
    _dump(
        {
            "base_url": config.base_url,
            "project_uuid": config.project_uuid or None,
            "system_status": client.system_status(),
            "provisional_endpoints": {
                name: config.endpoints[name] for name in PROVISIONAL_ENDPOINTS
            },
        }
    )
    return 0


def _cmd_projects(args: argparse.Namespace) -> int:
    _dump(FlightHubClient().list_projects(page=args.page, page_size=args.page_size))
    return 0


def _cmd_tasks(args: argparse.Namespace) -> int:
    _dump(FlightHubClient().list_flight_tasks(page=args.page, page_size=args.page_size))
    return 0


def _cmd_media(args: argparse.Namespace) -> int:
    client = FlightHubClient()
    _dump(
        {
            "task": client.get_flight_task(args.task_uuid),
            "media": client.get_task_media(args.task_uuid),
        }
    )
    return 0


def _cmd_pull(args: argparse.Namespace) -> int:
    if args.task_uuid:
        result = pull_flight_task(
            args.task_uuid,
            city_id=args.city,
            vehicle_id=args.vehicle,
            require_success=not args.any_status,
        )
    else:
        result = pull_completed_tasks(city_id=args.city, vehicle_id=args.vehicle, limit=args.limit)
    _dump(result)
    return 0


def _cmd_mock(args: argparse.Namespace) -> int:
    video = Path(args.video).resolve() if args.video else None
    if video and not video.exists():
        print(f"video not found: {video}", file=sys.stderr)
        return 2
    mock = MockFlightHub(video_path=video, host=args.host, port=args.port)
    mock.start()
    print(f"mock FlightHub 2 on {mock.base_url}")
    print(f"  CITYVISION_FH2_BASE_URL={mock.base_url}")
    print(f"  CITYVISION_FH2_USER_TOKEN={DEFAULT_USER_TOKEN}")
    print(f"  CITYVISION_FH2_PROJECT_UUID={mock.project_uuid}")
    print(f"  task_uuid={mock.task_uuid}   media={mock.media_name()}")
    print("Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        mock.stop()
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="probe auth + show which endpoints are unverified")
    status.set_defaults(func=_cmd_status)

    for name, handler, helptext in (
        ("projects", _cmd_projects, "list projects (gives X-Project-Uuid)"),
        ("tasks", _cmd_tasks, "list flight tasks"),
    ):
        cmd = sub.add_parser(name, help=helptext)
        cmd.add_argument("--page", type=int, default=1)
        cmd.add_argument("--page-size", type=int, default=10)
        cmd.set_defaults(func=handler)

    media = sub.add_parser("media", help="show one task and its media files")
    media.add_argument("task_uuid")
    media.set_defaults(func=_cmd_media)

    pull = sub.add_parser("pull", help="download media + trajectory and queue analysis")
    pull.add_argument("task_uuid", nargs="?", help="omit to pull all completed tasks")
    pull.add_argument("--city", default=None, help="city id (default: CITYVISION_DEFAULT_CITY)")
    pull.add_argument("--vehicle", default=None, help="existing vehicles.id to attribute the run to")
    pull.add_argument("--limit", type=int, default=None, help="max tasks when pulling all")
    pull.add_argument(
        "--any-status",
        action="store_true",
        help="pull even if the task is not reported finished",
    )
    pull.set_defaults(func=_cmd_pull)

    mock = sub.add_parser("mock", help="run a stand-in FlightHub 2 (no hardware needed)")
    mock.add_argument("--video", default=None, help="video file to serve as the task media")
    mock.add_argument("--host", default="127.0.0.1")
    mock.add_argument("--port", type=int, default=8099)
    mock.set_defaults(func=_cmd_mock)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
