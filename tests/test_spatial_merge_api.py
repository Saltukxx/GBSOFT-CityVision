"""Cross-run spatial merge + API smoke (requires PostGIS)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cityvision.config import ROOT
from cityvision.db.ingest import ingest_run_dir
from cityvision.db.store import Store
from cityvision.pipeline.model_resolve import resolve_model_b_paths
from cityvision.settings import get_settings


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        return Store().ping()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


@pytest.fixture()
def store() -> Store:
    get_settings.cache_clear()
    return Store()


def test_dual_model_b_weights_resolve():
    cfg = {
        "model_b_list": ["models/infra-b-road.pt", "models/infra-b-waste.pt"],
        "auto_discover_model_b": True,
        "model_b_fallbacks": [],
    }
    paths = resolve_model_b_paths(cfg)
    names = {p.name for p in paths}
    assert "infra-b-road.pt" in names
    assert "infra-b-waste.pt" in names


def test_spatial_merge_across_runs(store: Store, tmp_path: Path):
    import uuid

    suffix = uuid.uuid4().hex[:8]
    # Isolate by city so leftover demo/other-test events cannot fuse in.
    city_id = f"merge-city-{suffix}"
    store.upsert_city(city_id, f"Merge City {suffix}")
    # Unique coords so we don't collide with leftover demo data
    lat, lon = 39.90111 + (int(suffix[:2], 16) * 1e-5), 41.30111 + (int(suffix[2:4], 16) * 1e-5)
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    run_a.mkdir()
    run_b.mkdir()
    id_a = f"POT-MERGE-A-{suffix}"
    id_b = f"POT-MERGE-B-{suffix}"

    (run_a / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": id_a,
                    "type": "pothole",
                    "lat": lat,
                    "lon": lon,
                    "confidence": 0.82,
                    "confidence_band": "manual_review",
                    "observations": 1,
                    "severity": "medium",
                    "status": "under_review",
                    "vehicle_ids": ["DJI-A"],
                    "vehicle_id": "DJI-A",
                    "city_id": city_id,
                    "first_seen_ms": 1000,
                    "last_seen_ms": 1500,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_a / "summary.json").write_text(
        json.dumps({"vehicle_id": "DJI-A", "camera_id": "AERIAL", "city_id": city_id}),
        encoding="utf-8",
    )

    (run_b / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": id_b,
                    "type": "pothole",
                    "lat": lat + 0.00002,
                    "lon": lon + 0.00002,
                    "confidence": 0.88,
                    "confidence_band": "probable",
                    "observations": 1,
                    "severity": "medium",
                    "status": "under_review",
                    "vehicle_ids": ["DJI-B"],
                    "vehicle_id": "DJI-B",
                    "city_id": city_id,
                    "first_seen_ms": 2000,
                    "last_seen_ms": 2500,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_b / "summary.json").write_text(
        json.dumps({"vehicle_id": "DJI-B", "camera_id": "AERIAL", "city_id": city_id}),
        encoding="utf-8",
    )

    r1 = ingest_run_dir(run_a, store=store)
    assert r1["events_created"] == 1
    assert r1["events_merged"] == 0

    r2 = ingest_run_dir(run_b, store=store)
    assert r2["events_merged"] == 1
    assert r2["events_created"] == 0
    assert r2["merges"][0]["into"] == id_a

    merged = store.get_event(id_a)
    assert merged is not None
    assert int(merged["observations"]) >= 2
    assert store.get_event(id_b) is None
    payload = merged.get("payload") or {}
    assert id_b in (payload.get("merged_from") or [])
    vids = payload.get("vehicle_ids") or []
    assert "DJI-A" in vids and "DJI-B" in vids


def test_api_smoke_health_review_export(store: Store):
    from fastapi.testclient import TestClient

    from cityvision.api.app import app

    # Ensure at least one event exists
    if not store.list_events(limit=1):
        run = ROOT / "outputs" / "simulate_001"
        if (run / "events.json").exists():
            ingest_run_dir(run, store=store)
        else:
            pytest.skip("no events to exercise API")

    events = store.list_events(limit=1)
    assert events
    eid = events[0]["event_id"]

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/kpis").status_code == 200
    assert client.get("/map").status_code == 200
    assert client.get("/live").status_code == 200
    assert client.get("/detect").status_code == 200
    assert client.get(f"/events/{eid}").status_code == 200

    rev = client.post(
        f"/api/events/{eid}/review",
        json={"label": "confirmed", "note": "smoke", "reviewer": "pytest"},
    )
    assert rev.status_code == 200, rev.text

    export = client.get("/api/events/export.csv")
    assert export.status_code == 200
    assert "event_id" in export.text.splitlines()[0]
