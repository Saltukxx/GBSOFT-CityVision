from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from cityvision.api.auth import ApiKeyMiddleware, TenantMiddleware
from cityvision.api.deps import bind_tenant
from cityvision.api.routers import (
    admin,
    auth_export,
    edge,
    events,
    fleet,
    flights,
    health,
    ingest,
    learning,
    media_jobs,
    route_planning,
    zones,
)
from cityvision.config import ROOT

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="GBSoft City Vision API",
    version="0.9.0",
    description="Municipal event backend (PostGIS, city packs, RBAC, edge upload, transactional ingest)",
    dependencies=[Depends(bind_tenant)],
)

# Last added runs first. ApiKeyMiddleware is outer; TenantMiddleware sees
# requests that already passed the API-key / JWT gate.
app.add_middleware(TenantMiddleware)
app.add_middleware(ApiKeyMiddleware)

app.include_router(health.router)
app.include_router(auth_export.router)  # before events so /events/export.csv wins
app.include_router(events.router)
app.include_router(fleet.router)
app.include_router(zones.router)
app.include_router(ingest.router)
app.include_router(media_jobs.router)
app.include_router(edge.router)
app.include_router(flights.router)
app.include_router(admin.router)
app.include_router(learning.router)
app.include_router(route_planning.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Operator web app (React build from web/, `npm run build`). Served under /app;
# unknown sub-paths fall back to index.html so client-side routes deep-link.
WEBAPP_DIR = ROOT / "web" / "dist"
if (WEBAPP_DIR / "assets").exists():
    app.mount("/app/assets", StaticFiles(directory=str(WEBAPP_DIR / "assets")), name="webapp-assets")


@app.get("/app", include_in_schema=False)
@app.get("/app/{path:path}", include_in_schema=False)
def webapp(path: str = "") -> FileResponse:
    candidate = (WEBAPP_DIR / path).resolve()
    if path and candidate.is_file() and WEBAPP_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = WEBAPP_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="web app not built (cd web && npm run build)")
    return FileResponse(index)


@app.get("/")
def dashboard() -> RedirectResponse:
    return RedirectResponse(url="/map", status_code=307)


def _static_html(name: str) -> HTMLResponse:
    path = STATIC_DIR / name
    if not path.exists():
        return HTMLResponse("<h1>Missing page</h1>", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/landing", response_class=HTMLResponse)
def page_landing() -> HTMLResponse:
    return _static_html("landing.html")


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
