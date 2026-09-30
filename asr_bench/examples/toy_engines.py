"""TEST FIXTURES ONLY: deterministic fake "engines" for exercising the runner/report pipeline.
They are not ASR models and their output is never a benchmark result. Each maps the SHA-256 of
the PCM it receives to a text, read from the JSON file named by TOY_ENGINE_MAP."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass


@dataclass
class _T:
    text: str


class _MapEngine:
    def __init__(self, key: str, version: str):
        with open(os.environ["TOY_ENGINE_MAP"], encoding="utf-8") as f:
            self._m = json.load(f)[key]
        self.model_version = version

    def transcribe(self, pcm: bytes) -> _T:
        return _T(self._m.get(hashlib.sha256(pcm).hexdigest(), ""))


def perfect():
    return _MapEngine("perfect", "toy-perfect-1")


def degraded():
    return _MapEngine("degraded", "toy-degraded-1")


def mock():
    e = _MapEngine("perfect", "mock-stt-0")
    return e
