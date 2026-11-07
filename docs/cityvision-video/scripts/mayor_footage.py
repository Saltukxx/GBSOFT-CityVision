"""Real-footage answers for "Dear Mayor" — own DJI flights (16 Aug 2026), every frame anonymised
with CityVision's own anonymiser, boxes straight from the pipeline's detections.jsonl.

Shots are cropped in around the detection (the potholes are small in a 1080p aerial frame).
    ../../.venv/bin/python scripts/mayor_footage.py   → public/mayor/footage/*, src/mayor/footage.json
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
from cityvision.privacy.anonymize import Anonymizer  # noqa: E402

OUT = HERE / "public/mayor/footage"
OUT.mkdir(parents=True, exist_ok=True)
AR = 900 / 838  # answer card aspect
anon = Anonymizer(model_path=str(REPO / "yolov8n.pt"), vehicles="plates", imgsz=1920)
RUN = {"181137": "dji_181137", "175412": "dji_175412"}


def det(vid, n, cls):
    for line in open(REPO / f"outputs/{RUN[vid]}/detections.jsonl"):
        r = json.loads(line)
        if r.get("type") == "detection" and r["frame"] == n and r["class"] == cls:
            return r
    raise LookupError((vid, n, cls))


def crop_rect(box, h):
    """Crop of height h (card aspect) centred on the box, kept inside the 1920×1080 frame."""
    w = 2 * int(round(h * AR / 2))
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    x0 = int(max(0, min(1920 - w, cx - w / 2)))
    y0 = int(max(0, min(1080 - h, cy - h * 0.55)))
    return x0, y0, w, h


def frames(vid, first, n):
    cap = cv2.VideoCapture(str(REPO / f"data/samples/dji_fly_20260816_{vid}.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    for _ in range(n):
        ok, im = cap.read()
        assert ok
        yield im
    cap.release()


def shot(name, vid, n, cls, label, h, video_frames=0):
    r = det(vid, n, cls)
    x0, y0, w, hh = crop_rect(r["bbox_xyxy"], h)
    if video_frames:
        tmp = OUT / f"_{name}"
        tmp.mkdir(exist_ok=True)
        stream = anon.stream(every=1)
        for i, im in enumerate(frames(vid, n - video_frames + 1, video_frames)):
            cv2.imwrite(str(tmp / f"{i:04d}.png"), stream(im)[y0 : y0 + hh, x0 : x0 + w])
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", str(tmp / "%04d.png"), "-vf", "scale=1160:-2:flags=lanczos",
             "-c:v", "libx264", "-crf", "12", "-preset", "slow", "-pix_fmt", "yuv420p", str(OUT / f"{name}.mp4")],
            check=True,
        )
        for p in tmp.iterdir():
            p.unlink()
        tmp.rmdir()
    im = next(frames(vid, n, 1))
    clean, regions = anon.anonymize(im)
    c = clean[y0 : y0 + hh, x0 : x0 + w]
    c = cv2.resize(c, (1160, int(round(1160 * hh / w))), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(OUT / f"{name}.jpg"), c, [cv2.IMWRITE_JPEG_QUALITY, 94])
    k = 1160 / w
    x1, y1, x2, y2 = r["bbox_xyxy"]
    print(f"  {name}: {cls} {r['confidence']:.2f} · crop {w}×{hh} · blurred {len(regions)} region(s)")
    out = {
        "src": f"mayor/footage/{name}.jpg",
        "w": 1160,
        "h": c.shape[0],
        "box": [(x1 - x0) * k, (y1 - y0) * k, (x2 - x0) * k, (y2 - y0) * k],
        "label": f"{label} {r['confidence']:.2f}",
        "conf": r["confidence"],
    }
    if video_frames:
        out["video"] = {"src": f"mayor/footage/{name}.mp4", "frames": video_frames, "fps": 30}
    return out


assets = {
    "pothole": shot("pothole", "181137", 814, "pothole", "pothole", 640, video_frames=48),
    "crack": shot("crack", "175412", 1728, "road_damage", "road damage", 760),
    "damage": shot("damage", "175412", 258, "road_damage", "road damage", 760),
}
(HERE / "src/mayor/footage.json").write_text(json.dumps(assets, indent=1))
print("wrote src/mayor/footage.json")
