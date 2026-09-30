"""Source registry + licence gate tests (registry.py, adapters.check_registered). The bundled
registry is checked for documented values only; enforcement is tested with toy entries.
No dataset is read or downloaded. Same check() style.

    python asr_bench/test_registry.py
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.adapters import (AdapterContractError, DatasetAdapter, SourceInfo, SourceUtterance, build_row, build_rows,
                                check_registered)
from asr_bench.registry import RegistryError, SourceRegistry, gate_status, readiness_report

passed = 0
failed = 0


def check(name: str, condition: bool, detail="") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


# --- the bundled registry: documented values, nothing authorised ---------------------------------
REG = SourceRegistry.load()
PHASE_2A_SOURCES = {"indicvoices", "indicvoices_te_en", "vaani", "vaani_noise_event", "mucs2021_hien", "mucs2021_bnen",
                    "kathbath", "lahaja", "svarah", "fsd50k", "ami", "berst", "gram_vaani", "notsofar1", "phase0_prepped",
                    "phase0_real_recordings", "phase0_youtube_dev", "phase0_telugu_own",
                    "collected_safety", "collected_overlap"}
check("bundled registry loads, version 2 (R-4 split, FSD50K per-clip)", REG.version == 2)
check("old combined ID phase0_sets is gone", "phase0_sets" not in REG.sources)
check("every Phase 2A source is registered", set(REG.sources) == PHASE_2A_SOURCES, sorted(set(REG.sources) ^ PHASE_2A_SOURCES))
check("acquisition_authorised is false for every source", not any(e["acquisition_authorised"] for e in REG.sources.values()))
check("gated sources with unread gate terms are blocked",
      all(REG.sources[s]["use_restriction"] == "blocked" for s in ("indicvoices", "indicvoices_te_en", "vaani", "vaani_noise_event")))
check("collected sources (not collected, consent under review) are blocked",
      all(REG.sources[s]["use_restriction"] == "blocked" for s in ("collected_safety", "collected_overlap")))
check("no unresolved / permission-required / unread-gate licence is train_ok",
      not [s for s, e in REG.sources.items() if e["use_restriction"] == "train_ok" and
           any(k in e["licence"] for k in ("Unresolved", "Requires permission", "unread", "under review"))])
check("documented statuses kept verbatim",
      REG.sources["kathbath"]["licence"] == "Verified usable (CC0 packaging)"
      and REG.sources["svarah"]["licence"] == "Unresolved"
      and REG.sources["mucs2021_hien"]["speaker_metadata"] == "NOT VERIFIED"
      and REG.sources["indicvoices"]["english_word_script"] == "NOT VERIFIED"
      and REG.sources["vaani_noise_event"]["speaker_metadata"] == "NOT VERIFIED")
PHASE0 = ("phase0_prepped", "phase0_real_recordings", "phase0_youtube_dev", "phase0_telugu_own")
check("all four Phase 0 sets are eval_only, family phase0 (never train, Phase 1 §18)",
      all(REG.sources[s]["use_restriction"] == "eval_only" and REG.sources[s]["family"] == "phase0" for s in PHASE0))
check("Phase 0 sets keep distinct licence status (YouTube: video licences unknown; Telugu: own)",
      "video licences unknown" in REG.sources["phase0_youtube_dev"]["licence"] and REG.sources["phase0_telugu_own"]["licence"] == "Own / eval"
      and "licence not documented" in REG.sources["phase0_real_recordings"]["licence"])
check("FSD50K requires per-clip licence + use_restriction", REG.sources["fsd50k"].get("per_item_restriction_required") is True)
check("only FSD50K is per-item (no other source changed)",
      [s for s, e in REG.sources.items() if e.get("per_item_restriction_required")] == ["fsd50k"])
check("R-5 left unresolved: Vaani Noise Event keeps its own family", REG.sources["vaani_noise_event"]["family"] == "vaani_noise_event")
check("IndicVoices and its Te-En slice share a family", REG.sources["indicvoices"]["family"] == REG.sources["indicvoices_te_en"]["family"])
rep = readiness_report(REG)
check("readiness: no source may run an adapter today", not any(s["adapter_may_run"] for s in rep["sources"].values()))
check("readiness: documented blockers are carried", rep["sources"]["indicvoices_te_en"]["documented_blockers"][1].startswith("Phase 2A §8.3"))
check("readiness report is deterministic", readiness_report(SourceRegistry.load()) == rep)

# --- registry validation ------------------------------------------------------------------------------
ENTRY = {"name": "t", "family": "toy", "intended_use": "test", "acquisition_status": "toy", "licence": "toy licence",
         "gate_status": "toy", "use_restriction": "train_ok", "acquisition_authorised": True, "blockers": []}


def reg(**entries) -> dict:
    return {"format": "asr_bench.source_registry/1", "registry_version": 1, "sources": entries}


bad = {
    "wrong format": {**reg(toy=ENTRY), "format": "x"},
    "boolean version": {**reg(toy=ENTRY), "registry_version": True},
    "no sources": reg(),
    "id with ':'": reg(**{"to:y": ENTRY}),
    "missing field": reg(toy={k: v for k, v in ENTRY.items() if k != "gate_status"}),
    "empty licence": reg(toy={**ENTRY, "licence": ""}),
    "unknown use_restriction": reg(toy={**ENTRY, "use_restriction": "research"}),
    "non-boolean authorisation": reg(toy={**ENTRY, "acquisition_authorised": "yes"}),
    "blockers not a list": reg(toy={**ENTRY, "blockers": "none"}),
    "non-boolean per_item_restriction_required": reg(toy={**ENTRY, "per_item_restriction_required": "yes"}),
}
for name, raw in bad.items():
    check(f"invalid registry rejected: {name}", raises(lambda raw=raw: SourceRegistry.from_dict(raw), RegistryError))
check("registry digest changes with content",
      SourceRegistry.from_dict(reg(toy=ENTRY)).sha256 != SourceRegistry.from_dict(reg(toy={**ENTRY, "licence": "other"})).sha256)
check("gate_status: authorised + blocked cannot run an adapter",
      gate_status({**ENTRY, "use_restriction": "blocked"})["adapter_may_run"] is False)

# --- enforcement in adapters ---------------------------------------------------------------------------
TOY = SourceRegistry.from_dict(reg(toy=ENTRY, toynope={**ENTRY, "acquisition_authorised": False},
                                   toyev={**ENTRY, "licence": "toy eval licence", "use_restriction": "eval_only"},
                                   toyclip={**ENTRY, "licence": "toy per-clip", "per_item_restriction_required": True}))
SRC = SourceInfo("toy", "0", "toy licence", "train_ok")
check("registered + authorised + matching SourceInfo passes the gate", not raises(lambda: check_registered(SRC, TOY), AdapterContractError))
check("unregistered source -> rejected", raises(lambda: check_registered(SourceInfo("other", "0", "toy licence", "train_ok"), TOY), AdapterContractError))
check("registered but not authorised -> rejected",
      raises(lambda: check_registered(SourceInfo("toynope", "0", "toy licence", "train_ok"), TOY), AdapterContractError))
check("licence disagreeing with the registry -> rejected",
      raises(lambda: check_registered(SourceInfo("toy", "0", "CC0", "train_ok"), TOY), AdapterContractError))
check("use_restriction disagreeing with the registry (relaxing) -> rejected",
      raises(lambda: check_registered(SourceInfo("toyev", "0", "toy eval licence", "train_ok"), TOY), AdapterContractError))
check("use_restriction disagreeing with the registry (tightening) -> rejected too (must match exactly)",
      raises(lambda: check_registered(SourceInfo("toy", "0", "toy licence", "eval_only"), TOY), AdapterContractError))
check("default (bundled) registry: a real source is refused (not authorised)",
      raises(lambda: check_registered(SourceInfo("kathbath", "0", "Verified usable (CC0 packaging)", "train_ok")), AdapterContractError))
check("default registry: a toy source is refused (unregistered)", raises(lambda: check_registered(SRC), AdapterContractError))

tmp = Path(tempfile.mkdtemp(prefix="asr_bench_reg_"))
try:
    with wave.open(str(tmp / "a.wav"), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(bytes(3200))

    def utt(**c) -> SourceUtterance:
        base = dict(source_utt_id="1", audio_path="a.wav", speaker_id="toy:s1", session_id=None, recording_id=None,
                    transcript_ref="help me", transcript_romanised=None, tokens=None, language_primary="en-IN",
                    languages_present=["en-IN"], is_code_switched=False, cmi=None, script="Latn", english_word_script=None,
                    provenance="read", environment="quiet", condition_device="close", condition_real_or_synthetic="real",
                    aug_recipe=None, seed=None, snr_db=None, clipping_ratio=None, overlap=False, overlap_spans=None,
                    overlap_rel_db=None, safety_tags=None, keyword_spans=None, licence=None, use_restriction=None)
        base.update(c)
        return SourceUtterance(**base)

    row = build_row(SRC, utt(), split="dev", audio_root=tmp, registry=TOY)
    check("build_row with an authorised registered source builds a row", row["licence"] == "toy licence")
    check("build_row refuses an unauthorised source before reading any audio",
          raises(lambda: build_row(SourceInfo("toynope", "0", "toy licence", "train_ok"), utt(speaker_id="toynope:s1",
                                   audio_path="missing.wav"), split="dev", audio_root=tmp, registry=TOY), AdapterContractError))
    check("build_row without a registry argument uses the bundled one (toy refused)",
          raises(lambda: build_row(SRC, utt(), split="dev", audio_root=tmp), AdapterContractError))
    check("monotone P-S2-3 rule still applies with the registry (utterance relaxing eval_only -> rejected)",
          raises(lambda: build_row(SourceInfo("toyev", "0", "toy eval licence", "eval_only"),
                                   utt(speaker_id="toyev:s1", use_restriction="train_ok"), split="test", audio_root=tmp,
                                   registry=TOY), AdapterContractError))

    CLIP = SourceInfo("toyclip", "0", "toy per-clip", "train_ok")
    check("per-item source: clip without its own licence/use_restriction -> rejected (source train_ok is only a ceiling)",
          raises(lambda: build_row(CLIP, utt(speaker_id="toyclip:s1"), split="dev", audio_root=tmp, registry=TOY), AdapterContractError))
    check("per-item source: clip with licence but no use_restriction -> rejected",
          raises(lambda: build_row(CLIP, utt(speaker_id="toyclip:s1", licence="CC0"), split="dev", audio_root=tmp, registry=TOY), AdapterContractError))
    nc = build_row(CLIP, utt(speaker_id="toyclip:s1", licence="CC-BY-NC", use_restriction="eval_only"), split="test", audio_root=tmp, registry=TOY)
    check("per-item source: NC clip recorded as eval_only", (nc["licence"], nc["use_restriction"]) == ("CC-BY-NC", "eval_only"))
    cc0 = build_row(CLIP, utt(speaker_id="toyclip:s2", licence="CC0", use_restriction="train_ok"), split="train", audio_root=tmp, registry=TOY)
    check("per-item source: explicit train_ok clip allowed (within the ceiling)", cc0["use_restriction"] == "train_ok")
    check("per-item source: eval_only clip still cannot be placed in train (schema)",
          raises(lambda: build_row(CLIP, utt(speaker_id="toyclip:s3", licence="CC-BY-NC", use_restriction="eval_only"),
                                   split="train", audio_root=tmp, registry=TOY), Exception))
    check("non-per-item sources are unaffected (utterance values stay optional)",
          build_row(SRC, utt(), split="dev", audio_root=tmp, registry=TOY)["licence"] == "toy licence")

    class Unauthorised(DatasetAdapter):
        source = SourceInfo("toynope", "0", "toy licence", "train_ok")

        def utterances(self):
            yield utt(speaker_id="toynope:s1")

    check("build_rows refuses an unauthorised source outright (not one failure per utterance)",
          raises(lambda: build_rows(Unauthorised(), lambda u: "dev", audio_root=tmp, registry=TOY), AdapterContractError))

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "asr_bench.registry", *args], capture_output=True, text=True, cwd=HERE.parent)

    r = cli("report")
    check("CLI report: exit 0, lists every source", r.returncode == 0 and all(s in r.stdout for s in PHASE_2A_SOURCES), r.stdout + r.stderr)
    r = cli("report", "--json")
    check("CLI report --json parses", r.returncode == 0 and set(json.loads(r.stdout)["sources"]) == PHASE_2A_SOURCES)
    broken = tmp / "broken.json"
    broken.write_text(json.dumps({**reg(toy=ENTRY), "format": "x"}), encoding="utf-8")
    check("CLI report on an invalid registry exits 2", cli("report", "--registry", str(broken)).returncode == 2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
