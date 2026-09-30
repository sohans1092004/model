"""S4-S6 tests: normaliser, alignment, every Phase 2A §5 metric on hand-computed toy utterances,
speaker bootstrap and paired comparison. No audio, no model. Same check() style.

    python asr_bench/test_scoring_stats.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.align import align, counts
from asr_bench.scoring import (BenchmarkConfig, BenchmarkConfigError, failures, false_insertion_keywords,
                               keyword_recall_by_tag, ratio, score_utterance)
from asr_bench.stats import bootstrap_ci, paired_difference
from asr_bench.textnorm import english_number_words, normalise, word_script

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


CFG = BenchmarkConfig.load(HERE / "examples" / "toy_benchmark_config.json")


def row(uid, ref, *, spk="toy:s1", lang="hi", present=("hi", "en"), cs=True, tokens=None, dur=3.6, kw=None, tags=None):
    return {"utt_id": f"toy:{uid}", "speaker_id": spk, "duration_s": dur, "transcript_ref": ref, "language_primary": lang,
            "languages_present": list(present), "is_code_switched": cs, "tokens": tokens, "keyword_spans": kw,
            "safety_tags": tags}


def toks(words, langs):
    return [{"text": w, "lang": l, "script": None, "start_s": None, "end_s": None} for w, l in zip(words.split(), langs)]


def score(r, hyp, fi=()):
    return score_utterance(r, hyp, CFG, [list(k) for k in fi])


# --- normaliser / alignment ------------------------------------------------------------------------
check("normalise: lower-case, punctuation removed", normalise("Help me, mujhe koi attack kar raha hai!")[0] ==
      "help me mujhe koi attack kar raha hai".split())
check("normalise: apostrophe removed, English digits -> words", normalise("I don't need 2 cars", "en")[0] == "i dont need two cars".split())
w, left = normalise("मुझे 2 help", "hi")
check("normalise: Indic digits left as digits and counted (Q9)", w == ["मुझे", "2", "help"] and left == 1)
check("normalise: NFC (decomposed == composed)", normalise("क़")[0] == normalise("क़")[0])
check("number words", english_number_words(2105) == "two thousand one hundred five".split() and english_number_words(0) == ["zero"]
      and english_number_words(1_000_000) == ["one", "million"])
check("word_script", (word_script("help"), word_script("मुझे"), word_script("వదలండి"), word_script("123")) == ("Latn", "Deva", "Telu", None))
ops = align("a b c".split(), "a x c d".split())
check("alignment C S C I", [o for o, _, _ in ops] == ["C", "S", "C", "I"], ops)
check("alignment is deterministic", align(list("kitten"), list("sitting")) == align(list("kitten"), list("sitting")))
check("alignment of empty sides", counts(align([], ["a"]))["I"] == 1 and counts(align(["a"], []))["D"] == 1)

# --- WER / CER / S,D,I -------------------------------------------------------------------------------
ex = row(1, "Help me, mujhe koi attack kar raha hai", tokens=toks("help me mujhe koi attack kar raha hai", "en en hi hi en hi hi hi".split()))
s1 = score(ex, "help me attack")
check("WER = (S+D+I)/N: 5 deletions of 8", (s1["S"], s1["D"], s1["I"], s1["ref_words"]) == (0, 5, 0, 8)
      and ratio([s1], "wer")["value"] == 5 / 8)
check("deletion rate separate from insertion rate", ratio([s1], "deletion_rate")["value"] == 5 / 8 and ratio([s1], "insertion_rate")["value"] == 0)
c = score(row(2, "abc", present=["en"], cs=False, lang="en"), "abd")
check("CER on characters", ratio([c], "cer")["value"] == 1 / 3)

# --- language switch / English-word preservation / code-switch integrity ------------------------------
deva = row(3, "help me मुझे कोई attack कर रहा है", tokens=toks("help me मुझे कोई attack कर रहा है", "en en hi hi en hi hi hi".split()))
s3 = score(deva, "help me mujhe koi attack kar raha hai")
check("language-switch: Devanagari Hindi output as Latin words -> 5 of 8 changed",
      (s3["lang_switch_changed"], s3["lang_switch_n"]) == (5, 8), (s3["lang_switch_changed"], s3["lang_switch_n"]))
check("English-word preservation inside Hindi: help/me/attack kept", (s3["en_kept"], s3["en_words"]) == (3, 3))
check("code-switched integrity fails when a language's words are lost", s3["cs_eligible"] == 1 and s3["cs_ok"] == 0)
s3b = score(deva, "help me मुझे कोई attack कर रहा है")
check("perfect mixed-script output: no switches, integrity ok", s3b["lang_switch_changed"] == 0 and s3b["cs_ok"] == 1)
s1b = score(ex, "help me mujhe koi attack kar raha hai")
check("romanised Hindi reference: language undetermined by script, not counted as a switch (Q8)",
      s1b["lang_switch_changed"] == 0 and s1b["lang_switch_undetermined"] == 5)
drop = score(deva, "मुझे कोई कर रहा है")
check("English words dropped: preservation 0/3, integrity fails",
      (drop["en_kept"], drop["en_words"], drop["cs_ok"]) == (0, 3, 0))
bad_tokens = row(4, "help me now", tokens=toks("help me", ["en", "en"]))
check("tokens not matching the reference: tags unavailable, never guessed",
      score(bad_tokens, "help me now")["tags_available"] is False and score(bad_tokens, "help me now")["cs_eligible"] == 0)

# --- negation --------------------------------------------------------------------------------------
n1 = score(row(5, "mujhe help nahi chahiye", cs=False), "mujhe help chahiye")
check("negator dropped: preservation 0/1 and a polarity flip", (n1["neg_kept"], n1["neg_ref"], n1["neg_flip"]) == (0, 1, 1))
n2 = score(row(6, "I need help", lang="en", present=["en"], cs=False), "I don't need help")
check("negator inserted: polarity flip counted separately", (n2["neg_ref"], n2["neg_flip"]) == (0, 1))
n3 = score(row(7, "I don't need help", lang="en", present=["en"], cs=False), "I don't need help")
check("negation kept: no flip", (n3["neg_kept"], n3["neg_flip"]) == (1, 0))
check("flip rate over utterances with negation on either side", ratio([n1, n2, n3], "negation_polarity_flip_rate")["value"] == 2 / 3)

# --- safety keywords --------------------------------------------------------------------------------
kwr = row(8, "police ko call karo please", cs=False, kw=[{"text": "police", "start_s": 0, "end_s": 1},
                                                           {"text": "call", "start_s": 1, "end_s": 2}], tags=["safety_keyword"])
k1 = score(kwr, "please call karo")
check("keyword recall: 'call' found, 'police' missed", [k["found"] for k in k1["keywords"]] == [False, True]
      and ratio([k1], "safety_keyword_recall")["value"] == 0.5)
check("keyword recall per safety tag", keyword_recall_by_tag([k1])["safety_keyword"]["recall"] == 0.5)
harmless = row(9, "i will call you later", lang="en", present=["en"], cs=False, dur=36.0)
fi = [("help", "me"), ("police",)]
h = score(harmless, "i will call help me later", fi)
check("false keyword insertion on harmless audio: 1 in 0.01 h = 100/h",
      h["false_keywords"] == 1 and abs(ratio([h], "safety_keyword_false_insertions_per_hour")["value"] - 100) < 1e-9)
check("keywords already in the reference are not false insertions",
      score(row(10, "help me please", lang="en", present=["en"], cs=False), "help me please", fi)["false_keywords"] == 0)
check("false-insertion list defaults to the manifest's keyword spans (config null)",
      false_insertion_keywords([kwr], CFG) == [["call"], ["police"]])

# --- hallucination ---------------------------------------------------------------------------------
ns = score(row(11, "", lang="en", present=["en"], cs=False, dur=36.0), "Thanks for watching!")
check("words on no-speech audio per hour: 3 words in 0.01 h", abs(ratio([ns], "hallucinated_words_per_hour_no_speech")["value"] - 300) < 1e-9)
ir = score(row(12, "help", lang="en", present=["en"], cs=False, dur=36.0), "help thanks for watching")
check("insertion run >= 3 words on speech counted", ir["insertion_runs_ge3"] == 1)
check("failure list names each problem", "negation polarity flipped" in failures(n1) and any("missed keyword" in f for f in failures(k1))
      and any("no-speech" in f for f in failures(ns)))

# --- config validation -------------------------------------------------------------------------------
raw = copy.deepcopy(CFG.raw)
for name, change in (("romaniser set (Q6 not implemented)", {"romaniser": "iso15919"}),
                     ("unknown token-language method", {"token_language": {"method": "lid"}}),
                     ("bootstrap ci not 0.95", {"bootstrap": {"resamples": 10, "seed": 1, "ci": 0.9}}),
                     ("bad slice_by", {"slice_by": ["environment"]})):
    try:
        BenchmarkConfig.from_dict({**raw, **change})
        ok = False
    except BenchmarkConfigError:
        ok = True
    check(f"invalid benchmark config rejected: {name}", ok)
missing = {k: v for k, v in raw.items() if k != "negators"}
try:
    BenchmarkConfig.from_dict(missing)
    ok = False
except BenchmarkConfigError:
    ok = True
check("benchmark config has no defaults (missing key rejected)", ok)

# --- bootstrap / paired ----------------------------------------------------------------------------------
res = []
for spk in range(12):
    for k in range(3):
        r = row(f"b{spk}{k}", "one two three four", spk=f"toy:s{spk}", lang="en", present=["en"], cs=False)
        res.append(score(r, "one two three" if (spk + k) % 3 == 0 else "one two three four"))
b1 = bootstrap_ci(res, "wer", 1000, 7)
check("bootstrap deterministic for a seed", b1 == bootstrap_ci(res, "wer", 1000, 7))
check("bootstrap CI brackets the point estimate", b1["ci95"][0] <= b1["value"] <= b1["ci95"][1], b1)
check("bootstrap counts speakers (not utterances)", b1["speakers"] == 12 and b1["resamples_used"] == 1000)
b8 = bootstrap_ci(res, "wer", 1000, 8)
check("another seed also brackets the estimate", b8["ci95"][0] <= b8["value"] <= b8["ci95"][1])
one = [score(row("o", "a b", spk="toy:only", lang="en", present=["en"], cs=False), "a")]
check("single speaker: no interval claimed", bootstrap_ci(one, "wer", 1000, 7)["ci95"] is None)
nulls = [dict(r, speaker_id=None) for r in res[:4]]
check("null speakers become single-utterance clusters and are reported", bootstrap_ci(nulls, "wer", 100, 7)["unclustered_utterances"] == 4)
check("metric with zero denominator reports None", bootstrap_ci(res, "negation_preservation", 100, 7)["value"] is None)
worse = [dict(r, D=r["D"] + 1) for r in res]
pdiff = paired_difference(res, worse, "wer", 1000, 7)
check("paired difference B - A is positive when B is worse, CI excludes 0",
      pdiff["difference"] > 0 and pdiff["ci95"][0] > 0, pdiff)
check("paired comparison uses only shared utterances", paired_difference(res, worse[:30], "wer", 200, 7)["utterances"] == 30)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
