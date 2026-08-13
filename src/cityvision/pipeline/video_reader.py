from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class FrameBatch:
    index: int
    timestamp_ms: float
    image: np.ndarray


class VideoReader:
    def __init__(self, source: str | Path, stride: int = 1, max_frames: int | None = None):
        self.source = str(source)
        self.stride = max(1, stride)
        self.max_frames = max_frames
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {self.source}")

        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 25.0)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    def __iter__(self) -> Iterator[FrameBatch]:
        idx = 0
        emitted = 0
        while True:
            ok, frame = self.cap.read()
            if not ok:
                break
            if idx % self.stride == 0:
                ts = (idx / self.fps) * 1000.0 if self.fps > 0 else float(idx)
                yield FrameBatch(index=idx, timestamp_ms=ts, image=frame)
                emitted += 1
                if self.max_frames is not None and emitted >= self.max_frames:
                    break
            idx += 1

    def close(self) -> None:
        self.cap.release()

    def __enter__(self) -> VideoReader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
