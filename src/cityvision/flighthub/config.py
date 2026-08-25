"""FlightHub 2 OpenAPI connection settings.

Auth is two headers (DJI OpenAPI reference):
  * `X-User-Token`   — the organisation key from FlightHub 2 → My Organization →
                       Organization Settings → FlightHub Sync → Organization Key (a JWT)
  * `X-Project-Uuid` — project scope, read from `data.list.uuid` of the project list

Endpoint paths come in two groups. `CONFIRMED_ENDPOINTS` are quoted verbatim in DJI's
reference. `PROVISIONAL_ENDPOINTS` are calls DJI's Task Management tutorial names but
whose paths we could not read off the public reference; they stay env-overridable so a
wrong guess is a config change, not a code change. Verify them against the live
deployment's own OpenAPI page before the first real flight.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from cityvision.settings import read_env

DEFAULT_API_PREFIX = "/openapi/v0.1"

CONFIRMED_ENDPOINTS: Dict[str, str] = {
    "system_status": "/system_status",
    "project": "/project",
    "live_stream_start": "/live-stream/start",
}

PROVISIONAL_ENDPOINTS: Dict[str, str] = {
    "flight_task_list": "/flight-task",
    "flight_task": "/flight-task/{task_uuid}",
    "flight_task_media": "/flight-task/{task_uuid}/media",
    "flight_task_trajectory": "/flight-task/{task_uuid}/trajectory",
}


def _endpoint_env_key(name: str) -> str:
    return f"CITYVISION_FH2_EP_{name.upper()}"


def _bool_env(key: str, default: bool) -> bool:
    raw = read_env(key, "1" if default else "0") or ""
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass
class FlightHubConfig:
    """Where FlightHub 2 lives and how to authenticate against it."""

    base_url: str = ""
    user_token: str = ""
    project_uuid: str = ""
    api_prefix: str = DEFAULT_API_PREFIX
    language: str = "en"
    timeout_sec: float = 30.0
    verify_tls: bool = True
    endpoints: Dict[str, str] = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.user_token)

    def require(self) -> None:
        missing = [
            name
            for name, value in (
                ("CITYVISION_FH2_BASE_URL", self.base_url),
                ("CITYVISION_FH2_USER_TOKEN", self.user_token),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "FlightHub 2 is not configured; set " + ", ".join(missing) + ". "
                "Public cloud and On-Premises use different hosts, so there is no default."
            )

    def url(self, endpoint: str, **path_args: object) -> str:
        try:
            template = self.endpoints[endpoint]
        except KeyError as exc:
            raise KeyError(f"unknown FlightHub endpoint: {endpoint}") from exc
        path = template.format(**path_args) if path_args else template
        return f"{self.base_url.rstrip('/')}{self.api_prefix}{path}"

    def headers(self, *, project_scoped: bool) -> Dict[str, str]:
        headers = {
            "X-User-Token": self.user_token,
            "X-Language": self.language,
            "Accept": "application/json",
        }
        if project_scoped and self.project_uuid:
            headers["X-Project-Uuid"] = self.project_uuid
        return headers


def load_flighthub_config() -> FlightHubConfig:
    endpoints = dict(CONFIRMED_ENDPOINTS)
    endpoints.update(PROVISIONAL_ENDPOINTS)
    for name in list(endpoints):
        override = os.environ.get(_endpoint_env_key(name))
        if override:
            endpoints[name] = override
    return FlightHubConfig(
        base_url=(read_env("CITYVISION_FH2_BASE_URL", "") or "").strip(),
        user_token=(read_env("CITYVISION_FH2_USER_TOKEN", "") or "").strip(),
        project_uuid=(read_env("CITYVISION_FH2_PROJECT_UUID", "") or "").strip(),
        api_prefix=(read_env("CITYVISION_FH2_API_PREFIX", DEFAULT_API_PREFIX) or DEFAULT_API_PREFIX),
        language=(read_env("CITYVISION_FH2_LANGUAGE", "en") or "en"),
        timeout_sec=float(read_env("CITYVISION_FH2_TIMEOUT_SEC", "30") or "30"),
        verify_tls=_bool_env("CITYVISION_FH2_VERIFY_TLS", True),
        endpoints=endpoints,
    )


def config_for(base_url: str, *, user_token: str, project_uuid: str = "") -> FlightHubConfig:
    """Explicit config, used by tests and by the mock server CLI."""
    endpoints = dict(CONFIRMED_ENDPOINTS)
    endpoints.update(PROVISIONAL_ENDPOINTS)
    return FlightHubConfig(
        base_url=base_url,
        user_token=user_token,
        project_uuid=project_uuid,
        endpoints=endpoints,
    )
