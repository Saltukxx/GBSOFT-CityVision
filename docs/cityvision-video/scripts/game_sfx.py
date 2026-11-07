"""Sound design for "Can you beat the drone?" — beat-locked to src/game/timeline.json and
Sarah's word timings (src/game/vo_words.json).

    python3 scripts/game_sfx.py   -> public/game/sfx.wav
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfxlib import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent
TL = json.loads((ROOT / "src/game/timeline.json").read_text())
mixer = Mixer(ROOT / "src/game/timeline.json")
add, kinds, starts = mixer.add, mixer.kinds, mixer.starts
WORDS = json.loads((ROOT / "src/game/vo_words.json").read_text())
BEATF = 3600 / TL["bpm"]
bf = lambda b: int(np.floor(b * BEATF + 0.5))
sbeat, b = {}, 0
for sid, n, _ in TL["scenes"]:
    sbeat[sid] = b
    b += n


def w(scene, word, nth=0):
    return [f for x, f in WORDS[scene] if x == word][nth]


def mark(scene, beats):
    return bf(sbeat[scene] + beats) - bf(sbeat[scene])


def heartbeat():
    return thud() * 0.9


def shutter():
    click = tick(1500)
    burst = hp(rng.standard_normal(int(0.06 * SR)), 2500) * np.exp(-tt(0.06) * 70) * 0.6
    out = np.zeros(int(0.12 * SR))
    out[: len(click)] += click
    out[int(0.035 * SR) : int(0.035 * SR) + len(burst)] += burst
    return out


# hook
for word in ("can", "spot", "faster", "drone"):
    add("hook", w("hook", word), blip(700 + len(word) * 40, 0.05), 0.2)
add("hook", w("hook", "three") - 4, pop(520, 0.3), 0.8)
add("hook", w("hook", "three"), boing(160), 0.35)
add("hook", 212, whoosh(0.5, 3500, 300, rising=False), 0.45)

# rounds
for r, pitch in (("r1", 0), ("r2", 2), ("r3", 4)):
    up = 2 ** (pitch / 12)
    add(r, w(r, "round"), pop(440 * up, 0.2), 0.5)
    add(r, w(r, "find"), blip(880 * up, 0.05), 0.25)
    count, reveal = mark(r, 5), mark(r, 11)
    add(r, count - 8, whoosh(0.3, 400, 3000), 0.3)          # veil lifts
    for i, beat in enumerate(range(5, 11)):
        fr = mark(r, beat)
        add(r, fr, heartbeat(), 0.5 if i % 2 == 0 else 0.3)  # tension on every beat
        if i % 2 == 0:
            add(r, fr, tick(2600 + i * 120), 0.45)          # 3 · 2 · 1
    add(r, reveal - 20, whoosh(0.35, 300, 5000), 0.3)       # riser into the reveal
    add(r, reveal, shutter(), 0.9)
    add(r, reveal + 1, pop(760 * up, 0.16), 0.6)
    add(r, reveal + 8, chime((1047 * up, 1319 * up, 1568 * up)), 0.4)

# score
for i, word in enumerate(("three", "for", "three")):
    add("score", w("score", word, 1 if i == 2 else 0), pop(600 + i * 120, 0.16), 0.55, -0.2 + i * 0.2)
    add("score", w("score", word, 1 if i == 2 else 0) + 2, bell(1319 * 2 ** (i * 4 / 12), 0.8) * 0.5, 0.45)
add("score", w("score", "do") + 4, pop(500, 0.25), 0.5)

# map
for i in range(3):
    add("map", 6 + i * 10, pop(620 + i * 90, 0.16), 0.4, -0.3 + i * 0.3)
add("map", w("map", "every") - 6, whoosh(1.8, 200, 5000), 0.32)
add("map", w("map", "every") - 6, swell(2.2, 262), 0.3)

# end
add("end", w("end", "cityvision") - 4, pop(520, 0.3), 0.7)
add("end", 26, knock(), 0.4)
add("end", w("end", "book") - 4, pop(760, 0.16), 0.5)
add("end", w("end", "book") + 10, chime((1047, 1319, 1568, 2093)), 0.35)
add("end", 184, whoosh(0.55, 300, 4000), 0.45)

# transitions
for sid, kind in kinds.items():
    if kind == "cut":
        continue
    if kind.startswith("iris"):
        add(sid, 0, whoosh(0.35, 250, 2200), 0.3)
        add(sid, 1, pop(260, 0.22), 0.3)
    elif kind in ("whip", "push"):
        add(sid, 0, whoosh(0.28, 600, 5000), 0.4)
    elif kind == "zoom":
        add(sid, 0, whoosh(0.3, 3500, 400, rising=False), 0.35)

mixer.master(ROOT / "public/game/sfx.wav")
