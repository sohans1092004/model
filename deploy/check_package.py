"""Proves the image's file whitelist is complete, without Docker or GPU:
copies ONLY the whitelisted files to a temp dir and starts api.py there (no models
enabled), plus checks every local import in them is whitelisted.
    python deploy/check_package.py"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOT_DEPLOYED_OK = {"kafka_delivery", "dual_asr_guard"}  # imported only behind flags this deployment leaves off


def whitelist() -> list[Path]:
    rules = [l.strip() for l in (Path(__file__).parent / "Dockerfile.dockerignore").read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    keep = [r[1:].rstrip("/") for r in rules if r.startswith("!")]
    files = []
    for k in keep:
        p = ROOT / k
        assert p.exists(), f"whitelisted but missing: {k}"
        files += [f for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts] if p.is_dir() else [p]
    return files


def main() -> None:
    files = whitelist()
    local = {p.stem for p in ROOT.glob("*.py")}
    shipped = {p.stem for p in files if p.suffix == ".py" and p.parent == ROOT}
    for p in files:
        if p.suffix != ".py" or p.parent != ROOT:
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                [n.module] if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 else []
            for m in (x.split(".")[0] for x in names):
                assert m not in local or m in shipped or m in NOT_DEPLOYED_OK, f"{p.name} imports {m}.py, not in the image"
    with tempfile.TemporaryDirectory() as tmp:
        for p in files:
            dst = Path(tmp) / p.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
        env = {**os.environ, "UDK_DATA_DIR": str(Path(tmp) / "data"), "UDK_SERVICE_TOKEN": "check-token",
               "UDK_WEBHOOK_URL": "https://example.invalid/hook", "UDK_WEBHOOK_SECRET": "s"}
        code = ("from fastapi.testclient import TestClient; import api; c = TestClient(api.app); "
                "r = c.get('/metrics', headers={'X-Service-Token': 'check-token'}); assert r.status_code == 200, r.text; "
                "assert c.get('/metrics', headers={'X-Service-Token': ''}).status_code == 401; "
                "assert api._downstream_deliver.__qualname__.startswith('make_webhook_deliver')")
        r = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        # the dev token must be refused in a deployment
        env.pop("UDK_SERVICE_TOKEN")
        r = subprocess.run([sys.executable, "-c", "import api"], cwd=tmp, env=env, capture_output=True, text=True)
        assert r.returncode != 0 and "dev token is public" in r.stderr, "dev token accepted in deployment"
    print(f"deploy package OK: {len(files)} files; api.py starts from them alone")


if __name__ == "__main__":
    main()
