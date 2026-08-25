"""FlightHub 2 OpenAPI client (stdlib only, matching cityvision.edge.agent.uploader)."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cityvision.flighthub.config import FlightHubConfig, load_flighthub_config

log = logging.getLogger(__name__)

# FlightHub wraps every response as {"code": 0, "message": "success", "data": {...}}
SUCCESS_CODE = 0
_DOWNLOAD_CHUNK = 1 << 20


class FlightHubError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class FlightHubClient:
    def __init__(self, config: Optional[FlightHubConfig] = None) -> None:
        self.config = config or load_flighthub_config()
        self.config.require()

    # ---- raw plumbing -------------------------------------------------

    def _ssl_context(self) -> Optional[ssl.SSLContext]:
        if self.config.verify_tls:
            return None
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _call(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        project_scoped: bool = True,
        **path_args: object,
    ) -> Any:
        url = self.config.url(endpoint, **path_args)
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean)}"
        headers = self.config.headers(project_scoped=project_scoped)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(
                request, timeout=self.config.timeout_sec, context=self._ssl_context()
            ) as response:
                raw = response.read()
                status = response.status
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise FlightHubError(
                f"FlightHub {method} {endpoint} failed: HTTP {exc.code} {detail}",
                http_status=exc.code,
            ) from exc
        except URLError as exc:
            raise FlightHubError(
                f"FlightHub {method} {endpoint} unreachable at {url}: {exc.reason}"
            ) from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FlightHubError(
                f"FlightHub {endpoint} returned non-JSON body (HTTP {status})"
            ) from exc
        if not isinstance(payload, dict):
            raise FlightHubError(f"FlightHub {endpoint} returned {type(payload).__name__}, want object")
        code = payload.get("code")
        if code != SUCCESS_CODE:
            raise FlightHubError(
                f"FlightHub {endpoint} rejected the call: code={code} "
                f"message={payload.get('message')!r}",
                code=code if isinstance(code, int) else None,
                http_status=status,
            )
        return payload.get("data")

    # ---- confirmed endpoints -----------------------------------------

    def system_status(self) -> Any:
        return self._call("system_status", project_scoped=False)

    def list_projects(self, *, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        data = self._call(
            "project",
            params={"page": page, "page_size": page_size},
            project_scoped=False,
        )
        return _as_list(data)

    # ---- provisional endpoints (see config.PROVISIONAL_ENDPOINTS) -----

    def list_flight_tasks(self, *, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        data = self._call("flight_task_list", params={"page": page, "page_size": page_size})
        return _as_list(data)

    def get_flight_task(self, task_uuid: str) -> Dict[str, Any]:
        data = self._call("flight_task", task_uuid=task_uuid)
        return data if isinstance(data, dict) else {}

    def get_task_media(self, task_uuid: str) -> List[Dict[str, Any]]:
        data = self._call("flight_task_media", task_uuid=task_uuid)
        return _as_list(data)

    def get_task_trajectory(self, task_uuid: str) -> Any:
        return self._call("flight_task_trajectory", task_uuid=task_uuid)

    # ---- media download ----------------------------------------------

    def download_to(self, url: str, dest: Path) -> Path:
        """Fetch a presigned media URL. No auth headers: the signature carries them."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"Accept": "*/*"}, method="GET")
        try:
            with urlopen(
                request, timeout=self.config.timeout_sec, context=self._ssl_context()
            ) as response, dest.open("wb") as handle:
                while True:
                    chunk = response.read(_DOWNLOAD_CHUNK)
                    if not chunk:
                        break
                    handle.write(chunk)
        except HTTPError as exc:
            raise FlightHubError(
                f"media download failed: HTTP {exc.code} for {url}", http_status=exc.code
            ) from exc
        except URLError as exc:
            raise FlightHubError(f"media download unreachable: {url}: {exc.reason}") from exc
        return dest


def _as_list(data: Any) -> List[Dict[str, Any]]:
    """FlightHub returns collections as data.list; tolerate a bare list too."""
    if isinstance(data, dict):
        rows = data.get("list")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".ts"}


def video_media(media: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only video files — stills go to mapping products, not our pipeline."""
    out: List[Dict[str, Any]] = []
    for item in media:
        file_type = str(item.get("file_type") or "").lower()
        suffix = str(item.get("suffix") or "").lower()
        if not suffix:
            suffix = Path(str(item.get("name") or "")).suffix.lower()
        if file_type == "video" or suffix in VIDEO_SUFFIXES:
            out.append(item)
    return out
