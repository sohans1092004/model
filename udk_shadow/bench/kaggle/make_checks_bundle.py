"""Build the Kaggle upload for run_checks.py: the branch working tree (no .git, no __pycache__), the three tracked files
as they are at 96ea038 (baseline_overlay/), the 96ea038 file list, and the runner.

    python udk_shadow/bench/kaggle/make_checks_bundle.py <out.zip>   -> <out>_part1.zip ... _partN.zip
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOP = "udk_phase6c_checks"
BASE = "96ea038"
SAFE = re.compile(r"[A-Za-z0-9_./ -]+")  # anything else is stored renamed (renames.json) and restored by run_checks.py
PART_LIMIT = 27_000_000  # bytes of payload per part (file-transfer limit is 30 MiB)
README = """# UDK Phase 6C checks on Kaggle (GPU)

Runs the COMPLETE test suite on this branch and on the clean 96ea038 baseline, deploy/check_package.py on both, and
the shadow deployment smoke test (no Docker on Kaggle: it copies only the image-whitelisted files and starts api.py
from them). Summary separates baseline failures from regressions.

1. Create ONE Kaggle Dataset and upload ALL {N} part zips into it (Kaggle unzips each; the runner merges them).
2. Notebook settings: Accelerator = GPU, **Internet = ON** (installs deploy/requirements-deploy.txt + test deps and
   lets tests / the smoke test download models from Hugging Face).
3. One cell:

```
import glob, subprocess, sys
runner = glob.glob('/kaggle/input/**/udk_phase6c_checks_part1/run_checks.py', recursive=True)[0]
subprocess.run([sys.executable, runner], check=True)
```

4. Download /kaggle/working/udk_phase6c_check_results.zip and send it back (SUMMARY.md, results.json, logs/, smoke/).

Options: --timeout N (seconds per test file, default 900), --only branch|baseline, --skip-install.
"""


def main() -> None:
    out = sys.argv[1]
    def git0(*args):  # NUL-separated: git would otherwise quote non-ASCII file names
        return [x for x in subprocess.run(["git", *args, "-z"] if args[0] != "ls-tree" else ["git", args[0], "-z", *args[1:]], cwd=ROOT,
                                          capture_output=True, text=True, check=True).stdout.split("\0") if x]
    changed = git0("diff", "--name-only", BASE)
    base_files = "\n".join(git0("ls-tree", "-r", "--name-only", BASE))
    tracked = set(git0("ls-files"))
    untracked = git0("ls-files", "--others", "--exclude-standard")
    files = sorted(f for f in (tracked | set(untracked)) if f and "__pycache__" not in f and (ROOT / f).is_file())
    # Split into parts under the upload limit: part 1 = code + runner; big binaries go to data parts.
    big = sorted((f for f in files if (ROOT / f).stat().st_size > 1_000_000), key=lambda f: -(ROOT / f).stat().st_size)
    parts, sizes = [[]], [0]
    for f in big:
        n = (ROOT / f).stat().st_size
        i = next((k for k in range(1, len(parts)) if sizes[k] + n <= PART_LIMIT), None)
        if i is None:
            parts.append([]); sizes.append(0); i = len(parts) - 1
        parts[i].append(f); sizes[i] += n
    parts[0] = [f for f in files if f not in set(big)]
    stem = out[:-4] if out.endswith(".zip") else out

    def stored(f):  # Kaggle rejects some characters in uploaded names ('#', "'", ...) and auto-extracts nested .zip files:
        # store those under a hash (.bin for zips) and map back (renames.json)
        if f.endswith(".zip"):
            return f"renamed/{hashlib.sha1(f.encode()).hexdigest()}.bin"
        return f if SAFE.fullmatch(f) else f"renamed/{hashlib.sha1(f.encode()).hexdigest()}{Path(f).suffix if SAFE.fullmatch(Path(f).suffix) else ''}"
    for k, fs in enumerate(parts, 1):
        top = f"{TOP}_part{k}"
        with zipfile.ZipFile(f"{stem}_part{k}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            renames = {}
            for f in fs:
                name = stored(f)
                if name != f:
                    renames[name] = f
                z.write(ROOT / f, f"{top}/branch/{name}")
            z.writestr(f"{top}/renames.json", json.dumps(renames, ensure_ascii=False, indent=1))
            if k == 1:
                for f in changed:
                    blob = subprocess.run(["git", "show", f"{BASE}:{f}"], cwd=ROOT, capture_output=True, check=True).stdout
                    z.writestr(f"{top}/baseline_overlay/{f}", blob)
                z.writestr(f"{top}/baseline_files.txt", base_files)
                z.writestr(f"{top}/parts.txt", str(len(parts)))
                z.write(ROOT / "udk_shadow/bench/kaggle/run_checks.py", f"{top}/run_checks.py")
                z.writestr(f"{top}/README_KAGGLE.md", README.replace("{N}", str(len(parts))))
        print(f"wrote {stem}_part{k}.zip ({len(fs)} files)")
    print(f"{len(files)} branch files in {len(parts)} parts; baseline overlay: {', '.join(changed)}")


if __name__ == "__main__":
    main()
