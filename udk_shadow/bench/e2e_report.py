"""Tables for the VAD-cache end-to-end impact report, from e2e_vad_cache.py's summary.json (dry run or real models).

    python udk_shadow/bench/e2e_report.py <summary.json> [> tables.md]
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def recompute(path, C):
    """Re-derive every comparison from the saved (digest-only) runs with the current comparison code."""
    import e2e_vad_cache as e2e
    out = []
    for c in C:
        r = json.load(open(Path(path).parent / "runs" / f"{c['id']}_{c['chunk_ms']}.json"))["runs"]
        assert c["on_equals_oneshot"], f"{c['id']} {c['chunk_ms']}: ON != one-shot, cannot stand in for it"
        oneshot = [(s["start_ms"], s["end_ms"]) for s in r["on0"]["segments"]]
        n = e2e.compare_runs(r["off0"], r["on0"], r.get("off1"), r.get("on1"), oneshot)
        for k in ("id", "set", "chunk_ms", "audio_s", "perf", "flags"):
            n[k] = c[k]
        n["final_status"] = {"off": r["off0"].get("final_status", "COMPLETE"), "on": r["on0"].get("final_status", "COMPLETE")}
        out.append(n)
    return out


def main(path, redo=False):
    d = json.load(open(path))
    env, C = d["environment"], d["comparisons"]
    if redo:
        C = recompute(path, C)
        print("(comparisons recomputed from runs/ with the current comparison code)\n")
    for c in C:  # summaries written before tier changes / timing existed: recompute from the saved per-run data
        if "timing" not in c:
            import e2e_vad_cache as e2e
            r = json.load(open(Path(path).parent / "runs" / f"{c['id']}_{c['chunk_ms']}.json"))["runs"]
            assert c["on_equals_oneshot"], "one-shot boundaries needed; ON == one-shot lets ON's boundaries stand in"
            oneshot = [(s["start_ms"], s["end_ms"]) for s in r["on0"]["segments"]]
            eo = sorted(e2e._ev(e) for e in r["off0"]["events"])
            en = sorted(e2e._ev(e) for e in r["on0"]["events"])
            oo, on_ = e2e._pair_events(eo, en)
            c["tier_changes"], c["events_only_off"], c["events_only_on"] = e2e._tier_changes(oo, on_)
            c["timing"] = e2e._timing(r["off0"]["segments"], r["on0"]["segments"], oneshot)
    print(f"Components: `{json.dumps(env['components'])}`\n")
    print(f"Rows: {len(C)} (recording x chunk size); repeats per mode: {env['repeats']}; clock: {env['clock']}\n")
    print("| Set | Chunk | Rows | Segments OFF / ON | ON == one-shot | Events OFF / ON | Unpaired events OFF-only / ON-only | "
          "TRIGGER_ALL OFF / ON | Repeat-induced ALL OFF / ON | Duplicate alerts OFF / ON (designed) | Repeat-stable OFF / ON | "
          "Not COMPLETE | Errors |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    agg = collections.defaultdict(collections.Counter)
    for c in C:
        a = agg[(c["set"], c["chunk_ms"])]
        a["rows"] += 1
        for k in ("segments_off", "segments_on", "events_off", "events_on", "trigger_all_off", "trigger_all_on"):
            a[k] += c[k]
        a["on_oneshot"] += c["on_equals_oneshot"]
        a["only_off"] += len(c["events_only_off"])
        a["only_on"] += len(c["events_only_on"])
        a["rep_off"] += len(c["repeat_induced_trigger_all_off"])
        a["rep_on"] += len(c["repeat_induced_trigger_all_on"])
        a["dup_off"] += len(c["duplicate_alerts_off"])
        a["dup_on"] += len(c["duplicate_alerts_on"])
        a["dup_on_designed"] += sum(x.get("designed", False) for x in c["duplicate_alerts_on"])
        det = c["determinism"]
        a["stable_off"] += bool(det["off_vs_off_repeat_events"] and det["off_vs_off_repeat_segments"])
        a["stable_on"] += bool(det["on_vs_on_repeat_events"] and det["on_vs_on_repeat_segments"])
        a["incomplete"] += any(v != "COMPLETE" for v in c.get("final_status", {}).values())
        a["errors"] += bool(c["errors"]["off"] or c["errors"]["on"])
    for (s, ch), a in sorted(agg.items()):
        print(f"| {s} | {ch} ms | {a['rows']} | {a['segments_off']} / {a['segments_on']} | {a['on_oneshot']}/{a['rows']} | "
              f"{a['events_off']} / {a['events_on']} | {a['only_off']} / {a['only_on']} | {a['trigger_all_off']} / {a['trigger_all_on']} | "
              f"{a['rep_off']} / {a['rep_on']} | {a['dup_off']} / {a['dup_on']} ({a['dup_on_designed']}) | {a['stable_off']} / {a['stable_on']} | "
              f"{a['incomplete']} | {a['errors']} |")
    print("\nTier changes and per-utterance timing (virtual stream clock; delay = OFF - ON)")
    print("| Set | Chunk | Tier changes OFF->ON | Utterances decided >1 s later by OFF | Max decision delay s | "
          "Alerts >1 s later by OFF | Max alert delay s | Utterances alerted only by OFF / only by ON |")
    print("|---|---|---|---|---|---|---|---|")
    tagg = collections.defaultdict(lambda: {"tier": collections.Counter(), "late": 0, "maxd": 0.0, "late_a": 0, "maxa": 0.0, "ao": 0, "an": 0})
    for c in C:
        a = tagg[(c["set"], c["chunk_ms"])]
        for eo_, en_ in c["tier_changes"]:
            a["tier"][f"{eo_[1]}->{en_[1]}"] += 1
        for u in c["timing"]:
            dd, da = u["first_decision_delay_s"], u["first_alert_delay_s"]
            if dd is not None:
                a["late"] += dd > 1.0
                a["maxd"] = max(a["maxd"], dd)
            if da is not None:
                a["late_a"] += da > 1.0
                a["maxa"] = max(a["maxa"], da)
            a["ao"] += u["alert_only_off"]
            a["an"] += u["alert_only_on"]
    for (s, ch), a in sorted(tagg.items()):
        print(f"| {s} | {ch} ms | {dict(a['tier']) or 0} | {a['late']} | {a['maxd']:.1f} | {a['late_a']} | {a['maxa']:.1f} | {a['ao']} / {a['an']} |")
    print("\nTier changes (all rows):")
    for c in C:
        for eo_, en_ in c["tier_changes"]:
            print(f"- {c['id']} {c['chunk_ms']} ms OFF {eo_} -> ON {en_}")
    print("\nUtterances OFF handled >1 s later than ON (all rows):")
    for c in C:
        for u in c["timing"]:
            if (u["first_decision_delay_s"] or 0) > 1.0 or (u["first_alert_delay_s"] or 0) > 1.0:
                print(f"- {c['id']} {c['chunk_ms']} ms utterance {u['utterance']}: decision +{u['first_decision_delay_s']} s, "
                      f"alert +{u['first_alert_delay_s']} s")
    cls = collections.Counter()
    kinds = collections.Counter()
    fields = collections.Counter()
    review = []
    for c in C:
        for k, v in c["field_diff_counts"].items():
            fields[k] += v
        for x in c["differences"]:
            cls[x["class"]] += 1
            kinds[(x["kind"], x.get("detail", "").split(":")[0])] += 1
            if x["class"] != "expected_vad_correction" or x.get("needs_review"):
                review.append((c["id"], c["chunk_ms"], x["kind"], x.get("segment"), x["class"], x.get("detail"), x.get("fields")))
    print("\nDifference classes:", dict(cls))
    print("\nDifference kinds:", {f"{k[0]} / {k[1]}": v for k, v in kinds.items()})
    print("\nSame-boundary field differences (segments):", dict(fields) or "none")
    print("\nUnpaired events (all rows):")
    for c in C:
        for e in c["events_only_off"]:
            print(f"- {c['id']} {c['chunk_ms']} ms OFF-only {e}")
        for e in c["events_only_on"]:
            print(f"- {c['id']} {c['chunk_ms']} ms ON-only {e}")
    print("\nRepeat-induced TRIGGER_ALL (all rows):")
    for c in C:
        for x in c["repeat_induced_trigger_all_off"]:
            print(f"- {c['id']} {c['chunk_ms']} ms OFF {x}")
        for x in c["repeat_induced_trigger_all_on"]:
            print(f"- {c['id']} {c['chunk_ms']} ms ON {x}")
    print(f"\nFlagged for review ({len(review)}): not 'expected_vad_correction', or an OFF-only segment that alerted")
    for r in review:
        print("-", r)
    print("\nPerformance (per recording x chunk, repeat 0): live-loop call latency and totals")
    print("| Recording | Chunk | Mode | Calls | p50 ms | p95 ms | max ms | Total s | Wall s | CPU s | Components s | GPU peak MB |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in C:
        for m in ("off0", "on0"):
            p = c["perf"].get(m)
            if not p:
                continue
            q = p["calls"]
            print(f"| {c['id']} | {c['chunk_ms']} | {m[:-1].upper()} | {q.get('n')} | {q.get('p50_ms')} | {q.get('p95_ms')} | {q.get('max_ms')} | "
                  f"{q.get('total_s')} | {p['wall_s']} | {p['cpu_s']} | {p['segment_component_s']} | {(p['gpu'] or {}).get('torch_peak_alloc_mb')} |")


if __name__ == "__main__":
    main(sys.argv[1], "--recompute" in sys.argv[2:])
