"""Endpoints behind the web app's work-order board and admin screens."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from cityvision.api.deps import (
    Principal,
    get_principal,
    get_store,
    optional_city_id,
    require_admin,
    require_city_row,
    require_operator,
    resolve_city_id,
)
from cityvision.api.security import hash_password
from cityvision.domain.statuses import RESERVED_USERNAMES, USER_ROLES, WorkOrderStatus

router = APIRouter(prefix="/api", tags=["admin"])

DEFAULT_UNITS = ["roads", "sanitation", "parks", "other"]
LANGUAGES = {"en"}  # grows as translations are added to web/src/locales


def _city_for(principal: Principal, requested: Optional[str] = None) -> str:
    """The city an admin action applies to: always their own unless cross-city."""
    city = principal.city_id if not principal.is_cross_city else resolve_city_id(principal, requested)
    if not city:
        raise HTTPException(status_code=422, detail="city_required")
    return city


# ---------- work orders ----------


@router.get("/work-orders/board")
def work_order_board(
    status: Optional[str] = None,
    city_id: Optional[str] = None,
    limit: int = Query(500, ge=1, le=2000),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    """Work orders with what the board needs: event type, place and a thumbnail."""
    from cityvision.api.routers.media_jobs import attach_media_urls

    store = get_store()
    rows = store.list_work_orders(
        status=status, limit=limit, city_id=optional_city_id(principal, city_id)
    )
    firsts = store.first_images_for_events([r["event_id"] for r in rows])
    attach_media_urls(list(firsts.values()))
    for r in rows:
        m = firsts.get(r["event_id"])
        r["thumb_url"] = m.get("url") if m else None
    return rows


class WorkOrderPatch(BaseModel):
    status: Optional[WorkOrderStatus] = None
    note: Optional[str] = Field(None, max_length=2000)
    assignee: Optional[str] = Field(None, max_length=120)
    unit: Optional[str] = Field(None, max_length=60)
    due_date: Optional[date] = None
    clear_due_date: bool = False


@router.patch("/work-orders/{work_order_id}/board")
def patch_work_order_board(
    work_order_id: int,
    body: WorkOrderPatch,
    principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    store = get_store()
    require_city_row(store.get_work_order(work_order_id), principal, detail="work order not found")
    row = store.update_work_order(
        work_order_id,
        status=body.status,
        note=body.note,
        assignee=body.assignee,
        unit=body.unit,
        due_date=body.due_date,
        clear_due_date=body.clear_due_date,
        actor=principal.username,
    )
    if not row:
        raise HTTPException(status_code=404, detail="work order not found")
    return row


# ---------- users ----------


class UserPatch(BaseModel):
    display_name: Optional[str] = Field(None, max_length=120)
    role: Optional[Literal["viewer", "operator", "admin", "superadmin"]] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=200)


@router.patch("/users/{username}")
def patch_user(
    username: str, body: UserPatch, principal: Principal = Depends(require_admin)
) -> dict[str, Any]:
    store = get_store()
    user = require_city_row(store.get_user(username), principal, detail="user not found")
    if username.strip().lower() in RESERVED_USERNAMES:
        raise HTTPException(status_code=422, detail="username_reserved")
    is_self = principal.username == username
    if principal.role != "superadmin" and (user.get("role") == "superadmin" or body.role == "superadmin"):
        raise HTTPException(status_code=403, detail="superadmin_only")
    if is_self and (body.active is False or (body.role and body.role != user.get("role"))):
        # Avoid locking yourself out of the admin screens.
        raise HTTPException(status_code=422, detail="cannot_change_own_access")
    if body.role is not None and body.role not in USER_ROLES:
        raise HTTPException(status_code=422, detail="unsupported_role")

    changes: dict[str, Any] = {}
    if body.display_name is not None or body.role is not None or body.password is not None:
        role = body.role or user.get("role") or "operator"
        store.upsert_user(
            username,
            display_name=(body.display_name if body.display_name is not None else user.get("display_name")) or username,
            role=role,
            password_hash=hash_password(body.password) if body.password else None,
            city_id=user.get("city_id"),
        )
        if body.display_name is not None:
            changes["display_name"] = body.display_name
        if body.role is not None:
            changes["role"] = body.role
        if body.password:
            changes["password_reset"] = True
    if body.active is not None:
        store.set_user_active(username, body.active)
        changes["active"] = body.active
    store.add_audit(
        actor=principal.username,
        action="user_update",
        entity_type="user",
        entity_id=str(user["id"]),
        detail={"username": username, **changes},
        city_id=user.get("city_id"),
    )
    fresh = store.get_user(username) or {}
    return {k: fresh.get(k) for k in ("id", "username", "display_name", "role", "active", "city_id")}


# ---------- city settings ----------


class CitySettings(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    timezone: Optional[str] = Field(None, max_length=64)
    language: Optional[str] = None
    work_order_units: Optional[list[str]] = Field(None, max_length=30)


def _settings_view(city: dict[str, Any]) -> dict[str, Any]:
    props = city.get("props") or {}
    return {
        "id": city["id"],
        "name": city.get("name"),
        "timezone": city.get("timezone"),
        "language": props.get("language") or "en",
        "work_order_units": props.get("work_order_units") or DEFAULT_UNITS,
        "languages": sorted(LANGUAGES),
    }


@router.get("/city-settings")
def get_city_settings(
    city_id: Optional[str] = None, principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    """Readable by every signed-in user: the UI needs units and language."""
    city = get_store().get_city(_city_for(principal, city_id))
    if not city:
        raise HTTPException(status_code=404, detail="city not found")
    return _settings_view(city)


@router.patch("/city-settings")
def patch_city_settings(
    body: CitySettings,
    city_id: Optional[str] = None,
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    cid = _city_for(principal, city_id)
    props: dict[str, Any] = {}
    if body.language is not None:
        if body.language not in LANGUAGES:
            raise HTTPException(status_code=422, detail="unsupported_language")
        props["language"] = body.language
    if body.work_order_units is not None:
        units = [u.strip() for u in body.work_order_units if u and u.strip()]
        if not units:
            raise HTTPException(status_code=422, detail="units_required")
        props["work_order_units"] = list(dict.fromkeys(u[:60] for u in units))
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="unsupported_timezone") from exc
    store = get_store()
    city = store.update_city(cid, name=body.name, timezone=body.timezone, props_merge=props)
    if not city:
        raise HTTPException(status_code=404, detail="city not found")
    store.add_audit(
        actor=principal.username,
        action="city_settings_update",
        entity_type="city",
        entity_id=cid,
        detail=body.model_dump(exclude_none=True),
        city_id=cid,
    )
    return _settings_view(city)


# ---------- zones & routes upload ----------


class GeoJsonUpload(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[dict[str, Any]] = Field(..., max_length=5000)


@router.post("/zones/upload")
def upload_zones(
    body: GeoJsonUpload,
    city_id: Optional[str] = None,
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    from cityvision.db.zones import ingest_zones_features

    cid = _city_for(principal, city_id)
    store = get_store()
    out = ingest_zones_features(body.model_dump(), store=store, city_id=cid)
    store.add_audit(
        actor=principal.username,
        action="zones_upload",
        entity_type="zone",
        detail={"upserted": out["zones_upserted"], "skipped": out["skipped"]},
        city_id=cid,
    )
    return out


@router.post("/routes/upload")
def upload_routes(
    body: GeoJsonUpload,
    city_id: Optional[str] = None,
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    """LineString features become routes (id from `id`/`route_id`, else generated)."""
    cid = _city_for(principal, city_id)
    store = get_store()
    upserted: list[str] = []
    skipped = 0
    for i, feat in enumerate(body.features):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        coords = geom.get("coordinates")
        if geom.get("type") != "LineString" or not isinstance(coords, list) or len(coords) < 2:
            skipped += 1
            continue
        rid = str(props.get("route_id") or props.get("id") or f"{cid}-route-{i + 1}")[:80]
        name = str(props.get("name") or rid)[:120]
        store.upsert_route(rid, name, city=cid, linestring_lonlat=[[float(c[0]), float(c[1])] for c in coords])
        upserted.append(rid)
    store.add_audit(
        actor=principal.username,
        action="routes_upload",
        entity_type="route",
        detail={"upserted": len(upserted), "skipped": skipped},
        city_id=cid,
    )
    return {"city_id": cid, "routes_upserted": len(upserted), "route_ids": upserted, "skipped": skipped}


# ---------- review stats & audit ----------


@router.get("/kpis/review")
def review_kpis(
    days: int = Query(7, ge=1, le=365),
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    return get_store().review_stats(city_id=resolve_city_id(principal, city_id), days=days)


@router.get("/audit/search")
def search_audit(
    actor: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    before_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    city_id: Optional[str] = None,
    principal: Principal = Depends(require_admin),
) -> list[dict[str, Any]]:
    return get_store().list_audit(
        limit=limit,
        entity_type=entity_type,
        city_id=optional_city_id(principal, city_id),
        actor=actor,
        action=action,
        entity_id=entity_id,
        before_id=before_id,
    )
