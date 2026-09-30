"""EXPERIMENTAL: candidate fixes for live streaming re-segmentation (results/segmentation_integrity/). Not wired into the
service, not imported by api.py, not in the image whitelist. Every candidate is a drop-in replacement for the journey's
`vad.VAD` object, driven through the REAL live loop (`api._run_incremental_detection`) by segmentation_integrity.py.

  A_current   vad.VAD as deployed: one webrtcvad.Vad reused across every complete-buffer re-scan (state carries over).
  B_fresh     a fresh vad.VAD per re-scan: every frame re-classified from a clean state each time.
  C_frontier  A + a monotonic processed frontier: any part of a segment at or before journey.processed_up_to_ms is trimmed.
  D_cached    each 30 ms frame classified exactly ONCE, in order, by one persistent webrtcvad.Vad; its flag is cached and the
              UNCHANGED production segmentation (vad.VAD.segment_speech) runs over the cached flags. Classification has a
              monotonic frontier; segmentation (incl. the intentional overlap after a forced 8 s cut) is untouched.

Scripted classifiers (tests / boundary cases): frames whose CONTENT encodes speech/silence and their frame index, so a
scenario's flags are exact. DriftClassifier additionally mimics A's failure mode: it is stateful across scans and moves
a speech segment's last frame by one frame on alternate scans.

    python udk_shadow/bench/segmentation_candidates.py <audio files/dirs> [--chunks ...] [--skip-converted] [--out f.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import segmentation_integrity as si  # noqa: E402
from vad import FRAME_BYTES, FRAME_MS, VAD, SpeechSegment  # noqa: E402

BYTES_PER_MS = 32  # 16 kHz * 2 bytes


# ------------------------------------------------------------------ candidates
class CandidateA(VAD):
    """A_current: identical to the production vad.VAD (optionally with an injected classifier for scripted tests)."""
    name = "A_current"

    def __init__(self, classifier=None, **kw):
        super().__init__(**kw)
        if classifier is not None:
            self._vad = classifier


class CandidateB:
    name = "B_fresh"

    def __init__(self, classifier_factory=None, **kw):
        self.kw, self.cf = kw, classifier_factory

    def _fresh(self):
        v = VAD(**self.kw)
        if self.cf is not None:
            v._vad = self.cf()
        return v

    def segment_speech(self, pcm):
        return self._fresh().segment_speech(pcm)

    def total_ms(self, pcm):
        return (len(pcm) // FRAME_BYTES) * FRAME_MS


class CandidateC(CandidateA):
    name = "C_frontier"

    def __init__(self, classifier=None, **kw):
        super().__init__(classifier, **kw)
        self.journey, self.trimmed = None, 0

    def bind(self, journey):
        self.journey = journey

    def segment_speech(self, pcm):
        front = self.journey.processed_up_to_ms if self.journey is not None else 0
        out = []
        for s in super().segment_speech(pcm):
            if s.start_ms < front < s.end_ms:  # overlaps already-processed audio: keep only the part after the frontier
                self.trimmed += 1
                s = SpeechSegment(front, s.end_ms, pcm[front * BYTES_PER_MS:s.end_ms * BYTES_PER_MS])
            out.append(s)  # segments ending at/before the frontier are skipped by the live loop itself
        return out


class _CachedClassifier:
    """Proxy for VAD._vad: the real classifier sees each frame index once, in order; later scans get the cached flag."""
    def __init__(self, real):
        self.real, self.flags, self.i = real, [], 0

    def is_speech(self, frame, sample_rate):
        i = self.i
        self.i += 1
        if i < len(self.flags):
            return self.flags[i]
        f = self.real.is_speech(frame, sample_rate)
        self.flags.append(f)
        return f


class CandidateD(VAD):
    name = "D_cached"

    def __init__(self, classifier=None, **kw):
        super().__init__(**kw)
        self._cache = _CachedClassifier(classifier if classifier is not None else self._vad)
        self._vad = self._cache
        self._n_frames = 0

    def segment_speech(self, pcm):
        n = len(pcm) // FRAME_BYTES
        if n < self._n_frames:  # the live buffer is append-only; anything else invalidates the cache (never seen)
            raise RuntimeError("D_cached: buffer shrank; cached frame flags would no longer match the audio")
        self._n_frames = n
        self._cache.i = 0
        return super().segment_speech(pcm)


class CandidateDFlag(CandidateA):
    """D as implemented in production code: vad.VAD(cache_classifications=True) (prototype flag, OFF by default)."""
    name = "D_vad_flag"

    def __init__(self, classifier=None, **kw):
        super().__init__(classifier, cache_classifications=True, **kw)


CANDIDATES = {"A_current": CandidateA, "B_fresh": CandidateB, "C_frontier": CandidateC, "D_cached": CandidateD,
              "D_vad_flag": CandidateDFlag}


def factory(name, classifier_factory=None):
    """Zero-arg factory for simulate(); scripted classifiers are injected per candidate semantics."""
    cls = CANDIDATES[name]
    if name == "B_fresh":
        return lambda: cls(classifier_factory)
    return lambda: cls(classifier_factory() if classifier_factory else None)


# ------------------------------------------------------------------ scripted audio / classifiers (tests, boundary cases)
def scripted_pcm(pattern) -> bytes:
    """pattern: [(is_speech, ms), ...] -> PCM where each 30 ms frame's first byte is the flag and bytes 1..4 its index."""
    total_ms = sum(ms for _, ms in pattern)
    flags_ms = []
    for flag, ms in pattern:
        flags_ms += [flag] * ms
    out = bytearray(total_ms * BYTES_PER_MS)
    for k in range(total_ms // FRAME_MS):
        off = k * FRAME_BYTES
        out[off] = 1 if flags_ms[k * FRAME_MS] else 0  # the frame's flag = the pattern at its first millisecond
        out[off + 1:off + 5] = struct.pack("<I", k)
    return bytes(out)


def frame_index(frame) -> int:
    return struct.unpack("<I", frame[1:5])[0]


class ContentClassifier:
    """Stateless: speech iff the frame says so."""
    def is_speech(self, frame, sample_rate):
        return frame[0] == 1


class DriftClassifier:
    """Stateful ACROSS scans, like a reused webrtcvad.Vad: every re-scan (frame 0 seen again) flips a toggle; on flipped
    scans the first silent frame after speech is reported as speech, so a segment's end moves by one frame per scan."""
    def __init__(self):
        self.scan, self.prev = 0, False

    def is_speech(self, frame, sample_rate):
        if frame_index(frame) == 0:
            self.scan += 1
            self.prev = False
        speech = frame[0] == 1
        out = speech or (self.prev and self.scan % 2 == 0)
        self.prev = speech
        return out


def reference_flags(pcm, classifier_factory):
    """One-shot segmentation + speech frames with a fresh (single-pass) classifier: the ground truth for invariants."""
    v = VAD()
    v._vad = classifier_factory()
    ref = [(s.start_ms, s.end_ms) for s in v.segment_speech(pcm)]
    c = classifier_factory()
    speech = [(k * FRAME_MS, (k + 1) * FRAME_MS) for k in range(len(pcm) // FRAME_BYTES)
              if c.is_speech(pcm[k * FRAME_BYTES:(k + 1) * FRAME_BYTES], 16000)]
    return ref, speech


# ------------------------------------------------------------------ invariants
def evaluate(processed, ref, speech) -> dict:
    """Metrics + invariants. 'excess' overlap = processed overlap beyond the overlap the one-shot segmentation itself has
    by design (the pre-roll after a forced 8 s cut); only excess counts as re-processing."""
    m = si.analyse(processed, ref, speech)
    designed = si.analyse(ref, ref, [])["overlap_ms"]
    m["designed_overlap_ms"] = designed
    m["excess_overlap_ms"] = max(0, m["overlap_ms"] - designed)
    m["not_in_reference"] = [s for s in processed if tuple(s) not in {tuple(r) for r in ref}]
    m["reference_not_processed"] = [r for r in ref if tuple(r) not in {tuple(s) for s in processed}]
    m["inv_no_reprocessing"] = m["excess_overlap_ms"] == 0 and len(processed) == len({tuple(s) for s in processed})
    m["inv_no_skipped_speech"] = m["missed_speech_ms"] == 0
    m["inv_boundaries_equal_reference"] = [tuple(s) for s in processed] == [tuple(r) for r in ref]
    return m


def run_one(pcm, chunk, cand, ns, classifier_factory=None, ref=None, speech=None):
    """Stream through the real live loop with a candidate; per-call latency recorded."""
    times = []
    real = ns._run_incremental_detection

    def timed(j, final=False):
        t = time.perf_counter()
        try:
            return real(j, final)
        finally:
            times.append(time.perf_counter() - t)
    ns._run_incremental_detection = timed
    try:
        sim = si.simulate(pcm, chunk, ns, vad_factory=factory(cand, classifier_factory))
        err = None
    except Exception as e:
        sim, err = {"processed": []}, f"{type(e).__name__}: {e}"
    finally:
        ns._run_incremental_detection = real
    out = evaluate(sim["processed"], ref, speech)
    out.update(error=err, calls=len(times), total_s=sum(times), p50_call_ms=1000 * statistics.median(times) if times else None,
               p95_call_ms=1000 * sorted(times)[int(0.95 * (len(times) - 1))] if times else None,
               max_call_ms=1000 * max(times) if times else None, processed_spans=sim["processed"],
               # cost at the END of the recording (largest buffer): mean of the last 10 % of calls, final flush excluded
               last_decile_mean_ms=1000 * statistics.mean(times[-max(1, len(times) // 10) - 1:-1]) if len(times) > 2 else None)
    return out


# ------------------------------------------------------------------ recordings run
def run_recordings(paths, chunks, cands, determinism_chunks=(100,)):
    ns = si.live_loop_namespace()
    phrases = si.manifest_phrases()
    rows = []
    for p in paths:
        pcm = si.decode(p)
        ref, speech = si.reference(pcm)
        phrase = phrases.get((p.parent.name, p.stem))
        for c in chunks:
            for cand in cands:
                r = run_one(pcm, c, cand, ns, None, ref, speech)
                r.update(file=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), chunk_ms=c, candidate=cand,
                         audio_ms=len(pcm) // BYTES_PER_MS)
                if c in determinism_chunks:
                    r["deterministic"] = run_one(pcm, c, cand, ns, None, ref, speech)["processed_spans"] == r["processed_spans"]
                if phrase:
                    cons = si.consequences(pcm, c, phrase, speech, ns, vad_factory=factory(cand))
                    r.update(phrase=phrase, extra_events=cons["extra_events"], escalated=cons["escalated_by_streaming"],
                             repeat_induced_trigger_all=cons["repeat_induced_trigger_all"],
                             stream_events=[e[:2] for e in cons["stream_events"]], oneshot_events=[e[:2] for e in cons["oneshot_events"]])
                rows.append(r)
                print(f"{cand:10s} {r['file'][-42:]:42s} {c:5d}ms proc={r['processed']:3d}/{r['reference_segments']:3d} "
                      f"excess={r['excess_overlap_ms']:6d} missed={r['missed_speech_ms']} eq_ref={r['inv_boundaries_equal_reference']} "
                      f"extra_ev={r.get('extra_events')} rep_ALL={r.get('repeat_induced_trigger_all')} p95={r['p95_call_ms']:.2f}ms "
                      f"err={r['error']}", flush=True)
    return rows


def summarise(rows):
    out = {}
    for r in rows:
        k = f"{r['candidate']}|{r['chunk_ms']}"
        s = out.setdefault(k, {"recordings": 0, "processed": 0, "reference_segments": 0, "excess_overlap_ms": 0, "recordings_with_excess": 0,
                               "duplicate_segments": 0, "reprocessed_segments": 0, "missed_speech_ms": 0, "recordings_missed_speech": 0,
                               "boundary_mismatch": 0, "recordings_not_equal_reference": 0, "extra_events": 0, "recordings_extra_events": 0,
                               "escalated": 0, "repeat_induced_trigger_all": 0, "errors": 0, "nondeterministic": 0,
                               "p50_call_ms": [], "p95_call_ms": [], "max_call_ms": 0.0, "total_s": 0.0})
        s["recordings"] += 1
        for f in ("processed", "reference_segments", "excess_overlap_ms", "duplicate_segments", "reprocessed_segments", "missed_speech_ms", "boundary_mismatch"):
            s[f] += r[f]
        s["recordings_with_excess"] += r["excess_overlap_ms"] > 0
        s["recordings_missed_speech"] += r["missed_speech_ms"] > 0
        s["recordings_not_equal_reference"] += not r["inv_boundaries_equal_reference"]
        s["extra_events"] += max(0, r.get("extra_events") or 0)
        s["recordings_extra_events"] += (r.get("extra_events") or 0) > 0
        s["escalated"] += bool(r.get("escalated"))
        s["repeat_induced_trigger_all"] += r.get("repeat_induced_trigger_all") or 0
        s["errors"] += r["error"] is not None
        s["nondeterministic"] += r.get("deterministic") is False
        s["p50_call_ms"].append(r["p50_call_ms"] or 0); s["p95_call_ms"].append(r["p95_call_ms"] or 0)
        s["max_call_ms"] = max(s["max_call_ms"], r["max_call_ms"] or 0); s["total_s"] += r["total_s"]
    for s in out.values():
        s["p50_call_ms"] = round(statistics.median(s["p50_call_ms"]), 3)
        s["p95_call_ms"] = round(statistics.median(s["p95_call_ms"]), 3)
        s["max_call_ms"] = round(s["max_call_ms"], 2)
        s["total_s"] = round(s["total_s"], 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--chunks", default="20,100,250,500,1000")
    ap.add_argument("--candidates", default="A_current,B_fresh,C_frontier,D_cached")
    ap.add_argument("--skip-converted", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    files = []
    for p in map(Path, a.paths):
        files += sorted(f for f in p.rglob("*") if f.suffix.lower() in si.AUDIO_EXT and not (a.skip_converted and f.name.startswith("_converted_"))) \
            if p.is_dir() else [p]
    rows = run_recordings([f.resolve() for f in files], [int(c) for c in a.chunks.split(",")], a.candidates.split(","))
    summ = summarise(rows)
    print(json.dumps(summ, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
