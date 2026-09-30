"""Phase 2A §5 metrics (stages S4 + S5): per-utterance scoring and ratio-of-sums aggregation.

Every metric is a ratio sum(num) / sum(den) over utterances, so stats.py can bootstrap any of
them by resampling speakers. Per-utterance results are kept for failure listings (§5).

Configuration (BenchmarkConfig, JSON "asr_bench.benchmark_config/1") carries everything §6.3
says must be fixed on dev before the final run. Items still open are PROVISIONAL and every
report says so: token-language method (Q8), negator/stop-word lists (Q7), romaniser (Q6, none
-> romanised metrics and transliteration-equivalence are reported unavailable), Indic number
words (Q9), slice definition (N-7), robustness-subset mapping (M-1).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from asr_bench.align import align, counts
from asr_bench.textnorm import NORMALISER_VERSION, normalise, word_script

CONFIG_FORMAT = "asr_bench.benchmark_config/1"


class BenchmarkConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkConfig:
    raw: dict
    sha256: str

    @classmethod
    def from_dict(cls, raw) -> BenchmarkConfig:
        if not isinstance(raw, dict) or raw.get("format") != CONFIG_FORMAT:
            raise BenchmarkConfigError(f"format must be {CONFIG_FORMAT!r}")
        need = ("provisional", "token_language", "negators", "stopwords", "false_insertion_keywords", "romaniser",
                "slice_by", "bootstrap", "slice_minimums", "open_decisions")
        missing = [k for k in need if k not in raw]
        if missing:
            raise BenchmarkConfigError(f"missing {missing} (no defaults: every item is explicit configuration)")
        tl = raw["token_language"]
        if not (isinstance(tl, dict) and tl.get("method") == "script" and isinstance(tl.get("script_language"), dict)):
            raise BenchmarkConfigError("token_language: only {'method': 'script', 'script_language': {...}} is implemented (Q8)")
        if raw["romaniser"] is not None:
            raise BenchmarkConfigError("romaniser: none is implemented (Q6); use null")
        for k in ("negators", "stopwords"):
            if not isinstance(raw[k], dict) or not all(isinstance(v, list) for v in raw[k].values()):
                raise BenchmarkConfigError(f"{k} must map language -> list of words")
        if raw["false_insertion_keywords"] is not None and not isinstance(raw["false_insertion_keywords"], list):
            raise BenchmarkConfigError("false_insertion_keywords must be a list or null (null = keyword spans in the manifest)")
        if not (isinstance(raw["slice_by"], list) and set(raw["slice_by"]) <= {"language_primary", "is_code_switched"} and raw["slice_by"]):
            raise BenchmarkConfigError("slice_by must be a non-empty subset of ['language_primary', 'is_code_switched']")
        b = raw["bootstrap"]
        if not (isinstance(b, dict) and isinstance(b.get("resamples"), int) and b["resamples"] > 0
                and isinstance(b.get("seed"), int) and b.get("ci") == 0.95):
            raise BenchmarkConfigError("bootstrap needs integer resamples > 0, integer seed and ci 0.95 (§6.4)")
        return cls(raw, hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest())

    @classmethod
    def load(cls, path) -> BenchmarkConfig:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def negators(self) -> set:
        return {w for ws in self.raw["negators"].values() for w in normalise(" ".join(ws))[0]}

    def stopwords(self, lang: str) -> set:
        return set(normalise(" ".join(self.raw["stopwords"].get(lang.split("-")[0], [])))[0])

    def hyp_language(self, word: str) -> str | None:
        return self.raw["token_language"]["script_language"].get(word_script(word))


def _lang(tag) -> str | None:
    return tag.split("-")[0] if isinstance(tag, str) else None


def _ref_word_tags(row: dict, ref_words: list[str]) -> list[str | None] | None:
    """Language tag per normalised reference word, from the manifest tokens; None if the tokens
    do not normalise to exactly the reference words (reported as untagged, never guessed)."""
    toks = row.get("tokens")
    if not toks:
        return None
    words, tags = [], []
    for t in toks:
        w, _ = normalise(t.get("text", ""), row.get("language_primary"))
        words += w
        tags += [_lang(t.get("lang"))] * len(w)
    return tags if words == ref_words else None


def _count_phrase(words: list[str], phrase: list[str]) -> int:
    n = len(phrase)
    return sum(1 for i in range(len(words) - n + 1) if n and words[i:i + n] == phrase) if n else 0


def score_utterance(row: dict, hyp_text: str, cfg: BenchmarkConfig, fi_keywords: list[list[str]]) -> dict:
    lang = row.get("language_primary")
    ref, ref_left = normalise(row.get("transcript_ref", ""), lang)
    hyp, hyp_left = normalise(hyp_text, lang)
    ops = align(ref, hyp)
    c = counts(ops)
    ref_chars, hyp_chars = list(" ".join(ref)), list(" ".join(hyp))
    cc = counts(align(ref_chars, hyp_chars))
    hours = (row.get("duration_s") or 0) / 3600.0
    res = {"utt_id": row["utt_id"], "speaker_id": row.get("speaker_id"), "hours": hours,
           "ref_words": len(ref), "hyp_words": len(hyp), "S": c["S"], "D": c["D"], "I": c["I"],
           "ref_chars": len(ref_chars), "char_edits": cc["S"] + cc["D"] + cc["I"],
           "numbers_left_as_digits": ref_left + hyp_left, "no_speech": len(ref) == 0}

    # hallucination (§5): words output on no-speech segments; insertion runs of >= 3 words on speech
    runs, run = 0, 0
    for op, _, _ in ops + [("C", None, None)]:
        if op == "I":
            run += 1
        else:
            runs += run >= 3
            run = 0
    res["insertion_runs_ge3"] = runs if ref else 0

    hyp_of = {ri: hj for op, ri, hj in ops if op in "CS"}
    kept = {ri for op, ri, _ in ops if op == "C"}
    tags = _ref_word_tags(row, ref)
    res["tags_available"] = tags is not None

    # language-switch error: aligned tagged reference words whose output word is in another language
    ls_n = ls_changed = ls_undetermined = 0
    if tags:
        for ri, hj in hyp_of.items():
            if tags[ri] is None:
                continue
            hl = cfg.hyp_language(hyp[hj])
            # the script method can only judge words whose REFERENCE script identifies their tagged
            # language (e.g. Devanagari Hindi); a romanised Hindi reference word is undetermined
            if hl is None or cfg.hyp_language(ref[ri]) != tags[ri]:
                ls_undetermined += 1
                continue
            ls_n += 1
            ls_changed += hl != tags[ri]
    res.update(lang_switch_n=ls_n, lang_switch_changed=ls_changed, lang_switch_undetermined=ls_undetermined)

    # English-word preservation inside Indic utterances (exact word; transliteration equivalence
    # needs a romaniser, Q6)
    indic = any(_lang(t) != "en" for t in (row.get("languages_present") or []))
    en_idx = [i for i, t in enumerate(tags or []) if t == "en"] if indic else []
    res.update(en_words=len(en_idx), en_kept=sum(1 for i in en_idx if i in kept))

    # negation: reference negators kept; polarity flips (negation present in one side only)
    negs = cfg.negators()
    ref_neg = [i for i, w in enumerate(ref) if w in negs]
    hyp_has = any(w in negs for w in hyp)
    res.update(neg_ref=len(ref_neg), neg_kept=sum(1 for i in ref_neg if i in kept),
               neg_polarity_utt=int(bool(ref_neg) or hyp_has), neg_flip=int(bool(ref_neg) != hyp_has))

    # safety keywords: recall of keyword_spans (exact contiguous phrase in the output)
    kws = []
    for span in row.get("keyword_spans") or []:
        k, _ = normalise(span.get("text", ""), lang)
        kws.append({"text": " ".join(k), "found": _count_phrase(hyp, k) > 0})
    res["keywords"] = kws
    res["safety_tags"] = list(row.get("safety_tags") or [])
    harmless = not (row.get("keyword_spans") or [])
    res["harmless_hours"] = hours if harmless else 0.0
    res["false_keywords"] = (sum(max(0, _count_phrase(hyp, k) - _count_phrase(ref, k)) for k in fi_keywords)
                             if harmless else 0)

    # code-switched utterance integrity: every content word of every language kept, no language span dropped
    res["cs_eligible"] = int(bool(row.get("is_code_switched")) and bool(tags))
    ok = None
    if res["cs_eligible"]:
        content = [i for i, w in enumerate(ref) if w not in cfg.stopwords(tags[i] or "")]
        spans, start = [], 0
        for i in range(1, len(ref) + 1):
            if i == len(ref) or tags[i] != tags[start]:
                spans.append(range(start, i))
                start = i
        ok = all(i in kept for i in content) and all(any(i in kept for i in s) for s in spans)
    res["cs_ok"] = int(bool(ok))
    res["romanised"] = None  # Q6: no romaniser -> the romanised copy of every metric is unavailable
    return res


def false_insertion_keywords(rows: list[dict], cfg: BenchmarkConfig) -> list[list[str]]:
    listed = cfg.raw["false_insertion_keywords"]
    phrases = listed if listed is not None else sorted({s.get("text", "") for r in rows for s in (r.get("keyword_spans") or [])})
    out = sorted({tuple(normalise(p)[0]) for p in phrases if normalise(p)[0]})
    return [list(p) for p in out]


# name -> (numerator, denominator, scale); every §5 metric
METRICS = {
    "wer": (lambda r: r["S"] + r["D"] + r["I"], lambda r: r["ref_words"], 1),
    "cer": (lambda r: r["char_edits"], lambda r: r["ref_chars"], 1),
    "substitution_rate": (lambda r: r["S"], lambda r: r["ref_words"], 1),
    "deletion_rate": (lambda r: r["D"], lambda r: r["ref_words"], 1),
    "insertion_rate": (lambda r: r["I"], lambda r: r["ref_words"], 1),
    "hallucinated_words_per_hour_no_speech": (lambda r: r["hyp_words"] if r["no_speech"] else 0,
                                              lambda r: r["hours"] if r["no_speech"] else 0, 1),
    "insertion_runs_ge3_per_hour_speech": (lambda r: r["insertion_runs_ge3"], lambda r: 0 if r["no_speech"] else r["hours"], 1),
    "language_switch_error_rate": (lambda r: r["lang_switch_changed"], lambda r: r["lang_switch_n"], 1),
    "english_word_preservation": (lambda r: r["en_kept"], lambda r: r["en_words"], 1),
    "negation_preservation": (lambda r: r["neg_kept"], lambda r: r["neg_ref"], 1),
    "negation_polarity_flip_rate": (lambda r: r["neg_flip"], lambda r: r["neg_polarity_utt"], 1),
    "safety_keyword_recall": (lambda r: sum(k["found"] for k in r["keywords"]), lambda r: len(r["keywords"]), 1),
    "safety_keyword_false_insertions_per_hour": (lambda r: r["false_keywords"], lambda r: r["harmless_hours"], 1),
    "code_switched_utterance_integrity": (lambda r: r["cs_ok"], lambda r: r["cs_eligible"], 1),
}


def ratio(results: list[dict], metric: str) -> dict:
    num_f, den_f, _ = METRICS[metric]
    num = sum(num_f(r) for r in results)
    den = sum(den_f(r) for r in results)
    return {"value": (num / den) if den else None, "num": num, "den": den}


def keyword_recall_by_tag(results: list[dict]) -> dict:
    out = {}
    for r in results:
        for tag in r["safety_tags"] or ["(untagged)"]:
            d = out.setdefault(tag, {"found": 0, "total": 0})
            d["found"] += sum(k["found"] for k in r["keywords"])
            d["total"] += len(r["keywords"])
    return {t: {**v, "recall": v["found"] / v["total"] if v["total"] else None} for t, v in sorted(out.items())}


def failures(r: dict) -> list[str]:
    f = [f"missed keyword '{k['text']}'" for k in r["keywords"] if not k["found"]]
    if r["neg_flip"]:
        f.append("negation polarity flipped")
    if r["cs_eligible"] and not r["cs_ok"]:
        f.append("code-switched utterance not intact")
    if r["lang_switch_changed"]:
        f.append(f"{r['lang_switch_changed']} word(s) rendered in another language")
    if r["no_speech"] and r["hyp_words"]:
        f.append(f"{r['hyp_words']} word(s) output on no-speech audio")
    if r["insertion_runs_ge3"]:
        f.append("insertion run >= 3 words")
    return f


def finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


__all__ = ["BenchmarkConfig", "METRICS", "NORMALISER_VERSION", "score_utterance", "ratio", "failures"]
