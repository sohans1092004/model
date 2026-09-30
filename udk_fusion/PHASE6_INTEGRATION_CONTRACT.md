# Phase 6 integration contract: Phase 5 in shadow mode

**Status.** This is analysis only. No production, Phase 3, Phase 4 or Phase 5 code was changed.

**Evidence.** Every statement below is traced to live 96ea038 code, cited as `file:line`. Where marked **[checked]**, it was also confirmed by running the live `udk_engine` together with the live `api._either_stt_decisions` / `api._strongest` source. That source was extracted from `api.py` with `ast`, not re-typed. The check script was a scratch file, not committed: 10/10 checks passed.

**Deployed flags.** The flag set assumed below is `deploy/.env.example`:

| On | Off |
|---|---|
| STT (Whisper small.en), Parakeet, semantic matching, STT-confidence gate, scream corroboration (`SCREAM_DETECTION`), scream trigger, intent gate (0.02) | KWS; separation and dual-ASR (both unset, so off) |

Phase 0 marks "the live AWS image uses these flags" as NOT VERIFIED; see §10.

## 1. Current live call graph

Everything below is per finalized VAD segment inside `api._run_incremental_detection` (`api.py:433`).

| # | Step | Where | Notes |
|---|---|---|---|
| 0 | Segment finalized; `processed_up_to_ms = seg.end_ms` | `api.py:436-457` | VAD re-scans the whole buffer, and segments are finalized once audio exists after their end. Segment identity is `(start_ms, end_ms)` on the journey-audio clock. |
| 1 | Whisper transcript; Parakeet `second_text`; KWS (off) | `api.py:459, 467, 468` | |
| 2 | **Scream-alone check (4-class)** | `api.py:474` → `scream_trigger.check` | Runs on every finalized segment, before the empty-transcript skip. |
| 3 | Empty skip | `api.py:479` | Skipped if there is no text on either STT, no KWS match and no scream. The engine is not touched. |
| 4 | **9-class `scream_score`** | `api.py:481` | Computed only if not skipped and the corroboration flag is on; otherwise `None`. |
| 5 | STT-confidence gate / dual-ASR peek | `api.py:485, 498-503` | |
| 6 | `now_s = time.monotonic()`; `pre_state = engine.snapshot()` | `api.py:505-506` | This is the server processing clock, not the audio clock. |
| 7 | **Individual UDK matches**: `engine.decide_all(text, scream_score=…)` → `decide()` per whole segment and per sentence | `api.py:511`; `udk_engine.py:436-474, 504-` | Order inside `decide()`: match → text floor (`:542`) → **records the alert in the repetition window** (`:553-554`) → **applies the 9-class corroboration** (`:555-580`). |
| 8 | **Combine the two STTs**: `_either_stt_decisions` restores `pre_state`, runs `decide_all(second_text, …, scream_score)`, and keeps the stronger list (tier, then confidence) | `api.py:519, 851-872` | Engine state is left as if only the kept list had been decided. |
| 9 | **Intent veto** | `api.py:521, 832-844`; `intent_gate.py:49-56` | Only when the intent gate is on and `second_text` is non-empty. Only GENERAL, text-layer alerts, and only if `heard_by_both`. A vetoed whole-segment decision becomes NO_ACTION; a vetoed extra is dropped. The engine has already recorded it (§6). |
| 10 | Separation fallback | `api.py:529-536`; `separation.py:78-105` | Only if the decision is NO_ACTION with no extras. Calls `engine.decide` **without** `scream_score`, with a new `time.monotonic()`. Not vetoed. Off in `.env.example`. |
| 11 | **Final segment alerts**: `alerts = [decision if not NO_ACTION] + extras` | `api.py:540` | |
| 12 | **Scream-alone emission**: if `alerts` is empty and the scream fired → one TRIGGER_VERIFY with `udk=None`, `layer="acoustic_scream"` | `api.py:541-546` | |
| 13 | One event per alert: `event_id = sha256(journey:start_ms:udk_id)`, `audio_segment_id = journey:start-end`, `timestamp = started_at + start_ms/1000` | `api.py:547-548, 329-361, 552-575` | Emission, DB save and delivery. |

