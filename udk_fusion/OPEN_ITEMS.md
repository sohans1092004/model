# Phase 5 (fusion / decision engine): open items

Everything here is logic only. `test_fusion.py` results come from toy fixtures, and every report from `evaluation.evaluate(..., "fixture")` is stamped `performance_claims_allowed: false` with a TOY banner.

## Blockers (inherited, not re-decided)

- **Evidence models:**
  - S-1: no approved speaker embedder.
  - S-2: no approved overlap detector.
  - C-1: no approved context-aware intent model.
  - C-3: no runtime diarization.

  Their evidence stays UNAVAILABLE. R3 therefore reinstates every context veto at runtime, which leaves the context veto effectively off.
- **Data (S-3, C-9):** there is no real labelled scene, speaker, overlap or acoustic data, so no policy can be evaluated.
- **S-4:** open. The policy boundary exists (`s4_status: open`, options A–D); the choice is the owner's.
- **Integration:** not wired into `api.py`. Wiring should start in shadow mode, logging `record()`.

## Contract ambiguities to resolve before production integration

| ID | Ambiguity | Current Phase 5 handling |
|---|---|---|
| F-1 | **Two sources of attribution/overlap truth.** Phase 3 reads `ContextWindow.attribution_complete` / `concurrent` (from scene annotation or diarization); Phase 4 emits `speaker_attribution` / `overlap` Evidence. | A context veto stands only if Phase 4 evidence positively agrees (R3, conservative). Pick one source at integration. |
| F-2 | **Phase 4 Evidence is not linked to Phase 3 turns.** Nothing ties a `speaker_attribution` item to a context turn, or checks its label against Phase 3's same/other-speaker relation. | R3 requires *every* attribution item to be POSITIVE. It cannot check that labels agree. Evidence needs turn or segment IDs. |
| F-3 | **Double counting of live corroboration.** `udk_engine.decide` applies the 9-class scream corroboration *inside* the UDK decision when `scream_score` is passed, so a production `UdkEvidence.decision` may already be TRIGGER_ALL because of acoustics. | `acoustic_scream` alerts are rejected as linguistic input. Pre-lifted decisions **cannot be detected** from `UdkEvidence`. At integration, build UdkEvidence with `scream_score=None` and pass BEATs as Phase 4 Evidence. |
| F-4 | **Several UDK events per segment** (live `decide_all` sentence extras) versus one Phase 3/5 decision per UdkEvidence. Live scream-alone fires only if *no* event in the segment alerts. | Phase 5 decides per utterance. The integration must apply R6 once per segment, after all per-UDK decisions. |
| F-5 | **Dual-STT selection** (`_either_stt_decisions` keeps the stronger engine's list) happens before Phase 3. | Phase 5 receives the chosen event only. |
| F-6 | **Ordering.** Live corroboration runs before the intent veto, and the scream-alone check after it. | Phase 5 consumes the post-veto decision. Outcomes match live (conformance-tested against Phase 4 `fuse()`), but live counts a vetoed alert in the repetition window, which Phase 5 cannot see. |
| F-7 | **Sentence-veto guard** (`veto_guard.sentence_veto_requires_clean_overlap`). | OFF in production-equivalent (live veto unchanged); ON in the fixture policy. Owner decision. |
| F-8 | **Evidence spans.** Phase 4 spans are optional; BEATs 2 s windows versus the utterance span. | Evidence is ignored only when both spans are known and don't intersect. |
| F-9 | **Phase 4 `fuse()` and Phase 5 `decide()` overlap.** | Phase 5 matches `fuse()` on every grid case outside its own veto guards. Only one should be wired; `fuse()` is kept as the reference. |
| F-10 | **Media/TV voice saying a UDK** (Phase 3 C-2). | Unchanged: the alert is kept (product rule). |
