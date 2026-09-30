# asr_bench — Phase 2A ASR benchmark infrastructure

This folder is kept separate from the live service. The production baseline is still `main` @ 96ea038, and nothing here is imported by `api.py`.

**Stage S1:** the canonical manifest from Phase 2A §3, its validator, and the row-eligibility rule.
**Stage S2:** audio metadata + SHA-256 from the actual files, and the dataset adapter contract. No real adapters yet.
**Stage S3:** deterministic split assignment, leakage report, and the final-test freeze.
**Source registry + licence gate:** `source_registry.json` (versioned, documented facts only, nothing authorised) and `registry.py`. Adapters refuse sources that are unregistered, unauthorised, or that disagree with the registry. `python -m asr_bench.registry report` shows each source's gates and blockers.

    python -m asr_bench.validate path/to/manifest.jsonl                         # exit 0 valid, 1 invalid, 2 unreadable
    python -m asr_bench.validate path/to/manifest.jsonl --json                  # machine-readable
    python -m asr_bench.validate path/to/manifest.jsonl --indic-languages hi,te # benchmark config: enforce english_word_script
    python asr_bench/test_manifest_schema.py                                    # tests (toy rows only)
    python asr_bench/test_audio_meta_adapters.py                                # S2 tests (audio generated at run time)
    python -m asr_bench.splits assign --manifest in.jsonl --config cfg.json --out out.jsonl [--report r.json] [--freeze f.json]
    python -m asr_bench.splits report --manifest m.jsonl                        # leakage + source-disjoint report
    python -m asr_bench.freeze create --manifest m.jsonl --config cfg.json --out freeze.json
    python -m asr_bench.freeze verify --manifest m.jsonl --freeze freeze.json [--config cfg.json] [--audio-root src=dir]
    python asr_bench/test_splits_freeze.py                                      # S3 tests
    python -m asr_bench.registry report [--json]                                # source gates + documented blockers
    python asr_bench/test_registry.py                                           # registry / licence-gate tests

- `schema.py`: fields, enums and single-row rules (is this a valid manifest row?).
- `validate.py`: whole-manifest rules (utt_id uniqueness; no speaker, session, recording or audio hash in two splits), the blocked-row count, and the command line.
- `eligibility.py`: may this row be used, and for which split? Legally usable, then split-eligible. Blocked rows are valid inventory but never eligible. Every benchmark or training consumer must select rows through `select_eligible()`.
- `audio_meta.py`: `sample_rate_hz`, `duration_s`, `channels` of the ORIGINAL file, and `audio_sha256` = **SHA-256 of the exact source audio file bytes** (never decoded PCM; no content fingerprinting). WAV is read from its header with the stdlib. Other formats need PyAV, which is optional and not added as a requirement.
- `adapters.py`: `SourceInfo`, `SourceUtterance` (no defaults: every field explicit), `DatasetAdapter`, and `build_row` / `build_rows`. These add `utt_id`, the measured metadata and the caller's split, check the namespacing contract, and refuse any row the schema rejects.
- `splits.py`: split ASSIGNMENT. Rows are grouped by transitive union-find over non-null speaker/session/recording IDs (never audio). Each group goes to one split via `sha256(salt, group key)` and the source's explicit `hash` or `fixed` policy. Groups with a blocked row, or with a null speaker, become eval_only inventory, and eval_only-restricted groups never enter train. `leakage_report` adds exact-audio (error) and exact-transcript (warning) checks to the S1 validator, plus per-language source-disjoint availability.
- `freeze.py`: final-test FREEZE. A deterministic JSON of utt_ids plus per-row audio / audio-metadata / reference / metadata hashes (excluding `audio_path`), the config digest and salt. It is never overwritten; `verify` names every addition, removal, move and change.
- Four separate concepts: schema validity (`schema.py` / `validate.py`), eligibility (`eligibility.py`), split assignment (`splits.py`), final-test freezing (`freeze.py`).
- `examples/`: toy manifests (one valid, one deliberately invalid) and a toy split config (D-S3-1/2 values). They contain no real data.
- `PENDING_DECISIONS.md`: open decisions (including the Phase 1 vs 2A provenance conflict), and the readings of §3 that S1 made.

**Adapter contract.** `speaker_id`, `session_id` and `recording_id` must be globally namespaced by the adapter that writes them, e.g. `<source>:<source_speaker_id>` (`mucs2021_hien:spk017`). The validator does not parse any prefix. It compares IDs as opaque strings, so bare IDs such as `spk1` from two sources would be reported as one speaker leaking across splits. The CMI scale and definition must likewise be recorded with the source's adapter or the benchmark configuration; the schema accepts any finite number.

