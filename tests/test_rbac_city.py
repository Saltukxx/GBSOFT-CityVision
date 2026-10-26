"""RBAC + city_id backend tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cityvision.api.security import create_access_token, hash_password
from cityvision.db.ingest import ingest_run_dir
from cityvision.db.store import Store
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


def test_city_id_on_ingest_and_filter(store: Store, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CITYVISION_DEFAULT_CITY", "erzurum")
    get_settings.cache_clear()
    store.upsert_city("erzurum", "Erzurum")
    store.upsert_city("ankara", "Ankara")

    run = tmp_path / "city_run"
    run.mkdir()
    eid = "POT-CITY-ERZ"
    (run / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": eid,
                    "type": "pothole",
                    "lat": 39.92001,
                    "lon": 41.28001,
                    "confidence": 0.9,
                    "status": "under_review",
                    "observations": 1,
                    "vehicle_id": "DJI-C",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"city_id": "erzurum", "vehicle_id": "DJI-C"}),
        encoding="utf-8",
    )
    ingest_run_dir(run, store=store)
    row = store.get_event(eid)
    assert row is not None
    assert row.get("city_id") == "erzurum"
    erz = store.list_events(city_id="erzurum", limit=500)
    assert any(e["event_id"] == eid for e in erz)
    ank = store.list_events(city_id="ankara", limit=500)
    assert not any(e["event_id"] == eid for e in ank)


def test_rbac_viewer_cannot_patch_status(store: Store, monkeypatch):
    monkeypatch.setenv("CITYVISION_RBAC", "1")
    monkeypatch.setenv("CITYVISION_JWT_SECRET", "test-secret-rbac")
    get_settings.cache_clear()

    events = store.list_events(limit=1)
    if not events:
        pytest.skip("no events")
    eid = events[0]["event_id"]

    store.upsert_user(
        "viewer1",
        display_name="Viewer",
        role="viewer",
        password_hash=hash_password("viewerpass"),
    )
    store.upsert_user(
        "op1",
        display_name="Op",
        role="operator",
        password_hash=hash_password("oppass"),
    )

    from cityvision.api.app import app

    client = TestClient(app)
    viewer_tok = create_access_token("viewer1", "viewer", expires_minutes=30)
    op_tok = create_access_token("op1", "operator", expires_minutes=30)

    denied = client.patch(
        f"/api/events/{eid}/status",
        json={"status": "confirmed"},
        headers={"Authorization": f"Bearer {viewer_tok}"},
    )
    assert denied.status_code == 403

    allowed = client.patch(
        f"/api/events/{eid}/status",
        json={"status": "under_review"},
        headers={"Authorization": f"Bearer {op_tok}"},
    )
    assert allowed.status_code == 200

    anon = client.patch(
        f"/api/events/{eid}/status",
        json={"status": "confirmed"},
    )
    assert anon.status_code == 401
