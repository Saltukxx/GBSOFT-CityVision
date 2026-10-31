"""Flights for the operator web app: list, detail and resumable browser uploads.

A flight is an `edge_video_uploads` row, whatever brought it in (drone device,
FlightHub sync or browser upload). Browser uploads go through the
`/api/flights/uploads` endpoints; see `cityvision.flights.uploads`.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from starlette.requests import ClientDisconnect

from cityvision.api.deps import (
    Principal,
    get_principal,
    get_store,
    optional_city_id,
    require_city_row,
    require_operator,
    resolve_city_id,
)
from cityvision.flights import uploads as fu
from cityvision.settings import get_settings
from cityvision.workers.jobs import enqueue_job

router = APIRouter(prefix="/api/flights", tags=["flights"])

# Statuses that are still moving; the web app polls while any flight has one.
ACTIVE_STATUSES = {"uploading", "received", "queued", "analyzing"}


def _source(row: dict[str, Any]) -> str:
    payload = row.get("payload") or {}
    src = payload.get("source")
    if src == "flighthub2":
        return "flighthub"
    if src == "web":
        return "upload"
    return "device"


def _present(row: dict[str, Any]) -> dict[str, Any]:
    """Shape a flight row for the web app (no storage keys or local paths)."""
    payload = row.get("payload") or {}
    status = row.get("status")
    progress = row.get("job_progress")
    if status == "succeeded":
        progress = 1.0
    out = {
        "id": row["upload_id"],
        "name": payload.get("name") or payload.get("task_name") or payload.get("run_name")
        or payload.get("filename") or row["upload_id"][:8],
        "filename": payload.get("filename"),
        "source": _source(row),
        "device_name": row.get("device_name"),
        "city_id": row.get("city_id"),
        "route_id": row.get("route_id"),
        "flight_date": payload.get("flight_date"),
        "uploaded_by": payload.get("uploaded_by"),
        "bytes": row.get("bytes"),
        "status": status,
        "progress": progress,
        "error": row.get("error") or row.get("job_error"),
        "has_telemetry": bool(row.get("gps_object_key") or payload.get("has_telemetry")),
        "trajectory_warning": payload.get("trajectory_warning"),
        "duplicate_of": payload.get("duplicate_of"),
        "candidates": row.get("candidates") or 0,
        "holdout": bool(row.get("holdout")),
        "run_id": row.get("run_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "processing_started_at": row.get("job_started_at"),
        "processing_finished_at": row.get("job_finished_at"),
    }
    if status == "uploading":
        size = int(row.get("bytes") or 0)
        out["upload"] = {
            "chunk_size": fu.CHUNK_SIZE,
            "chunks": fu.chunk_count(size),
            "received": fu.received_chunks(row["upload_id"]),
        }
    return out


def _flight_or_404(upload_id: str, principal: Principal) -> dict[str, Any]:
    if not fu.valid_upload_id(upload_id):
        raise HTTPException(status_code=404, detail="flight not found")
    return require_city_row(get_store().get_flight(upload_id), principal, detail="flight not found")


def _uploading_or_409(upload_id: str, principal: Principal) -> dict[str, Any]:
    row = _flight_or_404(upload_id, principal)
    if row.get("status") != "uploading":
        raise HTTPException(status_code=409, detail="upload is already complete")
    return row


# ---------- read ----------


@router.get("")
def list_flights(
    status: Optional[str] = None,
    city_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    rows = get_store().list_flights(
        city_id=optional_city_id(principal, city_id), status=status, limit=limit
    )
    return [_present(r) for r in rows]


@router.get("/tracks")
def flight_tracks(
    days: int = Query(30, ge=1, le=730),
    route_id: Optional[str] = None,
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    """Flown GPS tracks ([lon, lat] pairs), newest first — for the map's flight-path layer."""
    return get_store().flight_tracks(
        city_id=optional_city_id(principal, city_id), days=days, route_id=route_id
    )


