# Phase 6C: shadow-mode production-readiness validation

Everything here comes from local or synthetic runs: proxy models and stubbed audio front-end. **None of it is production performance or real-world safety performance.** Passing tests is not production readiness.

## 1. Scope

This validation checks that shadow mode (`udk_shadow/`, hooked into `api.py`) can be packaged and deployed, fails closed, and leaves the authoritative live path unchanged. It also measures how much it interferes with the live path.

Out of scope, and not changed here:
- Phase 3/4/5 rules, UDK policy, BEATs policy and thresholds, live alert behaviour;
- S-4 and the sentence-veto guard;
- speaker and overlap models, datasets;
- deployment to users. Shadow is OFF by default and is not enabled anywhere.

## 2. Package/deployment result

**Before this phase**, `deploy/Dockerfile.dockerignore` was a strict whitelist that listed none of the new packages. An image built from it could never run shadow: shadow would fail closed to OFF at start-up.

**Change:** 29 lines added to the whitelist, listing the shadow runtime file by file. That is 26 files: 24 `.py` modules plus `udk_fusion/configs/production_equivalent.json` and `udk_context/configs/production_equivalent.json`.

| Package | Shipped |
|---|---|
| `udk_shadow` | `__init__`, `config`, `context`, `evidence`, `observation`, `processor`, `runner`, `selfcheck` |
| `udk_fusion` | `__init__`, `engine`, `inputs`, `policy` |
| `udk_context` | `__init__`, `context_window`, `decision`, `intent`, `negation`, `production_adapter`, `scene` |
| `udk_signals` | `__init__`, `acoustic`, `evidence` |
| `asr_bench` | `__init__`, `textnorm` only |

**Not shipped:** tests, `report.py`, `evaluation.py`, fixtures, docs, `bench/`, and the rest of `asr_bench`.

`deploy/check_package.py` (+81/−1) now:
- follows shadow's import closure, module- and function-level. It fails if an imported module isn't shipped, or if a shipped shadow file is never imported. The one documented exception is `udk_context.scene → asr_bench.splits`, offline tooling shadow never calls.
- starts `api.py` from the whitelisted files alone with: shadow OFF; shadow ON (plus self-check); `udk_shadow` unavailable; a shadow dependency unavailable.

I tested it by breaking the whitelist on purpose three ways (a module dropped, an extra file added, a config dropped). Each was caught.

**Results:**
- `deploy/check_package.py` passes here: "56 files; api.py starts from them alone, with shadow mode OFF and ON".
- It also passed on the Kaggle T4 on this branch; the 96ea038 original passed on its own tree.

**Fail closed:**
- `runner.load()` runs `selfcheck.run()` at start-up: one synthetic observation through every stage, with no model and no live state.
- If the self-check fails, or on any import or config error, shadow stays OFF and the service starts normally.

## 3. OFF vs ON vs ON-lite benchmark

**Setup** (local, synthetic, proxy models; Kaggle, Tesla T4, CUDA, torch 2.10.0+cu128, 4 vCPU, torch threads 2):
- **Live code:** the real live loop (`api._run_incremental_detection`, `_either_stt_decisions`, `_intent_veto`, `_decision_to_event`, extracted from `api.py`), the real `UDKEngine`, and the live `SentenceTransformerSemanticMatcher` and `IntentGate` classes.
- **Models:** random-weight proxies with the production architectures (MiniLM-L12 semantic, mDeBERTa-v3-base intent), loaded on the GPU.
- **Stubbed:** VAD, Whisper and Parakeet (fixed transcripts); BEATs (fixed values, no compute).

**Workload:** a fixed 16-item mix, repeated 12 times, gives 192 segments per run:
- standard UDKs, a two-UDK segment, verify-by-default phrases;
- near-misses and ordinary speech;
- one scream-only segment and one no-text segment (the latter 12 times → 12 no-text skips, so 180 segments are processed per run).

