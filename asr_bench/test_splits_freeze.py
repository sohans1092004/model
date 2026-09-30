"""S3 tests: split assignment + leakage report (splits.py) and the final-test freeze (freeze.py).
Toy rows and run-time-generated WAVs only; every artifact goes to a temp dir. Same check() style.

    python asr_bench/test_splits_freeze.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.adapters import DatasetAdapter, SourceInfo, SourceUtterance
from asr_bench.adapters import build_rows as _build_rows
from asr_bench.eligibility import select_eligible
from asr_bench.freeze import (FreezeError, check_artifact, create_freeze, dumps_freeze, load_freeze, verify_audio,
                              verify_freeze, write_freeze)
from asr_bench.schema import FIELDS
from asr_bench.splits import (EXECUTED_ORDER, SplitConfig, SplitConfigError, SplitError, _bucket, apply_plan,
                              assign_splits, group_records, hash_position, leakage_report, records_from_rows,
                              records_from_utterances)
from asr_bench.validate import validate_rows

# Registry gate (source-registry stage): these S2/S3 tests run against a toy registry in which the
# toy sources are registered and authorised; the bundled registry authorises nothing.
from asr_bench.registry import SourceRegistry
TOY_REGISTRY = SourceRegistry.from_dict({"format": "asr_bench.source_registry/1", "registry_version": 1, "sources": {
    sid: {"name": sid, "family": "toy", "intended_use": "test", "acquisition_status": "toy", "licence": lic,
          "gate_status": "toy", "use_restriction": ur, "acquisition_authorised": True, "blockers": []}
    for sid, lic, ur in (("toy", "toy (test fixture)", "train_ok"), ("toyg", "toy gated licence (gate terms unread)", "blocked"),
                         ("toyev", "toy eval-only licence", "eval_only"))}})


def build_rows(*a, **k):
    return _build_rows(*a, registry=TOY_REGISTRY, **k)

passed = 0
failed = 0


def check(name: str, condition: bool, detail="") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


RATIOS = {"train": 0.70, "dev": 0.10, "test": 0.10, "final_test": 0.10}


def cfg(salt="udk-phase2a-v1", **sources) -> SplitConfig:
    srcs = {"toy": {"policy": "hash", "ratios": dict(RATIOS)}}
    srcs.update(sources)
    return SplitConfig.from_dict({"format": "asr_bench.split_config/1", "salt": salt, "sources": srcs})


def mkrow(i, spk, sess=None, rec=None, src="toy", restr="train_ok", split="dev", text=None, audio=None, lang="en-IN"):
    """A schema-valid toy row (English, no tokens); `split` is a placeholder until a plan is applied."""
    return {
        "utt_id": f"{src}:{i}", "audio_path": f"{i}.wav", "audio_sha256": audio or sha(f"{src}-{i}"),
        "source_dataset": src, "source_version": "0", "speaker_id": spk, "session_id": sess, "recording_id": rec,
        "sample_rate_hz": 16000, "duration_s": 1.0, "channels": 1,
        "language_primary": lang, "languages_present": [lang], "is_code_switched": False, "cmi": None,
        "transcript_ref": text if text is not None else f"toy utterance {src} {i}", "transcript_romanised": None,
        "tokens": None, "script": "Latn", "english_word_script": None,
        "provenance": "read", "environment": "quiet", "condition_device": "close",
        "condition_real_or_synthetic": "real", "aug_recipe": None, "seed": None, "snr_db": None, "clipping_ratio": None,
        "overlap": False, "overlap_spans": None, "overlap_rel_db": None, "safety_tags": None, "keyword_spans": None,
        "split": split, "licence": "toy (test fixture)", "use_restriction": restr,
    }


def plan_rows(rows, config):
    plan = assign_splits(records_from_rows(rows), config)
    return plan, (apply_plan(rows, plan) if plan.ok else None)


def errs(issues, field=None):
    return [i for i in issues if i.level == "error" and (field is None or i.field == field)]


# A toy corpus: 80 speakers x 2 utterances, one session per speaker.
BASE_ROWS = [mkrow(f"{s:03d}{k}", f"toy:spk{s:03d}", f"toy:sess{s:03d}") for s in range(80) for k in "ab"]
C = cfg()

# --- configuration ----------------------------------------------------------------------------------
ex = SplitConfig.load(HERE / "examples" / "toy_split_config.json")
check("example config: approved toy ratios 0.70/0.10/0.10/0.10 and salt udk-phase2a-v1",
      ex.salt == "udk-phase2a-v1" and ex.sources["toy"]["ratios"] == RATIOS)
good = {"format": "asr_bench.split_config/1", "salt": "s", "sources": {"toy": {"policy": "hash", "ratios": dict(RATIOS)}}}
bad_configs = {
    "missing format": {k: v for k, v in good.items() if k != "format"},
    "empty salt": {**good, "salt": " "},
    "no sources (no defaults)": {**good, "sources": {}},
    "unknown top-level key": {**good, "ratios": RATIOS},
    "policy 'given' not implemented (D-S3-8)": {**good, "sources": {"toy": {"policy": "given"}}},
    "unknown policy": {**good, "sources": {"toy": {"policy": "random"}}},
    "ratios missing final_test": {**good, "sources": {"toy": {"policy": "hash", "ratios": {"train": 0.8, "dev": 0.1, "test": 0.1}}}},
    "negative ratio": {**good, "sources": {"toy": {"policy": "hash", "ratios": {**RATIOS, "train": 0.9, "dev": -0.1}}}},
    "ratios not summing to 1": {**good, "sources": {"toy": {"policy": "hash", "ratios": {**RATIOS, "train": 0.5}}}},
    "boolean ratio": {**good, "sources": {"toy": {"policy": "hash", "ratios": {**RATIOS, "train": True, "dev": 0.0}}}},
    "fixed to an unknown split": {**good, "sources": {"toy": {"policy": "fixed", "split": "holdout"}}},
    "extra key in a policy": {**good, "sources": {"toy": {"policy": "fixed", "split": "test", "ratios": RATIOS}}},
}
for name, raw in bad_configs.items():
    check(f"invalid config rejected: {name}", raises(lambda raw=raw: SplitConfig.from_dict(raw), SplitConfigError))
check("config digest changes with the salt", cfg("a").sha256 != cfg("b").sha256)

# --- deterministic assignment ------------------------------------------------------------------------
p1 = assign_splits(records_from_rows(BASE_ROWS), C)
p2 = assign_splits(records_from_rows(BASE_ROWS), C)
check("plan on the toy corpus has no errors", p1.ok, [str(i) for i in p1.issues])
check("same input + config -> identical assignment and report", p1.assignments == p2.assignments and p1.report == p2.report)
shuffled = copy.deepcopy(BASE_ROWS)
random.Random(7).shuffle(shuffled)
check("shuffled input -> identical assignment", assign_splits(records_from_rows(shuffled), C).assignments == p1.assignments)
p_salt = assign_splits(records_from_rows(BASE_ROWS), cfg("udk-phase2a-v2"))
check("different salt -> different split", p_salt.assignments != p1.assignments)
check("salt and config digest are recorded in the report",
      p1.report["salt"] == "udk-phase2a-v1" and p1.report["split_config_sha256"] == C.sha256 and p_salt.report["salt"] == "udk-phase2a-v2")
u = hash_position(C.salt, "speaker_id=toy:spk000")
check("hash position is in [0,1) and reproducible", 0 <= u < 1 and u == hash_position("udk-phase2a-v1", "speaker_id=toy:spk000"))
counts = p1.report["splits"]
check("all four executed splits receive groups on 80 speakers", all(counts[s]["groups"] > 0 for s in EXECUTED_ORDER), counts)
check("every row assigned exactly once", len(p1.assignments) == len(BASE_ROWS) and p1.report["unassigned_rows"] == 0)
check("both utterances of a speaker land in the same split",
      all(p1.assignments[f"toy:{s:03d}a"] == p1.assignments[f"toy:{s:03d}b"] for s in range(80)))

# --- grouping --------------------------------------------------------------------------------------
chain = [mkrow("c1", "toy:A", "toy:s1"), mkrow("c2", "toy:B", "toy:s1"), mkrow("c3", "toy:B", None, "toy:r1"),
         mkrow("c4", "toy:C", None, "toy:r1"), mkrow("c5", "toy:D")]
gs = group_records(records_from_rows(chain))
check("transitive grouping: speaker A-s1-B-r1-C is one group, D alone", sorted(len(g.records) for g in gs) == [1, 4], gs)
check("group key = smallest speaker_id", {g.key for g in gs} == {"speaker_id=toy:A", "speaker_id=toy:D"})
check("a grouped chain lands in one split",
      len({assign_splits(records_from_rows(chain), C).assignments[f"toy:c{i}"] for i in (1, 2, 3, 4)}) == 1)
two_src = [mkrow("1", "a:spk1", src="a"), mkrow("1", "b:spk1", src="b")]
check("namespaced a:spk1 and b:spk1 are separate groups", len(group_records(records_from_rows(two_src))) == 2)
check("session key used when a group has no speaker", group_records(records_from_rows([mkrow("n1", None, "toy:s9")]))[0].key == "session_id=toy:s9")
check("recording key used when only a recording exists", group_records(records_from_rows([mkrow("n2", None, None, "toy:r9")]))[0].key == "recording_id=toy:r9")
check("no identifiers -> no key is invented", group_records(records_from_rows([mkrow("n3", None)]))[0].key is None)
check("a session ID never links to an identical speaker ID string (typed IDs)",
      len(group_records(records_from_rows([mkrow("t1", "toy:x"), mkrow("t2", "toy:y", "toy:x")]))) == 2)
check("audio_sha256 never groups rows", len(group_records(records_from_rows(
    [mkrow("h1", "toy:h1", audio=sha("same")), mkrow("h2", "toy:h2", audio=sha("same"))]))) == 2)

# --- null identities -------------------------------------------------------------------------------
nulls = [mkrow("z1", None), mkrow("z2", None, "toy:zs"), mkrow("z3", "toy:zspk", "toy:zs")]
pn, rn = plan_rows(nulls, C)
check("null-speaker rows and their whole group go to eval_only", pn.ok and all(r["split"] == "eval_only" for r in rn), pn.assignments)
reasons = {g["group_key"]: g["reason"] for g in pn.report["eval_only_inventory_groups"]}
check("the limitation is reported (no identifiers / null speaker)",
      any("no speaker/session/recording identifier" in r for r in reasons.values()) and any("null speaker_id" in r for r in reasons.values()), reasons)
check("missing-ID counts are reported", pn.report["missing_ids"] == {"speaker_id": 2, "session_id": 1, "recording_id": 3})

# --- leakage after assignment ---------------------------------------------------------------------
linked = BASE_ROWS + [mkrow("x1", "toy:spk001", "toy:sessX", "toy:recX"), mkrow("x2", "toy:spk050", "toy:sessX"),
                      mkrow("x3", "toy:spk060", None, "toy:recX")]
pl, rl = plan_rows(linked, C)
check("assigned manifest passes S1 (no speaker/session/recording in two splits)", pl.ok and not errs(validate_rows(list(enumerate(rl, 1)))))
issues, rep = leakage_report(rl)
check("leakage report on the assigned manifest has no errors", not errs(issues), [str(i) for i in errs(issues)])
leak = copy.deepcopy(rl)
target = next(r for r in leak if r["utt_id"] == "toy:000a")
target["split"] = "test" if target["split"] != "test" else "dev"
check("planted speaker in two splits -> error", bool(errs(leakage_report(leak)[0], "speaker_id")))
check("planted session in two splits -> error", bool(errs(leakage_report(leak)[0], "session_id")))
leak_r = copy.deepcopy(rl)
x3 = next(r for r in leak_r if r["utt_id"] == "toy:x3")
x3["split"] = "test" if x3["split"] != "test" else "dev"
check("planted recording in two splits -> error", bool(errs(leakage_report(leak_r)[0], "recording_id")))

# --- exact audio / transcript duplicates -----------------------------------------------------------------
same_audio = [mkrow("d1", "toy:d1", split="dev", audio=sha("dup")), mkrow("d2", "toy:d2", split="dev", audio=sha("dup"))]
check("same audio in two different groups (same split) -> error (D-S3-5)", bool(errs(leakage_report(same_audio)[0], "audio_sha256")))
cross_audio = [mkrow("d1", "toy:d1", split="dev", audio=sha("dup")), mkrow("d2", "toy:d2", split="test", audio=sha("dup"))]
check("same audio across splits -> error", bool(errs(leakage_report(cross_audio)[0], "audio_sha256")))
one_group = [mkrow("g1", "toy:g", split="dev", audio=sha("dup")), mkrow("g2", "toy:g", split="dev", audio=sha("dup"))]
gi = leakage_report(one_group)[0]
check("same audio within one group and split -> warning only", not errs(gi) and any(i.field == "audio_sha256" for i in gi))
texts = [mkrow("w1", "toy:w1", split="dev", text="please help me"), mkrow("w2", "toy:w2", split="test", text="please help me")]
ti = leakage_report(texts)[0]
check("exact duplicate transcript across splits -> warning, not error (D-S3-9)",
      not errs(ti) and any(i.level == "warning" and i.field == "transcript_ref" for i in ti))

# --- blocked / eval_only groups ---------------------------------------------------------------------
blk = [mkrow("b1", "toy:bspk", "toy:bs"), mkrow("b2", "toy:bspk", "toy:bs", restr="blocked")]
pb, rb = plan_rows(blk, C)
check("group with any blocked row -> whole group eval_only (D-S3-4)", pb.ok and {r["split"] for r in rb} == {"eval_only"})
check("blocked reason reported", any("blocked" in g["reason"] for g in pb.report["eval_only_inventory_groups"]))
check("blocked rows are never eligible", select_eligible(rb, "eval_only")[0] == [rb[0]] and
      all(select_eligible(rb, s)[0] == [] for s in EXECUTED_ORDER))
name = next(f"toy:e{i}" for i in range(1000) if _bucket(hash_position(C.salt, f"speaker_id=toy:e{i}"), RATIOS, EXECUTED_ORDER) == "train")
ev = [mkrow("e1", name), mkrow("e2", name, restr="eval_only")]
pe, re_ = plan_rows(ev, C)
check("group with an eval_only row never enters train (D-S3-3)", pe.ok and {r["split"] for r in re_} != {"train"} and len({r["split"] for r in re_}) == 1)
uu = hash_position(C.salt, f"speaker_id={name}")
check("constrained placement: position inside the train bucket mapped onto permitted splits (no rehashing)",
      re_[0]["split"] == _bucket(uu / RATIOS["train"], RATIOS, ("dev", "test", "final_test")))
check("constrained assignment is reported with hashed and assigned split",
      pe.report["constrained_groups"][0]["hashed_split"] == "train" and pe.report["constrained_groups"][0]["assigned_split"] == re_[0]["split"])
name_dev = next(f"toy:f{i}" for i in range(1000) if _bucket(hash_position(C.salt, f"speaker_id=toy:f{i}"), RATIOS, EXECUTED_ORDER) == "dev")
pd = assign_splits(records_from_rows([mkrow("f1", name_dev, restr="eval_only")]), C)
check("eval_only group already outside train is not moved or reported", pd.assignments["toy:f1"] == "dev" and pd.report["constrained_groups"] == [])
only_train = cfg(toy={"policy": "hash", "ratios": {"train": 1.0, "dev": 0.0, "test": 0.0, "final_test": 0.0}})
check("eval_only row with a train-only source -> plan error", not assign_splits(records_from_rows([mkrow("o1", "toy:o", restr="eval_only")]), only_train).ok)
fixed_train = cfg(toy={"policy": "fixed", "split": "train"})
check("eval_only row in a source fixed to train -> plan error", not assign_splits(records_from_rows([mkrow("o2", "toy:o", restr="eval_only")]), fixed_train).ok)

# --- fixed hold-out and source-disjoint report -------------------------------------------------------
held = [mkrow(f"h{i}", f"toyheld:s{i}", src="toyheld") for i in range(5)]
ph, rh = plan_rows(BASE_ROWS + held, cfg(toyheld={"policy": "fixed", "split": "test"}))
check("fixed policy: every row of the held-out source goes to test", ph.ok and all(r["split"] == "test" for r in rh if r["source_dataset"] == "toyheld"))
sd = leakage_report(rh)[1]["source_disjoint_by_language"]["en-IN"]
check("source-disjoint report: held-out source listed, the hashed source (also in train/dev) is not",
      sd["held_out_test_sources"] == ["toyheld"] and "toy" in sd["test_sources"], sd)
check("source missing from the config -> plan error (no defaults)", not assign_splits(records_from_rows(held), C).ok)

# --- small / edge inputs ---------------------------------------------------------------------------
pe0 = assign_splits([], C)
check("empty input -> empty plan, no errors", pe0.ok and pe0.assignments == {} and pe0.report["groups"] == 0)
ps = assign_splits(records_from_rows([mkrow("s1", "toy:solo"), mkrow("s2", "toy:solo")]), C)
check("one speaker -> one group in one split; other splits reported empty (not forced)",
      len(set(ps.assignments.values())) == 1 and sum(v["groups"] == 0 for v in ps.report["splits"].values()) == 4)
dup = assign_splits(records_from_rows([mkrow("u1", "toy:a"), mkrow("u1", "toy:b")]), C)
check("duplicate utt_id in the input -> plan error", not dup.ok and bool(errs(dup.issues, "utt_id")))
span = assign_splits(records_from_rows([mkrow("1", "shared", src="toy"), mkrow("2", "shared", src="toyheld")]),
                     cfg(toyheld={"policy": "fixed", "split": "test"}))
check("group spanning two sources (un-namespaced IDs) -> plan error", not span.ok)
check("a plan with errors cannot be used", raises(lambda: dup.split_for(SourceInfo("toy", "0", "x", "train_ok")), SplitError)
      and raises(lambda: apply_plan([], dup), SplitError))

# --- final-test freeze ------------------------------------------------------------------------------
MAN = rl  # assigned, leakage-clean manifest
fz = create_freeze(MAN, C)
final_ids = sorted(r["utt_id"] for r in MAN if r["split"] == "final_test")
check("freeze covers exactly the final_test rows", [e["utt_id"] for e in fz["rows"]] == final_ids and fz["n_rows"] == len(final_ids) > 0)
check("freeze records config digest and salt", fz["split_config_sha256"] == C.sha256 and fz["salt"] == "udk-phase2a-v1")
text_dump = dumps_freeze(fz)
check("freeze holds IDs and hashes only (no transcript text, no audio path)",
      "toy utterance" not in text_dump and ".wav" not in text_dump)
shuf = copy.deepcopy(MAN)
random.Random(3).shuffle(shuf)
check("byte-identical freeze on re-creation and on shuffled rows", dumps_freeze(create_freeze(MAN, C)) == text_dump == dumps_freeze(create_freeze(shuf, C)))
check("verify: unchanged manifest -> no issues", verify_freeze(MAN, fz, C) == [])


def mutate(fn):
    m = copy.deepcopy(MAN)
    fn(m)
    return verify_freeze(m, fz, C)


def first_final(m):
    return next(r for r in m if r["split"] == "final_test")


moved_path = mutate(lambda m: first_final(m).update(audio_path="moved/elsewhere.wav"))
check("changing audio_path only -> freeze still verifies (P-S2-2)", moved_path == [], moved_path)
check("... and the re-created freeze is identical",
      dumps_freeze(create_freeze([{**r, "audio_path": "x/" + r["audio_path"]} for r in MAN], C)) == text_dump)
check("changed audio -> AUDIO CHANGED", any("AUDIO CHANGED" in i.message for i in mutate(lambda m: first_final(m).update(audio_sha256=sha("new")))))
check("changed duration with same audio -> metadata-only audio change reported",
      any("identical audio bytes" in i.message for i in mutate(lambda m: first_final(m).update(duration_s=1.5))))
check("changed transcript -> REFERENCE CHANGED", any("REFERENCE CHANGED" in i.message for i in mutate(lambda m: first_final(m).update(transcript_ref="edited"))))
check("changed metadata (environment) -> METADATA CHANGED", any("METADATA CHANGED" in i.message for i in mutate(lambda m: first_final(m).update(environment="crowd"))))
check("changed licence -> METADATA CHANGED", any("METADATA CHANGED" in i.message for i in mutate(lambda m: first_final(m).update(licence="other"))))
check("added carry-over field (pair_id) -> METADATA CHANGED", any("METADATA CHANGED" in i.message for i in mutate(lambda m: first_final(m).update(pair_id="P1"))))
check("row moved into final_test -> ADDED", any("ADDED" in i.message for i in mutate(lambda m: next(r for r in m if r["split"] == "dev").update(split="final_test"))))
check("row moved out of final_test -> MOVED", any("MOVED" in i.message for i in mutate(lambda m: first_final(m).update(split="test"))))
check("row deleted -> REMOVED", any("REMOVED" in i.message for i in mutate(lambda m: m.remove(first_final(m)))))
check("config digest mismatch -> error", bool(errs(verify_freeze(MAN, fz, cfg("other-salt")))))
tampered = copy.deepcopy(fz)
tampered["rows"][0]["reference_sha256"] = sha("x")
check("edited freeze artifact is detected (freeze_sha256 mismatch)", bool(check_artifact(tampered)) and bool(errs(verify_freeze(MAN, tampered))))

# frozen final_test blocks membership changes in later assignments
recs = records_from_rows(MAN)
check("re-assignment with the freeze and the same config -> ok", assign_splits(recs, C, freeze=fz).ok)
check("re-assignment with a different config -> error", not assign_splits(recs, cfg("udk-phase2a-v2"), freeze=fz).ok)
drop = [r for r in recs if r.utt_id != final_ids[0]]
check("dropping a frozen final_test row -> error", not assign_splits(drop, C, freeze=fz).ok)
extra_name = next(f"toy:q{i}" for i in range(2000) if _bucket(hash_position(C.salt, f"speaker_id=toy:q{i}"), RATIOS, EXECUTED_ORDER) == "final_test")
add = records_from_rows(MAN + [mkrow("q1", extra_name)])
check("new data that would join the frozen final_test -> error", not assign_splits(add, C, freeze=fz).ok)

# refusing to freeze
bad = copy.deepcopy(MAN)
bad[0]["environment"] = "market"
check("schema-invalid manifest -> freeze refused", raises(lambda: create_freeze(bad, C), FreezeError))
check("leaky manifest -> freeze refused", raises(lambda: create_freeze(leak, C), FreezeError))
check("manifest with no final_test rows -> freeze refused", raises(lambda: create_freeze([r for r in MAN if r["split"] != "final_test"], C), FreezeError))

# --- on disk: artifacts, audio verification, CLI, adapter end to end --------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="asr_bench_s3_"))
try:
    fpath = tmp / "freeze.json"
    write_freeze(fz, fpath)
    check("freeze written and re-loaded intact", load_freeze(fpath) == fz)
    check("an existing freeze is never overwritten", raises(lambda: write_freeze(fz, fpath), FileExistsError))
    tp = tmp / "tampered.json"
    tp.write_text(dumps_freeze(tampered), encoding="utf-8")
    check("loading an edited freeze file fails", raises(lambda: load_freeze(tp), FreezeError))

    def write_wav(path: Path, frames: int, seed: int) -> None:
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
            w.writeframes(bytes((i * seed) % 251 for i in range(frames * 2)))

    root = tmp / "audio_toy"
    root.mkdir()

    class ToyAdapter(DatasetAdapter):
        source = SourceInfo("toy", "0", "toy (test fixture)", "train_ok")

        def utterances(self):
            for s in range(40):
                for k in "ab":
                    yield SourceUtterance(
                        source_utt_id=f"{s}{k}", audio_path=f"{s}{k}.wav", speaker_id=f"toy:spk{s}", session_id=f"toy:sess{s}",
                        recording_id=None, transcript_ref=f"toy line {s}{k}", transcript_romanised=None, tokens=None,
                        language_primary="en-IN", languages_present=["en-IN"], is_code_switched=False, cmi=None, script="Latn",
                        english_word_script=None, provenance="read", environment="quiet", condition_device="close",
                        condition_real_or_synthetic="real", aug_recipe=None, seed=None, snr_db=None, clipping_ratio=None,
                        overlap=False, overlap_spans=None, overlap_rel_db=None, safety_tags=None, keyword_spans=None,
                        licence=None, use_restriction="eval_only" if s == 3 else None)

    ad = ToyAdapter()
    for n, utt_ in enumerate(ad.utterances()):
        write_wav(root / utt_.audio_path, 1600 + n, n + 3)
    plan = assign_splits(records_from_utterances(ad.source, ad.utterances()), C)
    rows_e2e, fails = build_rows(ad, plan.split_for(ad.source), audio_root=root)
    check("adapter -> split plan -> build_rows: all rows built", plan.ok and len(rows_e2e) == 80 and fails == [], fails)
    check("... rows carry the planned splits", all(r["split"] == plan.assignments[r["utt_id"]] for r in rows_e2e))
    check("... and pass S1 validation + leakage report", not errs(leakage_report(rows_e2e)[0]), [str(i) for i in errs(leakage_report(rows_e2e)[0])])
    check("... the eval_only-restricted speaker is not in train",
          all(r["split"] != "train" for r in rows_e2e if r["speaker_id"] == "toy:spk3"))
    fz2 = create_freeze(rows_e2e, C)
    check("on-disk audio verification with a source->root mapping", verify_audio(rows_e2e, {"toy": root}) == [])
    moved_root = tmp / "moved_audio"
    shutil.copytree(root, moved_root)
    check("files moved to a new root: freeze and on-disk check still pass",
          verify_freeze(rows_e2e, fz2, C) == [] and verify_audio(rows_e2e, {"toy": moved_root}) == [])
    fid = next(r for r in rows_e2e if r["split"] == "final_test")
    (moved_root / fid["audio_path"]).write_bytes(b"RIFF changed bytes")
    check("changed file bytes on disk -> detected", bool(errs(verify_audio(rows_e2e, {"toy": moved_root}), "audio_sha256")))
    check("no root for a source -> error", bool(errs(verify_audio(rows_e2e, {}))))

    man_path = tmp / "manifest.jsonl"
    man_path.write_text("".join(json.dumps(r) + "\n" for r in MAN), encoding="utf-8")
    cfg_path = HERE / "examples" / "toy_split_config.json"

    def cli(mod, *args):
        return subprocess.run([sys.executable, "-m", mod, *args], capture_output=True, text=True, cwd=HERE.parent)

    out = tmp / "reassigned.jsonl"
    r = cli("asr_bench.splits", "assign", "--manifest", str(man_path), "--config", str(cfg_path), "--out", str(out),
            "--report", str(tmp / "report.json"))
    check("CLI splits assign: exit 0, manifest + report written", r.returncode == 0 and out.exists() and (tmp / "report.json").exists(), r.stdout + r.stderr)
    r = cli("asr_bench.splits", "assign", "--manifest", str(man_path), "--config", str(cfg_path), "--out", str(out))
    check("CLI splits assign refuses to overwrite", r.returncode == 2, r.stdout + r.stderr)
    r = cli("asr_bench.splits", "report", "--manifest", str(out))
    check("CLI splits report on the result: exit 0", r.returncode == 0, r.stdout[-500:] + r.stderr)
    fcli = tmp / "freeze_cli.json"
    r = cli("asr_bench.freeze", "create", "--manifest", str(out), "--config", str(cfg_path), "--out", str(fcli))
    check("CLI freeze create: exit 0", r.returncode == 0 and fcli.exists(), r.stdout + r.stderr)
    r = cli("asr_bench.freeze", "verify", "--manifest", str(out), "--freeze", str(fcli), "--config", str(cfg_path))
    check("CLI freeze verify: VERIFIED", r.returncode == 0 and "VERIFIED" in r.stdout, r.stdout + r.stderr)
    edited = tmp / "edited.jsonl"
    lines = out.read_text(encoding="utf-8").splitlines()
    rows_out = [json.loads(x) for x in lines]
    next(x for x in rows_out if x["split"] == "final_test")["transcript_ref"] = "edited"
    edited.write_text("".join(json.dumps(x) + "\n" for x in rows_out), encoding="utf-8")
    r = cli("asr_bench.freeze", "verify", "--manifest", str(edited), "--freeze", str(fcli))
    check("CLI freeze verify on an edited manifest: MISMATCH, exit 1", r.returncode == 1 and "REFERENCE CHANGED" in r.stdout, r.stdout + r.stderr)
    r = cli("asr_bench.freeze", "create", "--manifest", str(out), "--config", str(cfg_path), "--out", str(fcli))
    check("CLI freeze create refuses to overwrite an existing freeze", r.returncode == 2, r.stdout + r.stderr)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

check("row field order is untouched by apply_plan", list(rl[0])[:len(FIELDS)] == list(FIELDS))

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
