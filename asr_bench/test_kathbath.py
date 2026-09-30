"""Kathbath adapter tests. The package used here is a GENERATED FIXTURE with a HYPOTHETICAL layout
(the real layout has not been inspected: see configs/kathbath_layout.TEMPLATE.json); only the
adapter's rules are tested, not Kathbath's real structure. The real registry entry is used
unchanged for the gate checks; the ingestion checks use a copy with only
acquisition_authorised flipped. .m4a checks need PyAV (SKIP otherwise). check() style.

    python asr_bench/test_kathbath.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.adapters import AdapterContractError, check_registered
from asr_bench.ingest import ingest, slice_readiness
from asr_bench.kathbath_adapter import KathbathAdapter, LayoutError, load_layout
from asr_bench.registry import SourceRegistry
from asr_bench.scoring import BenchmarkConfig
from asr_bench.splits import SplitConfig, leakage_report

passed = failed = skipped = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


LAYOUT = {  # HYPOTHETICAL fixture layout -- not Kathbath's real one
    "format": "asr_bench.kathbath_layout/1", "source_version": "fixture-0", "inspected_from": "test fixture",
    "audio_glob": "*/audio/*.m4a", "language_path_index": 0, "language_map": {"hindi": "hi", "telugu": "te"},
    "speaker_regex": r"^(?P<speaker>spk\d+)_", "transcripts": {"glob": "*/transcripts.tsv", "format": "tsv", "key": "stem",
                                                              "id_field": "file", "text_field": "text"}}
TEXT = {"hindi": ["मुझे मदद चाहिए", "यह एक वाक्य है"], "telugu": ["నన్ను వదలండి", "ఇది ఒక వాక్యం"]}

# --- layout spec ------------------------------------------------------------------------------------
tmpl = json.loads((HERE / "configs" / "kathbath_layout.TEMPLATE.json").read_text(encoding="utf-8"))
check("the shipped template is refused (nothing inspected yet)", raises(lambda: load_layout(tmpl), LayoutError))
check("a filled layout is accepted", load_layout(LAYOUT)["source_version"] == "fixture-0")
check("speaker_regex without a (?P<speaker>) group is refused", raises(lambda: load_layout({**LAYOUT, "speaker_regex": r"spk\d+"}), LayoutError))
check("unknown transcript format is refused",
      raises(lambda: load_layout({**LAYOUT, "transcripts": {**LAYOUT["transcripts"], "format": "xml"}}), LayoutError))
check("split config: kathbath uses the hash policy with the provisional 0.70/0.10/0.10/0.10 ratios",
      SplitConfig.load(HERE / "configs" / "phase2a_split_config.json").sources["kathbath"]["ratios"]
      == {"train": 0.70, "dev": 0.10, "test": 0.10, "final_test": 0.10})

# --- registry gate with the REAL entry -------------------------------------------------------------------
REAL = SourceRegistry.load()
tmp = Path(tempfile.mkdtemp(prefix="asr_bench_kathbath_"))
try:
    ad = KathbathAdapter(tmp, LAYOUT)
    check("the real registry refuses Kathbath today (acquisition not authorised)",
          raises(lambda: check_registered(ad.source), AdapterContractError))
    raw = json.loads((HERE / "source_registry.json").read_text(encoding="utf-8"))
    check("the real registry still says acquisition_authorised = false", raw["sources"]["kathbath"]["acquisition_authorised"] is False)
    authorised = copy.deepcopy(raw)
    authorised["sources"]["kathbath"]["acquisition_authorised"] = True
    AUTH = SourceRegistry.from_dict(authorised)
    check("the adapter's licence + use_restriction agree with the real registry entry (only the flag differs)",
          check_registered(ad.source, AUTH)["licence"] == "Verified usable (CC0 packaging)")

    # --- fixture package ------------------------------------------------------------------------------
    try:
        import av
    except ImportError:
        av = None
    lines = {}
    for lang, texts in TEXT.items():
        (tmp / lang / "audio").mkdir(parents=True)
        rows = ["file\ttext"]
        for s in range(4):
            for u, t in enumerate(texts):
                name = f"spk{s:04d}_{lang[:2]}{u}"
                rows.append(f"{name}.m4a\t{t}")
                lines[name] = t
        (tmp / lang / "transcripts.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (tmp / "bengali" / "audio").mkdir(parents=True)
    extra = [tmp / "hindi" / "audio" / "spk0009_notext.m4a", tmp / "bengali" / "audio" / "spk0001_bn0.m4a",
             tmp / "hindi" / "audio" / "nospeaker.m4a"]

    def make_m4a(path: Path, n: int, rate: int = 16000, variant: int = 0) -> None:
        with av.open(str(path), "w", format="mp4") as out:
            st = out.add_stream("aac", rate=rate, layout="mono")
            for i in range(0, n, 1024):
                fr = av.AudioFrame(format="s16", layout="mono", samples=1024)
                fr.planes[0].update(struct.pack("<1024h", *((i + k) % (300 + 7 * variant) - 150 for k in range(1024))))
                fr.sample_rate, fr.pts = rate, i
                for p in st.encode(fr):
                    out.mux(p)
            for p in st.encode(None):
                out.mux(p)

    if av is None:
        for f in [tmp / lang / "audio" / f"{n}.m4a" for n in lines for lang in TEXT if n.split("_")[1][:2] == lang[:2]] + extra:
            f.write_bytes(b"\x00placeholder")  # layout-only checks; never read as audio without PyAV
    else:
        for i, n in enumerate(sorted(lines)):
            make_m4a(tmp / ("hindi" if "_hi" in n else "telugu") / "audio" / f"{n}.m4a", 16000, variant=i)
        for j, f in enumerate(extra):
            make_m4a(f, 16000, variant=100 + j)
    (tmp / "hindi" / "audio" / "spk0000_hi0.wav").write_bytes(b"not used")

    utts = list(ad.utterances())
    probs = dict(ad.problems)
    check("one utterance per audio file with transcript + language + speaker", len(utts) == 16, len(utts))
    u0 = next(u for u in utts if u.source_utt_id.endswith("spk0000_hi0"))
    check("original .m4a is the audio path (relative to the Kathbath root)", u0.audio_path == "hindi/audio/spk0000_hi0.m4a")
    check("speaker namespaced kathbath:<speaker from file name>; no invented session/recording",
          (u0.speaker_id, u0.session_id, u0.recording_id) == ("kathbath:spk0000", None, None))
    check("language from the folder; script measured from the transcript",
          (u0.language_primary, u0.languages_present, u0.script) == ("hi", ["hi"], "Deva")
          and next(u for u in utts if u.language_primary == "te").script == "Telu")
    check("only documented/measured metadata: read, unknown environment/device/English script, no tokens/CMI/safety",
          (u0.provenance, u0.environment, u0.condition_device, u0.english_word_script, u0.tokens, u0.cmi, u0.safety_tags)
          == ("read", "unknown", "unknown", "unknown", None, None, None) and u0.is_code_switched is False)
    check("missing transcript recorded as a problem, not filled", probs.get("hindi/audio/spk0009_notext.m4a") == "no transcript")
    check("unmapped language folder recorded as a problem", "not in language_map" in probs.get("bengali/audio/spk0001_bn0.m4a", ""))
    check("file name without a speaker recorded as a problem", "speaker_regex" in probs.get("hindi/audio/nospeaker.m4a", ""))
    check("non-.m4a files are not picked up by the documented audio format", not any(u.audio_path.endswith(".wav") for u in utts))

    if av is None:
        for n in ("ingest m4a with exact file hash + decoded duration", "leakage + slice readiness on ingested rows"):
            skip(n, "PyAV not installed here")
    else:
        split_cfg = SplitConfig.load(HERE / "configs" / "phase2a_split_config.json")
        check("ingest with the REAL registry is refused", raises(lambda: ingest(ad, split_cfg, tmp, REAL), AdapterContractError))
        rows, rep = ingest(ad, split_cfg, tmp, AUTH)
        r0 = next(r for r in rows if r["utt_id"] == "kathbath:hindi/audio/spk0000_hi0")
        check("ingest (authorised copy): all 16 rows built", len(rows) == 16 and rep["failures"] == [], rep["failures"][:2])
        check("audio_sha256 = exact .m4a bytes", r0["audio_sha256"] == hashlib.sha256((tmp / r0["audio_path"]).read_bytes()).hexdigest())
        check("duration from decoded samples at the original rate (16000 samples -> ~1.0 s, AAC frame padding included)",
              r0["sample_rate_hz"] == 16000 and 1.0 <= r0["duration_s"] <= 1.2, (r0["sample_rate_hz"], r0["duration_s"]))
        check("licence + restriction copied from the registry", (r0["licence"], r0["use_restriction"]) == ("Verified usable (CC0 packaging)", "train_ok"))
        check("each speaker's utterances in one split; leakage-clean",
              not [i for i in leakage_report(rows)[0] if i.level == "error"])
        sr = slice_readiness(rows, BenchmarkConfig.load(HERE / "examples" / "toy_benchmark_config.json").raw["slice_minimums"])
        check("slice readiness reports the fixture's tiny slices as UNAVAILABLE with reasons",
              sr["hindi"]["status"].startswith("UNAVAILABLE") and sr["telugu"]["status"].startswith("UNAVAILABLE"))

    env = {**os.environ, "KATHBATH_ROOT": str(tmp), "KATHBATH_LAYOUT": str(tmp / "layout.json")}
    (tmp / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "asr_bench.ingest", "build", "--adapter", "asr_bench.kathbath_adapter:from_env",
                        "--split-config", str(HERE / "configs" / "phase2a_split_config.json"), "--audio-root", str(tmp),
                        "--out", str(tmp / "m.jsonl")], capture_output=True, text=True, cwd=HERE.parent, env=env)
    check("CLI ingest with the real registry is refused and writes nothing", r.returncode == 1 and not (tmp / "m.jsonl").exists(),
          r.stdout + r.stderr)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "")
      + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
