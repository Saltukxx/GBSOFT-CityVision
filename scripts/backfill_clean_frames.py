#!/usr/bin/env python3
"""Recover clean (box-free) evidence frames for events processed before
`frame_clean.jpg` existed, so they can be labelled for training.

The evidence clip starts `seconds_before` before the detection frame and is
written without boxes, so the detection frame sits at a known offset inside it:
    offset = min(sample_frame, int(seconds_before * fps))

    .venv/bin/python scripts/backfill_clean_frames.py --dry-run
    .venv/bin/python scripts/backfill_clean_frames.py --city erzurum
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cv2  # noqa: E402

from cityvision.config import load_pipeline_config  # noqa: E402
from cityvision.db.store import Store  # noqa: E402
from cityvision.labelling import _open_media, latest_evidence_set  # noqa: E402
from cityvision.storage import get_object_store  # noqa: E402
from cityvision.tenant import TENANT_ALL, set_tenant_city  # noqa: E402


def events_missing_frames(store: Store, city: str | None) -> list[dict]:
    sql = """
        SELECT e.event_id, e.city_id FROM events e
        WHERE EXISTS (SELECT 1 FROM event_media m WHERE m.event_id = e.event_id AND m.media_type = 'clip')
          AND EXISTS (SELECT 1 FROM event_media m WHERE m.event_id = e.event_id AND m.media_type = 'json')
          AND NOT EXISTS (SELECT 1 FROM event_media m WHERE m.event_id = e.event_id AND m.media_type = 'frame')
    """
    args: list = []
    if city:
        sql += " AND e.city_id = %s"
        args.append(city)
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql + " ORDER BY e.event_id", args)
            return [dict(r) for r in cur.fetchall()]


def local_copy(row: dict, workdir: Path, name: str) -> Path | None:
    """Read via the same route the app uses (storage first), so what we pair is what it serves."""
    fh = _open_media(row)
    if fh is None:
        return None
    dest = workdir / name
    with fh, dest.open("wb") as out:
        out.write(fh.read())
    return dest


def recover(store: Store, event_id: str, seconds_before: float, workdir: Path, dry_run: bool) -> str:
    # Clip and JSON must come from the same run, or the box won't match the frame.
    group = latest_evidence_set(store.list_event_media(event_id), ("clip", "json"))
    if not group:
        return "no run with both clip and json"
    clip, meta_row = group["clip"], group["json"]
    meta_path = local_copy(meta_row, workdir, f"{event_id}.json")
    if meta_path is None:
        return "json missing"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sample_frame = meta.get("sample_frame")
    if sample_frame is None:
        return "no sample_frame"
    clip_path = local_copy(clip, workdir, f"{event_id}.mp4")
    if clip_path is None:
        return "clip missing"

    cap = cv2.VideoCapture(str(clip_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if fps <= 0:
        return "unreadable clip"
    offset = min(int(sample_frame), int(seconds_before * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, offset)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return "frame not found in clip"
    bbox = meta.get("sample_bbox") or []
    h, w = frame.shape[:2]
    if len(bbox) >= 4 and (bbox[2] > w + 1 or bbox[3] > h + 1):
        return f"box outside {w}x{h} frame"
    if dry_run:
        return f"ok (frame {offset} of clip, {w}x{h})"

    out = workdir / f"{event_id}-frame_clean.jpg"
    cv2.imwrite(str(out), frame)
    # Store next to the clip it came from so frame, clip and JSON stay one set.
    key_dir = str(Path(str(clip.get("object_key") or f"evidence/{event_id}/x")).parent)
    key = f"{key_dir}/frame_clean.jpg"
    get_object_store().put_file(key, out)
    path_dir = Path(str(clip.get("path") or key)).parent
    store.upsert_event_media(
        event_id, "frame", str(path_dir / "frame_clean.jpg"), content_type="image/jpeg",
        nbytes=out.stat().st_size, object_key=key,
    )
    return "recovered"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--city", help="Only this city")
    ap.add_argument("--seconds-before", type=float, help="Override evidence.seconds_before")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    set_tenant_city(TENANT_ALL)
    store = Store()
    rows = events_missing_frames(store, args.city)
    print(f"{len(rows)} event(s) without a clean frame")
    results: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for row in rows:
            seconds = args.seconds_before
            if seconds is None:
                cfg = load_pipeline_config(city_id=row.get("city_id"))
                seconds = float((cfg.get("evidence") or {}).get("seconds_before", 5))
            try:
                outcome = recover(store, row["event_id"], seconds, Path(tmp), args.dry_run)
            except Exception as exc:  # noqa: BLE001 — report and continue
                outcome = f"error: {exc}"
            print(f"  {row['event_id']}: {outcome}")
            bucket = outcome.split(" (")[0].split(":")[0]
            results[bucket] = results.get(bucket, 0) + 1
    print("summary:", ", ".join(f"{k}={v}" for k, v in sorted(results.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
