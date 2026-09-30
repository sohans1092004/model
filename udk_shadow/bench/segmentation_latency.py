"""Sequential latency + determinism run for the segmentation candidates (run with NO other benchmark load).

Latency: per-call wall time of the real live loop (VAD + segmentation + loop; STT stubbed, so this isolates the
segmentation cost) for A/B/C/D on representative recordings and the longest one. Determinism: candidate D repeated on
the same input must give identical segment spans, identical cached frame classifications and identical UDK alert events.

    python udk_shadow/bench/segmentation_latency.py --out latency.json
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import segmentation_candidates as sc  # noqa: E402
import segmentation_integrity as si  # noqa: E402

LATENCY_SET = [  # (recording, chunk sizes)
    ("real_recordings/mixed/clip_01_clean.mp3", (20, 100, 250, 1000)),
    ("real_recordings/mixed/clip_19_muffled.mp3", (20, 100, 250, 1000)),
    ("real_recordings/negatives/5 podcasts you must listen Tamil.mp3", (100, 250, 1000)),
    ("real_recordings/negatives/Neil's difficult summer job in Canada 🫛  Practise your listening with Real Easy English - BBC Learning English.mp3",
     (100, 250, 1000)),  # the longest recording (326 s); 20 ms omitted: A/B re-classify the whole buffer 16 000+ times
]
DETERMINISM_SET = [("real_recordings/mixed/clip_19_muffled.mp3", (20, 250)), ("real_recordings/mixed/clip_28_overlapping.mp3", (20, 250)),
                   ("real_recordings/negatives/Heroine Powerful Fight Scene #ParuParvathy Deepika Das #shorts #ytshorts #youtubeshorts.mp3", (100,))]


def cached_flags(pcm, chunk, ns):
    """Run D once and return (processed spans, cached classifications)."""
    holder = {}

    def fac():
        holder["d"] = sc.CandidateD()
        return holder["d"]
    sim = si.simulate(pcm, chunk, ns, vad_factory=fac)
    return sim["processed"], list(holder["d"]._cache.flags)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", default="A_current,B_fresh,C_frontier,D_cached")
    a = ap.parse_args()
    ns = si.live_loop_namespace()
    phrases = si.manifest_phrases()
    lat = []
    for rel, chunks in LATENCY_SET:
        p = ROOT / rel
        pcm = si.decode(p)
        ref, speech = si.reference(pcm)
        for c in chunks:
            for cand in a.candidates.split(","):
                r = sc.run_one(pcm, c, cand, ns, None, ref, speech)
                row = {k: r[k] for k in ("calls", "total_s", "p50_call_ms", "p95_call_ms", "max_call_ms", "last_decile_mean_ms",
                                         "excess_overlap_ms", "missed_speech_ms", "inv_boundaries_equal_reference", "error")}
                row.update(file=rel, audio_s=len(pcm) / 32000, chunk_ms=c, candidate=cand)
                lat.append(row)
                print(f"{cand:10s} {rel[-40:]:40s} {c:5d}ms calls={row['calls']:6d} p50={row['p50_call_ms']:.3f} p95={row['p95_call_ms']:.3f} "
                      f"max={row['max_call_ms']:.2f} last10%={row['last_decile_mean_ms']:.2f} total={row['total_s']:.2f}s", flush=True)
    det = []
    for rel, chunks in DETERMINISM_SET:
        p = ROOT / rel
        pcm = si.decode(p)
        ref, speech = si.reference(pcm)
        phrase = phrases.get((p.parent.name, p.stem))
        for c in chunks:
            runs = [cached_flags(pcm, c, ns) for _ in range(3)]
            same_spans = all(r[0] == runs[0][0] for r in runs)
            same_flags = all(r[1] == runs[0][1] for r in runs)
            one_pass_flags = [s[0] // 30 for s in speech]  # speech frame indices from a fresh single-pass classifier
            flags_equal_single_pass = [i for i, f in enumerate(runs[0][1]) if f] == one_pass_flags
            alerts_same = None
            if phrase:
                ev = [[e[:2] for e in si.consequences(pcm, c, phrase, speech, ns, vad_factory=sc.factory("D_cached"))["stream_events"]]
                      for _ in range(3)]
                alerts_same = all(e == ev[0] for e in ev)
            det.append({"file": rel, "chunk_ms": c, "runs": 3, "identical_spans": same_spans, "identical_classifications": same_flags,
                        "classifications_equal_single_pass": flags_equal_single_pass, "identical_alerts": alerts_same,
                        "frames": len(runs[0][1])})
            print("determinism", det[-1], flush=True)
    env = {"python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor(),
           "cpu_count": __import__("os").cpu_count(), "note": "sequential; no other benchmark running"}
    Path(a.out).write_text(json.dumps({"environment": env, "latency": lat, "determinism": det}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
