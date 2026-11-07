"""Sound design for the English promo, frame-locked to src/promo/timeline.json.

    python3 scripts/promo_sfx.py   -> public/promo/sfx.wav
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfxlib import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent
mixer = Mixer(ROOT / "src/promo/timeline.json")
add, kinds = mixer.add, mixer.kinds

# ───────── cue sheet (scene, local frame @60fps) ─────────
# 01 map
add("map", 2, whoosh(0.5, 200, 2500), 0.55)
add("map", 10, thud(), 0.5)
prev = 0
for fr in range(26, 72):
    v = round(np.interp(fr, [26, 70], [0, 12]) ** 1)  # approx of eased counter
    if v != prev:
        add("map", fr, tick(2400 + v * 40), 0.32)
        prev = v
for i in range(12):
    add("map", 30 + i * 3, blip(1100 + i * 35), 0.13, pan=rng.uniform(-0.5, 0.5))
add("map", 76, pop(780), 0.45, 0.2)
add("map", 100, whoosh(0.4, 400, 5000), 0.5)

# 02 wrong
add("wrong", 0, slam(), 1.0)
add("wrong", 1, shatter(), 0.6)
add("wrong", 32, whoosh(0.4, 800, 4000), 0.35)

# 03 says
add("says", 0, whoosh(0.35, 500, 3000), 0.3)
add("says", 10, pop(520, 0.25), 0.8)
add("says", 112, whoosh(0.35, 500, 3000), 0.3)
add("says", 116, inflate(0.95), 0.55)
for k, fr in enumerate(np.linspace(118, 230, 30).astype(int)):
    add("says", fr, tick(2200 + k * 50), 0.22)
add("says", 232, boing(150), 0.5)
add("says", 236, bubble(320), 0.4, 0.4)

# 04 where
add("where", 0, whoosh(0.4, 3000, 400, rising=False), 0.45)
for i in range(23):
    add("where", int(14 + i * 1.6), blip(700 + i * 40, 0.05), 0.2, pan=-0.4 + i * 0.035)
add("where", 56, pop(980), 0.55)
add("where", 60, whoosh(0.35, 800, 3000), 0.35, 0.3)
add("where", 76, pop(430, 0.25), 0.6, 0.25)

# 05 feed
for b in range(4):
    o = b * 94
    add("feed", o + 2, whoosh(0.35, 300, 2500), 0.4, -0.5)
    add("feed", o + 8, pop(400 + b * 60, 0.2), 0.45, -0.5)
    for k in range(7):
        add("feed", o + 26 + k * 2, bubble(450 + k * 60 + b * 40), 0.2, -0.3 + k * 0.08)
    add("feed", o + 40, boing(150 + b * 18), 0.55, 0.15)
    add("feed", o + 42, pop(900 + b * 80, 0.12), 0.45, -0.3)
    for k, fr in enumerate(np.linspace(40, 66, 10).astype(int)):
        add("feed", o + fr, tick(2400 + k * 60), 0.18, 0.15)
    add("feed", o + 82, whoosh(0.25, 2500, 400, rising=False), 0.25, -0.5)
add("feed", 352, chime((1047, 1319, 1568)), 0.45)

# 06 find out
add("findout", 0, whoosh(0.4, 300, 2000), 0.4)
add("findout", 4, pop(380, 0.22), 0.5)
prev = 1
for fr in range(16, 77):
    p = (fr - 16) / 60
    e = 0.5 - 0.5 * np.cos(np.pi * p)
    v = int(round(1 + 42 * e))
    if v != prev:
        add("findout", fr, tick(1900 + v * 20), 0.22)
        prev = v
add("findout", 84, thud(), 0.8)
add("findout", 84, swell(1.4, 110), 0.35)
add("findout", 96, ring(0.9), 0.32, 0.2)

# 07 km
add("km", 0, slam(), 0.35)
for k, fr in enumerate(np.linspace(6, 80, 34).astype(int)):
    add("km", fr, tick(2000 + k * 30), 0.18)
for i in range(10):
    add("km", 10 + i * 6, blip(600 + i * 50, 0.05), 0.1, pan=rng.uniform(-0.7, 0.7))
add("km", 54, whoosh(0.4, 800, 4000), 0.3)

# 08 logo — music drop lands here
add("logo", 0, whoosh(0.3, 4000, 300, rising=False), 0.35)
add("logo", 2, pop(520, 0.3), 0.8)
add("logo", 26, knock(), 0.5)
add("logo", 14, chime((1568, 2093, 2637)), 0.3)

# 09 every
for fr, pan in ((2, -0.4), (10, 0.4), (64, -0.4), (72, 0.4), (126, -0.3), (132, 0.3)):
    add("every", fr, whoosh(0.4, 300, 3000), 0.32, pan)
for fr in (4, 62, 124, 192):
    add("every", fr, pop(760, 0.14), 0.4)
add("every", 186, whoosh(0.6, 4000, 200, rising=False), 0.5)
add("every", 220, pop(420, 0.3), 0.7)
add("every", 222, thud(), 0.5)

# 10 real
add("real", 0, whoosh(0.4, 200, 2500), 0.45)
for k, fr in enumerate(np.linspace(8, 50, 30).astype(int)):
    add("real", fr, tick(2200 + k * 30), 0.15)
for i in range(26):
    add("real", int(14 + i * 1.5), blip(900 + (i % 6) * 90, 0.04), 0.08, pan=rng.uniform(-0.6, 0.6))
add("real", 52, pop(760, 0.14), 0.45)

# 11 notify
add("notify", 12, crunch(1.0), 0.55)
add("notify", 90, whoosh(0.3, 500, 3500), 0.3)
add("notify", 100, ding(), 0.55)
add("notify", 118, pop(600, 0.18), 0.35, 0.4)
add("notify", 140, knock(), 0.7, 0.35)
add("notify", 154, knock(), 0.7, 0.35)

# 12 one tap
add("onetap", 4, pop(600, 0.2), 0.45)
add("onetap", 26, whoosh(0.45, 600, 3500), 0.35)
add("onetap", 52, tick(1800), 0.7)
add("onetap", 54, knock(), 0.35)
add("onetap", 70, chime(), 0.6)

# 13 morning
add("morning", 0, swell(1.8, 262), 0.3)
add("morning", 4, chime((1319, 1568, 1976)), 0.22)
for k in range(0, 31, 2):
    fr = int(np.interp(k, [0, 30], [30, 60]))
    add("morning", fr, tick(2600), 0.12)
add("morning", 40, drone_buzz(1.6), 0.22)
add("morning", 121, whoosh(0.4, 300, 2500), 0.4)
for i in range(3):
    add("morning", 157 + i * 9, ding() * 0.6, 0.35, -0.2 + i * 0.2)

# 14 fewer — the issues get fixed on half-beats
add("fewer", 2, thud(), 0.5)
for i in range(4):
    add("fewer", 4 + i * 4, pop(500 + i * 70, 0.15), 0.3, -0.6 + i * 0.4)
    t0 = int(round(31 + i * 15.65))
    add("fewer", t0, pop(300 + i * 40, 0.18), 0.5, -0.6 + i * 0.4)
    add("fewer", t0 + 3, bell(1047 * 2 ** (i * 4 / 12), 0.9) * 0.5, 0.55, -0.6 + i * 0.4)
add("fewer", 123, whoosh(0.6, 200, 3000), 0.5)
add("fewer", 138, swell(2.0, 196), 0.4)
add("fewer", 140, chime((784, 988, 1175, 1568), 0.09), 0.3)

# 15 end
add("end", 0, pop(520, 0.3), 0.7)
add("end", 24, knock(), 0.4)
add("end", 40, pop(760, 0.16), 0.5)
add("end", 56, chime((1047, 1319, 1568, 2093)), 0.4)
add("end", 184, whoosh(0.55, 300, 4000), 0.5)

# transitions: every non-cut entrance gets air; iris portals also get a low "bloop"
for sid, kind in kinds.items():
    if kind == "cut" or sid == "end":
        continue
    if kind.startswith("iris"):
        add(sid, 0, whoosh(0.35, 250, 2200), 0.32)
        add(sid, 1, pop(260, 0.22), 0.35)
    elif kind in ("whip", "push"):
        add(sid, 0, whoosh(0.28, 600, 5000), 0.42)
    elif kind == "zoom":
        add(sid, 0, whoosh(0.3, 3500, 400, rising=False), 0.35)


mixer.master(ROOT / "public/promo/sfx.wav")
