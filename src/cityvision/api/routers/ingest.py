from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from cityvision.api.deps import (
    Principal,
    check_media_access,
    get_principal,
    get_store,
    optional_city_id,
    require_admin,
    require_city_row,
    resolve_city_id,
)
from cityvision.api.media_tokens import run_video_resource
from cityvision.api.schemas import IngestBody
from cityvision.config import ROOT
from cityvision.db.ingest import ingest_run_dir
from cityvision.settings import get_settings

router = APIRouter(prefix="/api", tags=["ingest"])


@router.get("/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=500),
    city_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    from cityvision.api.media_tokens import run_video_url

    rows = get_store().list_runs(limit=limit, city_id=optional_city_id(principal, city_id))
    for row in rows:
        if row.get("id") is not None:
            row["annotated_url"] = run_video_url(
                int(row["id"]), city_id=row.get("city_id")
            )
    return rows


@router.get("/runs/{run_id}/detections")
def run_detections(
    run_id: int, principal: Principal = Depends(get_principal)
) -> list[dict[str, Any]]:
    require_city_row(get_store().get_run(run_id), principal, detail="run not found")
    return get_store().list_detection_stats(run_id)


@router.get("/runs/{run_id}/track")
def run_track(
    run_id: int, principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    row = require_city_row(get_store().get_run(run_id), principal, detail="run not found")
    summary = row.get("summary") or {}
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except json.JSONDecodeError:
            summary = {}
    coords = summary.get("track") if isinstance(summary, dict) else None
    if not isinstance(coords, list):
        coords = []
    return {
        "type": "Feature",
        "properties": {
            "run_id": row["id"],
            "vehicle_id": row.get("vehicle_id"),
            "camera_id": row.get("camera_id"),
            "model_a": row.get("model_a"),
            "model_b": row.get("model_b"),
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }


@router.get("/runs/{run_id}/annotated")
def run_annotated(
    run_id: int,
    principal: Principal = Depends(get_principal),
    exp: Optional[str] = Query(None),
    sig: Optional[str] = Query(None),
    cid: Optional[str] = Query(None),
) -> FileResponse:
    check_media_access(
        run_video_resource(run_id),
        principal=principal,
        exp=exp,
        sig=sig,
        city_id=cid,
    )
    row = require_city_row(
        get_store().get_run(run_id),
        principal,
        detail="run not found",
        signed_city_id=cid,
    )
    run_dir = Path(str(row.get("run_dir") or ""))
    path = run_dir / "annotated.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="annotated video not found")
    return FileResponse(path, media_type="video/mp4", filename="annotated.mp4")


@router.post("/ingest")
def ingest(
    body: IngestBody,
    principal: Principal = Depends(require_admin),
    city_id: Optional[str] = None,
) -> dict[str, Any]:
    path = Path(body.run_dir)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    overlay: Optional[str] = None
    if get_settings().strict_tenancy:
        overlay = resolve_city_id(principal, city_id)
    elif city_id:
        overlay = city_id
    try:
        return ingest_run_dir(path, store=get_store(), city_id=overlay)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
