"""Sound design for "How it works in 30 seconds", locked to src/howto/timeline.json
and to Sarah's word timings (src/howto/vo_words.json).

    python3 scripts/howto_sfx.py   -> public/howto/sfx.wav
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfxlib import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent
mixer = Mixer(ROOT / "src/howto/timeline.json")
add, kinds = mixer.add, mixer.kinds
WORDS = json.loads((ROOT / "src/howto/vo_words.json").read_text())


def w(scene, word, nth=0):
    return [f for x, f in WORDS[scene] if x == word][nth]


def header(scene, n):
    """Step header: number ball pop + soft thud, pitch rises step by step."""
    add(scene, w(scene, ["one", "two", "three", "four", "five", "six", "seven"][n - 1]), pop(420 + n * 45, 0.2), 0.55)
    add(scene, w(scene, ["one", "two", "three", "four", "five", "six", "seven"][n - 1]) + 1, thud(), 0.3)


# 0 hook
for k, word in enumerate(["how", "does", "cityvision", "work"]):
    add("hook", w("hook", word), blip(700 + k * 90, 0.05), 0.18)
add("hook", w("hook", "thirty") - 4, pop(520, 0.28), 0.8)
add("hook", w("hook", "thirty"), boing(160), 0.35)
add("hook", 156, whoosh(0.45, 3500, 300, rising=False), 0.45)

# timer: soft tick every second from fly to end
starts = mixer.starts
span = starts["end"] - starts["fly"]
for s in range(0, int(span / 60) + 1):
    add("fly", s * 60, tick(3000 if s % 5 else 2200), 0.07)

# 1 fly
header("fly", 1)
add("fly", w("fly", "planned") - 20, whoosh(0.9, 300, 2500), 0.3)
add("fly", 64, pop(700, 0.15), 0.35)
add("fly", 70, drone_buzz(3.8), 0.18)
for i in range(3):
    add("fly", w("fly", "every") - 30 + i * 12, blip(900 + i * 120, 0.06), 0.3, 0.5)

# 2 spot
header("spot", 2)
add("spot", 0, drone_buzz(2.6) * 0.5, 0.14)
for word in ("potholes", "cracks", "road"):
    # camera shutter on the freeze frame + box pop
    add("spot", w("spot", word), tick(1600), 0.7, 0.1)
    add("spot", w("spot", word) + 1, hp(rng.standard_normal(2400), 3000) * np.exp(-tt(0.05) * 90), 0.35)
    add("spot", w("spot", word) + 2, pop(880, 0.12), 0.45, 0.2)

# 3 pin
header("pin", 3)
for i in range(4):
    add("pin", w("pin", "each") + i * 7, pop(620 + i * 70, 0.16), 0.4, -0.4 + i * 0.25)
add("pin", w("pin", "photo") - 4, whoosh(0.3, 600, 3500), 0.3)
add("pin", w("pin", "photo"), pop(760, 0.15), 0.4)
for k in range(0, 34, 2):
    add("pin", w("pin", "gps") + k, tick(2800 + (k % 4) * 200), 0.1)
add("pin", w("pin", "pin") - 4, ding() * 0.7, 0.35)

# 4 merge
header("merge", 4)
for i in range(3):
    add("merge", w("merge", "seen") - 8 + i * 12, whoosh(0.28, 600, 4000), 0.32, -0.5 if i % 2 == 0 else 0.5)
add("merge", w("merge", "still") - 4, whoosh(0.5, 3500, 300, rising=False), 0.4)
add("merge", w("merge", "one") - 2, pop(500, 0.25), 0.6)
add("merge", w("merge", "one"), knock(), 0.4)
add("merge", w("merge", "work") - 8, whoosh(0.35, 300, 2500), 0.35)
add("merge", w("merge", "work"), chime((1047, 1319, 1568)), 0.35)

# 5 blur
header("blur", 5)
add("blur", w("blur", "faces") - 6, whoosh(1.4, 400, 6000), 0.28)
add("blur", w("blur", "faces") + 18, pop(900, 0.12), 0.4, -0.4)
add("blur", w("blur", "plates") + 18, pop(980, 0.12), 0.4, 0.2)
add("blur", w("blur", "photo"), knock(), 0.35)

# 6 approve
header("approve", 6)
add("approve", w("approve", "approves") - 40, whoosh(0.5, 300, 1500), 0.2)
add("approve", w("approve", "approves") - 2, tick(1800), 0.8)
add("approve", w("approve", "approves"), knock(), 0.5)
add("approve", w("approve", "approves") + 6, chime(), 0.55)

# 7 fix
header("fix", 7)
add("fix", 30, drone_buzz(2.0) * 0.6, 0.25)
add("fix", w("fix", "there") + 6, pop(500, 0.25), 0.6)
add("fix", w("fix", "there") + 8, chime((1319, 1568, 2093)), 0.45)

# 8 recap
for k, word in enumerate(["fly", "spot", "pin", "fix"]):
    add("recap", w("recap", word) - 2, pop(520 + k * 110, 0.18), 0.6, -0.3 + k * 0.2)
add("recap", w("recap", "repeat") - 2, whoosh(0.5, 300, 3000), 0.35)
add("recap", w("recap", "repeat"), chime((784, 988, 1175, 1568), 0.08), 0.35)

# 9 end
add("end", w("end", "cityvision") - 4, pop(520, 0.3), 0.7)
add("end", 26, knock(), 0.4)
add("end", w("end", "book") - 4, pop(760, 0.16), 0.5)
add("end", w("end", "book") + 10, chime((1047, 1319, 1568, 2093)), 0.35)
add("end", 214, whoosh(0.55, 300, 4000), 0.45)

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

mixer.master(ROOT / "public/howto/sfx.wav")
