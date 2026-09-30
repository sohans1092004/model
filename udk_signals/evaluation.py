"""Evaluation hooks for Phase 4 signals (Phase 1 §18 speaker metrics + acoustic / overlap / robustness).

All metrics are num/den; UNAVAILABLE and UNCERTAIN are counted separately and NEVER scored as a
negative ("no attribution" is not "not the target"). Every report is grouped by condition
(clean / pocket / far_field / traffic / crowd / ...), real vs synthetic kept apart by the caller.

  target_speaker_metrics(items)   items: (evidence, is_target: bool, condition)
      identification accuracy on decided items, false accept / false reject, coverage, undecided.
  attribution_metrics(items)      items: (evidence, true_speaker_ids: list, condition)
      accuracy after one-to-one label mapping on single-speaker segments; merged_overlap_violations =
      overlapped segments given ONE label (must be 0).
  overlap_metrics(items)          items: (evidence, true_overlap: bool, condition): precision / recall.
  acoustic_metrics(items)         items: (evidences, is_distress: bool, condition, label): distress recall
      and hard-negative false positives, per source.
"""
from __future__ import annotations

from collections import defaultdict

from udk_signals.evidence import NEGATIVE, POSITIVE, UNAVAILABLE, UNCERTAIN


def _r(n, d):
    return {"value": n / d if d else None, "num": n, "den": d}


def _by_condition(items, fn):
    groups = defaultdict(list)
    for it in items:
        groups["all"].append(it)
        groups[it[2]].append(it)
    return {c: fn(g) for c, g in sorted(groups.items())}


def target_speaker_metrics(items) -> dict:
    def one(g):
        decided = [(e, t) for e, t, _ in g if e.state in (POSITIVE, NEGATIVE)]
        return {"items": len(g), "coverage": _r(len(decided), len(g)),
                "identification_accuracy": _r(sum((e.state == POSITIVE) == t for e, t in decided), len(decided)),
                "false_accept": _r(sum(e.state == POSITIVE and not t for e, t in decided), sum(1 for _, t, _ in g if not t)),
                "false_reject": _r(sum(e.state == NEGATIVE and t for e, t in decided), sum(1 for _, t, _ in g if t)),
                "uncertain": sum(e.state == UNCERTAIN for e, _, _ in g), "unavailable": sum(e.state == UNAVAILABLE for e, _, _ in g)}
    return _by_condition(items, one)


def attribution_metrics(items) -> dict:
    def one(g):
        single = [(e, ids) for e, ids, _ in g if len(ids) == 1 and e.state == POSITIVE]
        # one-to-one mapping: each predicted label -> the true speaker it most often co-occurs with
        co = defaultdict(lambda: defaultdict(int))
        for e, ids in single:
            co[e.detail["label"]][ids[0]] += 1
        mapping, used = {}, set()
        for lab, cnt in sorted(co.items(), key=lambda kv: -max(kv[1].values())):
            best = max((c, s) for s, c in cnt.items() if s not in used) if any(s not in used for s in cnt) else None
            if best:
                mapping[lab] = best[1]
                used.add(best[1])
        correct = sum(mapping.get(e.detail["label"]) == ids[0] for e, ids in single)
        overlapped = [(e, ids) for e, ids, _ in g if len(ids) > 1]
        return {"segments": len(g), "attributed_single_speaker": len(single),
                "attribution_accuracy": _r(correct, len(single)),
                "merged_overlap_violations": sum(1 for e, _ in overlapped if e.state == POSITIVE and e.detail.get("label")),
                "unattributed": sum(e.state in (UNCERTAIN, UNAVAILABLE) for e, _, _ in g)}
    return _by_condition(items, one)


def overlap_metrics(items) -> dict:
    def one(g):
        dec = [(e, t) for e, t, _ in g if e.state in (POSITIVE, NEGATIVE)]
        tp = sum(e.state == POSITIVE and t for e, t in dec)
        return {"items": len(g), "precision": _r(tp, sum(e.state == POSITIVE for e, _ in dec)),
                "recall": _r(tp, sum(1 for _, t, _ in g if t)),
                "undecided": sum(e.state in (UNCERTAIN, UNAVAILABLE) for e, _, _ in g)}
    return _by_condition(items, one)


def acoustic_metrics(items) -> dict:
    def one(g):
        out = {}
        sources = sorted({e.source for evs, _, _, _ in g for e in evs})
        for src in sources:
            rows = [(next((e for e in evs if e.source == src), None), d, lab) for evs, d, _, lab in g]
            rows = [(e, d, lab) for e, d, lab in rows if e is not None]
            out[src] = {"distress_recall": _r(sum(e.state == POSITIVE for e, d, _ in rows if d), sum(1 for _, d, _ in rows if d)),
                        "hard_negative_false_positive": _r(sum(e.state == POSITIVE for e, d, _ in rows if not d),
                                                           sum(1 for _, d, _ in rows if not d)),
                        "uncertain_or_unavailable": sum(e.state in (UNCERTAIN, UNAVAILABLE) for e, _, _ in rows),
                        "false_positive_labels": sorted({lab for e, d, lab in rows if not d and e.state == POSITIVE})}
        return out
    return _by_condition([(evs, d, c, lab) for evs, d, c, lab in items], one)
