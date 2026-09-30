# Phase 3 (context-aware safety understanding): open items and blockers

No Phase 3 specification document exists. This layer is built only from requirements already established in the Phase 0, Phase 1 and Phase 2A documents:
- Phase 0: veto rules, the recall-first ranking, the "any voice saying a UDK must alert" product rule, and the v2 context-model failure.
- Phase 1 §15: the scene/annotation schema, problem types A/B/C, preceding context only.
- Phase 1 §18: the context and speaker-attribution metrics.
- Phase 2A: the transcript representation and split discipline.

## Blocking

| ID | Item |
|---|---|
| C-1 | **No approved context-aware intent model.** The live mDeBERTa v1 is sentence-only; v2 (context) was rejected (Phase 0 §11). `intent.py` defines the interface; the only context scorer here is the TEST-ONLY lexicon fixture. |
| C-3 | **No runtime speaker attribution / diarization** (Phase 0 F10). At runtime every turn is "unattributed", so context veto can never fire (H4) and roles are unknown. Target-speaker identification and attribution accuracy are UNAVAILABLE. |
| C-9 | **No real scene data.** Real SAFE/DANGER pairs, attacker/victim scenes, overlap scenes and danger-without-UDK sets come from the Phase 1 collection (not started; consent under legal review). The manifest schema extension for scenes (N-10) is still open; `scene.py` follows the Phase 1 §15 annotation fields directly. |
| C-10 | No Phase 3 specification document, so production thresholds, alert-tier policy for context and integration requirements are not defined. |

## Open (recorded, not decided)

| ID | Item | Current behaviour |
|---|---|---|
| C-2 | Media / TV voice saying a UDK: Phase 0's product rule ("any voice saying a UDK must alert") vs Phase 1's SAFE label for "movie/game dialogue playing nearby". | Alert kept (product rule). Evaluation counts it as a SAFE false alarm. |
| C-4 | Production wiring. `api.py` is NOT changed. The integration point is `api._either_stt_decisions` / `api._intent_veto` → `udk_context.decision.decide()` via `production_adapter.py`. | Not wired (waits for C-1, C-3, C-6). |
| C-5 | Context window size. | 20 s / 6 turns in both configs: recorded, provisional (Phase 0's rejected v2 used 20 s). |
| C-6 | Thresholds for context veto, sentence ceiling, escalation and danger-without-UDK. | Unset in `production_equivalent.json` (features off). `fixture_context.json` values are illustrative for tests only. |
| C-7 | Known false-alarm classes by design: a harmless report containing strong danger words (sentence ceiling); arguments between two speakers (H3: another speaker's context never lowers danger); custom-phrase mentions (H1). | Kept: recall first. |
| C-8 | Negator lists (Q7): Latin-script only. | Negation is evidence only (H5). |
| C-11 | Context escalation (VERIFY → ALL) changes alert tiers. | Off in production-equivalent. |
