from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from cityvision.api.deps import get_store, require_admin, require_operator
from cityvision.api.schemas import IngestBody, WorkOrderUpdate, ZonesIngestBody
from cityvision.config import ROOT
from cityvision.storage import get_object_store
from cityvision.storage.local import LocalObjectStore
from cityvision.workers.jobs import enqueue_job

router = APIRouter(prefix="/api", tags=["media-jobs"])


@router.get("/events/{event_id}/media")
def event_media_list(event_id: str) -> list[dict[str, Any]]:
    store = get_store()
    if not store.get_event(event_id):
        raise HTTPException(status_code=404, detail="event not found")
    rows = store.list_event_media(event_id)
    for r in rows:
        if r.get("object_key"):
            r["url"] = f"/api/storage/{r['object_key']}"
        elif r.get("id"):
            r["url"] = f"/api/media/{r['id']}"
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
def serve_media(media_id: int):
    row = get_store().get_event_media(media_id)
    if not row:
        raise HTTPException(status_code=404, detail="media not found")
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
def serve_storage(key: str):
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
def job_ingest(body: IngestBody, _principal=Depends(require_admin)) -> dict[str, Any]:
    path = Path(body.run_dir)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not (path / "events.json").exists():
        raise HTTPException(status_code=404, detail=f"missing events.json under {path}")
    job_id, deduped = enqueue_job(get_store(), "ingest_run", {"run_dir": str(path)})
    return {"job_id": job_id, "status": "queued", "deduped": deduped}


@router.post("/jobs/ingest-zones")
def job_ingest_zones(
    body: ZonesIngestBody, _principal=Depends(require_admin)
) -> dict[str, Any]:
    path = Path(body.path)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"missing {path}")
    job_id, deduped = enqueue_job(get_store(), "ingest_zones", {"path": str(path)})
    return {"job_id": job_id, "status": "queued", "deduped": deduped}


@router.get("/jobs")
def list_jobs(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    return get_store().list_jobs(limit=limit)


@router.get("/jobs/{job_id}")
def get_job(job_id: int) -> dict[str, Any]:
    row = get_store().get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    return row


@router.patch("/work-orders/{work_order_id}")
def patch_work_order(
    work_order_id: int,
    body: WorkOrderUpdate,
    _principal=Depends(require_operator),
) -> dict[str, Any]:
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
