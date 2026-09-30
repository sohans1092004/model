"""Bridge to the production objects, without modifying them.

  evidence_from_event(event, other_text)  udk_engine.DecisionEvent (+ the other STT's text) -> UdkEvidence;
                                          heard_by_both via intent_gate.heard_by_both (same rule as live).
  production_matcher(personal_phrase)     a fresh production UDKEngine per utterance -> UdkEvidence, for
                                          evaluating scenes through the REAL matcher.
  sentence_scorer_from_env()              the live IntentGate (UDK_INTENT_GATE) as a SentenceIntentScorer.

Integration point (not wired, C-4): api._either_stt_decisions / api._intent_veto would call
decision.decide() with the segment's window. Wiring waits for a context-aware model and diarization.
Needs rapidfuzz + numpy (the production stack) at call time.
"""
from __future__ import annotations

from udk_context.decision import UdkEvidence
from udk_context.intent import SentenceIntentScorer


def evidence_from_event(event, other_text: str | None) -> UdkEvidence:
    from intent_gate import heard_by_both
    udk = event.udk
    return UdkEvidence(decision=event.decision, udk_id=udk.udk_id if udk else None, udk_type=udk.udk_type if udk else None,
                       udk_phrase=udk.phrase if udk else None, layer=event.layer, confidence=float(event.confidence),
                       heard_by_both=None if other_text is None else heard_by_both(event.transcript, other_text),
                       transcript=event.transcript)


def production_matcher(personal_phrase: str | None = None, user_id: str = "U0"):
    """text, other_text -> UdkEvidence through udk_engine.UDKEngine.decide_all (stronger of whole
    segment / per-sentence). A personal phrase is added exactly as api.start_journey does."""
    from udk_engine import UDKEngine
    from udks import GENERAL_UDKS, UDK

    udks = list(GENERAL_UDKS) + ([UDK(f"PUDK_{user_id}", personal_phrase, "PERSONAL")] if personal_phrase else [])

    def evidence(text: str, other_text: str | None = None) -> UdkEvidence:
        decisions = UDKEngine(udks).decide_all(text, now_s=0.0)
        best = max(decisions, key=lambda d: ({"NO_ACTION": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2}[d.decision], d.confidence))
        return evidence_from_event(best, other_text)
    return evidence


def sentence_scorer_from_env(device: str = "cpu") -> SentenceIntentScorer | None:
    import intent_gate
    gate = intent_gate.from_env(device)
    return SentenceIntentScorer(gate) if gate is not None else None
