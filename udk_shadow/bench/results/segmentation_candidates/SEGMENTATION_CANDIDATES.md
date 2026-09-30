# Streaming segmentation: fix candidates A/B/C/D (PHASE6_INTEGRATION_CONTRACT §10 Q3)

**Experiment only. `api.py`, `vad.py` and all production defaults are unchanged.** Nothing here enables any candidate in
production, and nothing here authorizes doing so. Candidate D is recommended as the *basis* for a production fix. That
fix still needs its own isolated prototype behind an OFF-by-default flag, with the before/after evidence below re-run
against it.

- **Code:**
  - `udk_shadow/bench/segmentation_candidates.py`: candidates, scripted boundary cases, full-comparison runner.
  - `udk_shadow/bench/segmentation_latency.py`: the sequential latency and determinism run.
  - `udk_shadow/bench/segmentation_integrity.py`: live-loop harness and metrics, from the preceding measurement.
- **Tests:** `udk_shadow/test_segmentation_candidates.py` and `udk_shadow/test_segmentation_integrity.py`.
- **Raw data:** this folder.

## 1. Problem (measured earlier, `../segmentation_integrity/SEGMENTATION_INTEGRITY.md`)

`api._run_incremental_detection` re-scans the whole journey buffer on every chunk, using `journey.vad`. It finalizes
segments with `end_ms < total`, skips those with `end_ms <= processed_up_to_ms`, and advances `processed_up_to_ms`.

- **The fault:** `journey.vad` wraps ONE `webrtcvad.Vad` for the whole journey, and its adaptive state carries across
  re-scans. The same frame can therefore be classified differently on successive scans.
- **The consequence:** a finalized segment's end moves by a frame. It then has `end_ms > processed_up_to_ms` and is
  handed to STT again, together with the audio it shares with the earlier version.

## 2. Candidates

| | Candidate | Mechanism |
|---|---|---|
| A | `A_current` | Production behaviour: one persistent `webrtcvad.Vad`, the whole buffer re-classified on every scan. |
| B | `B_fresh` | A fresh `VAD()` (fresh `webrtcvad.Vad`) for every scan: the whole buffer re-classified from state zero. |
| C | `C_frontier` | Like A, but any segment reaching back before `processed_up_to_ms` is trimmed to start there. |
| D | `D_cached` | One persistent `webrtcvad.Vad` that classifies each 30 ms frame exactly once, in order. The flag is cached by frame index. Every scan runs the **unchanged** `VAD.segment_speech` over the cached flags. |

D is implemented as a `VAD` subclass. It replaces `self._vad` with a proxy (`_CachedClassifier`) that returns the
cached flag for any frame index already classified, and calls the real classifier only for new frames. It raises if the
buffer ever shrinks. The segmentation algorithm is untouched: pre/post-roll, the 8 s cap, and the designed overlap
after a forced cut.

## 3. Invariants

- **I1 No accidental re-processing.** No audio goes to STT twice, beyond the overlap the one-shot segmentation has
  **by design**: after a forced 8 s cut, the next segment's pre-roll overlaps back so a phrase split at the cut is not
  lost. Metric: `excess_overlap = processed overlap − one-shot self-overlap`, per recording, floored at 0. The designed
  overlap is reported separately and must be preserved.
- **I2 No skipped speech.** Every webrtcvad speech frame of a fresh single pass lies inside some processed segment.
- **I3 Valid boundaries.** The processed segments equal the one-shot segmentation of the complete recording
  (fresh `VAD()`).
- **I4 Alert semantics.** Streaming alerts equal one-pass alerts (real `UDKEngine`, 20 standard UDKs): no extra events,
  no repeat-induced TRIGGER_ALL, no escalation.
- **I5 Determinism.** Identical input gives identical spans, frame classifications and alerts.
- **I6 Latency.** Reported only. No acceptance threshold was invented.

## 4. Full comparison (48 recordings × all chunk sizes × A/B/C/D; `mixed_*.json`, `media_*.json`)

- **Mixed:** 30 × 30 s clips, each with a manifest phrase. Chunk sizes 20, 100, 250, 500 and 1000 ms.
- **Media:** 18 positives/negatives, 5–326 s, `_converted_*` duplicates skipped. Chunk sizes 100, 250, 500 and 1000 ms.
- **Harness:** the real `api._run_incremental_detection`, fed chunk by chunk as `_ingest_frame` does, then the
  `final=True` flush that `stop_journey` performs.
