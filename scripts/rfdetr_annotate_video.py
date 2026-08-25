#!/usr/bin/env python3
"""Render annotated videos from cached RF-DETR detections (outputs/rfdetr_aug21_results.json).
Each detection (sampled at 1fps) is held visible for the full ~1s window so playback at
normal speed is watchable, without re-running inference.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import cv2

RESULTS = Path("outputs/rfdetr_aug21_results.json")
OUT_DIR = Path("outputs/rfdetr_annotated")
OUT_SCALE = 0.5  # 3840x2160 -> 1920x1080, keeps encode time/file size sane

COLORS = {  # BGR
    "pothole": (0, 0, 255),
    "road_crack": (0, 255, 0),
    "manhole": (0, 165, 255),
    "road_damage": (255, 0, 255),
}

VIDEOS = {
    "aug21_v2": "/Users/saltuk/Downloads/21 AGU 2.MP4",
    "aug21_v3": "/Users/saltuk/Downloads/21 AGU 3.MP4",
    "aug21_v4": "/Users/saltuk/Downloads/21 AGU 4.MP4",
    "aug21_v5": "/Users/saltuk/Downloads/21 AGU 5.MP4",
    "aug21_v6": "/Users/saltuk/Downloads/21 AGU 6.MP4",
}


def main() -> None:
    dets = json.loads(RESULTS.read_text())
    by_video: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for d in dets:
        by_video[d["video"]][d["frame_idx"]].append(d)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for tag, path in VIDEOS.items():
        p = Path(path)
        if not p.exists():
            print(f"skip {tag}: not found")
            continue
        cap = cv2.VideoCapture(str(p))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = int(round(fps))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * OUT_SCALE)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * OUT_SCALE)
        out_path = OUT_DIR / f"{tag}_annotated.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

        sample_frames = sorted(by_video[tag].keys())
        active = []  # current window's detections
        next_sample_idx = 0
        t0 = time.time()
        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if next_sample_idx < len(sample_frames) and frame_idx == sample_frames[next_sample_idx]:
                active = by_video[tag][frame_idx]
                next_sample_idx += 1
            frame = cv2.resize(frame, (w, h))
            for d in active:
                x0, y0, x1, y1 = [int(v * OUT_SCALE) for v in d["bbox_xyxy"]]
                color = COLORS.get(d["class"], (255, 255, 255))
                cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)
                label = f"{d['class']} {d['confidence']:.2f}"
                cv2.putText(frame, label, (x0, max(15, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            writer.write(frame)
            frame_idx += 1
            if frame_idx % 900 == 0:
                print(f"{tag}: {frame_idx} frames, {time.time()-t0:.0f}s", flush=True)
        cap.release()
        writer.release()
        print(f"{tag}: done -> {out_path} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
