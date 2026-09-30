"""Phase 5: multimodal fusion / decision engine.

Consumes the Phase 3 linguistic decision (udk_context.decision.decide -> UdkEvidence + FinalDecision) and
Phase 4 signal evidence (udk_signals.evidence.Evidence) and returns one deterministic alert decision with
full provenance. Isolated: api.py does not import it and nothing here is wired into the live alert path.
Policy is explicit configuration (configs/*.json); precedence and invariants: udk_fusion/README.md;
open items and contract ambiguities: udk_fusion/OPEN_ITEMS.md.
"""
