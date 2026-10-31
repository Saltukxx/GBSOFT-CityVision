"""Retention: delete personal data once the city's retention period is over (GDPR / KVKK).

What is personal data here is the *un-anonymised* footage — the original video and
the annotated full video made from it. After `raw_video_days` those are deleted;
the flight keeps its GPS track, its events and their anonymised evidence.

Evidence of rejected candidates (false alarms) has no operational use after
`rejected_evidence_days` and is deleted too — except frames kept as training
labels, which are anonymised.

Flight erasure removes a flight completely on request (right to erasure).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from cityvision.db.store import Store
from cityvision.settings import get_settings

log = logging.getLogger(__name__)

DEFAULT_RAW_VIDEO_DAYS = 30
DEFAULT_REJECTED_EVIDENCE_DAYS = 90


def _store_delete(key: Optional[str]) -> bool:
    if not key:
        return False
    from cityvision.storage import get_object_store

    try:
        return bool(get_object_store().delete(str(key)))
    except Exception:  # noqa: BLE001 — already gone or unreachable: log and continue
        log.warning("could not delete object %s", key, exc_info=True)
        return False


def _unlink(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        log.warning("could not delete %s", path, exc_info=True)
    return False


def city_policy(store: Store, city_id: str) -> Dict[str, Optional[int]]:
    props = (store.get_city(city_id) or {}).get("props") or {}

    def days(key: str, default: int) -> Optional[int]:
        v = props.get(key, default)
        return None if v in (None, "", 0) else int(v)

    return {
        "raw_video_days": days("raw_video_days", DEFAULT_RAW_VIDEO_DAYS),
        "rejected_evidence_days": days("rejected_evidence_days", DEFAULT_REJECTED_EVIDENCE_DAYS),
    }


def purge_raw_video(store: Store, upload: Dict[str, Any]) -> int:
    """Delete one flight's un-anonymised footage. Returns files removed."""
    removed = int(_store_delete(upload.get("object_key")))
    work = get_settings().edge_upload_dir / "analyze" / str(upload["upload_id"])
    removed += _unlink(work / "video.mp4")
    if upload.get("run_dir"):
        removed += _unlink(Path(str(upload["run_dir"])) / "annotated.mp4")
    return removed


def run_retention(store: Store, city_id: Optional[str] = None) -> Dict[str, Any]:
    """Apply each city's policy. Idempotent: already-purged items are skipped."""
    cities = [city_id] if city_id else [c["id"] for c in store.list_cities()]
    report: Dict[str, Any] = {}
    for cid in cities:
        policy = city_policy(store, cid)
        raw_n = files_n = media_n = 0

        if policy["raw_video_days"]:
            with store.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT upload_id, object_key, run_dir FROM edge_video_uploads
                        WHERE city_id = %s
                          AND status IN ('succeeded', 'failed', 'stopped', 'duplicate')
                          AND created_at < NOW() - make_interval(days => %s)
                          AND NOT (payload ? 'raw_deleted_at')
                        """,
                        (cid, policy["raw_video_days"]),
                    )
                    rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                files_n += purge_raw_video(store, row)
                store.update_edge_video_upload(
                    row["upload_id"], payload_merge={"raw_deleted_at": _now(), "raw_deleted_reason": "retention"}
                )
                raw_n += 1

        if policy["rejected_evidence_days"]:
            with store.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT m.id, m.path, m.object_key FROM event_media m
                        JOIN events e ON e.event_id = m.event_id
                        WHERE e.city_id = %s AND e.status = 'false_positive'
                          -- counted from the rejection decision, not from any later touch
                          AND COALESCE(
                                (SELECT MAX(r.created_at) FROM review_feedback r WHERE r.event_id = e.event_id),
                                e.updated_at
                              ) < NOW() - make_interval(days => %s)
                          AND NOT EXISTS (SELECT 1 FROM training_labels t WHERE t.media_id = m.id)
                        """,
                        (cid, policy["rejected_evidence_days"]),
                    )
                    media = [dict(r) for r in cur.fetchall()]
                    for m in media:
                        _store_delete(m.get("object_key"))
                        if m.get("path") and not str(m["path"]).startswith("evidence/"):
                            _unlink(Path(str(m["path"])))
                    if media:
                        cur.execute("DELETE FROM event_media WHERE id = ANY(%s)", ([m["id"] for m in media],))
                store._commit(conn)
            media_n = len(media)

        report[cid] = {**policy, "raw_videos_deleted": raw_n, "files_deleted": files_n, "rejected_media_deleted": media_n}
        if raw_n or media_n:
            store.add_audit(
                actor="system",
                action="retention_purge",
                entity_type="city",
                entity_id=cid,
                detail=report[cid],
                city_id=cid,
            )
    return report


def erase_flight(store: Store, upload_id: str) -> Dict[str, Any]:
    """Remove a flight and everything derived only from it."""
    upload = store.get_edge_video_upload(upload_id)
    if not upload:
        return {"deleted": False}
    files = purge_raw_video(store, upload)
    files += int(_store_delete(upload.get("gps_object_key")))
    events_deleted: List[str] = []
    with store.connect() as conn:
        with conn.cursor() as cur:
            run_id = None
            if upload.get("run_dir"):
                cur.execute("SELECT id FROM runs WHERE run_dir = %s", (upload["run_dir"],))
                r = cur.fetchone()
                run_id = r["id"] if r else None
            if run_id is not None:
                # Events seen only on this flight go; events also seen on other flights stay.
                cur.execute(
                    """
                    SELECT e.event_id FROM events e
                    WHERE (e.run_id = %s
                           OR EXISTS (SELECT 1 FROM observations o WHERE o.event_id = e.event_id AND o.run_id = %s))
                      AND NOT EXISTS (SELECT 1 FROM observations o WHERE o.event_id = e.event_id AND o.run_id <> %s)
                    """,
                    (run_id, run_id, run_id),
                )
                events_deleted = [r["event_id"] for r in cur.fetchall()]
                cur.execute(
                    "SELECT object_key FROM event_media WHERE event_id = ANY(%s) AND object_key IS NOT NULL",
                    (events_deleted,),
                )
                keys = [r["object_key"] for r in cur.fetchall()]
                cur.execute("DELETE FROM events WHERE event_id = ANY(%s)", (events_deleted,))
                cur.execute("DELETE FROM observations WHERE run_id = %s", (run_id,))
                cur.execute("UPDATE events SET run_id = NULL WHERE run_id = %s", (run_id,))
                cur.execute("DELETE FROM runs WHERE id = %s", (run_id,))
            else:
                keys = []
            cur.execute("DELETE FROM edge_video_uploads WHERE upload_id = %s", (upload_id,))
        store._commit(conn)
    files += sum(_store_delete(k) for k in keys)
    work = get_settings().edge_upload_dir / "analyze" / upload_id
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(get_settings().edge_upload_dir / "flights" / upload_id, ignore_errors=True)
    return {"deleted": True, "events_deleted": len(events_deleted), "files_deleted": files}


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
