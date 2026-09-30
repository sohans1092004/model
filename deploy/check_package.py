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
# Shadow mode (UDK_SHADOW_MODE=1) ships its runtime modules only. A function-level import of a repo module that is
# NOT shipped is allowed only if listed here with the reason it can never run in the service.
SHADOW_PACKAGES = {"udk_shadow", "udk_fusion", "udk_context", "udk_signals", "asr_bench"}
LAZY_NOT_DEPLOYED_OK = {
    ("udk_context.scene", "asr_bench.splits"): "assign_scene_splits(): offline data-split tooling, never called by shadow",
}


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
    check_shadow_imports(files, local, shipped)
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
        check_shadow_runtime(tmp, env)
    print(f"deploy package OK: {len(files)} files; api.py starts from them alone, with shadow mode OFF and ON")


def _module_of(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    return ".".join(parts[:-1]) if parts[-1] == "__init__" else ".".join(parts)


def check_shadow_imports(files, local, shipped_root) -> None:
    """Every import (module- or function-level) inside a shipped shadow package resolves to a shipped file,
    except the documented LAZY_NOT_DEPLOYED_OK entries; and every shipped package file is actually reachable
    (nothing unrelated rides along)."""
    shipped = {_module_of(p) for p in files if p.suffix == ".py" and p.parts[len(ROOT.parts)] in SHADOW_PACKAGES}
    shipped_json = {str(p.relative_to(ROOT)) for p in files if p.suffix == ".json"}
    reached, todo = set(), ["udk_shadow.runner"]
    while todo:
        mod = todo.pop()
        if mod in reached:
            continue
        reached.add(mod)
        assert mod in shipped, f"shadow imports {mod}, not in the image"
        src = ROOT.joinpath(*mod.split("."))
        src = src / "__init__.py" if src.is_dir() else src.with_suffix(".py")
        for n in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                [n.module] + [f"{n.module}.{a.name}" for a in n.names] if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 else []
            for name in names:
                top = name.split(".")[0]
                if top in local:
                    assert top in shipped_root or top in NOT_DEPLOYED_OK, f"{mod} imports {top}.py, not in the image"
                elif top in SHADOW_PACKAGES:
                    parts = name.split(".")
                    target = next((".".join(parts[:i]) for i in range(len(parts), 0, -1)
                                   if (ROOT.joinpath(*parts[:i]).with_suffix(".py")).exists()
                                   or (ROOT.joinpath(*parts[:i]) / "__init__.py").exists()), None)
                    if target is None:
                        continue
                    if (mod, target) in LAZY_NOT_DEPLOYED_OK:
                        continue
                    todo += [".".join(parts[:i]) for i in range(1, parts.index(target.split(".")[-1]) + 2)]
    extra = shipped - reached
    assert not extra, f"shipped but never imported by shadow mode: {sorted(extra)}"
    for cfg in ("udk_fusion/configs/production_equivalent.json", "udk_context/configs/production_equivalent.json"):
        assert cfg in shipped_json, f"shadow needs {cfg}"


def _run(tmp, env, code):
    return subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env, capture_output=True, text=True)


def check_shadow_runtime(tmp, env) -> None:
    """Shadow OFF is the default path checked above. Here: ON loads and self-checks from the whitelisted files
    alone; a missing shadow package or a failing shadow import fails CLOSED (shadow OFF) and the service still
    serves."""
    probe = ("from fastapi.testclient import TestClient; import api; c = TestClient(api.app); "
             "assert c.get('/metrics', headers={'X-Service-Token': 'check-token'}).status_code == 200; ")
    env = {**env, "UDK_SERVICE_TOKEN": "check-token"}
    off = _run(tmp, env, probe + "assert api._shadow is None; import sys; assert 'udk_shadow' not in sys.modules")
    assert off.returncode == 0, "shadow OFF: " + off.stderr[-1500:]
    on_env = {**env, "UDK_SHADOW_MODE": "1"}
    on = _run(tmp, on_env, probe + "assert api._shadow is not None, 'shadow did not load'; "
                                   "from udk_shadow import selfcheck; r = selfcheck.run(api, api._either_stt_decisions); assert r['ok'], r")
    assert on.returncode == 0, "shadow ON: " + on.stderr[-1500:] + on.stdout[-500:]
    blocked = ("import sys, importlib.abc\n"
               "class Block(importlib.abc.MetaPathFinder):\n"
               "    def find_spec(self, name, path=None, target=None):\n"
               "        if name.split('.')[0] in BLOCK: raise ImportError('blocked for the check: ' + name)\n"
               "sys.meta_path.insert(0, Block())\n")
    for label, block in (("shadow package missing", "{'udk_shadow'}"), ("shadow dependency missing", "{'udk_context', 'asr_bench'}")):
        r = _run(tmp, on_env, f"BLOCK = {block}\n" + blocked + probe + "assert api._shadow is None")
        assert r.returncode == 0, f"{label}: " + r.stderr[-1500:]


if __name__ == "__main__":
    main()
