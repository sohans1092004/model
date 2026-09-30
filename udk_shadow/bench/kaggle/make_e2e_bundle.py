"""Bundle for the end-to-end VAD-cache impact test (udk_shadow/bench/e2e_vad_cache.py) on a Kaggle GPU.

Contents: the production image's file set (parsed from deploy/Dockerfile.dockerignore, so the live modules are exactly
what the service ships), deploy/.env.example (the configuration, read unmodified), the experiment tools and tests, and
the local calibration recordings renamed to Kaggle-safe ids (Kaggle rejects '#' and "'" in file names). The original
name of every recording is kept in recordings.json with its sha256. No model weights, no secrets.

    python udk_shadow/bench/kaggle/make_e2e_bundle.py <out.zip>
    python udk_shadow/bench/kaggle/make_e2e_bundle.py --local-manifest <out.json>   # same ids, original paths (local runs)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOP = "udk_e2e_vad_cache"
EXTRA = [
    "deploy/.env.example", "deploy/Dockerfile.dockerignore", "deploy/requirements-deploy.txt", "vad.py",
    "udk_shadow/bench/e2e_vad_cache.py", "udk_shadow/bench/e2e_report.py", "udk_shadow/bench/e2e_investigate.py", "udk_shadow/bench/segmentation_integrity.py",
    "udk_shadow/bench/kaggle/run_e2e_kaggle.py", "udk_shadow/test_e2e_vad_cache.py", "test_vad_classification_cache.py",
    "udk_shadow/bench/segmentation_candidates.py", "udk_shadow/bench/vad_flag_equivalence.py",
    "udk_shadow/bench/vad_original_96ea038.py",
    "real_recordings/mixed/manifest.json",
]
AUDIO = (".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac", ".webm")


def image_files() -> list[str]:
    """The whitelist of the production image: '!path' lines of deploy/Dockerfile.dockerignore (dirs expanded)."""
    out = []
    for line in (ROOT / "deploy" / "Dockerfile.dockerignore").read_text().splitlines():
        line = line.strip()
        if not line.startswith("!"):
            continue
        p = ROOT / line[1:]
        if p.is_dir():
            out += [str(f.relative_to(ROOT)) for f in sorted(p.rglob("*")) if f.is_file() and "__pycache__" not in f.parts]
        elif p.exists():
            out.append(line[1:])
    return out


def recordings() -> list[dict]:
    """30 mixed clips (manifest phrases) + 18 positives/negatives (converted duplicates skipped): the same material as
    the segmentation experiment. All are CALIBRATION / DEVELOPMENT recordings, not a held-out test set."""
    sys.path.insert(0, str(ROOT / "udk_shadow" / "bench"))
    import segmentation_integrity as si
    phrases = si.manifest_phrases()
    out = []
    for folder, prefix, set_ in (("mixed", "mix", "mixed"), ("positives", "pos", "media"), ("negatives", "neg", "media")):
        files = sorted(f for f in (ROOT / "real_recordings" / folder).iterdir()
                       if f.suffix.lower() in AUDIO and "_converted_" not in f.name)
        for n, f in enumerate(files, 1):
            rid = f"{prefix}_{f.stem}" if folder == "mixed" else f"{prefix}_{n:02d}"
            out.append({"id": rid, "set": set_, "folder": folder, "original": str(f.relative_to(ROOT)),
                        "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "phrase": phrases.get((folder, f.stem)),
                        "bundle_path": f"audio/{rid}{f.suffix.lower()}", "status": "calibration/development (not held-out)"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--local-manifest", default=None)
    ap.add_argument("--part-mb", type=float, default=25.0)
    a = ap.parse_args()
    recs = recordings()
    if a.local_manifest:
        Path(a.local_manifest).write_text(json.dumps([dict(r, path=str(ROOT / r["original"])) for r in recs], indent=1))
        print(f"{a.local_manifest}: {len(recs)} recordings")
        return
    files = sorted(set(image_files() + EXTRA))
    for n in files:
        assert "#" not in n and "'" not in n, n
    out = Path(a.out)
    # code + manifest in one zip; the recordings in parts below the 30 MB transfer limit (the runner gathers them)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in files:
            z.write(ROOT / n, f"{TOP}/{n}")
        z.writestr(f"{TOP}/recordings.json", json.dumps([dict(r, path=r["bundle_path"]) for r in recs], indent=1, ensure_ascii=False))
        z.writestr(f"{TOP}/README.md", README)
    parts, cur, size = [], [], 0
    for r in recs:
        s = (ROOT / r["original"]).stat().st_size
        if cur and size + s > a.part_mb * 2**20:
            parts.append(cur)
            cur, size = [], 0
        cur.append(r)
        size += s
    parts.append(cur)
    for i, part in enumerate(parts, 1):
        pz = out.with_name(f"{out.stem}_audio{i}.zip")
        with zipfile.ZipFile(pz, "w", zipfile.ZIP_STORED) as z:
            for r in part:
                z.write(ROOT / r["original"], f"{TOP}_audio{i}/{r['bundle_path']}")
        print(f"{pz}: {len(part)} recordings")
    print(f"{out}: {len(files)} code/config files + manifest of {len(recs)} recordings")


README = """# VAD classification cache: end-to-end impact test (Kaggle GPU)

Runs the REAL live pipeline (api.py as shipped, configured from deploy/.env.example) on the local calibration
recordings twice per chunk size -- journey VAD cache OFF vs ON, interleaved, two repeats each -- and compares every
processed segment and alert. Nothing is deployed; no production file is changed; the flag stays OFF by default.

## Run
1. Kaggle -> Datasets -> New Dataset -> upload the code zip AND every *_audioN.zip into the SAME dataset. (Private.)
2. Notebook -> Settings: Accelerator GPU (T4 x1 or P100); Internet ON (downloads Whisper small.en, Parakeet, MiniLM,
   BEATs from Hugging Face -- about 4.5 GB).
3. Optional, for the intent veto: Add-ons -> Secrets -> HF_TOKEN (read access to the private intent-model repo) and
   pass --intent-repo <hf-user>/udk-intent-mdeberta below. Without it the intent gate is recorded as UNAVAILABLE.
4. One cell:

```
import glob, subprocess, sys
runner = glob.glob('/kaggle/input/**/udk_shadow/bench/kaggle/run_e2e_kaggle.py', recursive=True)[0]
subprocess.run([sys.executable, runner], check=True)                                       # ~1-2 h on a T4
# subprocess.run([sys.executable, runner, '--intent-repo', '<hf-user>/udk-intent-mdeberta'], check=True)
# subprocess.run([sys.executable, runner, '--smoke'], check=True)                          # ~10 min check first
```

5. Download /kaggle/working/udk_e2e_results.zip and send it back.
"""

if __name__ == "__main__":
    main()