- **STT stub:** returns the clip's manifest phrase for any segment containing speech frames. Alert consequences are
  computed for `mixed/` only; the media recordings have no phrase manifest.
- **Timings in this section:** these runs ran the four candidates in parallel. Latency comes from §6 only.

**Mixed (30 clips; one-shot reference = 50 segments)**

| Chunk | Candidate | Processed | Excess overlap | Clips with excess | Missed speech | Clips ≠ one-shot | Extra alert events | Repeat-induced TRIGGER_ALL | VERIFY→ALL escalations |
|---|---|---|---|---|---|---|---|---|---|
| 20 ms | A | 159 | 202 590 ms | 30 | 0 | 30 | 26 | 10 | 4 |
| | B | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| | C | 159 | 0 | 0 | 0 | 30 | 2 | 1 | 1 |
| | **D** | **50** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| 100 ms | A | 133 | 141 030 ms | 30 | 0 | 30 | 19 | 7 | 2 |
| | B / D | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| | C | 133 | 0 | 0 | 0 | 30 | 1 | 0 | 0 |
| 250 ms | A | 103 | 77 940 ms | 26 | 0 | 30 | 13 | 6 | 2 |
| | B / D | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| | C | 103 | 0 | 0 | 0 | 30 | 1 | 0 | 0 |
| 500 ms | A | 96 | 63 360 ms | 23 | 0 | 30 | 11 | 6 | 2 |
| | B / D | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| | C | 96 | 0 | 0 | 0 | 30 | 1 | 0 | 0 |
| 1000 ms | A | 82 | 35 640 ms | 11 | 0 | 30 | 6 | 2 | 0 |
| | B / D | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| | C | 82 | 0 | 0 | 0 | 30 | 2 | 0 | 0 |

**Media (18 recordings; one-shot reference = 103 segments)**

| Chunk | A: processed / excess / recordings with excess / ≠ one-shot | B | C: processed / ≠ one-shot | D |
|---|---|---|---|---|
| 100 ms | 121 / 187 590 ms / 9 / 14 | 103, all zero | 121 / 15 | 103, all zero |
| 250 ms | 117 / 147 990 ms / 7 / 14 | 103, all zero | 117 / 15 | 103, all zero |
| 500 ms | 113 / 106 800 ms / 7 / 14 | 103, all zero | 113 / 15 | 103, all zero |
| 1000 ms | 110 / 75 330 ms / 7 / 15 | 103, all zero | 110 / 15 | 103, all zero |

**Across all rows:**
- No candidate had errors or missed speech.
- "reprocessed 1" for B and D in the mixed set is clip_02's designed 8 s-cut overlap (2 520 ms). It is identical in the
  one-shot reference and counted as designed, not excess.
- C removes that designed overlap.

## 5. Scripted boundary cases (`test_segmentation_candidates.py`)

- **Coverage:** 9 scenarios × 8 chunk sizes (20, 30, 90, 100, 250, 600, 1000, 1500 ms).
  - Scenarios: silence→speech→silence; speech at t=0; speech ending exactly at the buffer end; a short gap (< post-roll)
    inside one utterance; a long gap between two utterances; one-frame speech; 20 s speech with forced 8 s cuts;
    boundaries not aligned to frames; speech on a 1000 ms chunk boundary.
- **Frame content:** each frame encodes its own speech flag and index, so the flags are exact.
- **Drift:** `DriftClassifier` reproduces A's failure mode (state carried across scans moves a segment end by one frame).
- **Control:** re-scanning with a stateless classifier is harmless. A equals the reference in every case, so the harness
  adds nothing.
- **Failure mode reproduced:** A with drift re-processes audio in ≥ 9 cases.
- **B and D:** I1–I3 hold in all 72 cases, including the forced 8 s cuts. D keeps the designed cut overlap exactly.
- **C:** no re-processing and no skipped speech, but it violates I3 (trimmed fragments) and removes the designed cut
  overlap.
