"""Benchmark reports (Phase 2A §5–§6, §9; stage S6).

    python -m asr_bench.report score   --manifest m.jsonl --run run.jsonl --config bench.json --out report.json
                                       [--failures failures.jsonl] [--markdown report.md]
    python -m asr_bench.report compare --manifest m.jsonl --a baseline.jsonl --b candidate.jsonl --config bench.json
                                       --out compare.json

- Every metric per language slice x condition subset, real and synthetic separately, with item,
  speaker and hour counts and speaker-bootstrap 95% CIs. Nothing is pooled across languages (§6.5).
- dev/test: per-utterance failures listed (keywords missed, negation flips, broken code-switched
  utterances, language switches, hallucinations), incl. the safety-critical items (§9).
- final_test: totals per slice only, no per-utterance output (§6.2), and the output file is never
  overwritten, so it is produced once.
- compare: paired bootstrap differences (B - A) on the utterances both runs scored (§6.4).
- Latency: aggregate RTF (sum processing / sum audio) and per-utterance percentiles per slice.
Slice definition (N-7) and robustness-subset mapping (M-1) are provisional configuration.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.scoring import (METRICS, NORMALISER_VERSION, BenchmarkConfig, failures, false_insertion_keywords,
                               keyword_recall_by_tag, score_utterance)
from asr_bench.eligibility import select_eligible
from asr_bench.stats import bootstrap_ci, paired_difference
from asr_bench.validate import read_jsonl

FROZEN = ("phase0_whisper_small_en", "phase0_parakeet_tdt_0.6b_v2")


def slice_key(row: dict, cfg: BenchmarkConfig) -> str:
    parts = []
    for k in cfg.raw["slice_by"]:
        if k == "language_primary":
            parts.append(str(row.get("language_primary")))
        else:
            parts.append("cs" if row.get("is_code_switched") else "mono")
    return "|".join(parts)


def condition_subsets(row: dict) -> list[str]:
    """Phase 2A §4 robustness subsets from the row's own metadata (M-1, provisional)."""
    s = ["all"]
    env, dev = row.get("environment"), row.get("condition_device")
    tags = []
    if row.get("overlap"):
        tags.append("overlapping_speakers")
    if dev in ("pocket", "bag"):
        tags.append("pocket_bag")
    if dev == "far_field":
        tags.append("far_field")
    if dev == "phone_call":
        tags.append("phone_band")
    if env == "traffic":
        tags.append("traffic")
    if env == "crowd":
        tags.append("crowd_babble")
    if isinstance(row.get("snr_db"), (int, float)) and row["snr_db"] <= 0:
        tags.append("low_snr")
    if isinstance(row.get("clipping_ratio"), (int, float)) and row["clipping_ratio"] > 0:
        tags.append("clipping")
    if not tags and env == "quiet" and dev in ("close", "phone_hand"):
        tags.append("clean")
    return s + tags


def _pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))] if s else None


def _latency(recs: list[dict]) -> dict:
    ok = [r for r in recs if "proc_s" in r]
    audio = sum(r["audio_s"] for r in ok)
    return {"utterances": len(ok), "rtf_aggregate": (sum(r["proc_s"] for r in ok) / audio) if audio else None,
            "rtf_p50": _pct([r["rtf"] for r in ok], 0.5), "rtf_p90": _pct([r["rtf"] for r in ok], 0.9)}


def _load(manifest: Path, run: Path):
    parsed, issues = read_jsonl(manifest)
    if issues:
        raise ValueError(f"{manifest}: unparseable lines")
    rows = {r["utt_id"]: r for _, r in parsed}
    recs, rissues = read_jsonl(run)
    if rissues:
        raise ValueError(f"{run}: unparseable lines")
    return rows, [r for _, r in recs]


def score_run(rows: dict, recs: list[dict], cfg: BenchmarkConfig):
    splits = {r.get("split") for r in recs}
    engines = {(r.get("engine"), r.get("model_version")) for r in recs}
    if len(splits) > 1 or len(engines) > 1:
        raise ValueError(f"a run file must hold one split and one engine, got {splits} / {engines}")
    fi = false_insertion_keywords(list(rows.values()), cfg)
    scored, errors, unknown = [], 0, 0
    for rec in recs:
        row = rows.get(rec["utt_id"])
        if row is None:
            unknown += 1
            continue
        if "error" in rec:
            errors += 1
            continue
        scored.append((row, rec, score_utterance(row, rec["hyp"], cfg, fi)))
    return scored, errors, unknown, (splits.pop() if splits else None), (engines.pop() if engines else (None, None))


def _block(items, cfg: BenchmarkConfig) -> dict:
    res = [s for _, _, s in items]
    b = cfg.raw["bootstrap"]
    return {"items": len(res), "speakers": len({r["speaker_id"] for r in res if r["speaker_id"]}),
            "hours": round(sum(r["hours"] for r in res), 6),
            "metrics": {m: bootstrap_ci(res, m, b["resamples"], b["seed"]) for m in METRICS},
            "keyword_recall_by_safety_tag": keyword_recall_by_tag(res),
            "numbers_left_as_digits": sum(r["numbers_left_as_digits"] for r in res),
            "untagged_utterances": sum(1 for r in res if not r["tags_available"]),
            "latency": _latency([rec for _, rec, _ in items])}


