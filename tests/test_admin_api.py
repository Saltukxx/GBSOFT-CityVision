"""Work-order board, user admin, city settings, zone/route upload, review stats, audit."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cityvision.settings import get_settings


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        from cityvision.db.store import Store

        return Store().ping()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")

JWT = "test-admin-secret-0123456789abcdef0123"


@pytest.fixture()
def city(monkeypatch):
    """A throwaway city with an admin and an operator; removed afterwards."""
    from cityvision.api.security import hash_password
    from cityvision.db.store import Store
    from cityvision.tenant import TENANT_ALL, reset_tenant_city, set_tenant_city

    monkeypatch.setenv("CITYVISION_JWT_SECRET", JWT)
    monkeypatch.setenv("CITYVISION_API_KEY", "")
    monkeypatch.setenv("CITYVISION_STRICT_TENANCY", "1")
    monkeypatch.setenv("CITYVISION_RBAC", "1")  # conftest turns it off by default
    get_settings.cache_clear()

    token = set_tenant_city(TENANT_ALL)
    cid = f"t-{uuid.uuid4().hex[:8]}"
    store = Store()
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO cities (id, name) VALUES (%s, %s)", (cid, "Test City"))
        store._commit(conn)
    admin, op = f"adm-{cid}", f"op-{cid}"
    store.upsert_user(admin, "Admin", "admin", hash_password("admin-pass-1"), city_id=cid)
    store.upsert_user(op, "Operator", "operator", hash_password("op-pass-123"), city_id=cid)
    reset_tenant_city(token)

    yield {"id": cid, "admin": admin, "op": op, "store": store}

    token = set_tenant_city(TENANT_ALL)
    with store.connect() as conn:
        with conn.cursor() as cur:
            for table in ("work_orders",):
                cur.execute(
                    f"DELETE FROM {table} WHERE event_id IN (SELECT event_id FROM events WHERE city_id = %s)",
                    (cid,),
                )
            cur.execute("DELETE FROM runs WHERE city_id = %s", (cid,))
            for table in ("events", "zones", "routes", "audit_log", "users", "edge_video_uploads", "edge_devices"):
                cur.execute(f"DELETE FROM {table} WHERE city_id = %s", (cid,))
            cur.execute("DELETE FROM cities WHERE id = %s", (cid,))
        store._commit(conn)
    reset_tenant_city(token)
    get_settings.cache_clear()


def _client() -> TestClient:
    get_settings.cache_clear()
    from cityvision.api.app import app

    return TestClient(app)


def _auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _event(city: dict, tmp_path: Path) -> str:
    from cityvision.db.ingest import ingest_run_dir

    eid = f"ADM-{uuid.uuid4().hex[:8]}"
    run = tmp_path / eid
    run.mkdir()
    seed = uuid.uuid4().int % 10_000
    (run / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": eid,
                    "type": "pothole",
                    "lat": 37.0 + seed * 1e-4,
                    "lon": 29.0 + seed * 1e-4,
                    "confidence": 0.9,
                    "confidence_band": "probable",
                    "observations": 1,
                    "status": "under_review",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(json.dumps({"city_id": city["id"]}), encoding="utf-8")
    from cityvision.tenant import TENANT_ALL, reset_tenant_city, set_tenant_city

    token = set_tenant_city(TENANT_ALL)
    try:
        ingest_run_dir(run, store=city["store"], city_id=city["id"])
    finally:
        reset_tenant_city(token)
    return eid


def test_work_order_board_lifecycle(city, tmp_path):
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    eid = _event(city, tmp_path)

    r = client.post(f"/api/events/{eid}/review", json={"label": "work_order", "unit": "roads"}, headers=op)
    assert r.status_code == 200, r.text
    wid = r.json()["work_order_id"]

    board = client.get("/api/work-orders/board", headers=op).json()
    card = next(w for w in board if w["id"] == wid)
    assert card["event_type"] == "pothole" and "thumb_url" in card

    def patch(body):
        res = client.patch(f"/api/work-orders/{wid}/board", json=body, headers=op)
        assert res.status_code == 200, res.text
        return res.json()

    assert patch({"status": "in_progress", "assignee": "Crew 3", "due_date": "2026-11-05"})["due_date"] == "2026-11-05"
    assert client.get(f"/api/events/{eid}", headers=op).json()["status"] == "work_order_created"
    patch({"status": "resolved"})
    assert client.get(f"/api/events/{eid}", headers=op).json()["status"] == "resolved"
    patch({"status": "cancelled", "clear_due_date": True})
    assert client.get(f"/api/events/{eid}", headers=op).json()["status"] == "confirmed"

    admin = _auth(client, city["admin"], "admin-pass-1")
    audit = client.get("/api/audit/search", params={"action": "work_order_update", "entity_id": str(wid)}, headers=admin).json()
    # The person who made the change is recorded, not the assignee.
    assert {a["actor"] for a in audit} == {city["op"]}
    assert audit[-1]["detail"]["status"] == "in_progress"


def test_user_admin_rules(city):
    client = _client()
    admin = _auth(client, city["admin"], "admin-pass-1")
    op_name = city["op"]

    assert client.patch(f"/api/users/{op_name}", json={"active": False}, headers=admin).json()["active"] is False
    assert client.post("/api/auth/login", json={"username": op_name, "password": "op-pass-123"}).status_code == 401

    r = client.patch(f"/api/users/{op_name}", json={"active": True, "password": "brand-new-pass", "role": "viewer"}, headers=admin)
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    viewer = _auth(client, op_name, "brand-new-pass")

    assert client.patch(f"/api/users/{op_name}", json={"role": "superadmin"}, headers=admin).status_code == 403
    assert client.patch(f"/api/users/{city['admin']}", json={"active": False}, headers=admin).status_code == 422
    assert client.patch(f"/api/users/{city['admin']}", json={"display_name": "x"}, headers=viewer).status_code == 403
    assert client.patch("/api/users/erzurum-admin-not-here", json={"active": False}, headers=admin).status_code == 404


def test_city_settings(city):
    client = _client()
    admin = _auth(client, city["admin"], "admin-pass-1")
    op = _auth(client, city["op"], "op-pass-123")

    s = client.get("/api/city-settings", headers=op).json()
    assert s["id"] == city["id"] and s["language"] == "en" and s["work_order_units"]

    r = client.patch(
        "/api/city-settings",
        json={"name": "Renamed", "timezone": "Europe/Zagreb", "work_order_units": ["Roads", " Roads ", "Parks", ""]},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    assert r.json()["work_order_units"] == ["Roads", "Parks"]
    assert r.json()["timezone"] == "Europe/Zagreb"
    assert client.patch("/api/city-settings", json={"timezone": "Mars/Base"}, headers=admin).status_code == 422
    assert client.patch("/api/city-settings", json={"language": "xx"}, headers=admin).status_code == 422
    assert client.patch("/api/city-settings", json={"name": "Nope"}, headers=op).status_code == 403
    # A city admin cannot reach another city's settings.
    assert client.get("/api/city-settings", params={"city_id": "erzurum"}, headers=admin).status_code == 403


def test_zone_and_route_upload_stay_in_own_city(city):
    client = _client()
    admin = _auth(client, city["admin"], "admin-pass-1")
    square = {"type": "Polygon", "coordinates": [[[29, 37], [29.001, 37], [29.001, 37.001], [29, 37.001], [29, 37]]]}
    zones = {
        "type": "FeatureCollection",
        "features": [
            # A file must not be able to drop a zone into another city.
            {"type": "Feature", "properties": {"zone_id": f"z-{city['id']}", "city_id": "erzurum"}, "geometry": square},
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [29, 37]}},
        ],
    }
    r = client.post("/api/zones/upload", json=zones, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["zones_upserted"] == 1 and r.json()["skipped"] == 1
    listed = client.get("/api/zones", headers=admin).json()
    assert [z["city_id"] for z in listed if z["zone_id"] == f"z-{city['id']}"] == [city["id"]]

    routes = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "Main"}, "geometry": {"type": "LineString", "coordinates": [[29, 37], [29.01, 37.01]]}},
            {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": [[29, 37]]}},
        ],
    }
    r = client.post("/api/routes/upload", json=routes, headers=admin)
    assert r.json()["routes_upserted"] == 1 and r.json()["skipped"] == 1
    assert client.post("/api/routes/upload", json=routes, headers=_auth(client, city["op"], "op-pass-123")).status_code == 403


def test_review_stats_and_audit_paging(city, tmp_path):
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    admin = _auth(client, city["admin"], "admin-pass-1")
    e1, e2, e3 = (_event(city, tmp_path) for _ in range(3))
    client.post(f"/api/events/{e1}/review", json={"label": "correct"}, headers=op)
    client.post(f"/api/events/{e2}/review", json={"label": "wrong", "reason": "manhole"}, headers=op)
    client.post(f"/api/events/{e3}/review", json={"label": "wrong", "reason": "shadow"}, headers=op)

    s = client.get("/api/kpis/review", params={"days": 7}, headers=op).json()
    assert s["confirmed"] == 1 and s["false_alarms"] == 2
    assert s["false_alarm_reasons"] == {"manhole": 1, "shadow": 1}
    assert s["precision"] == pytest.approx(0.333, abs=0.001)
    assert s["by_reviewer"] == {city["op"]: 3}
    assert s["median_hours_to_decision"] is not None

    page1 = client.get("/api/audit/search", params={"limit": 2}, headers=admin).json()
    assert len(page1) == 2 and page1[0]["id"] > page1[1]["id"]
    page2 = client.get("/api/audit/search", params={"limit": 2, "before_id": page1[-1]["id"]}, headers=admin).json()
    assert page2 and page2[0]["id"] < page1[-1]["id"]
    assert all(a["city_id"] == city["id"] for a in page1 + page2)
    assert client.get("/api/audit/search", headers=op).status_code == 403
