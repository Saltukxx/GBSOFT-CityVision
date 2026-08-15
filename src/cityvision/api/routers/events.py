from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from cityvision.api.deps import (
    Principal,
    get_store,
    require_operator,
    resolve_city_id,
)
from cityvision.api.schemas import ReviewBody, StatusUpdate, WorkOrderCreate
from cityvision.api.security import actor_from_request_headers

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
def list_events(
    status: Optional[str] = None,
    type: Optional[str] = Query(None, alias="type"),
    city_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
) -> list[dict[str, Any]]:
    return get_store().list_events(
        status=status,
        event_type=type,
        limit=limit,
        city_id=resolve_city_id(city_id),
    )


@router.get("/events/near")
def events_near(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(50.0, ge=1, le=5000),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    return get_store().events_near(lat, lon, radius_m, limit)


@router.get("/events/{event_id}")
def get_event(event_id: str) -> dict[str, Any]:
    store = get_store()
    row = store.get_event(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    from cityvision.api.routers.media_jobs import attach_media_urls

    row["media"] = attach_media_urls(store.list_event_media(event_id))
    row["observations"] = store.list_observations(event_id)
    row["reviews"] = store.list_reviews(event_id=event_id, limit=50)
    return row


@router.patch("/events/{event_id}/status")
def patch_status(
    event_id: str,
    body: StatusUpdate,
    principal: Principal = Depends(require_operator),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    store = get_store()
    actor = principal.username if principal.is_authenticated else actor_from_request_headers(
        authorization, x_api_key
    )
    try:
        ok = store.update_event_status(event_id, body.status, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="event not found")
    return store.get_event(event_id) or {}


@router.post("/events/{event_id}/work-order")
def create_work_order(
    event_id: str,
    body: WorkOrderCreate,
    principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    store = get_store()
    if not store.get_event(event_id):
        raise HTTPException(status_code=404, detail="event not found")
    wid = store.create_work_order(
        event_id, body.unit, body.note, actor=principal.username
    )
    return {"work_order_id": wid, "event": store.get_event(event_id)}


@router.post("/events/{event_id}/review")
def review_event(
    event_id: str,
    body: ReviewBody,
    principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    reviewer = (
        principal.username
        if principal.is_authenticated and principal.username != "anonymous"
        else body.reviewer
    )
    try:
        return get_store().add_review(
            event_id=event_id,
            label=body.label,
            note=body.note,
            reviewer=reviewer,
            source="api",
            unit=body.unit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="event not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reviews")
def list_reviews(
    event_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    return get_store().list_reviews(event_id=event_id, limit=limit)


@router.get("/work-orders")
def list_work_orders(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    return get_store().list_work_orders(status=status, limit=limit)