## 2. Required Phase 6 insertion boundary

There is **one read-only observation hook per finalized segment**, placed after step 11 (`api.py:540`) and before or after step 13. It receives values the live loop has already computed. It must be:
- **exception-isolated**: a failure logs and never changes live behaviour;
- **non-mutating**: it must never touch `journey.engine`, `journey.events` or delivery;
- **off the alert latency path** (queued).

The hook captures the `SegmentObservation` in §8. Everything the shadow computes runs on **copies**:
- A **probe engine** is built as `UDKEngine(journey.engine.udks, semantic_matcher=journey.engine.semantic_matcher)` and then given `.restore(pre_state)`. This is the same throwaway-engine pattern `separation._best_candidate` already uses (`separation.py:117`).
- Phase 3 `decide()` then runs per UDK event, and Phase 5 `decide()` runs per event plus once per segment (§5).

Adding this hook is itself a production code change. It needs its own approval in Phase 6.

## 3. F-3 resolution: getting the UDK decision before corroboration

**Finding.** The live `DecisionEvent` cannot yield the decision as it stood before corroboration.
- The corroboration is applied inside `decide()` (`udk_engine.py:555-580`).
- When repetition or distinct-UDK escalation also holds, `reason` names only that escalation. **[checked]**
- `DecisionEvent` has no corroboration field.
- The "downgrade" can't be reversed afterwards either. The corroboration also affects **which STT list is kept** (step 8). **[checked]** For example, with primary "I don't feel safe here" (verify-by-default) and second text "I need help right now":
  - with `scream_score = 0.9`, Whisper's UDK_14 list is kept;
  - with `None`, Parakeet's UDK_05 list is kept.

  The intent-veto `other_text` (`api.py:521`) follows that choice.

**Resolution: replay steps 7–9 with `scream_score=None`.**
1. Take the probe engine restored from the live `pre_state`, with the live `now_s`, and the same `transcript.text`, `second_text`, `kws_match`, `stt_suspect` and `dual_asr_disagreement`.
2. Run `decide_all(..., scream_score=None)` and the live `_either_stt_decisions(probe, …, scream_score=None)`. Call the live functions; don't re-implement them.
3. Record `replay_chosen_stt` and the `other_text` the veto would use.
4. For each event in the kept list:
   - convert it with the existing `udk_context.production_adapter.evidence_from_event(event, other_text)`;
   - run Phase 3 `decide()` with the production-equivalent context config and `SentenceIntentScorer(live IntentGate)`. This reproduces the live veto (0.02, GENERAL text layers, heard-by-both).
5. Pass the live `scream_score` separately to Phase 5 as `Evidence("acoustic_distress", …, "beats_9class_corroboration")`. The existing Phase 4 `BeatsScreamSignal` does this.

**Why this is faithful.** **[checked]**
- The repetition and distinct-UDK windows are recorded *before* the corroboration check, so the engine state after the replay equals the state after the live decision.
- `scream_score` changes only tiers and reasons, never which UDKs fire.

So the replay differs from live only where the corroboration acted, including its effect on which STT list was kept. The live final events are logged separately **for comparison only** and are never fed back into Phase 5.

**Cost.** Matching runs twice (fuzzy plus semantic embedding). There is no extra STT or BEATs call. The intent gate may run once more per text event. Live `_intent_veto` returns `p_distress` only when it vetoes, so the non-veto score is not observable without calling the gate.

## 4. F-1 / F-2: associating context turns with speaker and overlap evidence

**What exists at runtime:**
- Segments: `(start_ms, end_ms)` on the journey-audio clock, plus `audio_segment_id`.
- No speaker IDs anywhere. Diarization is absent (C-3), and there is no approved embedder (S-1).
- Phase 3 `Turn`: `turn_index`, `speaker_id`, `role`, `text`, `start_s`, `end_s`.
- Phase 4 `Evidence`: optional `start_s`/`end_s`. Attribution labels are journey-local cluster labels in `detail["label"]`. `OverlapDetector.detect(x, sr)` returns **no span** (`overlap.py`).

