# Phase 2A — pending decisions

Open questions are recorded here rather than decided in code. Each one is taken up at the stage that needs it.

## Open project decision: provenance vocabulary (Phase 1 vs Phase 2A)

**D-PROV-1 — OPEN, needs the project owner.**

- **Phase 1 §15 ("Provenance labels")** says: "Every safety/context item carries exactly one `provenance` value". It then lists:

  | Value | Meaning | Planned in this corpus? |
  |---|---|---|
  | `acted_scripted` | Actors read a written scene | Yes, main source of pairs |
  | `acted_semi_scripted` | Actors given a situation and target phrase, words improvised | Yes |
  | `spontaneous_safe` | Unscripted real harmless speech | Yes, D_spontaneous_safe |
  | `real_incident` | Recording of an actual dangerous event | No; only with separate legal/ethics approval and consent |
  | `unknown` | Provenance cannot be established (e.g. mined media) | Evaluation/reference only |

- **Phase 2A §3** gives the provenance enum as `read, extempore, conversational, acted_scripted, acted_semi_scripted, spontaneous_safe, unknown`. It says the manifest "extends the Phase 1 §15 annotation schema; safety fields (pair_id, problem_type, roles) carry over unchanged for collected data". Provenance is not in that carry-over list.

What agrees and what does not:

