# Live streaming segmentation integrity (PHASE6_INTEGRATION_CONTRACT §10 Q3)

**Offline measurement only. The live code was not changed.** The tool is `udk_shadow/bench/segmentation_integrity.py`; the tests are in `udk_shadow/test_segmentation_integrity.py`; the raw data is in `mixed.json`, `media.json` and the logs.

## Question

When audio streams in chunks, does the live path hand the same audio to STT more than once, or never hand over speech at all?

## Method

- The real `api._run_incremental_detection` (extracted from `api.py`) and the real `vad.VAD` (webrtcvad, aggressiveness 1, pre- and post-roll 1.5 s, maximum segment 8 s).
- The loop is fed chunk by chunk, exactly as `_ingest_frame` does, and finishes with the `final=True` flush that `stop_journey` performs.
- **Compared against:**
  - a one-shot segmentation of the complete recording by a fresh `VAD`;
  - webrtcvad's own speech frames.
- **Alert consequences:** only for the 30 `mixed/` clips, which ship a manifest giving each clip's spoken phrase.
  - The STT stub returns that manifest phrase for any segment containing speech frames, and no text otherwise.
  - Alerts come from the real `UDKEngine` with the 20 standard UDKs and no semantic model.
- **Audio:** local `real_recordings/`.
  - `mixed/`: 30 clips × 30 s.
  - `positives/` and `negatives/`: 18 recordings, 5–326 s; the `_converted_*.wav` duplicates are skipped.
- **Client chunk size:** not documented, so it was tested at 20, 100, 250, 500 and 1000 ms (media: 100–1000 ms).

## Findings

**1. The same audio is re-processed.** The live `VAD` object is created once per journey, and webrtcvad keeps adaptive state from one `segment_speech` re-scan to the next. So the same frames are classified differently on successive scans. A segment whose end shifts by a frame has `end_ms > processed_up_to_ms` and is processed again.

The test shows that a fresh VAD per scan removes the re-processing on a real clip; the stateless scripted control gives exactly one processing per segment.

| Chunk | Mixed (30 clips): segments processed / one-shot | Mixed: clips with excess overlap | Mixed: excess overlap | Media (18): recordings with excess overlap | Media: excess overlap |
|---|---|---|---|---|---|
| 20 ms | 159 / 50 | 30 | 202.6 s | – | – |
| 100 ms | 133 / 50 | 30 | 141.0 s | 9 | 187.6 s |
| 250 ms | 103 / 50 | 26 | 77.9 s | 7 | 148.0 s |
| 500 ms | 96 / 50 | 23 | 63.4 s | 7 | 106.8 s |
| 1000 ms | 82 / 50 | 11 | 35.6 s | 7 | 75.3 s |

"Excess overlap" is streaming overlap minus the overlap the one-shot segmentation itself has by design. The VAD deliberately lets the segment after a forced 8 s cut overlap back into the previous one: 8.3 s of that in the mixed set, 127.1 s in the media set. The excess is computed per recording and floored at 0.

In the mixed set, much of the excess is leading silence re-processed several times at stream start. For example, clip_01's first 1.6 s went to STT 3 times.

**2. Alert consequences** (mixed set; STT = known phrase; real UDK engine):

| Chunk | Clips with extra alert events | Extra alert events | Clips escalated TRIGGER_VERIFY → TRIGGER_ALL by streaming |
|---|---|---|---|
| 20 ms | 13/30 | 26 | 4 |
| 100 ms | 11/30 | 19 | 2 |
| 250 ms | 10/30 | 13 | 2 |
| 500 ms | 9/30 | 11 | 2 |
| 1000 ms | 5/30 | 6 | 0 |

- **How escalation happens:** the re-processed utterance matches the same UDK again within `REPEAT_WINDOW_S = 15 s`. The engine counts that as a repetition, so the second event becomes TRIGGER_ALL with reason "repeated within window".
- **Examples:** clip_19 "Please leave me alone" (UDK_08; 100, 250 and 500 ms), clip_28 "Someone grabbed me" (UDK_04), clip_21, clip_23.
- In no case did streaming produce **fewer** alerts than the one-shot pass.

**3. Speech is not skipped.**
- 0 ms of webrtcvad speech frames was left unprocessed, in every recording at every chunk size.
- The only difference from the one-shot segments is tail post-roll, 240–360 ms in total across 8–11 clips: segments ending 30 ms earlier in the streamed version.

**4. Cost of re-scanning:** the worst single call of the live loop (VAD only; STT stubbed) was ≤ 95 ms, on recordings up to 326 s. This grows with journey length because each chunk re-scans the whole buffer, a risk Phase 0 already noted. This is not measured for longer journeys.

## What this means, and what it does not

- The contract §10 Q3 answer, for this material and these chunk sizes: **processed segments do overlap, and the same speech can be transcribed more than once.** `segment_id` = `journey:start-end` is therefore not unique per utterance: several ids can cover the same audio.
- **Safety-relevant effects on the live path**, as the code works today:
  - Duplicate alert events for one utterance. Their `event_id` differs whenever `start_ms` differs.
  - Repetition escalation to TRIGGER_ALL that a single utterance would not earn.
  - Re-processed audio also enters the repetition and distinct-UDK windows (see contract F-6).
- **Not measured:**
  - real client chunk sizes;
  - real STT output, since the STT stub returns the manifest phrase;
  - the semantic matcher;
  - the intent veto;
  - BEATs;
  - whether downstream consumers de-duplicate the events;
  - how often it happens on real journeys. These recordings are calibration/test clips with long silences, not journeys.
- **No live-code fix was made.** Any change (for example a fresh `Vad` per scan, or never re-processing audio at or before `processed_up_to_ms`) changes live alert behaviour and needs its own approved change, with before/after evidence from this same tool.
