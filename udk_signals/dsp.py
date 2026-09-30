"""Small, dependency-free signal measurements (floats in [-1, 1], any sample rate).

Used by the condition estimator and the test fixtures. Deliberately simple and deterministic:
level, clipping, frame-energy SNR estimate, Goertzel band energy. Not a model.
"""
from __future__ import annotations

import math


def rms(x) -> float:
    return math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0


def dbfs(x) -> float:
    r = rms(x)
    return 20 * math.log10(r) if r > 0 else -120.0


def clipping_ratio(x, level: float = 0.999) -> float:
    return sum(1 for v in x if abs(v) >= level) / len(x) if x else 0.0


def frames(x, n: int):
    return [x[i:i + n] for i in range(0, len(x) - n + 1, n)]


def snr_estimate_db(x, sr: int, frame_s: float = 0.02) -> float | None:
    """90th-percentile frame energy over 10th-percentile frame energy (speech peaks vs floor)."""
    fr = frames(x, max(1, int(sr * frame_s)))
    if len(fr) < 10:
        return None
    e = sorted(sum(v * v for v in f) / len(f) for f in fr)
    lo, hi = e[len(e) // 10], e[(9 * len(e)) // 10]
    if hi <= 0:
        return None
    return 99.0 if lo <= 0 else min(99.0, 10 * math.log10(hi / lo))  # silent floor between words: capped high


def goertzel_power(x, sr: int, freq: float) -> float:
    k = 2 * math.cos(2 * math.pi * freq / sr)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + k * s1 - s2
        s2, s1 = s1, s0
    return (s1 * s1 + s2 * s2 - k * s1 * s2) / (len(x) ** 2)


def band_power(x, sr: int, freqs) -> float:
    return sum(goertzel_power(x, sr, f) for f in freqs)
