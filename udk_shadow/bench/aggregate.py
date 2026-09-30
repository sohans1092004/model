"""Aggregate interference.py runs: median across repeats of each per-run statistic, per (mode, stt_delay).

    python udk_shadow/bench/aggregate.py <dir with r_<mode>_<delay>_<rep>.json>
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def g(d, path):
    for k in path.split("."):
        d = None if d is None else d.get(k)
    return d


ROWS = [("live loop latency p50 (ms)", "live_latency_s.p50", 1000), ("live loop latency p95 (ms)", "live_latency_s.p95", 1000),
        ("live loop latency max (ms)", "live_latency_s.max", 1000),
        ("call start -> alert emitted p50 (ms)", "time_to_alert_s.p50", 1000), ("call start -> alert emitted p95 (ms)", "time_to_alert_s.p95", 1000),
        ("live semantic similarity per call (ms)", "live_semantic_s.per_call_ms", 1), ("live intent p_distress per call (ms)", "live_intent_s.per_call_ms", 1),
        ("CPU cores used (cpu_s / wall_s)", "cpu_cores_used", 1), ("peak RSS (MB)", "peak_rss_mb", 1),
        ("shadow processing per record p50 (ms)", "shadow.processing_s.p50", 1000), ("shadow processing p95 (ms)", "shadow.processing_s.p95", 1000),
        ("shadow queue wait p50 (ms)", "shadow.queue_wait_s.p50", 1000), ("shadow queue wait p95 (ms)", "shadow.queue_wait_s.p95", 1000),
        ("shadow queue wait max (ms)", "shadow.queue_wait_s.max", 1000), ("drain after last live segment (s)", "drain_after_last_segment_s", 1),
        ("shadow intent calls", "shadow_intent_s.calls", 1), ("dropped observations", "shadow.dropped_queue_full", 1),
        ("records Phase5 == live", "shadow.phase5_vs_live_match", 1), ("live events emitted", "live_events", 1),
        ("GPU utilisation mean (%)", "gpu.util_pct.mean", 1), ("GPU utilisation p95 (%)", "gpu.util_pct.p95", 1),
        ("GPU memory used max (MB, whole device)", "gpu.mem_used_mb.max", 1), ("torch peak allocated (MB)", "gpu.torch_peak_allocated_mb", 1)]


def main(d):
    runs = defaultdict(list)
    for p in sorted(Path(d).glob("r_*.json")):
        r = json.loads(p.read_text())
        runs[(r.get("device", "cpu"), r["stt_delay_s"], r["mode"])].append(r)
    keys = sorted(runs)
    print("| metric | " + " | ".join(f"{m} ({dv}, STT {s}s, n={len(runs[(dv, s, m)])})" for dv, s, m in keys) + " |")
    print("|---|" + "---|" * len(keys))
    for name, path, scale in ROWS:
        cells = []
        for k in keys:
            vals = [g(r, path) for r in runs[k]]
            vals = [v for v in vals if v is not None]
            cells.append("–" if not vals else f"{statistics.median(vals) * scale:.1f}" if isinstance(vals[0], float) else str(statistics.median(vals)))
        print(f"| {name} | " + " | ".join(cells) + " |")
    any_r = next(iter(runs.values()))[0]
    print(f"\ncpu_count={any_r['cpu_count']} torch_threads={any_r['torch_threads']} cuda_available={any_r['cuda_available']} "
          f"gpu={(any_r.get('gpu') or {}).get('name')} torch={any_r.get('torch_version')}")


if __name__ == "__main__":
    main(sys.argv[1])
