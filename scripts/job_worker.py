#!/usr/bin/env python3
"""Redis job worker for City Vision backend.

Requires: docker compose --profile redis up -d
Fallback without Redis: API runs jobs in-process threads.
"""

from __future__ import annotations

import logging
import os
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
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def main() -> int:
    _load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from cityvision.workers.jobs import redis_worker_loop, startup_reclaim

    # Always reclaim on process start (even before Redis loop connects details)
    startup_reclaim(older_than_minutes=30)
    redis_worker_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
