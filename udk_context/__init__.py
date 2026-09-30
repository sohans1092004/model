"""Phase 3: context-aware safety understanding layer.

Isolated from the live service: api.py does not import this package. It wraps the production
objects (udk_engine.DecisionEvent, intent_gate.IntentGate) instead of changing them, and every
behaviour beyond the production-equivalent path is off unless its configuration turns it on.
Open items: udk_context/OPEN_ITEMS.md.
"""