**Matrix:** mode {OFF, ON, ON-lite} × stubbed speech-to-text time per segment {0.0 s, 0.5 s} × 3 repeats = 18 runs.
- 0.0 s: no idle time between segments (worst case).
- 0.5 s: the stubbed speech-to-text sleeps 0.5 s, as a real one would take time.
- ON-lite: `UDK_SHADOW_INTENT=0`, `UDK_SHADOW_SEMANTIC=off`.

Values are shown per repeat as r1/r2/r3. Raw data: `bench/results/kaggle_t4/runs/*.json`.

**Speech-to-text 0.0 s (no idle time):**

| metric | OFF | ON | ON-lite |
|---|---|---|---|
| live loop latency p50 (ms) | 30.4/30.9/30.4 | 62.7/60.5/61.8 | 31.8/31.8/32.0 |
| live loop latency p95 (ms) | 73.8/75.2/75.6 | 158.7/158.7/155.7 | 77.7/76.8/76.4 |
| call start → alert emitted p50 (ms) | 30.7/31.1/30.6 | 65.3/61.9/64.3 | 32.1/32.1/32.2 |
| call start → alert emitted p95 (ms) | 76.0/77.6/77.9 | 172.1/161.2/164.6 | 79.8/77.6/79.2 |
| live semantic similarity (ms/call) | 0.2 | 0.5 | 0.2 |
| live intent inference (ms/call) | 24.6/24.8/24.5 | 49.1/47.4/48.9 | 24.7/24.7/24.6 |
| CPU (cores = cpu_s/wall_s) | 1.0 | 1.7 | 1.0 |
| GPU utilisation mean (%) | 34.5–34.6 | 35.1–35.5 | 35.0–35.2 |
| peak RSS (MB) | 2158–2159 | 2158–2159 | 2158–2159 |
| shadow processing p50 / p95 (ms) | – | 61 / 158 | 0.9 / 2.9 |
| shadow queue wait p50 / p95 / max (ms) | – | 355–379 / 531–582 / 627–658 | 0.4 / 3.1–3.3 / 3.8–4.2 |

**Speech-to-text 0.5 s:**

| metric | OFF | ON | ON-lite |
|---|---|---|---|
| live loop latency p50 (ms) | 532.2/531.5/532.7 | 531.5/532.1/532.7 | 532.0/532.5/531.6 |
| live loop latency p95 (ms) | 575.0/573.0/577.5 | 574.3/575.7/575.7 | 576.7/579.0/574.1 |
| call start → alert emitted p95 (ms) | 577.9/577.7/581.8 | 576.7/579.7/580.0 | 584.1/580.3/576.7 |
| live intent inference (ms/call) | 26.0/25.6/26.5 | 23.8/24.3/24.8 | 26.2/26.4/25.6 |
| CPU (cores) | 0.1 | 0.1 | 0.1 |
| GPU utilisation mean (%) | 3.2–3.3 | 6.7–6.9 | 3.2–3.4 |
| peak RSS (MB) | 2158–2160 | 2158–2159 | 2158–2158 |
| shadow processing p50 / p95 (ms) | – | 30–32 / 71–74 | 1.0 / 2.8–2.9 |
| shadow queue wait max (ms) | – | 0.3 | 0.3–0.6 |

**Shadow outcomes in every ON / ON-lite run:**
- 192 observations: 180 processed with status `ok`, 12 `skipped_live_no_text`.
- 0 queue drops, 0 capture errors, 0 stage errors.
- Phase 5 decision equal to live on 180/180 processed segments in ON, 144/180 in ON-lite.
- ON-lite replays without semantic matching or the intent model, so it matches live less often. This is a known fidelity cost, not an error.

**CPU:** an earlier partial CPU matrix (4-core CPU; 1 repeat) showed the same pattern: ON roughly doubled no-idle live latency (208 → 465 ms p50). At the user's request, the full matrix was run on GPU only.

## 4. Authoritative live-path resource impact

