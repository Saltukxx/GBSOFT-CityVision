"""Shared sound-design instruments + a frame-locked mixer for the CityVision reels."""
import json
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000
rng = np.random.default_rng(7)


def tt(d):
    return np.arange(int(d * SR)) / SR


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="high", fs=SR, output="sos"), x)


def fade(x, a=0.002, b=0.01):
    na, nb = int(a * SR), int(b * SR)
    x = x.copy()
    if na:
        x[:na] *= np.linspace(0, 1, na)
    if nb:
        x[-nb:] *= np.linspace(1, 0, nb)
    return x


def sweep_sine(f0, f1, d, curve=4.0):
    t_ = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t_ * curve / d)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


# ───────── instruments ─────────
def pop(f=650, d=0.16):
    x = sweep_sine(f * 1.9, f, d, 9) * np.exp(-tt(d) * 26)
    click = hp(rng.standard_normal(len(x)), 2000) * np.exp(-tt(d) * 400) * 0.25
    return fade(x + click)


def blip(f=900, d=0.07):
    return fade(np.sin(2 * np.pi * f * tt(d)) * np.exp(-tt(d) * 60))


def tick(f=2600):
    d = 0.03
    x = np.sin(2 * np.pi * f * tt(d)) * np.exp(-tt(d) * 220)
    n = hp(rng.standard_normal(len(x)), 3000) * np.exp(-tt(d) * 600) * 0.4
    return fade(x + n, 0.0005, 0.005)


def whoosh(d=0.45, lo=300, hi=3500, rising=True):
    n = int(d * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    hop = int(0.01 * SR)
    for i in range(0, n, hop):
        p = i / n
        c = lo * (hi / lo) ** (p if rising else 1 - p)
        seg = noise[max(0, i - 2000) : i + hop]
        y = bp(seg, max(60, c * 0.6), min(SR / 2 - 100, c * 1.6))
        out[i : i + hop] = y[-min(hop, n - i) :]
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return fade(out * env * 1.3)


def slam():
    d = 0.9
    t_ = tt(d)
    body = sweep_sine(110, 42, d, 6) * np.exp(-t_ * 4.5)
    hit = lp(rng.standard_normal(len(t_)), 1800) * np.exp(-t_ * 22) * 0.9
    snap = hp(rng.standard_normal(len(t_)), 2500) * np.exp(-t_ * 60) * 0.5
    return fade(np.tanh((body * 1.3 + hit + snap) * 1.4))


def shatter():
    d = 0.7
    out = np.zeros(int(d * SR))
    for _ in range(46):
        f = rng.uniform(2500, 9000)
        s = int(rng.uniform(0, 0.35) * SR)
        dd = rng.uniform(0.02, 0.09)
        x = np.sin(2 * np.pi * f * tt(dd)) * np.exp(-tt(dd) * rng.uniform(40, 90))
        out[s : s + len(x)] += x * rng.uniform(0.1, 0.35)
    burst = hp(rng.standard_normal(len(out)), 3000) * np.exp(-tt(d) * 14) * 0.35
    return fade(out + burst)


def boing(f=170, d=0.35):
    t_ = tt(d)
    fm = f * (1 + 0.18 * np.sin(2 * np.pi * 14 * t_) * np.exp(-t_ * 8))
    x = np.sin(2 * np.pi * np.cumsum(fm) / SR) * np.exp(-t_ * 9)
    return fade(np.tanh(x * 1.5))


def inflate(d=0.9):
    t_ = tt(d)
    f = 160 + 420 * (t_ / d) ** 1.4
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 18 * t_))
    air = bp(rng.standard_normal(len(t_)), 600, 2400) * 0.25
    env = np.minimum(1, t_ / 0.1) * np.exp(-np.maximum(0, t_ - d + 0.15) * 20)
    return fade((x + air) * env)


def bubble(f=500):
    d = 0.06
    return fade(sweep_sine(f, f * 2.2, d, -2) * np.exp(-tt(d) * 40))


def bell(f=1320, d=1.4, partials=(1, 2.76, 5.4), amps=(1, 0.45, 0.2)):
    t_ = tt(d)
    x = sum(a * np.sin(2 * np.pi * f * p * t_) * np.exp(-t_ * (3 + p * 2)) for p, a in zip(partials, amps))
    return fade(x, 0.001, 0.05)


def ding():
    a = bell(1568, 1.1)
    b = bell(2093, 1.1)
    out = np.zeros(len(a) + int(0.09 * SR))
    out[: len(a)] += a
    out[int(0.09 * SR) :] += b * 0.8
    return out * 0.6


