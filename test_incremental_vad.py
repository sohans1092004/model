"""The live loop scans incrementally (api._run_incremental_detection + vad.VAD.segments): same segments as one pass
over the whole recording, and the audio it keeps stays bounded however long the journey runs. No models.
    python test_incremental_vad.py
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import numpy as np

os.environ.update(UDK_ENABLE_STT="0", UDK_ENABLE_SEMANTIC="0", UDK_ENABLE_SCREAM_DETECTION="0", UDK_ENABLE_PARAKEET="0")
import api  # noqa: E402
from storage import AudioStore  # noqa: E402
from vad import VAD  # noqa: E402

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name} {detail}")


rng = np.random.default_rng(0)
SR = 16000


def burst(s):  # speech-like: band-limited noise with a syllable-rate envelope
    t = np.arange(int(s * SR)) / SR
    return (rng.normal(0, 1, t.size) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t)) * 4000).astype("<i2")


def silence(s):
    return (rng.normal(0, 1, int(s * SR)) * 30).astype("<i2")


parts = []
for k in range(40):  # ~5 min: words, short pauses (< post-roll, kept in one segment), long pauses
    parts += [burst(0.6 + (k % 5) * 0.4), silence(0.5 if k % 3 else 2.5)]
parts += [burst(30.0), silence(3.0)]  # 30 s of continuous "speech": forced 8 s cuts with pre-roll overlap
for k in range(20):
    parts += [burst(1.0), silence(4.0)]
pcm = np.concatenate(parts).tobytes()

store = AudioStore(Path(tempfile.mkdtemp()))
store.write_segment = lambda *a, **k: None
api._store = api.JourneyStore(db=None)
seen, kept = [], []
api._existing_alerts = lambda journey, seg, scream_fired, pre=None, parakeet_job=None: (seen.append((seg.start_ms, seg.end_ms, seg.pcm)), ([], ""))[1]
j, _ = api._store.create_or_get("J_inc", "U", api._stt_backend)
t0 = time.perf_counter()
for i in range(0, len(pcm), 6400):
    api._ingest_frame(j, i // 6400, pcm[i:i + 6400], store)
    kept.append(len(j.audio_buffer))
api._run_incremental_detection(j, final=True)
took = time.perf_counter() - t0

ref = [(s.start_ms, s.end_ms, s.pcm) for s in VAD().segment_speech(pcm)]
check("segments handed to the models = one pass over the whole recording (same start, end and audio)",
      seen == ref, f"{len(seen)} vs {len(ref)}")
check("the test audio exercises the 8 s cut", any(s.cut for s in VAD().segment_speech(pcm)))
check(f"{len(ref)} segments in {len(pcm) / 32000:.0f} s of audio", len(ref) > 20)
check("kept audio stays bounded (< 20 s) on a ~7 min journey", max(kept) < 20 * 32000, f"max {max(kept) / 32000:.1f} s")
check("the loop is fast (< 3 s for ~7 min of 200 ms frames, models stubbed)", took < 3.0, f"{took:.1f}s")

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
