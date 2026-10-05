"""Per-user custom UDK, as in custom_udk_enrol_detect_v2.ipynb (MODE="text"): each user records their own phrase
4-6 times during app setup and the app sends the recordings in one refresh call; the service transcribes them
once, stores the profile per user (not the audio),
and checks it first on every segment: the phrase in the gate's own Whisper (medium.en, as in
the notebook) or Parakeet transcript -> TRIGGER_ALL straight away (no intent veto); otherwise the general model
decides, unchanged.

Notebook numbers (one speaker, 5 setup clips): 27/30 simulated conditions caught with Whisper + Parakeet (muffled
"pocket" audio is the weak case, 2/5); 1/17 near-miss sentences detected (that clip was heard exactly as the phrase);
"...worst place...", "is hogwarts...", "...the universe" rejected. Its MFCC-DTW sound match is not used: real phrase
clips scored worse on it than unrelated sentences. No speaker check: anyone saying the phrase matches.

Variants are the gate Whisper's own transcripts of the setup clips, so they are spelled the way the gate hears live
speech ("the blue bird" is heard as "the bluebird").
"""
from __future__ import annotations

import base64
import io
import re

from rapidfuzz import fuzz

MIN_CLIPS, MAX_CLIPS = 4, 6
MIN_WORDS, MAX_CHARS = 3, 40   # notebook values; MAX_CHARS 25 was also discussed
MIN_STABILITY = 80.0


def norm(text: str) -> str:
    """The notebook's normalisation: lowercase, keep a-z, digits, spaces (and Telugu)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9ఀ-౿ ]", "", (text or "").lower())).strip()


def build_profile(whisper_texts: list[str]) -> dict:
    """Whisper's transcript of each setup clip -> profile. `ok` False comes with a `reason` the app can show."""
    heard = [norm(t) for t in whisper_texts if norm(t)]
    if len(heard) < 2:
        return {"ok": False, "reason": "no speech recognised in the recordings", "variants": []}
    sims = [fuzz.ratio(a, b) for i, a in enumerate(heard) for b in heard[i + 1:]]
    stability = sum(sims) / len(sims)
    phrase = max(heard, key=lambda a: sum(fuzz.ratio(a, b) for b in heard))  # the most typical transcript
    reason = (f"phrase must have at least {MIN_WORDS} words" if len(phrase.split()) < MIN_WORDS else
              f"phrase must be at most {MAX_CHARS} characters" if len(phrase) > MAX_CHARS else
              f"recordings were heard differently ({stability:.0f}% alike, need {MIN_STABILITY:.0f}%); "
              "record again clearly, preferably with common words" if stability < MIN_STABILITY else None)
    return {"ok": reason is None, "phrase": phrase, "stability": round(stability, 1), "reason": reason,
            "variants": sorted(set(heard))}


def detect(texts: list[str], profile: dict) -> bool:
    """True when any variant appears as whole words in the segment's Whisper or Parakeet transcript."""
    padded = [f" {norm(t)} " for t in texts if t]
    return any(f" {v} " in t for t in padded for v in profile.get("variants", []))


def decode_recordings(files: list[str]) -> list[bytes]:
    """The setup recordings the app sends to refresh, base64 audio files (anything PyAV decodes: wav, webm, m4a, mp3,
    ogg), as 16 kHz mono int16 PCM. Raises on a file that is not decodable audio."""
    return [_to_pcm16k(base64.b64decode(f, validate=True)) for f in files]


def _to_pcm16k(audio_file: bytes) -> bytes:
    """Any audio file -> 16 kHz mono int16 PCM, via PyAV (a dependency of faster-whisper, so always installed)."""
    import av
    import numpy as np

    with av.open(io.BytesIO(audio_file)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        frames = []
        for packet in container.demux(stream):
            try:
                decoded = packet.decode()
            except av.error.InvalidDataError:
                continue  # one damaged packet: skip it like ffmpeg does, don't lose the whole recording
            for frame in decoded:
                frames += resampler.resample(frame)
        frames += resampler.resample(None)  # flush what the resampler still holds
    if not frames:
        raise ValueError("no decodable audio")
    return np.concatenate([f.to_ndarray().reshape(-1) for f in frames]).astype("<i2").tobytes()