@router.get("/{upload_id}")
def get_flight(upload_id: str, principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    row = _flight_or_404(upload_id, principal)
    out = _present(row)
    store = get_store()
    track: list[Any] = []
    event_ids: list[str] = []
    if row.get("run_id"):
        run = store.get_run(int(row["run_id"])) or {}
        summary = run.get("summary") or {}
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except json.JSONDecodeError:
                summary = {}
        if isinstance(summary, dict) and isinstance(summary.get("track"), list):
            track = summary["track"]
        event_ids = store.list_run_event_ids(int(row["run_id"]))
    out["track"] = track  # [[lon, lat], ...]
    out["event_ids"] = event_ids
    out["adherence"] = (
        store.route_adherence(str(row["route_id"]), track) if row.get("route_id") and len(track) > 1 else None
    )
    return out


class RouteAssign(BaseModel):
    route_id: Optional[str] = None


@router.patch("/{upload_id}/route")
def assign_route(
    upload_id: str, body: RouteAssign, principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    """Link a flight to the planned route it flew (or unlink with null)."""
    store = get_store()
    row = _flight_or_404(upload_id, principal)
    if body.route_id:
        require_city_row(store.get_route(body.route_id), principal, detail="route not found")
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE edge_video_uploads SET route_id = %s, updated_at = NOW() WHERE upload_id = %s",
                (body.route_id, upload_id),
            )
        store._commit(conn)
    store.add_audit(
        actor=principal.username,
        action="flight_route",
        entity_type="flight",
        entity_id=upload_id,
        detail={"route_id": body.route_id},
        city_id=row.get("city_id"),
    )
    return {"id": upload_id, "route_id": body.route_id}


# ---------- browser upload ----------


class UploadCreate(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    size: int = Field(..., gt=0)
    name: Optional[str] = Field(None, max_length=120)
    route_id: Optional[str] = None
    flight_date: Optional[date] = None
    city_id: Optional[str] = None


@router.post("/uploads", status_code=201)
def create_upload(
    body: UploadCreate, principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    if not body.filename.lower().endswith(fu.VIDEO_SUFFIXES):
        raise HTTPException(status_code=422, detail="unsupported_video_format")
    max_bytes = int(get_settings().flight_max_upload_gb * 1024**3)
    if body.size > max_bytes:
        raise HTTPException(status_code=413, detail="file_too_large")

    store = get_store()
    city = principal.city_id or resolve_city_id(principal, body.city_id)
    device_id = fu.web_device_id(store, city)
    upload_id = uuid.uuid4().hex
    suffix = Path(body.filename).suffix.lower()
    object_key = f"flights/{city or 'global'}/{upload_id}/video{suffix}"

    store.create_edge_video_upload(
        upload_id,
        device_id,
        object_key,
        f"{fu.PENDING_CHECKSUM_PREFIX}{upload_id}",
        city_id=city,
        route_id=body.route_id or None,
        nbytes=body.size,
        status="uploading",
        payload={
            "source": "web",
            "filename": body.filename,
            "name": (body.name or "").strip() or Path(body.filename).stem,
            "flight_date": body.flight_date.isoformat() if body.flight_date else None,
            "uploaded_by": principal.username,
        },
    )
    (fu.staging_dir(upload_id) / "chunks").mkdir(parents=True, exist_ok=True)
    store.add_audit(
        actor=principal.username,
        action="flight_upload_start",
        entity_type="flight",
        entity_id=upload_id,
        detail={"bytes": body.size, "filename": body.filename},
        city_id=city,
    )
    return _present(store.get_flight(upload_id) or {})


@router.put("/uploads/{upload_id}/chunks/{index}")
async def put_chunk(
    upload_id: str,
    index: int,
    request: Request,
    principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    row = _uploading_or_409(upload_id, principal)
    size = int(row.get("bytes") or 0)
    try:
        expected = fu.expected_chunk_bytes(index, size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="chunk_out_of_range") from exc

    final = fu.chunk_path(upload_id, index)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.with_suffix(f".tmp-{uuid.uuid4().hex[:8]}")
    written = 0
    try:
        with tmp.open("wb") as fh:
            async for block in request.stream():
                written += len(block)
                if written > expected:
                    raise HTTPException(status_code=422, detail="chunk_size_mismatch")
                fh.write(block)
        if written != expected:
            raise HTTPException(status_code=422, detail="chunk_size_mismatch")
        tmp.replace(final)  # atomic: a half-written chunk never counts as received
    except ClientDisconnect:
        # Browser paused/cancelled mid-chunk; the partial file is dropped below
        # and the chunk is simply sent again on resume.
        raise HTTPException(status_code=400, detail="client_disconnected") from None
    finally:
        tmp.unlink(missing_ok=True)
    return {"index": index, "received": True}


@router.put("/uploads/{upload_id}/telemetry")
async def put_telemetry(
    upload_id: str,
    request: Request,
    filename: str = Query(..., min_length=1, max_length=255),
    principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    _uploading_or_409(upload_id, principal)
    suffix = Path(filename).suffix.lower()
    if suffix not in fu.TELEMETRY_SUFFIXES:
        raise HTTPException(status_code=422, detail="unsupported_telemetry_format")
    folder = fu.staging_dir(upload_id)
    for old in folder.glob("telemetry.*"):
        old.unlink(missing_ok=True)
    dest = folder / f"telemetry{suffix}"
    written = 0
    try:
        with dest.open("wb") as fh:
            async for block in request.stream():
                written += len(block)
                if written > fu.TELEMETRY_MAX_BYTES:
                    raise HTTPException(status_code=413, detail="telemetry_too_large")
                fh.write(block)
    except (HTTPException, ClientDisconnect) as exc:
        dest.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail="client_disconnected") from None
    if written == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="empty_telemetry")
    get_store().update_edge_video_upload(
        upload_id, payload_merge={"has_telemetry": True, "telemetry_filename": filename}
    )
    return {"telemetry": True, "bytes": written}


@router.post("/uploads/{upload_id}/complete")
def complete_upload(
    upload_id: str, principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    row = _uploading_or_409(upload_id, principal)
    missing = fu.missing_chunks(upload_id, int(row.get("bytes") or 0))
    if missing:
        raise HTTPException(
            status_code=409,
            detail={"code": "chunks_missing", "missing": missing[:50], "count": len(missing)},
        )
    store = get_store()
    store.update_edge_video_upload(upload_id, status="received")
    job_id, _ = enqueue_job(
        store, "flight_upload", {"upload_id": upload_id, "city_id": row.get("city_id")}
    )
    store.update_edge_video_upload(upload_id, job_id=job_id)
    store.add_audit(
        actor=principal.username,
        action="flight_upload_complete",
        entity_type="flight",
        entity_id=upload_id,
        detail={"job_id": job_id},
        city_id=row.get("city_id"),
    )
    return _present(store.get_flight(upload_id) or {})


@router.delete("/uploads/{upload_id}", status_code=204)
def cancel_upload(upload_id: str, principal: Principal = Depends(require_operator)) -> None:
    row = _uploading_or_409(upload_id, principal)
    shutil.rmtree(fu.staging_dir(upload_id), ignore_errors=True)
    get_store().update_edge_video_upload(upload_id, status="cancelled")
    get_store().add_audit(
        actor=principal.username,
        action="flight_upload_cancel",
        entity_type="flight",
        entity_id=upload_id,
        city_id=row.get("city_id"),
    )
