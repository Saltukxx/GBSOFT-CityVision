from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from cityvision.api.deps import get_store, resolve_city_id
from cityvision.settings import get_settings
from cityvision.storage import get_object_store
from cityvision.storage.local import LocalObjectStore
from cityvision.workers.jobs import redis_available

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, Any]:
    store = get_store()
    settings = get_settings()
    try:
        ok = store.ping()
        obj = get_object_store()
        storage = "s3" if not isinstance(obj, LocalObjectStore) else "local"
        return {
            "status": "ok" if ok else "degraded",
            "database": "postgresql+postgis",
            "service": "cityvision-api",
            "storage": storage,
            "s3_endpoint": settings.s3_endpoint or None,
            "redis": "up" if redis_available() else "down",
            "api_key_required": bool(settings.api_key),
            "rbac_enabled": bool(settings.rbac_enabled),
            "default_city": settings.default_city,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@router.get("/api/kpis")
def kpis(city_id: Optional[str] = None) -> dict[str, Any]:
    return get_store().kpis(city_id=resolve_city_id(city_id))