- **D-specific properties:**
  - it classifies each frame exactly once across hundreds of re-scans;
  - it refuses a shrinking buffer;
  - repeated re-scans of an unchanged buffer hand nothing new to STT;
  - it is deterministic.
- **Real audio:** clip_01 and clip_19 at 20/100/1000 ms: D equals the one-shot segmentation.
- **Alert consequence:** clip_19 "Please leave me alone" at 100 ms: A has a repeat-induced TRIGGER_ALL; D has none and
  its events equal one pass.

## 6. Sequential latency (`latency.json`, `latency.log`)

The real live loop, per `_run_incremental_detection` call (VAD + segmentation + loop). STT is stubbed, so this isolates
the segmentation cost. The run was alone on a 4-vCPU x86_64 container, Python 3.11.15, with nothing else running.
Milliseconds per call; "last 10%" is the mean of the last decile of calls, i.e. the cost at the end of the recording.

| Recording (length) | Chunk | A p50 / p95 / max / last 10% | B p50 / p95 / max / last 10% | C p50 / p95 / max / last 10% | **D p50 / p95 / max / last 10%** |
|---|---|---|---|---|---|
| clip_01 (30 s) | 20 | 1.57 / 4.46 / 8.41 / 4.58 | 1.72 / 4.60 / 9.23 / 3.74 | 1.65 / 4.55 / 13.59 / 5.09 | **0.26 / 0.85 / 2.30 / 0.97** |
| | 100 | 1.53 / 5.23 / 5.62 / 4.24 | 1.48 / 3.75 / 4.71 / 3.54 | 1.47 / 3.97 / 4.55 / 3.99 | **0.31 / 0.60 / 0.90 / 0.57** |
| | 250 | 1.66 / 3.59 / 4.13 / 3.53 | 1.59 / 3.13 / 4.13 / 3.14 | 1.51 / 3.54 / 4.15 / 3.58 | **0.26 / 0.55 / 1.11 / 0.58** |
| | 1000 | 1.63 / 3.49 / 3.65 / 3.52 | 1.55 / 5.61 / 6.96 / 5.18 | 1.74 / 3.90 / 4.26 / 3.94 | **0.47 / 0.81 / 0.97 / 0.89** |
| clip_19 (30 s) | 20 | 1.60 / 3.14 / 17.79 / 3.21 | 1.83 / 4.34 / 6.01 / 3.69 | 1.72 / 2.92 / 3.97 / 2.89 | **0.28 / 0.55 / 0.82 / 0.54** |
| | 100 | 1.60 / 2.89 / 3.27 / 2.88 | 1.59 / 2.95 / 3.18 / 2.94 | 1.54 / 2.93 / 4.14 / 3.00 | **0.27 / 0.57 / 0.87 / 0.52** |
| | 250 | 1.53 / 2.91 / 3.09 / 2.90 | 1.62 / 2.94 / 3.08 / 2.89 | 1.57 / 4.17 / 5.17 / 3.57 | **0.51 / 0.91 / 1.46 / 0.90** |
| | 1000 | 1.69 / 3.61 / 5.11 / 4.03 | 1.73 / 3.27 / 3.95 / 3.22 | 2.02 / 3.52 / 8.73 / 3.74 | **0.79 / 1.30 / 2.13 / 1.52** |
| Tamil podcast (60 s) | 100 | 4.28 / 9.08 / 16.30 / 9.72 | 4.77 / 9.51 / 16.04 / 9.92 | 4.63 / 9.56 / 17.90 / 9.40 | **0.78 / 2.84 / 6.00 / 2.58** |
| | 250 | 4.37 / 13.07 / 20.33 / 13.07 | 5.88 / 12.12 / 14.26 / 11.68 | 6.00 / 14.37 / 19.01 / 13.66 | **1.29 / 2.29 / 3.62 / 2.33** |
| | 1000 | 4.75 / 9.61 / 11.56 / 9.64 | 5.12 / 9.12 / 10.92 / 9.63 | 4.95 / 9.78 / 11.02 / 9.55 | **1.02 / 2.77 / 4.33 / 3.09** |
| **BBC "Neil's summer job" (326 s, longest)** | 100 | 29.72 / 59.29 / 96.61 / 58.29 | 28.07 / 59.00 / 112.00 / 57.89 | 28.70 / 59.06 / 95.13 / 56.98 | **6.64 / 20.76 / 40.86 / 20.42** |
| | 250 | 27.73 / 59.43 / 92.91 / 57.00 | 28.23 / 57.15 / 109.75 / 58.20 | 27.66 / 56.47 / 95.52 / 54.47 | **7.45 / 16.59 / 23.87 / 15.48** |
| | 1000 | 28.01 / 57.26 / 73.09 / 56.30 | 32.05 / 61.60 / 74.90 / 55.82 | 29.23 / 52.68 / 71.21 / 52.37 | **7.00 / 15.40 / 26.07 / 16.14** |

