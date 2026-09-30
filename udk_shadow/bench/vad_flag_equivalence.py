"""Full-corpus equivalence check for the vad.VAD `cache_classifications` prototype (candidate D in production code).

For every recording x chunk size, through the REAL live loop (api._run_incremental_detection, fed as _ingest_frame does,
then the stop_journey final flush):

  OFF  vad.VAD()                              vs  the frozen original vad.py of 96ea038 (vad_original_96ea038.py):
       every segment_speech call must return identical segments (start, end, pcm), and STT must receive identical spans.
       With a phrase manifest (mixed/), alert events must be identical too.
  ON   vad.VAD(cache_classifications=True)    vs  the experiment's candidate D (segmentation_candidates.CandidateD):
       identical per-call segments, identical processed spans, identical kept flags; and vs the one-shot segmentation:
       no excess overlap, no missed speech, boundaries equal. With a phrase: 0 extra alert events, events == one pass.

    python udk_shadow/bench/vad_flag_equivalence.py real_recordings/mixed --chunks 20,100,250,500,1000 --out mixed.json
    python udk_shadow/bench/vad_flag_equivalence.py real_recordings/positives real_recordings/negatives --skip-converted \
           --chunks 100,250,500,1000 --out media.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import segmentation_candidates as sc  # noqa: E402
import segmentation_integrity as si  # noqa: E402
import vad as live_vad  # noqa: E402

ORIGINAL_SHA256 = "f5978f8525cb6079a4344b38ea505af57f9430c6021783be3869a62cc184f371"  # vad.py at 96ea038
ORIGINAL_PATH = HERE / "vad_original_96ea038.py"


def load_original():
    """The frozen pre-prototype vad.py, as its own module (never imported as `vad`)."""
    got = hashlib.sha256(ORIGINAL_PATH.read_bytes()).hexdigest()
    if got != ORIGINAL_SHA256:
        raise RuntimeError(f"{ORIGINAL_PATH.name} is not the 96ea038 vad.py (sha256 {got})")
    spec = importlib.util.spec_from_file_location("vad_original_96ea038", ORIGINAL_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    return mod


class TraceVAD:
    """Records every segment_speech result (start, end, pcm digest) -- the full observable output of the VAD."""
    def __init__(self, vad):
        self.vad, self.trace = vad, []

    def segment_speech(self, pcm):
        segs = self.vad.segment_speech(pcm)
        self.trace.append(tuple((s.start_ms, s.end_ms, hashlib.blake2b(s.pcm, digest_size=8).digest()) for s in segs))
        return segs

    def total_ms(self, pcm):
        return self.vad.total_ms(pcm)


def stream(pcm, chunk, ns, make):
    holder = {}

    def factory():
        holder["t"] = TraceVAD(make())
        return holder["t"]
    t0 = time.perf_counter()
    sim = si.simulate(pcm, chunk, ns, vad_factory=factory)
    return sim["processed"], holder["t"], time.perf_counter() - t0


def events(pcm, chunk, phrase, speech, ns, make):
    c = si.consequences(pcm, chunk, phrase, speech, ns, vad_factory=make)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--chunks", default="100,250,500,1000")
    ap.add_argument("--skip-converted", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    orig = load_original()
    ns = si.live_loop_namespace()
    phrases = si.manifest_phrases()
    files = []
    for p in a.paths:
        p = (ROOT / p) if not Path(p).is_absolute() else Path(p)
        files += sorted(f for f in p.iterdir() if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac", ".webm")
                        and not (a.skip_converted and "_converted_" in f.name))
    rows = []
    for f in files:
        pcm = si.decode(f)
        ref, speech = si.reference(pcm)
        phrase = phrases.get((f.parent.name, f.stem))
        for c in (int(x) for x in a.chunks.split(",")):
            po, to, so = stream(pcm, c, ns, orig.VAD)
            pf, tf, sf = stream(pcm, c, ns, live_vad.VAD)
            pd, td, sd = stream(pcm, c, ns, sc.CandidateD)
            pn, tn, sn = stream(pcm, c, ns, lambda: live_vad.VAD(cache_classifications=True))
            ev = sc.evaluate(pn, ref, speech)
            r = {"file": str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else f.name, "chunk_ms": c, "calls": len(tf.trace),
                 "off_trace_equal_original": tf.trace == to.trace, "off_processed_equal_original": pf == po,
                 "off_cache_untouched": len(tf.vad._flag_cache) == 0 and tf.vad.cache_resets == 0,
                 "on_trace_equal_candidate_d": tn.trace == td.trace, "on_processed_equal_candidate_d": pn == pd,
                 "on_flags_equal_candidate_d": list(tn.vad._flag_cache) == [int(x) for x in td.vad._cache.flags],
                 "on_cache_frames": len(tn.vad._flag_cache), "on_cache_resets": tn.vad.cache_resets,
                 "on_excess_overlap_ms": ev["excess_overlap_ms"], "on_designed_overlap_ms": ev["designed_overlap_ms"],
                 "on_missed_speech_ms": ev["missed_speech_ms"], "on_boundaries_equal_reference": ev["inv_boundaries_equal_reference"],
                 "off_excess_overlap_ms": sc.evaluate(pf, ref, speech)["excess_overlap_ms"],
                 "seconds": {"original": so, "off": sf, "candidate_d": sd, "on": sn}}
            if phrase:
                co = events(pcm, c, phrase, speech, ns, orig.VAD)
                cf = events(pcm, c, phrase, speech, ns, live_vad.VAD)
                cn = events(pcm, c, phrase, speech, ns, lambda: live_vad.VAD(cache_classifications=True))
                r.update(phrase=phrase, off_events_equal_original=[e[:4] for e in cf["stream_events"]] == [e[:4] for e in co["stream_events"]],
                         off_extra_events=cf["extra_events"], off_repeat_induced_trigger_all=cf["repeat_induced_trigger_all"],
                         on_extra_events=cn["extra_events"], on_repeat_induced_trigger_all=cn["repeat_induced_trigger_all"],
                         on_escalated=cn["escalated_by_streaming"],
                         on_events_equal_one_pass=[e[:2] for e in cn["stream_events"]] == [e[:2] for e in cn["oneshot_events"]])
            rows.append(r)
            ok_off = r["off_trace_equal_original"] and r["off_processed_equal_original"] and r["off_cache_untouched"] and r.get("off_events_equal_original", True)
            ok_on = (r["on_trace_equal_candidate_d"] and r["on_processed_equal_candidate_d"] and r["on_flags_equal_candidate_d"]
                     and r["on_excess_overlap_ms"] == 0 and r["on_missed_speech_ms"] == 0 and r["on_boundaries_equal_reference"]
                     and r["on_cache_resets"] == 0 and r.get("on_extra_events", 0) == 0 and r.get("on_events_equal_one_pass", True))
            r["off_ok"], r["on_ok"] = ok_off, ok_on
            print(f"{r['file'][-44:]:44s} {c:5d}ms calls={r['calls']:5d} OFF==orig {ok_off}  ON==D&oneshot {ok_on}  "
                  f"(off excess {r['off_excess_overlap_ms']} ms, on excess {r['on_excess_overlap_ms']} ms)", flush=True)
    summary = {"rows": len(rows), "recordings": len(files), "off_ok": sum(r["off_ok"] for r in rows), "on_ok": sum(r["on_ok"] for r in rows),
               "off_excess_rows": sum(r["off_excess_overlap_ms"] > 0 for r in rows),
               "alert_rows": sum("phrase" in r for r in rows),
               "off_extra_events": sum(r.get("off_extra_events", 0) for r in rows),
               "off_repeat_induced_trigger_all": sum(r.get("off_repeat_induced_trigger_all", 0) for r in rows),
               "on_extra_events": sum(r.get("on_extra_events", 0) for r in rows),
               "on_repeat_induced_trigger_all": sum(r.get("on_repeat_induced_trigger_all", 0) for r in rows)}
    print("SUMMARY", json.dumps(summary))
    Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
