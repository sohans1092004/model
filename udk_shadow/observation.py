"""SegmentObservation: what the live loop already computed for one finalized VAD segment, copied (never
referenced mutably) in the live thread. Contract §8. No audio is captured: `seg.pcm` and the journey buffer
are never read or stored.

capture() reads the live loop's locals by NAME with .get(): variables that exist only under some flags
(scream_peak / scream_class) or only after the empty-transcript skip are never evaluated in the live
frame, so a disabled feature cannot raise here. Values that are stale from a previous loop iteration are
never read: on a skipped segment only the fields assigned before the skip (api.py:459-474) are used.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from udk_shadow.config import OBSERVATION_SCHEMA


def decision_dict(d) -> dict:
    u = d.udk
    return {"decision": d.decision, "udk_id": u.udk_id if u else None, "udk_type": u.udk_type if u else None,
            "phrase": u.phrase if u else None, "layer": d.layer, "confidence": float(d.confidence),
            "repeated": bool(d.repeated), "reason": d.reason, "transcript": d.transcript}


@dataclass
class SegmentObservation:
    schema: str
    journey_id: str
    segment_id: str  # == live audio_segment_id
    start_ms: int
    end_ms: int
    audio_ts: float  # journey.started_at + start_ms / 1000 (audio clock)
    journey_started_at: float
    observed_at: float  # wall clock when captured (diagnostics only)
    language: str | None
    skipped_live: bool  # live skipped this segment (no text on either STT, no KWS, no scream): api.py:479
    stt: dict
    acoustic: dict
    now_s: float | None = None  # live monotonic clock passed to the engine (None when skipped)
    pre_state: tuple | None = None
    post_state: tuple | None = None
    udks: list = field(default_factory=list)
    semantic_matcher: object = None  # live object reference; shadow uses it only through an isolated view
    kws_match: object = None
    live: dict = field(default_factory=dict)


def capture(journey, seg, loc: dict, skipped: bool, n_alerts: int, new_events: list, live_mod) -> SegmentObservation:
    g = lambda name: getattr(live_mod, name, None)
    transcript = loc.get("transcript")
    trigger_ran = bool(g("_scream_trigger_enabled")) and g("_scream_detector") is not None
    acoustic = {"trigger_enabled": bool(g("_scream_trigger_enabled")), "corroboration_enabled": bool(g("_scream_corroboration_enabled")),
                "detector_loaded": g("_scream_detector") is not None, "trigger_ran": trigger_ran,
                "scream_fired": bool(loc.get("scream_fired", False)),
                "scream_peak": float(loc["scream_peak"]) if trigger_ran and "scream_peak" in loc else None,
                "scream_class": loc.get("scream_class") if trigger_ran else None,
                # None stays None: not computed when the flag is off or the segment was skipped (api.py:481)
                "scream_score": None if skipped or loc.get("scream_score") is None else float(loc["scream_score"])}
    stt = {"primary_text": getattr(transcript, "text", "") or "",
           "primary_avg_logprob": getattr(transcript, "avg_logprob", None),
           "primary_temperature": getattr(transcript, "temperature", None),
           "second_text": loc.get("second_text") or "",
           "second_stt_loaded": g("_parakeet_stt") is not None,
           "stt_suspect": None if skipped else bool(loc.get("stt_suspect", False)),
           "dual_asr_disagreement": None if skipped else bool(loc.get("dual_asr_disagreement", False)),
           "kws_match": None if loc.get("kws_match") is None else repr(loc.get("kws_match"))}
    seg_id = f"{journey.journey_id}:{seg.start_ms}-{seg.end_ms}"
    obs = SegmentObservation(OBSERVATION_SCHEMA, journey.journey_id, seg_id, int(seg.start_ms), int(seg.end_ms),
                             journey.started_at + seg.start_ms / 1000.0, journey.started_at, time.time(),
                             getattr(journey, "language", None), skipped, stt, acoustic)
    if skipped:
        obs.live = {"emitted_events": [], "decisions": [], "pre_veto": [], "separation_recovered": False,
                    "intent_gate_loaded": g("_intent_gate") is not None}
        return obs
    obs.now_s = float(loc["now_s"])
    obs.pre_state = loc["pre_state"]  # already a deep copy made by UDKEngine.snapshot()
    obs.post_state = journey.engine.snapshot()  # a fresh copy; the live engine is not modified
    obs.udks = list(journey.engine.udks)
    obs.semantic_matcher = journey.engine.semantic_matcher
    obs.kws_match = loc.get("kws_match")
    decisions, pre_veto, primary = loc["decisions"], loc.get("_shadow_pre_veto"), loc["primary"]
    decision = loc["decision"]
    emitted = new_events[len(new_events) - n_alerts:] if n_alerts else []
    obs.live = {"pre_veto": [decision_dict(d) for d in (pre_veto or [])],
                "pre_veto_is_primary": pre_veto is primary if pre_veto is not None else None,
                "decisions": [decision_dict(d) for d in decisions],
                "separation_recovered": decision is not decisions[0],
                "intent_gate_loaded": g("_intent_gate") is not None,
                "emitted_events": [{k: e.get(k) for k in ("event_id", "decision", "udk_id", "udk_type", "layer", "confidence",
                                                          "audio_segment_id", "transcript")} for e in emitted]}
    return obs
