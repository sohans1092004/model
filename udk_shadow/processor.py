"""Shadow processing of one SegmentObservation (runs in the shadow worker, never in the live thread).

Stages (each isolated: an exception is recorded in `errors` with its stage and processing continues with
what is safe to continue with; nothing is ever raised to the caller):
  replay   contract §3: a PROBE UDKEngine restored from the live pre_state, the live now_s and the same inputs;
           the live decide_all + api._either_stt_decisions with scream_score=None. The live engine and its
           semantic-matcher cache are never touched (IsolatedSemantic).
  phase3   per replayed event: production_adapter.evidence_from_event -> udk_context.decision.decide with the
           production-equivalent context config and the live intent model (inference only), and the rolling
           context window.
  phase4   evidence.build(obs): BEATs values reused from live, everything else UNAVAILABLE.
  phase5   per event without the 4-class evidence, then once per segment for acoustic-alone (contract §5).
Failure fallbacks: replay failed -> no Phase 3/5 (status "failed"); phase3 failed for an event -> that event is
skipped in Phase 5; phase4 failed -> Phase 5 runs with NO signals (missing is never negative); phase5 failed
-> recorded, no Phase 5 decision.
"""
from __future__ import annotations

import functools
import time
import traceback
from pathlib import Path

from udk_shadow import evidence as ev_mod
from udk_shadow.config import RECORD_SCHEMA

ROOT = Path(__file__).resolve().parent.parent
RANK = {"NO_ACTION": 0, "NO_ALERT": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2}
TIERS = ("NO_ALERT", "TRIGGER_VERIFY", "TRIGGER_ALL")
# What the replay is -- and is not (contract §3; the STT-flip case, Phase 6B):
REPLAY_SEMANTICS = ("counterfactual_linguistic_replay: the live decision functions re-run from the live engine state with "
                    "scream_score=None. NOT a reconstruction of the live path with BEATs disabled: the live 9-class score can "
                    "change which STT list the live path kept (see stt_choice_differs_from_live), and BEATs disabled in "
                    "production would also change the scream-alone rule and the live engine's later window state.")


def _tier(decisions) -> str:
    return TIERS[max((RANK[d] for d in decisions), default=0)]


class IsolatedSemantic:
    """Same model, same threshold attributes, but encodes through the UNCACHED function so the live
    lru_cache is never read or written; a small shadow-owned cache avoids re-encoding the 20 phrases."""

    def __init__(self, live):
        self._live = live
        self.threshold = live.threshold
        self.fuzzy_threshold = live.fuzzy_threshold
        raw = getattr(getattr(live, "_encode", None), "__wrapped__", None)
        if raw is None:
            raise TypeError("semantic matcher exposes no uncached encoder; cannot replay without touching live state")
        self._encode = functools.lru_cache(maxsize=256)(raw)

    def similarity(self, a: str, b: str) -> float:
        from sentence_transformers import util
        return util.cos_sim(self._encode(a), self._encode(b)).item()


