"""Dataset adapter contract: how an approved source dataset becomes canonical manifest rows (§3).

S2 defines the contract only. No public-dataset adapter exists yet, nothing is downloaded, and no
licence question is answered here.

An adapter supplies:
  - SourceInfo: source_dataset, source_version, and the source's licence + use_restriction
    exactly as recorded from Phase 1 §20 by whoever writes the adapter (not decided here);
  - one SourceUtterance per utterance: everything §3 needs that only the source knows.
    Every field must be passed explicitly (no defaults): a value the source cannot give is
    None, never guessed (§3). "unknown" is a real enum value and must be chosen deliberately.

build_row() adds what is MEASURED or DERIVED, never taken from the adapter:
  - utt_id = "<source_dataset>:<source_utt_id>" (§3: "<source>:<source_id>");
  - sample_rate_hz, duration_s, channels, audio_sha256 from the audio file (audio_meta.py);
and the split, which the CALLER supplies: split assignment is stage S3, not the adapter's job.
It then validates the finished row with schema.validate_row and refuses an invalid one.

Namespacing contract (S1, P-S1-2): speaker_id, session_id and recording_id must already be
namespaced by the adapter as "<source_dataset>:<source-local id>". build_row CHECKS that form
for the adapter's own source_dataset; it never constructs it, because how a source-local ID is
extracted (file name, metadata column, folder) is source-specific.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from pathlib import Path

from asr_bench.audio_meta import AudioMetadataError, read_audio_metadata
from asr_bench.registry import RegistryError, SourceRegistry
from asr_bench.schema import FIELDS, USE_RESTRICTION, Issue, validate_row


class AdapterContractError(ValueError):
    """The adapter broke the contract (bad SourceInfo, un-namespaced ID, missing audio root...)."""


class ManifestRowError(ValueError):
    """The assembled row fails schema.validate_row; `.issues` holds the errors."""

    def __init__(self, utt_id: str, issues: list[Issue]):
        self.issues = issues
        super().__init__(f"{utt_id}: " + "; ".join(f"{i.field}: {i.message}" for i in issues))


@dataclass(frozen=True)
class SourceInfo:
    source_dataset: str
    source_version: str
    licence: str
    use_restriction: str  # train_ok | eval_only | blocked, as recorded from Phase 1 §20


@dataclass(frozen=True, kw_only=True)
class SourceUtterance:
    """What the source knows about one utterance. No defaults on purpose (see module docstring)."""
    source_utt_id: str
    audio_path: str  # written to the manifest as given; relative paths resolve against audio_root (P-S2-2)
    speaker_id: str | None  # "<source_dataset>:<source speaker id>", or None if the source has none
    session_id: str | None
    recording_id: str | None
    transcript_ref: str
    transcript_romanised: str | None
    tokens: list | None
    language_primary: str
    languages_present: list
    is_code_switched: bool
    cmi: float | None  # scale/definition recorded by the adapter's documentation (P-S1-8)
    script: str
    english_word_script: str | None
    provenance: str
    environment: str
    condition_device: str
    condition_real_or_synthetic: str
    aug_recipe: str | None
    seed: int | None
    snr_db: float | None
    clipping_ratio: float | None
    overlap: bool
    overlap_spans: list | None
    overlap_rel_db: float | None
    safety_tags: list | None
    keyword_spans: list | None
    # Per-utterance licence, for sources whose licence varies by item (e.g. FSD50K per-clip,
    # Phase 1 §20). None = the SourceInfo values. use_restriction may only be equal to or
    # STRICTER than the source's (train_ok < eval_only < blocked); it never relaxes it (P-S2-3).
    licence: str | None
    use_restriction: str | None


# Manifest fields build_row fills itself; every other §3 field comes from SourceUtterance.
MEASURED = ("sample_rate_hz", "duration_s", "channels", "audio_sha256")
FROM_SOURCE_INFO = ("source_dataset", "source_version", "licence", "use_restriction")
# P-S2-3 (resolved): monotone precedence; the source value is the ceiling.
RESTRICTION_ORDER = {"train_ok": 0, "eval_only": 1, "blocked": 2}
_UTT_FIELDS = {f.name for f in fields(SourceUtterance)} - {"source_utt_id", "licence", "use_restriction"}
assert _UTT_FIELDS | set(MEASURED) | set(FROM_SOURCE_INFO) | {"utt_id", "split"} == set(FIELDS), "adapter/schema drift"


class DatasetAdapter(ABC):
    """One approved source. Implementations read the source's own files; they do not download."""

    @property
    @abstractmethod
    def source(self) -> SourceInfo: ...

    @abstractmethod
    def utterances(self) -> Iterable[SourceUtterance]: ...


def _check_source(src: SourceInfo) -> None:
    for name in ("source_dataset", "source_version", "licence"):
        v = getattr(src, name)
        if not (isinstance(v, str) and v.strip()):
            raise AdapterContractError(f"SourceInfo.{name} must be a non-empty string, got {v!r}")
    if ":" in src.source_dataset:
        raise AdapterContractError(f"source_dataset {src.source_dataset!r} must not contain ':' (it is the namespace)")
    if src.use_restriction not in USE_RESTRICTION:
        raise AdapterContractError(f"SourceInfo.use_restriction must be one of {USE_RESTRICTION}, got {src.use_restriction!r}")


_DEFAULT_REGISTRY: SourceRegistry | None = None


