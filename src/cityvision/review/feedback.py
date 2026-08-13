from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

LABEL_TO_STATUS = {
    "correct": "confirmed",
    "wrong": "false_positive",
    "work_order": "work_order_created",
    "resolved": "resolved",
}


def review_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "review_feedback.jsonl"


def append_feedback(
    output_dir: str | Path,
    event_id: str,
    label: str,
    note: str = "",
    reviewer: str = "operator",
) -> Path:
    if label not in LABEL_TO_STATUS:
        raise ValueError("label must be correct|wrong|work_order|resolved")
    path = review_path(output_dir)
    row = {
        "event_id": event_id,
        "label": label,
        "note": note,
        "reviewer": reviewer,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def load_feedback(output_dir: str | Path) -> List[Dict[str, Any]]:
    path = review_path(output_dir)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def apply_feedback_to_events(events_path: str | Path, output_dir: str | Path) -> Optional[Path]:
    """Update events.json statuses from human feedback (active learning loop input)."""
    events_path = Path(events_path)
    if not events_path.exists():
        return None
    events = json.loads(events_path.read_text(encoding="utf-8"))
    fb = {r["event_id"]: r for r in load_feedback(output_dir)}
    for ev in events:
        row = fb.get(ev.get("event_id"))
        if not row:
            continue
        label = row["label"]
        if label in LABEL_TO_STATUS:
            ev["status"] = LABEL_TO_STATUS[label]
        ev["review"] = row
    events_path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return events_path


def apply_feedback_to_db(
    event_id: str,
    label: str,
    note: str = "",
    reviewer: str = "operator",
    unit: str = "ops",
    store: Any = None,
) -> Dict[str, Any]:
    """Write review into PostgreSQL and update event status."""
    from cityvision.db.store import Store

    if label not in LABEL_TO_STATUS:
        raise ValueError("label must be correct|wrong|work_order|resolved")
    db = store or Store()
    return db.add_review(
        event_id=event_id,
        label=label,
        note=note,
        reviewer=reviewer,
        source="cli",
        unit=unit,
    )


def sync_jsonl_feedback_to_db(output_dir: str | Path, store: Any = None) -> Dict[str, Any]:
    """Replay review_feedback.jsonl into PostgreSQL (skips unknown events)."""
    from cityvision.db.store import Store

    db = store or Store()
    applied = 0
    skipped = 0
    errors: List[str] = []
    for row in load_feedback(output_dir):
        eid = row.get("event_id")
        label = row.get("label")
        if not eid or label not in LABEL_TO_STATUS:
            skipped += 1
            continue
        try:
            db.add_review(
                event_id=str(eid),
                label=str(label),
                note=str(row.get("note") or ""),
                reviewer=str(row.get("reviewer") or "operator"),
                source="jsonl",
            )
            applied += 1
        except KeyError:
            skipped += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{eid}: {exc}")
    return {"applied": applied, "skipped": skipped, "errors": errors}
