#!/usr/bin/env python3
"""Run our fine-tuned RF-DETR (resolution=1280) over the new 21 Agustos videos,
locally, on MPS. Same 1fps sampling convention as the rest of the project.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
from PIL import Image
from rfdetr import RFDETRMedium

CKPT = "models/rfdetr/rfdetr-1280-epoch41.pth"
NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
CONF = 0.3

VIDEOS = {
    "aug21_v2": "/Users/saltuk/Downloads/21 AGU 2.MP4",
    "aug21_v3": "/Users/saltuk/Downloads/21 AGU 3.MP4",
    "aug21_v4": "/Users/saltuk/Downloads/21 AGU 4.MP4",
    "aug21_v5": "/Users/saltuk/Downloads/21 AGU 5.MP4",
    "aug21_v6": "/Users/saltuk/Downloads/21 AGU 6.MP4",
}


def main() -> None:
    model = RFDETRMedium(pretrain_weights=CKPT, resolution=1280)
    results = []
    t_start = time.time()
    for tag, path in VIDEOS.items():
        p = Path(path)
        if not p.exists():
            print(f"skip {tag}: {path} not found")
            continue
        cap = cv2.VideoCapture(str(p))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = int(round(fps))
        frame_idx = 0
        n = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                dets = model.predict(img, threshold=CONF)
                for box, cls_id, conf in zip(dets.xyxy, dets.class_id, dets.confidence):
                    results.append(
                        {
                            "video": tag,
                            "frame_idx": frame_idx,
                            "timestamp_ms": frame_idx / fps * 1000,
                            "class": NAMES.get(int(cls_id), str(cls_id)),
                            "confidence": float(conf),
                            "bbox_xyxy": [float(x) for x in box],
                        }
                    )
                n += 1
                if n % 30 == 0:
                    elapsed = time.time() - t_start
                    print(f"{tag}: {n} sampled frames, {elapsed:.0f}s elapsed", flush=True)
            frame_idx += 1
        cap.release()
        print(f"{tag}: done, {n} frames sampled")

    out = Path("outputs/rfdetr_aug21_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    by_cls: dict[str, int] = {}
    for r in results:
        by_cls[r["class"]] = by_cls.get(r["class"], 0) + 1
    print(f"Wrote {len(results)} detections -> {out}")
    print("Class counts:", by_cls)
    print(f"Total time: {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
