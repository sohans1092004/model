"""Comparison reporting over shadow records (in-memory list or JSONL lines).

This is an OPERATIONAL comparison of two decision paths on the same inputs. There are no labels, so it says
nothing about which path is right: it is not a performance measurement.

compare(records, runner_stats=None) ->
  status_counts            ok / partial / failed / not_sampled / skipped_live_no_text (+ dropped_queue_full)
  failures_by_stage        stage -> count
  live_vs_phase3 / live_vs_phase5   match / shadow_higher / shadow_lower (segment tier)
  udk_set_differences      segments where the alerting UDK ids differ even if the tier matches
  difference_causes        for every live-vs-Phase-5 difference, which recorded evidence explains it:
                           scream_correlated, stt_selection_changed_by_scream, context_veto (Phase 3 vetoed:context or
                           Phase 5 R3), phase5_rules:<R>, separation_recovered (not comparable), replay_divergence_no_scream,
                           unexplained
  scream_correlated        counts of differences that coincide with a live scream signal
  no_data                  evidence UNAVAILABLE counts per kind/source; segments with no Phase 3 / Phase 5 decision
"""
from __future__ import annotations

import json
from collections import Counter

RANK = {"NO_ALERT": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2}
REPLAY_NOTE = ("Phase 3 / Phase 5 inputs come from a COUNTERFACTUAL linguistic replay (scream_score=None from the live engine "
               "state). It is not the live path with BEATs disabled: BEATs can change which STT list live kept "
               "(stt_choice_differs_from_live), so a difference there is a counterfactual difference, not a live-path bug.")
BANNER = "OPERATIONAL live-vs-shadow comparison. No labelled evaluation set exists: this is NOT a performance measurement."


def _cmp(live, shadow) -> str:
    if shadow is None:
        return "no_shadow_decision"
    return "match" if RANK[live] == RANK[shadow] else "shadow_higher" if RANK[shadow] > RANK[live] else "shadow_lower"


def _scream(rec) -> bool:
    a = rec.get("acoustic_observed", {})
    s = rec.get("scream_score")
    return bool(a.get("scream_fired")) or (s is not None and s >= 0.30)


def causes(rec) -> list[str]:
    out = []
    live = rec.get("live", {})
    if live.get("separation_recovered"):
        out.append("separation_recovered")
    if _scream(rec):
        out.append("scream_correlated")
    rep = rec.get("replay", {})
    if rep and live.get("live_chosen_stt") and rep.get("chosen_stt") != live.get("live_chosen_stt"):
        out.append("stt_selection_changed_by_scream" if _scream(rec) else "stt_selection_changed")
    p3 = rec.get("phase3") or []
    if any(p["source"] == "vetoed:context" for p in p3):
        out.append("context_veto")
    rules = sorted({r for e in (rec.get("phase5_events") or []) + [rec.get("phase5_segment_acoustic_alone") or {}]
                    for r in e.get("rules_fired", []) if r.startswith(("R3", "R4", "R5", "R6"))})
    if any(r.startswith("R3") for r in rules) and "context_veto" not in out:
        out.append("context_veto")
    out += [f"phase5_rules:{r}" for r in rules]
    if not _scream(rec) and rep:
        live_pre = [(d["decision"], d["udk_id"]) for d in live.get("pre_veto", [])]
        rep_ev = [(d["decision"], d["udk_id"]) for d in rep.get("events", [])]
        if live_pre and live_pre != rep_ev:
            out.append("replay_divergence_no_scream")
    return out or ["unexplained"]


def compare(records, runner_stats: dict | None = None) -> dict:
    recs = [json.loads(r) if isinstance(r, str) else r for r in records]
    st = Counter(r.get("status") for r in recs)
    if runner_stats:
        st["dropped_queue_full"] = runner_stats.get("dropped_queue_full", 0)
        st["capture_errors"] = runner_stats.get("capture_errors", 0)
    fail = Counter(e["stage"] for r in recs for e in r.get("errors", []))
    lv3, lv5, cz, udk_diff, scr = Counter(), Counter(), Counter(), 0, Counter()
    no_data = Counter()
    examples = []
    for r in recs:
        for e in r.get("phase4_evidence", []):
            if e.get("state") == "unavailable":
                no_data[f"{e['kind']}/{e['source']}"] += 1
        if r.get("status") not in ("ok", "partial"):
            continue
        live = r["live"]["live_decision"]
        lv3[_cmp(r["live"]["live_linguistic_decision"], r.get("shadow_phase3_decision"))] += 1
        c5 = _cmp(live, r.get("shadow_phase5_decision"))
        lv5[c5] += 1
        if r.get("shadow_phase3_decision") is None:
            no_data["segments_without_phase3_decision"] += 1
        if r.get("shadow_phase5_decision") is None:
            no_data["segments_without_phase5_decision"] += 1
        live_udks = {e["udk_id"] for e in r["live"]["emitted_events"] if e.get("udk_id")}
        p5_udks = {e["contributing"][0].get("udk_id") for e in (r.get("phase5_events") or [])
                   if e["decision"] != "NO_ALERT" and e.get("contributing") and e["contributing"][0].get("kind") == "linguistic"}
        if live_udks != p5_udks and r.get("shadow_phase5_decision") is not None:
            udk_diff += 1
        if c5 not in ("match",) or live_udks != p5_udks:
            cs = causes(r)
            for c in cs:
                cz[c] += 1
            if _scream(r):
                scr[c5] += 1
            if len(examples) < 20:
                examples.append({"segment_id": r["segment_id"], "live": live, "phase5": r.get("shadow_phase5_decision"),
                                 "live_udks": sorted(live_udks), "phase5_udks": sorted(p5_udks), "causes": cs})
    flips = sum(1 for r in recs if (r.get("replay") or {}).get("stt_choice_differs_from_live"))
    return {"banner": BANNER, "replay_semantics": REPLAY_NOTE, "stt_choice_differs_from_live": flips, "records": len(recs), "status_counts": dict(st), "failures_by_stage": dict(fail),
            "live_vs_phase3": dict(lv3), "live_vs_phase5": dict(lv5), "udk_set_differences": udk_diff,
            "difference_causes": dict(cz), "scream_correlated_differences": dict(scr), "no_data": dict(no_data),
            "examples": examples}
