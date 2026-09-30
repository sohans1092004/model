# Phase 6B: shadow mode (`udk_shadow/`)

This implements `udk_fusion/PHASE6_INTEGRATION_CONTRACT.md`. The live path stays authoritative. Shadow mode is **OFF unless `UDK_SHADOW_MODE=1`**.

## Architecture

```
api._run_incremental_detection (live thread)                       udk-shadow worker (daemon thread)
  ... live decision, veto, separation, scream-alone, emit ...
  observe(journey, seg, locals())  --copy, put_nowait-->  queue  -->  ShadowProcessor.process(obs)
     (after the segment's alerts were emitted;                             replay  (probe engine from live pre_state,
      also before the live no-text `continue`)                                     live now_s, scream_score=None,
                                                                                   live decide_all + _either_stt_decisions)
                                                                           context (rolling per-journey buffer)
                                                                           phase3  (udk_context.decide, live intent model)
                                                                           phase4  (BEATs values reused; rest UNAVAILABLE)
                                                                           phase5  (udk_fusion, per event + once per segment)
                                                                        -> bounded record deque (+ optional JSONL sink)
```

## Changes to `api.py` (38 added lines, no existing line changed; hook only)

1. `_load_shadow()` and `_shadow`. Nothing is imported unless `UDK_SHADOW_MODE=1`, and any start-up error gives `None`.
2. `observe(..., skipped=True)` just before the live no-text `continue`.
3. `_shadow_pre_veto = decisions`. This keeps a reference only, so the observer can see the list before the veto and which STT was kept.
4. `observe(..., skipped=False, ...)` **after** the segment's live events are emitted.

Both calls are wrapped in `try/except Exception: pass`. `observe()` itself also catches everything.

## Live-path isolation

- **Order:** the observer runs after `_emit_event` for the segment, so a live alert is never delayed by shadow.
- **Capture is copy-only:** strings, floats, `engine.snapshot()` (a new copy), a list copy of the UDKs, and dict copies of the events.
  - No audio is read or stored.
  - Names that exist only under some flags are read with `.get()`.
  - Stale previous-iteration locals are never read on a skipped segment.
- **Never blocks:** `put_nowait`. When the queue is full, the new observation is dropped and counted, and the journey's context gets a gap mark.
- **Replay** runs on a probe `UDKEngine` restored from the snapshot; the live engine is never passed to shadow code.
  - Semantic matching goes through `IsolatedSemantic`: the live model via its **uncached** encoder, so the live `lru_cache` is untouched.
  - Replay refuses a matcher without an uncached encoder, and that failure is recorded.
- **Intent model:** shadow calls `p_distress` (inference only; no state).
- **Stage failures** are recorded in `errors[]` with the stage name. The worker never dies.

**Residual shared resource:** the shadow worker runs the same torch models (semantic matcher, intent model) as the live thread, concurrently. That adds CPU/GPU contention, not state changes. Measure it before enabling in production. `UDK_SHADOW_SEMANTIC=off`, `UDK_SHADOW_INTENT=0` and `UDK_SHADOW_SAMPLE_RATE` reduce it.

## Configuration (all `UDK_SHADOW_*`; see `config.py`)

`MODE` (off), `SAMPLE_RATE` (1.0), `QUEUE_MAX` (256), `RECORDS_MAX` (1000), `JOURNEYS_MAX` (512), `CONTEXT_SEGMENTS` (32), `LOG_PATH` (none), `LOG_MAX_BYTES` (50 MB, one rotation to `.1`), `LOG_TEXT` (0 = transcripts written as sha256/length), `NO_TEXT_TURNS` (`exclude` | `include_empty`), `SEMANTIC` (`isolated` | `off`), `INTENT` (1).

Every record carries `shadow_config` and `runtime`. `runtime` holds the **actual** values of the production flags (unset stays `None`) and which components loaded.

## Record schema `udk_shadow.record/1`

