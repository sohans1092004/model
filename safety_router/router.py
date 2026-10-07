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
from contextlib import contextmanager
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


EXACT_ONLY_LANGUAGES = ("te", "ta", "kn")


def route_with_indic(probs: dict[str, float], supported: list[str], floor: float = 0.2) -> list[str]:
    """route(), except when Telugu / Tamil / Kannada is the most likely language: then ALL of the supported
    Telugu / Tamil / Kannada, plus English / Hindi only if they have at least `floor` of the (renormalised)
    probability. Segments led by English or Hindi are routed exactly as before (route(0.95)).
    Why: Whisper small is rarely 95 % sure of these languages, so route() also sent their speech to English (39-59 %
    of segments) and Hindi, which then 'heard' English/Hindi phrases in it -- every false ask on the te/ta/kn
    YouTube test (route_study.py, 715 segments: English share 3-16 % with this rule, every cry clip still reaches
    its own system). All three together because Whisper confuses them with each other: a real Telugu "I'm not safe"
    was 25 % Kannada and only Kannada was run. Costs IndicConformer up to 3 runs on such a segment.
    ponytail: floor tuned on that one sample; an English cry inside a Tamil-led segment needs P(en) >= 0.2."""
    p = {k: probs.get(k, 0.0) for k in supported}
    total = sum(p.values())
    top = max(supported, key=p.get) if total > 0 else None
    if top not in EXACT_ONLY_LANGUAGES:
        return route(probs, supported)
    by_p = sorted(supported, key=p.get, reverse=True)
    return [k for k in by_p if k in EXACT_ONLY_LANGUAGES] + [k for k in by_p if k not in EXACT_ONLY_LANGUAGES
                                                            and p[k] / total >= floor]


def combine(decisions: dict[str, str], scream_fired: bool = False) -> str:
    final = max(decisions.values(), key=LEVEL.get, default="none")
    return "VERIFY" if final == "none" and scream_fired else final


@contextmanager
def _keep_cuda_device():
    """CTranslate2 on another GPU (UDK_HINDI_DEVICE=cuda:1) leaves this thread's current CUDA device switched to it;
    every later plain "cuda" tensor (BEATs, the English models) would then land on the wrong GPU and crash
    ("weight is on cuda:0 ... other tensors on cuda:1"). Put the thread's device back afterwards."""
    try:
        import torch
        before = torch.cuda.current_device() if torch.cuda.is_available() else None
    except Exception:
        before = None
    try:
        yield
    finally:
        if before is not None:
            torch.cuda.set_device(before)


class WhisperLanguageID:
    """P(language) for one segment from Whisper small's language detection (one encoder pass, ~60 ms on a T4).
    Works on short audio, unlike VoxLingua107 (unreliable under ~6 s per Model/language_id.py)."""

    def __init__(self, device: str = "cuda", model_size: str = "small"):
        from faster_whisper import WhisperModel
        kind, _, index = device.partition(":")  # "cuda:1" -> second GPU
        import os
        threads = int(os.environ.get("UDK_CPU_THREADS", "0") or 0) if kind == "cpu" else 0  # see stt.cpu_threads
        with _keep_cuda_device():
            self.model = WhisperModel(model_size, device=kind, device_index=int(index or 0),
                                      compute_type="float16" if kind == "cuda" else "int8", cpu_threads=threads)

    def __call__(self, pcm: bytes) -> dict[str, float]:
        import numpy as np
        audio = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
        with _keep_cuda_device():
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
