"""Manifest population (stage S9 plumbing): approved adapter -> registry gate -> split plan ->
build_rows -> S1 validation + S3 leakage report -> manifest JSONL; plus the §7 slice-minimum
check ("every slice meets its minimum speakers/hours, or is explicitly marked unavailable").

    python -m asr_bench.ingest build --adapter module:Class --split-config cfg.json --audio-root <dir>
                                     --out manifest.jsonl [--registry reg.json] [--report ingest_report.json]
    python -m asr_bench.ingest slices --manifest m.jsonl --config bench.json

Nothing is downloaded: the adapter reads files already on disk, and only a registered source whose
acquisition the owner authorised can produce rows (adapters.check_registered).
"""
from __future__ import annotations

import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.adapters import build_rows, check_registered
from asr_bench.registry import SourceRegistry
from asr_bench.schema import FIELDS
from asr_bench.splits import SplitConfig, assign_splits, leakage_report, records_from_utterances
from asr_bench.validate import read_jsonl


class IngestError(RuntimeError):
    pass


def ingest(adapter, split_config: SplitConfig, audio_root, registry: SourceRegistry | None = None) -> tuple[list[dict], dict]:
    src = adapter.source
    check_registered(src, registry)
    utts = list(adapter.utterances())
    plan = assign_splits(records_from_utterances(src, utts), split_config)
    if not plan.ok:
        raise IngestError("split plan has errors: " + "; ".join(str(i) for i in plan.issues if i.level == "error"))

    class _Fixed:
        source = src

        def utterances(self):
            return iter(utts)

    rows, failures = build_rows(_Fixed(), plan.split_for(src), audio_root=audio_root, registry=registry)
    issues, leak = leakage_report(rows)
    report = {"source_dataset": src.source_dataset, "utterances": len(utts), "rows": len(rows),
              "failures": [{"source_utt_id": u, "error": f"{type(e).__name__}: {e}"} for u, e in failures],
              "leakage": leak, "issues": [str(i) for i in issues], "split_plan": plan.report}
    if any(i.level == "error" for i in issues):
        raise IngestError(f"leakage/validation errors: {[str(i) for i in issues if i.level == 'error'][:5]}")
    return rows, report


def slice_readiness(rows: list[dict], minimums: dict) -> dict:
    """Per configured slice: speakers + hours in the benchmark splits vs the §4 minimum. A slice
    rule matches rows by language_primary / is_code_switched (N-7, provisional)."""
    out = {}
    for name, rule in sorted(minimums.items()):
        sel = [r for r in rows if r.get("split") in ("test", "final_test")
               and all(r.get(k) == v for k, v in rule.get("match", {}).items())]
        spk = {r["speaker_id"] for r in sel if r.get("speaker_id")}
        hours = sum(r.get("duration_s", 0) for r in sel) / 3600
        reasons = []
        if len(spk) < rule.get("min_speakers", 0):
            reasons.append(f"{len(spk)} speakers < {rule['min_speakers']}")
        if hours < rule.get("min_hours", 0):
            reasons.append(f"{hours:.2f} h < {rule['min_hours']} h")
        out[name] = {"speakers": len(spk), "hours": round(hours, 4), "items": len(sel),
                     "status": "meets minimum" if not reasons else "UNAVAILABLE: " + "; ".join(reasons),
                     "sources": sorted({r["source_dataset"] for r in sel})}
    return out


def main(argv: list[str]) -> int:
    def opt(n):
        return argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else None

    if argv[:1] == ["slices"] and opt("--manifest") and opt("--config"):
        from asr_bench.scoring import BenchmarkConfig
        parsed, _ = read_jsonl(Path(opt("--manifest")))
        rep = slice_readiness([r for _, r in parsed], BenchmarkConfig.load(opt("--config")).raw["slice_minimums"])
        print(json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False))
        return 0 if all(v["status"] == "meets minimum" for v in rep.values()) else 1
    if argv[:1] != ["build"] or not (opt("--adapter") and opt("--split-config") and opt("--audio-root") and opt("--out")):
        print(__doc__.strip().splitlines()[4].strip(), file=sys.stderr)
        return 2
    out = Path(opt("--out"))
    if out.exists():
        print(f"{out} exists; refusing to overwrite", file=sys.stderr)
        return 2
    try:
        mod, cls = opt("--adapter").split(":", 1)
        adapter = getattr(importlib.import_module(mod), cls)()
        reg = SourceRegistry.load(opt("--registry")) if opt("--registry") else None
        rows, rep = ingest(adapter, SplitConfig.load(opt("--split-config")), opt("--audio-root"), reg)
    except Exception as e:
        print(f"ingest refused: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out.write_text("".join(json.dumps({f: r[f] for f in FIELDS}, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    if opt("--report"):
        Path(opt("--report")).write_text(json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out}: {len(rows)} rows, {len(rep['failures'])} failures")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
