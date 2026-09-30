"""Tests for the EXPERIMENTAL streaming-segmentation candidates (udk_shadow/bench/segmentation_candidates.py), driven
through the REAL live loop (api._run_incremental_detection). Nothing here changes api.py, vad.py or any default.

Invariants checked (see results/segmentation_candidates/SEGMENTATION_CANDIDATES.md):
  I1 no re-processing: no audio handed to STT twice beyond the overlap the one-shot segmentation has BY DESIGN (the
     pre-roll after a forced 8 s cut)            I2 no skipped speech frames
  I3 processed segments == the one-shot segmentation of the complete buffer
  I4 alert semantics: streaming alerts == one-pass alerts (real UDKEngine)   I5 determinism
Boundary cases use frames whose content encodes speech/silence (exact flags); DriftClassifier reproduces the current
failure mode (classifier state carried across re-scans moves a segment end by one frame).

    python udk_shadow/test_segmentation_candidates.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "bench"))

import segmentation_candidates as sc  # noqa: E402
import segmentation_integrity as si  # noqa: E402

passed = failed = skipped = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {str(detail)[:600]}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


ns = si.live_loop_namespace()
S, Q = True, False  # speech / quiet
SCENARIOS = {
    "silence->speech->silence": [(Q, 3000), (S, 1200), (Q, 3000)],
    "speech at t=0": [(S, 900), (Q, 3000)],
    "speech ends exactly at buffer end": [(Q, 2000), (S, 1500)],
    "speech->short gap (<post-roll)->speech (one utterance)": [(Q, 2000), (S, 900), (Q, 600), (S, 900), (Q, 3000)],
    "speech->long gap->speech (two utterances)": [(Q, 2000), (S, 900), (Q, 4000), (S, 900), (Q, 3000)],
    "one-frame speech": [(Q, 2000), (S, 30), (Q, 3000)],
    "long speech with forced 8 s cuts": [(Q, 1000), (S, 20000), (Q, 3000)],
    "frame-misaligned boundaries": [(Q, 3010), (S, 1210), (Q, 2990)],
    "speech starts/ends on a 1000 ms chunk boundary": [(Q, 3000), (S, 2000), (Q, 3000)],
}
CHUNKS = (20, 30, 90, 100, 250, 600, 1000, 1500)


def run(pattern, chunk, cand, cls):
    pcm = sc.scripted_pcm(pattern)
    ref, speech = sc.reference_flags(pcm, sc.ContentClassifier)
    return sc.run_one(pcm, chunk, cand, ns, cls, ref, speech)


print("-- metric definitions: designed overlap is not a defect")
pcm = sc.scripted_pcm(SCENARIOS["long speech with forced 8 s cuts"])
ref, speech = sc.reference_flags(pcm, sc.ContentClassifier)
self_eval = sc.evaluate(ref, ref, speech)
check("one-shot segmentation of a 20 s utterance has designed overlap after the forced cuts",
      self_eval["designed_overlap_ms"] > 0, self_eval)
check("... and scores as NO re-processing (excess 0), all invariants true", self_eval["excess_overlap_ms"] == 0
      and self_eval["inv_no_reprocessing"] and self_eval["inv_no_skipped_speech"] and self_eval["inv_boundaries_equal_reference"])

print("-- boundary cases x chunk sizes (scripted, exact flags)")
res = {(name, c, cand, cls): run(pat, c, cand, clsf)
       for name, pat in SCENARIOS.items() for c in CHUNKS
       for cand, cls, clsf in (("A_current", "content", sc.ContentClassifier), ("A_current", "drift", sc.DriftClassifier),
                               ("B_fresh", "drift", sc.DriftClassifier), ("C_frontier", "drift", sc.DriftClassifier),
                               ("D_cached", "drift", sc.DriftClassifier))}


def all_ok(cand, cls, pred):
    bad = [(n, c) for (n, c, k, s), r in res.items() if k == cand and s == cls and not pred(r)]
    return not bad, bad[:5]


ok, bad = all_ok("A_current", "content", lambda r: r["inv_boundaries_equal_reference"] and r["inv_no_reprocessing"])
check("control: re-scanning with a STATELESS classifier is harmless (A == reference in every case)", ok, bad)
drift_reprocess = [(n, c) for (n, c, k, s), r in res.items() if k == "A_current" and s == "drift" and not r["inv_no_reprocessing"]]
check("failure mode reproduced: A with a state-carrying classifier re-processes audio (one-frame boundary moves)",
      len(drift_reprocess) >= len(SCENARIOS), drift_reprocess[:5])
for cand in ("B_fresh", "D_cached"):
    ok, bad = all_ok(cand, "drift", lambda r: r["inv_no_reprocessing"] and r["inv_no_skipped_speech"]
                     and r["inv_boundaries_equal_reference"] and r["error"] is None)
    check(f"{cand}: I1-I3 hold in all {len(SCENARIOS)} scenarios x {len(CHUNKS)} chunk sizes (incl. forced 8 s cuts)", ok, bad)
ok, bad = all_ok("C_frontier", "drift", lambda r: r["inv_no_reprocessing"] and r["inv_no_skipped_speech"])
check("C_frontier: no re-processing and no skipped speech", ok, bad)
c_bad = [(n, c) for (n, c, k, s), r in res.items() if k == "C_frontier" and s == "drift" and not r["inv_boundaries_equal_reference"]]
check("C_frontier VIOLATES I3: it emits trimmed fragments / removes designed cut overlap (boundaries != one-shot)", bool(c_bad), c_bad[:3])
long_c = [r for (n, c, k, s), r in res.items() if k == "C_frontier" and n == "long speech with forced 8 s cuts" and s == "drift"]
check("C_frontier removes the DESIGNED overlap after an 8 s cut (the phrase-split protection)",
      all(r["overlap_ms"] < self_eval["designed_overlap_ms"] for r in long_c), [r["overlap_ms"] for r in long_c])
long_d = [r for (n, c, k, s), r in res.items() if k == "D_cached" and n == "long speech with forced 8 s cuts"]
check("D_cached keeps the designed 8 s-cut overlap exactly", all(r["overlap_ms"] == self_eval["designed_overlap_ms"] for r in long_d))

print("-- frontier / stability properties of D")
counter = {"n": 0}


class CountingContent(sc.ContentClassifier):
    def is_speech(self, frame, sample_rate):
        counter["n"] += 1
        return super().is_speech(frame, sample_rate)


pcm = sc.scripted_pcm(SCENARIOS["speech->long gap->speech (two utterances)"])
r = sc.run_one(pcm, 20, "D_cached", ns, CountingContent, *sc.reference_flags(pcm, sc.ContentClassifier))
check("D classifies every frame exactly once across hundreds of re-scans (classification frontier)",
      counter["n"] == len(pcm) // sc.FRAME_BYTES and r["calls"] > 100, (counter["n"], len(pcm) // sc.FRAME_BYTES, r["calls"]))
d = sc.CandidateD(sc.ContentClassifier())
d.segment_speech(pcm)
try:
    d.segment_speech(pcm[: len(pcm) // 2])
    shrink = False
except RuntimeError:
    shrink = True
check("D refuses a shrinking buffer (cache/audio mismatch can never pass silently)", shrink)

# repeated rescans of the same buffer: no new processing
from vad import SpeechSegment  # noqa: E402,F401
rv = si.RecordingVAD(sc.CandidateD(sc.DriftClassifier()))
stt = si.RecordingSTT(rv)
j = si.Journey(rv, stt)
j.audio_buffer.extend(pcm)
for _ in range(6):
    ns._run_incremental_detection(j)
before = list(stt.calls)
for _ in range(6):
    ns._run_incremental_detection(j)
check("repeated re-scans of an unchanged buffer hand nothing new to STT (D)", stt.calls == before and len(before) >= 1, (before, stt.calls))
r1 = run(SCENARIOS["frame-misaligned boundaries"], 90, "D_cached", sc.DriftClassifier)
r2 = run(SCENARIOS["frame-misaligned boundaries"], 90, "D_cached", sc.DriftClassifier)
check("determinism: identical input -> identical processed spans (D)", r1["processed_spans"] == r2["processed_spans"])

print("-- real audio (webrtcvad + PyAV, else SKIP)")
try:
    import av  # noqa: F401
    import webrtcvad  # noqa: F401
    clips = [ROOT / "real_recordings" / "mixed" / f for f in ("clip_01_clean.mp3", "clip_19_muffled.mp3")]
    have = all(c.exists() for c in clips)
except ImportError:
    have = False
if not have:
    skip("real-audio candidate checks", "needs webrtcvad + PyAV + real_recordings/mixed clips")
else:
    phrases = si.manifest_phrases()
    for clip in clips:
        audio = si.decode(clip)
        ref, speech = si.reference(audio)
        for c in (20, 100, 1000):
            a = sc.run_one(audio, c, "A_current", ns, None, ref, speech)
            dd = sc.run_one(audio, c, "D_cached", ns, None, ref, speech)
            check(f"{clip.name} {c} ms: D == one-shot, no re-processing, no missed speech (A excess {a['excess_overlap_ms']} ms)",
                  dd["inv_boundaries_equal_reference"] and dd["inv_no_reprocessing"] and dd["inv_no_skipped_speech"], dd)
    audio = si.decode(clips[1])
    ref, speech = si.reference(audio)
    ph = phrases[("mixed", "clip_19_muffled")]
    ca = si.consequences(audio, 100, ph, speech, ns, vad_factory=sc.factory("A_current"))
    cd = si.consequences(audio, 100, ph, speech, ns, vad_factory=sc.factory("D_cached"))
    check(f"alert consequence ('{ph}', 100 ms): A has a repeat-induced TRIGGER_ALL, D has none and equals one pass",
          ca["repeat_induced_trigger_all"] >= 1 and cd["repeat_induced_trigger_all"] == 0 and cd["extra_events"] == 0
          and [e[:2] for e in cd["stream_events"]] == [e[:2] for e in cd["oneshot_events"]], (ca["stream_events"], cd["stream_events"]))

print("-- production untouched")
import vad as live_vad  # noqa: E402
check("production vad.VAD is unchanged by the experiment (candidates subclass/wrap it; no monkey-patching)",
      live_vad.VAD.segment_speech.__qualname__ == "VAD.segment_speech" and not hasattr(live_vad.VAD, "bind"))

print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "") + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