**Association rule (deterministic, no inference).**
- One finalized VAD segment is one Phase 3 turn: `turn_index` is the segment's ordinal in the journey, and `start_s`/`end_s` = `start_ms/1000` and `end_ms/1000`.
- Phase 4 evidence belongs to a turn only by an **exact `segment_id` match**. Spans are a consistency check, not the key.
- `Turn.speaker_id` is:
  - `"{journey_id}:{namespace}:{label}"` only when that segment's `speaker_attribution` Evidence is POSITIVE;
  - otherwise `None`, which gives Phase 3 `attribution_complete=False`, so H4 blocks the context veto.
- `role` is always `None` at runtime.

**F-1 (two sources of truth) resolves mechanically.**
- Live VAD segments are sequential, so Phase 3 `ContextWindow.concurrent` is structurally empty at runtime. Overlap can only come from Phase 4 overlap Evidence.
- Phase 3 `attribution_complete` is derived from speaker IDs that come only from Phase 4 attribution Evidence.

The single source of truth is therefore **Phase 4 evidence**. The Phase 3 window is a view of it, and Phase 5 R3 re-checks the same evidence.

**F-2: the association is not possible with today's fields.** Phase 6 must add:

| Field | On | Why |
|---|---|---|
| `segment_id` (= live `audio_segment_id`) | every Phase 4 Evidence (`detail` or a wrapper) and every Phase 3 Turn | exact join key |
| `clock: "journey_audio_ms"` and `start_ms` / `end_ms` | the same | spans on one clock (not `now_s`) |
| `attribution_namespace` (clustering run/version) | attribution Evidence | labels are only comparable within one online-clustering run |
| span on overlap Evidence | the caller of `detect()` | the protocol returns none |
| rolling per-journey segment log: `segment_id`, span, text, `stt_used`, evidence refs | shadow state | Phase 3 needs the text of preceding turns; live keeps only alert events (`journey.events`) |

A VAD segment can hold several speakers: pauses under 1.5 s stay together, up to 8 s. That segment is then not attributable as one turn. Its Evidence must be UNCERTAIN (Phase 4 already emits UNCERTAIN on overlap), never split by guesswork.

## 5. F-4: segment/event aggregation

| Scope | Live behaviour |
|---|---|
| UDK events | Per segment: `decide_all` gives the whole-segment decision plus sentence extras (each a different UDK), for each STT. The stronger list is kept. Veto is per event. So there are **0..N alert events per segment**, and each becomes one live event (`event_id` keyed by `udk_id`). |
| Corroboration (9-class) | Per `decide()` call: the same `scream_score` is applied to every event of the segment (sentence extras included; `udk_engine.py:452`). Not applied to a separation-recovered decision. |
| Scream-alone (4-class) | **Once per segment**, only if *no* alert event remains after veto and separation (`api.py:541`). At most one scream event per segment. |
| Phase 5 input | **One `FusionInput` per event in the kept list**, including a NO_ACTION whole-segment decision and vetoed events. |

**Required aggregation boundary.** Phase 5 `decide()` applies its acoustic-alone rule (R6) per input. Calling it per event with the 4-class evidence would emit a scream VERIFY beside a vetoed event even when another event in the same segment alerts, which live never does. Phase 6 must therefore aggregate per segment without changing Phase 5:
1. **Per event:** run Phase 3 then Phase 5 with the 9-class evidence and the speaker/overlap/condition evidence, but **without** `beats_4class_scream_trigger` evidence.
2. **Per segment:**
   - if no event is fused into an alert, call Phase 5 `decide()` once with linguistic origin `none` plus the 4-class evidence. This is R6, at most once.
   - otherwise attach the 4-class evidence to the segment record as "considered, no effect".
3. **Segment output:** the list of fused events plus the optional acoustic-alone event, compared with the live events for the same `segment_id`.

## 6. F-6: repetition-window state

**Mechanism.** `decide()` calls `_record_and_check_repeat` and `_record_and_check_distinct` (`udk_engine.py:553-554`) for every decision that clears the text floor. That happens before it returns, and the veto runs later in `api._intent_veto` without touching the engine. **[checked]**
- A vetoed alert remains in `_recent` / `_recent_distinct`.
- The next same-UDK alert within `REPEAT_WINDOW_S = 15.0` s is `repeated` and becomes TRIGGER_ALL. Any different UDK within 15 s triggers distinct escalation.

