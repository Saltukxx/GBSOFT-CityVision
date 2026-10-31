"""Route planning, flight tracks and route adherence."""

from __future__ import annotations

import json
import uuid

import pytest
from test_admin_api import _auth, _client, _db_ok, _event, city  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")

# A ~1.1 km north-south line in Erzurum.
ROUTE = [[41.2700, 39.9000], [41.2700, 39.9050], [41.2700, 39.9100]]


def _plan(**over):
    body = {"name": "Kordon test", "coordinates": ROUTE, "altitude_m": 70, "speed_ms": 6, "gimbal_deg": -80}
    body.update(over)
    return body


def test_route_crud_export_and_permissions(city):  # noqa: F811
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    admin = _auth(client, city["admin"], "admin-pass-1")

    r = client.post("/api/routes/plan", json=_plan(), headers=op)
    assert r.status_code == 201, r.text
    route = r.json()
    rid = route["id"]
    assert rid.startswith("kordon-test-") and route["city_id"] == city["id"]
    assert 1100 < route["length_m"] < 1150
    assert route["props"]["altitude_m"] == 70 and route["created_by"] == city["op"]

    bad = client.post("/api/routes/plan", json=_plan(coordinates=[[41.27, 39.9]]), headers=op)
    assert bad.status_code == 422
    assert client.post("/api/routes/plan", json=_plan(coordinates=[[200, 39.9], [41.2, 39.9]]), headers=op).status_code == 422

    upd = client.put(f"/api/routes/{rid}/plan", json=_plan(name="Kordon v2", coordinates=ROUTE[:2]), headers=op)
    assert upd.status_code == 200 and upd.json()["name"] == "Kordon v2"
    assert 540 < upd.json()["length_m"] < 580

    kml = client.get(f"/api/routes/{rid}/export.kml", headers=op)
    assert kml.status_code == 200 and "kml" in kml.headers["content-type"]
    assert "41.27,39.9,70" in kml.text and "<name>WP2</name>" in kml.text and "relativeToGround" in kml.text
    gj = client.get(f"/api/routes/{rid}/export.geojson", headers=op).json()
    assert gj["features"][0]["geometry"]["coordinates"] == ROUTE[:2]

    listed = client.get("/api/routes", headers=op).json()
    assert any(x["id"] == rid and x["flights"] == 0 for x in listed)

    assert client.delete(f"/api/routes/{rid}", headers=op).status_code == 403
    assert client.delete(f"/api/routes/{rid}", headers=admin).status_code == 204
    assert client.get(f"/api/routes/{rid}", headers=op).status_code == 404


def test_tracks_and_adherence(city, tmp_path):  # noqa: F811
    from cityvision.flights.uploads import web_device_id

    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    store = city["store"]
    rid = client.post("/api/routes/plan", json=_plan(), headers=op).json()["id"]

    # A flight whose run has a GPS track along the route.
    eid = _event(city, tmp_path)
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_dir FROM runs WHERE city_id = %s ORDER BY id DESC LIMIT 1", (city["id"],))
            run_dir = cur.fetchone()["run_dir"]
            on_route = [[41.27001, 39.9 + i * 0.001] for i in range(11)]
            cur.execute(
                "UPDATE runs SET summary = jsonb_set(COALESCE(summary, '{}'::jsonb), '{track}', %s) WHERE run_dir = %s",
                (json.dumps(on_route), run_dir),
            )
        store._commit(conn)
    fid = uuid.uuid4().hex
    store.create_edge_video_upload(
        fid, web_device_id(store, city["id"]), f"flights/{fid}/v.mp4", f"sha-{fid}",
        city_id=city["id"], nbytes=1, payload={"source": "web", "name": "Track test"}, status="succeeded",
    )
    store.update_edge_video_upload(fid, run_dir=run_dir)
    assert eid

    tracks = client.get("/api/flights/tracks", headers=op).json()
    t = next(x for x in tracks if x["id"] == fid)
    assert t["name"] == "Track test" and len(t["track"]) == 11

    # Not linked yet → no adherence; link it, then it's measured.
    assert client.get(f"/api/flights/{fid}", headers=op).json()["adherence"] is None
    assert client.patch(f"/api/flights/{fid}/route", json={"route_id": rid}, headers=op).status_code == 200
    adh = client.get(f"/api/flights/{fid}", headers=op).json()["adherence"]
    assert adh["coverage"] > 0.95 and adh["off_route"] == 0 and adh["max_deviation_m"] < 5
    assert client.get("/api/flights/tracks", params={"route_id": rid}, headers=op).json()[0]["id"] == fid
    assert next(x for x in client.get("/api/routes", headers=op).json() if x["id"] == rid)["flights"] == 1

    # A track 300 m east of the route barely covers it.
    off = store.route_adherence(rid, [[41.2735, 39.9 + i * 0.001] for i in range(11)])
    assert off["coverage"] < 0.05 and off["off_route"] == 1.0 and off["max_deviation_m"] > 250

    assert client.patch(f"/api/flights/{fid}/route", json={"route_id": "nope"}, headers=op).status_code == 404