class ShadowProcessor:
    def __init__(self, cfg, context, either_fn, intent_gate=None, runtime: dict | None = None,
                 context_cfg=None, fusion_policy=None, stages: dict | None = None):
        from udk_context.decision import ContextConfig
        from udk_fusion.policy import FusionPolicy
        self.cfg, self.context, self.either_fn = cfg, context, either_fn
        self.runtime = runtime or {}
        self.context_cfg = context_cfg or ContextConfig.load(ROOT / "udk_context" / "configs" / "production_equivalent.json")
        self.policy = fusion_policy or FusionPolicy.load(ROOT / "udk_fusion" / "configs" / "production_equivalent.json")
        self.sentence_scorer = None
        if intent_gate is not None and cfg.intent:
            from udk_context.intent import SentenceIntentScorer
            self.sentence_scorer = SentenceIntentScorer(intent_gate)
        self.stages = {"replay": self._replay, "phase3": self._phase3, "phase4": ev_mod.build, "phase5": self._phase5}
        self.stages.update(stages or {})
        self._semantic_views: dict[int, object] = {}
        self.effective: dict = {}  # set by the runner (config.effective_settings): effective runtime values

    # ------------------------------------------------------------------ stages
    def _semantic(self, live_matcher):
        if live_matcher is None or self.cfg.semantic == "off":
            return None, "no_semantic" if live_matcher is not None else "exact"
        key = id(live_matcher)
        if key not in self._semantic_views:
            if len(self._semantic_views) > 8:
                self._semantic_views.clear()
            self._semantic_views[key] = IsolatedSemantic(live_matcher)
        return self._semantic_views[key], "exact"

    def _replay(self, obs) -> dict:
        from udk_engine import UDKEngine
        sem, fidelity = self._semantic(obs.semantic_matcher)
        probe = UDKEngine(obs.udks, semantic_matcher=sem)
        probe.restore(obs.pre_state)  # restore() copies; obs.pre_state is itself a copy
        pre = probe.snapshot()
        text, second = obs.stt["primary_text"], obs.stt["second_text"]
        primary = probe.decide_all(text, now_s=obs.now_s, kws_match=obs.kws_match, scream_score=None,
                                   stt_suspect=obs.stt["stt_suspect"], dual_asr_disagreement=obs.stt["dual_asr_disagreement"])
        events = self.either_fn(probe, primary, pre, second, obs.now_s, obs.kws_match, None)
        chosen = "primary" if events is primary else "second"
        # live veto runs only with the intent gate AND a second transcript; other_text as api.py:521
        other = None if not second else (second if chosen == "primary" else text)
        return {"events": events, "chosen_stt": chosen, "other_text": other, "fidelity": fidelity,
                "kept_text": text if chosen == "primary" else second, "post_state": probe.snapshot()}

    def _phase3(self, obs, rep, window):
        from udk_context.decision import decide
        from udk_context.production_adapter import evidence_from_event
        out = []
        for i, e in enumerate(rep["events"]):
            u = evidence_from_event(e, rep["other_text"])
            out.append((i, u, decide(u, window, self.context_cfg, self.sentence_scorer, None)))
        return out

    def _phase5(self, obs, p3, signals):
        from udk_context.decision import FinalDecision, UdkEvidence
        from udk_fusion.engine import decide
        from udk_fusion.inputs import FusionInput, from_phase3
        per_event_signals = tuple(s for s in signals if s.source != ev_mod.T4)
        t4 = tuple(s for s in signals if s.source == ev_mod.T4)
        span = (obs.start_ms / 1000.0, obs.end_ms / 1000.0)
        fused = [decide(FusionInput(from_phase3(u, fin), per_event_signals, *span, utterance_id=f"{obs.segment_id}#{i}"), self.policy)
                 for i, u, fin in p3]
        seg_level = None
        if not any(f.decision != "NO_ALERT" for f in fused):
            none_u = UdkEvidence("NO_ACTION", None, None, None, "none", 0.0, None, obs.stt["primary_text"])
            none_fin = FinalDecision("NO_ACTION", "udk_path", "NO_ACTION", ["segment-level acoustic-alone check (contract §5)"], {}, {})
            seg_level = decide(FusionInput(from_phase3(none_u, none_fin), per_event_signals + t4, *span,
                                           utterance_id=f"{obs.segment_id}#segment"), self.policy)
        return fused, seg_level

    # ------------------------------------------------------------------ driver
    def process(self, obs, sampled: bool = True) -> dict:
        t0 = time.monotonic()
        rec = {"schema": RECORD_SCHEMA, "segment_id": obs.segment_id, "journey_id": obs.journey_id,
               "start_ms": obs.start_ms, "end_ms": obs.end_ms, "audio_ts": obs.audio_ts, "now_s": obs.now_s,
               "observed_at": obs.observed_at, "language": obs.language, "skipped_live": obs.skipped_live,
               "sampled": sampled, "shadow_config": self.cfg.as_dict(), "runtime": self.runtime,
               "context_config_sha256": self.context_cfg.sha256, "fusion_policy_sha256": self.policy.sha256,
               "s4_status": self.policy.raw.get("s4_status"), "effective": self.effective, "stt": dict(obs.stt), "scream_score": obs.acoustic["scream_score"],
               "acoustic_observed": dict(obs.acoustic), "live": self._live_summary(obs), "errors": [], "status": "ok"}

        def run(stage, *args):
            try:
                return True, self.stages[stage](*args)
            except Exception as e:  # isolation: every stage failure is recorded, never raised
                rec["errors"].append({"stage": stage, "type": type(e).__name__, "message": str(e)[:500],
                                      "trace": traceback.format_exc(limit=3)[-1500:]})
                return False, None

        # context text for this segment (needed even when not sampled / skipped)
        if obs.skipped_live:
            text = "" if self.cfg.no_text_turns == "include_empty" else None
            win, cinfo = self.context.window_for(obs, "")
            self.context.append(obs, text)
            rec.update(status="skipped_live_no_text", context={**cinfo, "treatment": self.cfg.no_text_turns},
                       shadow_phase3_decision=None, shadow_phase5_decision=None)
            rec["elapsed_s"] = round(time.monotonic() - t0, 6)
            return rec

        rep = None
        if sampled:
            ok, rep = run("replay", obs)
        kept_text = rep["kept_text"] if rep else (obs.stt["second_text"] if obs.live.get("pre_veto_is_primary") is False
                                                   else obs.stt["primary_text"])
        try:
            win, cinfo = self.context.window_for(obs, kept_text)
        except Exception as e:
            rec["errors"].append({"stage": "context", "type": type(e).__name__, "message": str(e)[:500]})
            win, cinfo = None, {}
        rec["context"] = {**cinfo, "text_source": "replay" if rep else "live_choice", "treatment": self.cfg.no_text_turns}
        try:
            self.context.append(obs, kept_text)
        except Exception as e:
            rec["errors"].append({"stage": "context", "type": type(e).__name__, "message": str(e)[:500]})

        if not sampled:
            rec.update(status="not_sampled", shadow_phase3_decision=None, shadow_phase5_decision=None)
            rec["elapsed_s"] = round(time.monotonic() - t0, 6)
            return rec
        if rep is None:
            rec.update(status="failed", shadow_phase3_decision=None, shadow_phase5_decision=None)
            rec["elapsed_s"] = round(time.monotonic() - t0, 6)
            return rec

        from udk_shadow.observation import decision_dict
        live_choice = rec["live"]["live_chosen_stt"]
        rec["replay"] = {"semantics": REPLAY_SEMANTICS,
                         "stt_choice_differs_from_live": None if live_choice is None else rep["chosen_stt"] != live_choice,
                         "chosen_stt": rep["chosen_stt"], "other_text": rep["other_text"], "fidelity": rep["fidelity"],
                         "events": [decision_dict(e) for e in rep["events"]],
                         "window_state_matches_live": rep["post_state"] == obs.post_state}
        ok3, p3 = run("phase3", obs, rep, win) if win is not None else (False, None)
        if ok3:
            rec["phase3"] = [{"position": i, "udk_evidence": {"decision": u.decision, "udk_id": u.udk_id, "udk_type": u.udk_type,
                                                               "layer": u.layer, "confidence": u.confidence, "heard_by_both": u.heard_by_both},
                              "decision": f.decision, "source": f.source, "reasons": list(f.reasons), "scores": f.scores,
                              "negation": f.negation} for i, u, f in p3]
            rec["shadow_phase3_decision"] = _tier(f.decision for _, _, f in p3)
        else:
            rec["shadow_phase3_decision"] = None
        ok4, signals = run("phase4", obs)
        if not ok4:
            signals = []
        from udk_signals.evidence import Evidence
        valid = [x for x in (signals or []) if isinstance(x, Evidence)]
        if len(valid) != len(signals or []):  # malformed evidence is dropped (never read as negative) and recorded
            rec["errors"].append({"stage": "phase4_validation", "type": "MalformedEvidence",
                                  "message": f"{len(signals) - len(valid)} item(s) are not udk_signals Evidence; dropped"})
        rec["phase4_evidence"] = [{"kind": s.kind, "state": s.state, "source": s.source, "score": s.score, "reason": s.reason,
                                   "detail": {k: v for k, v in s.detail.items() if k != "known_false_alarm_sources"}}
                                  if hasattr(s, "kind") else {"malformed": repr(s)[:200]} for s in (signals or [])]
        if ok3:
            ok5, res = run("phase5", obs, p3, valid)
            if ok5:
                fused, seg = res
                rec["phase5_events"] = [f.record() for f in fused]
                rec["phase5_segment_acoustic_alone"] = seg.record() if seg else None
                rec["shadow_phase5_decision"] = _tier([f.decision for f in fused] + ([seg.decision] if seg else []))
            else:
                rec["shadow_phase5_decision"] = None
        else:
            rec["shadow_phase5_decision"] = None
        rec["status"] = "ok" if not rec["errors"] else "partial"
        rec["elapsed_s"] = round(time.monotonic() - t0, 6)
        return rec

    @staticmethod
    def _live_summary(obs) -> dict:
        live = obs.live
        emitted = live.get("emitted_events", [])
        return {"live_decision": _tier(e["decision"] for e in emitted),
                "live_linguistic_decision": _tier(e["decision"] for e in emitted if e.get("layer") != "acoustic_scream"),
                "live_scream_alone": any(e.get("layer") == "acoustic_scream" for e in emitted),
                "live_chosen_stt": None if live.get("pre_veto_is_primary") is None else ("primary" if live["pre_veto_is_primary"] else "second"),
                "veto_other_text": (None if not obs.stt["second_text"] or not live.get("intent_gate_loaded") else
                                    obs.stt["second_text"] if live.get("pre_veto_is_primary") else obs.stt["primary_text"]),
                "intent_vetoed": [d for d in live.get("decisions", []) if str(d.get("reason", "")).startswith("intent veto")],
                "separation_recovered": live.get("separation_recovered", False),
                "pre_veto": live.get("pre_veto", []), "decisions": live.get("decisions", []), "emitted_events": emitted}
