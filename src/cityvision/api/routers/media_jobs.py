from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from cityvision.api.deps import (
    Principal,
    check_media_access,
    get_principal,
    get_store,
    optional_city_id,
    require_admin,
    require_city_row,
    require_operator,
    resolve_city_id,
)
from cityvision.api.media_tokens import (
    media_resource,
    media_url,
    storage_resource,
    storage_url,
)
from cityvision.api.schemas import IngestBody, WorkOrderUpdate, ZonesIngestBody
from cityvision.config import ROOT
from cityvision.settings import get_settings
from cityvision.storage import get_object_store
from cityvision.storage.local import LocalObjectStore
from cityvision.workers.jobs import enqueue_job

router = APIRouter(prefix="/api", tags=["media-jobs"])


def _payload_with_city(
    principal: Principal, extra: dict[str, Any], city_id: Optional[str] = None
) -> dict[str, Any]:
    payload = dict(extra)
    if get_settings().strict_tenancy:
        cid = resolve_city_id(principal, city_id)
        payload["city_id"] = cid or get_settings().default_city
    elif city_id:
        payload["city_id"] = city_id
    return payload


@router.get("/events/{event_id}/media")
def event_media_list(
    event_id: str, principal: Principal = Depends(get_principal)
) -> list[dict[str, Any]]:
    store = get_store()
    event = require_city_row(store.get_event(event_id), principal, detail="event not found")
    return attach_media_urls(store.list_event_media(event_id), city_id=event.get("city_id"))


def attach_media_urls(
    rows: list[dict[str, Any]], city_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """Add a (signed, when auth is on) playable URL to each media row."""
    for r in rows:
        cid = r.get("city_id") or city_id
        if r.get("object_key"):
            r["url"] = storage_url(str(r["object_key"]), city_id=cid)
        elif r.get("id"):
            r["url"] = media_url(int(r["id"]), city_id=cid)
    return rows


def _stream_object(key: str, content_type: Optional[str] = None) -> StreamingResponse:
    store = get_object_store()
    try:
        body = store.open_read(key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="object not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid key") from exc

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                data = body.read(64 * 1024)
                if not data:
                    break
                yield data
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

    return StreamingResponse(chunks(), media_type=content_type or "application/octet-stream")


@router.get("/media/{media_id}")
def serve_media(
    media_id: int,
    principal: Principal = Depends(get_principal),
    exp: Optional[str] = Query(None),
    sig: Optional[str] = Query(None),
    cid: Optional[str] = Query(None),
):
    check_media_access(
        media_resource(media_id),
        principal=principal,
        exp=exp,
        sig=sig,
        city_id=cid,
    )
    row = require_city_row(
        get_store().get_event_media(media_id),
        principal,
        detail="media not found",
        signed_city_id=cid,
    )
    if row.get("object_key"):
        try:
            return _stream_object(row["object_key"], row.get("content_type"))
        except HTTPException:
            pass
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file missing on disk")
    return FileResponse(path, media_type=row.get("content_type") or None)


@router.get("/storage/{key:path}")
def serve_storage(
    key: str,
    principal: Principal = Depends(get_principal),
    exp: Optional[str] = Query(None),
    sig: Optional[str] = Query(None),
    cid: Optional[str] = Query(None),
):
    check_media_access(
        storage_resource(key),
        principal=principal,
        exp=exp,
        sig=sig,
        city_id=cid,
    )
    if get_settings().strict_tenancy and not principal.is_cross_city:
        require_city_row(
            get_store().lookup_storage_key(key),
            principal,
            detail="object not found",
            signed_city_id=cid,
        )
    obj = get_object_store()
    if isinstance(obj, LocalObjectStore):
        try:
            path = obj.resolve(key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="object not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid key") from exc
        return FileResponse(path)
    return _stream_object(key)


@router.post("/jobs/ingest")
def job_ingest(
    body: IngestBody,
    principal: Principal = Depends(require_admin),
    city_id: Optional[str] = None,
) -> dict[str, Any]:
    path = Path(body.run_dir)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not (path / "events.json").exists():
        raise HTTPException(status_code=404, detail=f"missing events.json under {path}")
    try:
        job_id, deduped = enqueue_job(
            get_store(),
            "ingest_run",
            _payload_with_city(principal, {"run_dir": str(path)}, city_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id, "status": "queued", "deduped": deduped}


@router.post("/jobs/ingest-zones")
def job_ingest_zones(
    body: ZonesIngestBody,
    principal: Principal = Depends(require_admin),
    city_id: Optional[str] = None,
) -> dict[str, Any]:
    path = Path(body.path)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"missing {path}")
    try:
        job_id, deduped = enqueue_job(
            get_store(),
            "ingest_zones",
            _payload_with_city(principal, {"path": str(path)}, city_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id, "status": "queued", "deduped": deduped}


@router.get("/jobs")
def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return get_store().list_jobs(
        limit=limit, city_id=optional_city_id(principal, city_id)
    )


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int, principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    row = require_city_row(get_store().get_job(job_id), principal, detail="job not found")
    return row


@router.patch("/work-orders/{work_order_id}")
def patch_work_order(
    work_order_id: int,
    body: WorkOrderUpdate,
    principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    require_city_row(
        get_store().get_work_order(work_order_id),
        principal,
        detail="work order not found",
    )
    try:
        row = get_store().update_work_order(
            work_order_id,
            status=body.status,
            note=body.note,
            assignee=body.assignee,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="work order not found")
    return row
