from __future__ import annotations

import csv
import io
import json
import time
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cityvision.api.deps import (
    Principal,
    get_principal,
    get_store,
    optional_city_id,
    require_admin,
    require_city_row,
    resolve_city_id,
)
from cityvision.api.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from cityvision.db.store import UsernameConflict
from cityvision.domain.statuses import RESERVED_USERNAMES, USER_ROLES
from cityvision.settings import get_settings

router = APIRouter(prefix="/api", tags=["auth-export"])


class LoginBody(BaseModel):
    username: str
    password: str


class PasswordSetBody(BaseModel):
    username: str
    password: str = Field(..., min_length=6)
    role: str = "operator"
    display_name: str = ""
    city_id: Optional[str] = None


@router.post("/auth/login")
def login(body: LoginBody) -> dict[str, Any]:
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="JWT not configured (CITYVISION_JWT_SECRET)")
    user = get_store().get_user(body.username)
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="invalid credentials")
    ph = user.get("password_hash")
    if not ph or not verify_password(body.password, ph):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(
        user["username"],
        user.get("role") or "operator",
        city_id=user.get("city_id"),
        expires_minutes=settings.jwt_expire_minutes,
    )
    get_store().add_audit(
        actor=user["username"],
        action="login",
        entity_type="user",
        entity_id=str(user["id"]),
        city_id=user.get("city_id"),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "display_name": user.get("display_name"),
            "role": user.get("role"),
            "city_id": user.get("city_id"),
        },
    }


@router.get("/auth/me")
def me(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    if not principal.is_authenticated:
        raise HTTPException(status_code=401, detail="missing bearer token")
    user = get_store().get_user(principal.username)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return {
        "username": user["username"],
        "display_name": user.get("display_name"),
        "role": user.get("role"),
        "city_id": user.get("city_id"),
        "active": user.get("active"),
    }


@router.post("/auth/users")
def set_user_password(
    body: PasswordSetBody, principal: Principal = Depends(require_admin)
) -> dict[str, Any]:
    """Create/update operator with password (admin when RBAC on)."""
    settings = get_settings()
    if body.role not in USER_ROLES:
        raise HTTPException(status_code=422, detail=f"unsupported role: {body.role}")
    if body.role == "superadmin" and principal.role != "superadmin":
        raise HTTPException(status_code=403, detail="cannot create superadmin")
    if body.username.strip().lower() in RESERVED_USERNAMES:
        raise HTTPException(status_code=422, detail="username is reserved")
    city_id = body.city_id
    if not principal.is_cross_city:
        city_id = principal.city_id
    elif body.role == "superadmin":
        city_id = None
    else:
        city_id = resolve_city_id(principal, city_id)
    try:
        uid = get_store().upsert_user(
            body.username,
            display_name=body.display_name or body.username,
            role=body.role,
            password_hash=hash_password(body.password),
            city_id=city_id,
        )
    except UsernameConflict as exc:
        raise HTTPException(status_code=409, detail="username already taken") from exc
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    get_store().add_audit(
        actor=principal.username,
        action="user_upsert",
        entity_type="user",
        entity_id=str(uid),
        detail={"username": body.username, "role": body.role},
        city_id=city_id,
    )
    return {"id": uid, "username": body.username, "jwt_configured": bool(settings.jwt_secret)}


@router.get("/audit")
def list_audit(
    limit: int = Query(100, ge=1, le=1000),
    entity_type: Optional[str] = None,
    city_id: Optional[str] = None,
    principal: Principal = Depends(require_admin),
) -> list[dict[str, Any]]:
    return get_store().list_audit(
        limit=limit,
        entity_type=entity_type,
        city_id=optional_city_id(principal, city_id),
    )


@router.get("/events/export.csv")
def export_events_csv(
    status: Optional[str] = None,
    type: Optional[str] = Query(None, alias="type"),
    city_id: Optional[str] = None,
    limit: int = Query(2000, ge=1, le=10000),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    rows = get_store().list_events(
        status=status,
        event_type=type,
        limit=limit,
        city_id=resolve_city_id(principal, city_id),
    )
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "event_id",
            "type",
            "status",
            "lat",
            "lon",
            "confidence",
            "severity",
            "zone_id",
            "vehicle_id",
            "observations",
            "updated_at",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=events.csv"},
    )


@router.get("/jobs/{job_id}/stream")
def stream_job(
    job_id: int, principal: Principal = Depends(get_principal)
) -> StreamingResponse:
    """Server-Sent Events for job status until terminal state."""

    def gen() -> Iterator[str]:
        store = get_store()
        first = store.get_job(job_id)
        try:
            require_city_row(first, principal, detail="not found")
        except HTTPException as exc:
            yield f"event: error\ndata: {json.dumps({'detail': exc.detail})}\n\n"
            return
        for _ in range(120):
            row = store.get_job(job_id)
            if not row:
                yield f"event: error\ndata: {json.dumps({'detail': 'not found'})}\n\n"
                return
            payload = json.dumps(row, default=str)
            yield f"data: {payload}\n\n"
            if row.get("status") in {"succeeded", "failed"}:
                yield "event: done\ndata: {}\n\n"
                return
            time.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")
