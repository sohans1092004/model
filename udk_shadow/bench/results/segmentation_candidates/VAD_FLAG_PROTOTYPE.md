# Candidate D prototype in `vad.VAD` (flag `cache_classifications`, OFF by default)

**Status: prototype only.**
- The flag defaults to OFF, and nothing sets it: `api.py` is unchanged and does not reference the flag.
- The live service behaves exactly as before.
- This does NOT enable the fix, change alert logic, or change any production default.
- Background: `SEGMENTATION_CANDIDATES.md`, from the completed experiment. It is not repeated here.

## 1. The change (`vad.py` only)

- `VAD.__init__` gets a new keyword `cache_classifications: bool = False`, plus three attributes that only ON mode
  reads or writes:
  - `_flag_cache`: a `bytearray` holding one byte per frame;
  - `_flag_cache_last_frame`: a copy of the last kept frame;
  - `cache_resets`: a counter.
- In `segment_speech`, one line changes, from
  `flags = [self._vad.is_speech(f, SAMPLE_RATE) for f in frames]` to `flags = self._classify(frames)`.
- **`_classify` with the flag OFF** returns exactly that original list comprehension.
- **`_classify` with the flag ON:**
  1. classifies only the frames beyond `len(_flag_cache)`, in order, using the same persistent `self._vad`;
  2. appends their flags to the cache;
  3. returns the cache.
- New helper: `reset_classification_cache()`.
- A module logger is added for the invalidation warning.
- **Not changed:**
  - the segmentation loop: pre/post-roll, the `max_segment_ms` cut and the overlap after it;
  - `total_ms`, `_frames`, `SpeechSegment`;
  - `api._run_incremental_detection`;
  - `JourneyState`;
  - alert logic.
- **Why the cache is kept outside `self._vad` rather than replacing it:** existing tests and tools inject a classifier
  by assigning `vad._vad`, and that keeps working in both modes.

## 2. Semantics (ON mode)

| Topic | Definition |
|---|---|
| **Frame identity** | Frame `k` means bytes `[k·960, (k+1)·960)` of the pcm passed to `segment_speech`, i.e. its index from the start of the journey buffer. This is valid only because `api.py`'s journey buffer is append-only: `_ingest_frame` only `extend`s it, in `seq` order, and duplicate or retried `seq` values are dropped before the append. The frame grid is fixed at byte 0, so chunks not aligned to frames do not shift it. |
| **Absolute offsets / trimming** | **Not provided and not supported.** The architecture has no base-offset or "audio epoch" for the journey buffer. If trimming is ever added, identity must become `base_frame + k`, designed together with trimming. This prototype does not invent that. |
| **Partial frames** | `_frames` yields complete frames only, so a partial tail frame is never classified. It is classified exactly once, in order, when it becomes complete. |
| **Repeated re-scans** | For an unchanged buffer, no classifier call is made; the kept flags are reused, and the segments are identical, so nothing new reaches STT. For a grown buffer, only the new complete frames are classified. |
| **Cache lifecycle** | The cache belongs to one `VAD` instance. In `api.py` each `JourneyState` owns its own `VAD` (`field(default_factory=VAD)`), so a new journey gets an empty cache and there is no cross-journey sharing. The cache is dropped together with the journey. A language switch rebuilds the engine, not the VAD, so the cache stays valid (same audio). A reconnect in the same process reuses the `JourneyState`, so the cache stays valid. |
| **Process restart / recovery** | A new `JourneyState` gets a fresh VAD and an empty cache. The buffer is refilled from `AudioStore.read_contiguous_prefix`, and the first scan classifies it once, in order, which equals a single pass over the recovered audio. **Pre-existing and unchanged:** `processed_up_to_ms` is not persisted, so recovered audio is re-sent to STT after a restart, with the same boundaries in ON mode. |
| **Journey reset** | `api.py` has no in-place reset: a journey ends via `stop_journey` (the `final=True` flush uses the cache) and a new journey gets a new VAD. `reset_classification_cache()` exists for explicit callers; live code does not call it. |
| **Buffer shrink** | This cannot happen today. If the pcm has fewer frames than the cache, the kept flags are discarded and the buffer is re-classified. A `WARNING` is logged on the `vad` logger and `cache_resets` is incremented. It does **not** raise: in the live ingest path an exception would stop detection for the journey, and falling back to a full re-classification is exactly today's behaviour. |
| **In-place rewrite** | If the frame at the last kept index no longer equals the kept copy, the cache is handled the same way as a shrink. This is a cheap guard, not a proof: a rewrite of an earlier frame, or trimming that happens to leave identical bytes at that index (for example digital silence), would go undetected. Trimming stays unsupported. |
| **8 s forced cut** | The segmentation code is unchanged, so the cut and the designed pre-roll overlap after it are produced exactly as in the one-shot segmentation. Tested: the overlap equals the one-shot's at every chunk size. |
| **Memory** | 1 byte per complete 30 ms frame, about 120 kB per hour of audio, plus one 960-byte frame copy. It grows with the journey, like the existing audio buffer (about 115 MB/h), and is freed with the journey. Nothing is allocated per call. |
| **Cost** | webrtcvad runs once per frame instead of once per frame per call. The frame list and segmentation over the whole buffer are still rebuilt on every call (O(n) Python), exactly as in candidate D. |

