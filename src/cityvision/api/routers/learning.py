"""Phase 4: labelling queue + training export (GBSoft), model performance, weekly report."""

from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from cityvision.api.deps import (
    Principal,
    get_principal,
    get_store,
    optional_city_id,
    require_admin,
    require_city_row,
    require_roles,
    resolve_city_id,
)
from cityvision.labelling import TRAINING_CLASSES, build_export, validate_boxes
from cityvision.settings import get_settings

router = APIRouter(prefix="/api", tags=["learning"])

# Labelling is GBSoft's job, not the municipality's.
require_superadmin = require_roles("superadmin")


def _media_with_urls(event_id: str, city_id: Optional[str]) -> list[dict[str, Any]]:
    from cityvision.api.routers.media_jobs import attach_media_urls

    return attach_media_urls(get_store().list_event_media(event_id), city_id=city_id)


def _sample_bbox(media: list[dict[str, Any]], frame: Optional[dict[str, Any]]) -> Optional[list[float]]:
    """The detector's box (frame pixels, x1 y1 x2 y2) from the same run as the frame."""
    from cityvision.labelling import _open_media, evidence_folder

    jsons = [m for m in media if m.get("media_type") == "json"]
    if frame is not None:
        same = [m for m in jsons if evidence_folder(m) == evidence_folder(frame)]
        jsons = same  # a box from another run would not line up with this frame
    for m in reversed(jsons):
        fh = _open_media(m)
        if fh is None:
            continue
        try:
            with fh:
                data = json.loads(fh.read(512 * 1024))
        except (ValueError, OSError):
            continue
        bbox = data.get("sample_bbox")
        if isinstance(bbox, list) and len(bbox) >= 4:
            return [float(v) for v in bbox[:4]]
    return None


# ---------- labelling ----------


@router.get("/labelling/classes")
def labelling_classes(principal: Principal = Depends(require_superadmin)) -> list[str]:
    return TRAINING_CLASSES


@router.get("/labelling/queue")
def labelling_queue(
    done: bool = False,
    city_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    principal: Principal = Depends(require_superadmin),
) -> dict[str, Any]:
    from cityvision.api.routers.media_jobs import attach_media_urls

    store = get_store()
    cid = optional_city_id(principal, city_id)
    items = store.labelling_queue(city_id=cid, done=done, limit=limit)
    firsts = store.first_images_for_events([i["event_id"] for i in items])
    attach_media_urls(list(firsts.values()))
    for i in items:
        m = firsts.get(i["event_id"])
        i["thumb_url"] = m.get("url") if m else None
    return {"items": items, "counts": store.labelling_counts(city_id=cid)}


@router.get("/labelling/items/{event_id}")
def labelling_item(event_id: str, principal: Principal = Depends(require_superadmin)) -> dict[str, Any]:
    store = get_store()
    item = require_city_row(store.labelling_item(event_id), principal, detail="item not found")
    media = _media_with_urls(event_id, item.get("city_id"))
    frame = next((m for m in media if m.get("media_type") == "frame"), None)
    annotated = next((m for m in media if m.get("media_type") == "image"), None)
    item["frame"] = {"id": frame["id"], "url": frame.get("url")} if frame else None
    item["annotated_url"] = annotated.get("url") if annotated else None
    item["sample_bbox"] = _sample_bbox(media, frame)
    return item


class LabelBody(BaseModel):
    kind: Literal["positive", "negative", "skip"]
    boxes: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


@router.put("/labelling/items/{event_id}")
def save_label(
    event_id: str, body: LabelBody, principal: Principal = Depends(require_superadmin)
) -> dict[str, Any]:
    store = get_store()
    item = require_city_row(store.labelling_item(event_id), principal, detail="item not found")
    try:
        boxes = validate_boxes(body.boxes) if body.kind == "positive" else []
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.kind == "positive" and not boxes:
        raise HTTPException(status_code=422, detail="positive_needs_boxes")
    media = store.list_event_media(event_id)
    frame = next((m for m in media if m.get("media_type") == "frame"), None)
    if body.kind != "skip" and frame is None:
        # Never train on the annotated evidence image (it has our box drawn on it).
        raise HTTPException(status_code=409, detail="no_clean_frame")
    return store.upsert_training_label(
        event_id,
        kind=body.kind,
        boxes=boxes,
        labeller=principal.username,
        media_id=int(frame["id"]) if frame else None,
        city_id=item.get("city_id"),
    )


@router.delete("/labelling/items/{event_id}", status_code=204)
def delete_label(event_id: str, principal: Principal = Depends(require_superadmin)) -> None:
    store = get_store()
    require_city_row(store.labelling_item(event_id), principal, detail="item not found")
    store.delete_training_label(event_id)


@router.get("/labelling/export.zip")
def export_training_set(
    city_id: Optional[str] = None, principal: Principal = Depends(require_superadmin)
) -> FileResponse:
    store = get_store()
    cid = optional_city_id(principal, city_id)
    rows = store.training_export_rows(city_id=cid)
    if not rows:
        raise HTTPException(status_code=404, detail="nothing_to_export")
    folder = get_settings().edge_upload_dir / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(dir=folder, suffix=".zip", delete=False)
    with tmp:
        manifest = build_export(rows, tmp, city_id=cid)
    store.add_audit(
        actor=principal.username,
        action="training_export",
        entity_type="dataset",
        detail={"images": manifest["images"], "skipped": len(manifest["skipped"])},
        city_id=cid,
    )
    name = f"cityvision-labels-{cid or 'all'}-{date.today().isoformat()}.zip"
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=name,
        background=BackgroundTask(Path(tmp.name).unlink, missing_ok=True),
    )


class HoldoutBody(BaseModel):
    holdout: bool


@router.patch("/flights/{upload_id}/holdout")
def set_holdout(
    upload_id: str, body: HoldoutBody, principal: Principal = Depends(require_superadmin)
) -> dict[str, Any]:
    store = get_store()
    row = require_city_row(store.get_flight(upload_id), principal, detail="flight not found")
    store.set_flight_holdout(upload_id, body.holdout)
    store.add_audit(
        actor=principal.username,
        action="flight_holdout",
        entity_type="flight",
        entity_id=upload_id,
        detail={"holdout": body.holdout},
        city_id=row.get("city_id"),
    )
    return {"id": upload_id, "holdout": body.holdout}


# ---------- model performance ----------


@router.get("/models/performance")
def model_performance(
    city_id: Optional[str] = None, principal: Principal = Depends(require_admin)
) -> list[dict[str, Any]]:
    return get_store().model_performance(city_id=resolve_city_id(principal, city_id))


# ---------- weekly report ----------


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


@router.get("/reports/weekly")
def weekly_report(
    start: Optional[date] = Query(None, description="Any day in the week; defaults to this week"),
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    store = get_store()
    cid = resolve_city_id(principal, city_id)
    week = _week_start(start or date.today())
    end = week + timedelta(days=7)
    report = store.weekly_report(cid, week, end)
    previous = store.weekly_report(cid, week - timedelta(days=7), week)
    city = store.get_city(cid) if cid else None
    report["previous"] = {
        k: previous[k]
        for k in ("new_candidates", "decisions", "confirmed", "false_alarms", "precision")
    }
    report["previous"]["flights"] = previous["flights"]["flights"]
    report["city"] = {"id": cid, "name": (city or {}).get("name") or cid}
    return report
