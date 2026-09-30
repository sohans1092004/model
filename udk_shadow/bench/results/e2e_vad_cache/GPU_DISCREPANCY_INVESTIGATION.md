# GPU discrepancy investigation: VAD cache OFF vs ON (real models, Tesla T4)

**Conclusion: `RESOLVED_SAFE_FOR_NEXT_CONTROLLED_TEST`.**
- All three cases are classified from observed evidence, and none is a defect in the cache logic.
- ON loses no detection and introduces no false alert.
- The one safety-relevant tier difference (pos_02) is Whisper's boundary sensitivity acting through the STT confidence
  gate. The 30 ms sweep shows it alternates with the segment's start position. ON's outcome is the majority outcome in
  that neighbourhood (6 of 9 positions), OFF's the minority (3 of 9), so the cache does not systematically remove it.
- The fragility itself exists before and without the cache, and is recorded as a separate risk (§4).
- This is **not** a production go/no-go.

## 1. Scope

**Cases:**

| Case | Question |
|---|---|
| pos_02 | OFF TRIGGER_ALL UDK_01 vs ON acoustic VERIFY |
| pos_01 | Same tier, different UDK |
| neg_10 | Whether the false alert is real live output |

mix_clip_30 is not re-investigated. The corrected saved results show no unexplained difference for it (utterances
alerted by only one mode: 0 in all rows).

**Evidence:**
- `gpu_t4_real_models/runs.zip`: live per-segment chain for OFF, ON and one repeat of each.
- `gpu_t4_investigation/`: v1 probe.
- **`gpu_t4_investigation_v2/`**: every window replayed through the real `api._run_incremental_detection`.
  - 5 repeats per exact window, on identical bytes;
  - 30 ms boundary sweeps, 3 repeats per position;
  - sequence replays of repeat-window state.
- Local checks:
  - window digests recomputed from the recordings;
  - the real `UDKEngine` replayed on the observed T4 transcripts.

**Components (T4):**
- faster-whisper small.en on CUDA; Parakeet on CUDA; MiniLM semantic matcher;
- STT confidence gate; BEATs trigger and corroboration;
- intent gate with the production-pinned model at threshold 0.02.

**Audio identity.** All six windows have exactly the digests the live run recorded, in the local recompute and in every
v2 repeat. The v2 replays therefore processed exactly the live bytes, and OFF's and ON's windows are different audio.

| Window | Digest |
|---|---|
| pos_02 OFF 26940–37920 | `6a1becc840c06639` |
| pos_02 ON 27060–38040 | `7abd15c4243ed524` |
| pos_01 OFF 17460–28440 | `9f9ef62aeff2f1d6` |
| pos_01 ON 17490–28470 | `ffa6a67f33bc27e0` |
| neg_10 OFF 0–9480 | `00b28d6f6b598cdc` |
| neg_10 OFF re-process / ON 0–9510 | `72e99052dc66438e` |

## 2. Evidence, OFF vs ON

### pos_02 (positive, Malayalam abduction scene)

| Stage | OFF 26940–37920 ms | ON 27060–38040 ms |
|---|---|---|
| Segmentation | drifted boundary (webrtcvad state drift) | one-shot boundary; +120 ms at both edges |
| Audio passed to both STTs | `6a1b…` | `7abd…` (different) |
| Whisper, same bytes repeated | **identical 12/12** (2 live + 5 v1 + 5 v2): "Help! Help! Help! Help! I can't believe it! I can't believe it! Please! Please! I can't believe it!"; T = 0.0, log-prob −0.727 | **text differs between runs** (12/12); T = 0.2–1.0 on every run; every run begins "Help! Help! … Please" |
| STT confidence gate (T > 0 or log-prob < −1.0) | not suspect 12/12 | **suspect 12/12** |
| Parakeet | empty text on every run | empty text on every run |
| UDK decision | sentence **UDK_01 exact 0.65** | text match **vetoed by the STT-confidence guardrail** |
| Intent | not called: needs text from both STTs | not called |
| BEATs | fired (peak 0.2375; corroboration 0.36) | fired (peak 0.2916; corroboration 0.40) |
| Final | **TRIGGER_ALL UDK_01** (live 2/2, v2 5/5) | **TRIGGER_VERIFY acoustic_scream** (live 2/2, v2 5/5) |

**Matcher separated from STT.** The real `UDKEngine.decide_all` was run locally on the observed transcripts. MiniLM is
absent locally, so the comparison is local against local:
- ON's transcripts with the suspect flag off give the same decisions as OFF's transcript, including UDK_01 exact
  TRIGGER_ALL.