1. **Extension (not a conflict).** 2A adds `read`, `extempore` and `conversational`, which describe public ASR sources (e.g. IndicVoices' read/extempore/conversational split, Phase 1 §3). Phase 1's list covers only collected safety/context items.
2. **Omission (conflict).** 2A omits `real_incident`, which Phase 1 defines. Phase 1 plans no such data, but real emergency audio is already in scope elsewhere: the 911 recordings are "Real calls" (Phase 1 §11), and the 911 sealed half is to enter `D_final_test` (Phase 1 §18, §21). If 911 audio ever becomes a manifest row, 2A has no value for it except `unknown`.
3. **Usage rule not in 2A (gap).** Phase 1 marks `unknown` as "Evaluation/reference only". 2A §3 attaches no use restriction to any provenance value, and S1 does not enforce one.

**Current implementation (conservative):** the Phase 2A §3 enum exactly as written. `real_incident` is not in the schema, and a test records its rejection as an open conflict, not a decision. No provenance-to-use-restriction rule is enforced.

**Binding rules while D-PROV-1 is open (owner decision, S1 review 3):**

1. `real_incident` is a Phase 1 provenance concept that is **unresolved** against the Phase 2A manifest enum. Its absence from the schema is not a decision that such data is out of scope.
2. A recording **known** to be a real incident must **not** be relabelled as `unknown` (or any other value) just to pass validation. `unknown` means "provenance cannot be established" (Phase 1 §15). A known real incident is the opposite case.
3. `unknown` is **not** equivalent to `real_incident` and must never be read as meaning it, in either direction, by any consumer, metric or report.
4. If known real-incident data becomes available before D-PROV-1 is resolved, it stays out of all training and benchmark execution. It cannot be written as a valid manifest row without breaking rule 2, so it is held **outside** the manifest (no row, and therefore never selected by `eligibility.select_eligible`) until the representation is decided. Once decided, it enters with `use_restriction=blocked` until its licence, legal and ethics status (Phase 1 §15: "only with separate legal/ethics approval and consent") is cleared.
5. D-PROV-1 stays an explicit unresolved project decision. Nothing in `asr_bench/` resolves it.

**Options for the owner:** (a) add `real_incident` to the 2A enum; (b) represent such audio some other explicit way (not `unknown`); (c) also make `unknown` provenance imply `use_restriction` ≠ `train_ok`, per Phase 1's "Evaluation/reference only".

## From the Phase 2A plan (deferred by the project owner)

| ID | Question | Needed by |
|---|---|---|
| Q4 | Should the frozen 96ea038 engines receive whole utterances, or go through the frozen VAD first? This affects WER. | S7 (runner) |
| Q5 | Which candidate ASR models are benchmarked? None is selected. | S7 |
| Q6 | Which romanisation/transliteration scheme produces `transcript_romanised` and "transliteration-equivalent" matches when a source does not supply them? | S4, S5 |
| Q7 | Who writes the per-language negator, content-word and safety-keyword lists? They are fixed on dev (Phase 2A §6.3). | S5 |
| Q8 | How is the language of each ASR output token determined, for the language-switch error rate? | S5 |
| Q9 | How are numbers converted to words for Hindi and Telugu in the normaliser? | S4 |
| Q10 | **Resolved by owner (S2):** `audio_sha256` = SHA-256 of the exact source audio file bytes, never decoded PCM. Near-duplicate / content fingerprinting (Phase 1 §19) is not in S2; whether and when it is built stays open. | S2 (done); fingerprinting: later |
| Q11 | Which dependencies may later stages add (e.g. an audio reader for metadata)? S1 adds none. | S2 onward |

## Readings of Phase 2A §3 in S1 (owner review 1 applied)

| ID | §3 text | What S1 does | Status |
|---|---|---|---|
| P-S1-1 | "session_id / recording_id" | Two separate nullable fields; both are checked for cross-split leakage. | Confirmed by owner |
| P-S1-2 | speaker_id "Namespaced by source" | **Adapter contract:** adapters must write globally namespaced IDs, e.g. `<source>:<source_speaker_id>`. The validator requires no prefix format and compares IDs as opaque strings, so un-namespaced IDs from two sources are reported as one speaker (demonstrated in tests). The utt_id prefix is not required to equal `source_dataset`. | Confirmed by owner |
| P-S1-3 | overlap_spans: "list" | The element format is not given, so only "non-empty list when overlap is true" is checked. | Open |
| P-S1-4 | english_word_script "Yes for Indic sources" | No language list lives in the schema. "Indic" is benchmark configuration, passed as `indic_languages` / `--indic-languages hi,te`. Without it, english_word_script is nullable on every row, i.e. the §3 requirement is not enforced until the configuration exists. | Changed per owner |
| P-S1-5 | snr_db, clipping_ratio "Estimated, method recorded" | No field for the method is named, so none is required. | Open |
| P-S1-6 | use_restriction `blocked` | See "Blocked data" below. | Changed per owner |
| P-S1-7 | §7 "no null speaker_id in speaker-disjoint splits; no speaker, audio hash or session in two splits" | Null speaker_id is allowed only in `eval_only`. Cross-split checks cover all five splits, `eval_only` and blocked inventory rows included. | Confirmed by owner |
| P-S1-8 | cmi "number if tags exist" | Any finite number; no scale (0–1 / 0–100) or sign assumed, and nothing normalised. **The scale and definition must be recorded with the source or benchmark configuration.** §3 has no field for it, so S1 cannot check it; it is a limitation until S2/S9 adapters record it. | Changed per owner |
| P-S1-9 | keyword_spans "If safety_tags" | Required (possibly `[]`) whenever `safety_tags` is non-empty. | Open |
| P-S1-10 | transcript_ref "Required" | A string, never null. `""` is allowed for no-speech segments (§5 hallucination rate). | Open |
| P-S1-11 | licence / use_restriction "from P1 §20" | S1 checks presence, the enum and split consistency. **Source-registry stage:** `adapters.build_row` now requires `SourceInfo.licence` and `use_restriction` to equal the entry in `source_registry.json`, whose values are copied from 2A §2 / P1 §20. The copied values themselves are not a legal conclusion. | Enforced (values: see R-2) |

## Blocked data (P-S1-6, revised)

The manifest is also the inventory and provenance record, so a blocked source may appear in it. Three questions are kept apart:

| Question | Answered by | Blocked row |
|---|---|---|
| a) Does the manifest contain the source? | `schema.validate_row` / `validate.py` | Yes: a valid row, with `licence` and `use_restriction=blocked` kept |
| b) Is the source legally usable? | `eligibility.legally_usable` (`train_ok` or `eval_only`) | No |
| c) Is the row eligible for a given split? | `eligibility.eligible_for` / `select_eligible`, which every benchmark or training consumer must use | Never, for any split |

**Schema limitation (kept as is, owner decision, S1 review 3):** §3 requires `split`, and its enum has no "unassigned" or "inventory" value. `eval_only` is therefore used as the inventory split for blocked rows, and the validator rejects blocked rows in `train`, `dev`, `test` or `final_test`. For a blocked row, `split="eval_only"` means only "not in an executed split". It does not mean evaluable: `use_restriction=blocked` always wins, and `eligibility.eligible_for` rejects the row for every split, `eval_only` included. A cleaner representation (a null split for inventory rows, or a new enum value) would be a Phase 2A schema change for the owner. Blocked rows stay in the manifest as inventory, and blocked rows are never train- or benchmark-eligible.

