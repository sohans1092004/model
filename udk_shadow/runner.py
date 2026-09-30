"""ShadowRunner: the only object api.py talks to.

observe(journey, seg, loc, skipped, n_alerts, new_events)   called in the LIVE thread after the segment's live
    events were emitted. It copies the needed fields (observation.capture), enqueues them with put_nowait and
    returns. It never raises (every exception is caught and counted), never blocks (a full queue drops the
    NEW observation and counts it), and never touches live state.
A single daemon worker thread processes observations FIFO (so each journey's context stays ordered) and
appends records to a bounded deque; an optional JSONL sink (size-capped, rotates once) persists them with
transcripts redacted unless UDK_SHADOW_LOG_TEXT=1. Raw audio is never captured.
`synchronous=True` (tests only) processes inline, still inside the same try/except.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import threading
import time
from collections import Counter, deque

from udk_shadow.config import ShadowConfig
from udk_shadow.context import ContextBuffer
from udk_shadow.observation import capture
from udk_shadow.processor import ShadowProcessor

TEXT_KEYS = ("transcript", "primary_text", "second_text", "text", "other_text", "veto_other_text")


def _redact(o):
    if isinstance(o, dict):
        return {k: ({"sha256": hashlib.sha256(v.encode()).hexdigest()[:16], "len": len(v)} if k in TEXT_KEYS and isinstance(v, str)
                    else _redact(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [_redact(v) for v in o]
    return o


class JsonlSink:
    def __init__(self, path: str, max_bytes: int, log_text: bool):
        self.path, self.max_bytes, self.log_text = path, max_bytes, log_text
        self.rotations = 0

    def write(self, rec: dict) -> None:
        line = json.dumps(rec if self.log_text else _redact(rec), default=str, ensure_ascii=False) + "\n"
        if os.path.exists(self.path) and os.path.getsize(self.path) + len(line.encode()) > self.max_bytes:
            os.replace(self.path, self.path + ".1")  # keep exactly one backup: bounded disk use
            self.rotations += 1
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)


class ShadowRunner:
    def __init__(self, cfg: ShadowConfig, live_mod, either_fn, intent_gate=None, runtime: dict | None = None,
                 synchronous: bool = False, stages: dict | None = None, process_started_at: float | None = None):
        self.cfg, self.live_mod, self.synchronous = cfg, live_mod, synchronous
        self.stats = Counter()
        self.records: deque = deque(maxlen=cfg.records_max)
        self.process_started_at = process_started_at if process_started_at is not None else time.time()
        proc = ShadowProcessor(cfg, None, either_fn, intent_gate, runtime, stages=stages)
        w = proc.context_cfg.sec("window")
        proc.context = ContextBuffer(cfg.journeys_max, cfg.context_segments, w["window_s"], w["max_turns"], self.process_started_at)
        self.processor = proc
        from udk_shadow.config import effective_settings
        try:
            proc.effective = effective_settings(None, live_mod, intent_gate, proc.policy, proc.context_cfg, cfg)
        except Exception as e:  # diagnostics must never stop shadow (or the service) from starting
            proc.effective = {"error": f"{type(e).__name__}: {e}"}
        self.sink = JsonlSink(cfg.log_path, cfg.log_max_bytes, cfg.log_text) if cfg.log_path else None
        self._q: queue.Queue = queue.Queue(maxsize=cfg.queue_max)
        self._worker = None
        if not synchronous:
            self._worker = threading.Thread(target=self._loop, name="udk-shadow", daemon=True)
            self._worker.start()

    # -------------------------------------------------------------- live thread
    def observe(self, journey, seg, loc, skipped: bool, n_alerts: int = 0, new_events=None) -> None:
        try:
            obs = capture(journey, seg, loc, skipped, n_alerts, new_events or [], self.live_mod)
            self.stats["observed"] += 1
            if self.synchronous:
                self._handle(obs)
                return
            try:
                self._q.put_nowait(obs)
            except queue.Full:
                self.stats["dropped_queue_full"] += 1
                try:
                    self.processor.context.note_gap(obs.journey_id)
                except Exception:
                    pass
        except Exception as e:  # nothing may escape into the live loop
            self.stats["capture_errors"] += 1
            self.stats[f"capture_error:{type(e).__name__}"] += 1

    # -------------------------------------------------------------- worker
    def _loop(self) -> None:
        while True:
            obs = self._q.get()
            try:
                if obs is None:
                    return
                self._handle(obs)
            finally:
                self._q.task_done()

    def _handle(self, obs) -> None:
        t_start = time.time()  # queue wait = t_start - obs.observed_at (both wall clock)
        try:
            rec = self.processor.process(obs, sampled=self.cfg.sampled(obs.segment_id))
        except Exception as e:  # processor already isolates stages; this is the last line of defence
            rec = {"schema": "udk_shadow.record/1", "segment_id": getattr(obs, "segment_id", None), "status": "failed",
                   "errors": [{"stage": "processor", "type": type(e).__name__, "message": str(e)[:500]}]}
        rec["runner"] = {"queue_wait_s": round(max(0.0, t_start - obs.observed_at), 6),
                         "dropped_queue_full": self.stats["dropped_queue_full"], "evicted_records": self.stats["evicted_records"],
                         "context_journey_evictions": self.processor.context.evictions}
        self.stats[f"status:{rec.get('status')}"] += 1
        if len(self.records) == self.records.maxlen:
            self.stats["evicted_records"] += 1
        self.records.append(rec)
        if self.sink is not None:
            try:
                self.sink.write(rec)
            except Exception as e:
                self.stats["sink_errors"] += 1
                self.stats[f"sink_error:{type(e).__name__}"] += 1

    def drain(self, timeout_s: float = 30.0) -> bool:
        """Tests / shutdown: wait until queued observations are processed."""
        if self.synchronous:
            return True
        end = time.monotonic() + timeout_s
        while self._q.unfinished_tasks and time.monotonic() < end:
            time.sleep(0.01)
        return not self._q.unfinished_tasks


def load(live_mod, either_fn, intent_gate, components: dict, env=None) -> ShadowRunner | None:
    """Called once by api.py. Returns None (shadow OFF) unless UDK_SHADOW_MODE=1; any error while building the
    runner also returns None -- a broken shadow can never stop the service from starting."""
    from udk_shadow.config import runtime_snapshot
    try:
        cfg = ShadowConfig.from_env(env)
        if not cfg.enabled:
            return None
        from udk_shadow import selfcheck
        chk = selfcheck.run(live_mod, either_fn)
        if not chk["ok"]:
            print(f"shadow mode requested but the start-up self-check failed ({chk['status']}: {chk['errors']}) -- shadow OFF, "
                  "live unaffected", flush=True)
            return None
        runner = ShadowRunner(cfg, live_mod, either_fn, intent_gate, runtime_snapshot(env, components))
        print(f"shadow mode ON (udk_shadow, self-check ok): sample={cfg.sample_rate} queue={cfg.queue_max} records={cfg.records_max} "
              f"sink={'on' if cfg.log_path else 'off'}", flush=True)
        return runner
    except Exception as e:
        import warnings
        warnings.warn(f"shadow mode requested but failed to start ({type(e).__name__}: {e}) -- shadow OFF, live unaffected")
        return None