- OFF's transcript with the flag on is vetoed like ON's.

The difference arises in Whisper's decoding confidence on different audio, and takes effect at the guardrail after
matching.

**Boundary sweep** (v2, live path, 3 repeats per position; the flag was identical across repeats at every position):

| Moved edge | Confident → TRIGGER_ALL UDK_01 | Suspect → acoustic TRIGGER_VERIFY |
|---|---|---|
| Both edges, start 26880–27120 | 26910, **26940 (OFF)**, 27000 (**3 / 9**) | 26880, 26970, 27030, **27060 (ON)**, 27090, 27120 (**6 / 9**) |
| Start only, 26940–27060 (end 37920) | 26940, 27000 | 26970, 27030, 27060 |
| End only, 37920–38040 (start 26940) | all 5 | none |

- The **start** edge decides the outcome; the end edge does not.
- The outcome **alternates** with 30 ms steps. It is not a trend in one direction.
- Every position alerts: TRIGGER_ALL or TRIGGER_VERIFY.

### pos_01 (positive, Urdu/Hindi)

| Stage | OFF 17460–28440 ms | ON 17490–28470 ms |
|---|---|---|
| Segmentation | drifted boundary | one-shot boundary; +30 ms at both edges |
| Audio | `9f9e…` | `ffa6…` (different) |
| Whisper | text differs between runs, suspect on every run (T 0.4–1.0), text vetoed | same |
| Parakeet, same bytes repeated | **identical 9/9**: "To my hard hook and I hard. I can get out of it." | **identical 9/9**: "To my yard, who can I hard? I can let out with it." |
| Either-STT decision | **UDK_20 semantic 0.671** (whole segment, verify-by-default) | sentence **UDK_10 semantic 0.744** |
| Intent | not called: the two STTs disagree | not called |
| BEATs | not fired | not fired |
| Final | **TRIGGER_VERIFY UDK_20** (live 2/2, v2 5/5) | **TRIGGER_VERIFY UDK_10** (live 2/2, v2 5/5) |

**Sweep** (both edges, start 17400–17550):
- **TRIGGER_VERIFY at all 6 positions.**
- The UDK is UDK_20 at 5 positions and UDK_10 only at ON's position (17490).
- Whisper was confident at the outer positions (17400, 17550) and suspect in between. The tier never changed.

### neg_10 (negative, English podcast)

| Stage | OFF | ON |
|---|---|---|
| Segments | 0–9480 at stream time 9.6 s, then **0–9510 again at 14.7 s** | 0–9510 once, at 9.6 s |
| Whisper (identical on every repeat, T = 0.0) | "People don't have discipline, and the minute you use the word discipline, they feel, oh, okay, something is going to be **taken away from me**. So I don't know why there's this whole misconception." | same text |
| Parakeet (identical on every repeat) | same sentence, with "Yeah" and "Negative" inserted | same |
| UDK decision | **UDK_03 "Get away from me" fuzzy 0.7875**, the lexical overlap "…away from me" → TRIGGER_VERIFY | same |
| Intent | p(distress) 0.84224 → no veto (vetoes below 0.02) | same |
| BEATs | not fired | not fired |
| State | the second pass lies inside the 15 s repeat window → **TRIGGER_ALL, repeated** | processed once |
| Live `journey.events` | VERIFY + TRIGGER_ALL UDK_03 (v2 sequence replay identical) | VERIFY UDK_03 (v2 identical) |

This is a real live false alarm in both modes. It first becomes an alert at the **fuzzy matcher**: "taken away from me"
scores 0.7875 against "Get away from me". Intent does not remove it, because the model scores the sentence 0.84.

## 3. Root cause per case

| Case | Primary cause | Where the difference begins | Segmentation | STT | Matcher | Intent | Acoustic | State | Harness |
|---|---|---|---|---|---|---|---|---|---|
| pos_02 | **`vad_boundary_sensitivity`** | Whisper decoding confidence on different audio, applied at the confidence guardrail | differs (+120 ms) | differs: confident vs suspect | same given the same flag | not involved | both fired | no | none |
| pos_01 | **`vad_boundary_sensitivity`** | Parakeet mis-transcribes different audio differently | differs (+30 ms) | Parakeet differs (deterministic) | different semantic UDK | not involved | none | no | none |
| neg_10 | **`state/timing_difference`** | OFF re-processes the utterance inside the repeat window | OFF processes twice | identical | identical | identical | none | OFF escalates | none |

## 4. Safety relevance

