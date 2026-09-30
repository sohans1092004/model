"""Phase 6C deployment smoke test WITHOUT Docker (Kaggle cannot run a Docker daemon): the same idea as the image,
i.e. copy ONLY the files deploy/Dockerfile.dockerignore whitelists into an empty folder, then start api.py from it.

Checks (each PASS/FAIL, all run):
  1 whitelisted package contains the shadow runtime and no tests / reports / evaluation / benchmark files
  2 shadow OFF (default): service answers /metrics, udk_shadow never imported
  3 shadow ON: runtime loads, start-up self-check ok, effective S-4 = open, Phase 5 sentence-veto guard = False
  4 shadow ON with the REAL semantic model on the GPU (UDK_ENABLE_SEMANTIC=1, UDK_DEVICE=cuda; needs Internet
    for the Hugging Face download): replay goes through the uncached encoder, the live lru_cache is untouched
  5 shadow ON + udk_fusion removed -> fails closed (shadow OFF), service serves
  6 shadow ON + a shadow dependency removed (asr_bench/textnorm.py) -> fails closed, service serves
  7 shadow ON + invalid shadow config -> fails closed, service serves
  8 real uvicorn server with shadow ON answers /metrics and logs the self-check
Writes <out>/smoke.json and prints a table.

    python smoke_shadow.py <repo_root> <out_dir>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def whitelist(root: Path) -> list[Path]:
    rules = [l.strip() for l in (root / "deploy" / "Dockerfile.dockerignore").read_text().splitlines() if l.strip() and not l.startswith("#")]
    files = []
    for k in (r[1:].rstrip("/") for r in rules if r.startswith("!")):
        p = root / k
        files += [f for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts] if p.is_dir() else [p]
    return files


def main() -> None:
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = []

    def res(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": str(detail)[-1500:]})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"\n       {str(detail)[-800:]}"), flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        for p in whitelist(root):
            dst = Path(tmp) / p.relative_to(root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
        shipped = sorted(str(p.relative_to(tmp)) for p in Path(tmp).rglob("*") if p.is_file() and
                         p.parts[len(Path(tmp).parts)] in ("udk_shadow", "udk_fusion", "udk_context", "udk_signals", "asr_bench"))
        def excluded(f):  # match path SEGMENTS / file names -- a substring test flagged asr_bench/ as "bench" (Kaggle run 1)
            parts, name = f.split("/"), f.rsplit("/", 1)[-1]
            return ("bench" in parts or "fixtures" in parts or name.startswith("test_") or
                    name in ("report.py", "evaluation.py", "splits.py", "fixtures.py") or name.endswith(".md"))
        bad = [f for f in shipped if excluded(f)]
        res(f"whitelist ships shadow runtime only ({len(shipped)} files)", "udk_shadow/runner.py" in shipped and not bad, bad)

        base = {**os.environ, "UDK_DATA_DIR": str(Path(tmp) / "data"), "UDK_SERVICE_TOKEN": "check-token",
                "UDK_WEBHOOK_URL": "https://example.invalid/hook", "UDK_WEBHOOK_SECRET": "s", "PYTHONPATH": tmp}
        for k in [k for k in base if k.startswith("UDK_ENABLE_") or k.startswith("UDK_SHADOW")]:
            base.pop(k)
        probe = ("from fastapi.testclient import TestClient; import api; c = TestClient(api.app); "
                 "assert c.get('/metrics', headers={'X-Service-Token': 'check-token'}).status_code == 200; ")

        def run(code, env, cwd=tmp, timeout=1800):
            r = subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout + r.stderr

        rc, o = run(probe + "import sys; assert api._shadow is None and 'udk_shadow' not in sys.modules", base)
        res("shadow OFF (default): service starts, udk_shadow not imported", rc == 0, o)
        on = {**base, "UDK_SHADOW_MODE": "1"}
        rc, o = run(probe + "e = api._shadow.processor.effective; print('EFF', e['s4_status'], e['sentence_veto']['phase5_sentence_veto_guard'], "
                            "e['UDK_ENABLE_SCREAM_TRIGGER']['env'], e['UDK_ENABLE_SCREAM_DETECTION']['env'])", on)
        res("shadow ON: loads, self-check ok, S-4 open, Phase 5 sentence-veto guard False, scream flags recorded as-is",
            rc == 0 and "self-check ok" in o and "EFF open False None None" in o, o)
        gpu = {**on, "UDK_ENABLE_SEMANTIC": "1", "UDK_DEVICE": "cuda"}
        rc, o = run(probe + (
            "m = api._semantic_matcher; assert m is not None; import torch; print('DEV', next(m._model.parameters()).device); "
            "from udk_shadow.processor import IsolatedSemantic; v = IsolatedSemantic(m); before = m._encode.cache_info().currsize; "
            "s = v.similarity('help me please', 'call the police'); after = m._encode.cache_info().currsize; "
            "print('ISO', before, after, round(s, 3)); assert before == after"), gpu, timeout=3600)
        res("shadow ON + real semantic model on GPU: isolated replay leaves the live cache untouched", rc == 0 and "DEV cuda" in o, o)
        for label, cmd in (("udk_fusion removed", "rm -rf udk_fusion"), ("shadow dependency removed (asr_bench/textnorm.py)", "rm -f asr_bench/textnorm.py")):
            with tempfile.TemporaryDirectory() as t2:
                shutil.copytree(tmp, t2, dirs_exist_ok=True)
                subprocess.run(cmd, shell=True, cwd=t2)
                rc, o = run(probe + "assert api._shadow is None", {**on, "PYTHONPATH": t2, "UDK_DATA_DIR": str(Path(t2) / "data")}, cwd=t2)
                res(f"shadow ON + {label}: fails closed (shadow OFF), service serves", rc == 0, o)
        rc, o = run(probe + "assert api._shadow is None", {**on, "UDK_SHADOW_QUEUE_MAX": "0"})
        res("shadow ON + invalid shadow config: fails closed, service serves", rc == 0, o)

        logf = open(out / "uvicorn.log", "w")
        srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8765", "--workers", "1"],
                               cwd=tmp, env=on, stdout=logf, stderr=subprocess.STDOUT)
        code = None
        for _ in range(120):
            try:
                urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8765/metrics", headers={"X-Service-Token": "check-token"}), timeout=2)
                code = 200
                break
            except Exception as e:
                code = getattr(e, "code", None)
                time.sleep(1)
        srv.terminate(); srv.wait(timeout=30); logf.close()
        log = (out / "uvicorn.log").read_text()
        res("uvicorn server with shadow ON answers /metrics and logs the self-check", code == 200 and "self-check ok" in log, log[-800:])

    (out / "smoke.json").write_text(json.dumps(results, indent=1))
    print(f"\nsmoke: {sum(r['ok'] for r in results)}/{len(results)} passed")


if __name__ == "__main__":
    main()
