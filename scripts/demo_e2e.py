#!/usr/bin/env python3
"""One-command demo: seed → simulate → ingest (+ cross-run merge) → optional API hint."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip().strip('"').strip("'")


def _run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *args]
    print(f"+ {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT))


def _write_cross_run(src: Path, dest: Path) -> Path:
    """Clone a run with new event_ids so ingest triggers spatial merge."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    events_path = dest / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            continue
        old = str(ev.get("event_id") or f"EVT-{i}")
        # Keep type/coords; change id + add another vehicle sighting
        prefix = old.split("-")[0] if "-" in old else "EVT"
        ev["event_id"] = f"{prefix}-X{i+1:04d}"
        vids = list(ev.get("vehicle_ids") or [])
        if "BUS-17" not in vids:
            vids.append("BUS-17")
        ev["vehicle_ids"] = vids
        ev["vehicle_id"] = "BUS-17"
        ev["observations"] = int(ev.get("observations") or 1)
        # Point evidence at clone dir if present
        ed = ev.get("evidence_dir")
        if ed:
            old_ed = Path(ed)
            if old_ed.name and (dest / "evidence" / old_ed.name).exists():
                ev["evidence_dir"] = str((dest / "evidence" / old_ed.name).resolve())
            elif (src / "evidence").exists():
                # evidence folders keyed by event id — remap if possible
                pass
    events_path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_path = dest / "summary.json"
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["vehicle_id"] = "BUS-17"
    summary["note"] = "cross-run clone for spatial merge demo"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="City Vision end-to-end demo loop")
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--skip-simulate", action="store_true")
    parser.add_argument("--skip-merge-demo", action="store_true", help="Only ingest one run")
    parser.add_argument("--serve", action="store_true", help="Start API after ingest")
    args = parser.parse_args()

    _load_env()
    from cityvision.db.store import Store
    from cityvision.settings import get_settings

    get_settings.cache_clear()
    store = Store()
    if not store.ping():
        print("ERROR: PostgreSQL/PostGIS not reachable. Start docker compose db first.", file=sys.stderr)
        return 1

    if not args.skip_seed:
        _run("seed_backend.py")
    if not args.skip_simulate:
        _run("simulate_events_demo.py")

    run1 = ROOT / "outputs" / "simulate_001"
    if not (run1 / "events.json").exists():
        print(f"ERROR: missing {run1 / 'events.json'}", file=sys.stderr)
        return 1

    from cityvision.db.ingest import ingest_run_dir

    print("\n=== Ingest run 1 ===")
    r1 = ingest_run_dir(run1, store=store)
    print(json.dumps({k: r1[k] for k in ("run_id", "events_created", "events_merged", "events_ingested")}, indent=2))

    r2 = None
    if not args.skip_merge_demo:
        run2 = _write_cross_run(run1, ROOT / "outputs" / "simulate_002_merge")
        print("\n=== Ingest run 2 (cross-run merge) ===")
        r2 = ingest_run_dir(run2, store=store)
        print(
            json.dumps(
                {
                    "run_id": r2["run_id"],
                    "events_created": r2["events_created"],
                    "events_merged": r2["events_merged"],
                    "merges": r2["merges"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    kpis = store.kpis()
    print("\n=== KPIs ===")
    print(json.dumps(kpis, indent=2, ensure_ascii=False, default=str))

    settings = get_settings()
    url = f"http://{settings.api_host}:{settings.api_port}/"
    print(f"\nDashboard: {url}")
    print("Login (if auth on): operator / operator")

    if args.serve:
        print("\nStarting API…")
        os.execv(
            sys.executable,
            [sys.executable, str(ROOT / "scripts" / "serve_api.py")],
        )

    print("\nNext: python scripts/serve_api.py")
    return 0 if (r2 is None or r2.get("events_merged", 0) > 0 or args.skip_merge_demo) else 0


if __name__ == "__main__":
    raise SystemExit(main())
