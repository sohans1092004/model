"""Shadow-mode resource-interference harness (Phase 6C). Test infrastructure only: not in the image whitelist.

Runs the REAL live loop (api._run_incremental_detection, _either_stt_decisions, _intent_veto, _decision_to_event,
extracted from api.py with ast -- api.py itself loads FastAPI and every model at import) with:
  - the real udk_engine.UDKEngine and the LIVE semantic.SentenceTransformerSemanticMatcher and intent_gate.IntentGate
    classes, loaded with RANDOM-WEIGHT proxies of the production architectures (build_proxy_models.py);
  - stubbed VAD / Whisper / Parakeet / BEATs: STT is a sleep of --stt-delay seconds (sleep releases the GIL, as
    CTranslate2 / ONNX inference does) returning a scripted transcript; BEATs returns scripted values at no cost.
Each condition runs in its own process (clean peak RSS). One call of the live loop processes exactly one new
segment; segments are fed back to back (no idle time between them beyond --stt-delay).

Measured per segment: live loop latency (call -> return), time from call start to each emitted alert, live-thread
semantic-similarity and intent-gate time. Per run: CPU seconds / wall seconds, peak RSS, shadow processing time
and queue wait per record (from the records), drain time after the last live segment, dropped observations.

    python udk_shadow/bench/interference.py --mode off|on|on_lite --proxy <dir> --stt-delay 0.0 --segments 100 --out r.json [--device cuda]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import resource
import statistics
import sys
import threading
import time
import types
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# (primary text, second text, (scream fired, peak, class) | None, 9-class score) -- a fixed, deterministic mix
WORKLOAD = [
    ("help me please", "help me please", None, 0.02),
    ("I was telling her about the new restaurant near the station", "I was telling her about the new restaurant near the station", None, 0.01),
    ("I don't feel safe here", "I don't feel safe here", None, 0.4),
    ("Let go of me! Please don't hurt me!", "Let go of me! Please don't hurt me!", None, 0.6),
    ("", "", (True, 0.35, "Screaming"), 0.5),
    ("can you pass me the salt", "can you pass me the salt", None, 0.01),
    ("someone is following me", "someone is following me", None, 0.05),
    ("", "", None, None),
    ("I want to go home now", "I want to go home now", None, 0.02),
    ("the meeting moved to three o'clock tomorrow", "the meeting moved to three tomorrow", None, 0.01),
    ("call the police I need help", "call the police I need help", None, 0.3),
    ("we should get out of here before the traffic starts", "we should get out of here before traffic", None, 0.01),
    ("stay away from me", "stay away from me", None, 0.2),
    ("I'm not saying this only because I'm tired", "I'm not saying this only because I'm tired", None, 0.01),
    ("please don't touch my phone it's charging", "please don't touch my phone", None, 0.01),
    ("I'm in danger", "I am in danger", None, 0.45),
]


@dataclass
class Seg:
    start_ms: int
    end_ms: int
    pcm: bytes


@dataclass
class Tx:
    text: str
    avg_logprob: float | None = -0.2
    temperature: float | None = 0.0


@dataclass
class Journey:
    journey_id: str
    engine: object
    stt: object
    vad: object
    user_id: str = "U1"
    started_at: float = field(default_factory=time.time)
    audio_buffer: bytearray = field(default_factory=lambda: bytearray(b"x"))
    processed_up_to_ms: int = 0
    kws: object = None
    events: list = field(default_factory=list)
    language: str | None = None


class VAD:
    def __init__(self):
        self.segs = []

    def segment_speech(self, pcm):
        return list(self.segs)

    def total_ms(self, pcm):
        return 10 ** 9


class STT:
    model_version = "stub-stt"

    def __init__(self, table, delay):
        self.table, self.delay = table, delay

    def transcribe(self, pcm):
        if self.delay:
            time.sleep(self.delay)
        return Tx(self.table.get(pcm, ""))


class Timed:
    """Accumulates call time per thread name (live = MainThread, shadow = udk-shadow)."""
    def __init__(self):
        self.t, self.n, self.lock = {}, {}, threading.Lock()

    def wrap(self, fn):
        def w(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                dt, name = time.perf_counter() - t0, threading.current_thread().name
                with self.lock:
                    self.t[name] = self.t.get(name, 0.0) + dt
                    self.n[name] = self.n.get(name, 0) + 1
        return w


class GpuSampler:
    """Samples GPU utilisation / memory every 0.2 s via nvidia-smi (whole device, all processes) while a run is timed."""
    def __init__(self):
        import shutil
        self.source = "nvidia-smi" if shutil.which("nvidia-smi") else None
        self.util, self.mem, self._stop = [], [], threading.Event()
        self._t = threading.Thread(target=self._loop, name="gpu-sampler", daemon=True)

    def _loop(self):
        import subprocess
        while not self._stop.is_set() and self.source:
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=5).stdout.strip().splitlines()[0]
                u, m = (float(x) for x in out.split(","))
                self.util.append(u); self.mem.append(m)
            except Exception:
                pass
            self._stop.wait(0.2)

    def start(self):
        self._t.start()

    def stop(self):
        self._stop.set(); self._t.join(timeout=10)

    def summary(self, which):
        xs = self.util if which == "util" else self.mem
        return None if not xs else {"mean": statistics.mean(xs), "p95": pct(xs, 95), "max": max(xs), "samples": len(xs)}


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("off", "on", "on_lite"), required=True)
    ap.add_argument("--proxy", required=True)
    ap.add_argument("--stt-delay", type=float, default=0.0)
    ap.add_argument("--segments", type=int, default=96)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu", help="cpu | cuda (models are loaded on this device, as UDK_DEVICE does live)")
    a = ap.parse_args()

    import torch
    from intent_gate import IntentGate
    from semantic import SentenceTransformerSemanticMatcher
    from udk_engine import TRIGGER_VERIFY_THRESHOLD, DecisionEvent, UDKEngine, match_transcript
    from udks import GENERAL_UDKS

    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    sem = SentenceTransformerSemanticMatcher(model_name=str(Path(a.proxy) / "semantic_minilm_l12_proxy"), device=a.device)
    gate = IntentGate(str(Path(a.proxy) / "intent_mdeberta_base_proxy"), device=a.device)
    for t in ("warm up the semantic model", "help me please"):  # warm-up outside the timed window
        sem.similarity(t, "call the police"); gate.p_distress(t)
    timed_sem, timed_gate = Timed(), Timed()
    sem.similarity = timed_sem.wrap(sem.similarity)  # live-thread semantic calls (shadow uses the uncached encoder)
    gate.p_distress = timed_gate.wrap(gate.p_distress)  # both threads call the same gate

    primary, second, scream, score9 = {}, {}, {}, {}
    segs = []
    for i in range(a.segments):
        p, s2, scr, s9 = WORKLOAD[i % len(WORKLOAD)]
        key = f"seg{i}".encode()
        primary[key], second[key] = p, s2
        if scr:
            scream[key] = scr
        if s9 is not None:
            score9[key] = s9
        segs.append(Seg(i * 3000, i * 3000 + 2000, key))

    det = types.SimpleNamespace(model_version="stub-beats", score=lambda pcm: score9.get(pcm, 0.01))
    ns = types.ModuleType("live")
    stt, stt2 = STT(primary, a.stt_delay), STT(second, 0.0)
    ns.__dict__.update({
        "DecisionEvent": DecisionEvent, "UDKEngine": UDKEngine, "match_transcript": match_transcript,
        "TRIGGER_VERIFY_THRESHOLD": TRIGGER_VERIFY_THRESHOLD, "time": time, "hashlib": hashlib, "replace": replace, "os": os,
        "PROCESSING_VERSION": "bench", "_maybe_update_language": lambda j: None, "_stt_backend": stt, "_parakeet_stt": stt2,
        "_scream_trigger_enabled": True, "_scream_detector": det, "_scream_corroboration_enabled": True,
        "scream_trigger": types.SimpleNamespace(check=lambda d, pcm: scream.get(pcm, (False, 0.02, "Screaming"))),
        "_stt_confidence_gate_enabled": False, "is_suspect": lambda t: False, "_dual_asr_guard": None, "_intent_gate": gate,
        "_separator": None, "_DECISION_RANK": {"NO_ACTION": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2},
        "_metrics": types.SimpleNamespace(detection=lambda *x: None, stt_latency=lambda *x: None), "_shadow": None})
    src = (ROOT / "api.py").read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_run_incremental_detection", "_either_stt_decisions", "_strongest",
                                                               "_intent_veto", "_decision_to_event"):
            exec(compile(ast.Module([node], []), "api.py", "exec"), ns.__dict__)
    alert_t = []
    call_t0 = [0.0]

    def emit(journey, decision, seg):
        e = ns._decision_to_event(journey, decision, seg)
        journey.events.append(e)
        alert_t.append(time.perf_counter() - call_t0[0])
        return e
    ns._emit_event = emit

    runner = None
    if a.mode != "off":
        from udk_shadow.config import ShadowConfig, runtime_snapshot
        from udk_shadow.runner import ShadowRunner
        cfg = ShadowConfig(enabled=True, intent=a.mode == "on", semantic="isolated" if a.mode == "on" else "off")
        runner = ShadowRunner(cfg, ns, ns._either_stt_decisions, gate, runtime_snapshot({}, {}))
        ns._shadow = runner

    engine = UDKEngine(list(GENERAL_UDKS), semantic_matcher=sem)
    vad = VAD()
    j = Journey("BENCH", engine, stt, vad)
    lat = []
    gpu = GpuSampler() if a.device.startswith("cuda") else None
    if gpu:
        torch.cuda.reset_peak_memory_stats()
        gpu.start()
    cpu0, wall0 = os.times(), time.perf_counter()
    for i in range(a.segments):
        vad.segs = segs[: i + 1]
        call_t0[0] = time.perf_counter()
        ns._run_incremental_detection(j, final=True)
        lat.append(time.perf_counter() - call_t0[0])
    live_wall = time.perf_counter() - wall0
    drain_s = None
    if runner is not None:
        t = time.perf_counter()
        runner.drain(600)
        drain_s = time.perf_counter() - t
    cpu1, wall1 = os.times(), time.perf_counter()
    gpu_stats = None
    if gpu:
        gpu.stop()
        gpu_stats = {"name": torch.cuda.get_device_name(0), "util_pct": gpu.summary("util"), "mem_used_mb": gpu.summary("mem"),
                     "torch_peak_allocated_mb": torch.cuda.max_memory_allocated() / 2**20, "sampler": gpu.source}
    recs = list(runner.records) if runner else []
    out = {
        "mode": a.mode, "device": a.device, "gpu": gpu_stats, "stt_delay_s": a.stt_delay, "segments": a.segments,
        "torch_threads": torch.get_num_threads(), "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(), "cpu_count": os.cpu_count(),
        "live_latency_s": {"p50": pct(lat, 50), "p95": pct(lat, 95), "max": max(lat), "mean": statistics.mean(lat)},
        "time_to_alert_s": {"p50": pct(alert_t, 50), "p95": pct(alert_t, 95), "max": max(alert_t) if alert_t else None, "n": len(alert_t)},
        "live_semantic_s": {"total": timed_sem.t.get("MainThread", 0.0), "calls": timed_sem.n.get("MainThread", 0),
                            "per_call_ms": 1000 * timed_sem.t.get("MainThread", 0.0) / max(1, timed_sem.n.get("MainThread", 0))},
        "live_intent_s": {"total": timed_gate.t.get("MainThread", 0.0), "calls": timed_gate.n.get("MainThread", 0),
                          "per_call_ms": 1000 * timed_gate.t.get("MainThread", 0.0) / max(1, timed_gate.n.get("MainThread", 0))},
        "shadow_intent_s": {"total": timed_gate.t.get("udk-shadow", 0.0), "calls": timed_gate.n.get("udk-shadow", 0)},
        "live_wall_s": live_wall, "drain_after_last_segment_s": drain_s,
        "cpu_s": (cpu1.user - cpu0.user) + (cpu1.system - cpu0.system), "wall_s": wall1 - wall0,
        "cpu_cores_used": ((cpu1.user - cpu0.user) + (cpu1.system - cpu0.system)) / (wall1 - wall0),
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, "rss_after_model_load_mb_floor": rss0 / 1024,
        "live_events": len(j.events),
        "shadow": None if runner is None else {
            "records": len(recs), "statuses": {k: v for k, v in runner.stats.items() if k.startswith("status:")},
            "dropped_queue_full": runner.stats["dropped_queue_full"], "capture_errors": runner.stats["capture_errors"],
            "processing_s": {"p50": pct([r["elapsed_s"] for r in recs], 50), "p95": pct([r["elapsed_s"] for r in recs], 95),
                             "max": max((r["elapsed_s"] for r in recs), default=None)},
            "queue_wait_s": {"p50": pct([r["runner"]["queue_wait_s"] for r in recs], 50), "p95": pct([r["runner"]["queue_wait_s"] for r in recs], 95),
                             "max": max((r["runner"]["queue_wait_s"] for r in recs), default=None)},
            "phase5_vs_live_match": sum(1 for r in recs if r.get("shadow_phase5_decision") == r["live"]["live_decision"]),
        },
    }
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("mode", "stt_delay_s", "live_latency_s", "cpu_cores_used", "peak_rss_mb")}))


if __name__ == "__main__":
    main()
