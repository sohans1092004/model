"""Phase 2A ASR benchmark infrastructure (UDK Phase 2A: Data Readiness + ASR Benchmark).

Isolated from the live service: nothing in api.py or the frozen 96ea038 pipeline imports
this package. Stage S1 = the canonical manifest schema (schema.py) and its validator
(validate.py). Open questions are listed in PENDING_DECISIONS.md, not decided in code.
"""
