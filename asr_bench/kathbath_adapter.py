"""Kathbath adapter (first real Phase 2A source). Registry id `kathbath`.

Documented facts only (Phase 2A §2, Phase 1 §3/§20/§23): read speech, native-script transcripts,
speaker in the file names, language per folder, .m4a audio, "Verified usable (CC0 packaging)",
Train + Eval. Everything the documents do NOT give -- directory layout, transcript file format,
the speaker pattern inside file names, folder -> language names, the release/version -- comes from
a LAYOUT SPEC written after inspecting the real package (template: configs/kathbath_layout.TEMPLATE.json).
A spec with any null field is refused: nothing about the package is guessed.

Per row:
  - audio_path = the ORIGINAL .m4a (relative to the Kathbath root); audio_sha256 = its exact bytes;
    duration = decoded samples (PyAV) -- owner decisions N-1 / P-S2-1 for Kathbath.
  - speaker_id = "kathbath:<speaker from file name>"; session_id / recording_id = None (none documented).
  - language_primary from the folder via the spec's language_map; languages_present = [that language];
    is_code_switched = False (Kathbath is not a code-switched source in Phase 1 §7-§8, K-2).
  - script MEASURED from the transcript's letters; english_word_script = "unknown" (not documented).
  - provenance "read"; environment / condition_device "unknown"; real; no tokens, CMI, overlap,
    safety tags or keyword spans (none supplied).
The registry gate is enforced by build_row / build_rows / ingest as for every source.
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from asr_bench.adapters import DatasetAdapter, SourceInfo, SourceUtterance
from asr_bench.textnorm import word_script

LAYOUT_FORMAT = "asr_bench.kathbath_layout/1"
SOURCE_ID = "kathbath"
LICENCE = "Verified usable (CC0 packaging)"  # must equal the registry entry
USE_RESTRICTION = "train_ok"
REQUIRED = ("source_version", "inspected_from", "audio_glob", "language_path_index", "language_map", "speaker_regex",
            "transcripts")
TRANSCRIPT_REQUIRED = ("glob", "format", "key", "id_field", "text_field")


class LayoutError(ValueError):
    pass


def load_layout(raw) -> dict:
    if not isinstance(raw, dict) or raw.get("format") != LAYOUT_FORMAT:
        raise LayoutError(f"layout spec format must be {LAYOUT_FORMAT!r}")
    nulls = [k for k in REQUIRED if raw.get(k) in (None, "", {})]
    if nulls:
        raise LayoutError(f"layout spec fields not filled from the real package: {nulls}")
    t = raw["transcripts"]
    tn = [k for k in TRANSCRIPT_REQUIRED if not isinstance(t, dict) or t.get(k) in (None, "")]
    if tn:
        raise LayoutError(f"transcripts spec fields not filled: {tn}")
    if t["format"] not in ("tsv", "csv", "jsonl"):
        raise LayoutError("transcripts.format must be tsv, csv or jsonl")
    if t["key"] not in ("stem", "relpath"):
        raise LayoutError("transcripts.key must be 'stem' (file name without extension) or 'relpath'")
    rx = re.compile(raw["speaker_regex"])
    if "speaker" not in rx.groupindex:
        raise LayoutError("speaker_regex needs a named group (?P<speaker>...)")
    if not isinstance(raw["language_path_index"], int):
        raise LayoutError("language_path_index must be an integer")
    return {**raw, "_speaker_rx": rx}


def _read_transcripts(root: Path, t: dict) -> dict:
    out = {}
    for f in sorted(root.glob(t["glob"])):
        if t["format"] == "jsonl":
            records = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        else:
            delim = "\t" if t["format"] == "tsv" else ","
            with open(f, encoding="utf-8", newline="") as fh:
                records = list(csv.DictReader(fh, delimiter=delim))
        for rec in records:
            key, text = rec.get(t["id_field"]), rec.get(t["text_field"])
            if key is None or text is None:
                raise LayoutError(f"{f}: record without {t['id_field']!r}/{t['text_field']!r}")
            key = str(key).strip()
            if t["key"] == "stem":
                key = Path(key).stem
            if key in out and out[key] != text:
                raise LayoutError(f"{f}: conflicting transcripts for {key!r}")
            out[key] = text
    return out


def _script_of(text: str) -> str | None:
    scripts = {s for s in (word_script(w) for w in text.split()) if s}
    return scripts.pop() if len(scripts) == 1 else ("mixed" if scripts else None)


class KathbathAdapter(DatasetAdapter):
    """utterances() yields one SourceUtterance per audio file that has a transcript, a language
    and a speaker; anything missing is recorded in `.problems`, never filled in."""

    def __init__(self, root: str | Path, layout: dict):
        self.root = Path(root)
        self.layout = load_layout(layout)
        self._source = SourceInfo(SOURCE_ID, self.layout["source_version"], LICENCE, USE_RESTRICTION)
        self.problems: list[tuple[str, str]] = []

    @property
    def source(self) -> SourceInfo:
        return self._source

    def utterances(self):
        L = self.layout
        texts = _read_transcripts(self.root, L["transcripts"])
        self.problems = []
        for audio in sorted(self.root.glob(L["audio_glob"])):
            rel = audio.relative_to(self.root).as_posix()
            parts = Path(rel).parts
            key = audio.stem if L["transcripts"]["key"] == "stem" else rel
            if audio.suffix.lower() != ".m4a":
                self.problems.append((rel, "not an .m4a file (the documented source format)"))
                continue
            try:
                folder = parts[L["language_path_index"]]
            except IndexError:
                self.problems.append((rel, "no language folder at language_path_index"))
                continue
            lang = L["language_map"].get(folder)
            m = L["_speaker_rx"].search(audio.stem)
            text = texts.get(key)
            if lang is None:
                self.problems.append((rel, f"folder {folder!r} not in language_map"))
            elif m is None or not m.group("speaker"):
                self.problems.append((rel, "speaker_regex does not match the file name"))
            elif text is None or not text.strip():
                self.problems.append((rel, "no transcript"))
            else:
                script = _script_of(text)
                if script is None:
                    self.problems.append((rel, "transcript has no letters to measure its script"))
                    continue
                yield SourceUtterance(
                    source_utt_id=str(Path(rel).with_suffix("")), audio_path=rel,
                    speaker_id=f"{SOURCE_ID}:{m.group('speaker')}", session_id=None, recording_id=None,
                    transcript_ref=text.strip(), transcript_romanised=None, tokens=None,
                    language_primary=lang, languages_present=[lang], is_code_switched=False, cmi=None,
                    script=script, english_word_script="unknown", provenance="read", environment="unknown",
                    condition_device="unknown", condition_real_or_synthetic="real", aug_recipe=None, seed=None,
                    snr_db=None, clipping_ratio=None, overlap=False, overlap_spans=None, overlap_rel_db=None,
                    safety_tags=None, keyword_spans=None, licence=None, use_restriction=None)


def from_env() -> KathbathAdapter:
    """For `python -m asr_bench.ingest build --adapter asr_bench.kathbath_adapter:from_env`:
    KATHBATH_ROOT = the package root on disk, KATHBATH_LAYOUT = the filled layout spec."""
    return KathbathAdapter(os.environ["KATHBATH_ROOT"], json.loads(Path(os.environ["KATHBATH_LAYOUT"]).read_text(encoding="utf-8")))
