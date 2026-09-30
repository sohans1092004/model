"""Phase 2A §7 evidence record for ONE candidate against the frozen baseline (Phase 2B input).

    python -m asr_bench.decision_evidence --baseline base_report.json --candidate cand_report.json
        --compare compare.json --out evidence.json [--candidate-meta run.jsonl.meta.json]
        [--licence licence_record.json] [--freeze final_test_freeze.json] [--evidence-config ev.json]

Mechanical only: every §7 rule becomes PASS, FAIL or UNAVAILABLE (with the reason and the numbers,
intervals included). It does NOT pick a winner and does NOT make the representation decision;
the record says so. Point estimates decide PASS/FAIL; whether each paired 95% interval excludes
zero is reported next to it (M-5: whether "beat" / "not worse" needs significance is open).
Inputs are report.py outputs on dev (§6.2: candidates are compared on dev), same benchmark config.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EVIDENCE_FORMAT = "asr_bench.decision_evidence/1"
PASS, FAIL, UNAVAILABLE = "PASS", "FAIL", "UNAVAILABLE"


class EvidenceError(ValueError):
    pass


def _real_all(rep: dict, sl: str) -> dict | None:
    return rep["slices"].get(sl, {}).get("all", {}).get("real")


def _val(block, metric):
    return None if block is None else block["metrics"][metric]["value"]


def _cmp(cmp: dict | None, sl: str, metric: str) -> dict | None:
    return None if cmp is None else cmp["slices"].get(sl, {}).get("real", {}).get(metric)


def _excludes_zero(d: dict | None, favourable: str) -> bool | None:
    if not d or not d.get("ci95"):
        return None
    lo, hi = d["ci95"]
    return lo > 0 if favourable == "higher" else hi < 0


def _rule(rule, dimension, verdict, **details) -> dict:
    return {"rule": rule, "dimension": dimension, "verdict": verdict, **details}


def evaluate(baseline: dict, candidate: dict, compare: dict | None = None, *, candidate_meta: dict | None = None,
             licence: dict | None = None, freeze: dict | None = None, config: dict | None = None) -> dict:
    config = config or {}
    for name, rep in (("baseline", baseline), ("candidate", candidate)):
        if rep.get("split") != "dev":
            raise EvidenceError(f"{name} report is on split {rep.get('split')!r}; candidates are compared on dev (§6.2)")
    if baseline["benchmark_config_sha256"] != candidate["benchmark_config_sha256"]:
        raise EvidenceError("baseline and candidate were scored with different benchmark configs")
    if compare is not None and (compare["a"]["engine"], compare["b"]["engine"]) != (baseline["engine"], candidate["engine"]):
        raise EvidenceError("compare file is not baseline (a) vs candidate (b)")

    rules = []
    slices = sorted(set(baseline["slices"]) | set(candidate["slices"]))
    required = config.get("required_slices") or sorted(baseline["slices"])

    # prerequisites (§7 checklist)
    rules.append(_rule("baseline is a frozen Phase 0 engine", "prerequisite",
                       PASS if baseline.get("baseline_engine") else FAIL, engine=baseline["engine"]))
    rules.append(_rule("final-test portion frozen and hashed", "prerequisite",
                       PASS if freeze and freeze.get("freeze_sha256") else UNAVAILABLE,
                       freeze_sha256=(freeze or {}).get("freeze_sha256"),
                       reason=None if freeze else "no freeze supplied (final freeze waits for collection, D-S3-6)"))

    # multilingual accuracy: WER + CER per slice, none hidden
    missing = [sl for sl in required if _val(_real_all(candidate, sl), "wer") is None or _val(_real_all(candidate, sl), "cer") is None]
    rules.append(_rule("WER + CER reported for every language slice", "multilingual accuracy",
                       PASS if not missing else FAIL, required_slices=required, missing=missing,
                       values={sl: {"baseline_wer": _val(_real_all(baseline, sl), "wer"), "candidate_wer": _val(_real_all(candidate, sl), "wer"),
                                    "baseline_cer": _val(_real_all(baseline, sl), "cer"), "candidate_cer": _val(_real_all(candidate, sl), "cer")}
                               for sl in slices}))

    # code-switch preservation: beat baseline on both CS slices
    for sl in config.get("cs_slices", []):
        b, c = _real_all(baseline, sl), _real_all(candidate, sl)
        bi, ci_ = _val(b, "code_switched_utterance_integrity"), _val(c, "code_switched_utterance_integrity")
        bl, cl = _val(b, "language_switch_error_rate"), _val(c, "language_switch_error_rate")
        if None in (bi, ci_, bl, cl):
            rules.append(_rule(f"beats baseline on code-switched slice {sl}", "code-switch preservation", UNAVAILABLE,
                               reason="slice or metric not available (Te-En / conversational Hinglish data blocked)"))
            continue
        ok = ci_ > bi and cl < bl
        rules.append(_rule(f"beats baseline on code-switched slice {sl}", "code-switch preservation", PASS if ok else FAIL,
                           integrity=[bi, ci_], language_switch_error=[bl, cl],
                           integrity_ci_excludes_zero=_excludes_zero(_cmp(compare, sl, "code_switched_utterance_integrity"), "higher"),
                           language_switch_ci_excludes_zero=_excludes_zero(_cmp(compare, sl, "language_switch_error_rate"), "lower")))
    if not config.get("cs_slices"):
        rules.append(_rule("beats baseline on both code-switched slices", "code-switch preservation", UNAVAILABLE,
                           reason="no code-switched slices configured (N-7) / available"))

    # safety-critical words: keyword recall per category not worse
    worse, compared = [], 0
    for sl in slices:
        bt = (_real_all(baseline, sl) or {}).get("keyword_recall_by_safety_tag", {})
        ct = (_real_all(candidate, sl) or {}).get("keyword_recall_by_safety_tag", {})
        for tag in sorted(set(bt) & set(ct)):
            if bt[tag]["recall"] is None or ct[tag]["recall"] is None:
                continue
            compared += 1
            if ct[tag]["recall"] < bt[tag]["recall"]:
                worse.append({"slice": sl, "category": tag, "baseline": bt[tag]["recall"], "candidate": ct[tag]["recall"]})
    rules.append(_rule("keyword recall not worse than baseline in any category", "safety-critical words",
                       UNAVAILABLE if not compared else (FAIL if worse else PASS), categories_compared=compared, worse=worse,
                       reason=None if compared else "no safety-critical items scored (collection, blocker 4)"))

    # negation: no increase in polarity flips
    flips, seen = [], False
    for sl in slices:
        b, c = _real_all(baseline, sl), _real_all(candidate, sl)
        if not b or not c:
            continue
        bn, cn = b["metrics"]["negation_polarity_flip_rate"]["num"], c["metrics"]["negation_polarity_flip_rate"]["num"]
        if b["metrics"]["negation_polarity_flip_rate"]["den"] or c["metrics"]["negation_polarity_flip_rate"]["den"]:
            seen = True
            if cn > bn:
                flips.append({"slice": sl, "baseline_flips": bn, "candidate_flips": cn})
    rules.append(_rule("no increase in negation polarity flips", "negation",
                       UNAVAILABLE if not seen else (FAIL if flips else PASS), increases=flips,
                       reason=None if seen else "no negation in the scored data"))

    # false danger words on harmless audio
    for metric in ("safety_keyword_false_insertions_per_hour", "hallucinated_words_per_hour_no_speech"):
        bad, seen = [], False
        for sl in slices:
            b, c = _val(_real_all(baseline, sl), metric), _val(_real_all(candidate, sl), metric)
            if b is None or c is None:
                continue
            seen = True
            if c > b:
                bad.append({"slice": sl, "baseline": b, "candidate": c,
                            "ci_excludes_zero": _excludes_zero(_cmp(compare, sl, metric), "higher")})
        rules.append(_rule(f"{metric} not worse than baseline", "false danger words",
                           UNAVAILABLE if not seen else (FAIL if bad else PASS), worse=bad,
                           reason=None if seen else "no harmless / no-speech audio scored"))

    # robustness: every real condition subset reported; pocket and overlap reported even if weak
    subsets = {sub for v in candidate["slices"].values() for sub, kinds in v.items() if "real" in kinds}
    need = {"pocket_bag", "overlapping_speakers"}
    rules.append(_rule("pocket and overlap reported (real)", "robustness",
                       PASS if need <= subsets else UNAVAILABLE, real_subsets=sorted(subsets), missing=sorted(need - subsets),
                       reason=None if need <= subsets else "real pocket/bag and overlap audio not collected (blocker 5)"))

    # latency / compute on production-class CPU
    meta = candidate_meta or {}
    rtf = [v["all"]["real"]["latency"]["rtf_aggregate"] for v in candidate["slices"].values() if v.get("all", {}).get("real")]
    rtf = [x for x in rtf if x is not None]
    limit = config.get("cpu_rtf_max")
    if not meta.get("hardware_class_verified") or meta.get("device") != "cpu":
        lat = _rule("fits production-class CPU", "latency / compute", UNAVAILABLE, rtf_aggregate_by_slice=rtf,
                    peak_rss_mb=meta.get("peak_rss_mb"), reason="not measured on verified production-class CPU (2A §8.7)")
    elif limit is None:
        lat = _rule("fits production-class CPU", "latency / compute", UNAVAILABLE, rtf_aggregate_by_slice=rtf,
                    reason="no RTF limit configured (M-6)")
    else:
        lat = _rule("fits production-class CPU", "latency / compute", PASS if rtf and max(rtf) <= limit else FAIL,
                    rtf_aggregate_by_slice=rtf, cpu_rtf_max=limit, peak_rss_mb=meta.get("peak_rss_mb"))
    rules.append(lat)

    # licensing: model + training-data licences commercially usable
    if not licence:
        rules.append(_rule("model and training-data licences commercially usable", "licensing", UNAVAILABLE,
                           reason="no licence record supplied for the candidate"))
    else:
        cu = licence.get("commercially_usable")
        rules.append(_rule("model and training-data licences commercially usable", "licensing",
                           UNAVAILABLE if cu is None else (PASS if cu is True else FAIL),
                           model_licence=licence.get("model_licence"), training_data=licence.get("training_data"),
                           evidence=licence.get("evidence"), note="as recorded in the supplied licence record; not verified here"))

    # representation quality: English words recoverable; romanisation round-trip
    worse_en, seen = [], False
    for sl in slices:
        b, c = _val(_real_all(baseline, sl), "english_word_preservation"), _val(_real_all(candidate, sl), "english_word_preservation")
        if b is None or c is None:
            continue
        seen = True
        if c < b:
            worse_en.append({"slice": sl, "baseline": b, "candidate": c})
    rules.append(_rule("English words recoverable (preservation not worse than baseline)", "representation quality",
                       UNAVAILABLE if not seen else (FAIL if worse_en else PASS), worse=worse_en))
    rules.append(_rule("romanisation round-trip keeps English words recoverable", "representation quality", UNAVAILABLE,
                       reason=candidate.get("romanised_metrics", "no romaniser (Q6)")))

    verdicts = {r["verdict"] for r in rules}
    failed = [r["rule"] for r in rules if r["verdict"] == FAIL]
    unavailable = [r["rule"] for r in rules if r["verdict"] == UNAVAILABLE]
    status = ("not eligible under §7 (FAIL present; a loss on keyword recall or code-switch integrity needs an explicit, "
              "recorded owner decision)" if FAIL in verdicts else
              "incomplete: some §7 evidence UNAVAILABLE" if UNAVAILABLE in verdicts else "all §7 rules PASS")
    return {
        "format": EVIDENCE_FORMAT,
        "baseline": {"engine": baseline["engine"], "model_version": baseline["model_version"]},
        "candidate": {"engine": candidate["engine"], "model_version": candidate["model_version"]},
        "split": "dev", "benchmark_config_sha256": candidate["benchmark_config_sha256"],
        "provisional_config": bool(candidate.get("provisional_config") or baseline.get("provisional_config")),
        "rules": rules, "failed": failed, "unavailable": unavailable, "eligibility_evidence": status,
        "decision": "NOT MADE: the ASR-representation decision is the owner's (Phase 2A §9); this record is evidence only",
    }


def main(argv: list[str]) -> int:
    def opt(n):
        return argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else None

    def load(n):
        return json.loads(Path(opt(n)).read_text(encoding="utf-8")) if opt(n) else None

    if not (opt("--baseline") and opt("--candidate") and opt("--out")):
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    out = Path(opt("--out"))
    if out.exists():
        print(f"{out} exists; refusing to overwrite", file=sys.stderr)
        return 2
    try:
        ev = evaluate(load("--baseline"), load("--candidate"), load("--compare"), candidate_meta=load("--candidate-meta"),
                      licence=load("--licence"), freeze=load("--freeze"), config=load("--evidence-config"))
    except (EvidenceError, KeyError, OSError, json.JSONDecodeError) as e:
        print(f"evidence error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out.write_text(json.dumps(ev, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out}: {ev['eligibility_evidence']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
