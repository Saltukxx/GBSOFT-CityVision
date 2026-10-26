"""Demo screens: GPS track ingest, annotated video, HTML routes."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from cityvision.api.app import app
from cityvision.db.ingest import _downsample_track, ingest_run_dir
from cityvision.db.store import Store
from cityvision.settings import get_settings


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        return Store().ping()
    except Exception:
        return False


def test_downsample_track_keeps_ends():
    pts = [[float(i), float(i)] for i in range(500)]
    out = _downsample_track(pts, max_points=20)
    assert len(out) <= 21
    assert out[0] == pts[0]
    assert out[-1] == pts[-1]


def _tiny_mp4(path: Path, n: int = 6) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 64))
    for i in range(n):
        writer.write(np.full((64, 64, 3), i * 10, dtype=np.uint8))
    writer.release()


def test_html_demo_routes():
    client = TestClient(app)
    assert client.get("/map").status_code == 200
    assert client.get("/live").status_code == 200
    assert client.get("/detect").status_code == 200
    page = client.get("/events/POT-DEMO-x")
    assert page.status_code == 200
    assert "Olay" in page.text
    loc = client.get("/", follow_redirects=False)
    assert loc.status_code == 307
    assert loc.headers["location"].endswith("/map")


@pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")
def test_run_track_and_annotated(tmp_path: Path):
    get_settings.cache_clear()
    store = Store()
    suffix = uuid.uuid4().hex[:8]
    city_id = f"demo-city-{suffix}"
    store.upsert_city(city_id, f"Demo {suffix}")
    run = tmp_path / "run"
    run.mkdir()
    lat0, lon0 = 39.91, 41.27
    lines = []
    for i in range(12):
        lines.append(
            json.dumps(
                {
                    "type": "detection",
                    "class": "car",
                    "confidence": 0.9,
                    "lat": lat0 + i * 0.0002,
                    "lon": lon0 + i * 0.0002,
                    "frame": i,
                }
            )
        )
    (run / "detections.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    eid = f"POT-DEMO-{suffix}"
    (run / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": eid,
                    "type": "pothole",
                    "lat": lat0,
                    "lon": lon0,
                    "confidence": 0.9,
                    "confidence_band": "probable",
                    "observations": 1,
                    "severity": "medium",
                    "status": "under_review",
                    "vehicle_ids": ["DJI-DEMO"],
                    "vehicle_id": "DJI-DEMO",
                    "city_id": city_id,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"vehicle_id": "DJI-DEMO", "camera_id": "AERIAL", "city_id": city_id}),
        encoding="utf-8",
    )
    _tiny_mp4(run / "annotated.mp4")

    result = ingest_run_dir(run, store=store)
    run_id = int(result["run_id"])
    row = store.get_run(run_id)
    assert row is not None
    track = (row.get("summary") or {}).get("track")
    assert isinstance(track, list)
    assert len(track) > 1

    client = TestClient(app)
    geo = client.get(f"/api/runs/{run_id}/track")
    assert geo.status_code == 200, geo.text
    body = geo.json()
    assert body["geometry"]["type"] == "LineString"
    assert len(body["geometry"]["coordinates"]) > 1
    assert body["properties"]["vehicle_id"] == "DJI-DEMO"

    video = client.get(f"/api/runs/{run_id}/annotated")
    assert video.status_code == 200
    assert video.headers["content-type"].startswith("video/")

    (run / "annotated.mp4").unlink()
    gone = client.get(f"/api/runs/{run_id}/annotated")
    assert gone.status_code == 404

    missing = client.get("/api/runs/99999999/annotated")
    assert missing.status_code == 404
