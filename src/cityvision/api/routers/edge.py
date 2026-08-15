from __future__ import annotations

import hashlib
import json
import shutil
import uuid
import zipfile
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from cityvision.api.deps import Principal, get_store, require_admin
from cityvision.edge.package import (
    ensure_run_summary,
    generate_edge_token,
    hash_edge_token,
    safe_extract_zip,
    validate_events_json,
    verify_edge_token,
)
from cityvision.settings import get_settings
from cityvision.workers.jobs import enqueue_job

router = APIRouter(prefix="/api/edge", tags=["edge"])


class EdgeDeviceCreate(BaseModel):
    id: str = Field(..., min_length=2, max_length=64, examples=["edge-bus-17"])
    name: str = Field(..., examples=["BUS-17 Jetson"])
    city_id: Optional[str] = None
    vehicle_id: Optional[str] = None


def _edge_token_from_headers(
    x_edge_token: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    if x_edge_token and x_edge_token.strip():
        return x_edge_token.strip()
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return None


def require_edge_device(
    x_edge_token: Optional[str] = Header(None, alias="X-Edge-Token"),
    authorization: Optional[str] = Header(None),
) -> dict[str, Any]:
    token = _edge_token_from_headers(x_edge_token, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing edge token")
    store = get_store()
    device = store.get_edge_device_by_token_hash(hash_edge_token(token))
    if not device:
        verify_edge_token(token, "0" * 64)
        raise HTTPException(status_code=401, detail="invalid edge token")
    if not device.get("active", True):
        raise HTTPException(status_code=403, detail="device inactive")
    store.touch_edge_device(str(device["id"]))
    return device


@router.post("/devices")
def register_device(
    body: EdgeDeviceCreate,
    principal: Principal = Depends(require_admin),
) -> dict[str, Any]:
    """Register an edge device. Returns the plaintext token once."""
    store = get_store()
    settings = get_settings()
    token = generate_edge_token()
    token_hash = hash_edge_token(token)
    city_id = body.city_id or settings.default_city
    try:
        store.upsert_city(city_id, city_id.title())
    except Exception:
        pass
    store.upsert_edge_device(
        body.id,
        body.name,
        token_hash,
        city_id=city_id,
        vehicle_id=body.vehicle_id,
    )
    store.add_audit(
        actor=principal.username,
        action="edge_device_register",
        entity_type="edge_device",
        entity_id=body.id,
        detail={"city_id": city_id, "vehicle_id": body.vehicle_id},
    )
    return {
        "id": body.id,
        "name": body.name,
        "city_id": city_id,
        "vehicle_id": body.vehicle_id,
        "token": token,
        "note": "Store this token securely; it is shown only once.",
    }


@router.get("/devices")
def list_devices(
    city_id: Optional[str] = None,
    _principal: Principal = Depends(require_admin),
) -> list[dict[str, Any]]:
    return get_store().list_edge_devices(city_id=city_id)


@router.post("/upload")
async def upload_run_package(
    file: UploadFile = File(..., description="Zip of pipeline run (must include events.json)"),
    vehicle_id: Optional[str] = Form(None),
    city_id: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    device: dict[str, Any] = Depends(require_edge_device),
) -> dict[str, Any]:
    """Accept a zip run package from an edge device, extract safely, enqueue ingest."""
    settings = get_settings()
    store = get_store()
    max_bytes = int(settings.edge_max_upload_mb) * 1024 * 1024

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty upload")
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"upload exceeds {settings.edge_max_upload_mb} MB limit",
        )

    upload_id = uuid.uuid4().hex
    device_id = str(device["id"])
    cid = city_id or device.get("city_id") or settings.default_city
    vid = vehicle_id or device.get("vehicle_id")
    name = run_name or f"{device_id}-{upload_id[:8]}"
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)[:80]

    staging = settings.edge_upload_dir / device_id / upload_id
    staging.mkdir(parents=True, exist_ok=True)
    zip_path = staging / "package.zip"
    zip_path.write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()

    extract_root = staging / "extract"
    try:
        run_dir = safe_extract_zip(zip_path, extract_root)
        n_events, _ = validate_events_json(run_dir)
        ensure_run_summary(
            run_dir,
            city_id=str(cid) if cid else None,
            vehicle_id=str(vid) if vid else None,
            device_id=device_id,
            upload_id=upload_id,
        )
    except (ValueError, zipfile.BadZipFile, json.JSONDecodeError, OSError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    final_dir = settings.edge_upload_dir / device_id / safe_name
    if final_dir.exists():
        final_dir = settings.edge_upload_dir / device_id / f"{safe_name}-{upload_id[:6]}"
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        shutil.rmtree(final_dir)
    shutil.move(str(run_dir), str(final_dir))
    # Drop staging leftovers (zip + empty extract tree)
    shutil.rmtree(staging, ignore_errors=True)

    row = store.create_edge_upload(
        upload_id,
        device_id,
        str(final_dir.resolve()),
        city_id=str(cid) if cid else None,
        vehicle_id=str(vid) if vid else None,
        nbytes=len(raw),
        checksum=checksum,
        payload={"events": n_events, "filename": file.filename},
    )
    job_id, deduped = enqueue_job(
        store,
        "ingest_run",
        {
            "run_dir": str(final_dir.resolve()),
            "city_id": cid,
            "edge_upload_id": upload_id,
        },
    )
    store.update_edge_upload(upload_id, status="queued", job_id=job_id)
    store.add_audit(
        actor=device_id,
        action="edge_upload",
        entity_type="edge_upload",
        entity_id=upload_id,
        detail={"job_id": job_id, "run_dir": str(final_dir), "events": n_events},
    )
    return {
        "upload_id": upload_id,
        "device_id": device_id,
        "run_dir": str(final_dir.resolve()),
        "events": n_events,
        "bytes": len(raw),
        "checksum": checksum,
        "job_id": job_id,
        "deduped": deduped,
        "status": "queued",
        "record": row,
    }


@router.get("/uploads/{upload_id}")
def get_upload(
    upload_id: str,
    device: dict[str, Any] = Depends(require_edge_device),
) -> dict[str, Any]:
    row = get_store().get_edge_upload(upload_id)
    if not row:
        raise HTTPException(status_code=404, detail="upload not found")
    if row.get("device_id") != device.get("id"):
        raise HTTPException(status_code=403, detail="upload belongs to another device")
    if row.get("job_id"):
        job = get_store().get_job(int(row["job_id"]))
        row = {**row, "job": job}
        if job and job.get("status") in {"succeeded", "failed"} and row.get("status") == "queued":
            updated = get_store().update_edge_upload(
                upload_id,
                status=str(job["status"]),
                error=job.get("error"),
            )
            if updated:
                row = {**updated, "job": job}
    return row


class HeartbeatBody(BaseModel):
    props: Optional[dict[str, Any]] = None


@router.post("/heartbeat")
def heartbeat(
    body: HeartbeatBody = HeartbeatBody(),
    device: dict[str, Any] = Depends(require_edge_device),
) -> dict[str, Any]:
    """Memphis thin-uploader liveness; updates last_seen (+ optional health props)."""
    store = get_store()
    props = body.props or None
    store.touch_edge_device(str(device["id"]), props=props)
    refreshed = store.get_edge_device(str(device["id"])) or device
    return {
        "ok": True,
        "device_id": refreshed.get("id"),
        "last_seen_at": refreshed.get("last_seen_at"),
        "props": refreshed.get("props") or {},
    }


@router.post("/video")
async def upload_video(
    file: UploadFile = File(..., description="Survey video segment (mp4)"),
    gps: Optional[UploadFile] = File(None, description="GPS sidecar jsonl/csv"),
    vehicle_id: Optional[str] = Form(None),
    city_id: Optional[str] = Form(None),
    route_id: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    camera_id: Optional[str] = Form(None),
    device: dict[str, Any] = Depends(require_edge_device),
) -> dict[str, Any]:
    """Memphis path: accept video (+ optional GPS), store, enqueue central analyze_video."""
    from cityvision.storage import get_object_store

    settings = get_settings()
    store = get_store()
    max_bytes = int(settings.edge_max_upload_mb) * 1024 * 1024

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty video upload")
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"upload exceeds {settings.edge_max_upload_mb} MB limit",
        )

    filename = (file.filename or "video.mp4").lower()
    if not filename.endswith((".mp4", ".mov", ".mkv", ".avi")):
        raise HTTPException(status_code=422, detail="video must be mp4/mov/mkv/avi")

    device_id = str(device["id"])
    checksum = hashlib.sha256(raw).hexdigest()
    existing = store.find_video_by_checksum(device_id, checksum)
    if existing:
        return {
            "upload_id": existing["upload_id"],
            "device_id": device_id,
            "checksum": checksum,
            "job_id": existing.get("job_id"),
            "status": existing.get("status"),
            "deduped": True,
            "record": existing,
        }

    upload_id = uuid.uuid4().hex
    cid = city_id or device.get("city_id") or settings.default_city
    vid = vehicle_id or device.get("vehicle_id")
    cam = camera_id or "FRONT"
    name = run_name or f"{device_id}-{upload_id[:8]}"

    obj = get_object_store()
    video_key = f"edge-video/{device_id}/{upload_id}/video.mp4"
    obj.put_bytes(video_key, raw)

    gps_key = None
    gps_bytes = 0
    if gps is not None:
        gps_raw = await gps.read()
        if gps_raw:
            gps_name = (gps.filename or "gps.jsonl").lower()
            suffix = ".jsonl"
            if gps_name.endswith(".csv"):
                suffix = ".csv"
            elif gps_name.endswith(".json"):
                suffix = ".json"
            gps_key = f"edge-video/{device_id}/{upload_id}/gps{suffix}"
            obj.put_bytes(gps_key, gps_raw)
            gps_bytes = len(gps_raw)

    row = store.create_edge_video_upload(
        upload_id,
        device_id,
        video_key,
        checksum,
        city_id=str(cid) if cid else None,
        vehicle_id=str(vid) if vid else None,
        route_id=str(route_id) if route_id else None,
        gps_object_key=gps_key,
        nbytes=len(raw),
        payload={
            "filename": file.filename,
            "run_name": name,
            "camera_id": cam,
            "gps_bytes": gps_bytes,
        },
    )
    job_id, deduped = enqueue_job(
        store,
        "analyze_video",
        {
            "upload_id": upload_id,
            "object_key": video_key,
            "gps_object_key": gps_key,
            "city_id": cid,
            "vehicle_id": vid,
            "route_id": route_id,
            "camera_id": cam,
            "run_name": name,
        },
    )
    store.update_edge_video_upload(upload_id, status="queued", job_id=job_id)
    store.add_audit(
        actor=device_id,
        action="edge_video_upload",
        entity_type="edge_video_upload",
        entity_id=upload_id,
        detail={"job_id": job_id, "bytes": len(raw), "gps": bool(gps_key)},
    )
    return {
        "upload_id": upload_id,
        "device_id": device_id,
        "object_key": video_key,
        "gps_object_key": gps_key,
        "bytes": len(raw),
        "checksum": checksum,
        "job_id": job_id,
        "deduped": deduped,
        "status": "queued",
        "record": row,
    }


@router.get("/video/{upload_id}")
def get_video_upload(
    upload_id: str,
    device: dict[str, Any] = Depends(require_edge_device),
) -> dict[str, Any]:
    row = get_store().get_edge_video_upload(upload_id)
    if not row:
        raise HTTPException(status_code=404, detail="video upload not found")
    if row.get("device_id") != device.get("id"):
        raise HTTPException(status_code=403, detail="upload belongs to another device")
    if row.get("job_id"):
        job = get_store().get_job(int(row["job_id"]))
        row = {**row, "job": job}
        if (
            job
            and job.get("status") in {"succeeded", "failed"}
            and row.get("status") in {"queued", "analyzing", "received"}
        ):
            updated = get_store().update_edge_video_upload(
                upload_id,
                status=str(job["status"]),
                error=job.get("error"),
            )
            if updated:
                row = {**updated, "job": job}
    return row
