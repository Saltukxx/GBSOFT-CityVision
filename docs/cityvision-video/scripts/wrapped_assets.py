"""Anonymised frame mosaic for "CityVision Wrapped": 24 frames evenly sampled from our 4 test flights.
    ../../.venv/bin/python scripts/wrapped_assets.py  → public/wrapped/mosaic/*.jpg
"""
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
from cityvision.privacy.anonymize import Anonymizer  # noqa: E402

OUT = HERE / "public/wrapped/mosaic"
OUT.mkdir(parents=True, exist_ok=True)
anon = Anonymizer(model_path=str(REPO / "yolov8n.pt"), vehicles="plates", imgsz=1920)
VIDS = ["dji_fly_20260816_175412", "dji_fly_20260816_180530", "dji_fly_20260816_181137", "dji_fly_20260816"]
k = 0
for v in VIDS:
    cap = cv2.VideoCapture(str(REPO / f"data/samples/{v}.mp4"))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for i in range(6):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (i + 0.5) / 6))
        ok, im = cap.read()
        if not ok:
            continue
        clean, regs = anon.anonymize(im)
        cv2.imwrite(str(OUT / f"{k:02d}.jpg"), cv2.resize(clean, (384, 216), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 90])
        k += 1
    cap.release()
print("wrote", k, "mosaic frames")
