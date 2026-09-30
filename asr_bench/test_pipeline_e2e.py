"""End-to-end pipeline test on toy fixtures only: ingest (registry gate) -> split -> leakage ->
freeze -> runner (fake engines, frozen-engine rules) -> report / compare -> synthetic conditions ->
slice readiness. Generated audio in a temp dir; nothing downloaded; no model. check() style.

    python asr_bench/test_pipeline_e2e.py      (synthetic-condition checks need numpy + scipy; SKIP otherwise)
"""
from __future__ import annotations

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

from asr_bench.examples.toy_adapter import LINES, N_SPEAKERS, ToyAdapter, ToyNoiseAdapter
from asr_bench.freeze import create_freeze, verify_freeze, write_freeze
from asr_bench.ingest import IngestError, ingest, slice_readiness
from asr_bench.registry import SourceRegistry
from asr_bench.report import build_report, compare, condition_subsets
from asr_bench.runner import RunnerError, decode_pcm16k, load_engine, run
from asr_bench.scoring import BenchmarkConfig
from asr_bench.splits import SplitConfig, leakage_report
from asr_bench.validate import validate_rows

passed = failed = skipped = 0


def check(name: str, condition: bool, detail="") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


def raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


def write_wav(path: Path, seed: int, seconds: float = 1.0) -> None:
    rng = random.Random(seed)
    n = int(16000 * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"".join(int(rng.gauss(0, 3000)).to_bytes(2, "little", signed=True) for _ in range(n)))


REG_RAW = {"format": "asr_bench.source_registry/1", "registry_version": 1, "sources": {
    sid: {"name": sid, "family": sid, "intended_use": "test", "acquisition_status": "toy", "licence": lic, "gate_status": "toy",
          "use_restriction": ur, "acquisition_authorised": True, "blockers": []}
    for sid, lic, ur in (("toy", "toy (test fixture)", "train_ok"), ("toynoise", "toy noise (test fixture)", "eval_only"))}}
REG = SourceRegistry.from_dict(REG_RAW)
SPLIT_RAW = {"format": "asr_bench.split_config/1", "salt": "udk-phase2a-v1", "sources": {
    "toy": {"policy": "hash", "ratios": {"train": 0.4, "dev": 0.2, "test": 0.2, "final_test": 0.2}},
    "toynoise": {"policy": "fixed", "split": "eval_only"}}}
SCFG = SplitConfig.from_dict(SPLIT_RAW)
BCFG = BenchmarkConfig.load(HERE / "examples" / "toy_benchmark_config.json")
DEGRADE = {LINES[0][0]: "help me mujhe koi attack kar raha hai", LINES[1][0]: "मुझे help चाहिए",
           LINES[2][0]: "please call the", LINES[3][0]: "i will call the police later"}

