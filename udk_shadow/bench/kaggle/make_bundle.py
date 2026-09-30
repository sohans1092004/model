"""Build the Kaggle upload: a zip with the live modules the benchmark executes, the shadow runtime, the benchmark,
the shadow tests, the Kaggle runner and (optionally) offline wheels. No model weights, no data, no secrets.

    python udk_shadow/bench/kaggle/make_bundle.py <out.zip> [--wheels <dir with .whl files>]
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOP = "udk_shadow_gpu_bench"
FILES = [
    # live modules executed by the benchmark (the live loop is extracted from api.py; engine / matcher / gate are the real classes)
    "api.py", "udk_engine.py", "udks.py", "semantic.py", "intent_gate.py", "beats_distress_detector.py", "kws.py", "scream_trigger.py",
    # shadow runtime (= the image whitelist) + tests + benchmark
    "udk_shadow/__init__.py", "udk_shadow/config.py", "udk_shadow/context.py", "udk_shadow/evidence.py", "udk_shadow/observation.py",
    "udk_shadow/processor.py", "udk_shadow/runner.py", "udk_shadow/selfcheck.py", "udk_shadow/report.py", "udk_shadow/test_shadow.py",
    "udk_shadow/bench/interference.py", "udk_shadow/bench/aggregate.py", "udk_shadow/bench/build_proxy_models.py",
    "udk_shadow/bench/kaggle/run_kaggle.py",
    "udk_fusion/__init__.py", "udk_fusion/engine.py", "udk_fusion/inputs.py", "udk_fusion/policy.py",
    "udk_fusion/configs/production_equivalent.json",
    "udk_context/__init__.py", "udk_context/context_window.py", "udk_context/decision.py", "udk_context/intent.py",
    "udk_context/negation.py", "udk_context/production_adapter.py", "udk_context/scene.py",
    "udk_context/configs/production_equivalent.json",
    "udk_signals/__init__.py", "udk_signals/acoustic.py", "udk_signals/evidence.py",
    "asr_bench/__init__.py", "asr_bench/textnorm.py",
]
README = """# UDK shadow-mode GPU interference benchmark (Kaggle)

Measures how much Phase 6 shadow mode slows the LIVE detection loop, shadow OFF vs ON, on a GPU.
Models are RANDOM-WEIGHT proxies with the production architectures (MiniLM-L12 semantic, mDeBERTa-v3-base intent);
STT/VAD/BEATs are stubbed. This measures interference only -- not detection quality.

## Run on Kaggle
1. Kaggle -> Datasets -> New Dataset -> upload this zip (Kaggle unzips it). Note the dataset name.
2. New Notebook -> Settings: Accelerator = GPU (T4 x1 or P100). Internet: optional (wheels are bundled).
3. Add the dataset to the notebook (Add Input), then run ONE cell:

```
import glob, subprocess, sys
runner = glob.glob('/kaggle/input/**/udk_shadow/bench/kaggle/run_kaggle.py', recursive=True)[0]
subprocess.run([sys.executable, runner], check=True)          # full run (~30-60 min on a T4)
# subprocess.run([sys.executable, runner, '--quick'], check=True)   # 2-5 min smoke run first, if you like
```

4. Download /kaggle/working/udk_shadow_gpu_results.zip (Output panel) and send it back.
   It contains RESULTS.md (table), runs/*.json (raw), environment.json, test_shadow.log, run.log.

Options: --quick (1 repeat, 32 segments), --with-cpu (also run the matrix on CPU), --reps N, --segments N,
--delays 0.0,0.5 (stubbed STT seconds per segment).

## Any other CUDA machine
    pip install torch transformers sentence-transformers rapidfuzz numpy
    python udk_shadow/bench/kaggle/run_kaggle.py --workdir ./out
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--wheels")
    a = ap.parse_args()
    missing = [f for f in FILES if not (ROOT / f).exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(ROOT / f, f"{TOP}/{f}")
        z.writestr(f"{TOP}/README_KAGGLE.md", README)
        if a.wheels:
            for w in sorted(Path(a.wheels).glob("*.whl")):
                z.write(w, f"{TOP}/wheels/{w.name}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
