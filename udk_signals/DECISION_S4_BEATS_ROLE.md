# S-4 decision note: the role of the existing BEATs acoustic signals

Status: **OPEN. This note makes no recommendation.** It sets out options A–D for the owner to decide between.

Sources used:
- Phase 0 §1, §8, §9, §11, §12, §14
- Phase 1 §2 (F9–F11, rows AA–AH), §6 Stream D, §15, §19
- Live code at 96ea038: `api.py` `_run_incremental_detection`, `scream_trigger.py`, `udk_engine.py` `decide`, `beats_distress_detector.py`
- `udk_signals/fusion.py`

Toy-fixture results are not used as evidence anywhere in this note.

## 0. Current live behaviour (96ea038, both paths ON in prod)

Both paths use the same model instance: BEATs iter3 AS2M cpt1 (Hugging Face revision unpinned). It is loaded if either flag is set.

| | P1: scream-alone trigger | P2: 9-class corroboration |
|---|---|---|
| Flag | `UDK_ENABLE_SCREAM_TRIGGER=1` | `UDK_ENABLE_SCREAM_DETECTION=1` |
| Rule | Screaming / Crying, sobbing / Whimper / Children shouting. Max prob ≥ 0.10 in 2 consecutive 2 s windows (0.5 s hop). | Max over 9 vocal classes, whole VAD segment, ≥ 0.30 (`DISTRESS_SCORE_THRESHOLD`) |
| Where | `api.py`: checked *before* the empty-transcript skip, so it works with no words. It fires only if **no alert is left** after both engines, the intent veto and the separation retry. | `udk_engine.decide`: looked at only *after* a text/KWS match has reached TRIGGER_VERIFY. Passed to both engines' decisions. |
| Effect | `TRIGGER_VERIFY`, `udk=None`, `layer=acoustic_scream`. It cannot be vetoed (Phase 0 §12; Phase 3 H1). | Lifts any `TRIGGER_VERIFY` (confidence 0.60–0.85, or a verify-by-default phrase) to `TRIGGER_ALL`. It never creates an alert. The intent veto runs afterwards, so it can still silence a lifted standard-phrase alert. |
| Coverage limit | Audio outside VAD segments is never scored; segments under 200 ms score zero. | Same |

## 1. Phase 0 evidence shared by all options

**False alarms (P1):**
- P1 is the main false-alarm source on unseen audio: 2.4/h on 12 h of sealed real YouTube. Total false alarms are 4.6/h with the scream trigger against 2.2/h for speech alone.
- Dev YouTube (4.6 h, 4-class rule): hard audio 7.3/h (within it, gameplay 18.7/h and festival 1.8/h), conversation 1.8/h, ambient 0. Phase 0 §9 attributes all 10 live-rule dev alerts to one gameplay video.
- Telugu own recordings: 0/h.
- 911 dev calls: 11.9 alert episodes/h, not scored, so true vs false is unknown.
- Calibration clips: cheering, crowd and laughter add 1–3 alerts per ~25 clips each. Sirens: 0.
- `scream_trigger.py` records 3/96 held-out prepped control runs alerting (the "Playful" clip). This was measured on 2026-09-24 with the earlier 9-class trigger rule, before it was narrowed to the live 4 classes.
- The 9-class set *used as a trigger* fired 182 times on the dev YouTube audio (20–77/h), which is why the trigger was narrowed to 4 classes. That rule is not the 0.30 corroboration rule.

**False escalation (P2):** I found no Phase 0 figure that isolates P2's false VERIFY→ALL escalations on real harmless audio. The code comment gives a real-negative ceiling of 0.0138 over 163 segments, but no heated-argument class was tested.

**Missed distress:**
- P1 misses 28 of 57 real distress sounds; the 9-class rule catches 31/57.
- Calibration: screams 11/25, crying 16/25. These used the earlier 9-class trigger rule, not the live 4-class rule.
- Frightened speech scores 0.013–0.022 ("Real fear, in pocket").
- For P2: RAVDESS fear/angry reaches 0/64 at 0.30. This comes from the `beats_distress_detector.py` code comment, not from a Phase 0 table.
- Live vs replayed screams is unresolved (Phase 0 §19 item 4).
- VAD gaps are never analysed.
- Every threshold was picked on the calibration sets (real_recordings plus FSD50K), so those sets are not independent evidence.

**Interaction with UDK alerts:**
- Real distress media (7 clips): scream alone 4/7; with UDKs 6/7. Both used the earlier 9-class trigger rule; there is no live 4-class figure for these clips.
- The prepped (78/84, 26/162) and real_recordings figures **exclude P1**, so live false alarms on those clips could be higher (NOT MEASURED).
- P2 turns verify-by-default phrases into TRIGGER_ALL.

**Interaction with classifier/context decisions:**
- The intent veto can silence a text alert, after which P1 may still fire (Phase 0 §12).
- P1 alerts cannot be vetoed. This is Phase 0 §12, kept as Phase 3 H1.
- Context model v2 silenced cries after attacker speech ("Get away!" 0.998 → 0.000; Phase 0 §11, Phase 1 F9/F10). P1 is the one path that is independent of any text classifier.
- In the Phase 4 contract, P2 can never lift a classifier-only (`context_intent`) alert (G3).

## 2. Options

### A — keep scream-alone VERIFY, drop 9-class corroboration
1. **Kept / removed:** P1 unchanged. P2 is removed, so a VERIFY from text stays VERIFY unless a repeat, a distinct UDK, KWS agreement or confidence ≥ 0.85 escalates it.
2. **Evidence:**
   - False alarms: P1 figures unchanged (2.4/h sealed, 18.7/h gameplay).
   - Misses: 28/57, plus frightened speech.
   - UDK interaction: VERIFY-level UDK alerts that come with a scream no longer escalate. In the 6/7 media figure (earlier 9-class trigger rule plus UDKs), the P2 share is not isolated.
   - Context interaction: unchanged.
