"""Final-test freeze, Phase 2A §6.2 ("frozen and hashed before any candidate is run"), stage S3.

    python -m asr_bench.freeze create --manifest m.jsonl --config split_config.json --out final_test_freeze.json
    python -m asr_bench.freeze verify --manifest m.jsonl --freeze final_test_freeze.json
                                      [--config split_config.json] [--audio-root <source>=<dir> ...]

The freeze is a JSON artifact of IDs and hashes only (no audio, no transcripts), deterministic to
the byte (sorted keys, no timestamps). Per final_test row it records:
  audio_sha256        the exact source-file hash (frozen content, P-S2-2)
  audio_meta_sha256   sample_rate_hz, duration_s, channels
  reference_sha256    transcript_ref, transcript_romanised, tokens, keyword_spans
  metadata_sha256     every other field (incl. any non-§3 carry-over field), EXCEPT audio_path:
                      the location is not content, so the freeze survives files moving (P-S2-2)
plus the split-config digest, and freeze_sha256 over all of it.

Workflow (D-S3-6): assemble -> validate -> leakage check -> assign splits -> freeze -> evaluate.
A freeze is immutable: files are never overwritten, and a deliberate benchmark revision needs a
new, explicitly versioned freeze. Where the artifact is kept is the owner's call (D-S3-7);
nothing here writes into the repository by default.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.audio_meta import AudioMetadataError, sha256_file
from asr_bench.schema import Issue
from asr_bench.splits import ALGORITHM_VERSION, SplitConfig, SplitConfigError, canonical_json, leakage_report
from asr_bench.validate import read_jsonl

FREEZE_FORMAT = "asr_bench.final_test_freeze/1"
AUDIO_META_FIELDS = ("sample_rate_hz", "duration_s", "channels")
REFERENCE_FIELDS = ("transcript_ref", "transcript_romanised", "tokens", "keyword_spans")
NOT_FROZEN = ("audio_path",)  # location, not content (P-S2-2)
_SEPARATE = {"utt_id", "audio_sha256", *AUDIO_META_FIELDS, *REFERENCE_FIELDS, *NOT_FROZEN}


class FreezeError(ValueError):
    def __init__(self, message: str, issues: list[Issue] | None = None):
        self.issues = issues or []
        super().__init__(message)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def row_entry(row: dict) -> dict:
    return {
        "utt_id": row["utt_id"],
        "audio_sha256": row["audio_sha256"],
        "audio_meta_sha256": _sha({f: row.get(f) for f in AUDIO_META_FIELDS}),
        "reference_sha256": _sha({f: row.get(f) for f in REFERENCE_FIELDS}),
        "metadata_sha256": _sha({k: v for k, v in row.items() if k not in _SEPARATE}),
    }


def _digest(body: dict) -> str:
    return _sha({k: v for k, v in body.items() if k != "freeze_sha256"})


def create_freeze(rows: list[dict], config: SplitConfig) -> dict:
    """Freeze the final_test rows of a manifest that is schema-valid and leakage-clean."""
    issues, _ = leakage_report(rows)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        raise FreezeError(f"manifest has {len(errors)} validation/leakage errors; refusing to freeze", errors)
    final = sorted((r for r in rows if r.get("split") == "final_test"), key=lambda r: r["utt_id"])
    if not final:
        raise FreezeError("manifest has no final_test rows; nothing to freeze")
    body = {
        "format": FREEZE_FORMAT,
        "algorithm_version": ALGORITHM_VERSION,
        "split_config_sha256": config.sha256,
        "salt": config.salt,
        "n_rows": len(final),
        "rows": [row_entry(r) for r in final],
    }
    body["freeze_sha256"] = _digest(body)
    return body


def dumps_freeze(freeze: dict) -> str:
    return json.dumps(freeze, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def write_freeze(freeze: dict, path: str | Path) -> None:
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"{p} exists; a freeze is never overwritten (a revision is a new, versioned freeze)")
    p.write_text(dumps_freeze(freeze), encoding="utf-8")


def load_freeze(path: str | Path) -> dict:
    """Load and self-check: format, and freeze_sha256 still matches the artifact's content."""
    try:
        freeze = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FreezeError(f"{path}: not valid JSON ({e.msg})") from e
    problems = check_artifact(freeze)
    if problems:
        raise FreezeError(f"{path}: " + "; ".join(i.message for i in problems), problems)
    return freeze


def check_artifact(freeze) -> list[Issue]:
    if not isinstance(freeze, dict) or freeze.get("format") != FREEZE_FORMAT:
        return [Issue("error", None, f"not a {FREEZE_FORMAT} artifact")]
    out = []
    if freeze.get("freeze_sha256") != _digest(freeze):
        out.append(Issue("error", None, "freeze artifact was edited: freeze_sha256 does not match its content"))
    rows = freeze.get("rows")
    if not isinstance(rows, list) or freeze.get("n_rows") != len(rows):
        out.append(Issue("error", None, "freeze artifact rows/n_rows are inconsistent"))
    return out


