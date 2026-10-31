"""Phase 4: labelling queue, training export, model performance, weekly report."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

# Shared fixtures/helpers: a throwaway city with an admin and an operator.
from test_admin_api import _auth, _client, _db_ok, _event, city  # noqa: F401

from cityvision.labelling import split_for, validate_boxes, yolo_lines

# ---------- pure helpers ----------


def test_validate_boxes_clips_and_rejects():
    out = validate_boxes([{"cls": "pothole", "x": -0.1, "y": 0.9, "w": 0.3, "h": 0.3}])
    assert out == [{"cls": "pothole", "x": 0.0, "y": 0.9, "w": 0.2, "h": 0.1}]
    with pytest.raises(ValueError):
        validate_boxes([{"cls": "manhole", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}])
    with pytest.raises(ValueError):
        validate_boxes([{"cls": "pothole", "x": 1.2, "y": 0.1, "w": 0.1, "h": 0.1}])


def test_split_keeps_flights_together_and_holdout_is_test():
    a = {"event_id": "E1", "flight_id": "F-1"}
    b = {"event_id": "E2", "flight_id": "F-1"}
    assert split_for(a) == split_for(b)
    assert split_for({**a, "holdout": True}) == "test"
    spread = {split_for({"event_id": f"E{i}", "flight_id": f"F{i}"}) for i in range(200)}
    assert spread == {"train", "val"}


def test_yolo_lines_are_center_format():
    line = yolo_lines([{"cls": "road_crack", "x": 0.1, "y": 0.2, "w": 0.2, "h": 0.4}])
    assert line == "1 0.200000 0.400000 0.200000 0.400000\n"
    assert yolo_lines([]) == ""


# ---------- API ----------

pytestmark_db = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


@pytest.fixture()
def superadmin(city):  # noqa: F811
    from cityvision.api.security import hash_password

    name = f"sa-{city['id']}"
    city["store"].upsert_user(name, "GBSoft", "superadmin", hash_password("super-pass-1"), city_id=None)
    yield name
    with city["store"].connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (name,))
        city["store"]._commit(conn)


def _add_media(city, event_id: str, tmp_path: Path, *, clean: bool = True) -> None:  # noqa: F811
    import cv2
    import numpy as np

    store = city["store"]
    frame = tmp_path / f"{event_id}-frame.jpg"
    cv2.imwrite(str(frame), np.full((90, 160, 3), 120, dtype=np.uint8))
    store.upsert_event_media(event_id, "image", str(frame))
    if clean:
        store.upsert_event_media(event_id, "frame", str(frame))
    meta = tmp_path / f"{event_id}.json"
    meta.write_text(json.dumps({"sample_bbox": [16, 9, 48, 36]}), encoding="utf-8")
    store.upsert_event_media(event_id, "json", str(meta))


@pytestmark_db
def test_labelling_flow_and_export(city, superadmin, tmp_path):  # noqa: F811
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    sa = _auth(client, superadmin, "super-pass-1")
    admin = _auth(client, city["admin"], "admin-pass-1")

    e_neg, e_pos, e_old = (_event(city, tmp_path) for _ in range(3))
    _add_media(city, e_neg, tmp_path)
    _add_media(city, e_pos, tmp_path)
    _add_media(city, e_old, tmp_path, clean=False)
    client.post(f"/api/events/{e_neg}/review", json={"label": "wrong", "reason": "manhole"}, headers=op)
    client.post(f"/api/events/{e_pos}/review", json={"label": "correct"}, headers=op)
    client.post(f"/api/events/{e_old}/review", json={"label": "unsure"}, headers=op)

    # GBSoft-only.
    assert client.get("/api/labelling/queue", headers=admin).status_code == 403

    q = client.get("/api/labelling/queue", params={"city_id": city["id"]}, headers=sa).json()
    ids = [i["event_id"] for i in q["items"]]
    assert ids[0] == e_old  # "not sure" first
    assert set(ids) == {e_neg, e_pos, e_old}
    assert q["counts"]["todo"] == 3

    item = client.get(f"/api/labelling/items/{e_pos}", headers=sa).json()
    assert item["sample_bbox"] == [16.0, 9.0, 48.0, 36.0]
    assert item["frame"]["url"] and item["review_label"] == "correct"

    put = lambda eid, body: client.put(f"/api/labelling/items/{eid}", json=body, headers=sa)  # noqa: E731
    assert put(e_old, {"kind": "negative"}).json()["detail"] == "no_clean_frame"
    assert put(e_pos, {"kind": "positive", "boxes": [{"cls": "manhole", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}]}).status_code == 422
    assert put(e_pos, {"kind": "positive", "boxes": []}).status_code == 422
    assert put(e_pos, {"kind": "positive", "boxes": [{"cls": "pothole", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.4}]}).status_code == 200
    assert put(e_neg, {"kind": "negative"}).status_code == 200
    assert put(e_old, {"kind": "skip"}).status_code == 200

    counts = client.get("/api/labelling/queue", params={"city_id": city["id"], "done": True}, headers=sa).json()["counts"]
    assert counts["todo"] == 0
    assert counts["by_kind"] == {"positive": 1, "negative": 1, "skip": 1}
    assert counts["boxes_by_class"] == {"pothole": 1}

    r = client.get("/api/labelling/export.zip", params={"city_id": city["id"]}, headers=sa)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    manifest = json.loads(zf.read("manifest.json"))
    assert sum(manifest["images"].values()) == 2  # skip is not exported
    assert sum(manifest["hard_negatives"].values()) == 1
    pos_label = next(n for n in names if n.startswith("labels/") and e_pos in n)
    assert zf.read(pos_label).decode() == "0 0.200000 0.300000 0.200000 0.400000\n"
    neg_label = next(n for n in names if n.startswith("labels/") and e_neg in n)
    assert zf.read(neg_label) == b""
    assert "names:\n  0: pothole" in zf.read("data.yaml").decode()

    assert client.delete(f"/api/labelling/items/{e_old}", headers=sa).status_code == 204


@pytestmark_db
def test_model_performance_and_weekly_report(city, tmp_path):  # noqa: F811
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    admin = _auth(client, city["admin"], "admin-pass-1")
    e1, e2, e3 = (_event(city, tmp_path) for _ in range(3))
    client.post(f"/api/events/{e1}/review", json={"label": "correct"}, headers=op)
    client.post(f"/api/events/{e2}/review", json={"label": "wrong", "reason": "shadow"}, headers=op)
    client.post(f"/api/events/{e3}/review", json={"label": "work_order", "unit": "roads"}, headers=op)

    perf = client.get("/api/models/performance", headers=admin).json()
    row = next(p for p in perf if p["model_version"] == "unknown")
    assert row["events"] == 3 and row["confirmed"] == 2 and row["false_alarms"] == 1
    assert row["precision"] == pytest.approx(0.667, abs=0.001)
    assert row["false_alarm_reasons"] == {"shadow": 1}
    assert client.get("/api/models/performance", headers=op).status_code == 403

    rep = client.get("/api/reports/weekly", headers=op).json()
    assert rep["city"]["id"] == city["id"]
    assert rep["new_candidates"] == 3 and rep["decisions"] == 3
    assert rep["confirmed"] == 2 and rep["false_alarms"] == 1
    assert rep["false_alarm_reasons"] == {"shadow": 1}
    assert rep["work_orders"]["opened"] == 1 and rep["work_orders"]["open_now"] == 1
    assert {e["event_id"] for e in rep["confirmed_events"]} == {e1, e3}
    assert rep["previous"]["decisions"] == 0
    last_week = client.get("/api/reports/weekly", params={"start": "2020-01-06"}, headers=op).json()
    assert last_week["start"] == "2020-01-06" and last_week["decisions"] == 0
