"""Source registry + licence gate: which sources exist, what the documents say about them, and
whether the owner has authorised acquiring them.

    python -m asr_bench.registry report [--registry path.json] [--json]

The registry (source_registry.json, versioned) copies documented facts only; UNKNOWN / NOT
VERIFIED / unresolved values are kept as written, and no licence permission is inferred.
It is the record for sources that cannot yet be manifest rows (no audio to hash).

adapters.build_row refuses a source that is not registered, whose acquisition the owner has not
authorised, or whose SourceInfo licence / use_restriction disagree with its registry entry.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.schema import USE_RESTRICTION

REGISTRY_FORMAT = "asr_bench.source_registry/1"
DEFAULT_REGISTRY = Path(__file__).resolve().parent / "source_registry.json"
REQUIRED = ("name", "family", "intended_use", "acquisition_status", "licence", "gate_status",
            "use_restriction", "acquisition_authorised", "blockers")


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class SourceRegistry:
    version: int
    sources: dict  # source_dataset -> entry dict
    sha256: str

    @classmethod
    def from_dict(cls, raw) -> SourceRegistry:
        if not isinstance(raw, dict) or raw.get("format") != REGISTRY_FORMAT:
            raise RegistryError(f"registry format must be {REGISTRY_FORMAT!r}")
        version = raw.get("registry_version")
        if not (isinstance(version, int) and not isinstance(version, bool) and version >= 1):
            raise RegistryError("registry_version must be an integer >= 1")
        sources = raw.get("sources")
        if not (isinstance(sources, dict) and sources):
            raise RegistryError("sources must be a non-empty object")
        for sid, e in sources.items():
            where = f"sources[{sid!r}]"
            if not (isinstance(sid, str) and sid.strip()) or ":" in sid:
                raise RegistryError(f"{where}: id must be a non-empty string without ':' (it is the namespace)")
            if not isinstance(e, dict):
                raise RegistryError(f"{where}: must be an object")
            missing = [k for k in REQUIRED if k not in e]
            if missing:
                raise RegistryError(f"{where}: missing {missing}")
            for k in ("name", "family", "licence"):
                if not (isinstance(e[k], str) and e[k].strip()):
                    raise RegistryError(f"{where}: {k} must be a non-empty string")
            if e["use_restriction"] not in USE_RESTRICTION:
                raise RegistryError(f"{where}: use_restriction must be one of {USE_RESTRICTION}")
            if not isinstance(e["acquisition_authorised"], bool):
                raise RegistryError(f"{where}: acquisition_authorised must be true or false")
            if not isinstance(e["blockers"], list) or not all(isinstance(b, str) for b in e["blockers"]):
                raise RegistryError(f"{where}: blockers must be a list of strings")
            # Optional: the source's licence varies per item (e.g. FSD50K per clip), so every item
            # must carry its own licence + use_restriction; the source value is only the ceiling.
            if not isinstance(e.get("per_item_restriction_required", False), bool):
                raise RegistryError(f"{where}: per_item_restriction_required must be true or false")
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return cls(version, sources, digest)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_REGISTRY) -> SourceRegistry:
        try:
            return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise RegistryError(f"{path}: not valid JSON ({e.msg})") from e

    def entry(self, source_dataset: str) -> dict:
        if source_dataset not in self.sources:
            raise RegistryError(f"source {source_dataset!r} is not in the source registry (v{self.version})")
        return self.sources[source_dataset]


def gate_status(entry: dict) -> dict:
    """Independent gates that can be judged WITHOUT data (G0-G1 of the readiness review).
    Manifest / train / eval / final_test gates need audio and are checked by S1-S3 later."""
    usable = entry["use_restriction"] != "blocked"
    return {
        "registered": True,
        "acquisition_authorised": entry["acquisition_authorised"],
        "legally_usable_per_docs": usable,
        "train_permitted_per_docs": entry["use_restriction"] == "train_ok",
        "adapter_may_run": entry["acquisition_authorised"] and usable,
        "documented_blockers": list(entry["blockers"]),
    }


def readiness_report(reg: SourceRegistry) -> dict:
    return {"registry_version": reg.version, "registry_sha256": reg.sha256,
            "sources": {sid: {"name": e["name"], "family": e["family"], "use_restriction": e["use_restriction"],
                              **gate_status(e)} for sid, e in sorted(reg.sources.items())}}


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "report":
        print("usage: python -m asr_bench.registry report [--registry path.json] [--json]", file=sys.stderr)
        return 2
    path = argv[argv.index("--registry") + 1] if "--registry" in argv and argv.index("--registry") + 1 < len(argv) else DEFAULT_REGISTRY
    try:
        rep = readiness_report(SourceRegistry.load(path))
    except (OSError, RegistryError) as e:
        print(f"registry error: {e}", file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False))
        return 0
    print(f"source registry v{rep['registry_version']} ({rep['registry_sha256'][:12]})")
    for sid, s in rep["sources"].items():
        flags = ", ".join(k for k in ("acquisition_authorised", "legally_usable_per_docs", "train_permitted_per_docs",
                                      "adapter_may_run") if s[k]) or "none"
        print(f"  {sid:20} {s['use_restriction']:9} gates passed: {flags}; blockers: {len(s['documented_blockers'])}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