def chime(notes=(1047, 1319, 1568, 2093), gap=0.07):
    out = np.zeros(int((gap * len(notes) + 1.4) * SR))
    for i, f in enumerate(notes):
        b = bell(f, 1.3)
        s = int(i * gap * SR)
        out[s : s + len(b)] += b * (0.8 - i * 0.1)
    return out * 0.55


def knock():
    d = 0.12
    t_ = tt(d)
    x = np.sin(2 * np.pi * 210 * t_) * np.exp(-t_ * 45) + lp(rng.standard_normal(len(t_)), 1200) * np.exp(-t_ * 90) * 0.6
    return fade(x)


def ring(d=0.9):
    t_ = tt(d)
    tone = np.sin(2 * np.pi * 1400 * t_) + np.sin(2 * np.pi * 1750 * t_)
    am = (np.sin(2 * np.pi * 22 * t_) > 0).astype(float)
    am = lp(am, 300)
    gate = ((t_ % 0.45) < 0.32).astype(float)
    gate = lp(gate, 60)
    return fade(tone * am * gate * 0.35, 0.005, 0.05)


def crunch(d=0.9):
    out = np.zeros(int(d * SR))
    for _ in range(70):
        s = int(rng.uniform(0, d - 0.05) * SR)
        g = lp(rng.standard_normal(int(0.025 * SR)), rng.uniform(600, 2500)) * np.exp(-tt(0.025) * 120)
        out[s : s + len(g)] += g * rng.uniform(0.2, 0.6)
    rumble = lp(rng.standard_normal(len(out)), 120) * 0.8
    env = np.sin(np.pi * np.linspace(0, 1, len(out)))
    return fade((out + rumble) * env)


def drone_buzz(d=1.6):
    t_ = tt(d)
    saw = signal.sawtooth(2 * np.pi * 190 * t_) * 0.5 + signal.sawtooth(2 * np.pi * 193 * t_) * 0.5
    x = lp(saw, 1400) * (0.75 + 0.25 * np.sin(2 * np.pi * 33 * t_))
    env = np.sin(np.pi * np.linspace(0, 1, len(t_))) ** 1.5
    return fade(x * env * 0.5)


def swell(d=1.6, f=262):
    t_ = tt(d)
    x = sum(np.sin(2 * np.pi * f * m * t_ + m) for m in (1, 1.5, 2, 3)) / 4
    env = np.minimum(1, t_ / 0.5) * np.exp(-np.maximum(0, t_ - 0.6) * 2.2)
    return fade(lp(x, 2500) * env)


def thud():
    d = 0.35
    t_ = tt(d)
    return fade(sweep_sine(120, 55, d, 8) * np.exp(-t_ * 12) + lp(rng.standard_normal(len(t_)), 600) * np.exp(-t_ * 40) * 0.4)




class Mixer:
    """Places sounds on scene-relative frames of a beat timeline (lengths in beats)."""

    def __init__(self, timeline_path):
        tl = json.loads(Path(timeline_path).read_text())
        self.fps = tl["fps"]
        beatf = 3600 / tl["bpm"]
        bf = lambda b: int(np.floor(b * beatf + 0.5))
        self.starts, self.kinds, beats = {}, {}, 0
        for sid, n, kind in tl["scenes"]:
            self.starts[sid] = bf(beats)
            self.kinds[sid] = kind
            beats += n
        self.total = bf(beats)
        n = int(self.total / self.fps * SR) + SR
        self.L = np.zeros(n)
        self.R = np.zeros(n)

    def add(self, scene, frame, x, gain=1.0, pan=0.0):
        i = int((self.starts[scene] + frame) / self.fps * SR)
        x = x * gain
        if i < 0:  # sound starts before the reel: keep only its audible tail
            x, i = x[-i:], 0
        n = min(len(x), len(self.L) - i)
        if n <= 0:
            return
        self.L[i : i + n] += x[:n] * np.sqrt((1 - pan) / 2) * 1.414
        self.R[i : i + n] += x[:n] * np.sqrt((1 + pan) / 2) * 1.414

    def master(self, out):
        mix = np.stack([self.L, self.R])[:, : int(self.total / self.fps * SR)]
        ir_t = tt(0.7)
        ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 7)
        ir = lp(ir, 5000)
        ir /= np.sqrt((ir**2).sum())
        wet = np.stack([signal.fftconvolve(ch, ir)[: mix.shape[1]] for ch in mix])
        mix = mix + wet * 0.18
        mix = hp(mix, 35)
        mix = mix / np.abs(mix).max() * 10 ** (-3 / 20)
        pcm = (np.clip(mix.T, -1, 1) * 32767).astype("<i2")
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        print("wrote", out, f"{mix.shape[1] / SR:.2f}s")
