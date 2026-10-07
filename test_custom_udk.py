"""Per-user custom UDK (custom_udk.py + api.py): refresh with the app's recordings, per-user profiles, detection on
every segment, alert without the intent veto, delete. No models load: MockSTT plays Whisper.
python test_custom_udk.py"""
from __future__ import annotations

import base64
import io
import os
import tempfile
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

import api
import custom_udk
from db import JourneyDB
from event_delivery import EventDeliveryQueue
from storage import AudioStore
from stt import MockSTT
from vad import SpeechSegment

_tmp = Path(tempfile.mkdtemp(prefix="udk_custom_test_"))
api._audio_store = AudioStore(_tmp / "audio")
api._event_queue = EventDeliveryQueue(_tmp / "events")
api._db = JourneyDB(_tmp / "journeys.sqlite3")
api._store = api.JourneyStore(db=api._db)
api._parakeet_stt = None
api._downstream_deliver = lambda event: True
api._rate_limiter = api.RateLimiter(max_requests=1000, window_s=60)

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = passed + cond, failed + (not cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {'' if cond else detail}")


# ---- the notebook's own transcripts (custom_udk_enrol_detect_v2.ipynb), pure functions ----
prof = custom_udk.build_profile(["hogwarts is the best place in the world"] * 5)
check("notebook setup clips -> accepted, 100% stable", prof["ok"] and prof["stability"] == 100.0, str(prof))
notebook = {  # clip: (Whisper, Parakeet) -> notebook's decision
    "81": (["yeah works is the best place in the world i think", "yaa hogwarts is the best place in the world i think"], True),
    "82": (["hogwarts is the worst place in the world"] * 2, False),
    "83": (["hogwarts is the best place in the universe"] * 2, False),
    "84": (["hogwarts was the best place in the world"] * 2, False),
    "85": (["is hogwarts the best place in the world"] * 2, False),
    "86": (["the coffee aroma is great"] * 2, False),
    "87": (["hogwarts is the best place in the world", "her works is the best place in the world"], True),
    "88": (["harvard is the best place in the world", "harbour is the best place in the world"], False),
}
got = {k: custom_udk.detect(t, prof) for k, (t, _) in notebook.items()}
check("same 1/0 decisions as the notebook on its 8 test clips", all(got[k] == want for k, (_, want) in notebook.items()), str(got))
check("too short -> rejected with a reason", custom_udk.build_profile(["help me"] * 4)["reason"] == "phrase must have at least 3 words")
check("inconsistent recordings -> rejected, asks to record again",
      "record again" in custom_udk.build_profile(["the cat sat here", "a bat ran far away", "dog is here now", "sun was hot today"])["reason"])


# ---- refresh: the app sends the recordings ----
def wav_file(tag: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(np.full(16000, 100 + tag, dtype="<i2").tobytes())  # 1 s, distinct per clip
    return buf.getvalue()


RECORDINGS = {"U_alice": [wav_file(i) for i in range(5)], "U_bob": [wav_file(10 + i) for i in range(5)],
              "U_short": [wav_file(20 + i) for i in range(2)]}
client = TestClient(api.app, headers={"X-Service-Token": api.DEV_SERVICE_TOKEN})


def b64(files):
    return [base64.b64encode(f).decode() for f in files]


def refresh(user, files=None, body=None):
    return client.post(f"/v1/users/{user}/custom-udk/refresh", json=body or {"recordings": b64(files)})


def start(user):
    return client.post("/v1/journeys/start", json={"user_id": user}).json()["custom_udk"]


os.environ.pop("UDK_CUSTOM_UDK_STT_MODEL", None)
check("off unless UDK_CUSTOM_UDK_STT_MODEL is set (no default model)", api._load_custom_udk_stt() is None)
check("off -> refresh 503", refresh("U_alice", RECORDINGS["U_alice"]).status_code == 503)
check("off -> journey start says custom_udk None", start("U_alice") is None)
general = MockSTT()
general.model_version = "faster-whisper-small.en"
saved_general, api._stt_backend = api._stt_backend, general
os.environ["UDK_CUSTOM_UDK_STT_MODEL"] = "small.en"
check("same model as the general Whisper -> that instance, not a second one", api._load_custom_udk_stt() is general)
api._stt_backend = saved_general
os.environ.pop("UDK_CUSTOM_UDK_STT_MODEL")

pcms = custom_udk.decode_recordings(b64(RECORDINGS["U_alice"]))
check("recordings decode to 16 kHz int16 PCM", len(pcms) == 5 and len(pcms[0]) == 32000)

api._custom_udk_stt = MockSTT()  # plays the gate's own Whisper on setup recordings and segments
for p in pcms:
    api._custom_udk_stt.register(p, "The blue bird sings at night")
for i, f in enumerate(RECORDINGS["U_bob"]):
    api._custom_udk_stt.register(custom_udk._to_pcm16k(f), ["pineapple on the rooftop", "my train is late again", "call me when you land", "blue moon tonight here", "stop the car near home"][i])

r = refresh("U_alice", RECORDINGS["U_alice"]).json()
check("refresh: alice's recordings -> accepted, with what each one was heard as",
      r["accepted"] and r["phrase"] == "the blue bird sings at night" and r["heard"] == ["the blue bird sings at night"] * 5, str(r))
check("profile stored for alice", api._db.load_custom_udk("U_alice")["variants"] == ["the blue bird sings at night"])
r = refresh("U_bob", RECORDINGS["U_bob"]).json()
check("refresh: bob's inconsistent recordings -> rejected with a reason, nothing stored",
      not r["accepted"] and "record again" in r["reason"] and api._db.load_custom_udk("U_bob") is None
      and r["heard"][0] == "pineapple on the rooftop", str(r))
r = refresh("U_short", RECORDINGS["U_short"]).json()
check("refresh: only 2 recordings -> rejected", not r["accepted"] and "4-6" in r["reason"], str(r))
for what, files in (("not audio", [base64.b64encode(b"not audio").decode()] * 4), ("not base64", ["%%%"] * 4)):
    r = refresh("U_bad", body={"recordings": files}).json()
    check(f"refresh: {what} -> rejected, asks to record again", not r["accepted"] and "record again" in r["reason"], str(r))
check("refresh: an oversized recording -> 422", refresh("U_bad", body={"recordings": ["A" * 2_000_001] * 4}).status_code == 422)
check("refresh needs the service token",
      TestClient(api.app).post("/v1/users/U_alice/custom-udk/refresh", json={"recordings": []}).status_code == 422)

check("journey start: alice's phrase is active", start("U_alice") is True)
check("journey start: bob has none", start("U_bob") is False)
api._db.save_custom_udk("U_old", {**api._db.load_custom_udk("U_alice"), "stt": "faster-whisper-medium.en"})
check("journey start: a profile another model built -> False (the app asks to record again)", start("U_old") is False)


# ---- live loop ----
seg_pcm = np.full(16000 * 3, 500, dtype="<i2").tobytes()


class OneSegmentVAD:
    def segment_speech(self, pcm):
        return [SpeechSegment(start_ms=0, end_ms=3000, pcm=pcm[: len(seg_pcm)])] if len(pcm) >= len(seg_pcm) else []

    def total_ms(self, pcm):
        return len(pcm) // 32


class VetoEverything:
    def veto(self, decision, other_text):
        return 0.0  # "certainly not distress" for every text alert


def run(jid, user, words, second=""):
    stt = MockSTT()
    stt.register(seg_pcm, words)  # the general model's Whisper
    api._custom_udk_stt.register(seg_pcm, words)  # the gate's Whisper hears the same words
    j, _ = api._store.create_or_get(jid, user, stt)
    j.vad = OneSegmentVAD()
    return j, api._ingest_frame(j, 0, seg_pcm + b"\x00\x00" * 100, api._audio_store)


j, ev = run("J_alice", "U_alice", "okay the blue bird sings at night")
check("alice says her phrase -> one TRIGGER_ALL, layer custom_udk", len(ev) == 1 and ev[0]["decision"] == "TRIGGER_ALL"
      and ev[0]["layer"] == "custom_udk" and ev[0]["udk_type"] == "PERSONAL", str(ev))
_, ev = run("J_bob", "U_bob", "okay the blue bird sings at night")
check("bob (no profile) says alice's phrase -> no custom alert (profiles are per user)", all(e["layer"] != "custom_udk" for e in ev), str(ev))
_, ev = run("J_alice2", "U_alice", "the blue bird sang at night yesterday")
check("near-miss wording -> no custom alert", all(e["layer"] != "custom_udk" for e in ev), str(ev))

# Gate with its own model (medium.en on a GPU) runs in parallel with the other paths: a hit -> only the custom alert
# (their result for the segment is discarded); a miss -> the general model decides
api._db.save_custom_udk("U_dave", custom_udk.build_profile(["get away from me now please"] * 4))
_, ev = run("J_dave_hit", "U_dave", "get away from me now please")
check("gate hit: only the custom alert, the general model's UDK_03 for the same segment is discarded",
      [e["layer"] for e in ev] == ["custom_udk"], str(ev))
_, ev = run("J_dave_miss", "U_dave", "get away from me")
check("gate miss: the general model decides (UDK_03 alert, no custom alert)",
      len(ev) == 1 and ev[0]["udk_id"] == "UDK_03" and ev[0]["layer"] != "custom_udk", str(ev))

import time  # noqa: E402


class SlowSTT(MockSTT):
    def transcribe(self, pcm):
        time.sleep(0.4)
        return super().transcribe(pcm)


class BrokenSTT(MockSTT):
    def transcribe(self, pcm):
        raise RuntimeError("gate model down")


gate_stt, api._custom_udk_stt = api._custom_udk_stt, SlowSTT()
slow = SlowSTT()
slow.register(seg_pcm, "get away from me")
api._custom_udk_stt.register(seg_pcm, "get away from me")
j, _ = api._store.create_or_get("J_dave_par", "U_dave", slow)
j.vad = OneSegmentVAD()
t0 = time.time()
ev = api._ingest_frame(j, 0, seg_pcm + b"\x00\x00" * 100, api._audio_store)
took = time.time() - t0
check("own-model gate and general model run at the same time (0.4 s each -> segment well under 0.8 s)",
      took < 0.7 and [e["udk_id"] for e in ev] == ["UDK_03"], f"{took:.2f}s {ev}")
api._custom_udk_stt = BrokenSTT()
_, ev = run("J_dave_broken", "U_dave", "get away from me")
check("a failing gate does not cost the general model's alert", [e["udk_id"] for e in ev] == ["UDK_03"], str(ev))
api._custom_udk_stt = gate_stt


class CountParakeet(MockSTT):
    n = 0

    def transcribe(self, pcm):
        CountParakeet.n += 1
        return super().transcribe(pcm)


saved_parakeet, api._parakeet_stt = api._parakeet_stt, CountParakeet()
api._parakeet_stt.register(seg_pcm, "get away from me")  # only Parakeet hears the phrase
saved_backend, general = api._stt_backend, MockSTT()
general.register(seg_pcm, "something else")
api._custom_udk_stt.register(seg_pcm, "something else")
api._stt_backend = general  # the general path reads Parakeet only on the service's own English backend
j, _ = api._store.create_or_get("J_dave_parakeet", "U_dave", general)
j.vad = OneSegmentVAD()
ev = api._ingest_frame(j, 0, seg_pcm + b"\x00\x00" * 100, api._audio_store)
check("own-model gate in parallel: Parakeet runs once per segment, shared by the gate and the general model "
      "(its UDK_03 still alerts)", CountParakeet.n == 1 and [e["udk_id"] for e in ev] == ["UDK_03"], f"{CountParakeet.n} {ev}")
api._parakeet_stt, api._stt_backend = saved_parakeet, saved_backend

api._intent_gate, api._parakeet_stt = VetoEverything(), MockSTT()
api._parakeet_stt.register(seg_pcm, "please help the blue bird sings at night")
_, ev = run("J_alice_veto", "U_alice", "okay the blue bird sings at night")
check("intent veto never silences the user's own phrase", any(e["layer"] == "custom_udk" and e["decision"] == "TRIGGER_ALL" for e in ev), str(ev))
api._intent_gate, api._parakeet_stt = None, None

class CountingSTT(MockSTT):
    calls = 0

    def transcribe(self, pcm):
        self.calls += 1
        return super().transcribe(pcm)


shared, parakeet = CountingSTT(), CountingSTT()
shared.register(seg_pcm, "get away from me")
parakeet.register(seg_pcm, "get away from me")
saved = api._stt_backend, api._custom_udk_stt
api._stt_backend = api._custom_udk_stt = shared
api._parakeet_stt = parakeet
j, _ = api._store.create_or_get("J_alice_shared", "U_alice", shared)
j.vad = OneSegmentVAD()
ev = api._ingest_frame(j, 0, seg_pcm + b"\x00\x00" * 100, api._audio_store)
check("gate miss on a shared Whisper: each model transcribes the segment once, the general model still decides",
      (shared.calls, parakeet.calls) == (1, 1) and [e["udk_id"] for e in ev] == ["UDK_03"], f"{shared.calls} {parakeet.calls} {ev}")
(api._stt_backend, api._custom_udk_stt), api._parakeet_stt = saved, None

j_carol, _ = api._store.create_or_get("J_carol", "U_carol", MockSTT())
refresh("U_carol", RECORDINGS["U_alice"])
check("a running journey picks up a profile refreshed mid-journey", j_carol.custom_udk is not None and j_carol.custom_udk["phrase"] == "the blue bird sings at night")

api._store._journeys.pop("J_alice")
j_rec, created = api._store.create_or_get("J_alice", "U_alice", MockSTT())
check("after a restart the journey reloads alice's profile from the DB", created and j_rec.custom_udk["phrase"] == "the blue bird sings at night")

r = client.delete("/v1/users/U_alice/custom-udk")
check("delete: profile gone, running journeys stop listening",
      r.status_code == 200 and api._db.load_custom_udk("U_alice") is None and j_rec.custom_udk is None, r.text)
check("journey start after delete: False", start("U_alice") is False)
check("delete needs the service token", TestClient(api.app).delete("/v1/users/U_alice/custom-udk").status_code == 422)
print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
