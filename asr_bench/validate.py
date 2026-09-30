"""Validate a Phase 2A canonical manifest (JSONL, one row per utterance; schema.py).

    python -m asr_bench.validate manifest.jsonl [--json] [--indic-languages hi,te]

Runs every single-row rule (schema.validate_row), then the whole-manifest rules of Phase 2A
§7 ("no null speaker_id in speaker-disjoint splits; no speaker, audio hash or session in two
splits; every row has licence + use_restriction") and utt_id uniqueness (§3, "globally
unique"). Exit status 0 = no errors (warnings allowed), 1 = errors, 2 = file unreadable.

--indic-languages: the benchmark configuration's Indic grouping (comma-separated language
subtags). Only with it is english_word_script required on Indic rows (schema.validate_row).
The summary also counts use_restriction=blocked rows: valid inventory, never usable
(eligibility.py).

This checks splits that are already assigned; it does not assign them (stage S3).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make `asr_bench` importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.schema import SPLITS, Issue, validate_row

# Values that must never be shared across two different splits (§7). Checked over all five
# splits, eval_only included: an eval_only speaker reappearing in train is leakage too.
CROSS_SPLIT_KEYS = ("speaker_id", "session_id", "recording_id", "audio_sha256")


def read_jsonl(path: Path) -> tuple[list[tuple[int, object]], list[Issue]]:
    """(line number, parsed row) for every non-blank line, plus parse errors."""
    rows, issues = [], []
    with open(path, encoding="utf-8") as f:
        for n, text in enumerate(f, start=1):
            if not text.strip():
                continue
            try:
                rows.append((n, json.loads(text)))
            except json.JSONDecodeError as e:
                issues.append(Issue("error", None, f"not valid JSON: {e.msg} (column {e.colno})", n))
    return rows, issues


def validate_rows(rows: list[tuple[int, object]], indic_languages: frozenset[str] | None = None) -> list[Issue]:
    issues: list[Issue] = []
    for line, row in rows:
        issues.extend(validate_row(row, line, indic_languages))
    issues.extend(_cross_row(rows))
    return issues


def _cross_row(rows: list[tuple[int, object]]) -> list[Issue]:
    issues = []
    ids: dict[str, list[int]] = defaultdict(list)
    # key -> value -> split -> lines
    seen = {k: defaultdict(lambda: defaultdict(list)) for k in CROSS_SPLIT_KEYS}
    for line, row in rows:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("utt_id"), str):
            ids[row["utt_id"]].append(line)
        split = row.get("split")
        if split not in SPLITS:
            continue  # already an error on the row itself
        for k in CROSS_SPLIT_KEYS:
            val = row.get(k)
            if isinstance(val, str) and val:
                seen[k][val][split].append(line)
    for uid, lines in ids.items():
        if len(lines) > 1:
            issues.append(Issue("error", "utt_id", f"{uid!r} appears on lines {lines} (must be globally unique)"))
    for k in CROSS_SPLIT_KEYS:
        for val, by_split in seen[k].items():
            if len(by_split) > 1:
                where = "; ".join(f"{s}: lines {ls}" for s, ls in sorted(by_split.items()))
                issues.append(Issue("error", k, f"{val!r} is in {len(by_split)} splits ({where})"))
            elif k == "audio_sha256":
                (split, ls), = by_split.items()
                if len(ls) > 1:
                    issues.append(Issue("warning", k, f"{val!r}: identical audio on lines {ls} (same split {split!r})"))
    return issues


def validate_file(path: Path, indic_languages: frozenset[str] | None = None) -> tuple[list[tuple[int, object]], list[Issue]]:
    """(rows read, issues)."""
    rows, issues = read_jsonl(path)
    return rows, issues + validate_rows(rows, indic_languages)


def main(argv: list[str]) -> int:
    argv = list(argv)
    indic = None
    if "--indic-languages" in argv:
        i = argv.index("--indic-languages")
        if i + 1 >= len(argv):
            print("--indic-languages needs a comma-separated list, e.g. hi,te", file=sys.stderr)
            return 2
        indic = frozenset(t.strip() for t in argv[i + 1].split(",") if t.strip())
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        rows, issues = validate_file(path, indic)
    except OSError as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return 2
    n = len(rows)
    blocked = sum(1 for _, r in rows if isinstance(r, dict) and r.get("use_restriction") == "blocked")
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    if "--json" in argv:
        print(json.dumps({"file": str(path), "rows": n, "valid": not errors, "blocked_rows": blocked,
                          "indic_languages": sorted(indic) if indic is not None else None,
                          "errors": [i.__dict__ for i in errors],
                          "warnings": [i.__dict__ for i in warnings]}, indent=1, ensure_ascii=False))
    else:
        for i in errors + warnings:
            print(i)
        print(f"{path}: {n} rows ({blocked} blocked: inventory only, never usable), "
              f"{len(errors)} errors, {len(warnings)} warnings -> " + ("VALID" if not errors else "INVALID"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
