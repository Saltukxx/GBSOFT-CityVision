from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from cityvision.api.deps import get_store, require_admin, resolve_city_id
from cityvision.api.schemas import ZonesIngestBody
from cityvision.config import ROOT
from cityvision.db.zones import ingest_zones_geojson

router = APIRouter(prefix="/api", tags=["zones"])


@router.get("/zones")
def list_zones(
    type: Optional[str] = Query(None, alias="type"),
    city_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    return get_store().list_zones(zone_type=type, city_id=resolve_city_id(city_id))


@router.get("/zones.geojson")
def zones_geojson(
    type: Optional[str] = Query(None, alias="type"),
    city_id: Optional[str] = None,
) -> dict[str, Any]:
    return get_store().zones_geojson(zone_type=type, city_id=resolve_city_id(city_id))


@router.get("/zones/{zone_id}/events")
def zone_events(zone_id: str, limit: int = Query(200, ge=1, le=2000)) -> list[dict[str, Any]]:
    return get_store().events_in_zone(zone_id, limit=limit)


@router.post("/zones/ingest")
def zones_ingest(
    body: ZonesIngestBody, _principal=Depends(require_admin)
) -> dict[str, Any]:
    path = Path(body.path)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"missing {path}")
    return ingest_zones_geojson(path, store=get_store())
