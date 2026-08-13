from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from cityvision.api.deps import get_store, require_admin, require_operator, resolve_city_id
from cityvision.api.schemas import CameraBody, RouteBody, VehicleBody

router = APIRouter(prefix="/api", tags=["fleet"])


@router.get("/cities")
def list_cities() -> list[dict[str, Any]]:
    from cityvision.cities import list_city_packs

    db_cities = get_store().list_cities()
    packs = set(list_city_packs())
    for row in db_cities:
        row["has_pack"] = row.get("id") in packs
    # Include pack-only cities not yet in DB
    known = {r.get("id") for r in db_cities}
    for cid in packs:
        if cid not in known:
            db_cities.append({"id": cid, "name": cid, "has_pack": True})
    return db_cities


@router.post("/cities/{city_id}/apply-pack")
def apply_pack(city_id: str, _principal=Depends(require_admin)) -> dict[str, Any]:
    from cityvision.cities import apply_city_pack, load_city_pack

    try:
        pack = load_city_pack(city_id)
    except FileNotFoundError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return apply_city_pack(pack, store=get_store())


@router.get("/vehicles")
def list_vehicles() -> list[dict[str, Any]]:
    return get_store().list_vehicles()


@router.post("/vehicles")
def create_vehicle(
    body: VehicleBody, _principal=Depends(require_operator)
) -> dict[str, Any]:
    vid = get_store().upsert_vehicle(body.id, body.name, body.plate, body.route_id)
    return {"id": vid}


@router.get("/cameras")
def list_cameras(vehicle_id: Optional[str] = None) -> list[dict[str, Any]]:
    return get_store().list_cameras(vehicle_id=vehicle_id)


@router.post("/cameras")
def create_camera(
    body: CameraBody, _principal=Depends(require_operator)
) -> dict[str, Any]:
    cid = get_store().upsert_camera(body.id, body.vehicle_id, body.label, body.facing)
    return {"id": cid}


@router.get("/routes")
def list_routes(city_id: Optional[str] = None) -> list[dict[str, Any]]:
    # list_routes currently returns all; city filter via SQL if column present
    rows = get_store().list_routes()
    cid = resolve_city_id(city_id)
    if not cid:
        return rows
    return [r for r in rows if r.get("city_id") == cid or r.get("city") == cid]


@router.post("/routes")
def create_route(body: RouteBody, _principal=Depends(require_admin)) -> dict[str, Any]:
    rid = get_store().upsert_route(
        body.id,
        body.name,
        city=body.city,
        linestring_lonlat=body.coordinates,
    )
    return {"id": rid}


@router.get("/assets")
def list_assets(
    type: Optional[str] = Query(None, alias="type"),
) -> list[dict[str, Any]]:
    return get_store().list_assets(asset_type=type)


@router.get("/users")
def list_users(_principal=Depends(require_admin)) -> list[dict[str, Any]]:
    return get_store().list_users()
