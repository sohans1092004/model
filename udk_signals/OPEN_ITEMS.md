# Phase 4 signal layer: open items and blockers

This layer lives on the `phase2a-asr-benchmark` feature branch only. It is **not wired into the live alert path**: `api.py` and other production modules do not import `udk_signals`. All numbers produced by `test_signals.py` come from toy fixtures and say nothing about real-world performance.

| ID | Item | Status | Blocks |
|---|---|---|---|
| S-1 | No approved speaker embedder. ECAPA and WavLM were experiments, not approved components. `TargetSpeakerVerifier` and `SpeakerAttributor` accept any `SpeakerEmbedder`; without one they return UNAVAILABLE. | open, blocker | real target-speaker ID and attribution |
| S-2 | No approved overlap detector or separation model. pyannote, WeSep and SepFormer were rejected or experimental. Only `from_annotation()` (evaluation) and the test fixture exist. | open, blocker | real overlap evidence |
| S-3 | No real labelled speaker, overlap or acoustic data. This depends on the Phase 1 collection and on registry sources with `acquisition_authorised=false`. | open, blocker | every real metric and threshold |
| S-4 | (Options A–D laid out in `DECISION_S4_BEATS_ROLE.md`.) Should the live scream-alone TRIGGER_VERIFY and the BEATs 9-class corroboration stay, given their known false alarms and the 28/57 misses? The production-equivalent config mirrors the live behaviour and records it without endorsing it. | open, owner decision | changing the production-equivalent config |
| S-5 | Condition thresholds (quiet, low SNR, clipping, muffled) and speaker thresholds (accept, reject, same_speaker) are provisional. They are fixture values in `fixture_signals.json` and null or provisional in `production_equivalent.json`, and must be set on a real dev split, never the final test. | open | calibration |
| S-6 | VAD gap: acoustic analysis runs only inside VAD segments, so a cry or scream that VAD does not flag is never analysed (UNAVAILABLE, not NEGATIVE). | open, limitation | acoustic recall |
| S-7 | Integration: `fuse()` is not called by the runtime. Wiring it in needs a separate approved change, with shadow-mode logging first. | open, deferred by instruction | live use |
| S-8 | The fixture overlap detector does not report crowd babble as an overlap; it returns UNCERTAIN or NEGATIVE depending on the mix. Real babble handling needs S-2. | open, limitation | none (fixture only) |
| S-9 | The fixtures, including `FixtureEmbedder`, `FixtureOverlapDetector` and `FixtureAcousticSource`, only exercise the logic (states, fusion rules, metric plumbing). They must never be used to choose or tune a real model. | standing rule | n/a |

Invariants enforced by tests, which must not be relaxed without an explicit decision:

- Acoustic evidence alone never produces TRIGGER_ALL. The config loader rejects `allow_acoustic_trigger_all`.
- Absence of BEATs output, or of speaker or overlap output, is UNCERTAIN or UNAVAILABLE, never NEGATIVE (safety).
- Overlapped segments are never given a single speaker label.
- A linguistic TRIGGER_ALL from Phase 3 passes through unchanged when acoustic or speaker evidence is missing.
