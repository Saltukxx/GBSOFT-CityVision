"""Dump gated-out municipal detections as labeling candidates."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import cv2

from cityvision.pipeline.annotate import draw_detections
from cityvision.pipeline.types import Detection

RejectedItem = Tuple[Detection, str]


def _dedupe(
    items: Sequence[RejectedItem],
    *,
    max_samples: int,
    min_spacing_frames: int,
) -> List[RejectedItem]:
    ranked = sorted(items, key=lambda pair: float(pair[0].confidence), reverse=True)
    kept: List[RejectedItem] = []
    seen: set[tuple[str, str, int]] = set()
    for det, reason in ranked:
        bucket = det.frame // max(1, min_spacing_frames)
        key = (reason, det.class_name, bucket)
        if key in seen:
            continue
        seen.add(key)
        kept.append((det, reason))
        if len(kept) >= max_samples:
            break
    return kept


def write_rejected_samples(
    source_video: str | Path,
    rejected: Sequence[RejectedItem],
    output_dir: str | Path,
    *,
    max_samples: int = 200,
    min_spacing_frames: int = 15,
) -> Dict[str, Any]:
    """
    Write boxed frames + crops for detections that did not become events.

    Layout:
      rejected/index.jsonl
      rejected/frames/{i}_{class}_{reason}.jpg
      rejected/crops/{i}_{class}_{reason}.jpg
    """
    dest = Path(output_dir) / "rejected"
    dest.mkdir(parents=True, exist_ok=True)
    frames_dir = dest / "frames"
    crops_dir = dest / "crops"
    frames_dir.mkdir(exist_ok=True)
    crops_dir.mkdir(exist_ok=True)

    picked = _dedupe(
        rejected, max_samples=max_samples, min_spacing_frames=min_spacing_frames
    )
    if not picked:
        summary = {"count": 0, "reasons": {}, "written": 0}
        (dest / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        return summary

    cap = cv2.VideoCapture(str(source_video))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    index_path = dest / "index.jsonl"
    written = 0
    reasons: Counter[str] = Counter()

    with index_path.open("w", encoding="utf-8") as fh:
        for i, (det, reason) in enumerate(picked, start=1):
            reasons[reason] += 1
            cap.set(cv2.CAP_PROP_POS_FRAMES, float(det.frame))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            safe_cls = det.class_name.replace("/", "_")
            stem = f"{i:04d}_{safe_cls}_{reason}_f{det.frame}"
            marked = draw_detections(frame, [det], hud_lines=[reason])
            frame_path = frames_dir / f"{stem}.jpg"
            cv2.imwrite(str(frame_path), marked)
            crop_rel = None
            if det.bbox_xyxy:
                x1, y1, x2, y2 = (int(v) for v in det.bbox_xyxy)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(max(width - 1, 1), x2), min(max(height - 1, 1), y2)
                if x2 > x1 and y2 > y1:
                    crop_path = crops_dir / f"{stem}.jpg"
                    cv2.imwrite(str(crop_path), frame[y1:y2, x1:x2])
                    crop_rel = str(crop_path.relative_to(dest))
            row = {
                **det.to_dict(),
                "reason": reason,
                "frame_jpg": str(frame_path.relative_to(dest)),
                "crop_jpg": crop_rel,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1

    cap.release()
    summary = {
        "count": len(rejected),
        "written": written,
        "reasons": dict(reasons),
    }
    (dest / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary
