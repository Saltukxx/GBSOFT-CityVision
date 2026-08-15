from pathlib import Path

import cv2
import numpy as np

from cityvision.events.rejected import write_rejected_samples
from cityvision.pipeline.types import Detection


def test_write_rejected_samples(tmp_path):
    video = tmp_path / "src.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 80))
    for _ in range(5):
        writer.write(np.zeros((80, 80, 3), dtype=np.uint8))
    writer.release()

    det = Detection(1, 100, "pothole", 0.91, (10, 10, 40, 40))
    summary = write_rejected_samples(
        video,
        [(det, "outside_roi")],
        tmp_path,
        max_samples=10,
        min_spacing_frames=1,
    )
    assert summary["written"] == 1
    assert summary["reasons"]["outside_roi"] == 1
    dest = Path(tmp_path) / "rejected"
    assert (dest / "index.jsonl").exists()
    assert list((dest / "frames").glob("*.jpg"))
    assert list((dest / "crops").glob("*.jpg"))
