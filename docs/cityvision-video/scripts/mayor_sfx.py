"""Sound design for "Dear Mayor" — paper, pen, phone, typewriter, stamps — locked to
src/mayor/timeline.json and the voices' word timings (src/mayor/vo_words.json).

    python3 scripts/mayor_sfx.py   -> public/mayor/sfx.wav
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfxlib import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent
mixer = Mixer(ROOT / "src/mayor/timeline.json")
add, kinds = mixer.add, mixer.kinds
WORDS = json.loads((ROOT / "src/mayor/vo_words.json").read_text())


def words(scene):
    return WORDS[scene]


def w(scene, word, nth=0):
    return [f for x, f in WORDS[scene] if x == word][nth]


def pen(n_chars):
    """Pen on paper: a short scratch per word, longer for longer words."""
    d = 0.05 + n_chars * 0.022
    x = bp(rng.standard_normal(int(d * SR)), 1800, 6500)
    env = np.abs(np.sin(np.linspace(0, np.pi * max(1, n_chars // 2), len(x)))) * np.sin(np.linspace(0, np.pi, len(x)))
    return x * env * 0.35


def clack():
    d = 0.045
    t = tt(d)
    body = lp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 120)
    key = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 90) * 0.6
    return fade(body + key, 0.0005, 0.01)


def paper(d=0.25):
    return whoosh(d, 1500, 6000) * 0.6


def decode(path, seconds):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", str(seconds), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


# letter 1 — handwritten
add("l1", 0, paper(0.4), 0.5)
for word, at in words("l1"):
    add("l1", at - 2, pen(len(word)), 0.5, -0.2)
add("l1", w("l1", "hole") + 8, pen(10) * 1.2, 0.45, 0.2)          # the circle around "hole"
add("l1", 330, crunch(0.8) * 0.7, 0.5)                              # paper tears open
add("l1", 352, pen(14), 0.4)                                        # signature

# answers — shutter on the freeze, stamp slam
for sid, freeze in (("a1", 94), ("a2", 18), ("a3", 18)):
    add(sid, 0, whoosh(0.3, 400, 3000), 0.3)
    add(sid, freeze, tick(1500), 0.8)
    add(sid, freeze + 1, hp(rng.standard_normal(2400), 3000) * np.exp(-tt(0.05) * 90), 0.35)
    add(sid, freeze + 2, pop(800, 0.14), 0.45)
    add(sid, freeze + 14, slam() * 0.6, 0.55)                      # rubber stamp

# letter 2 — message
add("l2", 0, paper(0.3), 0.3)
for word in ("dear", "the", "i've", "nobody"):
    at = w("l2", word)
    for k in range(3):
        add("l2", at - 18 + k * 5, tick(3400) * 0.5, 0.12, 0.3)     # typing dots
    add("l2", at, bubble(700), 0.5, 0.3)
add("l2", w("l2", "came") + 12, blip(520, 0.12), 0.25)

# letter 3 — typewriter
add("l3", 0, paper(0.4), 0.4)
for word, at in words("l3"):
    for c in range(len(word)):
        add("l3", at + int(c * 2.2), clack(), 0.35 * (1.6 if word == "second" and at == w("l3", "second", 1) else 1), -0.1)
add("l3", w("l3", "year") + 12, bell(2637, 1.0) * 0.6, 0.35)        # margin bell
add("l3", w("l3", "second", 1) + 16, pen(8), 0.5)                  # red underline
add("l3", w("l3", "second", 1) + 24, pen(8), 0.5)

# pile — paper flutter + a murmur of "Dear Mayor…" from the three residents; dead silence on the last beat
for i in range(30):
    add("pile", i * 3, paper(0.18), 0.22, rng.uniform(-0.8, 0.8))
clips = sorted((ROOT / "vo/clips/mayor").glob("0[0-2]-*.mp3"))
for k in range(9):
    c = clips[k % len(clips)]
    x = decode(c, 0.9)
    x = lp(x, 3000) * np.linspace(1, 0.6, len(x))
    add("pile", 4 + k * 9, x, 0.22 + 0.04 * (k % 3), rng.uniform(-0.7, 0.7))

# turn — the drop
add("turn", 0, slam(), 0.7)
add("turn", 0, swell(1.6, 98), 0.4)
add("turn", w("turn", "first") - 2, chime((784, 1047, 1319)), 0.3)

# payoff — map
add("payoff", 0, whoosh(0.4, 300, 2500), 0.35)
add("payoff", w("payoff", "flies") - 10, whoosh(1.2, 300, 3000), 0.25)
for i in range(3):
    add("payoff", w("payoff", "schedule") + i * 6, blip(900 + i * 120, 0.06), 0.25)
    add("payoff", w("payoff", "every") + i * 8, pop(620 + i * 90, 0.16), 0.45, -0.3 + i * 0.3)
    add("payoff", w("payoff", "write") + 4 + i * 4, paper(0.2), 0.3)
add("payoff", w("payoff", "write") + 8, chime((1047, 1319, 1568)), 0.35)

# close — the reply
add("close", 0, paper(0.4), 0.45)
for word, at in words("close"):
    add("close", at - 2, pen(len(word)), 0.5, -0.2)
add("close", 118, pop(520, 0.25), 0.45)
add("close", 122, pen(12), 0.45)
add("close", 146, pen(16), 0.35)

# end
add("end", 0, pop(520, 0.3), 0.6)
add("end", w("end", "book") - 4, pop(760, 0.16), 0.5)
add("end", w("end", "book") + 10, chime((1047, 1319, 1568, 2093)), 0.35)
add("end", 156, whoosh(0.55, 300, 4000), 0.45)

# transitions
for sid, kind in kinds.items():
    if kind == "cut" or sid in ("turn",):
        continue
    if kind.startswith("iris"):
        add(sid, 0, whoosh(0.35, 250, 2200), 0.3)
    elif kind in ("whip", "push"):
        add(sid, 0, whoosh(0.28, 600, 5000), 0.38)
    elif kind == "zoom":
        add(sid, 0, whoosh(0.3, 3500, 400, rising=False), 0.32)

# the silent beat: nothing from the last pile beat to the drop
s0 = int((mixer.starts["pile"] + 94) / mixer.fps * SR)
s1 = int(mixer.starts["turn"] / mixer.fps * SR)
mixer.L[s0:s1] *= np.linspace(1, 0, s1 - s0) ** 4
mixer.R[s0:s1] *= np.linspace(1, 0, s1 - s0) ** 4

mixer.master(ROOT / "public/mayor/sfx.wav")

# music bed: cut from the track at the timeline's start, and hold a true breath on the silent beat
import wave  # noqa: E402

TLJ = json.loads((ROOT / "src/mayor/timeline.json").read_text())
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-ss", str(TLJ["musicStart"]), "-t", str(mixer.total / mixer.fps + 0.6), "-i",
     str(ROOT / "public/muzik-lightbeats.mp3"), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
    capture_output=True, check=True).stdout
mus = np.frombuffer(raw, np.float32).astype(float).reshape(-1, 2).T.copy()
mus[:, : int(0.6 * SR)] *= np.linspace(0, 1, int(0.6 * SR))
g = np.ones(mus.shape[1])
f0, f1 = s0 - int(0.12 * SR), s1 - int(0.02 * SR)
g[f0:s0] = np.linspace(1, 0.04, s0 - f0)
g[s0:f1] = 0.04
g[f1:s1] = np.linspace(0.04, 1, s1 - f1)
mus *= g
with wave.open(str(ROOT / "public/mayor/music.wav"), "wb") as wv:
    wv.setnchannels(2)
    wv.setsampwidth(2)
    wv.setframerate(SR)
    wv.writeframes((np.clip(mus.T, -1, 1) * 32767).astype("<i2").tobytes())
print("wrote public/mayor/music.wav (breath on the silent beat)")
