"""Voiceovers for the CityVision reels (ElevenLabs, voice "Sarah").

Each line is its own clip, placed on a scene-relative frame so it stays locked to the
beat grid in src/promo/timeline.json. Also writes a ducked copy of the music bed.

    python3 scripts/vo.py promo            # generate missing clips, build tracks
    python3 scripts/vo.py howto --measure  # only generate clips and print their lengths
    python3 scripts/vo.py promo --regen    # re-generate every clip

Needs ELEVENLABS_API_KEY in docs/cityvision-video/.env (git-ignored).
Outputs (per project): public/<project>/vo.wav, music_duck.wav, sfx_duck.wav
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
VOICE = "EXAVITQu4vr4xnSDxMaL"  # Sarah — mature, reassuring, confident
MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.22, "use_speaker_boost": True, "speed": 1.06}

PROMO_LINES = [
    ("map", 8, "Your complaint map says twelve."),
    ("wrong", 3, "Wrong."),
    ("wrong", 36, "By a lot."),
    ("says", 6, "It says twelve issues."),
    ("says", 112, "There are actually a hundred and forty-seven."),
    ("where", 30, "So where were they hiding?"),
    ("feed", 34, "Potholes."),
    ("feed", 94 + 34, "Cracks."),
    ("feed", 188 + 34, "Overflowing bins."),
    ("feed", 282 + 34, "Illegal dumping."),
    ("findout", 6, "And you find out from a phone call."),
    ("km", 4, "Three hundred eighty kilometres."),
    ("logo", 6, "Meet CityVision."),
    ("every", 6, "Every flight. Every street. Every defect. One map."),
    ("real", 46, "That's the real number."),
    ("notify", 10, "A new pothole? It taps you on the shoulder."),
    ("onetap", 4, "One tap."),
    ("onetap", 74, "Crew sent."),
    ("morning", 10, "Every morning, before the first shift,"),
    ("morning", 134, "you know exactly where to go."),
    ("fewer", 10, "Fewer complaints."),
    ("fewer", 140, "Safer streets."),
    ("end", 8, "CityVision. Book your demo."),
]

HOWTO_LINES = [
    ("hook", 6, "How does CityVision work? Thirty seconds."),
    ("fly", 6, "One. A drone flies a planned route. Same streets, every time."),
    ("spot", 6, "Two. AI checks every frame for potholes, cracks and road damage."),
    ("pin", 2, "Three. Each one gets a photo and a GPS pin."),
    ("merge", 12, "Four. Seen on three flights? Still one issue. One work order."),
    ("blur", 6, "Five. Faces and number plates are blurred in every photo."),
    ("approve", 6, "Six. Someone on your team approves it."),
    ("fix", 6, "Seven. The crew drives straight there."),
    ("recap", 6, "Fly. Spot. Pin. Fix. Repeat."),
    ("end", 8, "CityVision. Book your demo."),
]

GAME_LINES = [
    ("hook", 6, "Can you spot it faster than a drone? You get three seconds."),
    ("r1", 6, "Round one. Find the pothole."),
    ("r1", "REVEAL", "Easy."),
    ("r2", 6, "Round two. Find the road damage."),
    ("r2", "REVEAL", "Got it? It did."),
    ("r3", 6, "Round three. Find the crack."),
    ("r3", "REVEAL", "Most people miss this one."),
    ("score", 6, "Three for three. How did you do?"),
    ("map", 6, "Now picture that on every street in your city."),
    ("end", 8, "CityVision. Book your demo."),
]

BILL, JESSICA, CHRIS = "pqHfZKP75CvOlQylNhV4", "cgSgspJ2msm6clMCkdW9", "iP95p4xoKVk53GoZ742B"
RESIDENT = {"stability": 0.38, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True, "speed": 0.98}

MAYOR_LINES = [
    ("l1", 6, "Dear Mayor. There's been a hole outside my door since March. My wife tripped on it last week.", BILL),
    ("l2", 6, "Dear Mayor. The road on our street is cracking. I've called twice. Nobody came.", JESSICA),
    ("l3", 6, "Dear Mayor. That's my second tyre this year. Second.", CHRIS),
    ("turn", 4, "What if the city found it first?"),
    ("payoff", 6, "CityVision flies your streets on a schedule and puts every issue on the map. Before anyone has to write."),
    ("close", 6, "Dear Mayor. We found it first."),
    ("end", 8, "Book your demo."),
]

EYES_LINES = [
    ("map", 26, "Same street. Different eyes."),
    ("end", 8, "CityVision. Book your demo."),
]

WRAPPED_LINES = [
    ("intro", 132, "Our flights. Wrapped."),
    ("air", 6, "Four flights. Six minutes in the air."),
    ("frames", 6, "Ten thousand, nine hundred and seven frames."),
    ("seen", 6, "Nine hundred and fifty-eight times, it spotted damage."),
    ("issues", 6, "Merged into seventy-five real issues."),
    ("top", 6, "Top category: road damage."),
    ("best", 6, "Strongest find? A pothole. Ninety-eight percent sure."),
    ("tossed", 6, "Three hundred and sixty-five maybes. Thrown out."),
    ("human", 6, "Twelve flagged for a human to check."),
    ("people", 6, "It saw people over a thousand times. Every face, blurred."),
    ("outro", 6, "All of that, in half an hour. Now imagine a year."),
    ("end", 8, "CityVision. Book your demo."),
]

PROJECTS = {
    # (scene, frame within scene @60fps, text)
    "promo": {
        "timeline": "src/promo/timeline.json",
        "out": "public/promo",
        "lines": PROMO_LINES,
    },
    "howto": {
        "timeline": "src/howto/timeline.json",
        "out": "public/howto",
        "lines": HOWTO_LINES,
        "timestamps": True,
        "words": "src/howto/vo_words.json",
    },
    "wrapped": {
        "timeline": "src/wrapped/timeline.json",
        "out": "public/wrapped",
        "lines": WRAPPED_LINES,
        "timestamps": True,
        "words": "src/wrapped/vo_words.json",
    },
    "eyes": {
        "timeline": "src/eyes/timeline.json",
        "out": "public/eyes",
        "lines": EYES_LINES,
        "timestamps": True,
        "words": "src/eyes/vo_words.json",
    },
    "mayor": {
        "timeline": "src/mayor/timeline.json",
        "out": "public/mayor",
        "lines": MAYOR_LINES,
        "timestamps": True,
        "words": "src/mayor/vo_words.json",
    },
    "game": {
        "timeline": "src/game/timeline.json",
        "out": "public/game",
        "lines": GAME_LINES,
        "timestamps": True,
        "words": "src/game/vo_words.json",
    },
}

NAME = next((a for a in sys.argv[1:] if not a.startswith("--")), "promo")
P = PROJECTS[NAME]
LINES = P["lines"]
OUT = ROOT / P["out"]

CACHE = ROOT / "vo/clips" / NAME
CACHE.mkdir(parents=True, exist_ok=True)


def api_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("ELEVENLABS_API_KEY missing in .env")


def clip(i, text, regen, voice=None):
    voice = voice or VOICE
    settings = SETTINGS if voice == VOICE else RESIDENT
    # context only from the same speaker, so each voice keeps its own prosody
    same = lambda j: 0 <= j < len(LINES) and (LINES[j][3] if len(LINES[j]) > 3 else VOICE) == voice
    prev_t = LINES[i - 1][2] if i and same(i - 1) else ""
    next_t = LINES[i + 1][2] if same(i + 1) else ""
    if voice == VOICE and not P.get("timestamps"):
        prev_t = LINES[i - 1][2] if i else ""
        next_t = LINES[i + 1][2] if i + 1 < len(LINES) else ""
    ts = P.get("timestamps", False)
    key_parts = [voice, MODEL, settings, text, prev_t, next_t] + (["ts"] if ts else [])
    key = hashlib.sha1(json.dumps(key_parts).encode()).hexdigest()[:10]
    mp3 = CACHE / f"{i:02d}-{key}.mp3"
    align_p = mp3.with_suffix(".json")
    if ts and (regen or not mp3.exists()):
        body = json.dumps(
            {"text": text, "model_id": MODEL, "voice_settings": settings, "previous_text": prev_t, "next_text": next_t}
        ).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
            data=body,
            headers={"xi-api-key": api_key(), "Content-Type": "application/json"},
        )
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
        mp3.write_bytes(base64.b64decode(d["audio_base64"]))
        align_p.write_text(json.dumps(d["alignment"]))
        print("  generated", mp3.name, repr(text))
    elif regen or not mp3.exists():
        body = json.dumps(
            {"text": text, "model_id": MODEL, "voice_settings": settings, "previous_text": prev_t, "next_text": next_t}
        ).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
            data=body,
            headers={"xi-api-key": api_key(), "Content-Type": "application/json"},
        )
        mp3.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        print("  generated", mp3.name, repr(text))
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    x = np.frombuffer(raw, np.float32).astype(float)
    # trim leading / trailing silence (keep 20 ms head, 60 ms tail)
    env = np.convolve(np.abs(x), np.ones(240) / 240, "same")
    on = np.where(env > 0.01)[0]
    a = max(0, on[0] - int(0.02 * SR))
    b = min(len(x), on[-1] + int(0.06 * SR))
    words = []
    if align_p.exists():
        al = json.loads(align_p.read_text())
        chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
        cur, w0 = "", None
        for c, t0, t1 in zip(chars + [" "], st + [0], en + [0]):
            if c.isalnum() or c in "'-":
                if not cur:
                    w0 = t0
                cur += c
            elif cur:
                words.append((cur.lower(), w0 - a / SR))
                cur = ""
    return x[a:b], words


def read_wav(p):
    with wave.open(str(p)) as w:
        ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
        d = np.frombuffer(w.readframes(n), "<i2").astype(float) / 32768
    d = d.reshape(-1, ch).T
    if sr != SR:
        d = signal.resample_poly(d, SR, sr, axis=1)
    return d


def write_wav(p, x):
    x = np.atleast_2d(x)
    if x.shape[0] == 1:
        x = np.vstack([x, x])
    pcm = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    regen = "--regen" in sys.argv
    if "--measure" in sys.argv:
        for i, (sid, fr, text, *v) in enumerate(LINES):
            x, _ = clip(i, text, regen, v[0] if v else None)
            print(f"{len(x) / SR:5.2f}s  {sid:8s} {text}")
        return
    TL = json.loads((ROOT / P["timeline"]).read_text())
    beatf = 3600 / TL["bpm"]
    bf = lambda b: int(np.floor(b * beatf + 0.5))
    starts, sbeat, beats = {}, {}, 0
    for sid, n, _ in TL["scenes"]:
        starts[sid] = bf(beats)
        sbeat[sid] = beats
        beats += n
    marks = TL.get("marks", {})

    def frame_of(sid, fr):
        # a string frame is a beat mark inside the scene (e.g. "REVEAL"), landing 6 frames after the beat
        return bf(sbeat[sid] + marks[fr]) - starts[sid] + 6 if isinstance(fr, str) else fr

    TOTAL = bf(beats)
    N = int(TOTAL / 60 * SR)
    vo = np.zeros(N)
    spans = []
    word_frames = {}
    for i, (sid, fr, text, *v) in enumerate(LINES):
        x, words = clip(i, text, regen, v[0] if v else None)
        fr = frame_of(sid, fr)
        for w, wt in words:
            word_frames.setdefault(sid, []).append([w, int(round(fr + wt * 60))])
        t0 = (starts[sid] + fr) / 60
        s = int(t0 * SR)
        n = min(len(x), N - s)
        vo[s : s + n] += x[:n]
        spans.append((t0, t0 + len(x) / SR, text, sid))
    # report timing so overlaps are visible
    for k, (a, b, text, sid) in enumerate(spans):
        nxt = spans[k + 1][0] if k + 1 < len(spans) else TOTAL / 60
        flag = "  <-- OVERLAPS next line" if b > nxt else ""
        print(f"{a:6.2f}–{b:6.2f}s  {sid:8s} {text}{flag}")

    # voice chain: gentle high-pass, presence lift, normalise to -16 dBFS RMS on speech
    vo = signal.sosfilt(signal.butter(2, 90, "high", fs=SR, output="sos"), vo)
    pres = signal.sosfilt(signal.butter(2, [2500, 6000], "band", fs=SR, output="sos"), vo)
    vo = vo + pres * 0.25
    speech = np.abs(vo) > 0.01
    rms = np.sqrt((vo[speech] ** 2).mean())
    vo *= 10 ** (-16 / 20) / rms
    vo = np.tanh(vo * 1.1) / 1.1  # soft limiter

    # ducking envelope from voice activity (40 ms attack, 250 ms release)
    act = np.convolve(np.abs(vo), np.ones(960) / 960, "same") > 0.004
    env = np.zeros(N)
    g = 0.0
    att, rel = 1 - np.exp(-1 / (0.04 * SR)), 1 - np.exp(-1 / (0.25 * SR))
    for i in range(N):
        tgt = 1.0 if act[i] else 0.0
        g += (tgt - g) * (att if tgt > g else rel)
        env[i] = g
    music = read_wav(OUT / "music.wav")[:, :N]
    music = np.pad(music, ((0, 0), (0, N - music.shape[1])))
    sfx = read_wav(OUT / "sfx.wav")[:, :N]
    sfx = np.pad(sfx, ((0, 0), (0, N - sfx.shape[1])))
    music_duck = music * (1 - env * (1 - 10 ** (-7 / 20)))  # -7 dB under voice
    sfx_duck = sfx * (1 - env * (1 - 10 ** (-3 / 20)))  # -3 dB under voice

    if P.get("words"):
        (ROOT / P["words"]).write_text(json.dumps(word_frames, indent=1))
        print("wrote", P["words"])
    OUT.mkdir(parents=True, exist_ok=True)
    write_wav(OUT / "vo.wav", vo)
    write_wav(OUT / "music_duck.wav", music_duck)
    write_wav(OUT / "sfx_duck.wav", sfx_duck)
    print("wrote vo.wav, music_duck.wav, sfx_duck.wav")


if __name__ == "__main__":
    main()
