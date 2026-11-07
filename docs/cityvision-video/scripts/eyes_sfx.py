"""Sound design for "Same street. Different eyes." — beat-locked to src/eyes/timeline.json.
Top half = the street going by (muffled), bottom half = CityVision (crisp shutter + log ticks).

    python3 scripts/eyes_sfx.py   -> public/eyes/sfx.wav
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfxlib import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent
mixer = Mixer(ROOT / "src/eyes/timeline.json")
add = mixer.add
WORDS = json.loads((ROOT / "src/eyes/vo_words.json").read_text())


def w(scene, word):
    return [f for x, f in WORDS[scene] if x == word][0]


def street(d):
    """Muffled street ambience: low traffic rumble + distant air."""
    n = int(d * SR)
    x = lp(rng.standard_normal(n), 400) * 0.8 + bp(rng.standard_normal(n), 600, 1800) * 0.15
    env = np.minimum(1, np.linspace(0, d, n) / 0.3) * np.minimum(1, (d - np.linspace(0, d, n)) / 0.3)
    return x * env


def shutter():
    out = np.zeros(int(0.12 * SR))
    c = tick(1500)
    out[: len(c)] += c
    b = hp(rng.standard_normal(int(0.06 * SR)), 2500) * np.exp(-tt(0.06) * 70) * 0.6
    out[int(0.035 * SR) : int(0.035 * SR) + len(b)] += b
    return out


# intro
add("intro", 0, whoosh(0.5, 300, 3000), 0.35)
add("intro", 18, bell(784, 1.2) * 0.5, 0.3, -0.3)
add("intro", 44, pop(520, 0.22), 0.45, 0.3)

HITS = {"m1": 152, "m2": 40, "m3": 96, "m4": 40}
for i, (m, hit) in enumerate(HITS.items()):
    add(m, 0, street(3.1), 0.22, -0.4)                                   # the passer-by's world
    if m == "m1":
        add(m, 20, ding() * 0.5, 0.25, -0.5)                             # their phone
    for k in range(6):                                                   # footsteps on the pavement
        step = lp(rng.standard_normal(int(0.07 * SR)), 900) * np.exp(-tt(0.07) * 55) + np.sin(2 * np.pi * 95 * tt(0.07)) * np.exp(-tt(0.07) * 40) * 0.5
        add(m, 8 + k * 30 + (k % 2) * 2, step, 0.32, -0.5 + (k % 2) * 0.2)
    add(m, hit, shutter(), 0.8, 0.3)                                     # CityVision sees it
    add(m, hit + 2, pop(700 + i * 60, 0.14), 0.45, 0.3)
    for k in range(3):
        add(m, hit + 12 + k * 3, tick(3000 + k * 250), 0.22, 0.4)        # logged
    add(m, hit + 14, bell(1319 * 2 ** (i * 2 / 12), 0.7) * 0.4, 0.3, 0.3)

# tally — four ticks, then the silent beat
for i in range(4):
    add("tally", 8 + i * 10, pop(600 + i * 110, 0.15), 0.5, 0.2)
s0 = int((mixer.starts["tally"] + 94) / mixer.fps * SR)
s1 = int(mixer.starts["map"] / mixer.fps * SR)
mixer.L[s0:s1] *= np.linspace(1, 0, s1 - s0) ** 4
mixer.R[s0:s1] *= np.linspace(1, 0, s1 - s0) ** 4

# map — the drop: halves split, pins land
add("map", 0, slam() * 0.7, 0.6)
add("map", 0, whoosh(0.5, 200, 3500), 0.45)
add("map", 0, swell(2.4, 131), 0.35)
for i in range(4):
    add("map", 30 + i * 9, pop(620 + i * 90, 0.16), 0.45, -0.3 + i * 0.2)
add("map", w("map", "different") - 2, chime((784, 988, 1175, 1568), 0.08), 0.3)

# end
add("end", 0, whoosh(0.35, 250, 2200), 0.3)
add("end", w("end", "cityvision") - 4, pop(520, 0.3), 0.6)
add("end", w("end", "book") - 4, pop(760, 0.16), 0.5)
add("end", w("end", "book") + 10, chime((1047, 1319, 1568, 2093)), 0.35)
add("end", 156, whoosh(0.55, 300, 4000), 0.45)

mixer.master(ROOT / "public/eyes/sfx.wav")

# music: cut at the timeline start with a true breath on the silent beat
import subprocess  # noqa: E402
import wave  # noqa: E402

TLJ = json.loads((ROOT / "src/eyes/timeline.json").read_text())
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(TLJ["musicStart"]), "-t", str(mixer.total / mixer.fps + 0.6), "-i",
                      str(ROOT / "public/muzik-lightbeats.mp3"), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                     capture_output=True, check=True).stdout
mus = np.frombuffer(raw, np.float32).astype(float).reshape(-1, 2).T.copy()
mus[:, : int(0.4 * SR)] *= np.linspace(0, 1, int(0.4 * SR))
g = np.ones(mus.shape[1])
f0, f1 = s0 - int(0.12 * SR), s1 - int(0.02 * SR)
g[f0:s0] = np.linspace(1, 0.04, s0 - f0)
g[s0:f1] = 0.04
g[f1:s1] = np.linspace(0.04, 1, s1 - f1)
mus *= g
with wave.open(str(ROOT / "public/eyes/music.wav"), "wb") as wv:
    wv.setnchannels(2)
    wv.setsampwidth(2)
    wv.setframerate(SR)
    wv.writeframes((np.clip(mus.T, -1, 1) * 32767).astype("<i2").tobytes())
print("wrote public/eyes/music.wav (breath on the silent beat)")