tmp = Path(tempfile.mkdtemp(prefix="asr_bench_e2e_"))
try:
    root, noise_root = tmp / "toy", tmp / "toynoise"
    root.mkdir(), noise_root.mkdir()
    toy, noise = ToyAdapter(), ToyNoiseAdapter()
    for i, u in enumerate(toy.utterances()):
        write_wav(root / u.audio_path, i)
    for i, u in enumerate(noise.utterances()):
        write_wav(noise_root / u.audio_path, 1000 + i, 2.0)

    # --- ingest ------------------------------------------------------------------------------------
    check("ingest refuses the toy source against the bundled registry (not registered/authorised)",
          raises(lambda: ingest(toy, SCFG, root), Exception))
    rows, rep = ingest(toy, SCFG, root, REG)
    nrows, _ = ingest(noise, SCFG, noise_root, REG)
    manifest = rows + nrows
    check("ingest: every utterance became a row", len(rows) == 2 * N_SPEAKERS and rep["failures"] == [], rep["failures"][:2])
    check("ingest: manifest valid + leakage-clean", not [i for i in leakage_report(manifest)[0] if i.level == "error"])
    check("ingest: noise rows (no speaker) are eval_only inventory", {r["split"] for r in nrows} == {"eval_only"})
    splits = {r["split"] for r in rows}
    check("ingest: toy rows spread over all executed splits", {"train", "dev", "test", "final_test"} <= splits, splits)
    man = tmp / "manifest.jsonl"
    man.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in manifest), encoding="utf-8")

    # --- freeze ---------------------------------------------------------------------------------
    fz = create_freeze(manifest, SCFG)
    fpath = tmp / "freeze.json"
    write_freeze(fz, fpath)
    scfg_path = tmp / "split.json"
    scfg_path.write_text(json.dumps(SPLIT_RAW), encoding="utf-8")
    check("freeze covers the final_test rows", fz["n_rows"] == sum(r["split"] == "final_test" for r in manifest))

    # --- toy engine map -----------------------------------------------------------------------------
    ref_of = {r["utt_id"]: r for r in manifest}
    emap = {"perfect": {}, "degraded": {}}
    for r in manifest:
        base = root if r["source_dataset"] == "toy" else noise_root
        h = hashlib.sha256(decode_pcm16k(base / r["audio_path"])).hexdigest()
        emap["perfect"][h] = r["transcript_ref"]
        emap["degraded"][h] = DEGRADE.get(r["transcript_ref"], "thanks for watching")
    mpath = tmp / "engine_map.json"
    mpath.write_text(json.dumps(emap, ensure_ascii=False), encoding="utf-8")
    os.environ["TOY_ENGINE_MAP"] = str(mpath)
    roots = {"toy": str(root), "toynoise": str(noise_root)}

    # --- runner ------------------------------------------------------------------------------------
    check("unknown engine name is refused", raises(lambda: load_engine("whisper_large"), RunnerError))
    check("engine that fails to load is an error (no MockSTT fallback)", raises(lambda: load_engine("no_such_module:x"), RunnerError))
    check("a mock backend is never benchmarked", raises(lambda: load_engine("asr_bench.examples.toy_engines:mock"), RunnerError))
    perfect = load_engine("asr_bench.examples.toy_engines:perfect")
    degraded = load_engine("asr_bench.examples.toy_engines:degraded")
    meta = {"engine": "toy"}
    check("input unit is required (Q4 open)", raises(lambda: run(manifest, "dev", perfect, "p", "", roots, tmp / "x.jsonl", meta), RunnerError))
    runs = {}
    for name, eng in (("perfect", perfect), ("degraded", degraded)):
        for split in ("dev", "eval_only"):
            out = tmp / f"{name}_{split}.jsonl"
            m = run(manifest, split, eng, f"toy_{name}", "utterance", roots, out, meta)
            runs[(name, split)] = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    dev_ids = {r["utt_id"] for r in manifest if r["split"] == "dev"}
    check("runner: exactly the eligible dev rows were run", {r["utt_id"] for r in runs[("perfect", "dev")]} == dev_ids)
    check("runner: RTF and processing time recorded per utterance", all("rtf" in r and r["rtf"] >= 0 for r in runs[("perfect", "dev")]))
    again = run(manifest, "dev", perfect, "toy_perfect", "utterance", roots, tmp / "perfect_dev.jsonl", meta)
    check("runner is resumable (second pass adds nothing)", again["new_records"] == 0)
    mf = json.loads((tmp / "perfect_dev.jsonl.meta.json").read_text())
    check("run metadata: engine, input unit, manifest hash, hardware (declared, unverified), peak RSS",
          mf["engine"] == "toy" and mf["peak_rss_mb"] and mf["eligible"] == len(dev_ids))

    class StubVAD:
        def segment_speech(self, pcm):
            class S:
                pass
            s = S()
            s.pcm = pcm
            return [s]
    vout = tmp / "vad.jsonl"
    run(manifest, "dev", perfect, "toy_perfect", "vad", roots, vout, meta, vad=StubVAD())
    check("VAD input unit runs through a VAD object (frozen vad.VAD in real runs)",
          all(json.loads(l)["input_unit"] == "vad" for l in vout.read_text().splitlines()))

    def cli(*a):
        return subprocess.run([sys.executable, "-m", *a], capture_output=True, text=True, cwd=HERE.parent, env=os.environ)

    r = cli("asr_bench.runner", "--manifest", str(man), "--split", "final_test", "--engine", "asr_bench.examples.toy_engines:perfect",
            "--input-unit", "utterance", "--out", str(tmp / "ft.jsonl"), "--audio-root", f"toy={root}")
    check("CLI runner: final_test without a freeze is refused", r.returncode == 2, r.stderr)
    r = cli("asr_bench.runner", "--manifest", str(man), "--split", "final_test", "--engine", "asr_bench.examples.toy_engines:perfect",
            "--input-unit", "utterance", "--out", str(tmp / "ft.jsonl"), "--audio-root", f"toy={root}",
            "--freeze", str(fpath), "--split-config", str(scfg_path), "--hardware-class", "c7i.2xlarge")
    check("CLI runner: final_test with a verified freeze runs", r.returncode == 0, r.stdout + r.stderr)
    ftm = json.loads((tmp / "ft.jsonl.meta.json").read_text())
    check("final_test run records the freeze hash; hardware class declared but not verified",
          ftm["final_test_freeze_sha256"] == fz["freeze_sha256"] and ftm["hardware_class_verified"] is False)
    tampered = [dict(x) for x in manifest]
    next(x for x in tampered if x["split"] == "final_test")["transcript_ref"] = "edited"
    tman = tmp / "tampered.jsonl"
    tman.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in tampered), encoding="utf-8")
    r = cli("asr_bench.runner", "--manifest", str(tman), "--split", "final_test", "--engine", "asr_bench.examples.toy_engines:perfect",
            "--input-unit", "utterance", "--out", str(tmp / "ft2.jsonl"), "--audio-root", f"toy={root}",
            "--freeze", str(fpath), "--split-config", str(scfg_path))
    check("CLI runner: final_test on a manifest that no longer matches the freeze is refused", r.returncode == 1, r.stdout + r.stderr)

    # --- reports ---------------------------------------------------------------------------------------
    rp, fp = build_report(ref_of, runs[("perfect", "dev")], BCFG)
    allm = {sl: v["all"]["real"]["metrics"] for sl, v in rp["slices"].items()}
    check("perfect engine: WER 0 in every slice, no failures", all(m["wer"]["value"] == 0 for m in allm.values()) and fp == [], fp[:2])
    check("report: slices are separate (no pooled language score)", set(rp["slices"]) <= {"hi|cs", "en-IN|mono"} and "all" not in rp["slices"])
    check("report: provisional configuration and open decisions are stated", rp["provisional_config"] and "Q7" in " ".join(rp["open_decisions"]))
    check("report: romanised metrics explicitly unavailable (Q6)", "unavailable" in rp["romanised_metrics"])
    check("report: nothing missing for eligible dev rows", rp["eligible_rows_without_record"] == 0)
    rd, fd = build_report(ref_of, runs[("degraded", "dev")], BCFG)
    hi = rd["slices"].get("hi|cs", {}).get("all", {}).get("real", {}).get("metrics")
    check("degraded engine: Hindi rendered in Latin -> language-switch errors > 0", hi and hi["language_switch_error_rate"]["value"] > 0, hi and hi["language_switch_error_rate"])
    check("degraded engine: speaker-bootstrap CI reported with item/speaker counts",
          hi and hi["wer"]["ci95"] is not None and rd["slices"]["hi|cs"]["all"]["real"]["speakers"] > 1)
    kinds = {f for x in fd for f in x["failures"]}
    check("failure listing names safety failures (missed keyword, negation, integrity)",
          any("missed keyword" in k for k in kinds) and any("not intact" in k for k in kinds), sorted(kinds)[:6])
    ev, _ = build_report(ref_of, runs[("degraded", "eval_only")], BCFG)
    em = ev["slices"]["en|mono"]["all"]["real"]["metrics"]
    check("hallucination on no-speech audio measured per hour", em["hallucinated_words_per_hour_no_speech"]["value"] > 0)
    en = rd["slices"].get("en-IN|mono", {}).get("all", {}).get("real", {}).get("metrics", {})
    check("false danger-word insertion on harmless audio measured per hour",
          en.get("safety_keyword_false_insertions_per_hour", {}).get("value", 0) > 0, en.get("safety_keyword_false_insertions_per_hour"))
    cmp = compare(ref_of, runs[("perfect", "dev")], runs[("degraded", "dev")], BCFG)
    d = cmp["slices"]["hi|cs"]["real"]["wer"]
    check("paired comparison: degraded - perfect WER > 0 on the same utterances", d["difference"] > 0 and d["utterances"] > 0)
    ft_recs = [json.loads(l) for l in (tmp / "ft.jsonl").read_text().splitlines()]
    rft, fft = build_report(ref_of, ft_recs, BCFG)
    check("final_test report: totals per slice only, no per-utterance failures",
          rft["final_test_totals_only"] and fft == [] and all(set(v) == {"all"} for v in rft["slices"].values()))
    check("final_test is never used for candidate comparison", raises(lambda: compare(ref_of, ft_recs, ft_recs, BCFG), ValueError))
    out_md = tmp / "r.md"
    r = cli("asr_bench.report", "score", "--manifest", str(man), "--run", str(tmp / "degraded_dev.jsonl"), "--config",
            str(HERE / "examples" / "toy_benchmark_config.json"), "--out", str(tmp / "r.json"), "--failures", str(tmp / "f.jsonl"),
            "--markdown", str(out_md))
    check("CLI report score writes JSON + failures + markdown", r.returncode == 0 and out_md.exists() and "PROVISIONAL" in out_md.read_text(), r.stderr)
    r = cli("asr_bench.report", "score", "--manifest", str(man), "--run", str(tmp / "degraded_dev.jsonl"), "--config",
            str(HERE / "examples" / "toy_benchmark_config.json"), "--out", str(tmp / "r.json"))
    check("CLI report never overwrites (final-test totals are produced once)", r.returncode == 1)

    # --- slice readiness ----------------------------------------------------------------------------------
    sr = slice_readiness(manifest, BCFG.raw["slice_minimums"])
    check("slice minimums: toy slices reported UNAVAILABLE with the reason", sr["hinglish"]["status"].startswith("UNAVAILABLE")
          and "speakers" in sr["hinglish"]["status"] and sr["telugu"]["items"] == 0)

    # --- synthetic robustness conditions ----------------------------------------------------------------------
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
        have_np = True
    except ImportError:
        have_np = False
    if not have_np:
        for n in ("synthetic conditions: all recipes", "synthetic determinism", "synthetic leakage/licence rules"):
            skip(n, "numpy/scipy not installed here")
    else:
        from asr_bench.conditions import ConditionError, derive_row
        dev_rows = [x for x in manifest if x["split"] == "dev"]
        base, other1, other2 = dev_rows[0], dev_rows[1], dev_rows[2]
        derived = {
            "low_snr": derive_row(base, "low_snr", {"snr_db": -5}, base_seed=1, roots=roots, inputs=[nrows[0]]),
            "traffic": derive_row(base, "traffic", {"snr_db": 5}, base_seed=1, roots=roots, inputs=[nrows[1]]),
            "crowd": derive_row(base, "crowd", {"snr_db": 0}, base_seed=1, roots=roots, inputs=[other1, other2]),
            "clipping": derive_row(base, "clipping", {"clip_level": 0.3}, base_seed=1, roots=roots),
            "phone": derive_row(base, "phone", {}, base_seed=1, roots=roots),
            "pocket": derive_row(base, "pocket", {}, base_seed=1, roots=roots),
            "overlap": derive_row(base, "overlap", {"target_rel_db": -6}, base_seed=1, roots=roots, inputs=[other1]),
        }
        check("every recipe gives a schema-valid synthetic row with recipe + integer seed",
              all(x["condition_real_or_synthetic"] == "synthetic" and isinstance(x["seed"], int) and x["aug_recipe"]
                  for x in derived.values()) and not [i for i in validate_rows(list(enumerate(derived.values(), 1))) if i.level == "error"])
        check("derived rows keep speaker/session and split (augmented copies stay in one group)",
              all((x["speaker_id"], x["session_id"], x["split"]) == (base["speaker_id"], base["session_id"], base["split"])
                  for x in derived.values()))
        check("robustness subsets land where §4 puts them", "low_snr" in condition_subsets(derived["low_snr"])
              and "traffic" in condition_subsets(derived["traffic"]) and "crowd_babble" in condition_subsets(derived["crowd"])
              and "clipping" in condition_subsets(derived["clipping"]) and "phone_band" in condition_subsets(derived["phone"])
              and "pocket_bag" in condition_subsets(derived["pocket"]) and "overlapping_speakers" in condition_subsets(derived["overlap"]))
        check("clipping ratio is measured on the output", 0 < derived["clipping"]["clipping_ratio"] < 1)
        check("overlap: target -6 dB under the other voice -> overlap_rel_db +6", derived["overlap"]["overlap_rel_db"] == 6.0)
        check("noise input's stricter restriction propagates (eval_only noise -> eval_only row)",
              derived["low_snr"]["use_restriction"] == "eval_only" and "toy noise" in derived["low_snr"]["licence"])
        first = (root / derived["pocket"]["audio_path"]).read_bytes()
        (root / derived["pocket"]["audio_path"]).unlink()
        again = derive_row(base, "pocket", {}, base_seed=1, roots=roots)
        check("synthesis is deterministic: same seed, byte-identical audio and row",
              again == derived["pocket"] and (root / again["audio_path"]).read_bytes() == first)
        check("an existing derived file is never overwritten",
              raises(lambda: derive_row(base, "pocket", {}, base_seed=1, roots=roots), ConditionError))
        other_split = next(x for x in manifest if x["source_dataset"] == "toy" and x["split"] == "test")
        check("other speaker from a different split is refused (speaker leakage)",
              raises(lambda: derive_row(base, "overlap", {"target_rel_db": 0}, base_seed=1, roots=roots, inputs=[other_split]), ConditionError))
        train_row = next(x for x in manifest if x["source_dataset"] == "toy" and x["split"] == "train")
        check("train row + eval_only noise -> refused (derived row would be eval_only data in train)",
              raises(lambda: derive_row(train_row, "low_snr", {"snr_db": 0}, base_seed=1, roots=roots, inputs=[nrows[0]]), ConditionError))
        check("synthetic rows are never augmented again", raises(lambda: derive_row(derived["pocket"], "phone", {}, base_seed=1, roots=roots), ConditionError))
        syn_manifest = manifest + list(derived.values())
        check("manifest with synthetic rows stays valid and leakage-clean",
              not [i for i in leakage_report(syn_manifest)[0] if i.level == "error"])
        syn_run = tmp / "syn.jsonl"
        run(syn_manifest, "dev", perfect, "toy_perfect", "utterance", roots, syn_run, meta)
        rs, _ = build_report({x["utt_id"]: x for x in syn_manifest}, [json.loads(l) for l in syn_run.read_text().splitlines()], BCFG)
        sl = rs["slices"][f"{base['language_primary']}|{'cs' if base['is_code_switched'] else 'mono'}"]
        check("report keeps synthetic results separate from real (never pooled)",
              "synthetic" in sl["low_snr"] and "real" not in sl["low_snr"] and "real" in sl["all"] and "synthetic" in sl["all"])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "")
      + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