## 3. OFF-mode guarantee

- With the flag OFF, `segment_speech` executes the same statements as the pre-prototype `vad.py` (96ea038): the only
  added work is one attribute test.
- The frozen original is kept at `udk_shadow/bench/vad_original_96ea038.py`, and its sha256 is verified when loaded.
- OFF mode never reads or writes the cache attributes.

## 4. Evidence

**Tests: `test_vad_classification_cache.py` (28 checks).**
- **OFF == original:**
  - 300 random flag patterns × roll and cap settings: identical segments and identical classifier call sequences;
  - the live loop with a state-carrying classifier, 8 scenarios × 7 chunk sizes: identical output on every call and
    identical STT spans, the current defect included;
  - real clip_01 and clip_19 at 20/250/1000 ms: identical output on every call;
  - real alerts (clip_19, 100 ms): identical events, including the original's repeat-induced TRIGGER_ALL.
- **ON == candidate D == one-shot:**
  - identical output on every call and identical kept flags compared with the experiment's `CandidateD`, for scripted
    and real audio;
  - no re-processing, no skipped speech, and boundaries equal to the one-shot;
  - designed 8 s-cut overlap preserved;
  - alerts equal to one pass.
- **Lifecycle:**
  - each frame is classified exactly once, in order, over hundreds of re-scans with a partial tail;
  - an unchanged re-scan makes no classifier calls;
  - 1 byte per frame;
  - the kept flags equal a single pass;
  - shrink and in-place rewrite are detected, logged and counted, and the result equals a fresh segmentation;
  - explicit reset works;
  - no sharing between instances;
  - empty and sub-frame buffers are handled;
  - determinism holds.
- **Mutation check** (run once by hand, `vad.py` restored byte-identical afterwards):
  - forcing OFF to use the cache fails 10 checks;
  - forcing ON to re-classify old frames fails 12 checks.

**Full corpus: `vad_flag_equivalence.py`**, 48 recordings × all chunk sizes; results in `vad_flag_mixed.json`,
`vad_flag_media.json` and the logs. The run compares, for every call of the real live loop, the segments returned (start, end, pcm digest), the spans
handed to STT, and (for the 30 mixed clips) the real UDKEngine alert events.

| Set | Rows (recordings × chunks) | OFF == original, every call, spans and alerts | ON == candidate D (every call, spans, kept flags) and == one-shot (0 excess, 0 missed, boundaries equal) | ON cache resets |
|---|---|---|---|---|
| mixed (30 clips; 20/100/250/500/1000 ms) | 150 | **150/150** | **150/150** | 0 |
| media (18 recordings; 100/250/500/1000 ms) | 72 | **72/72** | **72/72** | 0 |

Alerts, mixed set, summed over all chunk sizes:

| | Extra alert events | Repeat-induced TRIGGER_ALL |
|---|---|---|
| OFF | 75 | 31 |
| ON | 0 | 0 |

- OFF's totals are exactly the experiment's candidate A (26+19+13+11+6 extra events and 10+7+6+6+2 repeat-induced
  TRIGGER_ALLs): **OFF reproduces today's behaviour, defect included.**
- ON's events equal one pass in 150/150 rows.
- The designed 8 s-cut overlap is present in ON exactly as in the one-shot: 8.25 s per mixed pass, 127.05 s per media
  pass.
- The two sets ran in parallel, so their `seconds` fields are not latency.

**Latency: `vad_flag_latency.json`**, a sequential run of A (the OFF mode), D (experiment) and D_vad_flag.
The run was alone on the 4-vCPU container (Python 3.11.15), measuring milliseconds per live-loop call with STT
stubbed. Values are p95 / last 10 % mean.

