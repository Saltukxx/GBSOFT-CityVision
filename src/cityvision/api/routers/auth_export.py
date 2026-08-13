from __future__ import annotations

import csv
import io
import json
import time
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cityvision.api.deps import get_store, require_admin
from cityvision.api.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
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
        expires_minutes=settings.jwt_expire_minutes,
    )
    get_store().add_audit(
        actor=user["username"],
        action="login",
        entity_type="user",
        entity_id=str(user["id"]),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "display_name": user.get("display_name"),
            "role": user.get("role"),
        },
    }


@router.get("/auth/me")
def me(authorization: Optional[str] = Header(None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(status_code=401, detail="invalid token")
    user = get_store().get_user(str(payload.get("sub")))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return {
        "username": user["username"],
        "display_name": user.get("display_name"),
        "role": user.get("role"),
        "active": user.get("active"),
    }


@router.post("/auth/users")
def set_user_password(
    body: PasswordSetBody, _principal=Depends(require_admin)
) -> dict[str, Any]:
    """Create/update operator with password (admin when RBAC on)."""
    settings = get_settings()
    uid = get_store().upsert_user(
        body.username,
        display_name=body.display_name or body.username,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    get_store().add_audit(
        actor="system",
        action="user_upsert",
        entity_type="user",
        entity_id=str(uid),
        detail={"username": body.username, "role": body.role},
    )
    return {"id": uid, "username": body.username, "jwt_configured": bool(settings.jwt_secret)}


@router.get("/audit")
def list_audit(
    limit: int = Query(100, ge=1, le=1000),
    entity_type: Optional[str] = None,
    _principal=Depends(require_admin),
) -> list[dict[str, Any]]:
    return get_store().list_audit(limit=limit, entity_type=entity_type)


@router.get("/events/export.csv")
def export_events_csv(
    status: Optional[str] = None,
    type: Optional[str] = Query(None, alias="type"),
    city_id: Optional[str] = None,
    limit: int = Query(2000, ge=1, le=10000),
) -> StreamingResponse:
    from cityvision.api.deps import resolve_city_id

    rows = get_store().list_events(
        status=status,
        event_type=type,
        limit=limit,
        city_id=resolve_city_id(city_id),
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
def stream_job(job_id: int) -> StreamingResponse:
    """Server-Sent Events for job status until terminal state."""

    def gen() -> Iterator[str]:
        store = get_store()
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
