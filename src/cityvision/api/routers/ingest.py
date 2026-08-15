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
    require_admin,
)
from cityvision.api.media_tokens import run_video_resource
from cityvision.api.schemas import IngestBody
from cityvision.config import ROOT
from cityvision.db.ingest import ingest_run_dir

router = APIRouter(prefix="/api", tags=["ingest"])


@router.get("/runs")
def list_runs(limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    from cityvision.api.media_tokens import run_video_url

    rows = get_store().list_runs(limit=limit)
    for row in rows:
        if row.get("id") is not None:
            row["annotated_url"] = run_video_url(int(row["id"]))
    return rows


@router.get("/runs/{run_id}/detections")
def run_detections(run_id: int) -> list[dict[str, Any]]:
    return get_store().list_detection_stats(run_id)


@router.get("/runs/{run_id}/track")
def run_track(run_id: int) -> dict[str, Any]:
    row = get_store().get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
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
) -> FileResponse:
    check_media_access(
        run_video_resource(run_id), principal=principal, exp=exp, sig=sig
    )
    row = get_store().get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    run_dir = Path(str(row.get("run_dir") or ""))
    path = run_dir / "annotated.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="annotated video not found")
    return FileResponse(path, media_type="video/mp4", filename="annotated.mp4")


@router.post("/ingest")
def ingest(body: IngestBody, _principal=Depends(require_admin)) -> dict[str, Any]:
    path = Path(body.run_dir)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    try:
        return ingest_run_dir(path, store=get_store())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
