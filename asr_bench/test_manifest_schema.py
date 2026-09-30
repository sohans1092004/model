"""S1 tests: the Phase 2A §3 manifest schema (schema.py) and validator (validate.py), on toy
rows only -- no real dataset, no audio, no model. Same check() style as the repo's test_*.py.

    python asr_bench/test_manifest_schema.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.eligibility import eligible_for, legally_usable, select_eligible
from asr_bench.schema import FIELDS, NEVER_NULL, validate_row
from asr_bench.validate import read_jsonl, validate_rows

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


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# A toy code-switched row (the Phase 2A §1 example sentence). Invented values, source "toy".
# cmi 37.5 = 100 * (1 - 5/8): 8 tagged tokens, the dominant language (hi) has 5.
BASE = {
    "utt_id": "toy:0001", "audio_path": "toy/0001.wav", "audio_sha256": sha("toy-0001"),
    "source_dataset": "toy", "source_version": "0", "speaker_id": "toy:spk01",
    "session_id": "toy:sess01", "recording_id": None,
    "sample_rate_hz": 16000, "duration_s": 3.2, "channels": 1,
    "language_primary": "hi", "languages_present": ["hi", "en"], "is_code_switched": True, "cmi": 37.5,
    "transcript_ref": "help me mujhe koi attack kar raha hai", "transcript_romanised": None,
    "tokens": [{"text": w, "lang": l, "script": "Latn", "start_s": None, "end_s": None}
               for w, l in zip("help me mujhe koi attack kar raha hai".split(),
                               ["en", "en", "hi", "hi", "en", "hi", "hi", "hi"])],
    "script": "Latn", "english_word_script": "latin",
    "provenance": "acted_scripted", "environment": "quiet", "condition_device": "phone_hand",
    "condition_real_or_synthetic": "real", "aug_recipe": None, "seed": None,
    "snr_db": None, "clipping_ratio": None,
    "overlap": False, "overlap_spans": None, "overlap_rel_db": None,
    "safety_tags": ["safety_keyword", "intra_sentence_cs"],
    "keyword_spans": [{"text": "help me", "start_s": 0.1, "end_s": 0.6},
                      {"text": "attack", "start_s": 1.4, "end_s": 1.9}],
    "split": "dev", "licence": "toy (test fixture)", "use_restriction": "train_ok",
}


def row(**changes) -> dict:
    r = copy.deepcopy(BASE)
    r.update(changes)
    return r


def errors(r, field=None, indic=None) -> list:
    return [i for i in validate_row(r, indic_languages=indic) if i.level == "error" and (field is None or i.field == field)]


def warnings(r, field=None) -> list:
    return [i for i in validate_row(r) if i.level == "warning" and (field is None or i.field == field)]


def manifest_errors(rows: list, field=None) -> list:
    return [i for i in validate_rows(list(enumerate(rows, start=1)))
            if i.level == "error" and (field is None or i.field == field)]


# --- the base row ------------------------------------------------------------------------
check("toy base row is valid, with no warnings", validate_row(BASE) == [], [str(i) for i in validate_row(BASE)])
check("schema has every §3 field once", len(FIELDS) == len(set(FIELDS)) == 36, len(FIELDS))

# --- null handling (§3: fields a source cannot fill are null, never guessed) ----------------
for f in NEVER_NULL:
    check(f"null {f} is an error", bool(errors(row(**{f: None}), f)))
for f in ("session_id", "recording_id", "transcript_romanised", "snr_db", "clipping_ratio"):
    check(f"null {f} is allowed", not errors(row(**{f: None})))
check("tokens null -> cmi may be null", not errors(row(tokens=None, cmi=None)))
check("safety_tags null -> keyword_spans may be null", not errors(row(safety_tags=None, keyword_spans=None)))
missing = row()
del missing["session_id"]
check("absent key is an error (must be present as null)", bool(errors(missing, "session_id")))
check("unknown key is a warning, not an error (Phase 1 §15 carry-over)",
      not errors(row(pair_id="P0001")) and bool(warnings(row(pair_id="P0001"), "pair_id")))
check("non-object row is an error", bool(errors([1, 2, 3])))
check("empty transcript_ref allowed (no-speech segment, §5 hallucination)", not errors(row(transcript_ref="")))

# --- enums ---------------------------------------------------------------------------------
for f, bad in (("provenance", "scripted"), ("environment", "market"), ("condition_device", "hand"),
               ("condition_real_or_synthetic", "augmented"), ("english_word_script", "roman"),
               ("split", "validation"), ("use_restriction", "research_only")):
    check(f"{f}={bad!r} is rejected", bool(errors(row(**{f: bad}), f)))
check("unknown safety tag is rejected", bool(errors(row(safety_tags=["scream"]), "safety_tags")))
check("real_incident (Phase 1 §15 only) is rejected by the Phase 2A §3 enum -- open conflict D-PROV-1",
      bool(errors(row(provenance="real_incident"), "provenance")))
check("'unknown' is a valid value where §3 lists it",
      not errors(row(provenance="unknown", environment="unknown", condition_device="unknown", english_word_script="unknown")))

# --- identity, hash, format ------------------------------------------------------------------
check("utt_id without '<source>:' is rejected", bool(errors(row(utt_id="0001"), "utt_id")))
check("utt_id ':0001' is rejected", bool(errors(row(utt_id=":0001"), "utt_id")))
check("upper-case sha256 is rejected", bool(errors(row(audio_sha256=sha("x").upper()), "audio_sha256")))
check("short sha256 is rejected", bool(errors(row(audio_sha256="abc123"), "audio_sha256")))
check("float sample_rate_hz is rejected", bool(errors(row(sample_rate_hz=16000.0), "sample_rate_hz")))
check("boolean channels is rejected", bool(errors(row(channels=True), "channels")))
check("zero duration is rejected", bool(errors(row(duration_s=0), "duration_s")))
check("NaN duration is rejected", bool(errors(row(duration_s=float("nan")), "duration_s")))
check("original 44.1 kHz stereo is allowed", not errors(row(sample_rate_hz=44100, channels=2)))
check("empty audio_path is rejected", bool(errors(row(audio_path=" "), "audio_path")))
check("clipping_ratio 1.5 is rejected", bool(errors(row(clipping_ratio=1.5), "clipping_ratio")))

# --- language / code-switch ------------------------------------------------------------------
check("en-IN is a valid language tag", not errors(row(language_primary="en-IN", languages_present=["en-IN", "hi"])))
check("'Hindi' is not a BCP-47 tag", bool(errors(row(language_primary="Hindi"), "language_primary")))
check("empty languages_present is rejected", bool(errors(row(languages_present=[]), "languages_present")))
check("duplicate languages_present is rejected", bool(errors(row(languages_present=["hi", "hi"]), "languages_present")))
check("primary language missing from languages_present -> warning",
      bool(warnings(row(language_primary="te"), "language_primary")))
check("is_code_switched true with one language -> warning",
      bool(warnings(row(languages_present=["hi"], tokens=None, cmi=None), "is_code_switched")))
check("fully tagged tokens without cmi is an error (§3: number if tags exist)", bool(errors(row(cmi=None), "cmi")))
check("cmi on a 0-1 scale is accepted as given (no scale assumed)", not errors(row(cmi=0.375)))
check("cmi on a 0-100 scale is accepted as given (no scale assumed)", not errors(row(cmi=37.5)))
check("cmi as a string is rejected (must be numeric)", bool(errors(row(cmi="37.5"), "cmi")))
check("cmi NaN is rejected", bool(errors(row(cmi=float("nan")), "cmi")))
partial = row(cmi=None)
partial["tokens"][0]["lang"] = None
check("partly tagged tokens: cmi may be null", not errors(partial, "cmi"))
bad_tok = row()
del bad_tok["tokens"][0]["script"]
check("token missing a key is an error", bool(errors(bad_tok, "tokens[0]")))
check("empty tokens list is rejected (use null)", bool(errors(row(tokens=[]), "tokens")))
check("no Indic grouping configured: null english_word_script is allowed (no hidden language list)",
      not errors(row(english_word_script=None)))
check("Indic grouping {hi, te} configured: Hindi row with null english_word_script is an error",
      bool(errors(row(english_word_script=None), "english_word_script", indic={"hi", "te"})))
check("Indic grouping configured: English-only row may leave english_word_script null",
      not errors(row(language_primary="en-IN", languages_present=["en-IN"], is_code_switched=False,
                     tokens=None, cmi=None, english_word_script=None), indic={"hi", "te"}))
check("Indic grouping {te} configured: Hindi row is not affected",
      not errors(row(english_word_script=None), indic={"te"}))
check("script 'devanagari' is rejected (ISO 15924: Deva)", bool(errors(row(script="devanagari"), "script")))
check("script 'mixed' is allowed", not errors(row(script="mixed")))

# --- synthetic vs real -----------------------------------------------------------------------
check("synthetic row without aug_recipe/seed is rejected",
      len(errors(row(condition_real_or_synthetic="synthetic"))) == 2)
check("synthetic row with aug_recipe + integer seed is valid",
      not errors(row(condition_real_or_synthetic="synthetic", aug_recipe="toy_recipe", seed=7)))
check("synthetic seed must be an integer, not a bool",
      bool(errors(row(condition_real_or_synthetic="synthetic", aug_recipe="toy_recipe", seed=True), "seed")))
check("real row carrying a seed is rejected", bool(errors(row(seed=7), "seed")))

# --- overlap ---------------------------------------------------------------------------------
check("overlap true without spans or level is rejected", len(errors(row(overlap=True))) == 2)
check("overlap true with spans and level is valid",
      not errors(row(overlap=True, overlap_spans=[{"start_s": 1.0, "end_s": 2.0}], overlap_rel_db=-6)))
check("overlap false with a level is rejected", bool(errors(row(overlap_rel_db=-6), "overlap_rel_db")))

# --- safety tags / keyword spans ---------------------------------------------------------------
check("safety_tags set, keyword_spans null is rejected", bool(errors(row(keyword_spans=None), "keyword_spans")))
check("safety_tags set, keyword_spans [] is allowed", not errors(row(safety_tags=["negation"], keyword_spans=[])))
check("keyword span with start after end is rejected",
      bool(errors(row(keyword_spans=[{"text": "help", "start_s": 2.0, "end_s": 1.0}]))))
check("keyword span without times is rejected",
      bool(errors(row(keyword_spans=[{"text": "help", "start_s": None, "end_s": None}]))))
check("keyword span past duration_s -> warning",
      bool(warnings(row(keyword_spans=[{"text": "help", "start_s": 3.0, "end_s": 9.0}]))))

# --- licence / use_restriction -----------------------------------------------------------------
check("empty licence is rejected", bool(errors(row(licence=""), "licence")))
for s in ("train", "dev", "test", "final_test"):
    check(f"blocked row in executed split {s} is rejected",
          bool(errors(row(use_restriction="blocked", split=s), "use_restriction")))
BLOCKED = row(use_restriction="blocked", split="eval_only", licence="toy gated licence (gate terms unread)")
check("blocked row kept as inventory (split eval_only) is a valid manifest row", validate_row(BLOCKED) == [],
      [str(i) for i in validate_row(BLOCKED)])
check("eval_only data in train is rejected", bool(errors(row(use_restriction="eval_only", split="train"), "use_restriction")))
check("eval_only data in dev / test / eval_only is allowed",
      all(not errors(row(use_restriction="eval_only", split=s)) for s in ("dev", "test", "final_test", "eval_only")))

# --- speaker-disjoint splits (§6.1, §7) ---------------------------------------------------------
for s in ("train", "dev", "test", "final_test"):
    check(f"null speaker_id in {s} is rejected", bool(errors(row(speaker_id=None, split=s), "speaker_id")))
check("null speaker_id in eval_only is allowed", not errors(row(speaker_id=None, split="eval_only")))

a = row()
b = row(utt_id="toy:0002", audio_sha256=sha("toy-0002"), session_id="toy:sess02")
check("two clean rows validate", manifest_errors([a, b]) == [], [str(i) for i in manifest_errors([a, b])])
check("same speaker in the same split is fine", not manifest_errors([a, b], "speaker_id"))
check("duplicate utt_id is rejected", bool(manifest_errors([a, row(audio_sha256=sha("x"), session_id="toy:s9")], "utt_id")))
check("same speaker in two splits is rejected", bool(manifest_errors([a, row(**{**b, "split": "test"})], "speaker_id")))
check("same speaker in eval_only and train is rejected",
      bool(manifest_errors([row(split="train"), row(**{**b, "split": "eval_only"})], "speaker_id")))
check("same session in two splits is rejected",
      bool(manifest_errors([a, row(**{**b, "speaker_id": "toy:spk02", "session_id": "toy:sess01", "split": "test"})], "session_id")))
check("same recording in two splits is rejected",
      bool(manifest_errors([row(recording_id="toy:rec1"),
                            row(**{**b, "speaker_id": "toy:spk02", "recording_id": "toy:rec1", "split": "test"})], "recording_id")))
check("same audio hash in two splits is rejected",
      bool(manifest_errors([a, row(**{**b, "speaker_id": "toy:spk02", "audio_sha256": a["audio_sha256"], "split": "test"})], "audio_sha256")))
same_split_dup = validate_rows(list(enumerate([a, row(**{**b, "audio_sha256": a["audio_sha256"]})], start=1)))
check("same audio hash twice in one split -> warning only",
      not [i for i in same_split_dup if i.level == "error"] and any(i.field == "audio_sha256" for i in same_split_dup))
check("null speakers in eval_only never collide with each other",
      not manifest_errors([row(speaker_id=None, split="eval_only"),
                           row(**{**b, "speaker_id": None, "split": "eval_only"})]))

# --- speaker namespacing contract (adapters namespace; the validator does not parse a prefix) ---
un_a = row(utt_id="toyA:1", source_dataset="toyA", speaker_id="spk1", session_id=None, split="train")
un_b = row(utt_id="toyB:1", source_dataset="toyB", speaker_id="spk1", session_id=None,
           audio_sha256=sha("toyB-1"), split="test")
check("contract: bare 'spk1' from two sources is read as ONE speaker leaking across splits",
      bool(manifest_errors([un_a, un_b], "speaker_id")))
ns_a = row(**{**un_a, "speaker_id": "toyA:spk1"})
ns_b = row(**{**un_b, "speaker_id": "toyB:spk1"})
check("contract: adapter-namespaced 'toyA:spk1' / 'toyB:spk1' are two speakers, no leakage",
      not manifest_errors([ns_a, ns_b]), [str(i) for i in manifest_errors([ns_a, ns_b])])
check("no prefix format is required: an un-namespaced speaker_id is still a valid row", not errors(row(speaker_id="spk1")))

# --- eligibility: (a) in manifest, (b) legally usable, (c) eligible for a split ------------------
check("(b) train_ok and eval_only rows are legally usable, blocked is not",
      legally_usable(row()) and legally_usable(row(use_restriction="eval_only")) and not legally_usable(BLOCKED))
check("(c) valid dev row is eligible for dev", eligible_for(row(), "dev") == [])
check("(c) dev row is not eligible for test", bool(eligible_for(row(), "test")))
check("(c) blocked inventory row is not eligible even for its own split eval_only",
      any("blocked" in r for r in eligible_for(BLOCKED, "eval_only")))
check("(c) blocked row is not eligible for any split",
      all(eligible_for(BLOCKED, s) for s in ("train", "dev", "test", "final_test", "eval_only")))
check("(c) eval_only-restricted row is never eligible for train",
      any("never for training" in r for r in eligible_for(row(use_restriction="eval_only", split="train"), "train")))
check("(c) eval_only-restricted row in test is eligible for test",
      eligible_for(row(use_restriction="eval_only", split="test"), "test") == [])
ok_rows, rejected = select_eligible([row(split="eval_only", use_restriction="eval_only"), BLOCKED], "eval_only")
check("select_eligible returns the usable row and reports the blocked one with its reason",
      len(ok_rows) == 1 and len(rejected) == 1 and rejected[0][0] is BLOCKED and any("blocked" in r for r in rejected[0][1]))
check("blocked inventory rows still take part in leakage checks (speaker also in train)",
      bool(manifest_errors([row(split="train"), row(**{**BLOCKED, "utt_id": "toy:0009", "audio_sha256": sha("toy-0009"),
                                                          "session_id": "toy:s9"})], "speaker_id")))

# --- JSONL reading and the CLI -----------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    good = Path(tmp) / "good.jsonl"
    good.write_text(json.dumps(a) + "\n\n" + json.dumps(b) + "\n", encoding="utf-8")
    bad = Path(tmp) / "bad.jsonl"
    bad.write_text(json.dumps(a) + "\n{not json\n", encoding="utf-8")
    rows, parse = read_jsonl(bad)
    check("unparseable line is reported with its line number", len(rows) == 1 and parse and parse[0].line == 2)

    def cli(*args):
        return subprocess.run([sys.executable, str(HERE / "validate.py"), *args], capture_output=True, text=True)

    r = cli(str(good))
    check("CLI: valid manifest exits 0", r.returncode == 0 and "VALID" in r.stdout, r.stdout + r.stderr)
    r = cli(str(bad))
    check("CLI: invalid manifest exits 1", r.returncode == 1 and "INVALID" in r.stdout, r.stdout + r.stderr)
    r = cli(str(Path(tmp) / "missing.jsonl"))
    check("CLI: unreadable file exits 2", r.returncode == 2, r.stdout + r.stderr)
    r = cli(str(good), "--json")
    check("CLI: --json output parses", r.returncode == 0 and json.loads(r.stdout)["valid"] is True, r.stdout)
    no_ews = Path(tmp) / "no_ews.jsonl"
    no_ews.write_text(json.dumps(row(english_word_script=None)) + "\n", encoding="utf-8")
    check("CLI: without --indic-languages a null english_word_script passes", cli(str(no_ews)).returncode == 0)
    r = cli(str(no_ews), "--indic-languages", "hi,te")
    check("CLI: --indic-languages hi,te makes it an error", r.returncode == 1 and "english_word_script" in r.stdout, r.stdout)
    inv = Path(tmp) / "inventory.jsonl"
    inv.write_text(json.dumps(a) + "\n" + json.dumps({**BLOCKED, "utt_id": "toy:0010", "audio_sha256": sha("toy-0010"),
                                                        "speaker_id": "toy:spk10", "session_id": None}) + "\n", encoding="utf-8")
    r = cli(str(inv))
    check("CLI: blocked inventory row is valid and counted as blocked",
          r.returncode == 0 and "1 blocked" in r.stdout, r.stdout + r.stderr)
    r = cli(str(inv), "--json")
    check("CLI --json: blocked_rows = 1", r.returncode == 0 and json.loads(r.stdout)["blocked_rows"] == 1, r.stdout)

for name, expect in (("toy_manifest_valid.jsonl", 0), ("toy_manifest_invalid.jsonl", 1)):
    r = subprocess.run([sys.executable, "-m", "asr_bench.validate", str(HERE / "examples" / name)],
                       capture_output=True, text=True, cwd=HERE.parent)
    check(f"CLI (-m): examples/{name} exits {expect}", r.returncode == expect, r.stdout + r.stderr)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
