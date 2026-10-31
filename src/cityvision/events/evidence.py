from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence

import cv2
import numpy as np

from cityvision.pipeline.annotate import draw_detections
from cityvision.pipeline.types import Detection, MunicipalEvent


def _read_frame_at(cap: cv2.VideoCapture, frame_idx: int) -> Optional[np.ndarray]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


def write_evidence_packs(
    source_video: str | Path,
    events: Sequence[MunicipalEvent],
    output_dir: str | Path,
    fps: float,
    seconds_before: float = 5.0,
    seconds_after: float = 5.0,
    save_full_frame: bool = True,
    save_crop: bool = True,
    save_clips: bool = True,
    max_events: int = 50,
    draw_boxes: bool = True,
) -> List[MunicipalEvent]:
    out = Path(output_dir) / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source_video))
    if not cap.isOpened():
        return list(events)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = fps if fps > 0 else 25.0

    updated: List[MunicipalEvent] = []
    for event in list(events)[:max_events]:
        if event.confidence_band == "discard":
            updated.append(event)
            continue
        if event.sample_frame is None:
            updated.append(event)
            continue

        ed = out / event.event_id
        ed.mkdir(parents=True, exist_ok=True)
        event.evidence_dir = str(ed)

        frame = _read_frame_at(cap, int(event.sample_frame))
        if frame is not None:
            if save_full_frame:
                still = frame
                if draw_boxes and event.sample_bbox:
                    x1, y1, x2, y2 = (float(v) for v in event.sample_bbox[:4])
                    still = draw_detections(
                        frame,
                        [
                            Detection(
                                frame=int(event.sample_frame),
                                timestamp_ms=event.last_seen_ms,
                                class_name=event.type,
                                confidence=float(event.confidence),
                                bbox_xyxy=(x1, y1, x2, y2),
                            )
                        ],
                    )
                cv2.imwrite(str(ed / "event.jpg"), still)
                if still is not frame:
                    # Unannotated copy for training: a drawn box in a training image
                    # would teach the model to find our own rectangle.
                    cv2.imwrite(str(ed / "frame_clean.jpg"), frame)
            if save_crop and event.sample_bbox:
                x1, y1, x2, y2 = [int(v) for v in event.sample_bbox]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(width - 1, x2), min(height - 1, y2)
                if x2 > x1 and y2 > y1:
                    crop = frame[y1:y2, x1:x2]
                    cv2.imwrite(str(ed / "object_crop.jpg"), crop)

        if save_clips:
            start = max(0, int(event.sample_frame - seconds_before * fps))
            end = int(event.sample_frame + seconds_after * fps)
            clip_path = ed / "event.mp4"
            writer = cv2.VideoWriter(str(clip_path), fourcc, fps, (width, height))
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            for _ in range(start, end + 1):
                ok, fr = cap.read()
                if not ok:
                    break
                writer.write(fr)
            writer.release()

        (ed / "event.json").write_text(
            json.dumps(event.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        updated.append(event)

    # append remaining without evidence if truncated
    if len(events) > max_events:
        updated.extend(list(events)[max_events:])

    cap.release()
    return updated