## Decisions exposed by S2 (audio metadata + adapter contract)

| ID | Question | What S2 does now | Status |
|---|---|---|---|
| P-S2-1 | For compressed formats (MP3, M4A/AAC, OGG, FLAC), what is `duration_s`? The decoded sample count, which can include encoder priming or padding that the decoder emits, or the container's declared duration? | Decoded samples / sample rate, via PyAV, recorded as `reader="pyav-decoded"`. WAV is exact from the header (`riff-header`). | Open |
| P-S2-2 | Which `audio_path` convention goes in the manifest: relative to a data root, or absolute? Where is the root recorded? | **Resolved by owner (S3):** relative to a source root supplied at run time. `audio_path` is NOT frozen content, and `audio_sha256` IS, so a freeze stays valid when files move with identical bytes. Optional on-disk verification takes a source→root mapping (`freeze.verify_audio`, `--audio-root src=dir`). | Resolved |
| P-S2-3 | Precedence of per-utterance licence/use_restriction over the source-level values (for sources licensed per item, e.g. FSD50K). | **Resolved by owner (S3):** monotone, `train_ok` < `eval_only` < `blocked`. The source value is the ceiling: an utterance value may be equal or stricter, never more relaxed, and blocked always stays blocked (`adapters.build_row`). Source licence values are still copied from Phase 1 §20 by the adapter's author, unchecked by code. | Resolved |
| P-S2-4 | May PyAV (`av`) be a declared dependency of `asr_bench`? (part of Q11) | Optional: used if importable (it is already present wherever faster-whisper is installed), and never added to any requirements file. Without it only WAV can be read, and other formats raise `UnsupportedAudioFormat`. PyAV tests print SKIP where it is absent. | Open |
| P-S2-5 | Which WAV variants are supported? | PCM, IEEE float, A-law, mu-law, and EXTENSIBLE of those. RF64 is rejected. A codec inside a WAV container (e.g. ADPCM) goes to PyAV or is rejected. A WAV whose data size runs past the end of the file (truncated, or a streaming placeholder size) is rejected as corrupt. | Open |
| P-S2-6 | Containers with more than one audio stream. | Rejected (no stream is picked). A container with video plus exactly one audio stream (e.g. the Phase 0 `.mp4` files) is read from its audio stream. | Open |
| P-S2-7 | How do source-provided splits (e.g. MUCS given splits, the Vaani Noise held-back eval) reach the manifest? | The adapter carries no split. The caller passes `split` / `split_for` to `build_row` / `build_rows`. Split assignment belongs to S3. | Open (S3) |
| P-S2-8 | Zero-length audio. | Reported as it is (0.0 s, never padded). The row is then refused by the schema (`duration_s > 0`). | Open |
| P-S2-9 | `utt_id` prefix. | `build_row` composes `utt_id` as `<source_dataset>:<source_utt_id>` (§3 "`<source>:<source_id>`"), and `source_dataset` may not contain `:`. The generic S1 validator still does not require this (P-S1-2). | Open |

S2 leaves untouched: D-PROV-1, Q4, Q5, Q6, Q7, Q8, Q9 and Q11 (except its PyAV part, recorded as P-S2-4).

## S3 (split assignment, leakage, final-test freeze): owner decisions

| ID | Decision | Implemented as |
|---|---|---|
| D-S3-1 | Toy/example ratios train 0.70 / dev 0.10 / test 0.10 / final_test 0.10, as configuration only. | `examples/toy_split_config.json`. The splitter has no default ratios: every source needs an explicit policy, and all four ratios must be given. |
| D-S3-2 | Example salt `udk-phase2a-v1`, recorded in every split artifact. | Recorded in the split report and the freeze. A different salt gives a different split and config digest. |
| D-S3-3 | A group containing an eval_only-restricted row never enters train. It is assigned deterministically among its permitted splits, without rehashing, and reported. | The hashed split is kept if permitted. If it is train, the group's relative position inside the train bucket is mapped onto the permitted splits (renormalised ratios). Reported in `constrained_groups`. A source that can only produce train (ratios, or `fixed` to train) is a plan error. |
| D-S3-4 | A group containing any blocked row goes entirely to eval_only inventory, never eligible, with the reason reported. | `eval_only_inventory_groups`. |
| D-S3-5 | Exact `audio_sha256` shared by different groups or splits is an error; no automatic merging. | `splits.leakage_report`: an error for different groups (even in the same split). The S1 validator already errors across splits. Audio never forms groups. |
| D-S3-6 | Workflow: complete data → validate → leakage check → assign → freeze → evaluate. The frozen final test cannot silently change; a revision needs a new, versioned freeze. | A freeze file is never overwritten. `assign_splits(..., freeze=...)` fails on any final_test membership change or a different config digest. `verify_freeze` reports ADDED / REMOVED / MOVED / AUDIO / audio-metadata / REFERENCE / METADATA changes and an edited artifact. |
| D-S3-7 | Freeze = JSON of IDs, hashes and config digest. No real freeze committed yet; toy freezes only in temporary locations. | `freeze.py` writes only to the path given. Tests use temp dirs. |
| D-S3-8 | Only `hash` and `fixed` source policies; no `given`. | `given` is rejected by the config validator. |
| D-S3-9 | Exact duplicate transcripts across splits are warnings. Normalised detection waits for S4. | Warning in `leakage_report`. |

