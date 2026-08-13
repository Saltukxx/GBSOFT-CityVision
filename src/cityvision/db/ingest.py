from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from cityvision.db.store import Store
from cityvision.settings import get_settings
from cityvision.storage import get_object_store

_MEDIA_MAP = {
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".mp4": ("clip", "video/mp4"),
    ".json": ("json", "application/json"),
}


def ingest_run_dir(run_dir: str | Path, store: Store | None = None) -> Dict[str, Any]:
    """Ingest pipeline output into PostgreSQL (events, fleet, media, stats)."""
    run_dir = Path(run_dir).resolve()
    store = store or Store()
    settings = get_settings()

    events_path = run_dir / "events.json"
    summary_path = run_dir / "summary.json"
    if not events_path.exists():
        raise FileNotFoundError(f"Missing {events_path}")

    events = json.loads(events_path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("events.json must be a JSON array")

    summary: Dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    meta: Dict[str, Any] = {
        "source": summary.get("source") or str(run_dir),
        "vehicle_id": summary.get("vehicle_id"),
        "camera_id": summary.get("camera_id"),
        "model_a": summary.get("model_a"),
        "model_b": summary.get("model_b"),
        "route_id": summary.get("route_id"),
        "city_id": summary.get("city_id") or settings.default_city,
    }

    det_path = run_dir / "detections.jsonl"
    class_counts: Dict[tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "conf_sum": 0.0}
    )
    if det_path.exists():
        with det_path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                row_type = row.get("type")
                if row_type == "meta" or (i == 0 and row_type == "meta"):
                    meta["source"] = row.get("source") or meta["source"]
                    meta["vehicle_id"] = row.get("vehicle_id") or meta["vehicle_id"]
                    meta["camera_id"] = row.get("camera_id") or meta["camera_id"]
                    meta["model_a"] = row.get("model_a") or meta["model_a"]
                    if row.get("model_b") is not None:
                        meta["model_b"] = row.get("model_b")
                    continue
                if row_type == "summary":
                    continue
                # Per-detection lines (current pipeline) or legacy frame batches
                if row_type == "detection" or (
                    "class" in row and not isinstance(row.get("detections"), list)
                ):
                    dets = [row]
                else:
                    raw_dets = row.get("detections")
                    if not isinstance(raw_dets, list):
                        continue
                    dets = raw_dets
                for det in dets:
                    if not isinstance(det, dict):
                        continue
                    name = str(
                        det.get("class_name")
                        or det.get("class")
                        or det.get("name")
                        or "unknown"
                    )
                    role = str(det.get("model") or det.get("model_role") or det.get("model_id") or "A")
                    key = (name, role)
                    class_counts[key]["count"] += 1
                    class_counts[key]["conf_sum"] += float(det.get("confidence") or 0.0)

    # Ensure fleet rows exist before FK-ish attribution
    vehicle_ids: set[str] = set()
    camera_ids: set[str] = set()
    if meta.get("vehicle_id"):
        vehicle_ids.add(str(meta["vehicle_id"]))
    if meta.get("camera_id"):
        camera_ids.add(str(meta["camera_id"]))
    for ev in events:
        if not isinstance(ev, dict):
            continue
        for vid in ev.get("vehicle_ids") or []:
            vehicle_ids.add(str(vid))
        for cid in ev.get("camera_ids") or []:
            camera_ids.add(str(cid))
        if ev.get("vehicle_id"):
            vehicle_ids.add(str(ev["vehicle_id"]))
        if ev.get("camera_id"):
            camera_ids.add(str(ev["camera_id"]))

    for vid in sorted(vehicle_ids):
        store.upsert_vehicle(vid, name=vid, route_id=meta.get("route_id"), city_id=meta.get("city_id"))
    for cid in sorted(camera_ids):
        # Prefer attaching camera to run vehicle when known
        store.upsert_camera(cid, vehicle_id=meta.get("vehicle_id"), label=cid, facing=cid.lower())

    # DB writes (run/events/obs/stats/models) share one transaction.
    # Object-store file copies stay outside so I/O failures don't leave half-commits.
    media_jobs: List[Dict[str, Any]] = []
    with store.transaction():
        run_id = store.upsert_run(str(run_dir), meta, summary)

        for (class_name, role), agg in class_counts.items():
            c = int(agg["count"])
            avg = (agg["conf_sum"] / c) if c else None
            store.upsert_detection_stat(run_id, class_name, c, avg, model_role=role)

        n_events = 0
        n_created = 0
        n_updated = 0
        n_merged = 0
        n_already_merged = 0
        n_obs = 0
        merge_map: List[Dict[str, str]] = []
        for ev in events:
            if not isinstance(ev, dict) or not ev.get("event_id"):
                continue
            if meta.get("route_id") and not ev.get("route_id"):
                ev = {**ev, "route_id": meta["route_id"]}
            if meta.get("city_id") and not ev.get("city_id"):
                ev = {**ev, "city_id": meta["city_id"]}
            canonical_id, action = _upsert_or_merge_event(
                store,
                run_id,
                ev,
                enabled=settings.merge_enabled,
                radius_m=settings.merge_radius_m,
            )
            n_events += 1
            if action == "merged":
                n_merged += 1
                merge_map.append(
                    {
                        "from": str(ev["event_id"]),
                        "into": canonical_id,
                        "type": str(ev.get("type")),
                    }
                )
            elif action == "already_merged":
                n_already_merged += 1
                merge_map.append(
                    {
                        "from": str(ev["event_id"]),
                        "into": canonical_id,
                        "type": str(ev.get("type")),
                        "note": "already_merged",
                    }
                )
            elif action == "updated":
                n_updated += 1
            else:
                n_created += 1
            n_obs += _ingest_observations(store, run_id, {**ev, "event_id": canonical_id})
            store.sync_observation_count(canonical_id)
            media_jobs.append({**ev, "event_id": canonical_id})

        _register_models(store, meta, summary)

    n_media = 0
    for ev in media_jobs:
        n_media += _ingest_evidence_media(store, ev)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "events_ingested": n_events,
        "events_created": n_created,
        "events_updated": n_updated,
        "events_merged": n_merged,
        "events_already_merged": n_already_merged,
        "merges": merge_map,
        "observations_ingested": n_obs,
        "media_ingested": n_media,
        "detection_classes": len(class_counts),
        "vehicles": sorted(vehicle_ids),
        "city_id": meta.get("city_id"),
        "kpis": store.kpis(city_id=meta.get("city_id")),
    }


