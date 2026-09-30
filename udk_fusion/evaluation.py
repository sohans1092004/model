"""Evaluation / reporting interface for Phase 5 decisions.

evaluate(items, provenance) with items = [(FusedDecision, label "SAFE"|"DANGER", condition, group)]:
  per condition ("all" + each), per group:
    danger_alert_recall      DANGER items with any alert           (num / den)
    danger_trigger_all_rate  DANGER items at TRIGGER_ALL
    safe_false_alert         SAFE items with any alert
    safe_false_trigger_all   SAFE items at TRIGGER_ALL
    by_basis                 counts of none / linguistic / acoustic / fused
    rules                    how often each rule fired
    partial_evidence         items decided with uncertain / unavailable evidence
    vetoes_reinstated        R3 / R4 reinstatements
compare(items_by_policy, provenance)  the same report per policy (e.g. S-4 options A-D), side by side --
  a report, never a selection.

`provenance` is required: "real_dev", "real_eval", "synthetic" or "fixture". Anything but real_* is
stamped performance_claims_allowed=False; "fixture" reports carry a TOY banner. There is no final_test
provenance: final-test scoring is a separate frozen step (Phase 2A discipline), never this interface.
"""
from __future__ import annotations

from collections import Counter, defaultdict

PROVENANCE = ("real_dev", "real_eval", "synthetic", "fixture")


def _r(n, d):
    return {"value": n / d if d else None, "num": n, "den": d}


def _one(rows) -> dict:
    dz = [d for d, lab in rows if lab == "DANGER"]
    sf = [d for d, lab in rows if lab == "SAFE"]
    rules = Counter(r for d, _ in rows for r in d.rules_fired)
    return {"items": len(rows),
            "danger_alert_recall": _r(sum(d.decision != "NO_ALERT" for d in dz), len(dz)),
            "danger_trigger_all_rate": _r(sum(d.decision == "TRIGGER_ALL" for d in dz), len(dz)),
            "safe_false_alert": _r(sum(d.decision != "NO_ALERT" for d in sf), len(sf)),
            "safe_false_trigger_all": _r(sum(d.decision == "TRIGGER_ALL" for d in sf), len(sf)),
            "by_basis": dict(Counter(d.basis for d, _ in rows)),
            "rules": dict(sorted(rules.items())),
            "partial_evidence": sum(d.evidence_status == "partial" for d, _ in rows),
            "vetoes_reinstated": sum(any(r.endswith("veto_reinstated") for r in d.rules_fired) for d, _ in rows)}


def evaluate(items, provenance: str) -> dict:
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {PROVENANCE} (final-test scoring is not done here)")
    for _, lab, _, _ in items:
        if lab not in ("SAFE", "DANGER"):
            raise ValueError("label must be SAFE or DANGER")
    by_cond, by_group = defaultdict(list), defaultdict(list)
    for d, lab, cond, grp in items:
        by_cond["all"].append((d, lab))
        by_cond[cond].append((d, lab))
        by_group[grp].append((d, lab))
    rep = {"provenance": provenance, "performance_claims_allowed": provenance.startswith("real_"),
           "by_condition": {c: _one(r) for c, r in sorted(by_cond.items())},
           "by_group": {g: _one(r) for g, r in sorted(by_group.items())}}
    if provenance == "fixture":
        rep["banner"] = "TOY FIXTURE: checks decision logic only; not a performance measurement"
    return rep


def compare(items_by_policy: dict, provenance: str) -> dict:
    return {"provenance": provenance, "note": "side-by-side report; choosing a policy is an owner decision",
            "policies": {name: evaluate(items, provenance) for name, items in items_by_policy.items()}}
