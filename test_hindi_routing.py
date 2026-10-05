"""Hindi per-segment routing in the live loop (api.py + safety_router/), with fake language ID and a fake
Hindi system so no model loads. python test_hindi_routing.py"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

import api
import scream_trigger as ST
from db import JourneyDB
from event_delivery import EventDeliveryQueue
from safety_router.hindi import HindiResult
from storage import AudioStore
from stt import MockSTT
from udks import SAMPLE_PERSONAL_UDK
from vad import SpeechSegment

_tmp = Path(tempfile.mkdtemp(prefix="udk_hindi_test_"))
api._audio_store = AudioStore(_tmp / "audio")
api._event_queue = EventDeliveryQueue(_tmp / "events")
api._db = JourneyDB(_tmp / "journeys.sqlite3")
api._store = api.JourneyStore(db=api._db)
api._parakeet_stt = None

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = passed + cond, failed + (not cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {'' if cond else detail}")


seg_pcm = np.full(ST.HOP * 6, 500, dtype="<i2").tobytes()  # 3 s


class OneSegmentVAD:
    def segment_speech(self, pcm):
        return [SpeechSegment(start_ms=0, end_ms=3000, pcm=pcm[: len(seg_pcm)])] if len(pcm) >= len(seg_pcm) else []

    def total_ms(self, pcm):
        return len(pcm) // 32


class CountingSTT(MockSTT):
    calls = 0

    def transcribe(self, pcm):
        CountingSTT.calls += 1
        return super().transcribe(pcm)


class FakeHindi:
    def __init__(self, decision="none", udk_id="UDK_10", fail=False):
        self.decision, self.udk_id, self.fail, self.calls = decision, udk_id, fail, 0

    def process(self, pcm, start_ms, stream):
        self.calls += 1
        if self.fail:
            raise RuntimeError("model down")
        stream.add(start_ms, "मुझे छोड़ दो")
        return HindiResult(self.decision, "मुझे छोड़ दो", 0.9, 0.95 if self.decision == "ALERT" else 0.3, "LIVE_DIRECT", self.udk_id)


def lid(p_en, fail=False):
    def f(pcm):
        if fail:
            raise RuntimeError("lid down")
        return {"en": p_en, "hi": 1 - p_en}
    return f


def run(jid, hindi, p_en=None, words="", lid_fail=False, scream=False):
    api._hindi = hindi
    api._hindi_lid = lid(p_en, lid_fail) if hindi is not None else None
    api._scream_trigger_enabled = scream
    api._scream_detector = type("FakeBEATs", (), {"model_version": "fake", "score": lambda s, p: 0.0,
                                                  "label_probs": lambda s, p: np.eye(527, dtype=np.float32)[34] * 0.5})() if scream else None
    CountingSTT.calls = 0
    api._stt_backend = CountingSTT()
    api._stt_backend.register(seg_pcm, words)
    j, _ = api._store.create_or_get(jid, "U1", api._stt_backend, SAMPLE_PERSONAL_UDK)
    j.vad = OneSegmentVAD()
    return api._ingest_frame(j, 0, seg_pcm + b"\x00\x00" * 100, api._audio_store)


# Switch off: exactly the existing path
ev = run("J_off", None, words="get away from me")
check("switch OFF: English alert as before, no Hindi involved", len(ev) == 1 and ev[0]["udk_id"] == "UDK_03" and ev[0]["layer"] != "hi_frame", str(ev))

# Clearly Hindi -> Hindi only (English STT never runs)
h = FakeHindi("ALERT", "UDK_10")
ev = run("J_hi", h, p_en=0.01)
check("clearly Hindi: Hindi system runs, English STT does not", h.calls == 1 and CountingSTT.calls == 0, (h.calls, CountingSTT.calls))
check("Hindi ALERT -> TRIGGER_ALL event, layer hi_frame, Hindi UDK",
      len(ev) == 1 and ev[0]["decision"] == "TRIGGER_ALL" and ev[0]["layer"] == "hi_frame" and ev[0]["udk_id"] == "UDK_10", str(ev))

# Clearly English -> English only
h = FakeHindi("ALERT")
ev = run("J_en", h, p_en=0.99, words="get away from me")
check("clearly English: Hindi system not called, English alert unchanged",
      h.calls == 0 and len(ev) == 1 and ev[0]["udk_id"] == "UDK_03" and ev[0]["layer"] != "hi_frame", str(ev))

# Unsure -> both; the higher decision wins
h = FakeHindi("VERIFY", "UDK_03")
ev = run("J_both_low", h, p_en=0.6, words="get away from me")
check("unsure: both run; Hindi VERIFY does not override the English alert",
      h.calls == 1 and CountingSTT.calls == 1 and len(ev) == 1 and ev[0]["layer"] != "hi_frame", str(ev))
h = FakeHindi("ALERT", "UDK_10")
ev = run("J_both_high", h, p_en=0.6, words="hello there")
check("unsure: English quiet, Hindi ALERT -> one Hindi event", len(ev) == 1 and ev[0]["layer"] == "hi_frame", str(ev))
h = FakeHindi("none")
ev = run("J_both_none", h, p_en=0.5, words="hello there")
check("unsure: nothing from either -> no event", ev == [], str(ev))

# Scream runs on every route, also Hindi-only
h = FakeHindi("none")
ev = run("J_scream_hi", h, p_en=0.01, scream=True)
check("Hindi-only route + scream, no words -> acoustic TRIGGER_VERIFY",
      len(ev) == 1 and ev[0]["layer"] == "acoustic_scream" and ev[0]["decision"] == "TRIGGER_VERIFY", str(ev))

# Failures fall back to the existing path, never lose a detection
h = FakeHindi("ALERT", fail=True)
ev = run("J_hi_fail", h, p_en=0.01, words="get away from me")
check("Hindi system fails on a Hindi-only segment -> existing path runs instead",
      CountingSTT.calls == 1 and len(ev) == 1 and ev[0]["udk_id"] == "UDK_03", str(ev))
h = FakeHindi("ALERT")
ev = run("J_lid_fail", h, p_en=0.5, words="get away from me", lid_fail=True)
check("language ID fails -> existing path only", h.calls == 0 and len(ev) == 1 and ev[0]["udk_id"] == "UDK_03", str(ev))

api._hindi = api._hindi_lid = None
api._scream_trigger_enabled, api._scream_detector = False, None
print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