**With no idle time between segments:** shadow ON measurably and consistently changes the live path. The ranges across the 3 repeats don't overlap:
- live latency p50 +~31 ms (≈2×), p95 +~83 ms (≈2.1×);
- live intent inference 25 → 48 ms/call;
- CPU 1.0 → 1.7 cores.

The cause is shadow's own intent-model and semantic inference running concurrently on the same model instances and device. Phase 3 scores the sentence intent for every replayed event.

**ON-lite, no idle time:** a small but consistent shift: p50 +1.1–1.6 ms, p95 +1–2 ms.

**With 0.5 s speech-to-text per segment:** no measurable change to any live-path metric. The ranges overlap. Shadow's work completes during the speech-to-text wait. GPU utilisation rises 3.3 → 6.8 %.

**Memory:** RSS and GPU memory change by at most about 10 MB in any mode.

**Acceptance is not decided here.** No existing project requirement defines a latency or resource threshold, so whether these numbers are acceptable is an explicit open operational decision.

**What these numbers can't show:**
- 3 repeats of one synthetic workload on one T4 is not a statistical test, and not production performance.
- Real speech-to-text time per segment, the production device, and real model weights all change the absolute numbers.

## 5. Counterfactual replay clarification

The records and the report keep three things separate:
- **A. Live behaviour:** the `live` block: `live_decision`, `live_chosen_stt`, `pre_veto`, `decisions`, `emitted_events`.
- **B. Shadow replay:** the `replay` block. It re-runs the live decision functions from the live engine state with `scream_score=None`, so Phase 3/5 get linguistic evidence with the scream influence removed.
- **C. Removing the scream can change which STT list is kept.**
  - `replay.stt_choice_differs_from_live` flags this per segment.
  - `replay.semantics` says: "counterfactual_linguistic_replay … NOT a reconstruction of the live path with BEATs disabled".
  - `report.compare()` repeats the same note (`replay_semantics`) and counts the flips.

**Test coverage:** the STT-flip test (Whisper UDK_14 live vs Parakeet UDK_05 in the replay) checks these labels. Every replayed record in the live-service smoke carried the label.

The replay is never described as an exact reconstruction of the live path with BEATs disabled.

## 6. Runtime configuration verification

**How the values are obtained (code-traced):**
- `api.py` reads the environment at import.
- In AWS the container environment comes from `deploy/remote_deploy.sh`:
  - it fetches SSM `/sakhi/udk/config`;
  - it merges `deploy/.env.example` over it with `awk`, so for any key the repo file sets, the repo value wins, except `UDK_DEVICE`, which the host keeps;
  - the result is passed with `docker run --env-file`.

**Recorded values:** every shadow record's `effective` block now holds the raw environment value and the effective state for each setting below. It observes them and never changes a default.

| Setting | Repo `.env.example` | AWS/SSM | Effective in the Docker smoke container (no flags set) |
|---|---|---|---|
| `UDK_SHADOW_MODE` | not set; could only come from SSM | **UNVERIFIED** | set by the test: `1` → enabled; unset → OFF |
| `UDK_ENABLE_SCREAM_TRIGGER` | `1` (repo value wins) | **UNVERIFIED** | env None → effective False (no detector) |
| `UDK_ENABLE_SCREAM_DETECTION` | `1` (repo value wins) | **UNVERIFIED** | env None → effective False |
| Sentence veto (live) | `UDK_INTENT_GATE=/app/models/intent_mdeberta`, threshold 0.02 | **UNVERIFIED**: the model is only built in when the HF token exists in SSM; otherwise `intent_gate.from_env` returns None and there is no live veto | gate not loaded → effective False |
| Sentence veto (shadow Phase 3 / Phase 5 guard) | – | – | Phase 3 production-equivalent enabled at 0.02 (scored only if the gate loads); Phase 5 guard **False** |
| S-4 | – | – | `open` |
| `UDK_DEVICE` | excluded from the repo file; host value from SSM | **UNVERIFIED** (deploy comment says the host setting is `cpu`) | env None → live-resolved `cpu` |

