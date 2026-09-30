"""Split assignment + leakage report, Phase 2A §6.1 / §7 and Phase 1 §18–19 (stage S3).

Split ASSIGNMENT only. Whether a row is valid is schema.py/validate.py; whether it may be used
is eligibility.py; freezing the final test is freeze.py.

    python -m asr_bench.splits assign --manifest in.jsonl --config split_config.json --out out.jsonl
                                      [--report report.json] [--freeze final_test_freeze.json]
    python -m asr_bench.splits report --manifest m.jsonl [--out report.json]

Rules (PENDING_DECISIONS.md, "S3"):
  - Groups: rows linked by a shared non-null speaker_id, session_id or recording_id,
    transitively (union-find). Missing IDs are never invented; audio_sha256 never groups.
  - Group key: smallest speaker_id, else smallest session_id, else smallest recording_id.
  - A group goes to ONE split. Assignment uses only the group key, the salt and the source
    policy -- no audio, no row order, no randomness (Phase 1 §18: "deterministic hash ...
    before any audio is inspected").
  - Any blocked row -> the whole group is eval_only inventory (D-S3-4). Any row with a null
    speaker_id -> the whole group is eval_only (§3: excluded from speaker-disjoint sets).
  - Any eval_only-restricted row -> the group never enters train. If its hashed split is not
    train it stays there; if it is, the group's relative position inside the train bucket is
    mapped onto the permitted splits (ratios renormalised) -- one hash, no rehashing (D-S3-3).
  - Exact audio_sha256 shared by two different groups is an error to resolve by hand (D-S3-5).
  - Exact duplicate transcripts across splits are warnings (D-S3-9).
There are no default ratios: every source must be configured explicitly (D-S3-1).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.schema import FIELDS, SPLITS, Issue
from asr_bench.validate import read_jsonl, validate_rows

ALGORITHM_VERSION = "asr_bench.splits/1"
CONFIG_FORMAT = "asr_bench.split_config/1"
EXECUTED_ORDER = ("train", "dev", "test", "final_test")  # fixed order of the cumulative hash buckets
POLICIES = ("hash", "fixed")  # "given" (source-provided splits) is not implemented (D-S3-8)
_ID_KINDS = ("speaker_id", "session_id", "recording_id")  # also the group-key priority


class SplitConfigError(ValueError):
    pass


class SplitError(ValueError):
    """A split plan with errors was used as if it were valid."""


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


# --- configuration ------------------------------------------------------------------------------

@dataclass(frozen=True)
class SplitConfig:
    salt: str
    sources: dict  # source_dataset -> {"policy": "hash", "ratios": {...}} | {"policy": "fixed", "split": ...}
    sha256: str  # digest of the canonical config, recorded in split reports and freezes

    @classmethod
    def from_dict(cls, raw) -> SplitConfig:
        if not isinstance(raw, dict):
            raise SplitConfigError("config must be a JSON object")
        unknown = set(raw) - {"format", "salt", "sources"}
        if unknown:
            raise SplitConfigError(f"unknown config keys {sorted(unknown)}")
        if raw.get("format") != CONFIG_FORMAT:
            raise SplitConfigError(f"format must be {CONFIG_FORMAT!r}, got {raw.get('format')!r}")
        salt = raw.get("salt")
        if not (isinstance(salt, str) and salt.strip()):
            raise SplitConfigError("salt must be a non-empty string (it is recorded in every split artifact)")
        sources = raw.get("sources")
        if not (isinstance(sources, dict) and sources):
            raise SplitConfigError("sources must be a non-empty object: every source needs an explicit policy")
        for name, pol in sources.items():
            _check_policy(name, pol)
        return cls(salt=salt, sources=sources, sha256=hashlib.sha256(canonical_json(raw)).hexdigest())

    @classmethod
    def load(cls, path: str | Path) -> SplitConfig:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SplitConfigError(f"{path}: not valid JSON ({e.msg})") from e
        return cls.from_dict(raw)


def _check_policy(name, pol) -> None:
    where = f"sources[{name!r}]"
    if not (isinstance(name, str) and name.strip()):
        raise SplitConfigError(f"{where}: source name must be a non-empty string")
    if not isinstance(pol, dict):
        raise SplitConfigError(f"{where}: must be an object")
    kind = pol.get("policy")
    if kind == "given":
        raise SplitConfigError(f"{where}: policy 'given' (source-provided splits) is not implemented (D-S3-8)")
    if kind not in POLICIES:
        raise SplitConfigError(f"{where}: policy must be one of {POLICIES}, got {kind!r}")
    if kind == "hash":
        if set(pol) != {"policy", "ratios"}:
            raise SplitConfigError(f"{where}: a hash policy has exactly 'policy' and 'ratios'")
        ratios = pol["ratios"]
        if not isinstance(ratios, dict) or set(ratios) != set(EXECUTED_ORDER):
            raise SplitConfigError(f"{where}: ratios must give each of {EXECUTED_ORDER} explicitly")
        for s, r in ratios.items():
            if isinstance(r, bool) or not isinstance(r, (int, float)) or not math.isfinite(r) or r < 0:
                raise SplitConfigError(f"{where}: ratio {s}={r!r} must be a finite number >= 0")
        if abs(sum(ratios.values()) - 1.0) > 1e-9:
            raise SplitConfigError(f"{where}: ratios sum to {sum(ratios.values())}, not 1")
    else:
        if set(pol) != {"policy", "split"}:
            raise SplitConfigError(f"{where}: a fixed policy has exactly 'policy' and 'split'")
        if pol["split"] not in SPLITS:
            raise SplitConfigError(f"{where}: fixed split must be one of {SPLITS}, got {pol['split']!r}")


# --- records and grouping -----------------------------------------------------------------------

@dataclass(frozen=True)
class SplitRecord:
    """The only inputs assignment may look at (no audio, no transcript)."""
    utt_id: str
    source_dataset: str
    use_restriction: str
    speaker_id: str | None
    session_id: str | None
    recording_id: str | None


def records_from_rows(rows: Iterable[dict]) -> list[SplitRecord]:
    return [SplitRecord(r.get("utt_id"), r.get("source_dataset"), r.get("use_restriction"),
                        r.get("speaker_id"), r.get("session_id"), r.get("recording_id")) for r in rows]


def records_from_utterances(src, utterances: Iterable) -> list[SplitRecord]:
    """Before any audio is read (adapter path). utt_id and the effective restriction follow
    adapters.build_row: "<source_dataset>:<source_utt_id>", utterance value else source value."""
    return [SplitRecord(f"{src.source_dataset}:{u.source_utt_id}", src.source_dataset,
                        u.use_restriction if u.use_restriction is not None else src.use_restriction,
                        u.speaker_id, u.session_id, u.recording_id) for u in utterances]


@dataclass
class Group:
    key: str | None  # "speaker_id=<id>" etc.; None = no identifier at all (never invented)
    records: list[SplitRecord]


def group_records(records: list[SplitRecord]) -> list[Group]:
    """Transitive union-find over typed IDs; each record joins its own non-null IDs."""
    parent: dict = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i, r in enumerate(records):
        node = ("utt", i)
        parent.setdefault(node, node)
        for kind in _ID_KINDS:
            v = getattr(r, kind)
            if v is not None:
                idn = ("id", kind, v)
                parent.setdefault(idn, idn)
                union(node, idn)
    members = defaultdict(list)
    for i, r in enumerate(records):
        members[find(("utt", i))].append(r)
    groups = []
    for recs in members.values():
        key = None
        for kind in _ID_KINDS:  # priority: speaker, then session, then recording
            vals = sorted(getattr(r, kind) for r in recs if getattr(r, kind) is not None)
            if vals:
                key = f"{kind}={vals[0]}"
                break
        groups.append(Group(key, sorted(recs, key=lambda r: str(r.utt_id))))
    return sorted(groups, key=lambda g: (g.key is None, g.key or "", str(g.records[0].utt_id)))


def hash_position(salt: str, group_key: str) -> float:
    """Deterministic position in [0, 1) for a group."""
    h = hashlib.sha256(f"{salt}\x1f{group_key}".encode("utf-8")).hexdigest()
    return int(h[:16], 16) / 2 ** 64


def _bucket(u: float, ratios: dict, allowed: tuple[str, ...]) -> str | None:
    """Cumulative buckets over `allowed` splits in EXECUTED_ORDER, ratios renormalised over them."""
    parts = [(s, ratios[s]) for s in EXECUTED_ORDER if s in allowed and ratios[s] > 0]
    total = sum(r for _, r in parts)
    if not parts:
        return None
    cum = 0.0
    for s, r in parts:
        cum += r / total
        if u < cum:
            return s
    return parts[-1][0]


def _constrained_bucket(u: float, ratios: dict, allowed: tuple[str, ...]) -> str | None:
    """Split for position u when only `allowed` splits are permitted (D-S3-3). The hashed split
    is kept if permitted; otherwise u's relative position inside the forbidden split's bucket is
    mapped onto the permitted splits (ratios renormalised). One hash, no rehashing."""
    hashed = _bucket(u, ratios, EXECUTED_ORDER)
    if hashed in allowed:
        return hashed
    lo = 0.0
    for s in EXECUTED_ORDER:
        if s == hashed:
            break
        lo += ratios[s]
    width = ratios[hashed]
    rel = min(max((u - lo) / width, 0.0), 1.0 - 1e-12) if width > 0 else 0.0
    return _bucket(rel, ratios, allowed)


# --- assignment -------------------------------------------------------------------------------

@dataclass
class SplitPlan:
    assignments: dict  # utt_id -> split
    issues: list  # Issue; errors make the plan unusable
    report: dict

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    def split_for(self, src) -> Callable:
        """The callable adapters.build_rows expects."""
        if not self.ok:
            raise SplitError("split plan has errors: " + "; ".join(str(i) for i in self.issues if i.level == "error"))

        def f(utt) -> str:
            return self.assignments[f"{src.source_dataset}:{utt.source_utt_id}"]
        return f


def assign_splits(records: list[SplitRecord], config: SplitConfig, freeze: dict | None = None) -> SplitPlan:
    issues: list[Issue] = []
    assignments: dict = {}
    constrained, inventory = [], []

    def err(msg, field_=None):
        issues.append(Issue("error", field_, msg))

    seen = defaultdict(int)
    for r in records:
        seen[r.utt_id] += 1
    for uid, n in sorted(seen.items(), key=lambda kv: str(kv[0])):
        if n > 1:
            err(f"{uid!r} appears {n} times in the input", "utt_id")

    groups = group_records(records)
    for g in groups:
        ids = [r.utt_id for r in g.records]
        label = g.key or f"(no identifiers: {ids[0]})"
        sources = sorted({str(r.source_dataset) for r in g.records})
        if len(sources) > 1:
            err(f"group {label} spans sources {sources}: IDs are not namespaced per source; fix the adapter", "speaker_id")
            continue
        if sources[0] not in config.sources:
            err(f"source {sources[0]!r} has no policy in the split config (no defaults, D-S3-1)", "source_dataset")
            continue
        restrictions = {r.use_restriction for r in g.records}
        if "blocked" in restrictions:
            split, reason = "eval_only", "contains a blocked row: eval_only inventory, never eligible (D-S3-4)"
        elif g.key is None or any(r.speaker_id is None for r in g.records):
            split = "eval_only"
            reason = ("no speaker/session/recording identifier: cannot be grouped, eval_only (§3 null speaker)"
                      if g.key is None else "contains a row with null speaker_id: eval_only (§3, excluded from "
                                            "speaker-disjoint splits)")
        else:
            split, reason = None, None
        if split is not None:
            inventory.append({"group_key": g.key, "utt_ids": ids, "reason": reason})
        else:
            pol = config.sources[sources[0]]
            allowed = tuple(s for s in EXECUTED_ORDER if not (s == "train" and "eval_only" in restrictions))
            if pol["policy"] == "fixed":
                split = pol["split"]
                if split == "train" and "eval_only" in restrictions:
                    err(f"group {label}: source is fixed to train but the group has an eval_only-restricted row", "use_restriction")
                    continue
            else:
                u = hash_position(config.salt, g.key)
                hashed = _bucket(u, pol["ratios"], EXECUTED_ORDER)
                split = _constrained_bucket(u, pol["ratios"], allowed)
                if split is None:
                    err(f"group {label}: eval_only-restricted rows but the source's ratios allow only train", "use_restriction")
                    continue
                if split != hashed:
                    constrained.append({"group_key": g.key, "utt_ids": ids, "hashed_split": hashed, "assigned_split": split,
                                        "reason": "contains an eval_only-restricted row: never train (D-S3-3)"})
        for uid in ids:
            assignments[uid] = split

    if freeze is not None:
        issues.extend(_check_against_freeze(assignments, config, freeze))

    report = _plan_report(records, groups, assignments, config, constrained, inventory)
    return SplitPlan(assignments, issues, report)


def _check_against_freeze(assignments: dict, config: SplitConfig, freeze: dict) -> list[Issue]:
    out = []
    if freeze.get("split_config_sha256") != config.sha256:
        out.append(Issue("error", None, "split config differs from the one the final test was frozen with "
                                        f"({freeze.get('split_config_sha256')} != {config.sha256}); a deliberate "
                                        "revision needs a new, versioned freeze (D-S3-6)"))
    frozen = {r["utt_id"] for r in freeze.get("rows", [])}
    now = {u for u, s in assignments.items() if s == "final_test"}
    for u in sorted(frozen - now):
        out.append(Issue("error", "split", f"{u!r} is frozen in final_test but would be assigned "
                                           f"{assignments.get(u, 'nothing')!r}", utt_id=u))
    for u in sorted(now - frozen):
        out.append(Issue("error", "split", f"{u!r} would join the frozen final_test", utt_id=u))
    return out


def _plan_report(records, groups, assignments, config, constrained, inventory) -> dict:
    per = {s: {"rows": 0, "groups": 0, "speakers": set(), "sources": set()} for s in SPLITS}
    for g in groups:
        s = assignments.get(g.records[0].utt_id)
        if s is None:
            continue
        per[s]["groups"] += 1
        for r in g.records:
            per[s]["rows"] += 1
            per[s]["sources"].add(r.source_dataset)
            if r.speaker_id is not None:
                per[s]["speakers"].add(r.speaker_id)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "salt": config.salt,
        "split_config_sha256": config.sha256,
        "records": len(records),
        "groups": len(groups),
        "largest_group_rows": max((len(g.records) for g in groups), default=0),
        "unassigned_rows": sum(1 for r in records if r.utt_id not in assignments),
        "splits": {s: {"rows": v["rows"], "groups": v["groups"], "speakers": len(v["speakers"]),
                       "sources": sorted(map(str, v["sources"]))} for s, v in per.items()},
        "constrained_groups": constrained,
        "eval_only_inventory_groups": inventory,
        "missing_ids": {k: sum(1 for r in records if getattr(r, k) is None) for k in _ID_KINDS},
    }


def apply_plan(rows: list[dict], plan: SplitPlan) -> list[dict]:
    """New rows with `split` replaced from the plan (canonical field order kept)."""
    if not plan.ok:
        raise SplitError("split plan has errors")
    return [{**r, "split": plan.assignments[r["utt_id"]]} for r in rows]


# --- leakage report ---------------------------------------------------------------------------

def leakage_report(rows: list[dict], line_numbers: list[int] | None = None) -> tuple[list[Issue], dict]:
    """S1 validation (row rules + cross-split speaker/session/recording/audio) plus the S3 checks:
    exact audio shared by different groups (error, D-S3-5), exact transcripts across splits
    (warning, D-S3-9), and per-language source availability for source-disjoint testing."""
    lines = line_numbers or list(range(1, len(rows) + 1))
    issues = list(validate_rows(list(zip(lines, rows))))
    dict_rows = [r for r in rows if isinstance(r, dict)]
    recs = records_from_rows(dict_rows)
    group_of = {}
    for gi, g in enumerate(group_records(recs)):
        for r in g.records:
            group_of[r.utt_id] = gi

    by_audio = defaultdict(set)
    by_text = defaultdict(set)
    for r in dict_rows:
        if isinstance(r.get("audio_sha256"), str):
            by_audio[r["audio_sha256"]].add((group_of.get(r.get("utt_id")), r.get("utt_id")))
        t = r.get("transcript_ref")
        if isinstance(t, str) and t.strip() and r.get("split") in SPLITS:
            by_text[t].add(r["split"])
    for sha, members in sorted(by_audio.items()):
        if len({g for g, _ in members}) > 1:
            issues.append(Issue("error", "audio_sha256", f"{sha!r} is the exact audio of rows in different groups "
                                f"{sorted(str(u) for _, u in members)}: resolve by hand (D-S3-5)"))
    for text, splits in sorted(by_text.items()):
        if len(splits) > 1:
            issues.append(Issue("warning", "transcript_ref", f"exact transcript {text!r} occurs in splits {sorted(splits)} (D-S3-9)"))

    # Source-disjoint availability (Phase 2A §6.1), per language_primary: sources with test or
    # final_test rows and no train/dev rows. Candidate training sources are checked later (S7).
    lang_split_sources = defaultdict(lambda: defaultdict(set))
    for r in dict_rows:
        lang_split_sources[str(r.get("language_primary"))][r.get("split")].add(str(r.get("source_dataset")))
    source_disjoint = {}
    for lang, by_split in sorted(lang_split_sources.items()):
        seen_in_fit = by_split.get("train", set()) | by_split.get("dev", set())
        tested = by_split.get("test", set()) | by_split.get("final_test", set())
        source_disjoint[lang] = {"test_sources": sorted(tested), "held_out_test_sources": sorted(tested - seen_in_fit)}
    split_sources = defaultdict(set)
    for r in dict_rows:
        split_sources[str(r.get("split"))].add(str(r.get("source_dataset")))
    report = {
        "rows": len(rows),
        "errors": sum(1 for i in issues if i.level == "error"),
        "warnings": sum(1 for i in issues if i.level == "warning"),
        "sources_by_split": {s: sorted(v) for s, v in sorted(split_sources.items())},
        "source_disjoint_by_language": source_disjoint,
    }
    return issues, report


# --- CLI ----------------------------------------------------------------------------------------

def _opt(argv, name):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def _write_new(path: str, text: str) -> None:
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"{p} exists; refusing to overwrite")
    p.write_text(text, encoding="utf-8")


USAGE = ("usage: python -m asr_bench.splits assign --manifest in.jsonl --config cfg.json --out out.jsonl "
         "[--report r.json] [--freeze f.json]\n       python -m asr_bench.splits report --manifest m.jsonl [--out r.json]")


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("assign", "report"):
        print(USAGE, file=sys.stderr)
        return 2
    manifest = _opt(argv, "--manifest")
    if manifest is None:
        print("--manifest is required", file=sys.stderr)
        return 2
    try:
        parsed, parse_issues = read_jsonl(Path(manifest))
    except OSError as e:
        print(f"cannot read {manifest}: {e}", file=sys.stderr)
        return 2
    rows = [r for _, r in parsed]
    if argv[0] == "report":
        issues, report = leakage_report(rows, [n for n, _ in parsed])
        issues = parse_issues + issues
        for i in issues:
            print(i)
        text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        (_write_new(_opt(argv, "--out"), text) if _opt(argv, "--out") else print(text, end=""))
        return 1 if any(i.level == "error" for i in issues) else 0
    try:
        config = SplitConfig.load(_opt(argv, "--config") or "")
        freeze = None
        if _opt(argv, "--freeze"):
            from asr_bench.freeze import load_freeze
            freeze = load_freeze(_opt(argv, "--freeze"))
    except (SplitConfigError, OSError, ValueError) as e:
        print(f"config/freeze error: {e}", file=sys.stderr)
        return 2
    if parse_issues or not all(isinstance(r, dict) for r in rows):
        for i in parse_issues:
            print(i)
        print("manifest has unparseable rows; fix them first", file=sys.stderr)
        return 1
    plan = assign_splits(records_from_rows(rows), config, freeze)
    out_rows = apply_plan(rows, plan) if plan.ok else []
    issues = list(plan.issues) + (leakage_report(out_rows)[0] if plan.ok else [])
    for i in issues:
        print(i)
    if _opt(argv, "--report"):
        _write_new(_opt(argv, "--report"), json.dumps(plan.report, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    if any(i.level == "error" for i in issues):
        print("split assignment FAILED; nothing written", file=sys.stderr)
        return 1
    out = _opt(argv, "--out")
    if out is None:
        print("--out is required", file=sys.stderr)
        return 2
    _write_new(out, "".join(json.dumps({f: r[f] for f in FIELDS} | {k: v for k, v in r.items() if k not in FIELDS},
                                       ensure_ascii=False) + "\n" for r in out_rows))
    print(f"{out}: {len(out_rows)} rows; " + ", ".join(f"{s} {v['rows']}" for s, v in plan.report["splits"].items()))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        raise SystemExit(main(sys.argv[1:]))
    except FileExistsError as e:
        print(e, file=sys.stderr)
        raise SystemExit(2)
