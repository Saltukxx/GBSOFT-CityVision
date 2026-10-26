"""Evidence media access end to end: real event, real object, real bytes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

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

PIXEL = b"\xff\xd8\xff\xe0 fake jpeg bytes \xff\xd9"


@pytest.fixture()
def event_with_media(tmp_path, monkeypatch):
    """Ingest one event and attach a stored object to it."""
    store_dir = tmp_path / "object_store"
    monkeypatch.setenv("CITYVISION_OBJECT_STORE", str(store_dir))
    get_settings.cache_clear()

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    event_id = f"POT-MEDIA-{tmp_path.name[:8]}"
    (run_dir / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": event_id,
                    "type": "pothole",
                    "lat": 39.9042,
                    "lon": 41.2679,
                    "confidence": 0.9,
                    "confidence_band": "probable",
                    "observations": 2,
                    "severity": "medium",
                    "status": "under_review",
                    "vehicle_id": "DJI-MEDIA",
                    "first_seen_ms": 1000,
                    "last_seen_ms": 2000,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"vehicle_id": "DJI-MEDIA", "camera_id": "AERIAL"}), encoding="utf-8"
    )

    store = Store()
    ingest_run_dir(run_dir, store=store)
    canonical = store.find_canonical_for_source_id(event_id) or event_id

    from cityvision.storage import get_object_store

    key = f"evidence/{canonical}/event.jpg"
    get_object_store().put_bytes(key, PIXEL)
    store.upsert_event_media(
        canonical, "image", str(run_dir / "event.jpg"), "image/jpeg", len(PIXEL), key
    )
    return canonical, key


def _client(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    from cityvision.api.app import app

    return TestClient(app)


def test_signed_url_from_listing_serves_the_object(event_with_media, monkeypatch):
    event_id, _key = event_with_media
    client = _client(monkeypatch, CITYVISION_API_KEY="k-secret", CITYVISION_RBAC="0")

    listing = client.get(
        f"/api/events/{event_id}/media", headers={"X-API-Key": "k-secret"}
    )
    assert listing.status_code == 200
    rows = listing.json()
    assert rows, "expected the attached media row"
    url = rows[0]["url"]
    assert "sig=" in url, "listing must hand out a signed URL when auth is configured"

    # An <img> tag sends no headers — the signature alone must work.
    served = client.get(url)
    assert served.status_code == 200
    assert served.content == PIXEL


def test_same_object_is_refused_without_the_signature(event_with_media, monkeypatch):
    _event_id, key = event_with_media
    client = _client(monkeypatch, CITYVISION_API_KEY="k-secret", CITYVISION_RBAC="0")

    assert client.get(f"/api/storage/{key}").status_code == 401
    assert client.get(f"/api/storage/{key}", headers={"X-API-Key": "k-secret"}).status_code == 200


def test_event_detail_embeds_signed_media_urls(event_with_media, monkeypatch):
    event_id, _key = event_with_media
    client = _client(monkeypatch, CITYVISION_API_KEY="k-secret", CITYVISION_RBAC="0")

    detail = client.get(f"/api/events/{event_id}", headers={"X-API-Key": "k-secret"})
    assert detail.status_code == 200
    media = detail.json().get("media") or []
    assert media and all("url" in m for m in media)
    assert client.get(media[0]["url"]).status_code == 200


def test_media_open_without_credentials(event_with_media, monkeypatch):
    """Unconfigured local pilot keeps serving evidence without a signature."""
    _event_id, key = event_with_media
    client = _client(monkeypatch, CITYVISION_API_KEY="", CITYVISION_JWT_SECRET="")

    r = client.get(f"/api/storage/{key}")
    assert r.status_code == 200
    assert r.content == PIXEL


def test_run_annotated_video_requires_auth(monkeypatch, tmp_path):
    client = _client(monkeypatch, CITYVISION_API_KEY="k-secret")
    # 401 before the run is even looked up — no existence oracle either.
    assert client.get("/api/runs/999999/annotated").status_code == 401
