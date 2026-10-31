from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from cityvision.config import ROOT


def _read_env_file_value(key: str) -> Optional[str]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return None
    prefix = f"{key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(prefix) and len(line) > len(prefix):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key) or _read_env_file_value(key) or default


def read_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Env lookup with `.env` fallback, for optional subsystems that keep their own config."""
    return _env(key, default)


@lru_cache(maxsize=1)
def get_settings() -> "Settings":
    return Settings()


class Settings:
    """Runtime settings for API / DB (env first, then .env)."""

    def __init__(self) -> None:
        self.root: Path = ROOT
        self.database_url: str = (
            _env("DATABASE_URL")
            or "postgresql://cityvision:cityvision@localhost:5435/cityvision"
        )
        self.api_host: str = _env("CITYVISION_API_HOST", "127.0.0.1") or "127.0.0.1"
        self.api_port: int = int(_env("CITYVISION_API_PORT", "8088") or "8088")
        self.outputs_dir: Path = ROOT / "outputs"
        self.object_store_dir: Path = Path(
            _env("CITYVISION_OBJECT_STORE", str(ROOT / "data" / "object_store"))
            or (ROOT / "data" / "object_store")
        )
        self.api_key: str = (_env("CITYVISION_API_KEY", "") or "").strip()
        self.redis_url: str = (
            _env("REDIS_URL", "redis://localhost:6380/0") or "redis://localhost:6380/0"
        )
        self.redis_queue_key: str = _env("CITYVISION_REDIS_QUEUE", "cityvision:jobs") or "cityvision:jobs"
        # When set, use MinIO/S3 instead of local filesystem store
        self.s3_endpoint: str = (_env("CITYVISION_S3_ENDPOINT", "") or "").strip()
        self.s3_access_key: str = _env("CITYVISION_S3_ACCESS_KEY", "cityvision") or "cityvision"
        self.s3_secret_key: str = (
            _env("CITYVISION_S3_SECRET_KEY", "cityvisionsecret") or "cityvisionsecret"
        )
        self.s3_bucket: str = _env("CITYVISION_S3_BUCKET", "cityvision") or "cityvision"
        self.s3_region: str = _env("CITYVISION_S3_REGION", "us-east-1") or "us-east-1"
        self.jwt_secret: str = (_env("CITYVISION_JWT_SECRET", "") or "").strip()
        self.jwt_expire_minutes: int = int(_env("CITYVISION_JWT_EXPIRE_MIN", "720") or "720")
        # Evidence media (frames, crops, clips) is personal data under KVKK.
        # It is gated as soon as any credential is configured; a bare local
        # pilot with no API key and no JWT secret stays open as before.
        self.media_url_ttl_sec: int = int(_env("CITYVISION_MEDIA_URL_TTL_SEC", "3600") or "3600")
        self.webhook_url: str = (_env("CITYVISION_WEBHOOK_URL", "") or "").strip()
        # Cross-run spatial merge radius (meters) when ingesting events
        self.merge_radius_m: float = float(_env("CITYVISION_MERGE_RADIUS_M", "15") or "15")
        self.merge_enabled: bool = (_env("CITYVISION_MERGE_ENABLED", "1") or "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.default_city: str = (_env("CITYVISION_DEFAULT_CITY", "erzurum") or "erzurum").strip()
        # When on, the server derives city from the principal (never from a
        # client-supplied city_id except as a same-city convenience / superadmin
        # filter) and anonymous dashboard reads are closed. Default off so
        # existing single-city pilots keep working until staging is flipped.
        self.strict_tenancy: bool = (
            _env("CITYVISION_STRICT_TENANCY", "0") or "0"
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        rbac_raw = (_env("CITYVISION_RBAC", "auto") or "auto").strip().lower()
        if rbac_raw == "auto":
            # Enforce roles when JWT or API key is configured
            self.rbac_enabled: bool = bool(self.jwt_secret or self.api_key)
        else:
            self.rbac_enabled = rbac_raw not in {"0", "false", "no", "off"}
        self.edge_upload_dir: Path = Path(
            _env("CITYVISION_EDGE_UPLOAD_DIR", str(ROOT / "outputs" / "edge"))
            or (ROOT / "outputs" / "edge")
        )
        self.edge_max_upload_mb: int = int(_env("CITYVISION_EDGE_MAX_UPLOAD_MB", "200") or "200")
        # Browser flight uploads (resumable, chunked) — much larger than edge segments.
        self.flight_max_upload_gb: float = float(
            _env("CITYVISION_FLIGHT_MAX_UPLOAD_GB", "20") or "20"
        )
        # When true, jobs always run in-process threads (ignore Redis). Useful for tests/local.
        self.job_inline: bool = (_env("CITYVISION_JOB_INLINE", "0") or "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.auth_exempt_prefixes: tuple[str, ...] = (
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
            "/static",
            "/report",
            "/api/auth/login",
            "/api/auth/config",
        )

    @property
    def auth_configured(self) -> bool:
        """True when any credential mechanism is set up."""
        return bool(self.api_key or self.jwt_secret)

    @property
    def media_url_secret(self) -> str:
        """Signing key for short-lived evidence media URLs."""
        return self.jwt_secret or self.api_key