def build_report(rows: dict, recs: list[dict], cfg: BenchmarkConfig) -> tuple[dict, list[dict]]:
    scored, errors, unknown, split, (engine, version) = score_run(rows, recs, cfg)
    final = split == "final_test"
    groups = defaultdict(list)
    for row, rec, s in scored:
        subs = ["all"] if final else condition_subsets(row)
        for sub in subs:
            groups[(slice_key(row, cfg), sub, row.get("condition_real_or_synthetic"))].append((row, rec, s))
    slices = {}
    for (sl, sub, kind), items in sorted(groups.items()):
        slices.setdefault(sl, {}).setdefault(sub, {})[kind] = _block(items, cfg)
    report = {
        "engine": engine, "model_version": version, "split": split, "baseline_engine": engine in FROZEN,
        "benchmark_config_sha256": cfg.sha256, "normaliser_version": NORMALISER_VERSION,
        "provisional_config": bool(cfg.raw["provisional"]), "open_decisions": cfg.raw["open_decisions"],
        "romanised_metrics": "unavailable (Q6: no romaniser)",
        "run_errors_excluded": errors, "records_not_in_manifest": unknown,
        "eligible_rows_without_record": (len({r["utt_id"] for r in select_eligible(list(rows.values()), split)[0]}
                                             - {rec["utt_id"] for rec in recs}) if split else None),
        "slices": slices,
        "final_test_totals_only": final,
    }
    fails = [] if final else [
        {"utt_id": r["utt_id"], "slice": slice_key(r, cfg), "safety_tags": s["safety_tags"], "failures": f,
         "ref": r.get("transcript_ref"), "hyp": rec["hyp"]}
        for r, rec, s in scored if (f := failures(s))]
    return report, fails


def compare(rows: dict, recs_a: list[dict], recs_b: list[dict], cfg: BenchmarkConfig) -> dict:
    sa, _, _, split_a, eng_a = score_run(rows, recs_a, cfg)
    sb, _, _, split_b, eng_b = score_run(rows, recs_b, cfg)
    if split_a != split_b:
        raise ValueError(f"runs are on different splits ({split_a} vs {split_b})")
    if split_a == "final_test":
        raise ValueError("candidates are compared on dev (§6.2), not on final_test")
    by_a, by_b = defaultdict(list), defaultdict(list)
    for row, _, s in sa:
        by_a[(slice_key(row, cfg), row.get("condition_real_or_synthetic"))].append(s)
    for row, _, s in sb:
        by_b[(slice_key(row, cfg), row.get("condition_real_or_synthetic"))].append(s)
    b = cfg.raw["bootstrap"]
    out = {}
    for key in sorted(set(by_a) | set(by_b)):
        out.setdefault(key[0], {})[key[1]] = {m: paired_difference(by_a.get(key, []), by_b.get(key, []), m, b["resamples"], b["seed"])
                                              for m in METRICS}
    return {"a": {"engine": eng_a[0], "model_version": eng_a[1], "baseline_engine": eng_a[0] in FROZEN},
            "b": {"engine": eng_b[0], "model_version": eng_b[1]}, "split": split_a, "difference": "b - a",
            "benchmark_config_sha256": cfg.sha256, "provisional_config": bool(cfg.raw["provisional"]), "slices": out}


def to_markdown(rep: dict) -> str:
    lines = [f"# ASR benchmark: {rep['engine']} ({rep['model_version']}), split {rep['split']}", "",
             f"Config {rep['benchmark_config_sha256'][:12]}, normaliser {rep['normaliser_version']}"
             + (" -- PROVISIONAL configuration" if rep["provisional_config"] else ""), ""]
    show = ("wer", "cer", "language_switch_error_rate", "english_word_preservation", "negation_preservation",
            "negation_polarity_flip_rate", "safety_keyword_recall", "code_switched_utterance_integrity")
    for sl, subs in rep["slices"].items():
        lines += [f"## Slice {sl}", "", "| subset | kind | items | speakers | " + " | ".join(show) + " | RTF |",
                  "|" + "---|" * (len(show) + 5)]
        for sub, kinds in subs.items():
            for kind, blk in kinds.items():
                cells = []
                for m in show:
                    v = blk["metrics"][m]
                    cells.append("n/a" if v["value"] is None else f"{v['value']:.3f}" + (
                        f" [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]" if v["ci95"] else ""))
                rtf = blk["latency"]["rtf_aggregate"]
                lines.append(f"| {sub} | {kind} | {blk['items']} | {blk['speakers']} | " + " | ".join(cells)
                             + f" | {'n/a' if rtf is None else f'{rtf:.3f}'} |")
        lines.append("")
    return "\n".join(lines)


def _write_new(path: str, text: str) -> None:
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"{p} exists; refusing to overwrite")
    p.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    def opt(n):
        return argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else None

    if not argv or argv[0] not in ("score", "compare") or not (opt("--manifest") and opt("--config") and opt("--out")):
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    try:
        cfg = BenchmarkConfig.load(opt("--config"))
        if argv[0] == "score":
            rows, recs = _load(Path(opt("--manifest")), Path(opt("--run")))
            rep, fails = build_report(rows, recs, cfg)
            _write_new(opt("--out"), json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
            if opt("--failures") and not rep["final_test_totals_only"]:
                _write_new(opt("--failures"), "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in fails))
            if opt("--markdown"):
                _write_new(opt("--markdown"), to_markdown(rep))
        else:
            rows, ra = _load(Path(opt("--manifest")), Path(opt("--a")))
            _, rb = _load(Path(opt("--manifest")), Path(opt("--b")))
            _write_new(opt("--out"), json.dumps(compare(rows, ra, rb, cfg), indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    except (ValueError, OSError) as e:
        print(f"report error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {opt('--out')}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
