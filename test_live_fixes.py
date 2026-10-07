"""Live-loop fixes from the architecture review (no models; every STT is a MockSTT):
  - a failing or hanging Parakeet no longer ends the journey: the segment continues on Whisper alone;
  - the English model's 15 s repeat window is audio time (segment end), not processing time;
  - the WebSocket handler runs detection off the event loop: a slow journey does not stall another connection.
    python test_live_fixes.py
"""
from __future__ import annotations

import tempfile
import asyncio
import time
from pathlib import Path

import api
from db import JourneyDB
from event_delivery import EventDeliveryQueue
from fastapi.testclient import TestClient
from stt import MockSTT
from storage import AudioStore
from vad import SpeechSegment

_tmp = Path(tempfile.mkdtemp(prefix="udk_live_fixes_"))
api._audio_store = AudioStore(_tmp / "audio")
api._event_queue = EventDeliveryQueue(_tmp / "events")
api._db = JourneyDB(_tmp / "journeys.sqlite3")
api._store = api.JourneyStore(db=api._db)
api._downstream_deliver = lambda event: True

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    passed, failed = passed + cond, failed + (not cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {'' if cond else detail}")


BLOCK = 8


class TimedVAD:
    """One segment per BLOCK bytes, at the given journey times (seconds)."""
    def __init__(self, times_s):
        self.times = times_s

    def segment_speech(self, pcm):
        n = min(len(pcm) // BLOCK, len(self.times))
        return [SpeechSegment(start_ms=int(self.times[i] * 1000), end_ms=int(self.times[i] * 1000) + 1000,
                              pcm=pcm[i * BLOCK:(i + 1) * BLOCK]) for i in range(n)]

    def total_ms(self, pcm):
        segs = self.segment_speech(pcm)
        return segs[-1].end_ms + 1 if segs else 0


def run(journey_id, blocks, times_s):
    j, _ = api._store.create_or_get(journey_id, "U_fix", api._stt_backend)
    j.vad = TimedVAD(times_s)
    events = []
    for seq, b in enumerate(blocks):
        events += api._ingest_frame(j, seq, b, api._audio_store)
    return events


class RaisingSTT(MockSTT):
    def transcribe(self, pcm):
        raise RuntimeError("onnxruntime: CUDA failure")


class HangingSTT(MockSTT):
    def transcribe(self, pcm):
        time.sleep(3)
        return super().transcribe(pcm)


print("=== Parakeet failure ===")
a = b"A" * BLOCK
api._stt_backend = MockSTT()
api._stt_backend.register(a, "get away from me")
api._parakeet_stt = RaisingSTT()
try:
    ev = run("J_pk_raise", [a], [0])
    check("Parakeet raising: no exception, Whisper's alert still goes out",
          [e["udk_id"] for e in ev] == ["UDK_03"], str(ev))
except Exception as e:
    check("Parakeet raising: no exception, Whisper's alert still goes out", False, repr(e))

api._parakeet_stt = HangingSTT()
saved_timeout, api.PARAKEET_TIMEOUT_S = getattr(api, "PARAKEET_TIMEOUT_S", 30.0), 0.3
t = time.perf_counter()
try:
    ev = run("J_pk_hang", [a], [0])
except Exception as e:  # the old code raised here too
    ev = [repr(e)]
took = time.perf_counter() - t
check("Parakeet hanging: the segment is decided after the timeout, on Whisper alone",
      [e["udk_id"] for e in ev] == ["UDK_03"] and took < 2.0, f"{took:.1f}s {ev}")
api.PARAKEET_TIMEOUT_S = saved_timeout
time.sleep(3)  # let the hanging run finish before the pool is used again
api._parakeet_stt = None

print("\n=== repeat window on audio time ===")
h1, h2 = b"H" * BLOCK, b"I" * BLOCK
api._stt_backend = MockSTT()
api._stt_backend.register(h1, "help me")
api._stt_backend.register(h2, "help me")
ev = run("J_rep_far", [h1, h2], [0, 40])  # 40 s apart in the audio, processed back to back
check("two 'help me' 40 s apart in the audio stay asks (processed instantly)",
      [e["decision"] for e in ev] == ["TRIGGER_VERIFY", "TRIGGER_VERIFY"], str([e["decision"] for e in ev]))

clock = iter([1000.0, 1040.0, 1080.0, 1120.0])
real_monotonic = api.time.monotonic
api.time.monotonic = lambda: next(clock, 2000.0)  # a backlog: each segment decided 40 s after the previous one
try:
    ev = run("J_rep_near", [h1, h2], [0, 10])  # 10 s apart in the audio
finally:
    api.time.monotonic = real_monotonic
check("two 'help me' 10 s apart in the audio escalate, however late they are processed",
      [e["decision"] for e in ev] == ["TRIGGER_VERIFY", "TRIGGER_ALL"], str([e["decision"] for e in ev]))

print("\n=== WebSocket: detection off the event loop ===")
api._stt_backend = MockSTT()
client = TestClient(api.app, headers={"X-Service-Token": api.DEV_SERVICE_TOKEN})
sa = client.post("/v1/journeys/start", json={"user_id": "U_slow"}).json()
sb = client.post("/v1/journeys/start", json={"user_id": "U_fast"}).json()


class FakeWS:
    """Both connections on ONE event loop, as on the server (the TestClient gives each socket its own loop, which
    would hide the blocking)."""
    def __init__(self):
        self.q, self.sent = asyncio.Queue(), []

    async def accept(self):
        pass

    async def close(self, code=None):
        pass

    async def receive(self):
        return await self.q.get()

    async def send_json(self, data):
        self.sent.append((time.perf_counter(), data))


orig_ingest = api._ingest_frame


def slow_ingest(journey, seq, pcm, store):
    if journey.journey_id == sa["journey_id"]:
        time.sleep(3)  # a slow segment (a CPU segment takes ~20 s)
    return orig_ingest(journey, seq, pcm, store)


async def scenario():
    wa, wb = FakeWS(), FakeWS()
    ta = asyncio.create_task(api.stream_audio(wa, sa["journey_id"], sa["session_token"]))
    tb = asyncio.create_task(api.stream_audio(wb, sb["journey_id"], sb["session_token"]))
    await wa.q.put({"type": "websocket.receive", "bytes": api.FRAME_HEADER.pack(0, time.time()) + b"\x00" * 32})
    await asyncio.sleep(0.3)  # journey A is now inside its slow segment
    sent_at = time.perf_counter()
    await wb.q.put({"type": "websocket.receive", "text": '{"type": "heartbeat"}'})
    while not (wa.sent and wb.sent) and time.perf_counter() - sent_at < 10:
        await asyncio.sleep(0.05)
    for w in (wa, wb):
        await w.q.put({"type": "websocket.disconnect"})
    await asyncio.gather(ta, tb)
    return sent_at, wa.sent, wb.sent


api._ingest_frame = slow_ingest
try:
    sent_at, a_sent, b_sent = asyncio.run(scenario())
finally:
    api._ingest_frame = orig_ingest
# Clocks on a blocked loop would start late, so compare order instead: the other journey must be answered WHILE the
# slow frame is still being processed, i.e. well before that frame's ack (old code: only after it).
lead = (a_sent[0][0] - b_sent[0][0]) if (a_sent and b_sent) else -99.0
check("another journey is answered while one journey's segment is slow (same event loop)",
      bool(b_sent) and b_sent[0][1].get("type") == "heartbeat" and lead > 2.0,
      f"answered {lead:.1f}s before the slow frame's ack (needs > 2 s)")
check("the slow journey's frame is still processed and acked",
      bool(a_sent) and a_sent[0][1].get("ack_seq") == 0, str(a_sent))

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
