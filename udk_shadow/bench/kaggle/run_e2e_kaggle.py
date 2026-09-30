"""Kaggle entry point for the end-to-end VAD-cache impact test. Steps (each logged to results/run.log):

  0. copy the bundle to a writable directory
  1. install the service's runtime packages as deploy/Dockerfile does (requirements-deploy.txt, then onnxruntime-gpu in
     place of the CPU onnxruntime that onnx-asr pulls); Kaggle's own torch/transformers are used
  2. optional: download the private intent model (HF_TOKEN from Kaggle Secrets or env) -> models/intent_mdeberta
  3. environment report
  4. harness tests (fake models) as a bundle sanity check
  5. smoke: 2 recordings, 1 chunk size -- stops here if Whisper did not load on the GPU
  6. full run (unless --smoke)
  7. zip results -> /kaggle/working/udk_e2e_results.zip

    python run_e2e_kaggle.py [--smoke] [--intent-repo <hf-user>/udk-intent-mdeberta] [--intent-revision <commit>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "api.py").exists() and (p / "recordings.json").exists():
            return p
    raise SystemExit("bundle root (api.py + recordings.json) not found above " + str(HERE))


TOKEN_RE = re.compile(r"hf_[A-Za-z0-9]{20,}")


def redact(text: str, secret: str | None = None) -> str:
    """Defensive: the token is never passed on a command line, but nothing that could hold it is written unredacted."""
    if secret:
        text = text.replace(secret, "***REDACTED***")
    return TOKEN_RE.sub("hf_***REDACTED***", text)


def redact_tree(folder: Path, secret: str | None = None) -> list[str]:
    """Scrub every text file under `folder` (logs, JSON, tables) before it is zipped; returns the files changed."""
    changed = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix in (".log", ".json", ".md", ".txt", ".csv"):
            s = p.read_text(errors="replace")
            r = redact(s, secret)
            if r != s:
                p.write_text(r)
                changed.append(str(p))
    return changed


def sh(cmd, log, env=None, check=False):
    with open(log, "a") as f:
        f.write(f"\n$ {redact(' '.join(map(str, cmd)))}\n")
        f.flush()
        r = subprocess.run(list(map(str, cmd)), stdout=f, stderr=subprocess.STDOUT, env=env)
    if check and r.returncode:
        raise SystemExit(f"failed ({r.returncode}): {' '.join(map(str, cmd))} -- see {log}")
    return r.returncode


def hf_token():
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    try:
        from kaggle_secrets import UserSecretsClient
        return UserSecretsClient().get_secret("HF_TOKEN")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workdir", default="/kaggle/working" if Path("/kaggle/working").exists() else "./e2e_out")
    ap.add_argument("--intent-repo", default=None)
    ap.add_argument("--intent-revision", default=None)
    ap.add_argument("--skip-install", action="store_true")
    ap.add_argument("--investigate", action="store_true", help="only the targeted investigation of unexplained differences")
    a = ap.parse_args()
    work = Path(a.workdir)
    root = find_root()
    if not os.access(root, os.W_OK) or str(root).startswith("/kaggle/input"):
        dst = work / "bundle"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(root, dst)
        root = dst
    res = work / "results"
    res.mkdir(parents=True, exist_ok=True)
    log = res / "run.log"
    py = sys.executable
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(root), os.environ.get("PYTHONPATH")])), "HF_HOME": str(work / "hf_cache"), "PYTHONUNBUFFERED": "1"}
    if not a.skip_install:
        sh([py, "-m", "pip", "install", "-q", "-r", root / "deploy" / "requirements-deploy.txt", "av"], log, check=True)
        sh([py, "-m", "pip", "uninstall", "-y", "onnxruntime", "onnxruntime-gpu"], log)
        site = subprocess.run([py, "-c", "import site; print(site.getsitepackages()[0])"], capture_output=True, text=True).stdout.strip()
        shutil.rmtree(Path(site) / "onnxruntime", ignore_errors=True)
        sh([py, "-m", "pip", "install", "-q", "--no-deps", "onnxruntime-gpu>=1.22,<1.27,!=1.24.1,!=1.25.*,!=1.26.0"], log, check=True)
    intent_dir = None
    if a.intent_repo:
        tok = hf_token()
        target = work / "models" / "intent_mdeberta"
        # the token travels in the child's environment only: never on the command line, which sh() writes to run.log
        code = ("import os, sys; from huggingface_hub import snapshot_download; "
                "snapshot_download(sys.argv[1], revision=sys.argv[2] or None, local_dir=sys.argv[3], token=os.environ.get('HF_TOKEN') or None)")
        rc = sh([py, "-c", code, a.intent_repo, a.intent_revision or "", target], log, env={**env, **({"HF_TOKEN": tok} if tok else {})})
        intent_dir = str(target) if rc == 0 and (target / "config.json").exists() else None
        with open(log, "a") as f:
            f.write(f"\nintent model: {'downloaded to ' + str(target) if intent_dir else 'UNAVAILABLE (download failed / no token)'}\n")
    sh([py, "-c", "import torch, platform, json; print(json.dumps({'torch': torch.__version__, 'cuda': torch.cuda.is_available(), "
        "'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, 'python': platform.python_version()}))"], log, env=env)
    if not a.investigate:
        sh([py, root / "udk_shadow" / "test_e2e_vad_cache.py"], res / "test_e2e_vad_cache.log", env=env)
        sh([py, root / "test_vad_classification_cache.py"], res / "test_vad_classification_cache.log", env=env)
    manifest = root / "recordings.json"
    recs = json.loads(manifest.read_text())
    search = [root, *([Path("/kaggle/input")] if Path("/kaggle/input").exists() else []), root.parent]
    for r in recs:  # recordings ship in separate *_audioN parts: gather by file name
        name = Path(r["path"]).name
        hit = next((p for base in search for p in base.rglob(name) if p.is_file()), None)
        if hit is None:
            raise SystemExit(f"recording {name} not found -- upload every *_audioN.zip into the same dataset")
        r["path"] = str(hit)
    manifest.write_text(json.dumps(recs, indent=1))
    if a.investigate:
        inv = [py, root / "udk_shadow" / "bench" / "e2e_investigate.py", "--recordings", manifest, "--device", "cuda",
               "--out", res / "investigate_v2.json"] + (["--intent-dir", intent_dir] if intent_dir else [])
        sh(inv, res / "investigate_v2.log", env=env)
        scrubbed = redact_tree(res, hf_token())
        with open(log, "a") as f:
            f.write(f"\ncredential scan before zipping: {len(scrubbed)} file(s) redacted\n")
        shutil.make_archive(str(work / "udk_e2e_investigate_v2"), "zip", res)
        print("results:", work / "udk_e2e_investigate_v2.zip")
        return
    base = [py, root / "udk_shadow" / "bench" / "e2e_vad_cache.py", "--recordings", manifest, "--device", "cuda"]
    if intent_dir:
        base += ["--intent-dir", intent_dir]
    rc = sh(base + ["--out", res / "smoke", "--only", "mix_clip_19_muffled,neg_01", "--chunks", "mixed=100", "media=1000", "--repeats", "2"],
            res / "smoke.log", env=env)
    if rc != 0:
        with open(log, "a") as f:
            f.write("\nSMOKE FAILED (see smoke.log) -- full run skipped\n")
    elif not a.smoke:
        sh(base + ["--out", res / "full"], res / "full.log", env=env)
    for name in ("smoke", "full"):
        if (res / name / "summary.json").exists():
            sh([py, root / "udk_shadow" / "bench" / "e2e_report.py", res / name / "summary.json"], res / f"{name}_tables.md", env=env)
    redact_tree(res, hf_token())
    shutil.make_archive(str(work / "udk_e2e_results"), "zip", res)
    print("results:", work / "udk_e2e_results.zip")


if __name__ == "__main__":
    main()
