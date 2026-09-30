"""ASR benchmark runner (Phase 2A §6.6–6.7, stage S7): transcribe the eligible rows of one split
with one engine, and record per-utterance output, CPU time and real-time factor, plus the
reproducibility metadata needed to rebuild the run.

    python -m asr_bench.runner --manifest m.jsonl --split dev --engine phase0_whisper_small_en
        --input-unit utterance --audio-root <source>=<dir> [...] --out run.jsonl
        [--device cpu] [--hardware-class c7i.2xlarge] [--freeze freeze.json --split-config cfg.json]

- Engines: the frozen Phase 0 engines (Whisper small.en with language="en", Parakeet TDT 0.6B v2)
  through the production stt.py classes, unchanged. A candidate is "module:factory" returning an
  STTBackend; none is chosen here (Q5). A backend that fails to load is an error -- never the
  silent MockSTT fallback Phase 0 found in api.py.
- --input-unit is required: "utterance" (whole utterance to the engine) or "vad" (the frozen
  vad.VAD segments, transcripts joined). Which one the benchmark uses is Q4 (open).
- Rows come only from eligibility.select_eligible(split). final_test needs a freeze that verifies
  against the manifest (§6.2) and the split config it was frozen with.
- RTF = processing seconds / audio seconds, per utterance, measured on this machine. A
  --hardware-class label is recorded as declared, not verified.
- Resumable: utterances already in --out are skipped. Metadata goes to <out>.meta.json.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr_bench.eligibility import select_eligible
from asr_bench.schema import SPLITS
from asr_bench.validate import read_jsonl, validate_rows

REPO = Path(__file__).resolve().parent.parent
INPUT_UNITS = ("utterance", "vad")
FROZEN_ENGINES = ("phase0_whisper_small_en", "phase0_parakeet_tdt_0.6b_v2")
PACKAGES = ("faster-whisper", "ctranslate2", "onnx-asr", "onnxruntime", "onnxruntime-gpu", "numpy", "torch", "av",
            "webrtcvad", "webrtcvad-wheels")


class RunnerError(RuntimeError):
    pass


def load_engine(name: str, device: str = "cpu"):
    """The frozen Phase 0 engines, or 'module:factory' for a candidate. Load failure is fatal."""
    try:
        if name == "phase0_whisper_small_en":
            from stt import FasterWhisperSTT
            engine = FasterWhisperSTT(model_size="small.en", device=device, compute_type="float16" if device == "cuda" else "int8")
        elif name == "phase0_parakeet_tdt_0.6b_v2":
            from stt import ParakeetSTT
            engine = ParakeetSTT(device=device)
        elif ":" in name:
            mod, fn = name.split(":", 1)
            engine = getattr(importlib.import_module(mod), fn)()
        else:
            raise RunnerError(f"unknown engine {name!r}: use one of {FROZEN_ENGINES} or 'module:factory'")
    except RunnerError:
        raise
    except Exception as e:
        raise RunnerError(f"engine {name!r} failed to load ({type(e).__name__}: {e}); no fallback is used") from e
    version = getattr(engine, "model_version", None)
    if not isinstance(version, str) or version.startswith("mock"):
        raise RunnerError(f"engine {name!r} reports model_version {version!r}: a mock/unknown backend is never benchmarked")
    return engine


def decode_pcm16k(path: Path) -> bytes:
    """16 kHz mono int16 PCM for the engines (the 'derived 16 kHz copy' of §3, made on the fly)."""
    try:
        import numpy as np
        from faster_whisper import decode_audio
        return (np.clip(decode_audio(str(path), sampling_rate=16000), -1, 1) * 32767).astype("<i2").tobytes()
    except ImportError:
        pass
    import wave
    try:
        with wave.open(str(path), "rb") as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2):
                return w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        pass
    try:
        import av
    except ImportError as e:
        raise RunnerError(f"{path}: needs faster-whisper or PyAV to decode/resample to 16 kHz mono") from e
    out = bytearray()
    with av.open(str(path)) as c:
        rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in c.decode(c.streams.audio[0]):
            for f in rs.resample(frame):
                out += bytes(f.planes[0])[: f.samples * 2]
        for f in rs.resample(None):
            out += bytes(f.planes[0])[: f.samples * 2]
    return bytes(out)


def transcribe(engine, pcm: bytes, unit: str, vad=None) -> str:
    if unit == "utterance":
        return engine.transcribe(pcm).text.strip()
    if vad is None:
        from vad import VAD
        vad = VAD()
    return " ".join(t for t in (engine.transcribe(s.pcm).text.strip() for s in vad.segment_speech(pcm)) if t)


def _sha_file(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p and p.exists() else None


def repro_metadata(engine_name: str, engine, device: str, unit: str, manifest: Path, split: str,
                   hardware_class: str | None, freeze_sha: str | None) -> dict:
    head = REPO / ".git" / "HEAD"
    commit = None
    try:
        ref = head.read_text().strip()
        commit = (REPO / ".git" / ref[5:]).read_text().strip() if ref.startswith("ref: ") else ref
    except OSError:
        pass
    cpu = None
    try:
        cpu = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
    except OSError:
        pass
    pkgs = {}
    for p in PACKAGES:
        try:
            pkgs[p] = importlib.metadata.version(p)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {"engine": engine_name, "model_version": engine.model_version, "device": device, "input_unit": unit,
            "split": split, "manifest": str(manifest), "manifest_sha256": _sha_file(manifest), "final_test_freeze_sha256": freeze_sha,
            "git_commit": commit, "python": sys.version.split()[0], "platform": platform.platform(), "cpu_model": cpu,
            "cpu_count": os.cpu_count(), "hardware_class_declared": hardware_class, "hardware_class_verified": False,
            "packages": pkgs, "pythonhashseed": os.environ.get("PYTHONHASHSEED")}


def peak_rss_mb() -> float | None:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # Linux: KiB
    except (ImportError, AttributeError):
        return None


def run(rows: list[dict], split: str, engine, engine_name: str, unit: str, roots: dict, out: Path, meta: dict,
        vad=None) -> dict:
    if unit not in INPUT_UNITS:
        raise RunnerError(f"--input-unit must be one of {INPUT_UNITS} (Q4 is open; no default)")
    if split not in SPLITS:
        raise RunnerError(f"unknown split {split!r}")
    errors = [i for i in validate_rows(list(enumerate(rows, 1))) if i.level == "error"]
    if errors:
        raise RunnerError(f"manifest has {len(errors)} validation errors; run the S1 validator first")
    eligible, rejected = select_eligible(rows, split)
    done = set()
    if out.exists():
        done = {json.loads(l)["utt_id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    n_new = n_err = 0
    with open(out, "a", encoding="utf-8") as f:
        for r in sorted(eligible, key=lambda r: r["utt_id"]):
            if r["utt_id"] in done:
                continue
            rec = {"utt_id": r["utt_id"], "engine": engine_name, "model_version": engine.model_version, "split": split,
                   "input_unit": unit, "audio_s": r["duration_s"]}
            root = roots.get(r["source_dataset"])
            try:
                if root is None:
                    raise RunnerError(f"no audio root for source {r['source_dataset']!r}")
                pcm = decode_pcm16k(Path(root) / r["audio_path"])
                t0 = time.perf_counter()
                rec["hyp"] = transcribe(engine, pcm, unit, vad)
                rec["proc_s"] = time.perf_counter() - t0
                rec["rtf"] = rec["proc_s"] / r["duration_s"]
            except Exception as e:  # recorded per utterance, never silently dropped
                rec["error"] = f"{type(e).__name__}: {e}"
                n_err += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_new += 1
    meta = {**meta, "eligible": len(eligible), "rejected_not_eligible": len(rejected), "new_records": n_new,
            "errors": n_err, "peak_rss_mb": peak_rss_mb()}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def main(argv: list[str]) -> int:
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

    need = [opt("--manifest"), opt("--split"), opt("--engine"), opt("--input-unit"), opt("--out")]
    if None in need:
        print(__doc__.strip().splitlines()[4].strip(), file=sys.stderr)
        return 2
    manifest, split, engine_name, unit, out = Path(need[0]), need[1], need[2], need[3], Path(need[4])
    roots = dict(a.split("=", 1) for i, a in enumerate(argv) if i and argv[i - 1] == "--audio-root" and "=" in a)
    parsed, parse_issues = read_jsonl(manifest)
    if parse_issues:
        print("manifest has unparseable lines", file=sys.stderr)
        return 1
    rows = [r for _, r in parsed]
    freeze_sha = None
    if split == "final_test":
        from asr_bench.freeze import load_freeze, verify_freeze
        from asr_bench.splits import SplitConfig
        if not (opt("--freeze") and opt("--split-config")):
            print("final_test runs need --freeze and --split-config (§6.2)", file=sys.stderr)
            return 2
        fz = load_freeze(opt("--freeze"))
        problems = verify_freeze(rows, fz, SplitConfig.load(opt("--split-config")))
        if problems:
            for p in problems:
                print(p)
            print("freeze does not verify: final_test run refused", file=sys.stderr)
            return 1
        freeze_sha = fz["freeze_sha256"]
    device = opt("--device", "cpu")
    try:
        engine = load_engine(engine_name, device)
        meta = repro_metadata(engine_name, engine, device, unit, manifest, split, opt("--hardware-class"), freeze_sha)
        meta = run(rows, split, engine, engine_name, unit, roots, out, meta)
    except RunnerError as e:
        print(f"runner error: {e}", file=sys.stderr)
        return 1
    print(f"{out}: {meta['new_records']} new records ({meta['errors']} errors), {meta['eligible']} eligible in {split}")
    return 0 if meta["errors"] == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
