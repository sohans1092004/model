"""Per-segment language routing over per-language distress systems (docs/hindi_distress_system.md, section 1).

    segment -> language ID -> route(): most likely languages until they sum to >= 0.95 (cap 3)
            -> run those languages' systems (in parallel) -> the highest decision wins
            -> scream trigger on every segment, whatever the route (sound is language-independent)

A language system is any callable  (pcm: bytes, start_ms: int, session) -> "ALERT" | "VERIFY" | "none".
Measured on a mixed English+Hindi test (route_eval.py), Hindi rule of 2026-10-05: Hindi cries 48/0/2 (alert/ask/missed),
English cries 18/18/14, 1 false ALERT in 351 benign Hindi segments.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

LEVEL = {"none": 0, "VERIFY": 1, "ALERT": 2}
System = Callable[[bytes, int, object], str]


def route(probs: dict[str, float], supported: list[str], mass: float = 0.95, cap: int = 3) -> list[str]:
    """Languages to run: the most likely supported ones until their (renormalised) probability reaches `mass`."""
    p = {k: probs.get(k, 0.0) for k in supported}
    total = sum(p.values())
    if total <= 0:
        return list(supported[:cap])  # language ID has no idea: listen with everything (up to cap)
    chosen, acc = [], 0.0
    for lang in sorted(p, key=p.get, reverse=True):
        chosen.append(lang)
        acc += p[lang] / total
        if acc >= mass or len(chosen) == cap:
            break
    return chosen


def combine(decisions: dict[str, str], scream_fired: bool = False) -> str:
    final = max(decisions.values(), key=LEVEL.get, default="none")
    return "VERIFY" if final == "none" and scream_fired else final


class WhisperLanguageID:
    """P(language) for one segment from Whisper small's language detection (one encoder pass, ~60 ms on a T4).
    Works on short audio, unlike VoxLingua107 (unreliable under ~6 s per Model/language_id.py)."""

    def __init__(self, device: str = "cuda", model_size: str = "small"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_size, device=device, compute_type="float16" if device == "cuda" else "int8")

    def __call__(self, pcm: bytes) -> dict[str, float]:
        import numpy as np
        audio = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
        _, _, probs = self.model.detect_language(audio=audio)
        p = dict(probs)
        p["hi"] = p.get("hi", 0.0) + p.get("ur", 0.0)  # spoken Hindi and Urdu are one language for this purpose
        return p


@dataclass
class RouteResult:
    final: str                    # ALERT / VERIFY / none
    languages: list[str]          # systems that ran
    decisions: dict[str, str]     # per-language decision
    scream: bool
    probs: dict[str, float]


class SegmentRouter:
    def __init__(self, systems: dict[str, System], language_id: Callable[[bytes], dict[str, float]],
                 scream: Callable[[bytes], bool] | None = None, mass: float = 0.95, cap: int = 3):
        self.systems, self.lid, self.scream = systems, language_id, scream
        self.mass, self.cap = mass, cap
        self.pool = ThreadPoolExecutor(max_workers=cap + 1)

    def process(self, pcm: bytes, start_ms: int, sessions: dict[str, object]) -> RouteResult:
        """`sessions[lang]` = that system's per-session state (e.g. a HindiStream, the English UDKEngine)."""
        probs = self.lid(pcm)
        langs = route(probs, list(self.systems), self.mass, self.cap)
        scream_job = self.pool.submit(self.scream, pcm) if self.scream else None
        jobs = {lang: self.pool.submit(self.systems[lang], pcm, start_ms, sessions.get(lang)) for lang in langs}
        decisions = {lang: j.result() for lang, j in jobs.items()}
        fired = bool(scream_job.result()) if scream_job else False
        return RouteResult(combine(decisions, fired), langs, decisions, fired, {k: probs.get(k, 0.0) for k in self.systems})
