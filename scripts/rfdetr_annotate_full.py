#!/usr/bin/env python3
"""Run RF-DETR every STRIDE frames and linearly interpolate boxes for the frames
in between (matched by class + IoU), instead of running inference on literally
every frame. Newly-appeared/disappeared objects show up exactly at their real
detected frame (no static "stuck" boxes, no premature ghosting) while tracked
objects get smooth interpolated motion between real detections.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
from PIL import Image
from rfdetr import RFDETRMedium

CKPT = "models/rfdetr/rfdetr-v2-1280-ema.pth"
NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
CONF = 0.3
OUT_SCALE = 0.5
STRIDE = 3  # run real inference every STRIDE frames; interpolate in between

COLORS = {  # BGR
    "pothole": (0, 0, 255),
    "road_crack": (0, 255, 0),
    "manhole": (0, 165, 255),
    "road_damage": (255, 0, 255),
}

SOURCE = "/Users/saltuk/Downloads/18 Ağustos Salı 8. Video "
OUT = "outputs/rfdetr_annotated/aug18_v8_v2model_full_annotated.mp4"


def to_dets(dets) -> list[dict]:
    out = []
    for box, cls_id, conf in zip(dets.xyxy, dets.class_id, dets.confidence):
        out.append({"cls": NAMES.get(int(cls_id), str(cls_id)), "box": [float(v) for v in box], "conf": float(conf)})
    return out


def iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / (area_a + area_b - inter)


def match(prev: list[dict], cur: list[dict]) -> list[tuple[int | None, int | None]]:
    used_cur: set[int] = set()
    pairs: list[tuple[int | None, int | None]] = []
    for i, p in enumerate(prev):
        best_j, best_iou = None, 0.1  # threshold
        for j, c in enumerate(cur):
            if j in used_cur or c["cls"] != p["cls"]:
                continue
            v = iou(p["box"], c["box"])
            if v > best_iou:
                best_iou, best_j = v, j
        if best_j is not None:
            pairs.append((i, best_j))
            used_cur.add(best_j)
        else:
            pairs.append((i, None))
    for j in range(len(cur)):
        if j not in used_cur:
            pairs.append((None, j))
    return pairs


def draw(frame, cls: str, box: list[float], conf: float) -> None:
    x0, y0, x1, y1 = [int(v * OUT_SCALE) for v in box]
    color = COLORS.get(cls, (255, 255, 255))
    cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)
    cv2.putText(frame, f"{cls} {conf:.2f}", (x0, max(15, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def main() -> None:
    model = RFDETRMedium(pretrain_weights=CKPT, resolution=1280)

    cap = cv2.VideoCapture(SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * OUT_SCALE)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * OUT_SCALE)

    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUT, fourcc, fps, (w, h))

    t0 = time.time()
    frame_idx = 0
    n_infer = 0
    n_dets = 0
    buffer: list[tuple[int, "cv2.Mat"]] = []
    prev_dets: list[dict] | None = None
    prev_sample_idx = 0

    def run_infer(frame) -> list[dict]:
        nonlocal n_infer
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        dets = model.predict(Image.fromarray(rgb), threshold=CONF)
        n_infer += 1
        return to_dets(dets)

    def flush(cur_dets: list[dict]) -> None:
        nonlocal n_dets
        pairs = match(prev_dets, cur_dets) if prev_dets is not None else []
        span = buffer[-1][0] - prev_sample_idx if buffer else STRIDE
        for fidx, frame in buffer:
            t = (fidx - prev_sample_idx) / span if span else 0.0
            out_frame = cv2.resize(frame, (w, h))
            if t == 0.0 and prev_dets is not None:
                for d in prev_dets:
                    draw(out_frame, d["cls"], d["box"], d["conf"])
                    n_dets += 1
            else:
                for pi, ci in pairs:
                    if pi is not None and ci is not None:
                        p, c = prev_dets[pi], cur_dets[ci]
                        box = [p["box"][k] * (1 - t) + c["box"][k] * t for k in range(4)]
                        conf = p["conf"] * (1 - t) + c["conf"] * t
                        draw(out_frame, p["cls"], box, conf)
                        n_dets += 1
            writer.write(out_frame)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        buffer.append((frame_idx, frame))
        if frame_idx % STRIDE == 0:
            cur_dets = run_infer(frame)
            if prev_dets is not None:
                flush(cur_dets)
            buffer = [(frame_idx, frame)]
            prev_dets = cur_dets
            prev_sample_idx = frame_idx
            if n_infer % 200 == 0:
                elapsed = time.time() - t0
                eta = elapsed / (frame_idx + 1) * (total - frame_idx - 1)
                print(f"{frame_idx}/{total} frames, {n_infer} infer calls, {elapsed:.0f}s elapsed, ETA {eta:.0f}s, dets so far={n_dets}", flush=True)
        frame_idx += 1

    # tail: leftover buffered frames after the last sample point, hold last dets statically
    for fidx, frame in buffer:
        out_frame = cv2.resize(frame, (w, h))
        if prev_dets:
            for d in prev_dets:
                draw(out_frame, d["cls"], d["box"], d["conf"])
                n_dets += 1
        writer.write(out_frame)

    cap.release()
    writer.release()
    print(f"DONE -> {OUT} ({time.time()-t0:.0f}s, {n_infer} inference calls, {n_dets} boxes drawn)")


if __name__ == "__main__":
    main()
