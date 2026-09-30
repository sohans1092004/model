"""Phase 2B (defined portion) tests: decision_evidence.py, transcript_repr.py, asr_errors.py.
Toy fixtures only (examples/toy_adapter.py, examples/toy_engines.py); generated audio in a temp dir.
Same check() style.

    python asr_bench/test_phase2b.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.asr_errors import AsrErrorsError, build, label, word_boundary_errors
from asr_bench.decision_evidence import FAIL, PASS, UNAVAILABLE, EvidenceError, evaluate
from asr_bench.examples.toy_adapter import LINES, ToyAdapter, ToyNoiseAdapter
from asr_bench.freeze import create_freeze
from asr_bench.ingest import ingest
from asr_bench.registry import SourceRegistry
from asr_bench.report import build_report, compare
from asr_bench.runner import decode_pcm16k, load_engine, run
from asr_bench.scoring import BenchmarkConfig
from asr_bench.splits import SplitConfig
from asr_bench.transcript_repr import ReprError, Token, TranscriptRepr, from_manifest_row, from_run_record

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


CFG = BenchmarkConfig.load(HERE / "examples" / "toy_benchmark_config.json")
# Test-only copy adding the Devanagari negator used by the toy fixture. The shipped config's Latin-only list
# is the open Q7 limitation; this copy only exercises the negation FAIL/PASS paths, it decides nothing.
_raw = json.loads((HERE / "examples" / "toy_benchmark_config.json").read_text(encoding="utf-8"))
CFG_NEG = BenchmarkConfig.from_dict({**_raw, "negators": {**_raw["negators"], "hi": _raw["negators"]["hi"] + ["नहीं"]}})

# --- transcript representation --------------------------------------------------------------------------
row = {"utt_id": "toy:1", "transcript_ref": "help me मुझे कोई attack", "source_dataset": "toy", "source_version": "0",
       "provenance": "read", "split": "dev", "transcript_romanised": None,
       "tokens": [{"text": w, "lang": l, "script": None, "start_s": None, "end_s": None}
                  for w, l in zip("help me मुझे कोई attack".split(), ["en", "en", "hi", "hi", "en"])]}
ref = from_manifest_row(row)
check("reference: complete utterance kept in mixed script", ref.text_mixed == "help me मुझे कोई attack" and ref.source == "reference")
check("reference: manifest language tags carried with their source; script measured",
      [(t.lang, t.lang_source, t.script) for t in ref.tokens][2] == ("hi", "manifest", "Deva"))
check("reference: only the mixed-script view exists (no romaniser, Q6)", list(ref.views()) == ["mixed_script"])
rom = from_manifest_row({**row, "transcript_romanised": "help me mujhe koi attack"})
check("a source-provided romanised copy is kept as a second, named view (no choice made)",
      set(rom.views()) == {"mixed_script", "romanised:manifest (source-provided)"})
hyp = from_run_record({"utt_id": "toy:1", "hyp": "help me mujhe koi attack", "engine": "e", "model_version": "v1",
                       "input_unit": "utterance", "split": "dev"}, CFG)
check("ASR output: engine, version, input unit recorded", (hyp.engine, hyp.model_version, hyp.input_unit) == ("e", "v1", "utterance"))
check("ASR output: token language from the provisional script method, labelled as such",
      hyp.tokens[2].lang == "en" and "provisional" in hyp.tokens[2].lang_source)
check("ASR output without a config: token languages stay None (not guessed)",
      all(t.lang is None for t in from_run_record({"utt_id": "x", "hyp": "a b", "engine": "e", "model_version": "v"}).tokens))
check("round trip to_dict / from_dict", TranscriptRepr.from_dict(json.loads(json.dumps(hyp.to_dict()))) == hyp)
check("tokens dropping a word are refused (complete utterance)",
      raises(lambda: TranscriptRepr("x", "asr_output", "a b c", (Token("a"), Token("c")), "e", "v", None), ReprError))
check("romanised text without a named romaniser is refused",
      raises(lambda: TranscriptRepr("x", "reference", "a", None, None, None, None, text_romanised="a"), ReprError))
check("ASR output without engine/version is refused", raises(lambda: TranscriptRepr("x", "asr_output", "a", None, None, None, None), ReprError))
check("a token language without its source is refused",
      raises(lambda: TranscriptRepr("x", "reference", "a", (Token("a", lang="hi"),), None, None, None), ReprError))
check("run record with an error has no representation", raises(lambda: from_run_record({"utt_id": "x", "error": "boom"}), ReprError))

# --- ASR error labelling ---------------------------------------------------------------------------------
check("word-boundary: merge 'call karo' -> 'callkaro'", word_boundary_errors(["call", "karo"], ["callkaro"]) == 1)
check("word-boundary: split 'policeko' -> 'police ko'", word_boundary_errors(["policeko"], ["police", "ko"]) == 1)
check("word-boundary: plain substitution is not a boundary error", word_boundary_errors(["call"], ["fall"]) == 0)
r_neg = {"utt_id": "toy:n", "speaker_id": "toy:s", "duration_s": 1.0, "transcript_ref": "mujhe help nahi chahiye", "language_primary": "hi",
         "languages_present": ["hi", "en"], "is_code_switched": False, "tokens": None, "keyword_spans": None, "safety_tags": None}
lab = label(r_neg, "mujhe help chahiye", CFG, [])
check("negation error labelled (negator dropped)", "negation" in lab["error_types"] and "deletion" in lab["error_types"])
check("name/entity error is UNAVAILABLE (no entity annotation), never guessed", lab["labels"]["name_entity"] is None)
check("decoding confidence not recorded by the runner -> null", lab["avg_logprob"] is None and lab["temperature"] is None)
r_ns = {**r_neg, "utt_id": "toy:ns", "transcript_ref": ""}
check("hallucination labelled on no-speech audio", "hallucination" in label(r_ns, "thanks for watching", CFG, [])["error_types"])
r_deva = {**r_neg, "utt_id": "toy:d", "transcript_ref": "मुझे बचाओ", "tokens": [{"text": "मुझे", "lang": "hi"}, {"text": "बचाओ", "lang": "hi"}]}
check("language switching labelled (Devanagari Hindi output as Latin)", "language_switching" in label(r_deva, "mujhe bachao", CFG, [])["error_types"])

# --- toy end to end ----------------------------------------------------------------------------------------
REG = SourceRegistry.from_dict({"format": "asr_bench.source_registry/1", "registry_version": 1, "sources": {
    sid: {"name": sid, "family": sid, "intended_use": "test", "acquisition_status": "toy", "licence": lic, "gate_status": "toy",
          "use_restriction": ur, "acquisition_authorised": True, "blockers": []}
    for sid, lic, ur in (("toy", "toy (test fixture)", "train_ok"), ("toynoise", "toy noise (test fixture)", "eval_only"))}})
SPLIT = SplitConfig.from_dict({"format": "asr_bench.split_config/1", "salt": "udk-phase2a-v1", "sources": {
    "toy": {"policy": "hash", "ratios": {"train": 0.4, "dev": 0.2, "test": 0.2, "final_test": 0.2}},
    "toynoise": {"policy": "fixed", "split": "eval_only"}}})
DEGRADE = {LINES[0][0]: "help me mujhe koi attack kar raha hai", LINES[1][0]: "मुझे help चाहिए",
           LINES[2][0]: "please call the", LINES[3][0]: "i will call the police later"}

tmp = Path(tempfile.mkdtemp(prefix="asr_bench_p2b_"))
try:
    roots = {"toy": tmp / "toy", "toynoise": tmp / "toynoise"}
    for d in roots.values():
        d.mkdir()
    for adapter, root, base in ((ToyAdapter(), roots["toy"], 0), (ToyNoiseAdapter(), roots["toynoise"], 1000)):
        for i, u in enumerate(adapter.utterances()):
            rng = random.Random(base + i)
            with wave.open(str(root / u.audio_path), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
                w.writeframes(b"".join(int(rng.gauss(0, 3000)).to_bytes(2, "little", signed=True) for _ in range(16000)))
    rows = ingest(ToyAdapter(), SPLIT, roots["toy"], REG)[0] + ingest(ToyNoiseAdapter(), SPLIT, roots["toynoise"], REG)[0]
    by_id = {r["utt_id"]: r for r in rows}
    emap = {"perfect": {}, "degraded": {}}
    for r in rows:
        h = hashlib.sha256(decode_pcm16k(roots[r["source_dataset"]] / r["audio_path"])).hexdigest()
        emap["perfect"][h] = r["transcript_ref"]
        emap["degraded"][h] = DEGRADE.get(r["transcript_ref"], "thanks for watching")
    (tmp / "map.json").write_text(json.dumps(emap, ensure_ascii=False), encoding="utf-8")
    os.environ["TOY_ENGINE_MAP"] = str(tmp / "map.json")
    engines = {"perfect": load_engine("asr_bench.examples.toy_engines:perfect"),
               "degraded": load_engine("asr_bench.examples.toy_engines:degraded")}
    recs = {}
    for name, eng in engines.items():
        for split in ("train", "dev", "final_test"):
            out = tmp / f"{name}_{split}.jsonl"
            run(rows, split, eng, f"toy_{name}", "utterance", {k: str(v) for k, v in roots.items()}, out, {"engine": name})
            recs[(name, split)] = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    # the toy "baseline" is the perfect fake engine; report.baseline_engine is only true for the frozen Phase 0 engines
    base_rep = build_report(by_id, recs[("perfect", "dev")], CFG_NEG)[0]
    cand_rep = build_report(by_id, recs[("degraded", "dev")], CFG_NEG)[0]
    cmp = compare(by_id, recs[("perfect", "dev")], recs[("degraded", "dev")], CFG_NEG)
    ev = evaluate(base_rep, cand_rep, cmp, config={"cs_slices": ["hi|cs", "te|cs"]})
    v = {r["rule"]: r["verdict"] for r in ev["rules"]}
    check("evidence: toy baseline is not a frozen Phase 0 engine -> prerequisite FAIL", v["baseline is a frozen Phase 0 engine"] == FAIL)
    check("evidence: code-switch rule FAILs for the degraded candidate on hi|cs", v["beats baseline on code-switched slice hi|cs"] == FAIL)
    check("evidence: Te-En slice has no data -> UNAVAILABLE, not PASS", v["beats baseline on code-switched slice te|cs"] == UNAVAILABLE)
    check("evidence: keyword recall worse in some category -> FAIL", v["keyword recall not worse than baseline in any category"] == FAIL)
    check("evidence: negation flip increase -> FAIL", v["no increase in negation polarity flips"] == FAIL)
    q7 = evaluate(build_report(by_id, recs[("perfect", "dev")], CFG)[0], build_report(by_id, recs[("degraded", "dev")], CFG)[0])
    check("evidence with the shipped Latin-only negator list: Devanagari negation is UNAVAILABLE, not PASS (Q7)",
          {r["rule"]: r["verdict"] for r in q7["rules"]}["no increase in negation polarity flips"] == UNAVAILABLE)
    check("evidence: false keyword insertion worse -> FAIL", v["safety_keyword_false_insertions_per_hour not worse than baseline"] == FAIL)
    check("evidence: pocket/overlap not collected -> UNAVAILABLE", v["pocket and overlap reported (real)"] == UNAVAILABLE)
    check("evidence: CPU fit unmeasured on verified hardware -> UNAVAILABLE", v["fits production-class CPU"] == UNAVAILABLE)
    check("evidence: no licence record -> UNAVAILABLE", v["model and training-data licences commercially usable"] == UNAVAILABLE)
    check("evidence: romanisation round-trip -> UNAVAILABLE (Q6)", v["romanisation round-trip keeps English words recoverable"] == UNAVAILABLE)
    check("evidence: no winner / decision made", ev["decision"].startswith("NOT MADE") and "not eligible" in ev["eligibility_evidence"])
    same = evaluate(base_rep, base_rep, compare(by_id, recs[("perfect", "dev")], recs[("perfect", "dev")], CFG_NEG),
                    licence={"model_licence": "toy", "training_data": "toy", "commercially_usable": True, "evidence": "fixture"},
                    freeze=create_freeze(rows, SPLIT), config={"cs_slices": ["hi|cs"]})
    sv = {r["rule"]: r["verdict"] for r in same["rules"]}
    check("evidence: identical candidate does not 'beat' the baseline (strict) -> FAIL", sv["beats baseline on code-switched slice hi|cs"] == FAIL)
    check("evidence: identical candidate is not worse on recall / flips / false words -> PASS",
          sv["keyword recall not worse than baseline in any category"] == PASS and sv["no increase in negation polarity flips"] == PASS)
    check("evidence: supplied licence record and freeze are used (PASS, marked unverified)",
          sv["model and training-data licences commercially usable"] == PASS and sv["final-test portion frozen and hashed"] == PASS)
    meta_ok = {"hardware_class_verified": True, "device": "cpu", "peak_rss_mb": 100}
    check("evidence: verified CPU but no RTF limit configured -> UNAVAILABLE (M-6)",
          {r["rule"]: r["verdict"] for r in evaluate(base_rep, cand_rep, cmp, candidate_meta=meta_ok)["rules"]}["fits production-class CPU"] == UNAVAILABLE)
    check("evidence: verified CPU + limit -> judged",
          {r["rule"]: r["verdict"] for r in evaluate(base_rep, cand_rep, cmp, candidate_meta=meta_ok, config={"cpu_rtf_max": 1.0})["rules"]}
          ["fits production-class CPU"] in (PASS, FAIL))
    ft = build_report(by_id, recs[("degraded", "final_test")], CFG_NEG)[0]
    check("evidence refuses final_test reports (candidates compared on dev)", raises(lambda: evaluate(base_rep, ft), EvidenceError))
    other = copy.deepcopy(cand_rep)
    other["benchmark_config_sha256"] = "x"
    check("evidence refuses reports scored with different configs", raises(lambda: evaluate(base_rep, other), EvidenceError))
    check("evidence refuses a compare file of other engines", raises(lambda: evaluate(base_rep, cand_rep, {**cmp, "a": {"engine": "z"}}), EvidenceError))

    runs = [recs[("perfect", s)] + [] for s in ("train", "dev", "final_test")]
    all_perfect = recs[("perfect", "train")] + recs[("perfect", "dev")] + recs[("perfect", "final_test")]
    all_degraded = recs[("degraded", "train")] + recs[("degraded", "dev")] + recs[("degraded", "final_test")]
    d_rows, summary = build(by_id, [all_perfect, all_degraded], CFG_NEG)
    check("D_asr_errors: final_test records never included", all(r["split"] != "final_test" for r in d_rows)
          and summary["excluded"]["final_test_records"] == len(recs[("perfect", "final_test")]) * 2)
    check("D_asr_errors: one row per utterance with both engines side by side",
          all(set(r["outputs"]) == {"toy_perfect", "toy_degraded"} for r in d_rows))
    check("D_asr_errors: usable_for_training only for train + train_ok rows",
          all(r["usable_for_training"] == (r["split"] == "train" and r["use_restriction"] == "train_ok") for r in d_rows)
          and summary["usable_for_training"] > 0)
    check("D_asr_errors: perfect engine has no error types", all(r["outputs"]["toy_perfect"]["error_types"] == [] for r in d_rows))
    types = {t for r in d_rows for t in r["outputs"]["toy_degraded"]["error_types"]}
    check("D_asr_errors: degraded engine errors labelled (deletion, negation, language switching)",
          {"deletion", "negation", "language_switching"} <= types, sorted(types))
    check("D_asr_errors: condition, licence and split carried from the manifest",
          all(r["licence"] and r["split"] and r["condition"]["condition_real_or_synthetic"] == "real" for r in d_rows))
    dup = [recs[("perfect", "dev")], recs[("perfect", "dev")]]
    check("D_asr_errors: the same engine twice is refused", raises(lambda: build(by_id, dup, CFG_NEG), AsrErrorsError))
    check("D_asr_errors: deterministic", build(by_id, [all_perfect, all_degraded], CFG_NEG) == (d_rows, summary))
    hyps = [from_run_record(r, CFG) for r in recs[("degraded", "dev")]]
    check("every dev ASR output converts to a valid representation", len(hyps) == len(recs[("degraded", "dev")]))

    mpath = tmp / "m.jsonl"
    mpath.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    for n in ("perfect", "degraded"):
        (tmp / f"{n}_all.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in
                                                    (all_perfect if n == "perfect" else all_degraded)), encoding="utf-8")
    (tmp / "base.json").write_text(json.dumps(base_rep), encoding="utf-8")
    (tmp / "cand.json").write_text(json.dumps(cand_rep), encoding="utf-8")
    (tmp / "cmp.json").write_text(json.dumps(cmp), encoding="utf-8")

    def cli(*a):
        return subprocess.run([sys.executable, "-m", *a], capture_output=True, text=True, cwd=HERE.parent, env=os.environ)

    r = cli("asr_bench.asr_errors", "build", "--manifest", str(mpath), "--run", str(tmp / "perfect_all.jsonl"), "--run",
            str(tmp / "degraded_all.jsonl"), "--config", str(HERE / "examples" / "toy_benchmark_config.json"), "--out", str(tmp / "d.jsonl"))
    check("CLI asr_errors build", r.returncode == 0 and (tmp / "d.jsonl").exists(), r.stdout + r.stderr)
    r = cli("asr_bench.decision_evidence", "--baseline", str(tmp / "base.json"), "--candidate", str(tmp / "cand.json"),
            "--compare", str(tmp / "cmp.json"), "--out", str(tmp / "ev.json"))
    check("CLI decision_evidence writes the record", r.returncode == 0 and json.loads((tmp / "ev.json").read_text())["decision"].startswith("NOT MADE"),
          r.stdout + r.stderr)
    r = cli("asr_bench.decision_evidence", "--baseline", str(tmp / "base.json"), "--candidate", str(tmp / "cand.json"), "--out", str(tmp / "ev.json"))
    check("CLI decision_evidence never overwrites", r.returncode == 2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
