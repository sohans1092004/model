"""Offline measurement of live streaming-segmentation integrity (PHASE6_INTEGRATION_CONTRACT §10 Q3).

Question: when audio arrives in chunks, does the live path ever (a) process the same audio twice (overlapping processed
segments) or (b) never process audio that the VAD calls speech (skipped segments)?

Method (no models, no labels -- measurement only; the live code is NOT modified):
  * the REAL live loop `api._run_incremental_detection` (extracted from api.py with ast; api.py itself loads FastAPI and
    models at import) and the REAL `vad.VAD` (webrtcvad), run exactly as `_ingest_frame` does: append a chunk to the
    journey buffer, call the loop, repeat; at the end one `final=True` call, as `stop_journey` does (api.py:1242);
  * a transcript stub records every segment the live loop actually hands to STT (start_ms, end_ms), in order;
  * compared against (1) a one-shot segmentation of the complete buffer by a fresh VAD, and (2) webrtcvad's own speech
    frames (fresh Vad over the complete buffer).

Reported per recording x chunk size:
  processed            segments handed to STT
  overlap_ms           audio inside a processed segment that an EARLIER processed segment already covered
  duplicate_segments   processed segments whose span is entirely inside earlier processed audio
  reprocessed_segments processed segments at least half of whose audio an earlier processed segment already covered
  missed_ref_ms        audio inside the one-shot segments that no processed segment covered
  missed_speech_ms     webrtcvad speech frames (fresh one-shot pass) that no processed segment covered
  boundary_mismatch    processed segments not identical to a one-shot segment
Nothing here is a detection-performance measurement; it measures which audio reaches STT.

    python udk_shadow/bench/segmentation_integrity.py <audio files or dirs> [--chunks 20,100,250,500,1000] [--out results.json]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
import types
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SR = 16_000
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".flac", ".ogg")


# ------------------------------------------------------------------ interval helpers
def merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(x) for x in out]


def length(iv):
    return sum(b - a for a, b in merge(iv))


def subtract(a_iv, b_iv):
    """Parts of a_iv not covered by b_iv."""
    b = merge(b_iv)
    out = []
    for a0, a1 in merge(a_iv):
        cur = a0
        for b0, b1 in b:
            if b1 <= cur or b0 >= a1:
                continue
            if b0 > cur:
                out.append((cur, b0))
            cur = max(cur, b1)
        if cur < a1:
            out.append((cur, a1))
    return out


def analyse(processed, reference, speech):
    """processed: [(start, end)] in processing order; reference: one-shot segments; speech: speech frame spans."""
    seen, overlap, dup, mostly = [], 0, 0, 0
    for a, b in processed:
        inter = length([(a, b)]) - length(subtract([(a, b)], seen))
        overlap += inter
        if inter == b - a and b > a:
            dup += 1
        if b > a and inter >= 0.5 * (b - a):
            mostly += 1
        seen.append((a, b))
    return {"processed": len(processed), "reference_segments": len(reference),
            "overlap_ms": overlap, "duplicate_segments": dup, "reprocessed_segments": mostly,
            "missed_ref_ms": length(subtract(reference, processed)),
            "missed_speech_ms": length(subtract(speech, processed)),
            "boundary_mismatch": sum(1 for s in processed if tuple(s) not in {tuple(r) for r in reference}),
            "reference_ms": length(reference), "speech_ms": length(speech)}


# ------------------------------------------------------------------ the real live loop, stubbed around
def live_loop_namespace():
    from udk_engine import TRIGGER_VERIFY_THRESHOLD, DecisionEvent, match_transcript
    ns = types.ModuleType("live")
    ns.__dict__.update({"time": time, "DecisionEvent": DecisionEvent, "match_transcript": match_transcript,
                        "TRIGGER_VERIFY_THRESHOLD": TRIGGER_VERIFY_THRESHOLD, "_maybe_update_language": lambda j: None,
                        "_parakeet_stt": None, "_stt_backend": None, "_scream_trigger_enabled": False, "_scream_detector": None,
                        "_scream_corroboration_enabled": False, "_stt_confidence_gate_enabled": False, "is_suspect": lambda t: False,
                        "_dual_asr_guard": None, "_intent_gate": None, "_separator": None, "_shadow": None,
                        "_metrics": types.SimpleNamespace(stt_latency=lambda *a: None, detection=lambda *a: None),
                        "_emit_event": lambda *a: {}})
    for node in ast.parse((ROOT / "api.py").read_text()).body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_run_incremental_detection", "_either_stt_decisions", "_strongest", "_intent_veto"):
            exec(compile(ast.Module([node], []), "api.py", "exec"), ns.__dict__)
    return ns


@dataclass
class Tx:
    text: str = ""
    avg_logprob: float | None = None
    temperature: float | None = None


class RecordingVAD:
    """Wraps the live VAD; remembers the segments of the latest scan so the STT stub can name what it was given."""
    def __init__(self, vad):
        self.vad, self.last = vad, []

    def segment_speech(self, pcm):
        self.last = self.vad.segment_speech(pcm)
        return self.last

    def total_ms(self, pcm):
        return self.vad.total_ms(pcm)


class RecordingSTT:
    model_version = "recording-stub"

    def __init__(self, vad: RecordingVAD):
        self.vad, self.calls = vad, []

    def transcribe(self, pcm):
        seg = next(s for s in self.vad.last if s.pcm is pcm)
        self.calls.append((seg.start_ms, seg.end_ms))
        return Tx("")  # no text: the live loop then skips matching; which audio reached STT is what is measured


@dataclass
class Journey:
    vad: object
    stt: object
    journey_id: str = "SEGCHECK"
    started_at: float = 0.0
    audio_buffer: bytearray = field(default_factory=bytearray)
    processed_up_to_ms: int = 0
    kws: object = None
    engine: object = None
    events: list = field(default_factory=list)
    language: str | None = None


def simulate(pcm: bytes, chunk_ms: int, ns=None, vad_factory=None) -> dict:
    """Stream pcm (16 kHz mono s16le) through the real live loop in chunk_ms chunks. Returns processed spans + timing."""
    from vad import VAD
    ns = ns or live_loop_namespace()
    vad_factory = vad_factory or VAD
    rv = RecordingVAD(vad_factory())
    stt = RecordingSTT(rv)
    j = Journey(rv, stt)
    if hasattr(rv.vad, "bind"):  # candidates that read the journey's processed frontier (segmentation_candidates.py)
        rv.vad.bind(j)
    step = int(SR * chunk_ms / 1000) * 2
    t0, worst = time.perf_counter(), 0.0
    for i in range(0, len(pcm), step):
        j.audio_buffer.extend(pcm[i:i + step])
        c0 = time.perf_counter()
        ns._run_incremental_detection(j)
        worst = max(worst, time.perf_counter() - c0)
    ns._run_incremental_detection(j, final=True)
    return {"processed": stt.calls, "seconds": time.perf_counter() - t0, "worst_call_s": worst}


def reference(pcm: bytes, vad_factory=None):
    """One-shot segmentation and webrtcvad speech frames of the complete buffer, each from a FRESH VAD."""
    from vad import FRAME_BYTES, FRAME_MS, SAMPLE_RATE, VAD
    vad_factory = vad_factory or VAD
    ref = [(s.start_ms, s.end_ms) for s in vad_factory().segment_speech(pcm)]
    v = vad_factory()
    speech = [(k * FRAME_MS, (k + 1) * FRAME_MS)
              for k, i in enumerate(range(0, len(pcm) - FRAME_BYTES + 1, FRAME_BYTES))
              if v._vad.is_speech(pcm[i:i + FRAME_BYTES], SAMPLE_RATE)]
    return ref, speech


class PhraseSTT(RecordingSTT):
    """Consequence check: returns the recording's KNOWN spoken phrase (from its manifest, not invented) for any segment that
    contains webrtcvad speech, else no text -- so the real UDK engine sees what a correct STT would say for each span."""
    def __init__(self, vad, phrase, speech):
        super().__init__(vad)
        self.phrase, self.speech = phrase, merge(speech)

    def transcribe(self, pcm):
        seg = next(s for s in self.vad.last if s.pcm is pcm)
        self.calls.append((seg.start_ms, seg.end_ms))
        hit = any(a < seg.end_ms and b > seg.start_ms for a, b in self.speech)
        return Tx(self.phrase if hit else "")


def consequences(pcm: bytes, chunk_ms: int, phrase: str, speech, ns=None, vad_factory=None) -> dict:
    """Live alerts from streaming (chunked, as _ingest_frame) vs one pass over the complete buffer (the same live loop,
    called once with final=True on a fresh VAD), both through the real UDKEngine with no semantic model."""
    from udk_engine import UDKEngine
    from udks import GENERAL_UDKS
    from vad import VAD
    ns = ns or live_loop_namespace()

    def run(stream: bool):
        events = []
        ns._emit_event = lambda j, d, seg: events.append((d.decision, d.udk.udk_id if d.udk else None, seg.start_ms, seg.end_ms, d.reason)) or {}
        rv = RecordingVAD((vad_factory or VAD)() if stream else VAD())  # the one-pass reference always uses a fresh live VAD
        stt = PhraseSTT(rv, phrase, speech)
        j = Journey(rv, stt, engine=UDKEngine(list(GENERAL_UDKS)))
        if hasattr(rv.vad, "bind"):
            rv.vad.bind(j)
        if stream:
            step = int(SR * chunk_ms / 1000) * 2
            for i in range(0, len(pcm), step):
                j.audio_buffer.extend(pcm[i:i + step])
                ns._run_incremental_detection(j)
        else:
            j.audio_buffer.extend(pcm)
        ns._run_incremental_detection(j, final=True)
        return events
    st, one = run(True), run(False)
    tier = {"NO_ACTION": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2}
    return {"stream_events": st, "oneshot_events": one, "extra_events": len(st) - len(one),
            "max_tier_stream": max((tier[e[0]] for e in st), default=0), "max_tier_oneshot": max((tier[e[0]] for e in one), default=0),
            "escalated_by_streaming": max((tier[e[0]] for e in st), default=0) > max((tier[e[0]] for e in one), default=0),
            "repeat_reasons_stream": sum(1 for e in st if "repeat" in (e[4] or "")),
            # TRIGGER_ALL that exists only because streaming re-processed audio: a "repeated" ALL for a UDK the one pass
            # never escalated by repetition
            "repeat_induced_trigger_all": sum(1 for e in st if e[0] == "TRIGGER_ALL" and "repeat" in (e[4] or "")
                                              and not any(o[1] == e[1] and "repeat" in (o[4] or "") for o in one))}


def decode(path: Path) -> bytes:
    """Any audio file -> 16 kHz mono s16le PCM (PyAV / FFmpeg)."""
    import av
    import numpy as np
    out = []
    with av.open(str(path)) as c:
        rs = av.AudioResampler(format="s16", layout="mono", rate=SR)
        for frame in c.decode(audio=0):
            for f in rs.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
        for f in rs.resample(None):
            out.append(f.to_ndarray().reshape(-1))
    return (np.concatenate(out) if out else np.zeros(0, dtype=np.int16)).astype("<i2").tobytes()


def manifest_phrases() -> dict:
    """stem -> spoken phrase, from real_recordings/*/manifest.json (only recordings that ship a manifest)."""
    out = {}
    for m in (ROOT / "real_recordings").glob("*/manifest.json"):
        for row in json.loads(m.read_text(encoding="utf-8")):
            if row.get("phrase"):
                out[(m.parent.name, Path(row["file"]).stem)] = row["phrase"]
    return out


