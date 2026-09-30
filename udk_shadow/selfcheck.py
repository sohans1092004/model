"""Start-up self-check: push one synthetic observation through every shadow stage (replay, context, Phase 3,
Phase 4, Phase 5) on a throwaway runner, using the live module's own _either_stt_decisions and the real
UDKEngine. No model is called (no intent gate, no semantic matcher), no live state is read or written, and
no audio exists. runner.load() turns shadow OFF if this does not come back "ok" -- so an image with a missing
or broken shadow module fails closed at start-up instead of recording failures for every segment.
deploy/check_package.py runs it inside the whitelisted package too.
"""
from __future__ import annotations

import time


def run(live_mod, either_fn) -> dict:
    from udk_engine import UDKEngine
    from udks import GENERAL_UDKS

    from udk_shadow.config import OBSERVATION_SCHEMA, ShadowConfig
    from udk_shadow.observation import SegmentObservation
    from udk_shadow.runner import ShadowRunner

    runner = ShadowRunner(ShadowConfig(enabled=True, intent=False, semantic="off"), live_mod, either_fn, None, {"selfcheck": True},
                          synchronous=True, process_started_at=0.0)
    eng = UDKEngine(list(GENERAL_UDKS))
    obs = SegmentObservation(OBSERVATION_SCHEMA, "selfcheck", "selfcheck:0-2000", 0, 2000, 1.0, 1.0, time.time(), None, False,
                             {"primary_text": "help me please", "primary_avg_logprob": None, "primary_temperature": None,
                              "second_text": "help me please", "second_stt_loaded": True, "stt_suspect": False,
                              "dual_asr_disagreement": False, "kws_match": None},
                             {"trigger_enabled": True, "corroboration_enabled": True, "detector_loaded": True, "trigger_ran": True,
                              "scream_fired": False, "scream_peak": 0.01, "scream_class": "Screaming", "scream_score": 0.5},
                             now_s=100.0, pre_state=eng.snapshot(), post_state=eng.snapshot(), udks=list(GENERAL_UDKS))
    obs.live = {"pre_veto": [], "pre_veto_is_primary": True, "decisions": [], "separation_recovered": False,
                "intent_gate_loaded": False, "emitted_events": []}
    rec = runner.processor.process(obs)
    ok = (rec.get("status") == "ok" and rec.get("shadow_phase3_decision") is not None
          and rec.get("shadow_phase5_decision") is not None and not rec.get("errors"))
    return {"ok": ok, "status": rec.get("status"), "errors": rec.get("errors"),
            "phase3": rec.get("shadow_phase3_decision"), "phase5": rec.get("shadow_phase5_decision")}
