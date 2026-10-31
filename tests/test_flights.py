"""Flights: resumable browser upload, finalize job, list/detail API."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cityvision.flights import uploads as fu
from cityvision.settings import get_settings

# ---------- pure helpers (no DB) ----------


def test_chunk_math():
    cs = fu.CHUNK_SIZE
    assert fu.chunk_count(1) == 1
    assert fu.chunk_count(cs) == 1
    assert fu.chunk_count(cs + 1) == 2
    assert fu.expected_chunk_bytes(0, cs + 5) == cs
    assert fu.expected_chunk_bytes(1, cs + 5) == 5
    with pytest.raises(ValueError):
        fu.expected_chunk_bytes(2, cs + 5)
    with pytest.raises(ValueError):
        fu.expected_chunk_bytes(-1, 10)


def test_staging_dir_rejects_traversal():
    with pytest.raises(ValueError):
        fu.staging_dir("../../etc")
    assert fu.valid_upload_id(uuid.uuid4().hex)


# ---------- DB-backed ----------


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        from cityvision.db.store import Store

        return Store().ping()
    except Exception:
        return False


db = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


@pytest.fixture(autouse=True)
def _cleanup_flights(monkeypatch):
    """Delete every flight row (and its jobs) a test creates."""
    from cityvision.db.store import Store

    created: list[str] = []
    original = Store.create_edge_video_upload

    def recording(self, upload_id, *args, **kwargs):
        created.append(upload_id)
        return original(self, upload_id, *args, **kwargs)

    monkeypatch.setattr(Store, "create_edge_video_upload", recording)
    yield
    if not created or not _db_ok():
        return
    store = Store()
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_id FROM edge_video_uploads WHERE upload_id = ANY(%s) AND job_id IS NOT NULL",
                (created,),
            )
            job_ids = [r["job_id"] for r in cur.fetchall()]
            cur.execute("DELETE FROM edge_video_uploads WHERE upload_id = ANY(%s)", (created,))
            cur.execute("DELETE FROM jobs WHERE id = ANY(%s)", (job_ids,))
        store._commit(conn)


@contextmanager
def _client(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CITYVISION_API_KEY", "")
    monkeypatch.setenv("CITYVISION_JWT_SECRET", "")
    monkeypatch.setenv("CITYVISION_STRICT_TENANCY", "0")
    monkeypatch.setenv("CITYVISION_EDGE_UPLOAD_DIR", str(tmp_path / "edge"))
    monkeypatch.setenv("CITYVISION_OBJECT_STORE", str(tmp_path / "objects"))
    monkeypatch.setenv("CITYVISION_S3_ENDPOINT", "")
    get_settings.cache_clear()
    from cityvision.storage import get_object_store

    get_object_store.cache_clear()
    from cityvision.api.app import app

    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()
        get_object_store.cache_clear()


@pytest.fixture()
def queued(monkeypatch):
    """Capture enqueued jobs instead of running the video pipeline."""
    import cityvision.api.routers.flights as flights_router

    calls: list[tuple[str, dict]] = []

    def fake_enqueue(store, job_type, payload):
        calls.append((job_type, payload))
        return store.create_job(job_type, payload), False

    monkeypatch.setattr(flights_router, "enqueue_job", fake_enqueue)
    return calls


def _video_bytes(n: int) -> bytes:
    # Unique per test so dedupe never matches an earlier run.
    return (uuid.uuid4().bytes * (n // 16 + 1))[:n]


@db
def test_upload_resume_complete_and_finalize(monkeypatch, tmp_path, queued):
    monkeypatch.setattr(fu, "CHUNK_SIZE", 1024)
    import cityvision.api.routers.flights as flights_router

    monkeypatch.setattr(flights_router.fu, "CHUNK_SIZE", 1024)
    data = _video_bytes(2500)  # 3 chunks: 1024, 1024, 452

    with _client(monkeypatch, tmp_path) as client:
        r = client.post(
            "/api/flights/uploads",
            json={"filename": "DJI_0001.MP4", "size": len(data), "name": "Corridor A"},
        )
        assert r.status_code == 201, r.text
        flight = r.json()
        fid = flight["id"]
        assert flight["status"] == "uploading"
        assert flight["upload"] == {"chunk_size": 1024, "chunks": 3, "received": []}

        # Out of order, and a wrong-size chunk is rejected without being kept.
        assert client.put(f"/api/flights/uploads/{fid}/chunks/2", content=data[2048:]).status_code == 200
        bad = client.put(f"/api/flights/uploads/{fid}/chunks/0", content=data[:10])
        assert bad.status_code == 422
        assert client.put(f"/api/flights/uploads/{fid}/chunks/9", content=b"x").status_code == 422

        # Resume: the server reports what it already has.
        assert client.get(f"/api/flights/{fid}").json()["upload"]["received"] == [2]
        missing = client.post(f"/api/flights/uploads/{fid}/complete")
        assert missing.status_code == 409
        assert missing.json()["detail"]["missing"] == [0, 1]

        for i in (0, 1):
            chunk = data[i * 1024 : (i + 1) * 1024]
            assert client.put(f"/api/flights/uploads/{fid}/chunks/{i}", content=chunk).status_code == 200
        tele = client.put(
            f"/api/flights/uploads/{fid}/telemetry",
            params={"filename": "DJI_0001.SRT"},
            content=b"1\n00:00:00,000 --> 00:00:00,033\n[latitude: 39.9] [longitude: 41.2]\n",
        )
        assert tele.status_code == 200

        done = client.post(f"/api/flights/uploads/{fid}/complete")
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "received"
        assert queued[-1][0] == "flight_upload"
        # A finished upload can't take more chunks.
        assert client.put(f"/api/flights/uploads/{fid}/chunks/0", content=data[:1024]).status_code == 409

        # Run the job body with a stand-in for video analysis.
        from cityvision.db.store import Store

        store = Store()
        seen: dict = {}

        def fake_analyze(store_, payload, job_id):
            seen.update(payload)
            store_.update_edge_video_upload(payload["upload_id"], status="succeeded")
            return {"ok": True}

        fu.finalize_and_analyze(store, {"upload_id": fid}, None, fake_analyze)

        from cityvision.storage import get_object_store

        obj = get_object_store()
        assert obj.open_read(seen["object_key"]).read() == data
        assert seen["gps_object_key"].endswith("gps.srt")
        assert not fu.staging_dir(fid).exists()

        listed = client.get("/api/flights").json()
        row = next(f for f in listed if f["id"] == fid)
        assert row["status"] == "succeeded"
        assert row["name"] == "Corridor A"
        assert row["source"] == "upload"
        assert row["has_telemetry"] is True
        assert "object_key" not in row


@db
def test_duplicate_video_is_flagged(monkeypatch, tmp_path, queued):
    data = _video_bytes(300)
    from cityvision.db.store import Store

    with _client(monkeypatch, tmp_path) as client:
        ids = []
        for _ in range(2):
            fid = client.post("/api/flights/uploads", json={"filename": "a.mp4", "size": len(data)}).json()["id"]
            client.put(f"/api/flights/uploads/{fid}/chunks/0", content=data)
            assert client.post(f"/api/flights/uploads/{fid}/complete").status_code == 200
            fu.finalize_and_analyze(
                Store(), {"upload_id": fid}, None,
                lambda s, p, j: s.update_edge_video_upload(p["upload_id"], status="succeeded") and {},
            )
            ids.append(fid)

        second = client.get(f"/api/flights/{ids[1]}").json()
        assert second["status"] == "duplicate"
        assert second["duplicate_of"] == ids[0]


@db
def test_cancel_and_validation(monkeypatch, tmp_path, queued):
    with _client(monkeypatch, tmp_path) as client:
        assert client.post("/api/flights/uploads", json={"filename": "notes.txt", "size": 10}).status_code == 422
        monkeypatch.setenv("CITYVISION_FLIGHT_MAX_UPLOAD_GB", "0.000001")
        get_settings.cache_clear()
        assert client.post("/api/flights/uploads", json={"filename": "a.mp4", "size": 10_000}).status_code == 413
        monkeypatch.setenv("CITYVISION_FLIGHT_MAX_UPLOAD_GB", "20")
        get_settings.cache_clear()

        fid = client.post("/api/flights/uploads", json={"filename": "a.mp4", "size": 10}).json()["id"]
        bad_tele = client.put(f"/api/flights/uploads/{fid}/telemetry", params={"filename": "x.exe"}, content=b"1")
        assert bad_tele.status_code == 422
        assert client.delete(f"/api/flights/uploads/{fid}").status_code == 204
        assert not fu.staging_dir(fid).exists()
        assert all(f["id"] != fid for f in client.get("/api/flights").json())
        assert client.get("/api/flights/not-a-real-id").status_code == 404
