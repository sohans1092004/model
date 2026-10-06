"""Telugu / Tamil / Kannada in the live loop (api.py): per-segment routing like Hindi, exact or fuzzy match only, ask
only. Fake language ID and a fake IndicConformer, so no model loads. python test_indic_exact.py"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

import api
from db import JourneyDB
from event_delivery import EventDeliveryQueue
from storage import AudioStore
from stt import MockSTT, Transcript
from udks import general_udks
from vad import SpeechSegment

_tmp = Path(tempfile.mkdtemp(prefix="udk_indic_test_"))
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


check("off by default: no Telugu/Tamil/Kannada, no language ID, nothing loaded",
      api._indic_langs == [] and api._indic_stt is None and api._hindi_lid is None)

seg_pcm = np.full(16000 * 3, 400, dtype="<i2").tobytes()


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


class FakeIndic:
    """Plays IndicConformer: what it 'hears' depends on the language it is asked to transcribe in."""

    def __init__(self, heard: dict, fail=False):
        self.heard, self.fail, self.langs = heard, fail, []

    def transcribe(self, pcm, language=None):
        self.langs.append(language)
        if self.fail:
            raise RuntimeError("model down")
        return Transcript(text=self.heard.get(language, ""), model_version="fake-indic")


def run(jid, probs, heard, english="", fail=False, langs=("te", "ta", "kn")):
    api._indic_langs = list(langs)
    api._indic_udks = {l: general_udks(l) for l in langs}
    api._indic_stt = FakeIndic(heard, fail)
    api._hindi = None
    api._hindi_lid = lambda pcm: probs
    CountingSTT.calls = 0
    api._stt_backend = CountingSTT()
    api._stt_backend.register(seg_pcm, english)
    j, _ = api._store.create_or_get(jid, "U1", api._stt_backend)
    j.vad = OneSegmentVAD()
    return api._ingest_frame(j, 0, seg_pcm + b"\x00\x00" * 100, api._audio_store)


TE, TA, KN = "అయ్యో నన్ను వదిలేయ్ ప్లీజ్", "என்னை விடு தயவுசெய்து", "ನನ್ನನ್ನು ಬಿಡು ದಯವಿಟ್ಟು"

ev = run("J_te", {"te": 0.99, "en": 0.01}, {"te": TE})
check("clearly Telugu, phrase said -> one ask (TRIGGER_VERIFY), exact, Telugu UDK_10; English path not run",
      [(e["decision"], e["layer"], e["udk_id"]) for e in ev] == [("TRIGGER_VERIFY", "te_exact", "UDK_10")] and CountingSTT.calls == 0, str(ev))
check("Telugu-led -> IndicConformer asked in all three (te first): Whisper confuses te/ta/kn",
      api._indic_stt.langs[0] == "te" and sorted(api._indic_stt.langs) == ["kn", "ta", "te"], str(api._indic_stt.langs))
ev = run("J_te_as_kn", {"kn": 0.25, "en": 0.08, "te": 0.05}, {"te": "నేను సురక్షితంగా లేను"})
check("real case: Telugu 'I'm not safe' heard as 25 % Kannada -> Telugu still checked -> ask UDK_02",
      [(e["layer"], e["udk_id"]) for e in ev] == [("te_exact", "UDK_02")], str(ev))  # English also runs: 0.08 is 21 %
ev = run("J_te_save", {"te": 0.9}, {"te": "ఎవరైనా నన్ను కాపాడండి"})
check("Telugu 'anyone save me' (UDK_21, other word order) -> ask", [e["udk_id"] for e in ev] == ["UDK_21"], str(ev))
ev = run("J_ta_frag", {"ta": 0.9}, {"ta": "அது போக"})
check("real case: 2-word Tamil fragment 'அது போக' (1 of 5 words of UDK_18) -> no ask", ev == [], str(ev))
ev = run("J_te_tell", {"te": 0.9}, {"te": "దయచేసి సహాయం కోసం కాల్ చేయండి నాకు ఒకసారి చెప్పు"})
check("real case: UDK_19 next to 'tell me' (చెప్పు) -> still asks (cue is 'she said', not every 'tell')",
      [e["udk_id"] for e in ev] == ["UDK_19"], str(ev))
ev = run("J_ta", {"ta": 0.98, "en": 0.02}, {"ta": TA})
check("Tamil exact -> ask", [(e["decision"], e["layer"]) for e in ev] == [("TRIGGER_VERIFY", "ta_exact")], str(ev))
ev = run("J_kn", {"kn": 0.97, "en": 0.03}, {"kn": KN})
check("Kannada exact -> ask", [(e["decision"], e["layer"]) for e in ev] == [("TRIGGER_VERIFY", "kn_exact")], str(ev))
ev = run("J_te_fuzzy", {"te": 0.99}, {"te": "నన్ను వదిలెయ్"})
check("Telugu misheard spelling -> fuzzy match -> ask", [(e["decision"], e["layer"]) for e in ev] == [("TRIGGER_VERIFY", "te_fuzzy")], str(ev))
ev = run("J_te_none", {"te": 0.99}, {"te": "ఈరోజు వాతావరణం బాగుంది"})
check("Telugu speech without any phrase -> nothing", ev == [], str(ev))
ev = run("J_te_strong", {"te": 0.99}, {"te": TE + " " + TE + " పోలీసులకు కాల్ చేయండి, నాకు సహాయం కావాలి"})
check("several phrases in one segment -> still only an ask, never a direct alert",
      bool(ev) and all(e["decision"] == "TRIGGER_VERIFY" for e in ev), str(ev))
ev = run("J_te_hi_phrase", {"te": 0.99}, {"te": "मुझे छोड़ दो"})
check("a Hindi phrase on a Telugu-routed segment does not match (Telugu's own 20 phrases only)", ev == [], str(ev))

ev = run("J_mix_en_alert", {"en": 0.6, "te": 0.4}, {"te": TE}, english="get away from me")
check("unsure EN/TE: the English general model's alert stands; the Telugu ask does not replace or lower it",
      any(e["udk_id"] == "UDK_03" and not e["layer"].startswith("te_") for e in ev)
      and not any(e["layer"].startswith("te_") for e in ev), str(ev))
ev = run("J_mix_en_quiet", {"en": 0.5, "te": 0.5}, {"te": TE}, english="hello there")
check("unsure EN/TE: English quiet, Telugu phrase -> the Telugu ask", [e["layer"] for e in ev] == ["te_exact"], str(ev))
ev = run("J_en", {"en": 0.99, "te": 0.01}, {"te": TE}, english="get away from me")
check("clearly English -> Telugu path not run, English general model as before",
      api._indic_stt.langs == [] and [e["udk_id"] for e in ev] == ["UDK_03"], str(ev))
ev = run("J_te_off", {"te": 0.99, "en": 0.01}, {"te": TE}, langs=("ta",))
check("Telugu not enabled -> its segment goes to English, no Telugu matching",
      api._indic_stt.langs == [] and CountingSTT.calls == 1 and ev == [], str(ev))

ev = run("J_ta_led", {"ta": 0.7, "en": 0.15, "hi": 0.15}, {"ta": "சாதாரண பேச்சு"}, english="help me please")
check("Tamil-led segment (70 %), English 15 % -> English path not run (no English 'hearing' in Tamil speech)",
      CountingSTT.calls == 0 and ev == [], f"calls={CountingSTT.calls} {ev}")
ev = run("J_ta_en", {"ta": 0.6, "en": 0.4}, {"ta": "சாதாரண பேச்சு"}, english="get away from me")
check("Tamil-led but English 40 % -> English path still runs and its alert stands",
      CountingSTT.calls == 1 and [e["udk_id"] for e in ev] == ["UDK_03"], f"calls={CountingSTT.calls} {ev}")

ev = run("J_te_safe", {"te": 0.99}, {"te": "ఇంట్లో అందరూ సురక్షితంగా ఉన్నారా"})
check("Telugu word overlap only ('is everyone safe at home' ~ UDK_02) -> no ask (no loose fallback)", ev == [], str(ev))
ev = run("J_ta_ok", {"ta": 0.99}, {"ta": "நான் பாதுகாப்பாக இருக்கிறேன் பயப்படாதே"})
check("Tamil 'I am safe, don't be afraid' -> no ask (benign-context cue)", ev == [], str(ev))
ev = run("J_ta_need", {"ta": 0.99}, {"ta": "எனக்கு இப்போதே உதவி தேவை"})
check("Tamil UDK_05 'need help now' still asks (its own word தேவை is not the cue தேவையில்லை)",
      [e["udk_id"] for e in ev] == ["UDK_05"], str(ev))

ev = run("J_te_fail", {"te": 0.99}, {"te": TE}, english="get away from me", fail=True)
check("Telugu path fails on a Telugu-only segment -> the existing English path runs instead",
      CountingSTT.calls == 1 and [e["udk_id"] for e in ev] == ["UDK_03"], str(ev))

api._indic_langs, api._indic_stt, api._hindi_lid = [], None, None
print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
