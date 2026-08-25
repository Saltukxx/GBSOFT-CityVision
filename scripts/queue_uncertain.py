#!/usr/bin/env python3
"""Rank unlabeled aerial frames for labeling (active learning).

Scores every frame in data/datasets/model_b_aerial/raw_frames with the current
Model B weights and writes priority.txt, highest value first. The browser labeler
(`scripts/label_aerial.py`) shows this order under the "öncelik" filter.

Signals, in order of weight:
  1. class disagreement — two weights claim different classes on the same box
  2. rare class candidate — anything that looks like road_crack / pothole
  3. uncertainty — detections inside the low-confidence band
Frames that look near-identical to an already labeled frame are demoted, so the
same intersection is not labeled ten times.

  .venv/bin/python scripts/queue_uncertain.py --device cpu
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cv2
import numpy as np

from cityvision.config import load_pipeline_config
from cityvision.pipeline.detector import YoloDetector
from cityvision.pipeline.manhole import box_iou
from cityvision.pipeline.model_resolve import resolve_model_b_paths
from cityvision.pipeline.types import Detection

DS = ROOT / "data" / "datasets" / "model_b_aerial"
FRAMES = DS / "raw_frames"
LABELS = DS / "labels_hand"
BACKGROUND = DS / "background.txt"
PRIORITY = DS / "priority.txt"
# Suggestions only — the labeler still needs a human B press, because a model that
# misses a manhole would otherwise teach itself that the manhole is not there.
BACKGROUND_CANDIDATES = DS / "background_candidates.txt"
REPORT = DS / "priority.json"

RARE_CLASSES = {"road_crack", "pothole"}
DUP_HAMMING = 4


def dhash(image: np.ndarray, size: int = 8) -> int:
    """64-bit difference hash — cheap near-duplicate signature."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    out = 0
    for bit in bits.flatten():
        out = (out << 1) | int(bit)
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def score_frame(
    dets: Sequence[Detection],
    *,
    low: float,
    high: float,
    disagree_iou: float,
) -> tuple[float, Dict[str, int]]:
    uncertain = sum(1 for d in dets if low <= d.confidence < high)
    rare = sum(1 for d in dets if d.class_name in RARE_CLASSES)
    disagree = 0
    for i, a in enumerate(dets):
        for b in dets[i + 1 :]:
            if a.model_id == b.model_id or a.class_name == b.class_name:
                continue
            if box_iou(a.bbox_xyxy, b.bbox_xyxy) >= disagree_iou:
                disagree += 1
    score = 5.0 * disagree + 3.0 * rare + 1.0 * uncertain
    return score, {"disagree": disagree, "rare": rare, "uncertain": uncertain}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Rank frames for aerial labeling")
    p.add_argument("--device", default=None, help="cpu / mps / 0")
    p.add_argument("--conf-low", type=float, default=0.25)
    p.add_argument("--conf-high", type=float, default=0.55)
    p.add_argument("--disagree-iou", type=float, default=0.3)
    p.add_argument("--imgsz", type=int, default=960)
    p.add_argument("--limit", type=int, default=0, help="Only score first N frames (debug)")
    p.add_argument(
        "--include-labeled",
        action="store_true",
        help="Keep already labeled frames in the queue",
    )
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    frames = sorted(p for p in FRAMES.glob("*.jpg"))
    if not frames:
        raise SystemExit(f"No frames in {FRAMES}")
    if args.limit:
        frames = frames[: args.limit]

    labeled = {p.stem for p in LABELS.glob("*.txt")}
    clean = set()
    if BACKGROUND.exists():
        clean = {
            Path(ln.strip()).stem
            for ln in BACKGROUND.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        }

    cfg = load_pipeline_config()
    det_cfg = cfg["detection"]
    specs = [s for s in resolve_model_b_paths(det_cfg) if "waste" not in s.name.lower()]
    if not specs:
        raise SystemExit("No road Model B weights found in models/")

    detectors = [
        YoloDetector(
            model_path=str(spec.path),
            model_id=f"B{i}",
            conf=args.conf_low,
            iou=float(det_cfg.get("iou", 0.45)),
            imgsz=args.imgsz,
            device=args.device,
            allowed_classes=spec.allowed_classes,
            min_box_area=float(det_cfg.get("min_box_area", 0.0)),
            conf_discard=0.0,
            keep_low_conf=True,
        )
        for i, spec in enumerate(specs)
    ]
    print("Weights: " + ", ".join(s.name for s in specs))

    labeled_hashes: List[int] = []
    rows: List[dict] = []
    for n, path in enumerate(frames, 1):
        image = cv2.imread(str(path))
        if image is None:
            continue
        h = dhash(image)
        if path.stem in labeled:
            labeled_hashes.append(h)
        dets: List[Detection] = []
        for det in detectors:
            dets.extend(det.predict(image, n, 0.0))
        score, parts = score_frame(
            dets,
            low=args.conf_low,
            high=args.conf_high,
            disagree_iou=args.disagree_iou,
        )
        rows.append(
            {
                "name": path.name,
                "score": round(score, 3),
                "hash": h,
                "labeled": path.stem in labeled,
                "background": path.stem in clean,
                "detections": len(dets),
                **parts,
            }
        )
        if n % 50 == 0 or n == len(frames):
            print(f"  {n}/{len(frames)}", flush=True)

    for row in rows:
        if row["labeled"]:
            continue
        if any(hamming(row["hash"], lh) <= DUP_HAMMING for lh in labeled_hashes):
            row["duplicate"] = True
            row["score"] = round(row["score"] * 0.2, 3)
        else:
            row["duplicate"] = False

    queue = [r for r in rows if r["score"] > 0]
    if not args.include_labeled:
        queue = [r for r in queue if not r["labeled"] and not r["background"]]
    queue.sort(key=lambda r: (-r["score"], r["name"]))

    # Every model stayed silent here, so it is a likely clean frame — still needs confirming
    candidates = [
        r
        for r in rows
        if r["detections"] == 0 and not r["labeled"] and not r["background"]
    ]
    candidates.sort(key=lambda r: r["name"])

    PRIORITY.write_text("\n".join(r["name"] for r in queue) + "\n", encoding="utf-8")
    BACKGROUND_CANDIDATES.write_text(
        "\n".join(r["name"] for r in candidates) + "\n", encoding="utf-8"
    )
    REPORT.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    dupes = sum(1 for r in queue if r.get("duplicate"))
    print(f"\nqueue={len(queue)} frames → {PRIORITY}")
    print(f"clean candidates={len(candidates)} → {BACKGROUND_CANDIDATES} (B ile onayla)")
    print(f"  near-duplicate (demoted): {dupes}")
    print(f"  rare-class candidates: {sum(1 for r in queue if r['rare'])}")
    print(f"  model disagreement: {sum(1 for r in queue if r['disagree'])}")
    print("  top 10:")
    for r in queue[:10]:
        print(
            f"    {r['score']:7.2f}  {r['name']}  "
            f"disagree={r['disagree']} rare={r['rare']} uncertain={r['uncertain']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