**Always present:**
- **Identity:** `segment_id` (= live `audio_segment_id`), `journey_id`, `start_ms`, `end_ms`, `audio_ts`, `now_s`, `observed_at`, `language`
- **Flags:** `skipped_live`, `sampled`
- **Config:** `shadow_config`, `runtime`, `context_config_sha256`, `fusion_policy_sha256`, `s4_status`
- **Inputs:** `stt` (primary/second text, avg_logprob, temperature, stt_suspect, dual_asr_disagreement, kws_match), `scream_score` (float or **null**), `acoustic_observed`
- **Live:** `live`, which contains:
  - `live_decision` and `live_linguistic_decision`
  - `live_scream_alone`
  - `live_chosen_stt` and `veto_other_text`
  - `intent_vetoed` and `separation_recovered`
  - `pre_veto`, `decisions` and `emitted_events`
- **Context:** `context`, which contains:
  - `cold_start`, `cold_reason` and `possible_restart`
  - `gaps_so_far` and `buffered_segments`
  - `context_turns[]` (segment_id, span, text, speaker_id=null, relation)
  - `attribution_complete`, `treatment` and `text_source`
- **Status:** `status` (`ok` | `partial` | `failed` | `not_sampled` | `skipped_live_no_text`), `errors[]` (stage, type, message), `runner` (drop/eviction counters), `elapsed_s`

**Only when processed:**
- `replay` (chosen_stt, other_text, fidelity, events[], window_state_matches_live)
- `phase3[]` (udk_evidence, decision, source, reasons, scores, negation) and `shadow_phase3_decision`
- `phase4_evidence[]` (kind, state, source, score, reason, detail with segment_id / clock / span)
- `phase5_events[]` (the full `FusedDecision.record()`: rules_fired, contributing, considered, ignored, basis, annotations) and `phase5_segment_acoustic_alone`
- `shadow_phase5_decision`

## Comparison report

`report.compare(records, runner.stats)` gives:
- status and drop counts, and failures by stage;
- live vs Phase 3, and live vs Phase 5 (match, shadow_higher, shadow_lower);
- segments where the set of alerting UDKs differs;
- the cause of each difference: `scream_correlated`, `stt_selection_changed_by_scream`, `context_veto`, `phase5_rules:R*`, `separation_recovered`, `replay_divergence_no_scream`, `unexplained`;
- no-data counts.

The report is operational only. There is no labelled set, so it is **not** a performance measurement.

## Not decided here (recorded, unchanged)

- S-4 stays open: the policy is the production-equivalent mirror.
- The sentence-veto guard stays OFF.
- No speaker model and no overlap model.
- BEATs thresholds unchanged.
- How no-text segments are treated is configurable (`exclude` is the default because live has no notion of them) and is recorded on every record.

## Phase 6C: deployability and interference

- **Image:** `deploy/Dockerfile.dockerignore` whitelists the shadow runtime file by file: 26 files in total, 24 `.py` modules plus the two `production_equivalent.json` configs. `deploy/check_package.py` walks the shadow import closure and fails if a module it imports is missing or if a shipped shadow file is never imported. The one exception is the documented lazy `udk_context.scene -> asr_bench.splits` import, which shadow never calls. It then starts `api.py` from the whitelisted files with shadow OFF, shadow ON, `udk_shadow` missing, and a shadow dependency missing.
- **Fail closed:** `runner.load()` runs `selfcheck.run()`, one synthetic observation through every stage, at start-up. Any failure leaves shadow OFF, and the service starts normally either way.
- **Effective configuration:** each record carries `effective`: the raw environment value and the effective state for `UDK_SHADOW_MODE` and both scream flags, `UDK_DEVICE` (raw and as resolved by the live process), the sentence veto (live gate loaded / threshold / second STT, shadow Phase 3, and the Phase 5 guard), S-4 status and the acoustic policy. In the container the environment is SSM `/sakhi/udk/config` merged with `deploy/.env.example`, and the repo file wins for keys it sets (`deploy/remote_deploy.sh`). `UDK_SHADOW_MODE` is not in `.env.example`, so it could only come from SSM, and it is unset by default.
- **Replay label:** `replay.semantics` and `replay.stt_choice_differs_from_live` mark the replay as a counterfactual linguistic replay. It is **not** the live path with BEATs disabled.
- **Interference benchmark:** `bench/` (not shipped). Results on a Kaggle T4 are in `bench/results/kaggle_t4/`; the full suite (branch vs 96ea038) and the smoke test are in `bench/results/kaggle_t4_checks/`.
