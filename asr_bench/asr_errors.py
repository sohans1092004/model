"""D_asr_errors (Phase 1 §17): real audio + reference + the actual output of the frozen engines,
with the error types labelled, for later text-model training/testing on REAL STT mistakes.

    python -m asr_bench.asr_errors build --manifest m.jsonl --run whisper_dev.jsonl [--run parakeet_dev.jsonl ...]
                                         --config bench.json --out d_asr_errors.jsonl

One row per utterance, with every supplied engine's output side by side. Error types (§17):
substitution, deletion, insertion, hallucination (text with no speech; insertion runs >= 3 words),
language_switching (Indic reference words rendered in another language), word_boundary (two words
merged into one or one split into two), negation (a negator dropped or added), name_entity.
name_entity is UNAVAILABLE: the manifest has no entity annotation, so it is never guessed.

Guardrails (§17): final_test rows and final_test run records are never used -- their outputs exist
only inside the test set. Each row keeps its source split and licence; `usable_for_training` is true
only for split=train with use_restriction=train_ok. Decoding confidence (avg_logprob, temperature)
is null: the runner does not record it. Reuses textnorm / align / scoring, nothing re-implemented.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.align import align
from asr_bench.scoring import BenchmarkConfig, false_insertion_keywords, score_utterance
from asr_bench.textnorm import NORMALISER_VERSION, normalise
from asr_bench.validate import read_jsonl

ERRORS_FORMAT = "asr_bench.asr_errors/1"
ERROR_TYPES = ("substitution", "deletion", "insertion", "hallucination", "language_switching", "word_boundary",
               "negation", "name_entity")


class AsrErrorsError(ValueError):
    pass


def word_boundary_errors(ref: list[str], hyp: list[str]) -> int:
    """Merges (ref a b -> hyp ab) and splits (ref ab -> hyp a b) visible in the alignment."""
    ops = align(ref, hyp)
    n = 0
    for (o1, r1, h1), (o2, r2, h2) in zip(ops, ops[1:]):
        pair = {o1, o2}
        if pair == {"S", "D"}:
            rs = [r for r in (r1, r2) if r is not None]
            h = h1 if h1 is not None else h2
            if len(rs) == 2 and "".join(ref[i] for i in sorted(rs)) == hyp[h]:
                n += 1
        elif pair == {"S", "I"}:
            hs = [x for x in (h1, h2) if x is not None]
            r = r1 if r1 is not None else r2
            if len(hs) == 2 and "".join(hyp[j] for j in sorted(hs)) == ref[r]:
                n += 1
    return n


def label(row: dict, hyp_text: str, cfg: BenchmarkConfig, fi) -> dict:
    s = score_utterance(row, hyp_text, cfg, fi)
    lang = row.get("language_primary")
    ref, hyp = normalise(row.get("transcript_ref", ""), lang)[0], normalise(hyp_text, lang)[0]
    types = {
        "substitution": s["S"] > 0, "deletion": s["D"] > 0, "insertion": s["I"] > 0,
        "hallucination": (s["no_speech"] and s["hyp_words"] > 0) or s["insertion_runs_ge3"] > 0,
        "language_switching": s["lang_switch_changed"] > 0,
        "word_boundary": word_boundary_errors(ref, hyp) > 0,
        "negation": bool(s["neg_flip"]) or s["neg_kept"] < s["neg_ref"],
        "name_entity": None,  # unavailable: no entity annotation in the manifest
    }
    return {"text": hyp_text, "error_types": sorted(k for k, v in types.items() if v), "labels": types,
            "counts": {"S": s["S"], "D": s["D"], "I": s["I"], "ref_words": s["ref_words"],
                       "lang_switch_changed": s["lang_switch_changed"], "lang_switch_undetermined": s["lang_switch_undetermined"]},
            "avg_logprob": None, "temperature": None}


def build(rows: dict, runs: list[list[dict]], cfg: BenchmarkConfig) -> tuple[list[dict], dict]:
    fi = false_insertion_keywords(list(rows.values()), cfg)
    by_utt: dict[str, dict] = {}
    excluded = {"final_test_records": 0, "final_test_rows": 0, "run_errors": 0, "not_in_manifest": 0}
    engines = []
    for recs in runs:
        eng = {(r.get("engine"), r.get("model_version")) for r in recs}
        if len(eng) != 1:
            raise AsrErrorsError(f"each run file must hold exactly one engine, got {eng}")
        (engine, version), = eng
        engines.append({"engine": engine, "model_version": version})
        for rec in recs:
            if rec.get("split") == "final_test":
                excluded["final_test_records"] += 1
                continue
            row = rows.get(rec["utt_id"])
            if row is None:
                excluded["not_in_manifest"] += 1
                continue
            if row.get("split") == "final_test":
                excluded["final_test_rows"] += 1
                continue
            if "error" in rec:
                excluded["run_errors"] += 1
                continue
            out = by_utt.setdefault(rec["utt_id"], {
                "format": ERRORS_FORMAT, "utt_id": row["utt_id"], "source_dataset": row["source_dataset"],
                "licence": row["licence"], "use_restriction": row["use_restriction"], "split": row["split"],
                "speaker_id": row.get("speaker_id"),
                "usable_for_training": row["split"] == "train" and row["use_restriction"] == "train_ok",
                "reference": row.get("transcript_ref"), "language_primary": row.get("language_primary"),
                "languages_present": row.get("languages_present"), "is_code_switched": row.get("is_code_switched"),
                "token_languages": [t.get("lang") for t in row["tokens"]] if row.get("tokens") else None,
                "condition": {k: row.get(k) for k in ("condition_real_or_synthetic", "environment", "condition_device",
                                                      "snr_db", "overlap", "aug_recipe")},
                "normaliser_version": NORMALISER_VERSION, "benchmark_config_sha256": cfg.sha256,
                "outputs": {}})
            if engine in out["outputs"]:
                raise AsrErrorsError(f"{rec['utt_id']}: engine {engine!r} appears twice")
            out["outputs"][engine] = {"model_version": version, **label(row, rec["hyp"], cfg, fi)}
    result = [by_utt[u] for u in sorted(by_utt)]
    summary = {"rows": len(result), "engines": engines, "excluded": excluded,
               "usable_for_training": sum(r["usable_for_training"] for r in result),
               "error_type_counts": {e: {k["engine"]: sum(1 for r in result if e in r["outputs"].get(k["engine"], {}).get("error_types", []))
                                         for k in engines} for e in ERROR_TYPES if e != "name_entity"},
               "name_entity": "unavailable (no entity annotation)"}
    return result, summary


def main(argv: list[str]) -> int:
    def opt(n):
        return argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else None

    run_paths = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--run"]
    if argv[:1] != ["build"] or not (opt("--manifest") and run_paths and opt("--config") and opt("--out")):
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    out = Path(opt("--out"))
    if out.exists():
        print(f"{out} exists; refusing to overwrite", file=sys.stderr)
        return 2
    try:
        parsed, bad = read_jsonl(Path(opt("--manifest")))
        if bad:
            raise AsrErrorsError("manifest has unparseable lines")
        runs = []
        for p in run_paths:
            recs, rbad = read_jsonl(Path(p))
            if rbad:
                raise AsrErrorsError(f"{p}: unparseable lines")
            runs.append([r for _, r in recs])
        rows, summary = build({r["utt_id"]: r for _, r in parsed}, runs, BenchmarkConfig.load(opt("--config")))
    except (AsrErrorsError, OSError, ValueError) as e:
        print(f"asr_errors error: {e}", file=sys.stderr)
        return 1
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
