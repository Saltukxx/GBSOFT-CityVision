from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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


@app.get("/")
def dashboard() -> RedirectResponse:
    return RedirectResponse(url="/map", status_code=307)


def _static_html(name: str) -> HTMLResponse:
    path = STATIC_DIR / name
    if not path.exists():
        return HTMLResponse("<h1>Missing page</h1>", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/map", response_class=HTMLResponse)
def page_map() -> HTMLResponse:
    return _static_html("map.html")


@app.get("/live", response_class=HTMLResponse)
def page_live() -> HTMLResponse:
    return _static_html("live.html")


@app.get("/detect", response_class=HTMLResponse)
def page_detect() -> HTMLResponse:
    return _static_html("detect.html")


@app.get("/events/{event_id}", response_class=HTMLResponse)
def page_event(event_id: str) -> HTMLResponse:
    return _static_html("event.html")


@app.get("/report/{run_name}")
def report(run_name: str) -> FileResponse:
    path = ROOT / "outputs" / run_name / "report.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(path)
