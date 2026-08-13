from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import cv2
import numpy as np

from cityvision.pipeline.types import Detection

_COLORS = [
    (40, 180, 99),
    (52, 152, 219),
    (231, 76, 60),
    (241, 196, 15),
    (155, 89, 182),
    (26, 188, 156),
    (230, 126, 34),
]


def _color_for(name: str) -> Tuple[int, int, int]:
    return _COLORS[hash(name) % len(_COLORS)]


def draw_detections(
    frame: np.ndarray,
    detections: Sequence[Detection],
    line_y: Optional[float] = None,
    hud_lines: Optional[Iterable[str]] = None,
) -> np.ndarray:
    out = frame.copy()
    if line_y is not None:
        y = int(line_y)
        cv2.line(out, (0, y), (out.shape[1] - 1, y), (0, 255, 255), 1, cv2.LINE_AA)

    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det.bbox_xyxy)
        color = _color_for(det.class_name)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        if det.track_id is not None:
            label = f"#{det.track_id} {label}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            out,
            label,
            (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    if hud_lines:
        y = 24
        for line in hud_lines:
            cv2.putText(
                out,
                line,
                (12, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (20, 20, 20),
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                out,
                line,
                (12, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (240, 240, 240),
                1,
                cv2.LINE_AA,
            )
            y += 22
    return out