def check_registered(src: SourceInfo, registry: SourceRegistry | None = None) -> dict:
    """Licence gate: the source must be registered, its acquisition authorised by the owner, and
    its SourceInfo licence + use_restriction identical to the registry entry. None = the
    versioned asr_bench/source_registry.json."""
    global _DEFAULT_REGISTRY
    if registry is None:
        if _DEFAULT_REGISTRY is None:
            _DEFAULT_REGISTRY = SourceRegistry.load()
        registry = _DEFAULT_REGISTRY
    try:
        entry = registry.entry(src.source_dataset)
    except RegistryError as e:
        raise AdapterContractError(f"{e}; unregistered sources cannot produce manifest rows") from e
    if not entry["acquisition_authorised"]:
        raise AdapterContractError(f"source {src.source_dataset!r}: acquisition not authorised by the owner "
                                   f"(registry v{registry.version})")
    for f in ("licence", "use_restriction"):
        if getattr(src, f) != entry[f]:
            raise AdapterContractError(f"source {src.source_dataset!r}: SourceInfo.{f} {getattr(src, f)!r} disagrees "
                                       f"with the registry {entry[f]!r}")
    return entry


def check_namespaced(source_dataset: str, field: str, value) -> None:
    """Contract check only: value is None or "<source_dataset>:<non-empty local id>"."""
    if value is None:
        return
    prefix = f"{source_dataset}:"
    if not (isinstance(value, str) and value.startswith(prefix) and value[len(prefix):].strip()):
        raise AdapterContractError(
            f"{field} {value!r} is not namespaced as '{prefix}<source {field}>'; the adapter must namespace it")


def build_row(src: SourceInfo, utt: SourceUtterance, *, split: str, audio_root: str | Path | None = None,
              indic_languages: frozenset[str] | None = None, registry: SourceRegistry | None = None) -> dict:
    """One valid canonical manifest row, or AdapterContractError / AudioMetadataError / ManifestRowError."""
    _check_source(src)
    entry = check_registered(src, registry)
    if entry.get("per_item_restriction_required") and (utt.licence is None or utt.use_restriction is None):
        raise AdapterContractError(f"{utt.source_utt_id}: source {src.source_dataset!r} requires an explicit per-item licence "
                                   "and use_restriction (registry per_item_restriction_required); the source-level "
                                   f"{src.use_restriction!r} is only a ceiling")
    if not (isinstance(utt.source_utt_id, str) and utt.source_utt_id.strip()):
        raise AdapterContractError(f"source_utt_id must be a non-empty string, got {utt.source_utt_id!r}")
    for f in ("speaker_id", "session_id", "recording_id"):
        check_namespaced(src.source_dataset, f, getattr(utt, f))
    if utt.use_restriction is not None and (utt.use_restriction not in RESTRICTION_ORDER or
                                            RESTRICTION_ORDER[utt.use_restriction] < RESTRICTION_ORDER[src.use_restriction]):
        raise AdapterContractError(f"{utt.source_utt_id}: utterance use_restriction {utt.use_restriction!r} may only be "
                                   f"equal to or stricter than the source's {src.use_restriction!r} (P-S2-3)")

    audio = Path(utt.audio_path)
    if not audio.is_absolute():
        if audio_root is None:
            raise AdapterContractError(f"{utt.source_utt_id}: relative audio_path {utt.audio_path!r} needs audio_root")
        audio = Path(audio_root) / audio
    meta = read_audio_metadata(audio)

    row = {f: getattr(utt, f) for f in _UTT_FIELDS}
    row.update(
        utt_id=f"{src.source_dataset}:{utt.source_utt_id}",
        source_dataset=src.source_dataset, source_version=src.source_version,
        licence=utt.licence if utt.licence is not None else src.licence,
        use_restriction=utt.use_restriction if utt.use_restriction is not None else src.use_restriction,
        sample_rate_hz=meta.sample_rate_hz, duration_s=meta.duration_s, channels=meta.channels,
        audio_sha256=meta.audio_sha256, split=split,
    )
    row = {f: row[f] for f in FIELDS}  # canonical field order
    errors = [i for i in validate_row(row, indic_languages=indic_languages) if i.level == "error"]
    if errors:
        raise ManifestRowError(row["utt_id"], errors)
    return row


def build_rows(adapter: DatasetAdapter, split_for: Callable[[SourceUtterance], str], *,
               audio_root: str | Path | None = None, indic_languages: frozenset[str] | None = None,
               registry: SourceRegistry | None = None) -> tuple[list[dict], list[tuple[str, Exception]]]:
    """(rows, [(source_utt_id, error)]) over the whole adapter. Failures are collected, not hidden
    and not fatal, so one unreadable file does not stop an inventory run. `split_for` is the
    caller's split assignment (stage S3); S2 does not assign splits. The source itself must pass
    the registry gate (check_registered) or nothing is built."""
    rows, failures = [], []
    src = adapter.source
    _check_source(src)
    check_registered(src, registry)  # a source-level refusal is fatal, not one failure per utterance
    for utt in adapter.utterances():
        try:
            rows.append(build_row(src, utt, split=split_for(utt), audio_root=audio_root,
                                  indic_languages=indic_languages, registry=registry))
        except (AdapterContractError, AudioMetadataError, ManifestRowError) as e:
            failures.append((getattr(utt, "source_utt_id", None), e))
    return rows, failures