Total segmentation CPU for the 326 s recording at 100 ms chunks: A 97.9 s, B 94.6 s, C 95.8 s, **D 25.9 s**.

**Reading:**
- A, B and C all re-classify the whole buffer with webrtcvad on every call, so their cost is roughly the same and grows
  linearly with journey length: about 3–4 ms at the end of 30 s, about 10–13 ms at 60 s, and about 55–58 ms at 326 s.
- **B fixes correctness but does not reduce this cost at all.**
- D removes the webrtcvad re-classification, giving 3–5× lower per-call cost on every row. **D's cost still grows with
  journey length** (last decile about 0.5–1.5 ms at 30 s, 2.3–3.1 ms at 60 s, 15–20 ms at 326 s), because it still
  rebuilds the frame list and re-runs segmentation over the whole buffer in Python on every call (§10, "Remaining
  cost").
- Longer journeys were not measured. By extrapolation both A and D keep growing, and D does so more slowly.
- No acceptance threshold is set; these are the measured values.
- The latency rows also re-confirm correctness: in every latency row D and B had excess 0, missed speech 0 and
  boundaries equal to the one-shot; A had excess on every recording except clip_01 at 1000 ms.

## 7. Determinism of D (`latency.json` → `determinism`)

D was run 3 times on each input: identical spans, identical cached frame classifications, and identical alerts (real
`UDKEngine`, manifest phrase). "Equals single pass" means D's cached speech flags equal the speech frames of one fresh
webrtcvad pass over the complete recording.

| Recording | Chunk | Frames | Identical spans | Identical classifications | Classifications = single pass | Identical alerts |
|---|---|---|---|---|---|---|
| clip_19_muffled | 20 ms | 1000 | yes | yes | yes | yes |
| clip_19_muffled | 250 ms | 1000 | yes | yes | yes | yes |
| clip_28_overlapping | 20 ms | 1000 | yes | yes | yes | yes |
| clip_28_overlapping | 250 ms | 1000 | yes | yes | yes | yes |
| Heroine fight scene (negative) | 100 ms | 1700 | yes | yes | yes | n/a (no phrase manifest) |

The full comparison (§4) also re-ran every recording at 100 ms and found 0 nondeterministic results for all candidates.

## 8. Invariant review

| | A current | B fresh-per-scan | C frontier-trim | **D cached classification** |
|---|---|---|---|---|
| I1 no accidental re-processing | **fails** (every mixed clip at 20–100 ms) | holds | holds | **holds** |
| I2 no skipped speech | holds | holds | holds | **holds** |
| I3 boundaries = one-shot | **fails** | holds | **fails** (fragments; removes designed cut overlap) | **holds** |
| I4 alerts = one pass | **fails** (extra events, repeat-induced ALL, escalations) | holds | **fails** (extra events; 1 repeat-induced ALL, 1 escalation at 20 ms) | **holds** |
| I5 determinism | deterministic (the defect is deterministic too) | holds | holds | **holds** (§7) |
| I6 latency (reported) | p95 59 ms/call at 326 s, growing | same as A (no saving) | same as A | p95 15–21 ms/call at 326 s, still growing, 3–5× lower (§6) |

Why D's streaming output equals the one-shot segmentation, beyond the measurement:
- With flags fixed per frame, `segment_speech` is a pure function of the flag prefix.
- A segment is finalized only when `end_ms < total`. That can happen only once the loop has stopped on real evidence,
  either post-roll silence or the 8 s cap with more frames after it. So a finalized segment's boundaries do not change
  as the prefix grows.
- If the classifier sees the frames once, in order, D's flags are exactly the flags of a single pass over the full
  recording.

## 9. Recommendation: D, not B, not C

- **D over B.**
  - **Same correctness:** identical results on all 48 recordings, every chunk size, and all boundary cases.
  - **Cost:** B re-classifies the entire buffer from a fresh `webrtcvad.Vad` on every chunk, so its per-call cost grows
    with journey length exactly like A's. D calls webrtcvad only for new frames (§6).
  - **Semantics:** B's flags are not the same kind as the one-shot's. Each scan re-derives them from state zero. They
    happened to match the one-shot here because every scan starts from zero, just like the one-shot does. D's flags are
    by construction the single-pass flags.
- **Not C.**
  - C stops the duplicated audio but emits fragments that are not utterances (I3 fails in every recording).
  - It removes the designed 8 s-cut overlap, which is the phrase-split protection.
  - It still produces extra alert events, and one repeat-induced TRIGGER_ALL at 20 ms (I4 fails).
- **Not A.** A is the defect.

## 10. Recommended production design (NOT implemented)

**The exact change, for a future isolated prototype behind a flag that defaults to OFF:**
- `vad.VAD` gains an opt-in, per-instance classification cache: a list of booleans indexed by frame number from the
  start of the buffer passed to `segment_speech`.
- `segment_speech`:
  1. builds the frames exactly as today;
  2. reuses the cached flags for indices `< len(cache)`;
  3. calls `self._vad.is_speech` only for new complete frames, in order, appending to the cache;
  4. runs the unchanged segmentation.
- Nothing else in `segment_speech` changes: pre/post-roll, the 8 s cap and the post-cut overlap stay as they are.
- `api._run_incremental_detection` needs no change. The flag selects the cached behaviour when `JourneyState.vad` is
  constructed. With the flag OFF, behaviour is byte-identical to today.

**Persisted state.** Only the in-memory per-VAD flag list and the count of frames seen. It is not written to the
DB/AudioStore. It is derived state, rebuildable from the audio.

**Frame identity.** A frame is identified by its index `k` = byte offset `k·960` from the start of the journey buffer.
This is valid today only because of how the architecture works:
- `JourneyState.audio_buffer` is append-only (`_ingest_frame` extends it; nothing trims it);
- frames are appended strictly in `seq` order (`pending_frames` reorders);
- duplicate or retried `seq` values are dropped before append (`seq < next_expected_seq`);
- the frame grid is fixed at byte 0, so chunk sizes that are not frame-aligned do not shift it. A partial tail frame is
  never classified until it is complete (`_frames` yields whole frames only).

What the index is **not** safe against:
- **Trimming.** If the buffer is ever trimmed, index `k` refers to different audio. Identity must then become an
  absolute frame offset (`base_frame + k`), with `base_frame` advanced by exactly the trimmed frame count.
- **Rewriting.** Any mutation of already-appended bytes.

Guards for the prototype:
1. raise, or reset the cache and log, if the buffer is shorter than the cached frame count (the experiment raises);
2. optionally keep a cheap checksum of the last cached frame and verify it on each call, which detects in-place rewrites.

**Unresolved:** there is no architectural "journey audio epoch" id. If trimming is introduced, identity must be designed
with it (absolute offsets), not bolted on.

**Lifecycle.** The cache belongs to the `VAD` instance, which belongs to exactly one `JourneyState`
(`field(default_factory=VAD)`). There is therefore no cross-journey sharing and no leakage.

| Event | What happens to the cache |
|---|---|
| New journey | New `VAD` with an empty cache. |
| Continuous streaming | The cache grows by the new complete frames. |
| Growth or partial tail | Only complete frames are classified; the tail waits. |
| Same frame presented again (duplicate or retried seq) | Dropped before the buffer, so the cache is untouched. |
| Same buffer re-scanned | Cached flags only; no new classification and no new STT work (tested). |
| Language switch | Engine rebuilt, VAD kept, so the cache is still valid (same audio). |
| Reconnect (same process) | Same `JourneyState` and VAD, so the cache is still valid. |
| Process restart / recovery | A new `JourneyState` and fresh VAD and cache. The buffer is refilled from `AudioStore.read_contiguous_prefix`, and the first scan classifies that prefix once, in order. The result equals a single pass over the recovered audio. |
| Reset / `stop_journey` / end | The `final=True` flush uses the cache; the journey and its VAD are dropped, and the cache with them. |
| Trimming (does not exist today) | Invalidates index identity; needs absolute offsets. Until then, the shrink guard fails loudly. |

**Restart caveat (pre-existing, not introduced by D).** `processed_up_to_ms` is not persisted (it is not in
`db.save_journey`), and recovery starts it at 0. So after a restart, all recovered audio is re-segmented and re-sent to
STT, and alerts may be re-emitted.
- With D, the re-emitted segments are the same segments, so `event_id = sha256(journey:start_ms:udk_id)` is identical
  and can be de-duplicated. With A, the start/end values differ.
- Repeat-window counting across a replay is unresolved and out of scope here.
- The recovery docstring says "resume without reprocessing everything" (api.py ≈ l.196). The code does not persist
  the processed frontier, so that intent and the code disagree. This is pre-existing and separate from this fix.

**Segment identity.** With D, `segment_id = journey:start-end` becomes unique per utterance. Designed post-cut segments
overlap but have distinct ids, exactly as in the one-shot segmentation.

**Memory.**
- The cache holds one flag per 30 ms: about 120 000 entries per hour. As a Python list of bools that is about 1 MB/h of
  pointer storage (a `bytearray` would be 120 kB/h).
- This is negligible next to the existing unbounded audio buffer, at 115 MB/h of s16 PCM, which is pre-existing and
  unchanged.

**Remaining cost.** D still rebuilds the frame list and runs segmentation over the whole buffer on each call (O(n)
Python per chunk). It removes the webrtcvad re-classification, not the re-scan.
- A later optimization is to resume segmentation from the last finalized segment. It is not needed for correctness and
  not recommended in the same change.

**8 s-cut overlap.** Unchanged. D preserves it exactly (§4, §5). No change to `max_segment_ms`, pre-roll or post-roll.

## 11. Uncertainties

- **Chunk size:** the client chunk size is undocumented, so 20–1000 ms was swept.
- **Material:** the recordings are calibration/test clips with long silences, not real journeys. They are not
  evidence of real-world frequency or of field latency.
- **STT:** stubbed with the manifest phrase. The semantic matcher, intent veto and BEATs are not exercised. Real STT
  could mask or add differences.
- **Media alerts:** alert consequences are measured on the 30 mixed clips only.
- **Hardware:** latency is from a 4-vCPU cloud container with sequential runs; it is not production hardware.
- **Restart:** restart behaviour was reasoned from code, not executed end to end.

## 12. Reproducibility

- **Code base:** git HEAD `96ea038`, plus the uncommitted working tree. `api.py` and `vad.py` are identical to what the
  earlier integrity measurement used; `api.py` differs from 96ea038 only by the +38-line shadow hook, with 0 changed
  lines.
- **Candidate config:**
  - `vad.VAD` defaults: webrtcvad aggressiveness 1, 30 ms frames, pre/post-roll 1500 ms, `max_segment_ms` 8000;
  - `UDKEngine` with the 20 standard UDKs and no semantic model;
  - `REPEAT_WINDOW_S` 15.
- **Recordings:** `real_recordings/mixed/*.mp3` (30), plus `real_recordings/positives` and `real_recordings/negatives`
  with `--skip-converted` (18). Decoded by PyAV to 16 kHz mono s16.
- **Commands:**
  ```
  python udk_shadow/bench/segmentation_candidates.py real_recordings/mixed --chunks 20,100,250,500,1000 --candidates <C> --out mixed_<C>.json
  python udk_shadow/bench/segmentation_candidates.py real_recordings/positives real_recordings/negatives --skip-converted \
         --chunks 100,250,500,1000 --candidates <C> --out media_<C>.json
  python udk_shadow/bench/segmentation_latency.py --out latency.json      # alone, no other load
  python udk_shadow/test_segmentation_candidates.py
  ```
- **Environment:** see `latency.json` → `environment`. Dependencies: webrtcvad-wheels, PyAV, numpy, rapidfuzz, and the
  fastapi stack for importing `api.py`.
- **Result files:** `mixed_{A_current,B_fresh,C_frontier,D_cached}.json|.log`, `media_*.json|.log`, `latency.json|.log`.
