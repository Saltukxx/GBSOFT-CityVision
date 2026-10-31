"""Backend support for the operator web app (web/): review reasons, the
"unsure" label, list thumbnails, public auth config and the /app route."""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cityvision.settings import get_settings


@contextmanager
def _client(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from cityvision.api.app import app

    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


class _FakeStore:
    """Just enough store for the review route without a database."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_event(self, event_id):
        return {"event_id": event_id, "city_id": None, "status": "under_review"}

    def add_review(self, **kwargs):
        self.calls.append(kwargs)
        return {"event_id": kwargs["event_id"], "label": kwargs["label"], "reason": kwargs.get("reason")}


@pytest.fixture()
def fake_store(monkeypatch):
    import cityvision.api.routers.events as events_router

    store = _FakeStore()
    monkeypatch.setattr(events_router, "get_store", lambda: store)
    return store


def _no_auth(monkeypatch):
    return _client(
        monkeypatch,
        CITYVISION_API_KEY="",
        CITYVISION_JWT_SECRET="",
        CITYVISION_STRICT_TENANCY="0",
    )


def test_auth_config_is_public_even_with_strict_tenancy(monkeypatch):
    with _client(
        monkeypatch,
        CITYVISION_API_KEY="secret123",
        CITYVISION_JWT_SECRET="jwt-secret",
        CITYVISION_STRICT_TENANCY="1",
    ) as client:
        r = client.get("/api/auth/config")
    assert r.status_code == 200
    assert r.json() == {"login_enabled": True, "auth_required": True}


def test_auth_config_reports_login_disabled_without_jwt(monkeypatch):
    with _no_auth(monkeypatch) as client:
        r = client.get("/api/auth/config")
    assert r.json() == {"login_enabled": False, "auth_required": False}


def test_review_passes_reason_through(monkeypatch, fake_store):
    with _no_auth(monkeypatch) as client:
        r = client.post("/api/events/EV-1/review", json={"label": "wrong", "reason": "manhole"})
    assert r.status_code == 200, r.text
    assert fake_store.calls[0]["reason"] == "manhole"
    assert fake_store.calls[0]["label"] == "wrong"


@pytest.mark.parametrize(
    "body",
    [
        {"label": "correct", "reason": "manhole"},  # reason only with a rejection
        {"label": "wrong", "reason": "aliens"},  # unknown reason
    ],
)
def test_review_rejects_bad_reason(monkeypatch, fake_store, body):
    with _no_auth(monkeypatch) as client:
        r = client.post("/api/events/EV-1/review", json=body)
    assert r.status_code == 400
    assert fake_store.calls == []


def test_webapp_serves_index_for_client_routes(monkeypatch, tmp_path: Path):
    import cityvision.api.app as app_module

    (tmp_path / "index.html").write_text("<!doctype html><title>CityVision</title>", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEBAPP_DIR", tmp_path)
    with _no_auth(monkeypatch) as client:
        deep = client.get("/app/review?e=EV-1")
        root = client.get("/app")
        asset = client.get("/app/favicon.svg")
        escape = client.get("/app/..%2F..%2Fpyproject.toml")
    assert deep.status_code == 200 and "CityVision" in deep.text
    assert root.status_code == 200 and "CityVision" in root.text
    assert asset.text == "<svg/>"
    # Path traversal falls back to index.html instead of leaking files.
    assert "CityVision" in escape.text


# ---------- DB-backed ----------


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        from cityvision.db.store import Store

        return Store().ping()
    except Exception:
        return False


db = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


@pytest.fixture()
def cleanup_events():
    """Remove events and runs a test ingests, so they don't pile up in the dev DB."""
    created: list[tuple[str, str]] = []
    yield created
    if not created:
        return
    from cityvision.db.store import Store

    store = Store()
    with store.connect() as conn:
        with conn.cursor() as cur:
            for event_id, run_dir in created:
                cur.execute("DELETE FROM events WHERE event_id = %s", (event_id,))
                cur.execute("DELETE FROM runs WHERE run_dir = %s", (run_dir,))
        store._commit(conn)


def _ingest_event(tmp_path: Path, event_id: str, created: list):
    from cityvision.db.ingest import ingest_run_dir
    from cityvision.db.store import Store

    run = tmp_path / event_id
    run.mkdir()
    # Spread test events so spatial merge never folds them together.
    seed = uuid.uuid4().int % 10_000
    (run / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": event_id,
                    "type": "pothole",
                    "lat": 38.0 + seed * 1e-4,
                    "lon": 30.0 + seed * 1e-4,
                    "confidence": 0.9,
                    "confidence_band": "probable",
                    "observations": 1,
                    "status": "under_review",
                    "first_seen_ms": 0,
                    "last_seen_ms": 10,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(json.dumps({"vehicle_id": "DRONE-T"}), encoding="utf-8")
    store = Store()
    created.append((event_id, str(run.resolve())))
    ingest_run_dir(run, store=store)
    return store


@db
def test_store_saves_reason_and_unsure(tmp_path: Path, cleanup_events):
    eid = f"WEB-{uuid.uuid4().hex[:8]}"
    store = _ingest_event(tmp_path, eid, cleanup_events)

    out = store.add_review(event_id=eid, label="wrong", reviewer="pytest", reason="shadow")
    assert out["status"] == "false_positive"
    assert out["reason"] == "shadow"

    unsure = store.add_review(event_id=eid, label="unsure", reviewer="pytest")
    assert unsure["status"] == "under_review"

    reviews = store.list_reviews(event_id=eid)
    assert {r["label"]: r["reason"] for r in reviews} == {"wrong": "shadow", "unsure": None}


@db
def test_first_images_prefers_crop(tmp_path: Path, cleanup_events):
    eid = f"WEB-{uuid.uuid4().hex[:8]}"
    store = _ingest_event(tmp_path, eid, cleanup_events)
    store.upsert_event_media(eid, "image", str(tmp_path / "frame.jpg"))
    store.upsert_event_media(eid, "crop", str(tmp_path / "crop.jpg"))

    firsts = store.first_images_for_events([eid, "missing"])
    assert set(firsts) == {eid}
    assert firsts[eid]["media_type"] == "crop"
