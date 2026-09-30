"""Transcript representation contract (Phase 2B input; Phase 2A §3/§5/§9, Phase 1 §8).

One TranscriptRepr = one complete utterance, never split by language (2A §4: scored as one
utterance). It carries BOTH candidate formats named in 2A §9 without choosing between them:
  - text_mixed:      the utterance as produced, each word in its own script (always present);
  - text_romanised:  optional single-script copy, only with the name of the romaniser that made it
                     (Q6 open: none exists yet, so builders leave it None).
Tokens carry text, language, script, start/end times where available, each with where it came
from (lang_source / script measured from the characters / times only if the engine or manifest gave
them). Engine, version, input unit and provenance are recorded. Nothing is inferred beyond that.

  from_run_record(rec, cfg)  -- an ASR output (runner.py record); token language by the configured
                                provisional method (Q8), times None (the engines expose none here).
  from_manifest_row(row)     -- the reference (manifest tokens when they match the reference words).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from asr_bench.textnorm import word_script

REPR_FORMAT = "asr_bench.transcript_repr/1"
SOURCES = ("asr_output", "reference")


class ReprError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    text: str
    lang: str | None = None
    lang_source: str | None = None  # "manifest", "script-method (provisional, Q8)", or None
    script: str | None = None  # ISO 15924, measured from the token's characters
    start_s: float | None = None
    end_s: float | None = None


@dataclass(frozen=True)
class TranscriptRepr:
    utt_id: str | None
    source: str  # asr_output | reference
    text_mixed: str
    tokens: tuple[Token, ...] | None
    engine: str | None
    model_version: str | None
    input_unit: str | None
    provenance: dict = field(default_factory=dict)
    text_romanised: str | None = None
    romaniser: str | None = None
    format: str = REPR_FORMAT

    def __post_init__(self):
        validate(self)

    def views(self) -> dict:
        """Every representation this record actually holds (no choice is made here)."""
        v = {"mixed_script": self.text_mixed}
        if self.text_romanised is not None:
            v[f"romanised:{self.romaniser}"] = self.text_romanised
        return v

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tokens"] = None if self.tokens is None else [asdict(t) for t in self.tokens]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> TranscriptRepr:
        if d.get("format") != REPR_FORMAT:
            raise ReprError(f"format must be {REPR_FORMAT!r}")
        toks = None if d.get("tokens") is None else tuple(Token(**t) for t in d["tokens"])
        return cls(**{**d, "tokens": toks})


def validate(r: TranscriptRepr) -> None:
    if r.source not in SOURCES:
        raise ReprError(f"source must be one of {SOURCES}")
    if not isinstance(r.text_mixed, str):
        raise ReprError("text_mixed must be a string (\"\" for no output)")
    if (r.text_romanised is None) != (r.romaniser is None):
        raise ReprError("a romanised copy must name the romaniser that produced it (and only then)")
    if r.source == "asr_output" and not (r.engine and r.model_version):
        raise ReprError("an ASR output must record engine and model_version")
    if r.tokens is not None:
        # complete utterance: the tokens are exactly the words of text_mixed, in order, none dropped
        if [t.text for t in r.tokens] != r.text_mixed.split():
            raise ReprError("tokens must reproduce every word of text_mixed, in order")
        for t in r.tokens:
            if (t.lang is None) != (t.lang_source is None):
                raise ReprError(f"token {t.text!r}: a language needs its lang_source, and only then")
            if t.start_s is not None and t.end_s is not None and t.start_s > t.end_s:
                raise ReprError(f"token {t.text!r}: start_s after end_s")


def _tokens_from_words(words: list[str], lang_of) -> tuple[Token, ...]:
    out = []
    for w in words:
        lang, src = lang_of(w)
        out.append(Token(text=w, lang=lang, lang_source=src if lang else None, script=word_script(w)))
    return tuple(out)


def from_run_record(rec: dict, cfg=None, provenance: dict | None = None) -> TranscriptRepr:
    """ASR output -> representation. `cfg` (scoring.BenchmarkConfig) supplies the provisional
    token-language method; without it token languages stay None."""
    if "error" in rec or "hyp" not in rec:
        raise ReprError(f"{rec.get('utt_id')}: run record has no transcript ({rec.get('error', 'missing hyp')})")
    words = rec["hyp"].split()

    def lang_of(w):
        return (cfg.hyp_language(w), "script-method (provisional, Q8)") if cfg is not None else (None, None)

    return TranscriptRepr(utt_id=rec["utt_id"], source="asr_output", text_mixed=" ".join(words),
                          tokens=_tokens_from_words(words, lang_of), engine=rec.get("engine"),
                          model_version=rec.get("model_version"), input_unit=rec.get("input_unit"),
                          provenance={"split": rec.get("split"), **(provenance or {})})


def from_manifest_row(row: dict) -> TranscriptRepr:
    """Reference transcript -> representation. Manifest token tags are used only when the manifest
    tokens are exactly the reference words; otherwise tokens carry script only."""
    words = (row.get("transcript_ref") or "").split()
    mt = row.get("tokens")
    if mt and [t.get("text") for t in mt] == words:
        toks = tuple(Token(text=t["text"], lang=t.get("lang"), lang_source="manifest" if t.get("lang") else None,
                           script=t.get("script") or word_script(t["text"]), start_s=t.get("start_s"), end_s=t.get("end_s"))
                     for t in mt)
    else:
        toks = _tokens_from_words(words, lambda w: (None, None))
    rom = row.get("transcript_romanised")
    return TranscriptRepr(utt_id=row["utt_id"], source="reference", text_mixed=" ".join(words), tokens=toks,
                          engine=None, model_version=None, input_unit=None,
                          provenance={"source_dataset": row.get("source_dataset"), "source_version": row.get("source_version"),
                                      "provenance": row.get("provenance"), "split": row.get("split")},
                          text_romanised=rom, romaniser="manifest (source-provided)" if rom is not None else None)