def _upsert_or_merge_event(
    store: Store,
    run_id: int,
    ev: Dict[str, Any],
    *,
    enabled: bool,
    radius_m: float,
) -> Tuple[str, str]:
    """
    Insert event, update existing, or merge into a nearby same-type event.

    Returns (canonical_event_id, action) where action is one of:
    created | updated | merged | already_merged
    """
    event_id = str(ev["event_id"])

    # Idempotent: this source id was already folded into a canonical event.
    prior = store.find_canonical_for_source_id(event_id)
    if prior:
        return prior, "already_merged"

    # Re-ingest of the same event_id updates in place (preserves operator status).
    if store.get_event(event_id) is not None:
        store.upsert_event(run_id, ev)
        return event_id, "updated"

    lat, lon = ev.get("lat"), ev.get("lon")
    if enabled and lat is not None and lon is not None and ev.get("type"):
        cand = store.find_merge_candidate(
            str(ev["type"]),
            float(lat),
            float(lon),
            radius_m=radius_m,
            exclude_event_id=event_id,
            city_id=str(ev["city_id"]) if ev.get("city_id") else None,
        )
        if cand and cand.get("event_id"):
            canonical = str(cand["event_id"])
            store.merge_into_event(canonical, run_id, ev)
            return canonical, "merged"

    store.upsert_event(run_id, ev)
    return event_id, "created"


def _ingest_observations(store: Store, run_id: int, ev: Dict[str, Any]) -> int:
    event_id = str(ev["event_id"])
    vids = [str(v) for v in (ev.get("vehicle_ids") or [])]
    cids = [str(c) for c in (ev.get("camera_ids") or [])]
    tids = ev.get("track_ids") or []
    if not vids and ev.get("vehicle_id"):
        vids = [str(ev["vehicle_id"])]
    if not cids and ev.get("camera_id"):
        cids = [str(ev["camera_id"])]

    rows: List[Dict[str, Any]] = []
    n = max(len(vids), len(tids), 1 if vids or tids else 0)
    if n == 0:
        return 0
    for i in range(n):
        rows.append(
            {
                "vehicle_id": vids[i] if i < len(vids) else (vids[-1] if vids else None),
                "camera_id": cids[0] if cids else None,
                "track_id": tids[i] if i < len(tids) else None,
                "lat": ev.get("lat"),
                "lon": ev.get("lon"),
                "confidence": ev.get("confidence"),
                "frame_idx": ev.get("sample_frame"),
                "seen_ms": ev.get("first_seen_ms") or ev.get("first_seen"),
                "payload": {"index": i},
            }
        )
    return store.replace_observations(event_id, run_id, rows)


def _ingest_evidence_media(store: Store, ev: Dict[str, Any]) -> int:
    event_id = str(ev["event_id"])
    ed = ev.get("evidence_dir")
    if not ed:
        return 0
    root = Path(ed)
    if not root.is_dir():
        return 0
    obj = get_object_store()
    n = 0
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        media_type, ctype = _MEDIA_MAP.get(path.suffix.lower(), ("other", None))
        if path.name.lower().startswith("crop"):
            media_type = "crop"
        key = f"evidence/{event_id}/{path.name}"
        try:
            obj.put_file(key, path)
        except OSError:
            key = None
        store.upsert_event_media(
            event_id,
            media_type,
            str(path.resolve()),
            content_type=ctype,
            nbytes=path.stat().st_size,
            object_key=key,
        )
        n += 1
    return n


def _register_models(store: Store, meta: Dict[str, Any], summary: Dict[str, Any]) -> None:
    # model_versions table via raw SQL through store.connect
    rows = []
    if meta.get("model_a"):
        rows.append(("model_a", str(meta["model_a"]), "A"))
    mb = meta.get("model_b")
    if isinstance(mb, list):
        for i, p in enumerate(mb):
            rows.append((f"model_b_{i}", str(p), "B"))
    elif mb:
        rows.append(("model_b", str(mb), "B"))
    mv = summary.get("model_version") or meta.get("model_version")
    if mv:
        rows.append((str(mv), str(mv), "event"))
    if not rows:
        return
    with store.connect() as conn:
        with conn.cursor() as cur:
            for name, path, role in rows:
                cur.execute(
                    """
                    INSERT INTO model_versions (name, path, role, metrics)
                    SELECT %s, %s, %s, '{}'::jsonb
                    WHERE NOT EXISTS (
                      SELECT 1 FROM model_versions WHERE name = %s AND path = %s
                    )
                    """,
                    (name, path, role, name, path),
                )
        store._commit(conn)