| Case | Relevance |
|---|---|
| pos_02 | **Tier.** TRIGGER_ALL with UDK_01 (OFF) vs TRIGGER_VERIFY acoustic (ON) on a true positive; an alert in both. **Not ON-specific:** at the same audio, 30 ms start shifts alternate between the two outcomes, and ON's is the more common. |
| pos_01 | **Not safety-relevant.** The same tier (VERIFY) at every boundary position; only the UDK identity recorded in the event differs, because of a non-English mis-transcription. |
| neg_10 | **In ON's favour.** ON removes a false TRIGGER_ALL; the VERIFY-level false alarm remains in both modes. |

**Separate risk, pre-existing and independent of the cache:**
- Whether a real "Help! Help!" becomes TRIGGER_ALL or TRIGGER_VERIFY here depends on 30 ms of segment-start position,
  because Whisper's temperature fallback trips the STT confidence gate.
- Any segmentation, including OFF's drifting one, samples this at random.
- It is outside this task's scope, and no gate or threshold was changed.

## 5. Is a genuine positive detection lost with ON?

**No.**
- Every utterance OFF alerted on is alerted by ON (126 benchmark rows).
- pos_02 keeps an alert at every boundary position swept.
- The pos_02 tier difference is boundary sensitivity, and the ON outcome is the majority outcome at that audio.

## 6. Is a genuine false alert introduced by ON?

**No.** ON raised no alert or TRIGGER_ALL that OFF lacked, and it removes neg_10's false TRIGGER_ALL.

## 7. Nondeterminism (identical bytes, identical model and configuration)

The three cases the brief asks to keep apart:
1. **Different input audio:** every OFF-vs-ON pair (digests differ). Not counted as nondeterminism.
2. **Same input, different model output:**
   - Whisper varies between runs on identical bytes **only when it falls back to temperature sampling**: pos_02 ON,
     pos_01 both windows, and the suspect sweep positions.
   - At T = 0 it was identical every time: pos_02 OFF 12/12; neg_10 both windows; the confident sweep positions.
   - Parakeet was identical on every repeat of every window.
   - **Alerts were identical on every repeat** in all exact runs and at every sweep position. Text varied, but the gate
     flag and the decision did not.
3. **Same model output, different downstream decision:**
   - neg_10: identical STT text, but OFF's second pass is escalated by repeat state;
   - pos_02 in the local engine replay: the same text decides differently only through the suspect flag.

## 8. Harness corrections

| Defect | Effect | Fix |
|---|---|---|
| v1 scored transcripts with the whole-text matcher, not the live per-sentence engine | Reported "no UDK" on pos_02's OFF window, where the live run emitted an exact UDK_01 sentence match | v2 replays windows through the real `api._run_incremental_detection` |
| v1 sweep recorded neither Whisper metadata nor the suspect flag | Could not measure boundary sensitivity | v2 records temperature, suspect flag, UDKs and alerts per run |
| v1 did not record the audio digest | "Same input" unproven | v2 records it; it matched the live digests in every repeat |
| Credential safeguard | The token was already passed via the environment only | Commands redacted before logging; every text artefact scrubbed before zipping. The v2 run reported "0 file(s) redacted", and all saved results scan clean. |

## 9. Focused regression tests (`udk_shadow/test_e2e_investigate.py`, 14 checks)

- **replay == live:** transcripts, suspect flags, decisions, alerts, events and audio digests.
- **The v1 whole-text bug:** reproduced, and the v2 live-path capture of UDK_01 checked.
- **The pos_02 pattern:** confident → TRIGGER_ALL; suspect → vetoed, acoustic VERIFY.
- **The neg_10 pattern:** repeat-window escalation, reproduced by sequence replay.
- **Other checks:** repeat identity on identical bytes; sweep geometry.
- **Credential redaction:** the token is never on a command line and never in a log.

## 10. Conclusion: `RESOLVED_SAFE_FOR_NEXT_CONTROLLED_TEST`

**Resolved:**
- pos_01: `vad_boundary_sensitivity`, same tier at every position.
- neg_10: `state/timing_difference`; a pre-existing fuzzy-matcher false alarm; ON removes the TRIGGER_ALL escalation.
- pos_02: `vad_boundary_sensitivity` through the STT confidence gate. The outcome alternates with 30 ms start shifts,
  and ON's result is the majority one.

**Not claimed:** a production go/no-go, or real-world rates. Only 3 recordings were investigated, all calibration
material.

**Carry into the controlled test:** measure how often segment-start position flips the confidence gate across more
positives. It is a pre-existing risk, not a VAD-cache one.
