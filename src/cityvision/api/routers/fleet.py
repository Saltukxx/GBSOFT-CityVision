from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from cityvision.api.deps import (
    Principal,
    get_principal,
    get_store,
    optional_city_id,
    require_admin,
    require_operator,
    resolve_city_id,
)
from cityvision.api.schemas import CameraBody, RouteBody, VehicleBody
from cityvision.settings import get_settings

router = APIRouter(prefix="/api", tags=["fleet"])


@router.get("/cities")
def list_cities(principal: Principal = Depends(get_principal)) -> list[dict[str, Any]]:
    from cityvision.cities import list_city_packs

    db_cities = get_store().list_cities()
    packs = set(list_city_packs())
    for row in db_cities:
        row["has_pack"] = row.get("id") in packs
    known = {r.get("id") for r in db_cities}
    for cid in packs:
        if cid not in known:
            db_cities.append({"id": cid, "name": cid, "has_pack": True})
    if get_settings().strict_tenancy and not principal.is_cross_city:
        return [r for r in db_cities if r.get("id") == principal.city_id]
    return db_cities


@router.post("/cities/{city_id}/apply-pack")
def apply_pack(
    city_id: str, principal: Principal = Depends(require_admin)
) -> dict[str, Any]:
    from cityvision.cities import apply_city_pack, load_city_pack

    resolve_city_id(principal, city_id)
    try:
        pack = load_city_pack(city_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return apply_city_pack(pack, store=get_store())


@router.get("/vehicles")
def list_vehicles(
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return get_store().list_vehicles(city_id=optional_city_id(principal, city_id))


@router.post("/vehicles")
def create_vehicle(
    body: VehicleBody,
    principal: Principal = Depends(require_operator),
    city_id: Optional[str] = None,
) -> dict[str, Any]:
    cid = resolve_city_id(principal, city_id)
    vid = get_store().upsert_vehicle(
        body.id, body.name, body.plate, body.route_id, city_id=cid
    )
    return {"id": vid}


@router.get("/cameras")
def list_cameras(
    vehicle_id: Optional[str] = None,
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return get_store().list_cameras(
        vehicle_id=vehicle_id, city_id=optional_city_id(principal, city_id)
    )


@router.post("/cameras")
def create_camera(
    body: CameraBody, principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    store = get_store()
    if get_settings().strict_tenancy and body.vehicle_id and not principal.is_cross_city:
        owned = {v["id"] for v in store.list_vehicles(city_id=principal.city_id)}
        if body.vehicle_id not in owned:
            raise HTTPException(status_code=404, detail="vehicle not found")
    cid = store.upsert_camera(body.id, body.vehicle_id, body.label, body.facing)
    return {"id": cid}


@router.get("/routes")
def list_routes(
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return get_store().list_routes(city_id=resolve_city_id(principal, city_id))


@router.post("/routes")
def create_route(
    body: RouteBody, principal: Principal = Depends(require_admin)
) -> dict[str, Any]:
    resolve_city_id(principal, body.city)
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
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return get_store().list_assets(
        asset_type=type, city_id=optional_city_id(principal, city_id)
    )


@router.get("/users")
def list_users(
    city_id: Optional[str] = None,
    principal: Principal = Depends(require_admin),
) -> list[dict[str, Any]]:
    cid = optional_city_id(principal, city_id)
    return get_store().list_users(city_id=cid)
