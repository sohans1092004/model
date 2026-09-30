"""Canonical manifest schema, UDK Phase 2A §3: one JSONL row per utterance, shared by every source.

Only what §3 states is enforced. Every field is present on every row; a field a source cannot
fill is null, never guessed (§3), so an absent key is an error, not an implicit null. Where §3
leaves something open (e.g. the element format of overlap_spans) it is left unchecked here and
listed in PENDING_DECISIONS.md.

validate_row() checks one row on its own. Checks that need the whole manifest (duplicate
utt_id; a speaker, session, recording or audio hash in two splits) are in validate.py. Whether
a valid row may be USED for a given split is a separate question, answered by eligibility.py.
Stdlib only (S1 adds no dependencies).

Adapter contract (not parsed here): speaker_id, session_id and recording_id must be globally
namespaced by the adapter that writes them, e.g. "<source>:<source_speaker_id>"
("mucs2021_hien:spk017"). The validator compares them as opaque strings, so two sources that
both emit a bare "spk1" would be reported as one speaker leaking across splits; no particular
prefix format is required or parsed.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Every §3 field, in the order §3 lists them. session_id and recording_id are kept as two
# fields: §3 lists "session_id / recording_id" and does not say whether they are one field
# or two (PENDING_DECISIONS.md, P-S1-1).
FIELDS = (
    "utt_id", "audio_path", "audio_sha256", "source_dataset", "source_version", "speaker_id",
    "session_id", "recording_id", "sample_rate_hz", "duration_s", "channels",
    "language_primary", "languages_present", "is_code_switched", "cmi",
    "transcript_ref", "transcript_romanised", "tokens", "script", "english_word_script",
    "provenance", "environment", "condition_device", "condition_real_or_synthetic",
    "aug_recipe", "seed", "snr_db", "clipping_ratio", "overlap", "overlap_spans",
    "overlap_rel_db", "safety_tags", "keyword_spans", "split", "licence", "use_restriction",
)

# §3 "Required: Yes" with no null clause: never null.
NEVER_NULL = (
    "utt_id", "audio_path", "audio_sha256", "source_dataset", "source_version",
    "sample_rate_hz", "duration_s", "channels", "language_primary", "languages_present",
    "is_code_switched", "transcript_ref", "script", "provenance", "environment",
    "condition_device", "condition_real_or_synthetic", "overlap", "split", "licence",
    "use_restriction",
)

ENGLISH_WORD_SCRIPT = ("latin", "transliterated", "mixed", "unknown")
# Exactly the Phase 2A §3 list. Phase 1 §15 also defines real_incident, which §3 does not list;
# that conflict is open (PENDING_DECISIONS.md, D-PROV-1), so real_incident is rejected for now.
# Until it is resolved, a KNOWN real incident must not be relabelled "unknown" to pass: "unknown"
# means provenance cannot be established, and is never equivalent to real_incident. Such data
# is held outside the manifest, and so outside all execution, until the owner decides.
PROVENANCE = ("read", "extempore", "conversational", "acted_scripted", "acted_semi_scripted",
              "spontaneous_safe", "unknown")
ENVIRONMENT = ("quiet", "traffic", "crowd", "home_tv", "transit", "office", "unknown")
CONDITION_DEVICE = ("close", "phone_hand", "pocket", "bag", "far_field", "phone_call", "unknown")
REAL_OR_SYNTHETIC = ("real", "synthetic")
SAFETY_TAGS = ("safety_keyword", "negation", "short_cry", "disfluency", "repetition", "intra_sentence_cs")
SPLITS = ("train", "dev", "test", "final_test", "eval_only")
USE_RESTRICTION = ("train_ok", "eval_only", "blocked")  # from Phase 1 §20

# §6.1 / §7: "no null speaker_id in speaker-disjoint splits". eval_only is not one of them:
# it is where §3's "null only if source has none -> excluded from speaker-disjoint sets"
# rows go. The cross-split checks in validate.py still cover all five splits.
SPEAKER_DISJOINT_SPLITS = ("train", "dev", "test", "final_test")

# Splits that are executed by the benchmark or training. A use_restriction=blocked row may never
# be in one of these. §3 has no "unassigned" split value, so a blocked row that is kept in the
# manifest as inventory/provenance must carry split="eval_only"; the split value alone never
# makes it usable -- use_restriction does (eligibility.py; PENDING_DECISIONS.md, P-S1-6).
EXECUTED_SPLITS = ("train", "dev", "test", "final_test")

TOKEN_KEYS = ("text", "lang", "script", "start_s", "end_s")
KEYWORD_SPAN_KEYS = ("text", "start_s", "end_s")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# Well-formedness only (language subtag, then optional script/region/variant subtags);
# BCP-47 registry lookup would need a dependency.
_BCP47 = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
_SCRIPT = re.compile(r"^[A-Z][a-z]{3}$")  # ISO 15924, e.g. Deva, Telu, Latn
_TIME_SLACK_S = 0.01  # a span ending this far past duration_s is rounding, not an error


@dataclass(frozen=True)
class Issue:
    level: str  # "error" fails validation; "warning" is reported only
    field: str | None
    message: str
    line: int | None = None
    utt_id: str | None = None

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line is not None else "manifest"
        who = f" [{self.utt_id}]" if self.utt_id else ""
        what = f" {self.field}:" if self.field else ""
        return f"{self.level.upper()} {where}{who}{what} {self.message}"


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _lang(tag: str) -> str:
    return tag.split("-", 1)[0]


def validate_row(row, line: int | None = None, indic_languages: frozenset[str] | None = None) -> list[Issue]:
    """All single-row §3 rules. Returns [] for a valid row.

    indic_languages: §3 requires english_word_script "for Indic sources", but the manifest has
    no field saying which languages count as Indic. That grouping is benchmark configuration,
    not a schema rule: pass the configured language subtags here (e.g. {"hi", "te"}) to enforce
    it; None (default) leaves english_word_script nullable on every row (P-S1-4)."""
    issues: list[Issue] = []
    if not isinstance(row, dict):
        return [Issue("error", None, f"row must be a JSON object, got {type(row).__name__}", line)]
    uid = row.get("utt_id") if isinstance(row.get("utt_id"), str) else None

    def err(field, msg):
        issues.append(Issue("error", field, msg, line, uid))

    def warn(field, msg):
        issues.append(Issue("warning", field, msg, line, uid))

    for f in FIELDS:
        if f not in row:
            err(f, "missing (a field the source cannot fill must be present as null, §3)")
    for f in sorted(set(row) - set(FIELDS)):
        # Phase 1 §15 safety fields (pair_id, problem_type, roles...) may ride along (§3).
        warn(f, "not a Phase 2A §3 field; kept, not validated")
    for f in NEVER_NULL:
        if f in row and row[f] is None:
            err(f, "required, must not be null")
    v = {f: row.get(f) for f in FIELDS}

    # --- identity, audio, source ------------------------------------------------------
    if v["utt_id"] is not None:
        head, sep, tail = v["utt_id"].partition(":") if isinstance(v["utt_id"], str) else ("", "", "")
        if not (sep and head.strip() and tail.strip()):
            err("utt_id", f"must be '<source>:<source_id>', got {v['utt_id']!r}")
    for f in ("audio_path", "source_dataset", "source_version"):
        if v[f] is not None and not _is_text(v[f]):
            err(f, "must be a non-empty string")
    if v["audio_sha256"] is not None and not (isinstance(v["audio_sha256"], str) and _SHA256.match(v["audio_sha256"])):
        err("audio_sha256", "must be 64 lower-case hex characters (SHA-256)")
    for f in ("speaker_id", "session_id", "recording_id"):
        if v[f] is not None and not _is_text(v[f]):
            err(f, "must be a non-empty string or null")
    if v["speaker_id"] is None and v["split"] in SPEAKER_DISJOINT_SPLITS:
        err("speaker_id", f"null speaker_id is not allowed in speaker-disjoint split {v['split']!r} "
                          "(§3: excluded from speaker-disjoint sets; use split 'eval_only')")

    # --- audio format -------------------------------------------------------------------
    if v["sample_rate_hz"] is not None and not (_is_int(v["sample_rate_hz"]) and v["sample_rate_hz"] > 0):
        err("sample_rate_hz", "must be a positive integer (the original rate, §3)")
    if v["channels"] is not None and not (_is_int(v["channels"]) and v["channels"] >= 1):
        err("channels", "must be an integer >= 1")
    duration = v["duration_s"] if _is_num(v["duration_s"]) else None
    if v["duration_s"] is not None and not (duration is not None and duration > 0):
        err("duration_s", "must be a finite number > 0")
        duration = None

    # --- language / code-switching --------------------------------------------------------
    if v["language_primary"] is not None and not (isinstance(v["language_primary"], str) and _BCP47.match(v["language_primary"])):
        err("language_primary", f"must be a BCP-47 tag (e.g. hi, te, en-IN), got {v['language_primary']!r}")
    present_ok = False
    if v["languages_present"] is not None:
        lp = v["languages_present"]
        if not (isinstance(lp, list) and lp):
            err("languages_present", "must be a non-empty list of BCP-47 tags")
        elif not all(isinstance(t, str) and _BCP47.match(t) for t in lp):
            err("languages_present", f"every entry must be a BCP-47 tag, got {lp!r}")
        elif len(set(lp)) != len(lp):
            err("languages_present", f"duplicate entries in {lp!r}")
        else:
            present_ok = True
    if present_ok and isinstance(v["language_primary"], str) and _BCP47.match(v["language_primary"]):
        if _lang(v["language_primary"]) not in {_lang(t) for t in v["languages_present"]}:
            warn("language_primary", f"{v['language_primary']!r} is not among languages_present {v['languages_present']!r}")
    if v["is_code_switched"] is not None and not isinstance(v["is_code_switched"], bool):
        err("is_code_switched", "must be true or false")
    elif isinstance(v["is_code_switched"], bool) and present_ok:
        n_langs = len({_lang(t) for t in v["languages_present"]})
        if v["is_code_switched"] and n_langs < 2:
            warn("is_code_switched", "true, but languages_present names fewer than 2 languages")
        if not v["is_code_switched"] and n_langs >= 2:
            warn("is_code_switched", "false, but languages_present names 2 or more languages")

    # --- transcripts and tokens ---------------------------------------------------------
    # transcript_ref may be "" (a segment with no reference speech, for §5 hallucination rate),
    # never null.
    if v["transcript_ref"] is not None and not isinstance(v["transcript_ref"], str):
        err("transcript_ref", "must be a string")
    if v["transcript_romanised"] is not None and not isinstance(v["transcript_romanised"], str):
        err("transcript_romanised", "must be a string or null")
    tags_exist = False
    if v["tokens"] is not None:
        toks = v["tokens"]
        if not isinstance(toks, list) or not toks:
            err("tokens", "must be a non-empty list of {text, lang, script, start_s, end_s}, or null")
        else:
            ok = True
            for i, t in enumerate(toks):
                label = f"tokens[{i}]"
                if not isinstance(t, dict):
                    err(label, "must be an object"); ok = False; continue
                missing = [k for k in TOKEN_KEYS if k not in t]
                if missing:
                    err(label, f"missing {missing} (unknown values are null)"); ok = False
                if not _is_text(t.get("text")):
                    err(label, "text must be a non-empty string"); ok = False
                if t.get("lang") is not None and not (isinstance(t["lang"], str) and _BCP47.match(t["lang"])):
                    err(label, f"lang must be a BCP-47 tag or null, got {t.get('lang')!r}"); ok = False
                if t.get("script") is not None and not (isinstance(t["script"], str) and (_SCRIPT.match(t["script"]) or t["script"] == "mixed")):
                    err(label, f"script must be an ISO 15924 code or 'mixed', got {t.get('script')!r}"); ok = False
                _check_times(t.get("start_s"), t.get("end_s"), label, duration, err, warn, nullable=True)
            tags_exist = ok and all(t.get("lang") is not None for t in toks)
    # "cmi: Yes, number if tags exist" -- required once every token carries a language tag.
    # Scale and definition are not given in §3 and are not assumed here (0-1 and 0-100 both
    # pass, nothing is normalised); they must be recorded with the source / benchmark
    # configuration (P-S1-8).
    if v["cmi"] is not None and not _is_num(v["cmi"]):
        err("cmi", "must be a finite number or null")
    if tags_exist and v["cmi"] is None:
        err("cmi", "required: every token has a language tag, so the Code-Mixing Index must be given (§3)")
    if v["script"] is not None and not (isinstance(v["script"], str) and (_SCRIPT.match(v["script"]) or v["script"] == "mixed")):
        err("script", f"must be an ISO 15924 code (Deva, Telu, Latn...) or 'mixed', got {v['script']!r}")
    if v["english_word_script"] is not None and v["english_word_script"] not in ENGLISH_WORD_SCRIPT:
        err("english_word_script", f"must be one of {ENGLISH_WORD_SCRIPT}, got {v['english_word_script']!r}")
    if (indic_languages is not None and present_ok and v["english_word_script"] is None
            and {_lang(t) for t in v["languages_present"]} & set(indic_languages)):
        err("english_word_script", "required for Indic speech (§3; configured Indic languages "
                                   f"{sorted(indic_languages)}); use 'unknown' if not yet checked")

    # --- provenance and conditions ------------------------------------------------------
    for f, allowed in (("provenance", PROVENANCE), ("environment", ENVIRONMENT),
                       ("condition_device", CONDITION_DEVICE),
                       ("condition_real_or_synthetic", REAL_OR_SYNTHETIC)):
        if v[f] is not None and v[f] not in allowed:
            err(f, f"must be one of {allowed}, got {v[f]!r}")
    if v["condition_real_or_synthetic"] == "synthetic":
        if not _is_text(v["aug_recipe"]):
            err("aug_recipe", "required for synthetic rows (§3: synthetic rows name aug_recipe + seed)")
        if not _is_int(v["seed"]):
            err("seed", "required for synthetic rows, as an integer (§3)")
    elif v["condition_real_or_synthetic"] == "real":
        for f in ("aug_recipe", "seed"):
            if v[f] is not None:
                err(f, "must be null on a real row (only synthetic rows carry an augmentation recipe)")
    if v["snr_db"] is not None and not _is_num(v["snr_db"]):
        err("snr_db", "must be a finite number or null")
    if v["clipping_ratio"] is not None and not (_is_num(v["clipping_ratio"]) and 0 <= v["clipping_ratio"] <= 1):
        err("clipping_ratio", "must be a number in [0, 1] or null")

    # --- overlap ------------------------------------------------------------------------
    if v["overlap"] is not None and not isinstance(v["overlap"], bool):
        err("overlap", "must be true or false")
    if v["overlap"] is True:
        # Span element format is not given in §3 (P-S1-3): only list-ness is checked.
        if not (isinstance(v["overlap_spans"], list) and v["overlap_spans"]):
            err("overlap_spans", "required when overlap is true: a non-empty list")
        if not _is_num(v["overlap_rel_db"]):
            err("overlap_rel_db", "required when overlap is true: other-speaker level relative to target, in dB")
    elif v["overlap"] is False:
        if v["overlap_spans"] not in (None, []):
            err("overlap_spans", "must be null (or empty) when overlap is false")
        if v["overlap_rel_db"] is not None:
            err("overlap_rel_db", "must be null when overlap is false")

    # --- safety tags and keyword spans --------------------------------------------------
    tags = v["safety_tags"]
    if tags is not None:
        if not isinstance(tags, list):
            err("safety_tags", "must be a list or null")
            tags = None
        else:
            bad = [t for t in tags if t not in SAFETY_TAGS]
            if bad:
                err("safety_tags", f"unknown tag(s) {bad}; allowed {SAFETY_TAGS}")
    if tags and v["keyword_spans"] is None:
        err("keyword_spans", "required when safety_tags is set (§3: 'If safety_tags'); use [] if the item has none")
    if v["keyword_spans"] is not None:
        if not isinstance(v["keyword_spans"], list):
            err("keyword_spans", "must be a list of {text, start_s, end_s} or null")
        else:
            for i, s in enumerate(v["keyword_spans"]):
                label = f"keyword_spans[{i}]"
                if not isinstance(s, dict):
                    err(label, "must be an object"); continue
                missing = [k for k in KEYWORD_SPAN_KEYS if k not in s]
                if missing:
                    err(label, f"missing {missing}")
                if not _is_text(s.get("text")):
                    err(label, "text must be a non-empty string")
                _check_times(s.get("start_s"), s.get("end_s"), label, duration, err, warn, nullable=False)

    # --- split, licence, use restriction ------------------------------------------------
    if v["split"] is not None and v["split"] not in SPLITS:
        err("split", f"must be one of {SPLITS}, got {v['split']!r}")
    if v["licence"] is not None and not _is_text(v["licence"]):
        err("licence", "must be a non-empty string")
    if v["use_restriction"] is not None and v["use_restriction"] not in USE_RESTRICTION:
        err("use_restriction", f"must be one of {USE_RESTRICTION}, got {v['use_restriction']!r}")
    if v["use_restriction"] == "blocked" and v["split"] in EXECUTED_SPLITS:
        err("use_restriction", f"blocked (Phase 1 §20: licence/legal not cleared) data may not be in executed split "
                               f"{v['split']!r}; keep it as inventory with split 'eval_only'")
    elif v["use_restriction"] == "eval_only" and v["split"] == "train":
        err("use_restriction", "eval_only data may not be in split 'train'")
    return issues


def _check_times(start, end, label, duration, err, warn, nullable: bool) -> None:
    for name, t in (("start_s", start), ("end_s", end)):
        if t is None:
            if not nullable:
                err(label, f"{name} must be a number")
        elif not (_is_num(t) and t >= 0):
            err(label, f"{name} must be a finite number >= 0" + (" or null" if nullable else ""))
    if _is_num(start) and _is_num(end):
        if start > end:
            err(label, f"start_s {start} is after end_s {end}")
        elif duration is not None and end > duration + _TIME_SLACK_S:
            warn(label, f"end_s {end} is past duration_s {duration}")
