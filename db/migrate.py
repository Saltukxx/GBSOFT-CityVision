#!/usr/bin/env python3
"""Apply SQL migrations to City Vision PostgreSQL."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_DIR = ROOT / "db" / "init"


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and len(line) > 13:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "postgresql://cityvision:cityvision@localhost:5435/cityvision"


def main() -> int:
    import psycopg

    url = _database_url()
    print(f"Connecting… host from URL (password hidden)")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            for sql_path in sorted(INIT_DIR.glob("*.sql")):
                print(f"Applying {sql_path.name}")
                cur.execute(sql_path.read_text(encoding="utf-8"))
        conn.commit()
    print("Migrations OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