| Recording | Chunk | A = OFF (today) | D experiment | **D_vad_flag (prototype ON)** |
|---|---|---|---|---|
| clip_01 (30 s) | 20 / 100 / 250 / 1000 | 4.17/4.12, 3.67/3.48, 3.59/3.54, 3.68/3.55 | 0.56/0.59, 0.91/0.81, 0.71/0.56, 0.70/0.65 | **0.41/0.40, 0.68/0.68, 0.47/0.47, 0.59/0.53** |
| clip_19 (30 s) | 20 / 100 / 250 / 1000 | 2.91/3.08, 4.25/3.70, 3.78/3.54, 3.03/2.97 | 0.53/0.51, 0.75/0.54, 0.58/0.56, 0.85/0.82 | **0.42/0.40, 0.41/0.39, 0.45/0.43, 0.50/0.50** |
| Tamil podcast (60 s) | 100 / 250 / 1000 | 10.60/10.34, 13.03/11.33, 9.21/9.28 | 2.76/2.02, 1.69/1.62, 1.66/1.66 | **3.00/3.22, 1.68/2.00, 1.54/1.54** |
| BBC (326 s, longest) | 100 / 250 / 1000 | 52.87/53.56, 52.80/52.35, 52.39/52.06 | 15.61/15.36, 21.65/15.40, 15.51/14.70 | **12.67/12.56, 16.81/12.18, 13.70/13.42** |

Total segmentation CPU for the 326 s recording at 100 ms chunks: A 90.4 s, D 24.2 s, **prototype 20.0 s**.

Full numbers for the longest recording (BBC, 326 s; `vad_flag_latency.log`). Milliseconds per call, total = sum over
all calls:

| Chunk | Mode | Calls | p50 | p95 | Worst call | Total |
|---|---|---|---|---|---|---|
| 100 ms | OFF (today) | 3261 | 27.50 | 52.87 | 87.61 | 90.44 s |
| | D (experiment) | 3261 | 6.81 | 15.61 | 27.55 | 24.16 s |
| | **ON (prototype)** | 3261 | **5.69** | **12.67** | **21.23** | **20.02 s** |
| 250 ms | OFF | 1305 | 27.30 | 52.80 | 83.47 | 36.35 s |
| | D | 1305 | 6.86 | 21.65 | 35.74 | 10.50 s |
| | **ON** | 1305 | **5.29** | **16.81** | **26.97** | **8.52 s** |
| 1000 ms | OFF | 327 | 26.44 | 52.39 | 68.15 | 8.98 s |
| | D | 327 | 7.41 | 15.51 | 26.46 | 2.47 s |
| | **ON** | 327 | **5.82** | **13.70** | **19.37** | **2.14 s** |

Why ON is slightly cheaper than the experiment's D, while agreeing on everything else:
- **The webrtcvad work is identical:** each frame is classified exactly once, in order, by the same persistent
  classifier (§4 shows identical flags on every row).
- **The difference is Python overhead on cached frames.** D kept `VAD.segment_speech` untouched and put a proxy object
  in place of `self._vad`, so every re-scan still made one Python method call per cached frame (`_CachedClassifier.is_speech`
  plus an index check) and built a new `flags` list. The prototype skips cached frames entirely: it classifies
  `frames[k:]` only and hands the kept `bytearray` straight to the unchanged segmentation loop.
- **Both still rebuild the frame list and re-run segmentation over the whole buffer** on every call, so both still grow
  with journey length. The remaining gap to OFF is the webrtcvad re-classification that ON and D both remove.
- **Run-to-run variation:** OFF was 90.4 s total here vs 97.9 s for the same configuration in the earlier sequential
  run (about 8 %). Differences of that size between runs are noise, not a property of either implementation.

- The prototype costs the same as the experiment's D, or slightly less, since it has no Python proxy call per cached
  frame.
- Like D, its cost per call still grows with journey length, because the whole-buffer segmentation re-scan remains.
- In every latency row the prototype had 0 excess, 0 missed speech, and boundaries equal to the one-shot.
- The D determinism checks re-passed (5/5).
- No threshold is set; longer journeys and production hardware were not measured.

## 5. Not covered / open

- The flag is not wired into `api.py`. Enabling it needs a separate, approved change: a config or env switch read
  when `JourneyState.vad` is created, plus effective-config reporting.
- Buffer trimming and absolute frame offsets are unsupported (§2).
- Persisting the processed point across restarts is pre-existing and out of scope.
- Real STT, the semantic matcher, the intent veto and BEATs are not exercised (STT is stubbed with the manifest
  phrase).
- The real client chunk size is unknown.
- These recordings are test clips, not journeys, so no real-world frequency or latency claims follow from them.
