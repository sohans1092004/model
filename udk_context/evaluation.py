"""Evaluation of the context layer on scenes (Phase 1 §15 problem types, §18 context metrics).

Every metric is reported PER problem_type (A_standard_udk, B_custom_udk, C_danger_no_udk), never
pooled (Phase 1 §15), with num/den:
  danger_recall, safe_false_alarm_rate, pair_separation (SAFE twin silent AND DANGER twin alerting),
  role_conditioned_recall (preceding context role: attacker / friend / other / none),
  turn_order (attacker->victim vs victim->attacker scenes judged correctly),
  overlap_recall by relative level, negation (SAFE 'negation' family false alarms,
  DANGER 'negation_but_danger' recall), by context family and by language set.
Target-speaker identification / attribution accuracy need the SYSTEM's speaker attribution; no
diarization exists at runtime, so they are UNAVAILABLE (C-3) rather than computed from labels.
recall_check(): DANGER scenes the production-equivalent path caught and a configuration lost
(Phase 0 §22 rule 5: any lost real danger fails unless the owner accepts it).
final_test: totals only, no per-scene failures; tuning on it is refused.
"""
from __future__ import annotations

from collections import defaultdict

from udk_context.context_window import build_window
from udk_context.decision import decide


def run_layer(scenes, cfg, evidence_fn, sentence_scorer=None, context_scorer=None) -> dict:
    w = cfg.sec("window")
    out = {}
    for s in scenes:
        win = build_window(s, w["window_s"], w["max_turns"])
        out[s.scene_id] = decide(evidence_fn(s), win, cfg, sentence_scorer, context_scorer)
    return out


def _alert(d) -> bool:
    return d.decision != "NO_ACTION"


def _ratio(n, d):
    return {"value": n / d if d else None, "num": n, "den": d}


def _context_role(s) -> str:
    tgt = s.target
    roles = {t.role for t in s.turns if t.turn_index < tgt.turn_index and t.speaker_id and t.speaker_id != tgt.speaker_id}
    if not any(t.turn_index < tgt.turn_index for t in s.turns):
        return "none"
    return "attacker" if "attacker" in roles else "friend" if "friend" in roles else "other"


def _turn_order(s) -> str | None:
    tgt = s.target
    before = {t.role for t in s.turns if t.turn_index < tgt.turn_index}
    if tgt.role == "victim" and "attacker" in before:
        return "attacker_to_victim"
    if tgt.role == "attacker" and "victim" in before:
        return "victim_to_attacker"
    return None


def evaluate(scenes, decisions: dict, split: str) -> dict:
    sel = [s for s in scenes if s.split == split]
    if not sel:
        raise ValueError(f"no scenes in split {split!r}")
    final = split == "final_test"
    per = {}
    for pt in sorted({s.problem_type for s in sel}):
        ss = [s for s in sel if s.problem_type == pt]
        dang = [s for s in ss if s.label == "DANGER"]
        safe = [s for s in ss if s.label == "SAFE"]
        m = {"danger_recall": _ratio(sum(_alert(decisions[s.scene_id]) for s in dang), len(dang)),
             "safe_false_alarm_rate": _ratio(sum(_alert(decisions[s.scene_id]) for s in safe), len(safe))}
        pairs = defaultdict(dict)
        for s in ss:
            if s.pair_id:
                pairs[s.pair_id][s.label] = s
        full = [p for p in pairs.values() if set(p) == {"SAFE", "DANGER"}]
        m["pair_separation"] = _ratio(sum(_alert(decisions[p["DANGER"].scene_id]) and not _alert(decisions[p["SAFE"].scene_id])
                                          for p in full), len(full))
        if not final:
            rc = defaultdict(lambda: [0, 0])
            for s in dang:
                rc[_context_role(s)][0] += _alert(decisions[s.scene_id])
                rc[_context_role(s)][1] += 1
            m["role_conditioned_recall"] = {k: _ratio(*v) for k, v in sorted(rc.items())}
            to = defaultdict(lambda: [0, 0])
            for s in ss:
                o = _turn_order(s)
                if o:
                    to[o][0] += _alert(decisions[s.scene_id]) == (s.label == "DANGER")
                    to[o][1] += 1
            m["turn_order_correct"] = {k: _ratio(*v) for k, v in sorted(to.items())}
            ov = defaultdict(lambda: [0, 0])
            for s in dang:
                if s.overlap:
                    key = f"rel_db={s.overlap.get('rel_db')}|attributed={all(t.speaker_id for t in s.turns)}"
                    ov[key][0] += _alert(decisions[s.scene_id])
                    ov[key][1] += 1
            m["overlap_recall"] = {k: _ratio(*v) for k, v in sorted(ov.items())}
            fam = defaultdict(lambda: [0, 0])
            for s in ss:
                fam[f"{s.context_family}|{s.label}"][0] += _alert(decisions[s.scene_id])
                fam[f"{s.context_family}|{s.label}"][1] += 1
            m["alert_rate_by_context_family"] = {k: _ratio(*v) for k, v in sorted(fam.items())}
            lang = defaultdict(lambda: [0, 0])
            for s in ss:
                k = f"{'+'.join(s.languages)}|{s.label}"
                lang[k][0] += _alert(decisions[s.scene_id])
                lang[k][1] += 1
            m["alert_rate_by_language"] = {k: _ratio(*v) for k, v in sorted(lang.items())}
        per[pt] = m
    report = {"split": split, "scenes": len(sel), "by_problem_type": per, "totals_only": final,
              "target_speaker_identification_accuracy": "UNAVAILABLE (no runtime speaker attribution, C-3)",
              "speaker_attribution_accuracy": "UNAVAILABLE (no runtime speaker attribution, C-3)"}
    if not final:
        report["failures"] = [{"scene_id": s.scene_id, "problem_type": s.problem_type, "label": s.label,
                               "decision": decisions[s.scene_id].decision, "source": decisions[s.scene_id].source,
                               "reasons": decisions[s.scene_id].reasons}
                              for s in sel if _alert(decisions[s.scene_id]) != (s.label == "DANGER")]
    return report


def recall_check(scenes, baseline: dict, candidate: dict, split: str) -> dict:
    lost = [s.scene_id for s in scenes if s.split == split and s.label == "DANGER"
            and _alert(baseline[s.scene_id]) and not _alert(candidate[s.scene_id])]
    gained = [s.scene_id for s in scenes if s.split == split and s.label == "DANGER"
              and not _alert(baseline[s.scene_id]) and _alert(candidate[s.scene_id])]
    silenced_safe = [s.scene_id for s in scenes if s.split == split and s.label == "SAFE"
                     and _alert(baseline[s.scene_id]) and not _alert(candidate[s.scene_id])]
    return {"lost_danger": lost, "gained_danger": gained, "silenced_false_alarms": silenced_safe,
            "passes_recall_first": not lost}