def run(paths, chunks) -> dict:
    ns = live_loop_namespace()
    phrases = manifest_phrases()
    rows = []
    for p in paths:
        pcm = decode(p)
        ref, speech = reference(pcm)
        phrase = phrases.get((p.parent.name, p.stem))
        for c in chunks:
            sim = simulate(pcm, c, ns)
            r = analyse(sim["processed"], ref, speech)
            if phrase:
                r.update(phrase=phrase, **consequences(pcm, c, phrase, speech, ns))
            r.update(file=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), chunk_ms=c,
                     audio_ms=len(pcm) // 2 * 1000 // SR, seconds=round(sim["seconds"], 3), worst_call_s=round(sim["worst_call_s"], 4),
                     processed_spans=sim["processed"], reference_spans=ref)
            rows.append(r)
            print(f"{r['file'][-60:]:60s} chunk={c:5d}ms processed={r['processed']:3d} ref={r['reference_segments']:3d} "
                  f"overlap={r['overlap_ms']:6d}ms dup={r['duplicate_segments']} missed_ref={r['missed_ref_ms']:6d}ms "
                  f"missed_speech={r['missed_speech_ms']:6d}ms mismatch={r['boundary_mismatch']}"
                  + (f" | alerts stream={len(r['stream_events'])} oneshot={len(r['oneshot_events'])} escalated={r['escalated_by_streaming']}"
                     if "stream_events" in r else ""), flush=True)
    return {"rows": rows, "summary": summarise(rows)}


