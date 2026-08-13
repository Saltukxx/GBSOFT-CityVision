#!/usr/bin/env python3
"""Start City Vision FastAPI (PostgreSQL-backed)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve City Vision API + operator dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    # Load DATABASE_URL from .env if present (without printing secrets)
    env_path = ROOT / ".env"
    if env_path.exists() and not os.environ.get("DATABASE_URL"):
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and len(line) > 13:
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    import uvicorn

    uvicorn.run(
        "cityvision.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