Grouping rule (owner): transitive union-find over non-null `speaker_id`, `session_id` and `recording_id` (typed, so a session ID never links to an identical speaker-ID string). The group key is the smallest speaker_id, else the smallest session_id, else the smallest recording_id. No IDs are invented, and `audio_sha256` never groups.

### Open, surfaced while implementing S3

| ID | Question | What S3 does now |
|---|---|---|
| O-S3-1 | Null-identity policy inside a group. | A group with any null-`speaker_id` row goes entirely to eval_only (§3: such rows are excluded from speaker-disjoint splits, and splitting the group would put its session in two splits). One speakerless utterance therefore moves its whole session and speaker to eval_only. This is reported. A row with no identifier at all is its own eval_only item with no key. |
| O-S3-2 | The split config carries no licence information. | Contradictions between a source's policy and its rows' restrictions are caught per group (plan errors or constrained groups), not by rejecting the config up front. |
| O-S3-3 | A group spanning two sources (only possible with un-namespaced IDs). | Plan error: fix the adapter. |
| O-S3-4 | Source-disjoint judgement per candidate, and the "pretrained on this source" flag (2A §6.1). | Needs the candidate list (Q5): S7. S3 reports, per `language_primary`, which test/final_test sources have no train/dev rows. Mapping rows to language slices is S6 configuration. |
| O-S3-5 | Very large groups (multi-speaker sessions such as AMI meetings, DISPLACE, collected scenes) can pull a whole source into one split. | Reported (`largest_group_rows`, per-split groups). Nothing is split just to meet a ratio. |
| O-S3-6 | Phase 0 sealed sets entering `D_final_test` (Phase 1 §18). | Not ASR manifest rows yet; out of S3. |
| O-S3-7 | Where a real freeze artifact and its digest are kept, once real data exists. | Open (D-S3-7 covers only "not now"). |

Still open and unchanged by S3: D-PROV-1, Q4–Q9, Q11, P-S2-1, P-S2-4 to P-S2-9, P-S1-3/5/9/10/11.

## Source registry + licence gate

`source_registry.json` (v1) and `registry.py`. Every source's `acquisition_authorised` is `false` until the owner sets it; `build_row` / `build_rows` refuse unregistered or unauthorised sources, and any `SourceInfo` that disagrees with the registry.

