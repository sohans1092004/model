"""Phase 4: acoustic, speaker-attribution and overlap signal layer.

Isolated: api.py and udk_context do not import it and nothing here is wired into the live alert
path. Every signal is an Evidence with an explicit state (positive / negative / uncertain /
unavailable) so a downstream fusion can never mistake "no information" for "safe". Acoustic
evidence alone can never produce TRIGGER_ALL (fusion.py). Open items: udk_signals/OPEN_ITEMS.md.
"""
