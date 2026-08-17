#!/usr/bin/env python3
"""Build a YOLO aerial set from DJI frames + existing pipeline boxes.

Boxes come from prior run detections.jsonl. Class remap is the marking step:
RDD often wrote manhole covers as pothole — those windows become `manhole`.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.pipeline.manhole import box_iou

OUT = ROOT / "data" / "datasets" / "model_b_aerial"
CFG = ROOT / "configs" / "model_b_aerial.data.yaml"

NAMES = {0: "manhole", 1: "road_crack", 2: "road_damage"}
NAME_TO_ID = {v: k for k, v in NAMES.items()}

# (video, detections.jsonl, [(t0_ms, t1_ms, src_class, dst_class), ...])
JOBS = [
    (
        ROOT / "data/samples/dji_fly_20260816.mp4",
        ROOT / "outputs/dji_fly_20260816/detections.jsonl",
        [
            (147_000, 151_200, "pothole", "manhole"),
            (152_000, 155_000, "road_damage", "road_damage"),
        ],
    ),
    (
        ROOT / "data/samples/dji_fly_20260816_175412.mp4",
        ROOT / "outputs/dji_fly_20260816_175412/detections.jsonl",
        [
            (6_000, 9_000, "pothole", "manhole"),
        ],
    ),
    (
        ROOT / "data/samples/dji_fly_20260816_181137.mp4",
        ROOT / "outputs/dji_fly_20260816_181137/detections.jsonl",
        [
            (0, 8_000, "road_crack", "road_crack"),
        ],
    ),
]


def _load_dets(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if "class" not in obj:
            continue
        rows.append(obj)
    return rows


def _nms(boxes: list[tuple[str, float, tuple[float, float, float, float]]], iou_thr: float = 0.45):
    kept: list[tuple[str, float, tuple[float, float, float, float]]] = []
    for cls in {b[0] for b in boxes}:
        group = sorted([b for b in boxes if b[0] == cls], key=lambda b: b[1], reverse=True)
        taken: list[tuple[str, float, tuple[float, float, float, float]]] = []
        for cand in group:
            if any(box_iou(cand[2], t[2]) >= iou_thr for t in taken):
                continue
            taken.append(cand)
        kept.extend(taken)
    return kept


def _xyxy_to_yolo(box: tuple[float, float, float, float], w: int, h: int) -> str:
    x1, y1, x2, y2 = box
    x1, x2 = max(0.0, min(w, x1)), max(0.0, min(w, x2))
    y1, y2 = max(0.0, min(h, y1)), max(0.0, min(h, y2))
    bw, bh = x2 - x1, y2 - y1
    if bw <= 1 or bh <= 1:
        return ""
    xc = (x1 + x2) / 2.0 / w
    yc = (y1 + y2) / 2.0 / h
    return f"{xc:.6f} {yc:.6f} {bw / w:.6f} {bh / h:.6f}"


def _export_job(video: Path, jsonl: Path, windows: list[tuple[int, int, str, str]], split_mod: int = 5) -> dict[str, int]:
    stats = {"images": 0, "manhole": 0, "road_crack": 0, "road_damage": 0, "train": 0, "val": 0}
    if not video.exists() or not jsonl.exists():
        print(f"skip missing {video.name if video.exists() else video} / {jsonl}")
        return stats

    dets = _load_dets(jsonl)
    by_frame: dict[int, list[tuple[str, float, tuple[float, float, float, float]]]] = defaultdict(list)
    for d in dets:
        ts = float(d.get("timestamp_ms") or 0)
        src = d["class"]
        dst = None
        for t0, t1, want, mapped in windows:
            if t0 <= ts <= t1 and src == want:
                dst = mapped
                break
        if dst is None:
            continue
        box = tuple(float(x) for x in d["bbox_xyxy"])
        frame = int(d["frame"])
        by_frame[frame].append((dst, float(d.get("confidence") or 0), box))  # type: ignore[arg-type]

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {video}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
    stem_prefix = video.stem

    for i, frame_idx in enumerate(sorted(by_frame)):
        kept = _nms(by_frame[frame_idx])
        if not kept:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, image = cap.read()
        if not ok:
            continue
        split = "val" if i % split_mod == 0 else "train"
        name = f"{stem_prefix}_f{frame_idx:06d}"
        img_path = OUT / "images" / split / f"{name}.jpg"
        lbl_path = OUT / "labels" / split / f"{name}.txt"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        lbl_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(img_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        lines: list[str] = []
        for cls, _conf, box in kept:
            yolo = _xyxy_to_yolo(box, width, height)
            if not yolo:
                continue
            cid = NAME_TO_ID[cls]
            lines.append(f"{cid} {yolo}")
            stats[cls] += 1
        lbl_path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        stats["images"] += 1
        stats[split] += 1
    cap.release()
    return stats


def main() -> int:
    if OUT.exists():
        import shutil

        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True)
        (OUT / "labels" / split).mkdir(parents=True)

    totals: dict[str, int] = defaultdict(int)
    for video, jsonl, windows in JOBS:
        print(f"Export {video.name} …", flush=True)
        stats = _export_job(video, jsonl, windows)
        print(f"  {stats}", flush=True)
        for k, v in stats.items():
            totals[k] += v

    CFG.write_text(
        "path: data/datasets/model_b_aerial\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: manhole\n"
        "  1: road_crack\n"
        "  2: road_damage\n",
        encoding="utf-8",
    )
    (OUT / "README.md").write_text(
        "# Aerial DJI Model B (marked from pipeline boxes)\n\n"
        "RDD `pothole` boxes on known rögar covers were remapped to `manhole`. "
        "Alligator crack stays `road_damage`. Linear crack stays `road_crack`.\n\n"
        f"images={totals['images']} train={totals['train']} val={totals['val']} "
        f"manhole={totals['manhole']} crack={totals['road_crack']} damage={totals['road_damage']}\n",
        encoding="utf-8",
    )
    print(f"Done → {OUT}")
    print(dict(totals))
    print(
        "Train:\n"
        "  python scripts/train_model_b.py \\\n"
        "    --data configs/model_b_aerial.data.yaml --epochs 80 --device mps \\\n"
        "    --batch 8 --name train_aerial --no-val \\\n"
        "    --export-to models/infra-b-road-aerial.pt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