| ID | Choice made only because the registry needs a value | Status |
|---|---|---|
| R-1 | Source IDs (namespace prefixes) such as `indicvoices`, `mucs2021_hien` (2A §3's own example). Renaming later changes every namespaced ID. | Kept by owner review (confirm before first ingestion) |
| R-2 | `use_restriction` per source taken from the 2A readiness column: Blocked/Collect → `blocked`; Eval, Eval-only, "Eval now; Train after legal review" → `eval_only`; "Train + Eval" → `train_ok` (Kathbath, AMI, FSD50K). **Resolved (registry v2):** Kathbath and AMI are kept as `train_ok`. FSD50K stays `train_ok` as a *ceiling* only, and is marked `per_item_restriction_required`: `build_row` refuses any clip without its own `licence` + `use_restriction`, and the monotone rule (P-S2-3) keeps every clip at or below the ceiling. CC-BY-NC and Sampling+ clips must be recorded as `eval_only` by the adapter. | Resolved |
| R-3 | "Conditions" licences (CC BY attribution) are recorded as text only. The actual attribution statements and licence-file references must come from each source's own licence/card before that source is authorised (N-9). | **Open: needs evidence** |
| R-4 | **Resolved (registry v2):** split into `phase0_prepped`, `phase0_real_recordings`, `phase0_youtube_dev` and `phase0_telugu_own` (family `phase0`, all `eval_only`), each with its own documented licence status. The sealed YouTube half is not registered. | Resolved |
| R-5 | Vaani Noise Event keeps its own family for now. NEEDS EXTERNAL SOURCE EVIDENCE: the Vaani Noise Event dataset card (cited in Phase 1 §6) must state whether its audio is cut from Vaani recordings (and which release) and whether its speaker/utterance IDs map to Vaani's. If so, merge into the `vaani` family. | **Open: needs evidence** |
| R-6 | FSD50K's documented scope "noise mixes only" (2A §2) cannot be expressed by `use_restriction`. Nothing stops an FSD50K `train_ok` clip being used directly as a training utterance rather than as mix noise. | Open (new) |

Gates checked without data: registered, acquisition authorised, legally usable per documents, train permitted per documents, adapter may run. The manifest / train / evaluation / final_test gates need audio and remain S1–S3 checks.

## Recorded from the real-data readiness review (open, not resolved)

N-1 which file is the source audio when 2A converts formats (Kathbath m4a→wav, Gram Vaani mp3→16 kHz) · N-2 blocked sources cannot be manifest rows before download; the registry now holds them · N-3 the public-family rule (P1 §19) is recorded as `family` but not enforced on splits, and exact hashes miss resampled copies · N-4 `phase0_prepped` has no reference transcripts and an unrecoverable crowd seed · N-5 Kathbath Telugu speaker count vs ≥ 50 · N-6 the final freeze waits for collection (D-S3-6); until then dev only · N-7 CMI threshold / slice definitions · N-8 English-script sample-check procedure · N-9 where attribution obligations are recorded · N-10 schema extension for SAFE/DANGER context structure.

## Benchmark execution (S4–S9): provisional choices, recorded, not decided

Every report carries `provisional_config: true` and the open-decision list until these are fixed on dev (§6.3).

| ID | Item | Provisional behaviour |
|---|---|---|
| Q4 | Input unit | `--input-unit` is required (`utterance` or `vad`, the frozen `vad.VAD`); no default. |
| Q5 | Candidates | None chosen. The runner accepts the two frozen Phase 0 engines or `module:factory`. |
| Q6 | Romaniser | None. Romanised metrics and transliteration-equivalent matches are reported "unavailable". English-word preservation and keyword recall are exact-match only. |
| Q7 | Word lists | Negators are only the 2A §5 examples, written in Latin script (not, don't, nahi, mat, ledu, vaddu). Native-script negators (e.g. नहीं) are NOT matched yet. No stop-word lists, so every word is a "content word" for integrity (strict). The false-insertion keyword list defaults to the manifest's keyword spans. |
| Q8 | Output-token language | "script" method: the script of a word gives its language. A pair is judged only when the reference word's own script identifies its tagged language, so romanised Hindi reference words are counted as *undetermined*, not as switches. |
| Q9 | Numbers | English digit strings become words. Indic digits are kept and counted per report. |
| N-7 | Slices | `slice_by` = language_primary × code-switched; minimums per 2A §4 in `slice_minimums`. |
| M-1 | Robustness subsets | Derived from row metadata (overlap, pocket/bag, far_field, phone_call, traffic, crowd, snr_db ≤ 0, clipping_ratio > 0, else quiet/close = clean); real and synthetic are always reported separately. |
| M-2 | Metric definitions | CER over normalised characters including spaces. Hallucination = output words per hour on no-speech rows (`transcript_ref` ""), plus insertion runs ≥ 3 per hour of speech. Negation flip = a negator on one side only (utterance level). False insertion counts keyword occurrences in the output beyond those in the reference, on rows without keyword spans, per hour of that audio. |
| M-3 | Phone-band recipe | 300–3,400 Hz band-limit only. The codec step of 2A §4 is not applied (no codec chosen). |
| P-S1-3 | overlap_spans elements | The overlap recipe writes `{"start_s", "end_s"}` elements (the tokens/keyword_spans convention). Still open for real data. |
| M-4 | Latency | RTF measured per utterance on the running machine, and `--hardware-class` recorded as declared, never verified. Production-class (c7i.2xlarge) numbers require running there (2A §8.7). |

## Phase 2A status

Infrastructure for every Phase 2A step is implemented and tested on toy fixtures. **No real benchmark result exists.** No registered source has `acquisition_authorised = true`, and the frozen engines were not run on real data.

Closure condition (2A §7): the manifest must be populated for every §4 slice (or each slice marked unavailable with a reason), the final test frozen, the frozen Phase 0 engines scored on it, and CPU latency measured. That requires at least one owner-authorised real source, and, for the safety-critical set and real pocket/crowd/overlap subsets, the Phase 1 collection.

## Kathbath (first real source)

| ID | Item | Status |
|---|---|---|
| N-1 (Kathbath) | Source audio = the ORIGINAL `.m4a`; `audio_sha256` = its exact bytes. | Resolved by owner |
| P-S2-1 (Kathbath) | Duration = decoded samples / rate (PyAV). AAC priming/padding samples the decoder emits are included. | Resolved by owner |
| P-S2-4 (Kathbath) | PyAV must be importable wherever Kathbath is ingested (m4a). It is still not added to any requirements file. | Required in the ingestion environment |
| P-S2-7 (Kathbath) | Kathbath's own given splits are NOT used; the deterministic hash split applies. | Resolved by owner |
| R-1 (Kathbath) | Source id `kathbath`; speaker IDs `kathbath:<speaker from file name>`. | Kept |
| K-1 | The package layout (directory layout, transcript file format and fields, speaker pattern in file names, folder → language names, release/version) was NOT inspected: huggingface.co is denied by this environment's network policy. `configs/kathbath_layout.TEMPLATE.json` must be filled from the real package; the adapter refuses nulls. | **Blocker** |
| K-2 | `is_code_switched = false`, `languages_present = [language]`: Kathbath is not listed as a code-switched source (Phase 1 §7–§8). `english_word_script = "unknown"` (not documented). | Recorded |
| K-3 | Kathbath split ratios 0.70 / 0.10 / 0.10 / 0.10 and salt `udk-phase2a-v1` (`configs/phase2a_split_config.json`): the documented toy values, used because the split config requires concrete ratios. | Provisional |
| K-4 | Access gate: `acquisition_authorised` stays false until the owner accepts the Kathbath gate with their own account and the package is on disk. | **Blocker** |
| K-5 | `session_id` / `recording_id` are null (none documented), so grouping is by speaker only. | Recorded |

## Phase 2B (defined portion: §7 evidence, transcript representation, D_asr_errors)

No Phase 2B specification document exists in the repo. Only the parts defined by Phase 1 §15–§18 and Phase 2A §7/§9 are implemented.

| ID | Item | Status |
|---|---|---|
| M-5 | 2A §7 "beat" / "not worse": PASS/FAIL uses point estimates. Whether the paired 95% CI excludes zero is reported next to each result. Whether significance is required is open. "Beat" is strict (a tie is FAIL). | Open |
| M-6 | 2A §7 "fits production-class CPU": no RTF or memory limit is defined, so the latency rule is UNAVAILABLE unless the run metadata shows verified production-class CPU and a `cpu_rtf_max` is configured. | Open |
| M-7 | Code-switched slices for the §7 rule must be named in the evidence config (`cs_slices`, e.g. `hi\|cs`, `te\|cs`); follows N-7. | Open |
| M-8 | The candidate licence record (model + training-data licences, `commercially_usable`, evidence) must be supplied per candidate; the evidence tool records it and does not verify it. | Open (per candidate) |
| M-9 | D_asr_errors: `name_entity` errors are UNAVAILABLE (no entity annotation). `avg_logprob` / `temperature` are null (the runner does not record them). Word-boundary errors come only from alignment merges/splits. | Recorded |
| Q7 (seen in tests) | The shipped negator list is Latin-only, so Devanagari negation (e.g. नहीं) yields negation evidence UNAVAILABLE. | Open (unchanged) |
| P2B-1 | The ASR-representation decision (mixed-script, romanised or both) needs real §7 evidence, and none exists (no authorised data, frozen engines not run). | **Blocked** |
| P2B-2 | Context / speaker-attribution evaluation (Phase 1 §18). | **Blocked** by N-10 and the Phase 1 collection acceptance criteria |
| P2B-3 | Any Phase 2B work beyond the Phase 1 / 2A-defined portion needs a Phase 2B specification. | **Blocked** (no document) |