## 7. Docker/package smoke test

**The production image could not be built here.** The Dockerfile's `pip install torchaudio --index-url https://download.pytorch.org/…` and `deploy/prefetch_models.py` (Hugging Face) are blocked by this environment's egress proxy. Kaggle has no Docker daemon.

**What was built instead:** a smoke image (`bench/docker_smoke/`: `python:3.11-slim`, light CPU dependencies, no weights). It uses the same build context and a byte-identical copy of `deploy/Dockerfile.dockerignore`, so the files shipped are exactly those of the production image. The environment's CA bundle was passed as a BuildKit secret; TLS verification stayed on.

**9/9 checks pass:**
1. The image ships exactly the 26 shadow runtime files and no tests, reports, evaluation, fixtures or benchmark files.
2. Shadow OFF: the service starts and `udk_shadow` is never imported.
3. Shadow ON: the runtime loads, the start-up self-check passes, and the effective config is recorded (S-4 `open`, guard False).
4. `udk_fusion` missing: fails closed and the service serves.
5. A shadow dependency (`asr_bench/textnorm.py`) missing: fails closed and the service serves.
6. Invalid shadow config: fails closed and the service serves.
7. A real uvicorn server with shadow ON answers `/metrics` (200) and logs the self-check.
8. `test_shadow.py` (live-path and failure isolation) run against the image's code: 79/79.
9. Live-service smoke **inside the image**: 11/11. This is the real `api` module, REST journey start plus websocket streaming through the real `_run_incremental_detection` and hook, 10 blocks and 6 real alerts including a two-UDK segment:
   - shadow ON: 9 observations, 6 `ok`, 3 no-text skips, 0 errors, Phase 5 equal to live on 6/6;
   - a shadow-stage exception: 6 `partial`, errors recorded at `phase5`;
   - queue full (`UDK_SHADOW_QUEUE_MAX=1` with a slow stage): 2 drops counted;
   - `udk_shadow` missing: shadow OFF.

   In every scenario the live events were identical to shadow OFF and the service stayed up.

On Kaggle (T4, without Docker), the whitelisted-copy smoke passed 7/8. The one failure was a filter bug in the check itself (the substring "bench" matched `asr_bench/`), not in the package. It is fixed and re-verified by checks 1 and 8 above.

## 8. Complete-suite results

Kaggle Tesla T4, deploy requirements plus test dependencies installed. Full logs are in `bench/results/kaggle_t4_checks/`. Branch and baseline were run from the same upload.

Since that run, only docs and test tooling changed, plus the `UDK_DEVICE` diagnostic, which was re-tested here and in the image.

**Current branch** (43 test files):
- **37 pass.** 25 root tests plus the 12 package tests:
  - `asr_bench`: 74, 25, 133, 53, 48, 51, 45, 105;
  - `udk_context` 62, `udk_fusion` 86, `udk_shadow` 79, `udk_signals` 55.
- **6 fail on environment or dependencies**:
  - `test_beats_on_real_distress_overlap.py`, `test_wavlm_speaker_verification.py`: they need Windows `powershell`;
  - `test_speaker_verification.py`: needs `speechbrain`;
  - `test_wesep_corroboration.py`, `test_wesep_target_extraction.py`: need `wespeaker.models`;
  - `test_emotion_distress.py`: needs a local evaluation log file that isn't in the repo.
- **0 skipped:** the root suites have no skip mechanism; the package suites skip nothing when their dependencies are present.

**Re-run here** (CPU, test-only deps): `udk_shadow` 79/79, `udk_context` 62/62, `udk_signals` 55/55, `udk_fusion` 86/86, all 8 `asr_bench` suites, and `deploy/check_package.py` pass.

The full suite does **not** pass: 6 files fail on environment or dependency issues.

## 9. Baseline comparison