This is accepted in the code ("the engine already counted a vetoed alert toward repetition escalation", `api.py:836`).

Details of the window:
- It uses `now_s = time.monotonic()` at processing time (`api.py:505`), not audio time. **[checked]**: an event 15.5 s later is not repeated.
- NO_ACTION below the floor is never recorded. **[checked]**
- Sentence extras are each recorded within the same segment. **[checked]**
- Separation records its single winner with its own `time.monotonic()`.
- A language switch builds a new engine (`api.py:373`), which resets the window.
- The window is not persisted across restarts.

**What shadow mode needs to reproduce it:**
- Do not keep an independent shadow window. Use the live `pre_state` snapshot and the live `now_s` per segment (§3). The escalation is then already inside each replayed `udk_decision`, exactly as live computed it, vetoed history included.
- Log `pre_state` and the live post-segment `snapshot()`, so any drift is detectable.
- Log whether separation ran, with its `now_s`.
- Phase 5 neither reads nor writes the window. A Phase 5 R3 reinstatement or a standing Phase 3 context veto does not alter it, which is consistent with live.

## 7. F-7: evaluation required before the sentence-veto guard

**Current production-equivalent behaviour.** `veto_guard.sentence_veto_requires_clean_overlap = false`. The live veto stands exactly as at `api.py:521` (Phase 3 `production_equivalent.json`: 0.02, both STTs agree, GENERAL text layers only).

**What enabling it changes.**
- A sentence veto would stand only when overlap Evidence is a clean NEGATIVE; otherwise the alert is reinstated.
- With no approved overlap detector (S-2), overlap is always UNAVAILABLE. **Every** sentence veto would be reinstated, so the live veto would in effect be switched off.
- The false alarms it removes on real audio would return. Phase 0 records 16.0/h conversation before the veto against 3.6/h at 96ea038, from a superseded transcript replay spanning other changes too.

**Evidence required before enabling it:**
1. An approved overlap detector, with precision and recall measured on real overlapped speech.
2. Real, speaker-attributed Phase 1 scenes containing overlap in which the live veto silenced a genuine UDK (lost danger).
3. Real harmless overlapped speech with UDK-like wording, to measure the false alarms/hour that would return.
4. Both measured on a dev split, never the final test, reported by condition.

## 8. Shadow-mode schema

**`SegmentObservation`** (captured by the hook, read-only)

```
journey_id, segment_id, start_ms, end_ms, audio_ts (= started_at + start_ms/1000), now_s (monotonic),
processing_version, flags {stt, parakeet, kws, semantic, stt_conf_gate, dual_asr, separation, scream_detection,
                           scream_trigger, intent_gate, intent_threshold}, language, model_version {...}
stt:        primary_text, primary_avg_logprob, primary_temperature, stt_suspect, second_text (""=none),
            kws_match (null), dual_asr_disagreement
engine:     pre_state (snapshot), post_state (snapshot), udks_version
acoustic:   scream_score (float | null: null when not computed), scream_fired, scream_peak, scream_class,
            in_vad_segment: true
live:       chosen_stt, veto_other_text, vetoed [{position, udk_id, p_distress}], separation_ran,
            separation_now_s, emitted_events [{event_id, decision, udk_id, udk_type, layer, confidence, reason}]
            -- COMPARISON ONLY
phase4:     [Evidence + segment_id, clock, attribution_namespace]   (today: speaker/overlap UNAVAILABLE)
```

**`ShadowRecord`** (computed off the path)

```
segment_id, replay {chosen_stt, other_text, events [UdkEvidence]},
phase3 [{position, FinalDecision, config_sha256}],
phase5_events [FusedDecision.record()], phase5_segment_acoustic_alone (FusedDecision.record() | null),
policy_sha256, comparison {live_tiers, shadow_tiers, per_udk: match | shadow_higher | shadow_lower, reasons}
```

## 9. Fields that must never be inferred