**Open decision D-PROV-1 (provenance).** The schema uses the Phase 2A §3 provenance enum exactly. Phase 1's `real_incident` is unresolved against it. A known real incident must not be relabelled `unknown`, and `unknown` is never equivalent to `real_incident`. Such data stays out of the manifest and all execution until the owner decides. See `PENDING_DECISIONS.md`.

**Schema limitation.** Blocked rows stay in the manifest as inventory with `split="eval_only"`, because §3 has no unassigned split. They are never train- or benchmark-eligible.

**Stages S4–S9 (benchmark execution):**
- `textnorm.py`, `align.py`, `scoring.py`: the §5 normaliser and every §5 metric (WER, CER, S/D/I rates, hallucination, language-switch error, English-word preservation, negation preservation + polarity flips, safety-keyword recall + false insertion per hour, code-switched utterance integrity) per utterance, aggregated as ratios of sums.
- `stats.py`: speaker-level bootstrap 95% CIs (1,000 resamples) and paired bootstrap differences.
- `runner.py`: runs the frozen Phase 0 engines (production `stt.py` classes, unchanged) or a `module:factory` candidate on the eligible rows of one split. It records per-utterance output, RTF, peak RSS and reproducibility metadata. It refuses mock/unloadable engines, and refuses final_test without a verified freeze.
- `report.py`: slice × condition × real/synthetic tables with CIs, failure listings, final-test totals only, paired comparison.
- `conditions.py`: the §4 synthetic recipes (traffic, crowd, low SNR, clipping, phone band, pocket, overlap), labelled synthetic with recipe + seed.
- `ingest.py`: adapter → registry gate → split → rows → leakage check → manifest; §7 slice-minimum check.

    python -m asr_bench.runner --manifest m.jsonl --split dev --engine phase0_whisper_small_en --input-unit utterance --audio-root <source>=<dir> --out run.jsonl
    python -m asr_bench.report score --manifest m.jsonl --run run.jsonl --config bench.json --out report.json [--failures f.jsonl] [--markdown r.md]
    python -m asr_bench.report compare --manifest m.jsonl --a baseline.jsonl --b candidate.jsonl --config bench.json --out cmp.json
    python -m asr_bench.ingest build --adapter module:Class --split-config cfg.json --audio-root dir --out m.jsonl
    python -m asr_bench.ingest slices --manifest m.jsonl --config bench.json
    python asr_bench/test_scoring_stats.py && python asr_bench/test_pipeline_e2e.py

**Kathbath (first real source):** `kathbath_adapter.py` (original .m4a, exact file hash, decoded duration, `kathbath:` speaker IDs, registry gate), `configs/phase2a_split_config.json` (hash policy, provisional ratios), `configs/kathbath_layout.TEMPLATE.json` (must be filled from the real package). After the gate is accepted and the package is on disk:

    KATHBATH_ROOT=<dir> KATHBATH_LAYOUT=<filled layout.json> python -m asr_bench.ingest build --adapter asr_bench.kathbath_adapter:from_env --split-config asr_bench/configs/phase2a_split_config.json --audio-root <dir> --out kathbath_manifest.jsonl

**Phase 2B (defined portion only):**
- `decision_evidence.py`: the 2A §7 rules for one candidate vs the frozen baseline, as PASS / FAIL / UNAVAILABLE with numbers and CIs. It makes no decision and picks no winner. `python -m asr_bench.decision_evidence --baseline b.json --candidate c.json --compare cmp.json --out ev.json`
- `transcript_repr.py`: the transcript representation contract. It holds the complete utterance in mixed script plus an optional named romanised view, per-token language / script / times with their sources, and engine and provenance. No representation is chosen.
- `asr_errors.py`: `D_asr_errors` (Phase 1 §17) from run files + manifest, with labelled error types. final_test is never included, and `usable_for_training` is true only for train + train_ok. `python -m asr_bench.asr_errors build --manifest m.jsonl --run a.jsonl --run b.jsonl --config bench.json --out d.jsonl`
- Context / speaker-attribution evaluation is NOT implemented: it is blocked by N-10 and the Phase 1 collection.

**Phase 3** lives in `udk_context/` (context-aware safety layer; see `udk_context/OPEN_ITEMS.md`). Tests: `python udk_context/test_context.py`.

**Phase 4** lives in `udk_signals/` (acoustic / speaker / overlap signal layer, not wired into the live path; see `udk_signals/OPEN_ITEMS.md`). Tests: `python udk_signals/test_signals.py`.

`examples/toy_benchmark_config.json` is PROVISIONAL (it says so in every report). `examples/toy_engines.py` and `examples/toy_adapter.py` are test fixtures, not models or data.

The core (S1–S3, registry, scoring, stats, report) uses the Python standard library only. Audio decoding and synthesis use the repo's existing stack when present (faster-whisper / PyAV, numpy, scipy); nothing is added to any requirements file.
