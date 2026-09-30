"""Shadow-mode configuration (environment) and runtime diagnostics.

All shadow settings are read from UDK_SHADOW_* variables; none of the existing production flags are read
for shadow behaviour or changed. Defaults are chosen so an enabled shadow is bounded:

  UDK_SHADOW_MODE              "1" enables shadow mode. Anything else (default: unset) = OFF, no hook work.
  UDK_SHADOW_SAMPLE_RATE       fraction of segments fully processed, deterministic by segment_id (1.0).
                               The context buffer is updated for every observed segment regardless.
  UDK_SHADOW_QUEUE_MAX         observations waiting for the worker (256). Full -> the NEW observation is
                               dropped and counted (live never waits).
  UDK_SHADOW_RECORDS_MAX       shadow records kept in memory (1000). Full -> oldest evicted, counted.
  UDK_SHADOW_JOURNEYS_MAX      journeys with a context buffer (512). Full -> least-recently-used evicted.
  UDK_SHADOW_CONTEXT_SEGMENTS  segments kept per journey (32); also pruned to the Phase 3 window.
  UDK_SHADOW_LOG_PATH          optional JSONL sink (default: none, nothing written to disk).
  UDK_SHADOW_LOG_MAX_BYTES     sink size cap (50 MB); at the cap the file rotates once to <path>.1.
  UDK_SHADOW_LOG_TEXT          "1" writes transcripts to the sink; default "0" writes sha256/length only.
  UDK_SHADOW_NO_TEXT_TURNS     "exclude" (default: live has no notion of skipped segments, so they are not
                               context turns) or "include_empty" (kept as empty-text turns). Recorded.
  UDK_SHADOW_SEMANTIC          "isolated" (default: replay uses the live model through its UNCACHED encode, so
                               the live lru cache is never touched) or "off" (replay without semantic matching;
                               records replay_fidelity="no_semantic").
  UDK_SHADOW_INTENT            "1" (default) scores the Phase 3 sentence veto with the live intent model
                               (inference only); "0" skips it (Phase 3 then cannot veto; recorded).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass

RECORD_SCHEMA = "udk_shadow.record/1"
OBSERVATION_SCHEMA = "udk_shadow.observation/1"
LIVE_FLAGS = ("UDK_ENABLE_STT", "UDK_STT_MODEL", "UDK_ENABLE_PARAKEET", "UDK_ENABLE_KWS", "UDK_ENABLE_SEMANTIC",
              "UDK_ENABLE_STT_CONFIDENCE_GATE", "UDK_ENABLE_DUAL_ASR", "UDK_ENABLE_SEPARATION", "UDK_ENABLE_SCREAM_DETECTION",
              "UDK_ENABLE_SCREAM_TRIGGER", "UDK_INTENT_GATE", "UDK_INTENT_THRESHOLD", "UDK_ENABLE_LANGUAGE_ID",
              "UDK_ENABLE_INDIC_STT", "UDK_ENABLE_INDIC_KWS", "UDK_DEVICE")


class ShadowConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ShadowConfig:
    enabled: bool = False
    sample_rate: float = 1.0
    queue_max: int = 256
    records_max: int = 1000
    journeys_max: int = 512
    context_segments: int = 32
    log_path: str | None = None
    log_max_bytes: int = 50_000_000
    log_text: bool = False
    no_text_turns: str = "exclude"
    semantic: str = "isolated"
    intent: bool = True

    @classmethod
    def from_env(cls, env=None) -> ShadowConfig:
        env = os.environ if env is None else env
        try:
            cfg = cls(enabled=env.get("UDK_SHADOW_MODE") == "1",
                      sample_rate=float(env.get("UDK_SHADOW_SAMPLE_RATE", "1.0")),
                      queue_max=int(env.get("UDK_SHADOW_QUEUE_MAX", "256")),
                      records_max=int(env.get("UDK_SHADOW_RECORDS_MAX", "1000")),
                      journeys_max=int(env.get("UDK_SHADOW_JOURNEYS_MAX", "512")),
                      context_segments=int(env.get("UDK_SHADOW_CONTEXT_SEGMENTS", "32")),
                      log_path=env.get("UDK_SHADOW_LOG_PATH") or None,
                      log_max_bytes=int(env.get("UDK_SHADOW_LOG_MAX_BYTES", "50000000")),
                      log_text=env.get("UDK_SHADOW_LOG_TEXT") == "1",
                      no_text_turns=env.get("UDK_SHADOW_NO_TEXT_TURNS", "exclude"),
                      semantic=env.get("UDK_SHADOW_SEMANTIC", "isolated"),
                      intent=env.get("UDK_SHADOW_INTENT", "1") == "1")
        except ValueError as e:
            raise ShadowConfigError(f"bad UDK_SHADOW_* value: {e}") from e
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ShadowConfigError("UDK_SHADOW_SAMPLE_RATE must be in [0, 1]")
        for k in ("queue_max", "records_max", "journeys_max", "context_segments", "log_max_bytes"):
            if getattr(self, k) < 1:
                raise ShadowConfigError(f"{k} must be >= 1 (shadow state is always bounded)")
        if self.no_text_turns not in ("exclude", "include_empty"):
            raise ShadowConfigError("UDK_SHADOW_NO_TEXT_TURNS must be exclude or include_empty")
        if self.semantic not in ("isolated", "off"):
            raise ShadowConfigError("UDK_SHADOW_SEMANTIC must be isolated or off")

    def as_dict(self) -> dict:
        return asdict(self)

    def sampled(self, segment_id: str) -> bool:
        if self.sample_rate >= 1.0:
            return True
        h = int(hashlib.sha256(segment_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return h < self.sample_rate


def runtime_snapshot(env=None, components: dict | None = None) -> dict:
    """What the LIVE process actually runs with: the raw values of the production flags (unset -> None,
    never a default guessed from deploy files) plus which components really loaded."""
    env = os.environ if env is None else env
    flags = {k: env.get(k) for k in LIVE_FLAGS}
    snap = {"flags": flags, "components": dict(components or {})}
    snap["sha256"] = hashlib.sha256(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()
    return snap


def effective_settings(env, live_mod, intent_gate, policy, context_cfg, shadow_cfg) -> dict:
    """The EFFECTIVE values this process runs with, next to the raw environment values (which can differ: e.g.
    UDK_INTENT_GATE set but the model folder absent -> intent_gate.from_env returns None -> no live veto).
    Nothing here has a default of its own; unset stays None."""
    env = os.environ if env is None else env
    g = lambda name: getattr(live_mod, name, None)
    detector = g("_scream_detector") is not None
    sv = context_cfg.sec("sentence_veto")
    return {
        "UDK_SHADOW_MODE": {"env": env.get("UDK_SHADOW_MODE"), "effective_enabled": shadow_cfg.enabled},
        "UDK_ENABLE_SCREAM_TRIGGER": {"env": env.get("UDK_ENABLE_SCREAM_TRIGGER"), "live_flag": g("_scream_trigger_enabled"),
                                      "detector_loaded": detector, "effective": bool(g("_scream_trigger_enabled")) and detector},
        "UDK_ENABLE_SCREAM_DETECTION": {"env": env.get("UDK_ENABLE_SCREAM_DETECTION"), "live_flag": g("_scream_corroboration_enabled"),
                                        "detector_loaded": detector, "effective": bool(g("_scream_corroboration_enabled")) and detector},
        "sentence_veto": {
            "live": {"UDK_INTENT_GATE": env.get("UDK_INTENT_GATE"), "UDK_INTENT_THRESHOLD": env.get("UDK_INTENT_THRESHOLD"),
                     "intent_gate_loaded": intent_gate is not None,
                     "effective_threshold": getattr(intent_gate, "threshold", None),
                     "second_stt_loaded": g("_parakeet_stt") is not None,
                     "effective": intent_gate is not None and g("_parakeet_stt") is not None},
            "shadow_phase3": {"enabled": sv["enabled"], "threshold": sv["threshold"], "require_heard_by_both": sv["require_heard_by_both"],
                              "scored": intent_gate is not None and shadow_cfg.intent},
            "phase5_sentence_veto_guard": policy.sec("veto_guard")["sentence_veto_requires_clean_overlap"]},
        "UDK_DEVICE": {"env": env.get("UDK_DEVICE"),
                       # api._DEVICE is resolved lazily by api._device() the first time a GPU-capable backend loads; read,
                       # never resolved here (resolving could import torch). None = no GPU-capable backend has loaded.
                       "live_resolved": g("_DEVICE")},
        "s4_status": policy.raw.get("s4_status"),
        "acoustic_policy": {"acoustic_alone": policy.sec("acoustic_alone"), "corroboration": policy.sec("corroboration")},
    }
