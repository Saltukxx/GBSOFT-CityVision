#!/usr/bin/env python3
"""Ingest a pipeline output directory into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Pipeline output folder containing events.json")
    args = parser.parse_args()

    env_path = ROOT / ".env"
    if env_path.exists() and not os.environ.get("DATABASE_URL"):
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and len(line) > 13:
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    from cityvision.db.ingest import ingest_run_dir

    result = ingest_run_dir(args.run_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
