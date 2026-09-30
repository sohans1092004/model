"""Phase 6C checks on a Kaggle GPU notebook (Internet ON): complete test suite on this branch AND on the clean 96ea038
baseline, deploy/check_package.py on both, the shadow deployment smoke test (smoke_shadow.py), and a summary that
separates baseline failures from regressions.

Bundle layout (make_checks_bundle.py): branch/ = the branch working tree; baseline_overlay/ = the three tracked files
the branch changed, as they are at 96ea038. The baseline tree is rebuilt here as branch/ minus the new packages
(asr_bench, udk_context, udk_signals, udk_fusion, udk_shadow) with the overlay restored, and verified against the
bundled 96ea038 file list.

    python run_checks.py [--timeout 900] [--only branch|baseline] [--skip-install]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEW_PACKAGES = ("asr_bench", "udk_context", "udk_signals", "udk_fusion", "udk_shadow")
EXTRA_TEST_DEPS = ["soundfile", "librosa", "httpx", "pvporcupine"]


def log(msg, fh):
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n"); fh.flush()


def bundle_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "branch" / "api.py").exists():
            return p
    raise SystemExit("bundle root (branch/api.py) not found")


def part_dirs(src: Path) -> list[Path]:
    """All uploaded parts (<name>_partK/) -- siblings of part 1, or anywhere under /kaggle/input."""
    stem = src.name.rsplit("_part", 1)[0]
    roots = [src.parent] + ([Path("/kaggle/input")] if Path("/kaggle/input").is_dir() else [])
    found = {p.resolve() for r in roots for p in r.rglob(f"{stem}_part*") if (p / "branch").is_dir()}
    return sorted(found, key=lambda p: p.name)


def summary_line(out: str) -> str:
    total = [l for l in out.strip().splitlines() if "TOTAL" in l]  # a check() suite's own count wins over later warnings
    if total:
        return total[-1][:200]
    keys = ("passed", "failed", "Error", "OK", "FAIL", "Traceback")
    lines = [l for l in out.strip().splitlines() if any(k in l for k in keys)]
    return (lines[-1] if lines else (out.strip().splitlines() or [""])[-1])[:200]


def run_suite(tree: Path, label: str, timeout: int, out: Path, fh) -> list[dict]:
    tests = sorted(p for p in tree.glob("test_*.py")) + sorted(p for pkg in NEW_PACKAGES for p in (tree / pkg).glob("test_*.py"))
    rows = []
    env = {**os.environ, "PYTHONPATH": str(tree)}
    for i, t in enumerate(tests, 1):
        rel = str(t.relative_to(tree))
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, rel], cwd=tree, env=env, capture_output=True, text=True, timeout=timeout)
            rc, o = r.returncode, r.stdout + r.stderr
        except subprocess.TimeoutExpired as e:
            rc, o = "timeout", ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) + f"\nTIMEOUT after {timeout}s"
        dt = time.time() - t0
        (out / "logs" / label).mkdir(parents=True, exist_ok=True)
        (out / "logs" / label / (rel.replace("/", "__") + ".log")).write_text(o)
        row = {"test": rel, "rc": rc, "seconds": round(dt, 1), "summary": summary_line(o)}
        rows.append(row)
        log(f"{label} [{i}/{len(tests)}] {rel}: rc={rc} {dt:.0f}s | {row['summary']}", fh)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=900, help="seconds per test file")
    ap.add_argument("--only", choices=("branch", "baseline"))
    ap.add_argument("--skip-install", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="rebuild and verify both trees, list the tests, run nothing")
    ap.add_argument("--workdir", default="/kaggle/working" if Path("/kaggle/working").is_dir() else str(Path.cwd()))
    a = ap.parse_args()
    src = bundle_root()
    work = Path(a.workdir) / "udk_checks"
    out = Path(a.workdir) / "check_results"
    out.mkdir(parents=True, exist_ok=True)
    fh = open(out / "run.log", "a")
    if work.exists():
        shutil.rmtree(work)
    parts = part_dirs(src)
    expected = int((src / "parts.txt").read_text()) if (src / "parts.txt").exists() else 1
    log(f"parts found: {[p.name for p in parts]} (expected {expected})", fh)
    if len(parts) < expected:
        raise SystemExit(f"only {len(parts)} of {expected} parts found under /kaggle/input: upload all part zips to the dataset")
    for p in parts:
        shutil.copytree(p / "branch", work / "branch", dirs_exist_ok=True)
    for p in parts:  # restore original file names stored under safe names (Kaggle rejects '#', "'", ...)
        rn = p / "renames.json"
        for stored_name, original in (json.loads(rn.read_text(encoding="utf-8")) if rn.exists() else {}).items():
            dst = work / "branch" / original
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(work / "branch" / stored_name), str(dst))
    if (work / "branch" / "renamed").is_dir() and not any((work / "branch" / "renamed").iterdir()):
        (work / "branch" / "renamed").rmdir()
    base = work / "baseline"
    shutil.copytree(work / "branch", base, ignore=shutil.ignore_patterns(*NEW_PACKAGES))
    for f in (src / "baseline_overlay").rglob("*"):
        if f.is_file():
            dst = base / f.relative_to(src / "baseline_overlay")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    want = set((src / "baseline_files.txt").read_text().split("\n")) - {""}
    have = {str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}
    log(f"baseline tree rebuilt: {len(have)} files; missing vs 96ea038: {sorted(want - have)[:10]}; extra: {sorted(have - want)[:10]}", fh)
    if a.dry_run:
        for label in ("baseline", "branch"):
            t = work / label
            n = len(list(t.glob("test_*.py"))) + sum(len(list((t / p).glob("test_*.py"))) for p in NEW_PACKAGES)
            log(f"dry run: {label} has {n} test files", fh)
        print("baseline tree identical to 96ea038:", want == have)
        return

    if not a.skip_install:
        reqs = [l.split("#")[0].strip() for l in (work / "branch" / "deploy" / "requirements-deploy.txt").read_text().splitlines()]
        reqs = [r for r in reqs if r] + EXTRA_TEST_DEPS
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", *reqs], capture_output=True, text=True)
        log(f"pip install ({len(reqs)} packages) rc={r.returncode} {r.stderr[-600:] if r.returncode else ''}", fh)

    import importlib
    env_info = {"python": sys.version.split()[0]}
    try:
        torch = importlib.import_module("torch")
        env_info.update(torch=torch.__version__, cuda=torch.cuda.is_available(), gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    except Exception as e:
        env_info["torch"] = f"unavailable: {e}"
    (out / "environment.json").write_text(json.dumps(env_info, indent=1))
    log(f"environment: {env_info}", fh)

    results = {}
    for label in ("baseline", "branch"):
        if a.only and a.only != label:
            continue
        results[label] = run_suite(work / label, label, a.timeout, out, fh)
        r = subprocess.run([sys.executable, "deploy/check_package.py"], cwd=work / label, capture_output=True, text=True, timeout=3600)
        results[f"{label}_check_package"] = {"rc": r.returncode, "summary": summary_line(r.stdout + r.stderr)}
        (out / "logs" / f"{label}__check_package.log").write_text(r.stdout + r.stderr)
        log(f"{label} deploy/check_package.py rc={r.returncode} | {results[f'{label}_check_package']['summary']}", fh)
    if a.only != "baseline":
        r = subprocess.run([sys.executable, str(work / "branch" / "udk_shadow" / "bench" / "kaggle" / "smoke_shadow.py"), str(work / "branch"),
                            str(out / "smoke")], capture_output=True, text=True, timeout=7200)
        (out / "smoke_shadow.log").write_text(r.stdout + r.stderr)
        log("smoke: " + summary_line(r.stdout), fh)
    (out / "results.json").write_text(json.dumps(results, indent=1))

    md = ["# Phase 6C checks (Kaggle GPU)", "", f"environment: `{json.dumps(env_info)}`", ""]
    if "baseline" in results and "branch" in results:
        b = {r["test"]: r for r in results["baseline"]}
        md += ["| test | 96ea038 baseline | branch | verdict |", "|---|---|---|---|"]
        for r in results["branch"]:
            o = b.get(r["test"])
            if o is None:
                verdict = "new (branch only): " + ("pass" if r["rc"] == 0 else "FAIL")
            elif o["rc"] == 0 and r["rc"] != 0:
                verdict = "REGRESSION"
            elif o["rc"] != 0 and r["rc"] == 0:
                verdict = "fixed on branch"
            elif o["rc"] != 0:
                verdict = "fails on both (baseline failure)" + ("" if o["summary"] == r["summary"] else " -- output differs, check logs")
            else:
                verdict = "pass both"
            md.append(f"| {r['test']} | rc={o['rc'] if o else '–'} {o['summary'] if o else ''} | rc={r['rc']} {r['summary']} | {verdict} |")
        for k in ("baseline_check_package", "branch_check_package"):
            md.append(f"\n{k}: rc={results[k]['rc']} {results[k]['summary']}")
    md += ["", "## shadow smoke", "```", (out / "smoke_shadow.log").read_text()[-4000:] if (out / "smoke_shadow.log").exists() else "not run", "```"]
    (out / "SUMMARY.md").write_text("\n".join(md))
    print("\n".join(md))
    fh.close()
    print("\nDONE. Download:", shutil.make_archive(str(Path(a.workdir) / "udk_phase6c_check_results"), "zip", out))


if __name__ == "__main__":
    main()