def summarise(rows) -> dict:
    by = {}
    for r in rows:
        s = by.setdefault(r["chunk_ms"], {"recordings": 0, "audio_ms": 0, "speech_ms": 0, "overlap_ms": 0, "recordings_with_overlap": 0,
                                          "duplicate_segments": 0, "reprocessed_segments": 0, "missed_ref_ms": 0, "recordings_with_missed_ref": 0,
                                          "missed_speech_ms": 0, "recordings_with_missed_speech": 0, "boundary_mismatch": 0,
                                          "processed": 0, "reference_segments": 0, "worst_call_s": 0.0})
        s["recordings"] += 1
        for k in ("audio_ms", "speech_ms", "overlap_ms", "duplicate_segments", "reprocessed_segments", "missed_ref_ms", "missed_speech_ms", "boundary_mismatch",
                  "processed", "reference_segments"):
            s[k] += r[k]
        s["recordings_with_overlap"] += r["overlap_ms"] > 0
        s["recordings_with_missed_ref"] += r["missed_ref_ms"] > 0
        s["recordings_with_missed_speech"] += r["missed_speech_ms"] > 0
        s["worst_call_s"] = max(s["worst_call_s"], r["worst_call_s"])
        if "stream_events" in r:
            s["with_phrase"] = s.get("with_phrase", 0) + 1
            s["extra_alert_events"] = s.get("extra_alert_events", 0) + max(0, r["extra_events"])
            s["recordings_with_extra_alerts"] = s.get("recordings_with_extra_alerts", 0) + (r["extra_events"] > 0)
            s["recordings_escalated_by_streaming"] = s.get("recordings_escalated_by_streaming", 0) + r["escalated_by_streaming"]
            s["recordings_fewer_alerts_than_oneshot"] = s.get("recordings_fewer_alerts_than_oneshot", 0) + (r["extra_events"] < 0)
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--chunks", default="20,100,250,500,1000")
    ap.add_argument("--out")
    ap.add_argument("--skip-converted", action="store_true", help="skip _converted_*.wav (duplicates of the mp3s in real_recordings)")
    a = ap.parse_args()
    files = []
    for p in map(Path, a.paths):
        files += sorted(f for f in p.rglob("*") if f.suffix.lower() in AUDIO_EXT and not (a.skip_converted and f.name.startswith("_converted_"))) \
            if p.is_dir() else [p]
    res = run([f.resolve() for f in files], [int(c) for c in a.chunks.split(",")])
    print(json.dumps(res["summary"], indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
