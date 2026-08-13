from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from cityvision.api.deps import get_store, require_admin
from cityvision.api.schemas import IngestBody
from cityvision.config import ROOT
from cityvision.db.ingest import ingest_run_dir

router = APIRouter(prefix="/api", tags=["ingest"])


@router.get("/runs")
def list_runs(limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    return get_store().list_runs(limit=limit)


@router.get("/runs/{run_id}/detections")
def run_detections(run_id: int) -> list[dict[str, Any]]:
    return get_store().list_detection_stats(run_id)


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
