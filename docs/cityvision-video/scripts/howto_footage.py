"""Real-footage assets for "How it works", cut from our own DJI flights (Kartal, 16 Aug 2026).

Every frame goes through CityVision's own anonymiser (people + plates blurred) before it is
written. Detection boxes come straight from the pipeline output (detections.jsonl).

Run with the repo venv (needs cv2 + ultralytics):
    ../../.venv/bin/python scripts/howto_footage.py
Writes public/howto/footage/* and src/howto/footage.json
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent.parent  # docs/cityvision-video
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
from cityvision.privacy.anonymize import Anonymizer  # noqa: E402

OUT = HERE / "public/howto/footage"
OUT.mkdir(parents=True, exist_ok=True)
CARD_AR = 880 / 820  # Spot card aspect
anon = Anonymizer(model_path=str(REPO / "yolov8n.pt"), vehicles="plates", imgsz=1920)


def video(vid):
    return str(REPO / f"data/samples/dji_fly_20260816_{vid}.mp4")


def frame(vid, n):
    cap = cv2.VideoCapture(video(vid))
    cap.set(cv2.CAP_PROP_POS_FRAMES, n)
    ok, im = cap.read()
    cap.release()
    assert ok, (vid, n)
    return im


def det(vid, n, cls):
    for line in open(REPO / f"outputs/dji_{vid}/detections.jsonl"):
        r = json.loads(line)
        if r.get("type") == "detection" and r["frame"] == n and r["class"] == cls:
            return r
    raise LookupError((vid, n, cls))


def crop_x(cx, w, full=1920):
    return int(max(0, min(full - w, cx - w / 2)))


def still(name, vid, n, cls, label):
    im = frame(vid, n)
    clean, regions = anon.anonymize(im)
    r = det(vid, n, cls)
    x1, y1, x2, y2 = r["bbox_xyxy"]
    h = im.shape[0]
    w = 2 * int(round(h * CARD_AR / 2))
    x0 = crop_x((x1 + x2) / 2, w)
    cv2.imwrite(str(OUT / f"{name}.jpg"), clean[:, x0 : x0 + w], [cv2.IMWRITE_JPEG_QUALITY, 94])
    print(f"  {name}: {cls} {r['confidence']:.2f}, blurred {len(regions)} region(s)")
    return {
        "src": f"howto/footage/{name}.jpg",
        "w": w,
        "h": h,
        "box": [x1 - x0, y1, x2 - x0, y2],
        "label": f"{label} {r['confidence']:.2f}",
        "conf": r["confidence"],
    }


assets = {}

# Spot: real approach to the pothole, ending on the exact detection frame
VID, HIT = "180530", 1560
pot = det(VID, HIT, "pothole")
W = 2 * int(round(1080 * CARD_AR / 2))
X0 = crop_x((pot["bbox_xyxy"][0] + pot["bbox_xyxy"][2]) / 2, W)
N_INTRO = 76  # source frames (30 fps) ≈ 2.5 s
tmp = OUT / "_intro"
tmp.mkdir(exist_ok=True)
cap = cv2.VideoCapture(video(VID))
cap.set(cv2.CAP_PROP_POS_FRAMES, HIT - N_INTRO + 1)
stream = anon.stream(every=1)
for i in range(N_INTRO):
    ok, im = cap.read()
    assert ok
    cv2.imwrite(str(tmp / f"{i:04d}.png"), stream(im)[:, X0 : X0 + W])
cap.release()
subprocess.run(
    ["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", str(tmp / "%04d.png"), "-c:v", "libx264", "-crf", "12",
     "-preset", "slow", "-pix_fmt", "yuv420p", str(OUT / "intro.mp4")],
    check=True,
)
for p in tmp.iterdir():
    p.unlink()
tmp.rmdir()
assets["intro"] = {"src": "howto/footage/intro.mp4", "frames": N_INTRO, "fps": 30, "w": W, "h": 1080}
print("  intro clip: 180530 frames", HIT - N_INTRO + 1, "→", HIT)

assets["pothole"] = still("pothole", VID, HIT, "pothole", "pothole")
assets["crack"] = still("crack", "181137", 10, "road_crack", "crack")
assets["damage"] = still("damage", "181137", 240, "road_damage", "road damage")

# Merge / Pin / Approve: tight evidence crops of the same pothole from three frames
thumbs = []
for n in (1552, 1560, 1566):
    im = frame(VID, n)
    clean, _ = anon.anonymize(im)
    x1, y1, x2, y2 = det(VID, n, "pothole")["bbox_xyxy"]
    cx, cy, s = (x1 + x2) / 2, (y1 + y2) / 2, 760
    ax = int(max(0, min(1920 - s, cx - s / 2)))
    ay = int(max(0, min(1080 - s * 0.66, cy - s * 0.33)))
    c = clean[ay : ay + int(s * 0.66), ax : ax + s]
    name = f"evidence_{n}.jpg"
    cv2.imwrite(str(OUT / name), c, [cv2.IMWRITE_JPEG_QUALITY, 94])
    thumbs.append({"src": f"howto/footage/{name}", "w": s, "h": int(s * 0.66), "box": [x1 - ax, y1 - ay, x2 - ax, y2 - ay]})
assets["evidence"] = thumbs

# Blur: busy street frame — anonymised, with the regions it blurred
im = frame("181137", 938)
clean, regions = anon.anonymize(im)
bw = int(round(1080 * 900 / 800))
bx0 = 300
cv2.imwrite(str(OUT / "street.jpg"), clean[:, bx0 : bx0 + bw], [cv2.IMWRITE_JPEG_QUALITY, 94])
regs = []
for r in regions:
    x1, y1, x2, y2 = r.box
    if x2 < bx0 or x1 > bx0 + bw:
        continue
    regs.append({"kind": r.kind, "box": [max(0, x1 - bx0), y1, min(bw, x2 - bx0), y2]})
assets["street"] = {"src": "howto/footage/street.jpg", "w": bw, "h": 1080, "regions": regs}
print(f"  street: {len(regs)} blurred region(s):", [r["kind"] for r in regs])

(HERE / "src/howto/footage.json").write_text(json.dumps(assets, indent=1))
print("wrote src/howto/footage.json")
