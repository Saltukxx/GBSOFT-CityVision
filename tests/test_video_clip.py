"""Clip window on VideoReader + CLI flags."""

from pathlib import Path

import cv2
import numpy as np

from cityvision.cli import build_parser
from cityvision.pipeline.video_reader import VideoReader


def _tiny_video(path: Path, n: int = 30, fps: float = 10.0) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 64))
    for i in range(n):
        writer.write(np.full((64, 64, 3), i % 255, dtype=np.uint8))
    writer.release()


def test_video_reader_start_and_duration(tmp_path):
    path = tmp_path / "clip.mp4"
    _tiny_video(path)
    with VideoReader(path, start_sec=1.0, duration_sec=1.0, stride=1) as reader:
        batches = list(reader)
        planned = reader.planned_emits()
    assert planned is None or 8 <= planned <= 12
    assert len(batches) >= 8
    assert batches[0].index >= 8
    assert batches[-1].index < 22
    assert batches[0].timestamp_ms >= 700


def test_cli_clip_flags():
    args = build_parser().parse_args(
        [
            "run",
            "--source",
            "a.mp4",
            "--output",
            "out",
            "--start-sec",
            "12.5",
            "--duration",
            "30",
            "--stride",
            "2",
        ]
    )
    assert args.start_sec == 12.5
    assert args.duration == 30.0
    assert args.stride == 2
