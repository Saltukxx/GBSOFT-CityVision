#!/usr/bin/env python3
"""Create a tiny synthetic MP4 for smoke tests (no real street footage required)."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="data/samples/smoke.mp4")
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--size", type=int, default=640)
    args = p.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, 15.0, (args.size, args.size))

    for i in range(args.frames):
        frame = np.zeros((args.size, args.size, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)
        # Moving rectangle — not a real vehicle; only validates I/O path.
        x = 40 + (i * 6) % (args.size - 160)
        cv2.rectangle(frame, (x, 220), (x + 120, 300), (0, 180, 255), -1)
        cv2.putText(
            frame,
            f"smoke {i}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
        )
        writer.write(frame)

    writer.release()
    print(f"Wrote {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
