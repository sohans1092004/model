"""One-command GPU run of the Phase 6C shadow-interference benchmark on Kaggle (or any CUDA machine).

What it does, in order (each step logs to results/run.log; a failing step is reported, later steps still run):
  0. copies the bundle to a writable dir if it sits in read-only /kaggle/input
  1. installs missing test-only dependencies (rapidfuzz, sentence-transformers) from the bundled wheels, falling
     back to pip over the internet
  2. environment report (GPU, torch, python)
  3. runs the shadow test suite (udk_shadow/test_shadow.py) as a sanity check of the bundle
  4. builds random-weight proxy models of the production architectures (build_proxy_models.py)
  5. runs the matrix: device x STT pacing x mode (off / on / on_lite) x repeats, one process per run
  6. aggregates to results/RESULTS.md and zips everything to <workdir>/udk_shadow_gpu_results.zip

Nothing here is a performance claim about UDK detection: the models have random weights and the workload is synthetic.
It measures only how much shadow mode interferes with the live loop on this hardware.

    python run_kaggle.py                 # full: cuda, STT 0.0 and 0.5 s, 3 repeats, 192 segments
    python run_kaggle.py --quick         # smoke: 1 repeat, 32 segments
    python run_kaggle.py --with-cpu      # also the same matrix on CPU (slower)
"""
from __future__ import annotations

import argparse
import datetime
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "api.py").exists() and (p / "udk_shadow").is_dir():
            return p
    raise SystemExit("bundle root (api.py + udk_shadow/) not found above " + str(HERE))


def log(msg: str, fh=None) -> None:
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if fh:
        fh.write(line + "\n"); fh.flush()


def ensure_deps(root: Path, fh) -> None:
    wheels = root / "wheels"
    for mod, pkg in (("rapidfuzz", "rapidfuzz"), ("sentence_transformers", "sentence-transformers"), ("transformers", "transformers")):
        try:
            importlib.import_module(mod)
            log(f"dependency ok: {mod}", fh)
            continue
        except ImportError:
            pass
        cmds = ([[sys.executable, "-m", "pip", "install", "-q", "--no-index", "--find-links", str(wheels), pkg]] if wheels.is_dir() else []) + \
               [[sys.executable, "-m", "pip", "install", "-q", pkg]]
        for c in cmds:
            r = subprocess.run(c, capture_output=True, text=True)
            if r.returncode == 0:
                log(f"installed {pkg} ({'bundled wheel' if '--no-index' in c else 'internet'})", fh)
                break
        else:
            log(f"WARNING: could not install {pkg}; enable Internet in the notebook settings. {r.stderr[-300:]}", fh)
        importlib.invalidate_caches()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--with-cpu", action="store_true")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--segments", type=int, default=192)
    ap.add_argument("--delays", default="0.0,0.5", help="stubbed STT seconds per segment (0.0 = no idle time, worst case)")
    ap.add_argument("--workdir", default="/kaggle/working" if Path("/kaggle/working").is_dir() else str(Path.cwd()))
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()
    if a.quick:
        a.reps, a.segments = 1, 32

    root = find_root()
    work = Path(a.workdir)
    if not os.access(root, os.W_OK) or str(root).startswith("/kaggle/input"):
        dst = work / "udk_bench"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(root, dst)
        root = dst
    out = work / "results"
    runs = out / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    fh = open(out / "run.log", "a")
    log(f"bundle root: {root}", fh)
    ensure_deps(root, fh)

    import torch
    env = {"python": sys.version.split()[0], "torch": torch.__version__, "cuda": torch.cuda.is_available(),
           "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "cpu_count": os.cpu_count()}
    (out / "environment.json").write_text(json.dumps(env, indent=1))
    log(f"environment: {env}", fh)
    devices = (["cuda"] if torch.cuda.is_available() else []) + (["cpu"] if a.with_cpu or not torch.cuda.is_available() else [])
    if not torch.cuda.is_available():
        log("WARNING: no CUDA device -- set Accelerator to GPU in the notebook settings. Running on CPU only.", fh)

    pypath = {**os.environ, "PYTHONPATH": str(root) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    if not a.skip_tests:
        r = subprocess.run([sys.executable, "udk_shadow/test_shadow.py"], cwd=root, env=pypath, capture_output=True, text=True)
        (out / "test_shadow.log").write_text(r.stdout + r.stderr)
        log(f"shadow tests: {(r.stdout.strip().splitlines() or ['no output'])[-1]} (rc={r.returncode})", fh)

    proxy = work / "proxy"
    if not (proxy / "intent_mdeberta_base_proxy" / "config.json").exists():
        log("building proxy models (random weights, production shapes; ~2 GB on disk)...", fh)
        r = subprocess.run([sys.executable, "udk_shadow/bench/build_proxy_models.py", str(proxy)], cwd=root, env=pypath,
                           capture_output=True, text=True)
        log(f"proxy build rc={r.returncode} {r.stderr[-400:] if r.returncode else ''}", fh)
        if r.returncode:
            raise SystemExit("proxy model build failed; see run.log")

    delays = [d.strip() for d in a.delays.split(",") if d.strip()]
    plan = [(rep, dev, d, m) for rep in range(1, a.reps + 1) for dev in devices for d in delays for m in ("off", "on", "on_lite")]
    log(f"matrix: {len(plan)} runs ({a.segments} segments each)", fh)
    t0 = time.time()
    for i, (rep, dev, d, m) in enumerate(plan, 1):
        dest = runs / f"r_{dev}_{m}_{d}_{rep}.json"
        cmd = [sys.executable, "udk_shadow/bench/interference.py", "--mode", m, "--proxy", str(proxy), "--stt-delay", d,
               "--segments", str(a.segments), "--device", dev, "--out", str(dest)]
        r = subprocess.run(cmd, cwd=root, env=pypath, capture_output=True, text=True, timeout=7200)
        status = "ok" if r.returncode == 0 else f"FAILED rc={r.returncode}: {r.stderr[-300:]}"
        log(f"[{i}/{len(plan)}] {dev} mode={m} stt={d}s rep={rep}: {status} ({time.time() - t0:.0f}s elapsed)", fh)

    r = subprocess.run([sys.executable, "udk_shadow/bench/aggregate.py", str(runs)], cwd=root, env=pypath, capture_output=True, text=True)
    (out / "RESULTS.md").write_text(
        "# Shadow-mode interference, OFF vs ON (proxy models, synthetic workload)\n\n"
        "Random-weight models with the production architectures; stubbed STT/VAD/BEATs. Measures interference only, "
        "not detection quality. Medians across repeats.\n\n" + r.stdout + (("\n\nstderr:\n" + r.stderr[-1000:]) if r.returncode else ""))
    log("RESULTS.md written", fh)
    print(r.stdout)
    fh.close()
    zip_path = shutil.make_archive(str(work / "udk_shadow_gpu_results"), "zip", out)
    print(f"\nDONE. Download: {zip_path}")


if __name__ == "__main__":
    main()
