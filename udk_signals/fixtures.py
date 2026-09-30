"""TEST FIXTURES ONLY: deterministic toy audio and toy detectors for the Phase 4 layer.

Toy "voices" are harmonic tones (male ~120/150 Hz, female ~220 Hz fundamentals); screams are
loud 2 kHz tones with vibrato; crying is a ~400 Hz voice amplitude-modulated at 4 Hz; traffic is
seeded low-frequency noise; crowd babble is several quiet voices; pocket = low-pass + attenuation;
far-field = attenuation + echo. The detectors below exploit exactly these constructions. They are
not models, prove nothing about real audio, and must never be used to choose a real model.
"""
from __future__ import annotations

import math
import random

from udk_signals.dsp import band_power, dbfs, goertzel_power, rms
from udk_signals.evidence import NEGATIVE, POSITIVE, UNCERTAIN, Evidence, unavailable

SR = 8000
F0_BANK = tuple(range(100, 301, 10))


def voice(f0: float, dur: float = 0.5, amp: float = 0.3, sr: int = SR):
    """Harmonic tone with a small 2.5 kHz 'fricative' component, gated into ~5 syllables/s
    (speech has pauses: this is what lets the SNR and muffling measurements mean something)."""
    n = int(dur * sr)
    out = []
    for i in range(n):
        gate = 1.0 if (i / sr * 5) % 1.0 < 0.65 else 0.0
        v = sum((0.6 ** (k - 1)) * math.sin(2 * math.pi * k * f0 * i / sr) for k in (1, 2, 3)) / 1.96
        v += 0.08 * math.sin(2 * math.pi * 2500 * i / sr)
        out.append(amp * gate * v)
    return out


def scream(dur: float = 0.5, amp: float = 0.8, sr: int = SR):
    return [amp * math.sin(2 * math.pi * (2000 * i / sr + 3 * math.sin(2 * math.pi * 6 * i / sr))) for i in range(int(dur * sr))]


def cry(dur: float = 0.5, amp: float = 0.5, sr: int = SR):
    return [amp * (0.55 + 0.45 * math.sin(2 * math.pi * 4 * i / sr)) * math.sin(2 * math.pi * 400 * i / sr) for i in range(int(dur * sr))]


def traffic(dur: float = 0.5, amp: float = 0.08, seed: int = 1, sr: int = SR):
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(int(dur * sr))]
    k = 40  # moving average ~ low-pass below ~100 Hz at 8 kHz
    out, acc = [], 0.0
    for i, v in enumerate(raw):
        acc += v - (raw[i - k] if i >= k else 0.0)
        out.append(amp * acc / k * 4)
    return out


def crowd(dur: float = 0.5, amp: float = 0.05, sr: int = SR):
    """Several quiet voices whose syllables do NOT line up (rotated), so the babble fills pauses."""
    vs = [voice(f, dur, amp, sr) for f in (170, 190, 260, 280)]
    return mix(*[v[k * 397 % len(v):] + v[:k * 397 % len(v)] for k, v in enumerate(vs, 1)])


def mix(*xs):
    n = max(len(x) for x in xs)
    return [sum(x[i] if i < len(x) else 0.0 for x in xs) for i in range(n)]


def scale_db(x, db: float):
    g = 10 ** (db / 20)
    return [v * g for v in x]


def pocket(x):
    k, out, acc = 6, [], 0.0
    for i, v in enumerate(x):
        acc += v - (x[i - k] if i >= k else 0.0)
        out.append(acc / k * 0.5)
    return out


def far_field(x, sr: int = SR):
    d = int(0.03 * sr)
    return [0.3 * (v + 0.5 * (x[i - d] if i >= d else 0.0)) for i, v in enumerate(x)]


def clip(x, level: float = 0.2):
    return [max(-level, min(level, v)) / level for v in x]


def silence(dur: float = 0.5, sr: int = SR):
    return [0.0] * int(dur * sr)


class FixtureEmbedder:
    embedder_id = "fixture-f0-bank (TEST ONLY)"

    def embed(self, x, sr: int):
        if rms(x) < 1e-4:
            return None
        e = [goertzel_power(x, sr, f) for f in F0_BANK]
        n = math.sqrt(sum(v * v for v in e))
        return tuple(v / n for v in e) if n else None


class FixtureOverlapDetector:
    detector_id = "fixture-f0-peaks (TEST ONLY)"

    def __init__(self, rel_threshold: float = 0.02):
        self.rel = rel_threshold

    def detect(self, x, sr: int) -> Evidence:
        if dbfs(x) < -60:
            return unavailable("overlap", self.detector_id, "no speech energy")
        e = {f: goertzel_power(x, sr, f) for f in F0_BANK}
        voice_e = sum(e.values())
        other = band_power(x, sr, (400, 600, 800, 1000, 1500, 2000))
        if voice_e < other:
            return Evidence("overlap", UNCERTAIN, self.detector_id, "non-voice sound dominates the segment")
        top = max(e.values())
        med = sorted(e.values())[len(e) // 2]
        peaks = {f for f, v in e.items() if v >= self.rel * top and v >= 20 * med
                 and v >= e.get(f - 10, 0) and v >= e.get(f + 10, 0)}
        fund = sorted(f for f in peaks if f / 2 not in peaks)
        if not fund:
            return Evidence("overlap", UNCERTAIN, self.detector_id, "no voice fundamental found")
        if len(fund) == 1:
            return Evidence("overlap", NEGATIVE, self.detector_id, "one voice", detail={"n_speakers": 1})
        en = sorted((e[f] for f in fund), reverse=True)
        return Evidence("overlap", POSITIVE, self.detector_id, f"{len(fund)} voices", detail={
            "n_speakers": len(fund), "rel_db": round(10 * math.log10(en[1] / en[0]), 2), "fundamentals_hz": fund})


class FixtureAcousticSource:
    """TEST ONLY; unlike BEATs, this fixture may assert absence (NEGATIVE) on its own toy signals."""
    source_id = "fixture-acoustic (TEST ONLY)"

    def assess(self, x, sr: int, start_s=None, end_s=None) -> list[Evidence]:
        if dbfs(x) < -60:
            return [unavailable("acoustic_distress", self.source_id, "silence")]
        hf = band_power(x, sr, (1800, 1900, 2000, 2100, 2200))
        mid = band_power(x, sr, (380, 400, 420))
        voice_e = band_power(x, sr, F0_BANK)
        total = hf + mid + voice_e
        frames = [x[i:i + sr // 40] for i in range(0, len(x) - sr // 40 + 1, sr // 40)]
        fr = [rms(f) for f in frames]
        mean = sum(fr) / len(fr)
        mod = (max(fr) - min(fr)) / mean if mean else 0.0
        if hf / total > 0.5 and dbfs(x) > -20:
            return [Evidence("acoustic_distress", POSITIVE, self.source_id, "scream-like", score=hf / total, start_s=start_s, end_s=end_s,
                             detail={"class": "scream"})]
        if mid / total > 0.5 and mod > 0.8:
            return [Evidence("acoustic_distress", POSITIVE, self.source_id, "cry-like", score=mod, start_s=start_s, end_s=end_s,
                             detail={"class": "cry"})]
        return [Evidence("acoustic_distress", NEGATIVE, self.source_id, "no distress sound (fixture)", start_s=start_s, end_s=end_s)]
