# VAD classification cache: end-to-end impact on the live pipeline, OFF vs ON

**Status: complete. Every OFF-vs-ON difference is explained (§H and §O).**
- Done: the harness, the full-corpus dry run (stubbed STT), the full real-model run on a Kaggle T4, and a targeted GPU
  investigation of the two differences on positive recordings (`gpu_t4_investigation/`).
- Scope: a VAD-cache impact test only, not a validation of the safety system.

**Unchanged:**
- `cache_classifications` is still OFF by default;
- `api.py` is unmodified and does not reference the flag;
- no thresholds, UDK, intent, BEATs or decision logic changed;
- nothing was deployed or committed.

> **Follow-up (GPU discrepancy investigation):** see `GPU_DISCREPANCY_INVESTIGATION.md`. Result:
> `RESOLVED_SAFE_FOR_NEXT_CONTROLLED_TEST`.
> - pos_01: `vad_boundary_sensitivity`, same tier at every boundary position.
> - neg_10: a real fuzzy-matcher false alarm ("taken away from me" → UDK_03) in both modes; ON removes OFF's
>   repeat-escalated TRIGGER_ALL (`state/timing_difference`).
> - pos_02: `vad_boundary_sensitivity` through the STT confidence gate. The outcome alternates with 30 ms start shifts
>   (TRIGGER_ALL at 3/9 positions, VERIFY at 6/9, ON's position among the majority); an alert at every position.
> - No production go/no-go.

## A. Objective

Does fixing the streaming-segmentation defect (the VAD classification cache) correct the existing pipeline without
introducing different downstream behaviour? Method: the same audio and the same process, cache OFF against cache ON.

## B. Pipeline configuration

- **The pipeline:**
  - the real `api` module;
  - configured from the detection section of `deploy/.env.example`, read at start-up and never edited;
  - driven in-process through the real service path: `api.start_journey`, then `api._ingest_frame` per chunk (the
    WebSocket handler's call, including its per-frame heartbeat and journey save), then `api.stop_journey`.
- **The only per-mode difference:** `journey.vad = VAD(cache_classifications=False|True)`, set before any audio arrives.
- **Held identical:** audio, chunks, models, configuration, device, process and order.
- **Ordering:** OFF and ON run interleaved, twice each.
- **Clock.** `api.py` stamps decisions with `time.monotonic()`, and the 15 s repeat window uses it. The harness gives
  `api` a virtual clock equal to the audio seconds delivered, i.e. real-time streaming without processing delay: it is
  deterministic and identical in both modes. Wall time is used only for latency measurement.
- **Capture:**
  - the existing read-only Phase 6 hook records each processed segment;
  - backends are wrapped in pass-through timing proxies;
  - persisted runs hold transcript **digests** only. Text is kept only for same-window STT differences (6 segments in
    the GPU run).
- **Comparison:**
  - events are paired by utterance, using the largest overlap;
  - a segment's alert is credited to the one-shot utterance it overlaps most;
  - "re-processing" means overlap beyond the designed 8 s-cut overlap;
  - `e2e_report.py --recompute` re-derives every table from the saved runs.
- **Code:**
  - `udk_shadow/bench/e2e_vad_cache.py`, `e2e_report.py`, `e2e_investigate.py`;
  - `udk_shadow/bench/kaggle/make_e2e_bundle.py`, `run_e2e_kaggle.py`;
  - `udk_shadow/test_e2e_vad_cache.py` (42 checks).

## C. Recordings

- The 48 local recordings of the segmentation experiment:
  - `mixed`: 30 × 30 s, each with a manifest phrase;
  - `positives` and `negatives`: 18 recordings of 5–326 s.
- **Calibration and development material, not held out.** The negatives trained and thresholded the BEATs head.
- Chunk sizes on the GPU: mixed 20, 100 and 1000 ms; media 100 and 1000 ms.
- Chunk sizes in the dry run: mixed also 250 and 500 ms.

## D. Components executed (GPU run: Tesla T4, torch 2.10.0+cu128, Python 3.12)

| Component | Loaded, as reported by class name |
|---|---|
| Whisper | `FasterWhisperSTT`, `faster-whisper-small.en`, **cuda** |
| Parakeet | `ParakeetSTT`, providers CUDA and CPU |
| Semantic matcher | `SentenceTransformerSemanticMatcher` |
| STT confidence gate | on |
| BEATs | `BEATsDistressDetector`, with the scream trigger and corroboration on |
| Intent gate | `IntentGate`: production-pinned `sohans1092004/udk-intent-mdeberta@6131acc`, threshold 0.02, cuda |
| KWS, dual-ASR, separation, language ID | off, as in production |

## E. Components unavailable

- **GPU run:** none.
- **Dry run:** all models were unavailable. Stub STT (the manifest phrase when a segment contains speech); BEATs, intent
  and semantic off.
- **Library versions differ from the production image:** Kaggle's torch 2.10 against the image's 2.5.1. The model
  weights are the same.

## F and G. Results, real models (126 rows × OFF, ON and two repeats each; `gpu_t4_real_models/`)

| Set | Chunk | Segments OFF / ON | ON == one-shot | Events OFF / ON | TRIGGER_ALL OFF / ON | Repeat-induced ALL OFF / ON | Overlapping same-UDK alerts OFF / ON | Alerts stable on repeat |
|---|---|---|---|---|---|---|---|---|
| mixed | 20 ms | 159 / 50 | 30/30 | 27 / 23 | 17 / 13 | 4 / 0 | 5 / 0 | 30/30 both |
| mixed | 100 ms | 133 / 50 | 30/30 | 27 / 23 | 17 / 13 | 4 / 0 | 5 / 0 | 30/30 |
| mixed | 1000 ms | 82 / 50 | 30/30 | 26 / 23 | 16 / 13 | 3 / 0 | 3 / 0 | 30/30 |
| media | 100 ms | 121 / 103 | 18/18 | 5 / 4 | 2 / 0 | 1 / 0 | 1 / 1 (designed) | 18/18 |
| media | 1000 ms | 110 / 103 | 18/18 | 5 / 4 | 2 / 0 | 1 / 0 | 1 / 1 (designed) | 18/18 |

Across all rows: no errors, and every journey ended COMPLETE.

**Dry run** (stub STT, 186 rows; `dryrun_stub_stt/`):
- ON == one-shot everywhere;
- OFF gave 2–10 repeat-induced TRIGGER_ALLs per chunk size, ON gave 0;
- 843 differences, all expected VAD corrections.

## H. OFF-vs-ON differences (real models)

Classes: 624 expected VAD correction, 6 STT nondeterminism, 0 others.

**Segments.**
- OFF-only segments: 186 re-processing, 188 drifted boundary, 60 spurious.
- ON-only segments: 185, each exactly a one-shot segment.
- Same boundaries, different decision: 5 segments, explained by OFF's re-processed alerts in the engine history.

**Utterances alerted by only one mode: 0**, at every chunk size in both runs.

**Alert differences, individually:**

| Recording | OFF | ON | Status |
|---|---|---|---|
| mix_clip_06, 07, 17, 19, 21 | Extra TRIGGER_ALL "repeated within window" on re-processed or drifted copies of an utterance | The utterance's first alert only | Expected VAD correction. The duplicate escalation is removed. |
| neg_10 (negative) | TRIGGER_VERIFY UDK_03, then TRIGGER_ALL UDK_03 on the **same utterance** re-processed 30 ms later | One TRIGGER_VERIFY UDK_03 (intent p = 0.84, no veto) | Expected VAD correction. A false-alarm escalation to TRIGGER_ALL on a negative recording is removed; the VERIFY-level false alarm exists in both modes. |
| **pos_01** (positive, Urdu/Hindi) | TRIGGER_VERIFY **UDK_20** semantic on 17.46–28.44 s | TRIGGER_VERIFY **UDK_10** semantic on 17.49–28.47 s | **Explained: STT sensitivity to the boundary.** English Parakeet mis-transcribes the non-English utterance differently on the two windows: OFF "To my hard hook and I hard. I can get out of it." (→ UDK_20), ON "To my yard, who can I hard? I can let out with it." (→ UDK_10 through MiniLM, seen on both ON repeats). Both are deterministic. Same utterance, same tier; the UDK identity is an artefact of mis-transcription. |
| **pos_02** (positive, Malayalam) | **TRIGGER_ALL UDK_01** exact + UDK_08, corroborated by BEATs, on 26.94–37.92 s | **TRIGGER_VERIFY** acoustic scream on 27.06–38.04 s | **Explained: Whisper decoding confidence depends on the cut, and the STT confidence gate vetoes suspect transcripts.** See "pos_02 in detail" below. |

**pos_02 in detail** (`gpu_t4_investigation/`: 5 Whisper and 2 Parakeet runs per window, 30 ms sweep):
- **Both windows contain the same speech.** OFF's window decodes deterministically at temperature 0 (5/5 identical,
  not suspect): "Help! Help! Help! Help! I can't believe it! … Please! Please!". ON's window, 120 ms later, is also heard
  as "Help! Help! … Please" in every run, but Whisper needs temperature fallback (T 0.2–1.0) in 5/5 runs, so the
  **STT confidence gate** flags every ON transcript as suspect.
- **The engine behaves identically given the same flag.** Replaying the actual transcripts through the real engine:
  - ON's transcripts, *not* flagged suspect, produce exactly OFF's alerts (UDK_01 exact TRIGGER_ALL, with BEATs);
  - OFF's transcript, flagged suspect, is vetoed exactly like ON's.
- **Conclusion:** the tier change is not produced by the cache logic. The VAD correction moved the cut to the one-shot
  position, and there Whisper decodes this speech with low confidence. The production guardrail then vetoes the text
  match, and the acoustic path still raises TRIGGER_VERIFY. OFF's higher tier came from a drifted window that happened
  to decode confidently.
- **This fragility existed before the fix:** a text alert depends on how confidently Whisper decodes a particular cut.
  It can go either way at any boundary. On this corpus it went against ON once.
- **Limitation:** the sweep used whole-text matching, not the engine's per-sentence decision, and did not record the
  confidence flag, so it does not quantify how often a 30 ms shift flips the gate.

**Late decisions.**
- In 5 noisy mixed clips, OFF decided the opening segment (0–1.6 s) **3–23 s late**. The mechanism, traced: the
  persistent webrtcvad re-reads the opening speech as non-speech until later speech shifts its state.
- With real STT, **that segment alerted in neither mode**. It holds only a fragment of the phrase, and the stub
  over-stated it. **The late-decision defect is real, but no real alert was delayed on this material.**

## I. Duplicate-alert consequences

- OFF raised 3–5 overlapping same-UDK alerts per mixed chunk size; ON raised 0.
- In media, both modes have 1, and ON's is the designed 8 s-cut overlap (existing intentional behaviour).
- **Missing alerts with ON: none by utterance.** pos_02 is a tier and type change, counted in J.

## J. TRIGGER_ALL differences

- OFF has 3–4 repeat-induced TRIGGER_ALLs per mixed chunk size and 1 per media chunk size (neg_10). ON has 0.
- **ON produced no TRIGGER_ALL that OFF lacked.**
- **pos_02:** OFF's TRIGGER_ALL (exact UDK_01 + BEATs) becomes ON's acoustic TRIGGER_VERIFY. This is the one
  TRIGGER_ALL that ON loses *not* because of duplication. Explained in §H: Whisper confidence at the corrected boundary plus the STT confidence gate; not the cache logic.

## K. STT differences

- **Whisper small.en on the GPU is not deterministic between runs.** The same window gives different transcripts on
  repeat; its temperature fallback samples without a fixed seed. This is production behaviour.
- Same-window Whisper differences OFF vs ON: 6 segments (pos_04, neg_03, neg_05 at both chunk sizes). All fall within
  the repeat-noise baseline, and none changed an alert.
- Parakeet was repeat-stable on the windows examined.
- Different windows (drifted or shifted) give different STT input. That is the mechanism behind pos_01 and pos_02.

## L. Intent differences

- The intent gate ran (production model). Scores were identical wherever both modes scored the same text (e.g. neg_10:
  0.84224 in both).
- Vetoes: 2 per run in every OFF and ON run, so no difference in veto count.
- ON made 69 intent calls against OFF's 81: nothing is re-processed.

## M. Acoustic differences

- BEATs evidence is identical on identical windows.
- It differs only where the windows differ, e.g. pos_02 peak 0.2375 vs 0.2916 on the shifted windows. Both fired, so
  no trigger decision changed.

## N. Performance (Tesla T4, sequential, OFF and ON repeat 0; no threshold)

| Set / chunk | Wall s OFF / ON | CPU s OFF / ON | Model time s OFF / ON (Whisper) | Median p50 / p95 per call, ms OFF → ON | Worst call ms OFF / ON |
|---|---|---|---|---|---|
| mixed 20 ms | 621 / 506 | 497 / 329 | 59 / 25 (27 / 11) | 12.7 / 19.3 → 10.9 / 15.8 | 971 / 942 |
| mixed 100 ms | 113 / 69 | 158 / 74 | 48 / 22 (21 / 9) | 6.7 / 11.7 → 4.5 / 8.1 | 760 / 866 |
| mixed 1000 ms | 38 / 25 | 82 / 53 | 31 / 21 (12 / 8) | 5.6 / 14.7 → 3.5 / 6.2 | 779 / 830 |
| media 100 ms | 394 / 286 | 459 / 339 | 179 / 157 (114 / 101) | 8.7 / 14.1 → 5.8 / 10.2 | 4786 / 4750 |
| media 1000 ms | 178 / 165 | 275 / 255 | 158 / 154 (99 / 99) | 6.9 / 961 → 3.9 / 929 | 4067 / 5294 |

- **The 326 s recording at 100 ms chunks:** wall time 189 s OFF against 118 s ON; p95 per call 84 ms against 45 ms.
- **Resources:** GPU peak allocation about 3.7 GB and process RSS about 4.2 GB, the same in both modes.
- **Where ON's saving comes from:** fewer segments to transcribe (no re-processing) and no whole-buffer
  re-classification.
- **Worst calls** are the calls that ran the models on a segment. They are similar in both modes.

## O. Failure classification (real models)

| Class | Count |
|---|---|
| Expected VAD correction | 624 |
| Existing intentional behaviour | 1 designed-overlap duplicate |
| STT nondeterminism | 6 |
| Model nondeterminism | 0 |
| Timing/order artefact | 0 |
| Genuine regression | 0 established |
| Environment/tooling | 0 in the data |
| Unable to determine | **0**. pos_01 is explained as STT boundary sensitivity (same tier); pos_02 as Whisper confidence at the boundary plus the STT confidence gate |

Harness and metric defects found and fixed during this work; none touched production:
1. The first dry run lacked the per-frame heartbeat, so slow journeys timed out and lost their final flush. That run is
   discarded, and non-COMPLETE journeys are now flagged.
2. Events were matched on the exact segment key; they are now paired by utterance, with tier changes reported
   separately.
3. Alerts were credited to every utterance a segment touched; now each goes to its best-overlap utterance, with ties
   broken by centre. This removed a false "alert only OFF" (mix_clip_30) and a false "alert only ON" (mix_clip_02).
4. Designed-overlap segments were labelled as re-processing.
5. **Security:** the Kaggle runner wrote the HF token into `run.log`. The saved copy is redacted, and the runner now
   passes the token through the environment only. **The exposed token must be revoked.**

## P. Limitations

- **Material:** calibration clips, not journeys, and not held out. No real-world rates follow.
- **Whisper is nondeterministic on GPU.** Text-level comparison is only meaningful against the repeat baseline.
- **Clock:** the virtual clock omits processing delay.
- **Untested:** the client chunk size is unknown, and restart/replay was not exercised.
- **Library versions** differ from the production image (Kaggle torch 2.10).
- **Boundary sensitivity is not quantified.** How often a small boundary shift flips Whisper's confidence, and so the
  confidence gate, was not measured (§H, pos_02). It is a pre-existing risk that any segmentation change moves, in
  either direction.
- **Local environment:** `test_intent_gate.py` cannot import here (`librosa` missing). It passed on the Kaggle T4 in
  the Phase 8 run.

## Q. Is ON safe to proceed to controlled integration testing?

**Yes, to controlled integration testing only.** This is not production enablement, and the flag stays OFF by default.
- **What ON removes:**
  - re-processed audio;
  - duplicate alerts;
  - repeat-escalated TRIGGER_ALLs, including a false TRIGGER_ALL on a negative recording;
  - late decisions on opening speech.
- **What ON costs:** it misses no utterance that OFF alerted on, and it is faster.
- **No difference is attributable to a defect in the cache logic.**
- **One caveat for integration testing:** on one positive recording (pos_02), ON's corrected cut decoded with low
  Whisper confidence, the STT confidence gate vetoed the text match, and the tier fell from TRIGGER_ALL to
  TRIGGER_VERIFY (the acoustic alert remains). Integration testing should measure how often boundary position flips the
  confidence gate, since that risk exists with or without the cache.
