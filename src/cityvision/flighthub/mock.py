"""A stand-in FlightHub 2 server, so the Dock flow is runnable before hardware exists.

It answers the same endpoints as `FlightHubConfig` resolves and serves a real video file
as the task's media, which means `pull_flight_task` can drive the whole chain —
download → object store → analyze_video → events — with nothing but Python running.

Routes are derived from the shared endpoint table rather than hardcoded, so a corrected
path in `config.py` moves the mock with it and the two cannot drift apart.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple
from urllib.parse import urlparse

from cityvision.flighthub.config import FlightHubConfig, config_for

log = logging.getLogger(__name__)

DEFAULT_USER_TOKEN = "mock-organization-key"
DEFAULT_PROJECT_UUID = "11111111-1111-4111-8111-111111111111"
DEFAULT_TASK_UUID = "22222222-2222-4222-8222-222222222222"
# Erzurum city centre — matches CITYVISION_DEFAULT_CITY so demo events land on the map.
DEFAULT_LAT = 39.9086
DEFAULT_LON = 41.2769
# Epoch millis, fixed so trajectory output is reproducible across runs.
DEFAULT_START_MS = 1_755_000_000_000

_MEDIA_PREFIX = "/media/"


def _route_patterns(config: FlightHubConfig) -> List[Tuple[str, Pattern[str]]]:
    routes: List[Tuple[str, Pattern[str]]] = []
    for name, template in config.endpoints.items():
        raw = config.api_prefix + template
        parts = raw.split("{task_uuid}")
        pattern = "(?P<task_uuid>[^/]+)".join(re.escape(part) for part in parts)
        routes.append((name, re.compile("^" + pattern + "$")))
    return routes


class MockFlightHub:
    """Threaded mock server. Use as a context manager or call start()/stop()."""

    def __init__(
        self,
        *,
        video_path: Optional[Path] = None,
        host: str = "127.0.0.1",
        port: int = 0,
        user_token: str = DEFAULT_USER_TOKEN,
        project_uuid: str = DEFAULT_PROJECT_UUID,
        task_uuid: str = DEFAULT_TASK_UUID,
        task_status: str = "success",
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
        start_ms: int = DEFAULT_START_MS,
        trajectory_points: int = 12,
        trajectory_step_ms: int = 1000,
    ) -> None:
        self.video_path = Path(video_path) if video_path else None
        self.user_token = user_token
        self.project_uuid = project_uuid
        self.task_uuid = task_uuid
        self.task_status = task_status
        self.lat = lat
        self.lon = lon
        self.start_ms = start_ms
        self.trajectory_points = trajectory_points
        self.trajectory_step_ms = trajectory_step_ms
        self.requests: List[Tuple[str, str]] = []

        self._config = config_for(f"http://{host}:{port}", user_token=user_token)
        self._routes = _route_patterns(self._config)
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._server.mock = self  # type: ignore[attr-defined]
        self._thread: Optional[threading.Thread] = None

    # ---- lifecycle ----------------------------------------------------

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[0], self.port
        return f"http://{host}:{port}"

    def config(self, *, project_scoped: bool = True) -> FlightHubConfig:
        """A client config pointed at this instance."""
        return config_for(
            self.base_url,
            user_token=self.user_token,
            project_uuid=self.project_uuid if project_scoped else "",
        )

    def start(self) -> "MockFlightHub":
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.1},
            daemon=True,
            name="mock-flighthub",
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "MockFlightHub":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    # ---- payloads -----------------------------------------------------

    def match(self, path: str) -> Optional[Tuple[str, Dict[str, str]]]:
        for name, pattern in self._routes:
            found = pattern.match(path)
            if found:
                return name, found.groupdict()
        return None

    def media_name(self) -> str:
        return self.video_path.name if self.video_path else "DJI_mock_0001.mp4"

    def payload(self, endpoint: str, path_args: Dict[str, str]) -> Any:
        if endpoint == "system_status":
            return {"status": "normal", "version": "mock"}
        if endpoint == "project":
            return {
                "list": [
                    {
                        "uuid": self.project_uuid,
                        "name": "CityVision Pilot",
                        "updated_at": self.start_ms,
                    }
                ],
                "pagination": {"total": 1, "page": 1, "page_size": 10},
            }
        if endpoint == "flight_task_list":
            return {"list": [self._task()], "pagination": {"total": 1, "page": 1, "page_size": 10}}
        if endpoint == "flight_task":
            return self._task(path_args.get("task_uuid"))
        if endpoint == "flight_task_media":
            return {"list": [self._media()]}
        if endpoint == "flight_task_trajectory":
            return {"list": self._trajectory()}
        if endpoint == "live_stream_start":
            return {"url": f"{self.base_url}/live/mock.flv", "url_type": "flv"}
        return {}

    def _task(self, task_uuid: Optional[str] = None) -> Dict[str, Any]:
        end_ms = self.start_ms + self.trajectory_points * self.trajectory_step_ms
        return {
            "task_uuid": task_uuid or self.task_uuid,
            "name": "Kordon koridoru - otonom tarama",
            "status": self.task_status,
            "begin_time": self.start_ms,
            "end_time": end_ms,
            "dock_sn": "MOCKDOCK0001",
            "aircraft_sn": "MOCKM4TD0001",
        }

    def _media(self) -> Dict[str, Any]:
        name = self.media_name()
        size = self.video_path.stat().st_size if self.video_path and self.video_path.exists() else 0
        return {
            "uuid": "33333333-3333-4333-8333-333333333333",
            "name": Path(name).stem,
            "file_type": "video",
            "suffix": Path(name).suffix or ".mp4",
            "size": size,
            "preview_url": f"{self.base_url}{_MEDIA_PREFIX}{name}",
            "original_url": f"{self.base_url}{_MEDIA_PREFIX}{name}",
            "create_at": self.start_ms,
            "update_at": self.start_ms,
        }

    def _trajectory(self) -> List[Dict[str, Any]]:
        # A straight ~1 m/step leg; enough for interpolation to have real work to do.
        step_deg = 0.00001
        return [
            {
                "timestamp": self.start_ms + i * self.trajectory_step_ms,
                "latitude": self.lat + i * step_deg,
                "longitude": self.lon + i * step_deg,
                "height": 60.0,
                "speed": 5.0,
                "yaw": 90.0,
            }
            for i in range(self.trajectory_points)
        ]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def mock(self) -> MockFlightHub:
        return self.server.mock  # type: ignore[attr-defined,no-any-return]

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug("mock-flighthub %s", fmt % args)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        path = urlparse(self.path).path
        self.mock.requests.append(("GET", path))

        if path.startswith(_MEDIA_PREFIX):
            self._serve_media(path[len(_MEDIA_PREFIX) :])
            return

        matched = self.mock.match(path)
        if not matched:
            self._send_json(404, {"code": 404, "message": "not found", "data": {}})
            return
        if self.headers.get("X-User-Token") != self.mock.user_token:
            self._send_json(
                401, {"code": 401, "message": "invalid X-User-Token", "data": {}}
            )
            return

        endpoint, path_args = matched
        data = self.mock.payload(endpoint, path_args)
        self._send_json(200, {"code": 0, "message": "success", "data": data})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.do_GET()

    def _serve_media(self, name: str) -> None:
        video = self.mock.video_path
        if not video or not video.exists() or name != video.name:
            self._send_json(404, {"code": 404, "message": "media not found", "data": {}})
            return
        body = video.read_bytes()
        content_type = mimetypes.guess_type(video.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