- **The pre-corroboration decision.** Never derive it by downgrading a live TRIGGER_ALL or parsing `reason`; take it only from the §3 replay.
- **`speaker_id` / `role` / attribution labels.** Absent Evidence gives `None`, never a guess.
- **Overlap NEGATIVE.** Absence of a detector gives UNAVAILABLE.
- **Acoustic NEGATIVE.** BEATs not firing gives UNCERTAIN; audio outside VAD gives UNAVAILABLE.
- **`scream_score`.** When not computed (flag off, or segment skipped) it is `null`, never `0.0`.
- **`heard_by_both`.**
  - When `second_text` is empty the live veto never runs, so record `None`, not `False` or `True`.
  - The `other_text` must be the one the veto would use for the kept list.
- **`udk_type`.** It is `None` for scream events. A scream event is never linguistic input (Phase 5 rejects `acoustic_scream`).
- **Timestamps.** Audio time comes from `start_ms`, never `server_received_ts` or `now_s`. The window uses `now_s`, never audio time.
- **SAFE/DANGER labels.** Never inferred from live decisions; they come only from annotation.
- **`p_distress` for a non-vetoed event.** Only from an actual gate call, never assumed ≥ 0.02.

## 10. Open questions the current code cannot resolve

1. **Deployed flags.** Whether the live AWS image uses `deploy/.env.example`, including separation and dual-ASR being off. Phase 0: NOT VERIFIED.
2. **Replay determinism of semantic matching.** A second embedding call on GPU may differ near the 0.65 threshold. This can only be measured by running shadow mode; any divergence shows up as a replay-vs-live mismatch with `scream_score` absent.
3. **VAD re-segmentation.** `segment_speech` re-scans the whole buffer, and the code does not prevent a later segment from starting before `processed_up_to_ms`. Whether processed segments ever overlap in practice is unmeasured, and it matters for the `segment_id` join key. **Measured offline (post-6D):** they do. The live VAD's webrtcvad state carries across re-scans, so the same audio is re-processed (every mixed clip at 20–100 ms chunks). This produces duplicate alert events and some repetition escalations to TRIGGER_ALL; no speech was skipped. See `udk_shadow/bench/results/segmentation_integrity/SEGMENTATION_INTEGRITY.md`. Live code not changed. **Fix candidates compared offline (post-6D, experiment only):** A current, B fresh VAD per scan, C trim at the processed frontier, and D classify each frame once and cache it (unchanged segmentation). The comparison covered 48 recordings × 20–1000 ms chunks, 72 scripted boundary cases, and a sequential latency run. Results: D and B both satisfy no re-processing, no skipped speech, boundaries equal to one-shot, alerts equal to one pass, and determinism. C fails boundaries and alerts, and removes the designed 8 s-cut overlap. D keeps the designed cut overlap and costs 3–5× less per call than A and B (p95 15–21 ms vs 57–62 ms on the 326 s recording), though its cost still grows with journey length. D is recommended as the basis for a future fix behind an OFF-by-default flag. **The fix is NOT implemented; the live `api.py` and `vad.py` are unchanged, and nothing is enabled.** See `udk_shadow/bench/results/segmentation_candidates/SEGMENTATION_CANDIDATES.md`. **Prototype (post-experiment):** `vad.VAD(cache_classifications=True)` implements D in `vad.py`. The flag is OFF by default and NOT wired into `api.py`, so live behaviour is unchanged. With the flag OFF the output is identical to the pre-prototype `vad.py` on every call; with it ON the output equals D and the one-shot segmentation. Evidence: 222/222 recording × chunk rows and 28 checks; see `VAD_FLAG_PROTOTYPE.md` in the same folder. Enabling it is a separate, not-yet-approved change.
4. **Attribution label stability.** No embedder exists (S-1), so the namespace and online-clustering label stability within a journey cannot be specified beyond "labels comparable only within one namespace".
5. **Skipped segments in the context window.** Should segments skipped at `api.py:479` (no text, no scream) appear as empty context turns? Live has no notion of this; Phase 3 C-5 leaves it open.
6. **Restart recovery.** The live window is not persisted, so after a restart shadow and live both start empty. Whether shadow should flag post-restart segments is a design choice.
7. **Approval of the hook itself.** Adding the hook changes `api.py` and needs an explicit Phase 6 decision.
