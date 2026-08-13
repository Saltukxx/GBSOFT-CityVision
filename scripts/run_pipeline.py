#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.cli import main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0] not in {"run", "review", "summary"}:
        argv = ["run", *argv]
    raise SystemExit(main(argv))
