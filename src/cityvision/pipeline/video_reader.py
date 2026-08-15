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
    def __init__(
        self,
        source: str | Path,
        stride: int = 1,
        max_frames: int | None = None,
        start_sec: float = 0.0,
        duration_sec: float | None = None,
    ):
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
        self.start_frame = max(0, int(float(start_sec) * self.fps)) if start_sec else 0
        if self.frame_count > 0:
            self.start_frame = min(self.start_frame, max(0, self.frame_count - 1))
        if duration_sec is not None:
            span = max(0, int(float(duration_sec) * self.fps))
            self.end_frame: int | None = self.start_frame + span
        else:
            self.end_frame = None

    def planned_emits(self) -> int | None:
        """How many frames this iterator will yield (for progress bars)."""
        end = self.end_frame if self.end_frame is not None else self.frame_count
        if end <= 0:
            return None
        first = self.start_frame
        if first % self.stride:
            first += self.stride - (first % self.stride)
        if first >= end:
            return 0
        count = ((end - 1 - first) // self.stride) + 1
        if self.max_frames is not None:
            count = min(count, int(self.max_frames))
        return count

    def __iter__(self) -> Iterator[FrameBatch]:
        idx = self.start_frame
        if self.start_frame > 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, float(self.start_frame))
        emitted = 0
        while True:
            if self.end_frame is not None and idx >= self.end_frame:
                break
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
