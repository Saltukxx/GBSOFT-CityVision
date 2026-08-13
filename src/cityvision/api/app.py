from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from cityvision.api.auth import ApiKeyMiddleware
from cityvision.api.routers import (
    auth_export,
    edge,
    events,
    fleet,
    health,
    ingest,
    media_jobs,
    zones,
)
from cityvision.config import ROOT

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="GBSoft City Vision API",
    version="0.9.0",
    description="Municipal event backend (PostGIS, city packs, RBAC, edge upload, transactional ingest)",
)

app.add_middleware(ApiKeyMiddleware)

app.include_router(health.router)
app.include_router(auth_export.router)  # before events so /events/export.csv wins
app.include_router(events.router)
app.include_router(fleet.router)
app.include_router(zones.router)
app.include_router(ingest.router)
app.include_router(media_jobs.router)
app.include_router(edge.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>City Vision</h1><p>Dashboard missing.</p>")
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.get("/report/{run_name}")
def report(run_name: str) -> FileResponse:
    path = ROOT / "outputs" / run_name / "report.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(path)