On the clean 96ea038 baseline (31 test files), the **same 25 pass and the same 6 fail**, with identical causes. This baseline tree was reconstructed from the Kaggle upload and verified file-for-file against `git ls-tree 96ea038`.

For `test_emotion_distress.py`, only the absolute path in the error message differs, because the two trees sit in different directories.

Both trees saw one Kaggle artifact identically: Kaggle auto-extracted `real_recordings/panic_phrases_synthetic_audio.zip`. It is read only by a packaging script, not by any test.

`deploy/check_package.py` passed on both trees.

## 10. Regressions

**None found.**

- `git diff --stat 96ea038`: 3 files, 147 insertions, 1 deletion.
  - `api.py` +38: the shadow hook; 0 lines changed or removed.
  - `deploy/Dockerfile.dockerignore` +29.
  - `deploy/check_package.py` +81/−1: the final print line was reworded.
- **Unchanged vs 96ea038:** `deploy/.env.example` (production alert flags), `scream_trigger.py` and `beats_distress_detector.py` (scream thresholds), `udk_engine.py`, `udks.py`, `semantic.py`, `intent_gate.py`, `kws.py`, `vad.py`, `stt*.py`, `separation.py`, the Dockerfile, the requirements, and `prefetch_models.py`. No production model changes.
- **Phase 3/4/5:**
  - their code and config files (`udk_context/`, `udk_signals/`, `udk_fusion/`) were last modified during Phase 5, with no Phase 6 edits;
  - their unchanged suites pass;
  - the Phase 5 production-equivalent policy is still `s4_status: open` with the sentence-veto guard False.

## 11. Known limitations

- **Benchmark realism:**
  - proxy random-weight models; stubbed Whisper, Parakeet, VAD and BEATs (BEATs cost excluded);
  - one synthetic workload, 3 repeats, one T4;
  - absolute numbers are not production performance.
- **Unmeasured:** the effect of real speech-to-text latency and the real production device (possibly CPU) on interference.
- **Docker:** the production image was not built (§7); packaging was verified with a smoke image that uses the identical whitelist.
- **Replay fidelity:** ON-lite gives lower replay fidelity (144/180 vs 180/180) in exchange for lower live impact.
- **No model or data blockers lifted:** no speaker or overlap model (S-1, S-2) and no labelled data (S-3). Shadow comparisons are operational, not accuracy measurements.
- **Unverified config:** the AWS/SSM values in §6.

## 12. Remaining blockers

1. **Operational acceptance criteria** for live-path latency and resource impact are undefined (§4). Someone has to set them.
2. **Production values are unverified:**
   - `UDK_DEVICE`;
   - whether the intent-model token is present (this decides whether the live veto exists at all);
   - the scream flags and `UDK_SHADOW_MODE` in SSM;
   - real per-segment speech-to-text time.
3. **The real production image build** (GPU base, weights) with the new whitelist has not run. It needs a build environment with access to download.pytorch.org and Hugging Face.
4. **Still open:** S-4 (owner decision), the sentence-veto guard, S-1 to S-3. None blocks shadow logging itself, but all block drawing accuracy conclusions from it.

## 13. Recommendation for next engineering step

Prerequisites for a controlled shadow deployment. These are stated as prerequisites only; no option is ranked.

1. Read the actual SSM `/sakhi/udk/config` values and the image build log, and fill the UNVERIFIED cells in §6.
2. Build the production image with the updated whitelist in the normal pipeline. Run `deploy/check_package.py` and `bench/docker_smoke/run_smoke.sh` against it; the smoke Dockerfile must be swapped for the production one.
3. Measure real speech-to-text latency per segment on the production device. Re-run `bench/interference.py` with that value and the production device.
4. Define the operational acceptance criteria. Then choose the shadow settings that meet them: ON, ON-lite, or a sampling rate (`UDK_SHADOW_SAMPLE_RATE`), plus log sink limits.
5. Only then set `UDK_SHADOW_MODE=1` for a limited, monitored scope, as a separately approved change.
