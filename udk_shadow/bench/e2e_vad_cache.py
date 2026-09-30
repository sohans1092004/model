"""Offline end-to-end impact test of the VAD classification cache: the REAL live pipeline, cache OFF vs ON.

Experiment tooling only (not in the image). It does not change api.py, vad.py, any default or any threshold.

What runs
  * The real `api` module, configured from the detection section of deploy/.env.example (the validated production
    configuration), read at start-up and never edited. The device and the intent-model path are the only values set
    per machine; a component whose model is not available is recorded as UNAVAILABLE (never as "negative").
  * The real service path, in-process: api.start_journey -> api._ingest_frame per chunk (what the WebSocket handler
    calls) -> api.stop_journey (the final flush). Real Whisper, Parakeet, semantic matcher, STT confidence gate,
    either-STT decision, sentence extras, intent veto, BEATs corroboration and scream trigger, as loaded by api.py.
  * The ONLY difference between modes: `journey.vad = VAD(cache_classifications=<mode>)`, set right after the journey
    is created and before any audio arrives. Same audio, chunk sequence, models, config, device, process, input order.

Clock
  api.py stamps each decision with time.monotonic() (the 15 s repeat window uses it). Fed faster than real time, wall
  time would compress the stream and inflate repeat escalations. The harness therefore gives the api module a virtual
  clock: monotonic() = seconds of audio delivered so far (as in a real-time stream, minus processing delay). It is
  identical in both modes and makes decisions independent of processing speed. All other time functions are real.

Capture
  The existing read-only Phase 6 hook (api._shadow.observe(journey, seg, locals(), ...)) is given a recorder that copies
  each processed segment's evidence: boundaries, audio digest, Whisper/Parakeet output, confidence-gate flag, BEATs
  evidence, decisions before/after the intent veto, intent scores, alerts and the emitted events. Backends are wrapped
  by pass-through timing proxies. Persisted output holds transcript DIGESTS only; transcript text is written solely for
  segments whose OFF/ON (or repeat) outputs differ, so each difference can be investigated.

    python udk_shadow/bench/e2e_vad_cache.py --recordings <manifest.json> --out <dir> [--chunks mixed=20,100,1000 ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import secrets
import sys
import tempfile
import time as _time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

# detection keys taken from deploy/.env.example (the validated production configuration)
DETECTION_PREFIXES = ("UDK_ENABLE_", "UDK_STT_MODEL", "UDK_DEVICE", "UDK_INTENT_GATE", "UDK_INTENT_THRESHOLD")


def production_env(env_example: Path, device: str, intent_dir: str | None) -> tuple[dict, dict]:
    """The detection env of deploy/.env.example; returns (env, notes). Only UDK_DEVICE and UDK_INTENT_GATE are set per
    machine. Without an intent model the gate is left unset -> api.py runs with it off (recorded as unavailable)."""
    env, notes = {}, {}
    for line in env_example.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.startswith(DETECTION_PREFIXES):
            env[k] = v
    notes["from_env_example"] = dict(env)
    env["UDK_DEVICE"] = device
    if intent_dir:
        env["UDK_INTENT_GATE"] = intent_dir
    else:
        env.pop("UDK_INTENT_GATE", None)
        notes["intent_gate"] = "UNAVAILABLE (no intent model directory given)"
    return env, notes


def digest(b) -> str:
    if isinstance(b, str):
        b = b.encode()
    return hashlib.blake2b(b, digest_size=8).hexdigest()


class VirtualClock:
    """Stands in for api.time: monotonic() = audio seconds delivered; everything else is the real time module."""
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def __getattr__(self, name):
        return getattr(_time, name)


class Timed:
    """Pass-through proxy that times selected methods of a backend (behaviour untouched)."""
    def __init__(self, inner, name, sink, methods):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_sink", sink)
        object.__setattr__(self, "_methods", set(methods))

    def __getattr__(self, attr):
        v = getattr(self._inner, attr)
        if attr in self._methods and callable(v):
            def timed(*a, **k):
                t = _time.perf_counter()
                try:
                    return v(*a, **k)
                finally:
                    self._sink.append((f"{self._name}.{attr}", _time.perf_counter() - t))
            return timed
        return v

    def __setattr__(self, attr, value):
        setattr(self._inner, attr, value)


def dec(d) -> dict | None:
    if d is None:
        return None
    return {"decision": d.decision, "udk_id": d.udk.udk_id if d.udk else None, "confidence": round(float(d.confidence), 4),
            "layer": d.layer, "repeated": bool(d.repeated), "reason": d.reason}


class Recorder:
    """The Phase 6 hook's observer for this experiment: copies one processed segment's evidence (read-only)."""
    def __init__(self):
        self.segments, self.intent_calls, self.timings = [], [], []

    def observe(self, journey, seg, loc, skipped, n_alerts=0, new_events=None):
        tr = loc.get("transcript")
        rec = {
            "start_ms": seg.start_ms, "end_ms": seg.end_ms, "pcm": digest(seg.pcm), "skipped": bool(skipped),
            "now_s": loc.get("now_s"),
            "whisper": None if tr is None else {"text": tr.text, "avg_logprob": _r(tr.avg_logprob), "temperature": tr.temperature,
                                                 "compression_ratio": _r(tr.compression_ratio), "model": tr.model_version},
            "parakeet": loc.get("second_text", ""),
            "kws": None if loc.get("kws_match") is None else repr(loc.get("kws_match")),
            "scream_trigger": None if "scream_peak" not in loc else {"fired": bool(loc.get("scream_fired")), "peak": _r(loc.get("scream_peak")),
                                                                        "class": loc.get("scream_class")},
            "scream_score": _r(loc.get("scream_score")),
            "stt_suspect": loc.get("stt_suspect"),
            "primary": [dec(d) for d in loc.get("primary") or []],
            "pre_veto": [dec(d) for d in loc.get("_shadow_pre_veto") or []],
            "final": dec(loc.get("decision")),
            "alerts": [dec(d) for d in loc.get("alerts") or []],
            "events": [{k: e.get(k) for k in ("event_id", "decision", "udk_id", "layer", "confidence", "audio_segment_id")}
                       for e in (new_events or [])[len(new_events or []) - n_alerts:]] if n_alerts else [],
            "intent": list(self.intent_calls),
            "component_s": list(self.timings),
        }
        self.intent_calls.clear()
        self.timings.clear()
        self.segments.append(rec)


def _r(x, n=4):
    return None if x is None else round(float(x), n)


class Harness:
    """Loads api once (models once), then runs journeys: one per (recording, chunk size, mode, repeat)."""
    def __init__(self, env: dict, prepare=None):
        self.data_dir = tempfile.mkdtemp(prefix="udk_e2e_")
        os.environ.update(env)
        os.environ["UDK_DATA_DIR"] = self.data_dir
        os.environ.setdefault("UDK_SERVICE_TOKEN", secrets.token_hex(16))
        import api  # noqa: E402  (models load here, exactly as in the service)
        from vad import VAD
        self.api, self.VAD = api, VAD
        if prepare is not None:  # tests: swap in fake backends
            prepare(api)
        self.recorder = Recorder()
        self.heartbeat = True  # False only in the harness's own negative-control test
        self.clock = VirtualClock()
        api.time = self.clock
        api._shadow = self.recorder
        t = self.recorder.timings
        if api._stt_backend is not None:
            api._stt_backend = Timed(api._stt_backend, "whisper", t, ("transcribe",))
        if api._parakeet_stt is not None:
            api._parakeet_stt = Timed(api._parakeet_stt, "parakeet", t, ("transcribe",))
        if api._scream_detector is not None:
            api._scream_detector = Timed(api._scream_detector, "beats", t, ("score", "label_probs"))
        if api._intent_gate is not None:
            gate, calls = api._intent_gate, self.recorder.intent_calls
            inner_p = gate.p_distress

            def p_distress(text):
                p = inner_p(text)
                calls.append({"text": digest(text), "p": _r(p, 6)})
                return p
            gate.p_distress = p_distress  # instance attribute: same model, same threshold; score recorded
        self.components = describe_components(api)

    def run(self, pcm: bytes, chunk_ms: int, cache: bool, label: str) -> dict:
        api = self.api
        rec = self.recorder
        rec.segments = []
        self.clock.now = 1000.0
        journey_id = f"e2e-{label}-{secrets.token_hex(4)}"
        api.start_journey(api.StartRequest(user_id="e2e", journey_id=journey_id))
        journey = api._store.get(journey_id)
        journey.vad = self.VAD(cache_classifications=cache)  # THE experimental variable
        step = int(16000 * chunk_ms / 1000) * 2
        calls, err = [], None
        cpu0, wall0 = _time.process_time(), _time.perf_counter()
        gpu = _gpu_reset()
        try:
            for seq, i in enumerate(range(0, len(pcm), step)):
                chunk = pcm[i:i + step]
                self.clock.now = 1000.0 + (i + len(chunk)) / 32000.0
                t = _time.perf_counter()
                api._ingest_frame(journey, seq, chunk, api._audio_store)
                if self.heartbeat:  # exactly what the WebSocket handler does after every frame
                    journey.last_heartbeat_at = _time.time()
                    api._db.save_journey(journey)
                calls.append(_time.perf_counter() - t)
            t = _time.perf_counter()
            api.stop_journey(journey_id, api.StopRequest())
            calls.append(_time.perf_counter() - t)
        except Exception:
            err = traceback.format_exc(limit=6)
        wall, cpu = _time.perf_counter() - wall0, _time.process_time() - cpu0
        events = [{k: e.get(k) for k in ("decision", "udk_id", "layer", "confidence", "audio_segment_id")} for e in journey.events]
        for e in events:
            e["segment"] = e.pop("audio_segment_id").split(":", 1)[1]  # "start-end" (journey id stripped)
        return {"label": label, "cache": cache, "chunk_ms": chunk_ms, "segments": rec.segments, "events": events,
                "error": err, "calls": len(calls), "call_s": calls, "wall_s": wall, "cpu_s": cpu,
                "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, "gpu": _gpu_peak(gpu),
                "flag_in_journey": journey.vad.cache_classifications, "final_status": journey.status}


def _inner(x):
    return object.__getattribute__(x, "_inner") if isinstance(x, Timed) else x


def describe_components(api) -> dict:
    """What ACTUALLY loaded (api.py's loaders fall back silently: Whisper -> MockSTT, others -> None)."""
    def cls(x):
        return None if x is None else type(_inner(x)).__name__
    stt = _inner(api._stt_backend)
    whisper = cls(stt)
    return {
        "whisper": whisper if whisper == "FasterWhisperSTT" else f"UNAVAILABLE ({whisper})",
        "whisper_model": getattr(stt, "model_version", None),
        "whisper_device": str(getattr(getattr(getattr(stt, "_model", None), "model", None), "device", "?")),  # ctranslate2
        "parakeet": cls(api._parakeet_stt) or "UNAVAILABLE",
        "parakeet_providers": getattr(_inner(api._parakeet_stt), "providers", None) if api._parakeet_stt is not None else None,
        "semantic": cls(api._semantic_matcher) or "UNAVAILABLE",
        "stt_confidence_gate": bool(api._stt_confidence_gate_enabled),
        "beats": cls(api._scream_detector) or "UNAVAILABLE",
        "scream_trigger": bool(api._scream_trigger_enabled and api._scream_detector is not None),
        "scream_corroboration": bool(api._scream_corroboration_enabled and api._scream_detector is not None),
        "intent_gate": cls(api._intent_gate) or "UNAVAILABLE",
        "intent_threshold": getattr(api._intent_gate, "threshold", None),
        "kws": cls(api._kws_backend) or "off", "dual_asr": cls(api._dual_asr_guard) or "off",
        "separation": cls(api._separator) or "off", "language_id": cls(api._language_detector) or "off",
        "device": api._device(), "processing_version": api.PROCESSING_VERSION,
    }


def _gpu_reset():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            return True
    except Exception:
        pass
    return False


def _gpu_peak(active):
    if not active:
        return None
    import torch
    return {"torch_peak_alloc_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1)}


# ---------------------------------------------------------------------------------------------------------- comparison
STT_KEYS = ("whisper", "parakeet", "stt_suspect")
ACOUSTIC_KEYS = ("scream_trigger", "scream_score")


def _seg_key(s):
    return (s["start_ms"], s["end_ms"])


def _wtext(w):
    return None if w is None else w.get("text", w.get("text_digest"))


def _norm_whisper(w):
    return None if w is None else {"text": _wtext(w), **{k: w.get(k) for k in ("avg_logprob", "temperature", "compression_ratio")}}


def compare_segment(a: dict, b: dict) -> dict:
    """Field-by-field equality of two processed segments with identical boundaries."""
    return {
        "audio": a["pcm"] == b["pcm"],
        "whisper_text": _wtext(a["whisper"]) == _wtext(b["whisper"]),
        "whisper_meta": _norm_whisper(a["whisper"]) == _norm_whisper(b["whisper"]),
        "parakeet": a["parakeet"] == b["parakeet"],
        "stt_suspect": a["stt_suspect"] == b["stt_suspect"],
        "acoustic": all(a[k] == b[k] for k in ACOUSTIC_KEYS),
        "udk_primary": a["primary"] == b["primary"],
        "pre_veto": a["pre_veto"] == b["pre_veto"],
        "intent": [c["p"] for c in a["intent"]] == [c["p"] for c in b["intent"]],
        "final": a["final"] == b["final"],
        "alerts": a["alerts"] == b["alerts"],
        "skipped": a["skipped"] == b["skipped"],
    }


def _overlaps_earlier(segs, idx) -> int:
    s = segs[idx]
    return max([0] + [min(s["end_ms"], p["end_ms"]) - max(s["start_ms"], p["start_ms"]) for p in segs[:idx]])


def _ev(e):
    return (e["segment"], e["decision"], e["udk_id"], e["layer"])


def compare_runs(off: dict, on: dict, off_rep: dict | None, on_rep: dict | None, oneshot: list) -> dict:
    """OFF vs ON for one recording x chunk size, with every difference classified (see CLASSES)."""
    oneshot = [tuple(x) for x in oneshot]
    so, sn = off["segments"], on["segments"]
    ko, kn = [_seg_key(s) for s in so], [_seg_key(s) for s in sn]
    by_on = {k: s for k, s in zip(kn, sn)}
    rep_off = {_seg_key(s): s for s in off_rep["segments"]} if off_rep else {}
    rep_on = {_seg_key(s): s for s in on_rep["segments"]} if on_rep else {}
    diffs = []
    # 1) segments OFF processed that ON did not. Three VAD-defect shapes, each named; an OFF-only segment that ALERTED
    #    is flagged for manual review (ON will not raise that alert from that audio)
    for i, s in enumerate(so):
        if _seg_key(s) in by_on:
            continue
        ov = _overlaps_earlier(so, i)
        ov_ref = max([0] + [min(s["end_ms"], e) - max(s["start_ms"], b) for b, e in oneshot])
        best = _best_ref(s, oneshot)
        designed = _overlaps_earlier([{"start_ms": b, "end_ms": e} for b, e in oneshot], oneshot.index(best)) if best else 0
        if ov > designed + 30:  # beyond the one-shot's own (designed) overlap, with one frame of drift tolerance
            why = "re-processing: OFF handed already-processed audio to STT again"
        elif ov_ref > 0:
            why = "drifted boundary: OFF cut a one-shot utterance at a different frame"
        else:
            why = "spurious segment: audio the single-pass VAD does not call speech (classifier state drift)"
        diffs.append({"kind": "segment_only_off", "segment": _seg_key(s), "overlap_with_earlier_off_ms": ov,
                      "overlap_with_oneshot_ms": ov_ref, "class": "expected_vad_correction", "detail": why,
                      "alerts": s["alerts"], "needs_review": bool(s["alerts"])})
    # 2) segments ON processed that OFF did not
    oneshot_set = {tuple(x) for x in oneshot}
    for s in sn:
        if _seg_key(s) in set(ko):
            continue
        in_ref = _seg_key(s) in oneshot_set
        diffs.append({"kind": "segment_only_on", "segment": _seg_key(s), "on_equals_oneshot_segment": in_ref,
                      "class": "expected_vad_correction" if in_ref else "genuine_regression",
                      "alerts": s["alerts"], "detail": "ON processed the one-shot segment; OFF processed drifted boundaries instead"
                      if in_ref else "ON segment is not a one-shot segment"})
    # 3) same boundaries: compare every stage
    field_diff_counts = {}
    for s in so:
        k = _seg_key(s)
        if k not in by_on:
            continue
        c = compare_segment(s, by_on[k])
        bad = [f for f, ok in c.items() if not ok]
        for f in bad:
            field_diff_counts[f] = field_diff_counts.get(f, 0) + 1
        if not bad:
            continue
        noise_off = k in rep_off and not all(compare_segment(s, rep_off[k]).values())
        noise_on = k in rep_on and not all(compare_segment(by_on[k], rep_on[k]).values())
        stt_changed = any(f in bad for f in ("whisper_text", "whisper_meta", "parakeet"))
        only_state = set(bad) <= {"udk_primary", "pre_veto", "final", "alerts", "intent"} and not stt_changed
        if not c["audio"]:
            cls = "environment_tooling"
        elif noise_off or noise_on:
            cls = "stt_nondeterminism" if stt_changed else "model_nondeterminism"
        elif only_state:
            cls = "state_from_earlier_difference"  # resolved below against the engine history
        else:
            cls = "unable_to_determine"
        entry = {"kind": "same_segment_different_output", "segment": k, "fields": bad, "class": cls,
                 "repeat_off_differs": noise_off, "repeat_on_differs": noise_on,
                 "off": {f: s[f] for f in ("primary", "pre_veto", "final", "alerts")},
                 "on": {f: by_on[k][f] for f in ("primary", "pre_veto", "final", "alerts")}}
        if stt_changed:  # text kept ONLY for differing segments, so the difference can be investigated
            entry["text"] = {"off_whisper": (s["whisper"] or {}).get("text"), "on_whisper": (by_on[k]["whisper"] or {}).get("text"),
                             "off_parakeet": s["parakeet"], "on_parakeet": by_on[k]["parakeet"]}
        diffs.append(entry)
    # state differences: explained iff an earlier OFF-only (re-processed) segment alerted, so the engine's repeat /
    # distinct-UDK history differs; otherwise unexplained
    prior_off_only_alerts = sorted(d["segment"] for d in diffs if d["kind"] == "segment_only_off" and d["alerts"])
    for d in diffs:
        if d["class"] == "state_from_earlier_difference":
            earlier = [p for p in prior_off_only_alerts if p[1] <= d["segment"][1]]
            d["class"] = "expected_vad_correction" if earlier else "unable_to_determine"
            d["detail"] = (f"engine history differs: OFF re-processed alerting audio earlier at {earlier[:3]}" if earlier
                           else "decision differs on identical inputs with no earlier difference")
    # events
    eo, en = sorted(_ev(e) for e in off["events"]), sorted(_ev(e) for e in on["events"])
    only_off, only_on = _pair_events(eo, en)
    tier_changes, only_off, only_on = _tier_changes(only_off, only_on)
    rep_all_off = [e for e in off["events"] if e["decision"] == "TRIGGER_ALL"]
    repeat_all = _repeat_induced(off, on)
    return {
        "segments_off": len(so), "segments_on": len(sn), "same_boundaries": ko == kn,
        "on_equals_oneshot": [k for k in kn] == [tuple(x) for x in oneshot],
        "off_equals_oneshot": [k for k in ko] == [tuple(x) for x in oneshot],
        "field_diff_counts": field_diff_counts,
        "events_off": len(eo), "events_on": len(en), "events_only_off": only_off, "events_only_on": only_on,
        "trigger_all_off": len(rep_all_off), "trigger_all_on": sum(e["decision"] == "TRIGGER_ALL" for e in on["events"]),
        "repeat_induced_trigger_all_off": repeat_all["off"], "repeat_induced_trigger_all_on": repeat_all["on"],
        "tier_changes": tier_changes,  # same utterance + UDK + layer, different decision: (off_event, on_event)
        "timing": _timing(so, sn, oneshot),
        "events_exact_key_only_off": [e for e in eo if e not in en], "events_exact_key_only_on": [e for e in en if e not in eo],
        "duplicate_alerts_off": _duplicates(off, oneshot), "duplicate_alerts_on": _duplicates(on, oneshot),
        "determinism": {"off_vs_off_repeat_events": None if off_rep is None else eo == sorted(_ev(e) for e in off_rep["events"]),
                        "on_vs_on_repeat_events": None if on_rep is None else en == sorted(_ev(e) for e in on_rep["events"]),
                        "off_vs_off_repeat_segments": None if off_rep is None else ko == [_seg_key(s) for s in off_rep["segments"]],
                        "on_vs_on_repeat_segments": None if on_rep is None else kn == [_seg_key(s) for s in on_rep["segments"]]},
        "differences": diffs,
        "errors": {"off": off["error"], "on": on["error"]},
        # a journey that did not end COMPLETE (e.g. heartbeat timeout) skipped the final flush: harness artefact, never a result
        "final_status": {"off": off.get("final_status", "COMPLETE"), "on": on.get("final_status", "COMPLETE")},
    }


def _repeat_induced(off, on) -> dict:
    """TRIGGER_ALL whose reason is a repetition, per mode; "induced" = a repeat-ALL for a UDK the other mode never
    escalated by repetition."""
    def rep(run):
        out = []
        for s in run["segments"]:
            for a in s["alerts"]:
                if a["decision"] == "TRIGGER_ALL" and "repeat" in (a["reason"] or "").lower():
                    out.append((s["start_ms"], s["end_ms"], a["udk_id"]))
        return out
    ro, rn = rep(off), rep(on)
    return {"off": [x for x in ro if x[2] not in {y[2] for y in rn}], "on": [x for x in rn if x[2] not in {y[2] for y in ro}],
            "off_all": ro, "on_all": rn}


def _span(seg: str) -> tuple:
    a, b = seg.split("-")
    return int(a), int(b)


def _pair_events(eo: list, en: list) -> tuple[list, list]:
    """Pair OFF and ON events that are the same alert for the same utterance: same decision, UDK and layer, and
    overlapping audio (OFF may have cut the utterance a frame differently). Returns the unpaired events of each side."""
    left_on = list(en)
    only_off = []
    for e in eo:
        s = _span(e[0])
        m = _best_match(s, [x for x in left_on if x[1:] == e[1:]])
        if m is None:
            only_off.append(e)
        else:
            left_on.remove(m)
    return only_off, left_on


def _ovl(a, b) -> int:
    return min(a[1], b[1]) - max(a[0], b[0])


def _best_match(span, candidates):
    """The candidate event whose segment overlaps `span` most (None if none overlaps)."""
    best = max(candidates, key=lambda x: _ovl(span, _span(x[0])), default=None)
    return best if best is not None and _ovl(span, _span(best[0])) > 0 else None


def _best_ref(seg, oneshot):
    """The one-shot utterance this processed segment overlaps most (None if none)."""
    s = (seg["start_ms"], seg["end_ms"])
    mid = (s[0] + s[1]) / 2  # ties (e.g. a segment spanning a forced cut) go to the utterance with the closest centre
    best = max((tuple(x) for x in oneshot), key=lambda r: (_ovl(s, r), -abs((r[0] + r[1]) / 2 - mid)), default=None)
    return best if best is not None and _ovl(s, best) > 0 else None


def _tier_changes(only_off, only_on):
    """Unpaired events that ARE the same alert for the same utterance at a different tier (e.g. OFF TRIGGER_ALL because
    re-processed audio filled the repeat window, ON TRIGGER_VERIFY)."""
    changes, left_on, left_off = [], list(only_on), []
    for e in only_off:
        s = _span(e[0])
        m = _best_match(s, [x for x in left_on if x[2:] == e[2:]])
        if m is None:
            left_off.append(e)
        else:
            left_on.remove(m)
            changes.append((e, m))
    return changes, left_off, left_on


def _timing(so, sn, oneshot) -> dict:
    """Per one-shot utterance: stream time (virtual clock, s) at which each mode first DECIDED on audio of it (non-empty transcript), and first
    alerted on it. delay = OFF - ON (> 0: OFF handled that utterance later than ON)."""
    oneshot = [tuple(x) for x in oneshot]

    def first(segs, b, e, alerting):  # each processed segment counts for the ONE utterance it overlaps most
        ts = [s["now_s"] for s in segs if s["now_s"] is not None and _best_ref(s, oneshot) == (b, e)
              and (s["alerts"] if alerting else True)]
        return min(ts) if ts else None
    rows = []
    for b, e in oneshot:
        fo, fn = first(so, b, e, False), first(sn, b, e, False)
        ao, an = first(so, b, e, True), first(sn, b, e, True)
        rows.append({"utterance": (b, e), "first_decision_delay_s": None if fo is None or fn is None else round(fo - fn, 3),
                     "first_alert_delay_s": None if ao is None or an is None else round(ao - an, 3),
                     "alert_only_off": ao is not None and an is None, "alert_only_on": an is not None and ao is None})
    return rows


def _duplicates(run, oneshot=()) -> list:
    """Alerts for the same UDK from segments that overlap in audio. `designed` = both segments are one-shot segments,
    i.e. the overlap the VAD keeps ON PURPOSE after a forced 8 s cut (existing intentional behaviour)."""
    ref = {tuple(x) for x in oneshot}
    evs = [(_span(e["segment"]), e["udk_id"], e["decision"]) for e in run["events"]]
    out = []
    for i, (si, ui, di) in enumerate(evs):
        for sj, uj, dj in evs[:i]:
            if ui == uj and min(si[1], sj[1]) - max(si[0], sj[0]) > 0 and si != sj:
                out.append({"segment": si, "earlier_segment": sj, "udk_id": ui, "decision": di,
                            "designed": si in ref and sj in ref})
    return out


def strip_text(run: dict) -> dict:
    """Persistable copy: transcript text replaced by digests (differing segments keep text in the comparison)."""
    out = dict(run)
    segs = []
    for s in run["segments"]:
        s = dict(s)
        if s["whisper"] is not None:
            w = dict(s["whisper"])
            t = w.pop("text")
            w["text_digest"], w["words"] = digest(t), len(t.split())
            s["whisper"] = w
        p = s["parakeet"] or ""
        s["parakeet"] = {"text_digest": digest(p), "words": len(p.split())}
        s["alerts"] = [{k: v for k, v in a.items()} for a in s["alerts"]]
        segs.append(s)
    out["segments"] = segs
    return out


class ManifestPhraseSTT:
    """DRY-RUN ONLY (not a real-STT result): returns the recording's manifest phrase when the segment contains
    single-pass webrtcvad speech, else "" -- the stub of the earlier segmentation experiment, now under the virtual clock."""
    def __init__(self, holder, name):
        self.holder, self.model_version = holder, f"manifest-phrase-stub-{name}"

    def transcribe(self, pcm):
        import webrtcvad
        from stt import Transcript
        v = webrtcvad.Vad(1)
        speech = any(v.is_speech(pcm[i:i + 960], 16000) for i in range(0, len(pcm) - 959, 960))
        return Transcript(self.holder.get("phrase", "") if speech else "", self.model_version)


def dry_run_prepare(holder):
    def prepare(api):
        api._stt_backend, api._parakeet_stt = ManifestPhraseSTT(holder, "whisper"), ManifestPhraseSTT(holder, "parakeet")
        api._scream_detector = api._intent_gate = api._semantic_matcher = None
    return prepare


def percentiles(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]  # noqa: E731
    return {"n": len(xs), "p50_ms": round(1000 * q(0.5), 2), "p95_ms": round(1000 * q(0.95), 2), "max_ms": round(1000 * xs[-1], 2),
            "total_s": round(sum(xs), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", required=True, help="JSON list of {id, path, set, phrase?, original}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunks", nargs="+", default=["mixed=20,100,1000", "media=100,1000"])
    ap.add_argument("--repeats", type=int, default=2, help="runs per mode (>=2 measures run-to-run nondeterminism)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--intent-dir", default=None)
    ap.add_argument("--only", default=None, help="comma list of recording ids (smoke runs)")
    ap.add_argument("--allow-missing-whisper", action="store_true", help="tooling checks only; results are not a real-STT test")
    ap.add_argument("--dry-run-manifest-stt", action="store_true",
                    help="NO real models: manifest-phrase STT stub, BEATs/intent/semantic off (harness + clock check only)")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    env, notes = production_env(ROOT / "deploy" / ".env.example", a.device, a.intent_dir)
    t0 = _time.perf_counter()
    holder = {}
    if a.dry_run_manifest_stt:
        env = {k: ("0" if k.startswith("UDK_ENABLE_") else v) for k, v in env.items()}
        notes["dry_run"] = "manifest-phrase STT stub; BEATs, intent, semantic OFF -- NOT a real-pipeline result"
        a.allow_missing_whisper = True
    h = Harness(env, prepare=dry_run_prepare(holder) if a.dry_run_manifest_stt else None)
    load_s = _time.perf_counter() - t0
    print("components", json.dumps(h.components), flush=True)
    if h.components["whisper"].startswith("UNAVAILABLE") and not a.allow_missing_whisper:
        raise SystemExit("Whisper did not load (api.py fell back to MockSTT): refusing to run a real-STT comparison")
    import segmentation_integrity as si
    from vad import VAD
    recs = json.loads(Path(a.recordings).read_text())
    if a.only:
        keep = set(a.only.split(","))
        recs = [r for r in recs if r["id"] in keep]
    chunks = {k: [int(x) for x in v.split(",")] for k, v in (c.split("=") for c in a.chunks)}
    summary = []
    for r in recs:
        pcm = si.decode(Path(r["path"]))
        holder["phrase"] = r.get("phrase") or ""
        oneshot = [(s.start_ms, s.end_ms) for s in VAD().segment_speech(pcm)]
        for c in chunks.get(r["set"], []):
            runs = {}
            for rep in range(a.repeats):  # interleaved: off, on, off, on ...
                for mode, cache in (("off", False), ("on", True)):
                    runs[(mode, rep)] = h.run(pcm, c, cache, f"{r['id']}-{c}-{mode}{rep}")
            cmp_ = compare_runs(runs[("off", 0)], runs[("on", 0)], runs.get(("off", 1)), runs.get(("on", 1)), oneshot)
            cmp_.update(id=r["id"], set=r["set"], chunk_ms=c, audio_s=round(len(pcm) / 32000, 2),
                        perf={f"{m}{rp}": {"calls": percentiles(x["call_s"]), "wall_s": round(x["wall_s"], 3), "cpu_s": round(x["cpu_s"], 3),
                                           "peak_rss_mb": round(x["peak_rss_mb"], 1), "gpu": x["gpu"],
                                           "segment_component_s": _component_totals(x)} for (m, rp), x in runs.items()},
                        flags={f"{m}{rp}": x["flag_in_journey"] for (m, rp), x in runs.items()})
            summary.append(cmp_)
            (out / "runs" / f"{r['id']}_{c}.json").write_text(json.dumps(
                {"comparison": cmp_, "runs": {f"{m}{rp}": strip_text(x) for (m, rp), x in runs.items()}}, indent=1, default=str))
            bad = {m: x["final_status"] for m, x in runs.items() if x["final_status"] != "COMPLETE"}
            if bad:
                cmp_["differences"].append({"kind": "journey_not_complete", "segment": None, "class": "environment_tooling",
                                            "detail": f"journeys not COMPLETE: {bad}"})
            cls = sorted({d["class"] for d in cmp_["differences"]})
            print(f"{r['id']:10s} {c:5d}ms seg off/on {cmp_['segments_off']:3d}/{cmp_['segments_on']:3d} ev off/on "
                  f"{cmp_['events_off']}/{cmp_['events_on']} ALL off/on {cmp_['trigger_all_off']}/{cmp_['trigger_all_on']} "
                  f"on==oneshot {cmp_['on_equals_oneshot']} diffs {len(cmp_['differences'])} {cls} err={bool(cmp_['errors']['off'] or cmp_['errors']['on'])}",
                  flush=True)
    env_report = {"python": platform.python_version(), "machine": platform.machine(), "cpu_count": os.cpu_count(), "model_load_s": round(load_s, 1),
                  "env": env, "notes": notes, "components": h.components, "chunks": chunks, "repeats": a.repeats,
                  "clock": "virtual: monotonic() = audio seconds delivered", "recordings": len(recs)}
    try:
        import torch
        env_report["torch"] = torch.__version__
        env_report["cuda"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        env_report["torch"] = None
    (out / "summary.json").write_text(json.dumps({"environment": env_report, "comparisons": summary}, indent=1, default=str))
    print("DONE", json.dumps({"rows": len(summary), "components": h.components}))


def _component_totals(run):
    tot = {}
    for s in run["segments"]:
        for name, sec in s["component_s"]:
            tot[name] = tot.get(name, 0.0) + sec
    return {k: round(v, 3) for k, v in tot.items()}


if __name__ == "__main__":
    main()
