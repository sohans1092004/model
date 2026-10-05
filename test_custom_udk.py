"""Per-user custom UDK (custom_udk.py + api.py): refresh from the app's DB endpoint, per-user profiles, detection on
every segment, alert without the intent veto. No models load: a local HTTP server plays the app's DB endpoint and
MockSTT plays Whisper. python test_custom_udk.py"""
from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
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


# ---- the app's DB endpoint (assumed shape: {"recordings": [base64 audio file, ...]}) ----
def wav_file(tag: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(np.full(16000, 100 + tag, dtype="<i2").tobytes())  # 1 s, distinct per clip
    return buf.getvalue()


RECORDINGS = {"U_alice": [wav_file(i) for i in range(5)], "U_bob": [wav_file(10 + i) for i in range(5)],
              "U_short": [wav_file(20 + i) for i in range(2)]}
SEEN_AUTH = []


class FakeAppDB(BaseHTTPRequestHandler):
    def do_GET(self):
        SEEN_AUTH.append(self.headers.get("Authorization"))
        user = self.path.split("/")[-2]
        body = json.dumps({"recordings": [base64.b64encode(f).decode() for f in RECORDINGS.get(user, [])]}).encode()
        self.send_response(200), self.send_header("Content-Type", "application/json"), self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


server = HTTPServer(("127.0.0.1", 0), FakeAppDB)
threading.Thread(target=server.serve_forever, daemon=True).start()
client = TestClient(api.app, headers={"X-Service-Token": api.DEV_SERVICE_TOKEN})

os.environ.pop("UDK_PHRASE_DB_URL", None)
check("not configured (no gate Whisper) -> 503, nothing stored", client.post("/v1/users/U_alice/custom-udk/refresh").status_code == 503)
os.environ["UDK_PHRASE_DB_URL"] = f"http://127.0.0.1:{server.server_port}/api"
os.environ["UDK_PHRASE_DB_TOKEN"] = "app-db-secret"

pcms = [custom_udk._to_pcm16k(f) for f in RECORDINGS["U_alice"]]
check("fetch decodes the files to 16 kHz int16 PCM", custom_udk.fetch_recordings("U_alice") == pcms and len(pcms[0]) == 32000)
check("fetch sends the configured token", SEEN_AUTH[-1] == "Bearer app-db-secret", str(SEEN_AUTH[-1:]))

api._custom_udk_stt = MockSTT()  # plays the gate's own Whisper (medium.en) on setup recordings and segments
for p in pcms:
    api._custom_udk_stt.register(p, "The blue bird sings at night")
for i, f in enumerate(RECORDINGS["U_bob"]):
    api._custom_udk_stt.register(custom_udk._to_pcm16k(f), ["pineapple on the rooftop", "my train is late again", "call me when you land", "blue moon tonight here", "stop the car near home"][i])

r = client.post("/v1/users/U_alice/custom-udk/refresh").json()
check("refresh: alice's recordings -> accepted", r["accepted"] and r["phrase"] == "the blue bird sings at night", str(r))
check("profile stored for alice", api._db.load_custom_udk("U_alice")["variants"] == ["the blue bird sings at night"])
r = client.post("/v1/users/U_bob/custom-udk/refresh").json()
check("refresh: bob's inconsistent recordings -> rejected with a reason, nothing stored",
      not r["accepted"] and "record again" in r["reason"] and api._db.load_custom_udk("U_bob") is None, str(r))
r = client.post("/v1/users/U_short/custom-udk/refresh").json()
check("refresh: only 2 recordings -> rejected", not r["accepted"] and "4-6" in r["reason"], str(r))
check("refresh needs the service token", TestClient(api.app).post("/v1/users/U_alice/custom-udk/refresh").status_code == 422)


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

# Gate: a hit stops there; a miss goes on to the general model
api._db.save_custom_udk("U_dave", custom_udk.build_profile(["get away from me now please"] * 4))
_, ev = run("J_dave_hit", "U_dave", "get away from me now please")
check("gate hit: only the custom alert, the general model (UDK_03 'get away from me') does not run",
      [e["layer"] for e in ev] == ["custom_udk"], str(ev))
_, ev = run("J_dave_miss", "U_dave", "get away from me")
check("gate miss: the general model decides (UDK_03 alert, no custom alert)",
      len(ev) == 1 and ev[0]["udk_id"] == "UDK_03" and ev[0]["layer"] != "custom_udk", str(ev))

api._intent_gate, api._parakeet_stt = VetoEverything(), MockSTT()
api._parakeet_stt.register(seg_pcm, "please help the blue bird sings at night")
_, ev = run("J_alice_veto", "U_alice", "okay the blue bird sings at night")
check("intent veto never silences the user's own phrase", any(e["layer"] == "custom_udk" and e["decision"] == "TRIGGER_ALL" for e in ev), str(ev))
api._intent_gate, api._parakeet_stt = None, None

j_carol, _ = api._store.create_or_get("J_carol", "U_carol", MockSTT())
RECORDINGS["U_carol"] = RECORDINGS["U_alice"]
client.post("/v1/users/U_carol/custom-udk/refresh")
check("a running journey picks up a profile refreshed mid-journey", j_carol.custom_udk is not None and j_carol.custom_udk["phrase"] == "the blue bird sings at night")

api._store._journeys.pop("J_alice")
j_rec, created = api._store.create_or_get("J_alice", "U_alice", MockSTT())
check("after a restart the journey reloads alice's profile from the DB", created and j_rec.custom_udk["phrase"] == "the blue bird sings at night")

server.shutdown()
os.environ.pop("UDK_PHRASE_DB_URL", None)
print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