def verify_freeze(rows: list[dict], freeze: dict, config: SplitConfig | None = None) -> list[Issue]:
    """Every difference between the manifest's final_test and the freeze is an error."""
    issues = check_artifact(freeze)
    if issues:
        return issues
    if config is not None and config.sha256 != freeze["split_config_sha256"]:
        issues.append(Issue("error", None, f"split config digest {config.sha256} differs from the frozen "
                                           f"{freeze['split_config_sha256']} (D-S3-6)"))
    frozen = {e["utt_id"]: e for e in freeze["rows"]}
    by_id = {}
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("utt_id"), str):
            if r["utt_id"] in by_id:
                issues.append(Issue("error", "utt_id", "duplicate utt_id in manifest", utt_id=r["utt_id"]))
            by_id[r["utt_id"]] = r
    current = {u: r for u, r in by_id.items() if r.get("split") == "final_test"}
    for u in sorted(set(current) - set(frozen)):
        issues.append(Issue("error", "split", "ADDED to final_test after freezing", utt_id=u))
    for u in sorted(set(frozen) - set(current)):
        if u in by_id:
            issues.append(Issue("error", "split", f"MOVED out of final_test to {by_id[u].get('split')!r}", utt_id=u))
        else:
            issues.append(Issue("error", "split", "REMOVED: frozen final_test row is missing from the manifest", utt_id=u))
    for u in sorted(set(frozen) & set(current)):
        was, now = frozen[u], row_entry(current[u])
        if was["audio_sha256"] != now["audio_sha256"]:
            issues.append(Issue("error", "audio_sha256", "AUDIO CHANGED since freezing", utt_id=u))
        elif was["audio_meta_sha256"] != now["audio_meta_sha256"]:
            issues.append(Issue("error", "duration_s", "audio metadata changed with identical audio bytes "
                                                       "(re-extraction difference? see P-S2-1)", utt_id=u))
        if was["reference_sha256"] != now["reference_sha256"]:
            issues.append(Issue("error", "transcript_ref", "REFERENCE CHANGED since freezing", utt_id=u))
        if was["metadata_sha256"] != now["metadata_sha256"]:
            issues.append(Issue("error", None, "METADATA CHANGED since freezing", utt_id=u))
    return issues


def verify_audio(rows: list[dict], roots: dict[str, str | Path]) -> list[Issue]:
    """Optional on-disk check of final_test audio: re-hash each file under its source root."""
    issues = []
    for r in sorted((r for r in rows if isinstance(r, dict) and r.get("split") == "final_test"), key=lambda r: r["utt_id"]):
        root = roots.get(r.get("source_dataset"))
        if root is None:
            issues.append(Issue("error", "audio_path", f"no audio root given for source {r.get('source_dataset')!r}",
                                utt_id=r["utt_id"]))
            continue
        try:
            actual = sha256_file(Path(root) / r["audio_path"])
        except (OSError, AudioMetadataError) as e:
            issues.append(Issue("error", "audio_path", f"cannot read audio: {e}", utt_id=r["utt_id"]))
            continue
        if actual != r.get("audio_sha256"):
            issues.append(Issue("error", "audio_sha256", "file on disk does not match audio_sha256", utt_id=r["utt_id"]))
    return issues


USAGE = ("usage: python -m asr_bench.freeze create --manifest m.jsonl --config cfg.json --out freeze.json\n"
         "       python -m asr_bench.freeze verify --manifest m.jsonl --freeze freeze.json [--config cfg.json] "
         "[--audio-root <source>=<dir> ...]")


def main(argv: list[str]) -> int:
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None

    if not argv or argv[0] not in ("create", "verify") or opt("--manifest") is None:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        parsed, parse_issues = read_jsonl(Path(opt("--manifest")))
        config = SplitConfig.load(opt("--config")) if opt("--config") else None
        freeze = load_freeze(opt("--freeze")) if argv[0] == "verify" and opt("--freeze") else None
    except (OSError, SplitConfigError, FreezeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    rows = [r for _, r in parsed]
    if argv[0] == "create":
        if config is None or opt("--out") is None:
            print(USAGE, file=sys.stderr)
            return 2
        try:
            if parse_issues:
                raise FreezeError("manifest has unparseable lines", parse_issues)
            fz = create_freeze(rows, config)
            write_freeze(fz, opt("--out"))
        except FreezeError as e:
            for i in e.issues:
                print(i)
            print(f"freeze REFUSED: {e}", file=sys.stderr)
            return 1
        except FileExistsError as e:
            print(e, file=sys.stderr)
            return 2
        print(f"{opt('--out')}: {fz['n_rows']} final_test rows frozen; freeze_sha256 {fz['freeze_sha256']}")
        return 0
    if freeze is None:
        print(USAGE, file=sys.stderr)
        return 2
    issues = parse_issues + verify_freeze(rows, freeze, config)
    roots = {}
    for i, a in enumerate(argv):
        if a == "--audio-root" and i + 1 < len(argv) and "=" in argv[i + 1]:
            src, root = argv[i + 1].split("=", 1)
            roots[src] = root
    if roots:
        issues += verify_audio(rows, roots)
    for i in issues:
        print(i)
    ok = not any(i.level == "error" for i in issues)
    print(f"freeze {freeze['freeze_sha256']}: " + ("VERIFIED" if ok else "MISMATCH"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