3. **Safety consequence:**
   - Wordless screams and cries still get "Are you safe?", with the measured false-alarm cost.
   - Some genuine incidents drop from TRIGGER_ALL to VERIFY, meaning a slower or softer response.
4. **Data required:**
   - Real incidents where a UDK phrase co-occurs with a scream or cry, to measure the escalations lost.
   - Held-out real hard negatives (Phase 1 AE–AH, live vs replayed pairs) for P1's false-alarm rate on unseen Indian audio.
5. **Supported by the Phase 4 contract:** yes. Set `acoustic_alone.enabled=true`, `corroboration.enabled=false`.
6. **Changes:**
   - `udk_signals`: a new config file only (not created).
   - Production (not done): unset `UDK_ENABLE_SCREAM_DETECTION` in deployment. No code change; the detector stays loaded through the trigger flag.

### B — keep 9-class corroboration, drop scream-alone VERIFY
1. **Kept / removed:** P2 unchanged. P1 is removed, so no alert is raised without words, KWS or a match.
2. **Evidence:**
   - False alarms: removes the largest unseen-audio source (2.4/h sealed; 18.7/h gameplay), bringing the sealed total to the speech-only 2.2/h.
   - Misses: every wordless distress sound becomes a miss (P1's 29/57 caught go to 0 without words; the media "scream alone 4/7", measured with the 9-class rule, is lost).
   - Context interaction: removes the only path that is independent of the text classifier, which is the one that covers cries after attacker speech (F9/F10).
   - P2's own false-escalation rate: not measured (see §1).
3. **Safety consequence:**
   - Fewer false alarms.
   - A victim who screams or cries without saying a UDK phrase, or whose words are missed by ASR or masked by overlap, gets no alert.
4. **Data required:**
   - Real distress without UDK words (Phase 1 AA–AD) to quantify the recall given up.
   - Real UDK plus concurrent distress, and UDK plus harmless loud audio (quoted phrases, arguments, games), to measure P2's true and false escalation.
   - A heated-but-safe argument class (the open item in `beats_distress_detector.py`).
5. **Supported by the Phase 4 contract:** yes. Set `acoustic_alone.enabled=false`, `corroboration.enabled=true`. G3 limits lifting to UDK-path alerts.
6. **Changes:**
   - `udk_signals`: a config file only (not created).
   - Production (not done): unset `UDK_ENABLE_SCREAM_TRIGGER`. No code change.

### C — keep both (current live state)
1. **Kept / removed:** Everything in §0 is kept.
2. **Evidence:** all of §1 applies unchanged. This is the configuration behind the 4.6/h sealed total and the 28/57 misses. The media 4/7 and 6/7 and the 11/25 and 16/25 figures predate the 4-class narrowing.
3. **Safety consequence:**
   - Highest acoustic coverage of the four.
   - Carries every measured false-alarm source (media, gameplay, crowds) and the unmeasured P2 escalation risk.
   - Absence of a BEATs signal is still not evidence of safety (the Phase 4 wrapper reports it as UNCERTAIN).
4. **Data required:** everything listed for A and B. In particular, sealed real audio with the scream trigger *included* in the prepped and real_recordings harnesses, which is currently NOT MEASURED.
5. **Supported by the Phase 4 contract:** yes. `configs/production_equivalent.json` is exactly this, and tests exercise it.
6. **Changes:** none.

### D — neither until real-data validation
1. **Kept / removed:** Both P1 and P2 are removed. Decisions become text/KWS only, and the BEATs model need not be loaded.
2. **Evidence:**
   - False alarms: sealed total falls to the speech-only 2.2/h, and the gameplay/media alerts go.
   - Misses: all wordless distress, plus the lost escalations from A.
   - Context interaction: loses the unvetoable acoustic path.
   - Note: Phase 0's headline 78/84 prepped recall does not include P1, so that number would not change, but real-world wordless recall would.
3. **Safety consequence:**
   - A known, measured recall loss (at least the 29/57 real distress sounds P1 catches).
   - This is traded for removing a known false-alarm source until validation exists.
4. **Data required:** the same set as C would be needed later to justify re-enabling either path.
5. **Supported by the Phase 4 contract:** yes. Set both `enabled=false`; the wrapper can still log BEATs evidence in shadow mode without affecting decisions.
6. **Changes:**
   - `udk_signals`: a config file only (not created).
   - Production (not done): unset both flags. No code change.

## 3. Summary (facts only, no ranking)

| | A | B | C (live) | D |
|---|---|---|---|---|
| Alert with no words | yes | no | yes | no |
| Scream lifts VERIFY→ALL | no | yes | yes | no |
| Largest measured false-alarm source (P1) | kept | removed | kept | removed |
| Only classifier-independent path (P1) | kept | removed | kept | removed |
| Phase 4 contract | config | config | config (exists) | config |
| Production change | 1 env flag | 1 env flag | none | 2 env flags |

**Common blocker for any choice beyond "as measured" (Phase 1 Stream D, §15):** real labelled data that is independent of the calibration sets. That means:
- Screams and cries (AA–AC)
- Frightened speech (AD)
- Ordinary shouting and arguing, laughter, cheering, gaming/TV/movie audio in Indian settings (AE–AH)
- Live vs replayed pairs
- Speaker-attributed UDK plus distress-sound incidents

Any threshold choice goes on a dev split, never the final test.

**Parity note for integration (not a choice):** live P1 is evaluated after the intent veto, and live P2 before it. `fuse()` reproduces this only if it is given the *post-veto* linguistic decision.
