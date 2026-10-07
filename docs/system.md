# UDK multilingual detection service — system card (2026-10-08)

The live distress-detection service (`api.py`) with everything on: English (the live model, unchanged), each user's
own phrase (custom UDK), Hindi, and Telugu / Tamil / Kannada. Branch `multilingual`, tag `gpu-deploy-ready-2026-10-08`
(frozen system `freeze-2026-10-07-r2` + the GPU deployment). Deployment: `deploy/README.md` ("GPU host").
Language detail: `docs/hindi_distress_system.md`, `safety_router/README.md`.

## 1. Per speech segment

```
phone audio, 200 ms chunks over a WebSocket (each journey processed on a worker thread, in order)
  -> VAD (webrtcvad mode 1, 30 ms frames, 1.5 s kept before/after, cut at 8 s of continuous speech)
  -> in parallel:
     a. scream detector (BEATs, 2 s windows, 4 classes)                     -> ask
     b. custom-UDK gate: its own Whisper medium.en (beam 5, one decode) + the segment's Parakeet run
        -> the user's phrase in either transcript (setup spellings, whole words)      -> ALERT contacts,
           and the other branches' result for that segment is dropped
     c. language ID (Whisper small) -> route:
          English / Hindi-led: the most likely languages up to 95 % (both when mixed)
          Telugu / Tamil / Kannada-led: all three, plus English / Hindi only at >= 20 %
        English -> general model: Whisper small.en + Parakeet, exact / fuzzy / MiniLM match to 20 phrases,
                   intent veto (mDeBERTa), a repeat within 15 s of AUDIO escalates ask -> alert
        Hindi   -> IndicConformer -> [A] LaBSE similarity + [B] MuRIL (30 s context, a false-alarm filter,
                   not a detector) + rule, and a word-for-word phrase check (ask)
        te/ta/kn-> the same IndicConformer encoding, decoded per language -> exact / fuzzy on 21 phrases,
                   >= half the phrase's words, safe-context cue words -> ask only
  -> decide: the highest level wins (none < ask < alert); a custom hit overrides
  -> event (TRIGGER_VERIFY = ask "Are you safe?", TRIGGER_ALL = alert contacts) with layer, transcript, audio times
```

Failure handling: Parakeet failing or exceeding `UDK_PARAKEET_TIMEOUT_S` (30 s) -> that segment uses Whisper
alone; the gate, Hindi or te/ta/kn failing -> the other branches' result stands; a feature enabled but not
loadable -> the service refuses to start (the deploy rolls back).

## 2. Settings
Detection settings ship in `deploy/.env.example`. HOST settings come from the host's SSM config and never from that
file: `UDK_DEVICE`, `UDK_CUSTOM_UDK_STT_MODEL`, `UDK_ENABLE_HINDI`, `UDK_ENABLE_INDIC_EXACT`, `UDK_HINDI_DEVICE`,
`UDK_TEXT_MODELS_DEVICE`, `UDK_CPU_THREADS`.

| | GPU host (`sakhi-udk-gpu`) | CPU host (`sakhi-udk`, live today) |
|---|---|---|
| device | `cuda` (one 16 GB T4) | `cpu` |
| custom-UDK gate | `medium.en`, its own model, in parallel | `small.en`, shared with the English model |
| Hindi, Telugu/Tamil/Kannada | on | off |
| text models (LaBSE, MuRIL, intent veto) | `UDK_TEXT_MODELS_DEVICE=cpu` | CPU |
| models at start | all baked into the image, `HF_HUB_OFFLINE=1` | baked into the image |

Precision: all models fp32 except Whisper (int8 on CPU, float16 on GPU); Whisper beam search, 5 candidates.

## 3. Measured (Kaggle, 2026-10-07; same code and settings on both devices)

| | GPU (T4) | CPU (4 vCPU) |
|---|---|---|
| time per speech segment (median) | 1.5–1.9 s | 21 s |
| seconds of work per second of speech | 0.21–0.23 (keeps up) | 2.55 (falls behind) |
| 10-minute journey | flat, 11–21 s of work per minute | — |
| peak memory | 11.9 GB GPU, 5.4 GB RAM | 11.9 GB RAM |
| decisions GPU vs CPU | identical (10/10) | |

Time per segment by model (GPU | CPU): gate Whisper medium.en 0.88 | 16.6 s, Parakeet 0.46 | 3.7, IndicConformer
encoder 0.43 | 3.4 and decoders 0.64 | 1.6, language ID 0.11 | 2.8, English Whisper small.en 1.08 | 6.9 per English
segment, LaBSE + MuRIL 0.03 | 0.5 per Hindi segment.

Detection:
- Custom phrase (8 phrases x 4 synthetic voices): 193/224 should-fire caught (muffled 19/32); 0/128 near-misses,
  0/9,856 other-phrase checks. Misses: 13 of 31 spelling mismatches, 16 mishearings.
- Telugu real voice notes 10/10; Telugu/Tamil/Kannada acted scenes 12/12; 0 asks on 100 min of real te/ta/kn YouTube.
- Hindi real acted danger scenes: 2 alerts, 1 ask, 2 missed (the misses carry none of the 20 phrases).
  Hindi TV / phone talk: 0–0.8 alerts/h, 0.4–1.3 asks/h.
- Whole system on 2 h of talk-heavy real YouTube / podcasts (hi/te/ta/kn): ~10 events per journey-hour, from 3 of
  12 journeys, in bursts (no cooldown).

## 4. Known limits (not fixed)
- No drop policy: if the host falls behind, a journey's delay grows. One T4 keeps up with roughly 4–5 journeys of
  continuous speech; one worker per container; Parakeet and the gate each run on one worker shared by all journeys.
- On continuous speech the VAD never closes: segments are ~11 s windows overlapping by 1.5 s, so a phrase longer than
  1.5 s that straddles a cut can be missed (custom phrases ~4–10 %, Indian-language phrases ~13–21 %, during
  continuous talk only), and decisions wait ~9.5 s of audio plus processing.
- No cooldown or de-duplication of events; no escalation across branches (scream then a phrase); what an
  unanswered ask does is decided in the app, not here.
- Custom phrase: exact spelling match; setup does not check the phrase against the general list or everyday audio.
- Hindi detects the 20 phrases, not danger in other words ([B] scores real conversational danger ~0.003–0.1).
- The CPU host cannot run the medium.en gate in real time; its small.en gate's recall is unmeasured.

## 5. Tested and not adopted
fp16 encoders (slower; some segments lost words), greedy decoding (less reliable than beam 5), distil-medium.en
gate (faster, caught 186 vs 193 of 224), parallel Indian-language decoders, query-by-example matching (twice).

## 6. Checks
`python test_live_fixes.py` (Parakeet failure / timeout, audio-time repeat window, non-blocking WebSocket),
`test_custom_udk.py`, `test_hindi_routing.py`, `test_indic_exact.py`, `test_incremental_vad.py`,
`test_memory_options.py`, `test_multilingual.py`, `test_m3`–`test_m7`, `test_kws.py`, `test_scream_trigger.py`,
`test_parakeet_either.py`, `python -m safety_router.test_router`, `python deploy/check_package.py`.
