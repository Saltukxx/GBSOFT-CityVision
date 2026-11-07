"""Eye-level clips for the top half of "Same street. Different eyes." (Pixabay Content License).

Cuts 3.2 s from each source, crops to the half-screen (1080×950), and blurs any face it finds
(OpenCV face cascade) so no passer-by is identifiable.
    ../../.venv/bin/python scripts/eyes_stock.py  → public/eyes/street/*.mp4
"""
import subprocess
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "public/eyes/stock"
OUT = HERE / "public/eyes/street"
OUT.mkdir(parents=True, exist_ok=True)
W, H, SECONDS = 1080, 950, 3.2
faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

CLIPS = [  # (output name, source file, start seconds, focus x 0..1, has faces)
    ("walk", "109674-685086225.mp4", 2.0, 0.5, False),   # empty street, no people
    ("over", "7713-203079893.mp4", 1.2, 0.5, False),     # legs only
    ("around", "21782-321298091.mp4", 0.6, 0.45, False), # feet only
    ("phone", "6590-193729460.mp4", 0.4, 0.5, True),
]

for name, src, start, fx, has_faces in CLIPS:
    cap = cv2.VideoCapture(str(SRC / src))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start * fps))
    tmp = OUT / f"_{name}"
    tmp.mkdir(exist_ok=True)
    last, found = [], 0
    for i in range(int(SECONDS * fps)):
        ok, im = cap.read()
        if not ok:
            break
        h, w = im.shape[:2]
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        boxes = (list(faces.detectMultiScale(gray, 1.1, 5, minSize=(24, 24))) + list(profile.detectMultiScale(gray, 1.1, 5, minSize=(24, 24)))) if has_faces else []
        if boxes:
            last = boxes
        elif last:
            boxes = last  # carry the last face box over a missed frame
        for (x, y, bw, bh) in boxes:
            g = int(max(bw, bh) * 0.35)
            x0, y0, x1, y1 = max(0, x - g), max(0, y - g), min(w, x + bw + g), min(h, y + bh + g)
            roi = im[y0:y1, x0:x1]
            small = cv2.resize(roi, (max(1, roi.shape[1] // 14), max(1, roi.shape[0] // 14)))
            im[y0:y1, x0:x1] = cv2.GaussianBlur(cv2.resize(small, (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_NEAREST), (0, 0), 9)
            found += 1
        # cover-crop to the half screen
        s = max(W / w, H / h)
        im = cv2.resize(im, (int(w * s + 0.5), int(h * s + 0.5)), interpolation=cv2.INTER_AREA)
        cx = int(im.shape[1] * fx - W / 2)
        cx = max(0, min(im.shape[1] - W, cx))
        cy = (im.shape[0] - H) // 2
        cv2.imwrite(str(tmp / f"{i:04d}.png"), im[cy : cy + H, cx : cx + W])
    cap.release()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{fps:.3f}", "-i", str(tmp / "%04d.png"), "-c:v", "libx264", "-crf", "14",
                    "-preset", "slow", "-pix_fmt", "yuv420p", str(OUT / f"{name}.mp4")], check=True)
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    print(f"  {name}: {src} @ {start}s, {fps:.2f} fps, face blurs applied on {found} frame-boxes")
