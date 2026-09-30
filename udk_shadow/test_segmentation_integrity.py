"""Tests for udk_shadow/bench/segmentation_integrity.py (offline measurement of which audio the live streaming path hands to
STT). The live loop under test is the real api._run_incremental_detection (extracted from api.py); nothing here changes it.

  * interval arithmetic and the analyse() metrics on hand-computed cases;
  * harness controls: a STATELESS scripted VAD must give exactly one processing per segment (no harness artifact), and a
    VAD whose segment end drifts between scans must be detected as overlap (positive control);
  * the documented mechanism on real audio (needs webrtcvad + PyAV, else SKIP): with the live, state-carrying VAD object the
    streaming path re-processes audio; with a fresh VAD per scan it does not.

    python udk_shadow/test_segmentation_integrity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "bench"))

import segmentation_integrity as si  # noqa: E402

passed = failed = skipped = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


print("-- interval arithmetic / metrics")
check("merge joins touching and overlapping spans", si.merge([(5, 8), (0, 3), (3, 4), (7, 10)]) == [(0, 4), (5, 10)])
check("length counts merged coverage", si.length([(0, 10), (5, 15), (20, 25)]) == 20)
check("subtract returns uncovered parts", si.subtract([(0, 100)], [(10, 20), (15, 30), (90, 120)]) == [(0, 10), (30, 90)])
m = si.analyse([(0, 100), (0, 110), (200, 300), (250, 260)], [(0, 110), (200, 300), (400, 500)], [(20, 60), (420, 440)])
check("analyse: overlap = audio an earlier processed segment already covered", m["overlap_ms"] == 100 + 10, m)
check("analyse: duplicate (fully inside earlier) vs reprocessed (>= half inside earlier)",
      m["duplicate_segments"] == 1 and m["reprocessed_segments"] == 2, m)
check("analyse: missed reference audio and missed speech frames", m["missed_ref_ms"] == 100 and m["missed_speech_ms"] == 20, m)
check("analyse: boundary mismatches counted", m["boundary_mismatch"] == 2, m)

print("-- harness controls (real live loop, scripted VAD)")
from vad import FRAME_BYTES, FRAME_MS, SpeechSegment  # noqa: E402


class ScriptedVAD:
    """Stateless: segments are a fixed function of the audio seen so far (spans that have fully arrived)."""
    SPANS = [(0, 900), (1500, 2400), (3000, 4800)]

    def __init__(self, drift_ms=0):
        self.drift, self.scans = drift_ms, 0

    def total_ms(self, pcm):
        return (len(pcm) // FRAME_BYTES) * FRAME_MS

    def segment_speech(self, pcm):
        self.scans += 1
        tot = self.total_ms(pcm)
        out = []
        for a, b in self.SPANS:
            b = b + (self.drift * self.scans if a == 0 else 0)  # drift: the first segment's end moves on every scan
            if b <= tot:
                out.append(SpeechSegment(a, b, pcm[a * 32:b * 32]))
        return out


pcm = b"\x00\x01" * 16 * 6000  # 6 s of (content-free) 16 kHz s16 audio; the scripted VAD ignores content
ns = si.live_loop_namespace()
for chunk in (30, 100, 500):
    sim = si.simulate(pcm, chunk, ns, vad_factory=lambda: ScriptedVAD())
    check(f"stateless VAD, {chunk} ms chunks: each segment processed exactly once, in order (no harness artifact)",
          sim["processed"] == ScriptedVAD.SPANS, sim["processed"])
sim = si.simulate(pcm, 100, ns, vad_factory=lambda: ScriptedVAD(drift_ms=30))
res = si.analyse(sim["processed"], ScriptedVAD.SPANS, [])
check("positive control: a segment end that drifts between scans is re-processed and reported as overlap",
      res["overlap_ms"] > 0 and res["reprocessed_segments"] >= 1, (sim["processed"], res))
check("the harness drives the REAL live loop from api.py", "_run_incremental_detection" in ns.__dict__
      and ns._run_incremental_detection.__code__.co_filename == "api.py")

print("-- mechanism on real audio (live VAD vs fresh VAD per scan)")
clip = ROOT / "real_recordings" / "mixed" / "clip_01_clean.mp3"
try:
    import av  # noqa: F401
    import webrtcvad  # noqa: F401
    have = clip.exists()
except ImportError:
    have = False
if not have:
    skip("real-audio mechanism checks", "needs webrtcvad + PyAV and real_recordings/mixed/clip_01_clean.mp3")
else:
    from vad import VAD
    audio = si.decode(clip)
    ref, speech = si.reference(audio)

    class FreshPerScan:
        def segment_speech(self, p):
            return VAD().segment_speech(p)

        def total_ms(self, p):
            return VAD().total_ms(p)
    live = si.analyse(si.simulate(audio, 250, ns)["processed"], ref, speech)
    fresh = si.analyse(si.simulate(audio, 250, ns, vad_factory=FreshPerScan)["processed"], ref, speech)
    check("real clip, live (state-carrying) VAD, 250 ms chunks: audio is handed to STT more than once", live["overlap_ms"] > 0, live)
    check("same clip, fresh VAD per scan: no re-processing and no missed speech (isolates webrtcvad state as the cause)",
          fresh["overlap_ms"] == 0 and fresh["missed_speech_ms"] == 0, fresh)
    phrase = si.manifest_phrases().get(("mixed", "clip_01_clean"))
    cons = si.consequences(audio, 250, phrase, speech, ns)
    check(f"consequence on the real UDK engine ('{phrase}'): streaming emits more alert events than one pass",
          cons["extra_events"] >= 1, cons)

print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "") + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
