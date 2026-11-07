"""Sound design for "CityVision Wrapped": card whooshes, counter ticks that follow the numbers,
pops on reveals — locked to src/wrapped/timeline.json and Sarah's word timings.
    python3 scripts/wrapped_sfx.py   -> public/wrapped/sfx.wav
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfxlib import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent
mixer = Mixer(ROOT / "src/wrapped/timeline.json")
add, kinds = mixer.add, mixer.kinds
WORDS = json.loads((ROOT / "src/wrapped/vo_words.json").read_text())


def w(scene, word):
    return [f for x, f in WORDS[scene] if x == word][0]


def count(scene, a, b, n=22, base=2200):
    """Ticks that speed up and rise in pitch as a number counts from frame a to b, then a landing pop."""
    for k in range(n):
        t = 1 - (1 - k / n) ** 2
        add(scene, int(a + (b - a) * t), tick(base + k * 45), 0.16)
    add(scene, b, pop(820, 0.16), 0.5)
    add(scene, b + 1, bell(1568, 0.6) * 0.4, 0.3)


# intro — a hit on every half-beat flash, then the gift bursts
for k in range(8):
    fr = int(round(k * 15.65))
    add("intro", fr, pop(480 + k * 70, 0.12), 0.55, -0.5 + (k % 2))
    add("intro", fr, whoosh(0.18, 800, 6000), 0.25, (k % 2) - 0.5)
add("intro", 127, slam() * 0.4, 0.4)
add("intro", 128, bubble(400), 0.4)
add("intro", w("intro", "wrapped") - 4, slam() * 0.5, 0.5)
add("intro", w("intro", "wrapped") - 2, shatter() * 0.5, 0.35)
add("intro", w("intro", "wrapped"), chime((784, 988, 1175, 1568), 0.06), 0.35)

count("air", w("air", "six") - 4, w("air", "minutes") + 12)
for i in range(4):
    add("air", w("air", "flights") + i * 6, blip(900 + i * 110, 0.06), 0.3)
add("air", 60, drone_buzz(1.6), 0.18)

count("frames", w("frames", "ten") - 2, w("frames", "frames"), n=30)
for i in range(24):
    add("frames", 4 + i * 3, tick(3400), 0.08, -0.6 + (i % 6) * 0.24)

count("seen", w("seen", "nine") - 2, w("seen", "times"), n=26)
for i in range(30):
    add("seen", int(8 + i * 3.6), blip(1200 + (i % 5) * 140, 0.03), 0.07, rng.uniform(-0.8, 0.8))

add("issues", w("issues", "merged") - 4, whoosh(0.9, 3000, 300, rising=False), 0.4)
count("issues", w("issues", "seventy-five") - 4, w("issues", "seventy-five") + 16, n=14)

add("top", w("top", "road") - 10, whoosh(0.6, 300, 2500), 0.3)
add("top", w("top", "damage") + 4, pop(620, 0.2), 0.5)

add("best", w("best", "find") - 6, whoosh(0.35, 400, 3000), 0.35)
add("best", w("best", "pothole") - 2, tick(1500), 0.7)
count("best", w("best", "ninety-eight") - 4, w("best", "percent"), n=18)

count("tossed", w("tossed", "three") - 2, w("tossed", "sixty-five") + 10, n=18)
for i in range(8):
    add("tossed", w("tossed", "thrown") - 8 + i * 4, whoosh(0.25, 2500, 400, rising=False), 0.12, rng.uniform(-0.6, 0.6))

count("human", w("human", "twelve") - 4, w("human", "twelve") + 18, n=12)
for i in range(12):
    add("human", 10 + i * 4, paper_flick := hp(rng.standard_normal(1600), 2500) * np.exp(-tt(1600 / SR) * 80), 0.12)

count("people", w("people", "over") - 4, w("people", "times"), n=26)
add("people", w("people", "every"), whoosh(0.6, 400, 5000), 0.3)

add("outro", w("outro", "now") - 4, whoosh(0.5, 200, 2500), 0.4)
add("outro", w("outro", "year") - 4, slam() * 0.5, 0.45)
for i in range(52):
    add("outro", int(w("outro", "now") + 10 + i * 1.6), blip(700 + (i % 13) * 60, 0.04), 0.1)

add("end", 0, whoosh(0.35, 250, 2200), 0.3)
add("end", w("end", "cityvision") - 4, pop(520, 0.3), 0.6)
add("end", w("end", "book") - 4, pop(760, 0.16), 0.5)
add("end", w("end", "book") + 10, chime((1047, 1319, 1568, 2093)), 0.35)
add("end", 186, whoosh(0.55, 300, 4000), 0.45)

for sid, kind in kinds.items():
    if kind == "push":
        add(sid, 0, whoosh(0.28, 600, 5000), 0.4)

mixer.master(ROOT / "public/wrapped/sfx.wav")
