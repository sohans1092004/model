# Phase 6D: production image / deployment-pipeline validation

**Status (after the retry): production-image validation blocked by the build environment's TLS interception. Docker build containers do not trust this environment's TLS-interception CA, so every HTTPS fetch in the Dockerfile's `pip install` step fails certificate verification. No code blocker identified.**

(First attempt: additionally, `download.pytorch.org` and `huggingface.co` were denied by the egress policy. The user then widened Network access. On the retry all three hosts returned 200 from the host, but the build failed at the same step on TLS verification. See §2.)

Evidence labels used below:

| Label | Meaning |
|---|---|
| **[PROD-IMAGE]** | verified in the actual production image. **Nothing in this document carries this label**: the image was not built. |
| **[SMOKE-IMAGE]** | verified only in the Phase 6C smoke image: same build context, byte-identical whitelist, `python:3.11-slim`, light dependencies, no weights. |
| **[T4-SYNTH]** | verified only in the local/Kaggle-T4 synthetic benchmark (proxy models, stubbed front-end). |
| **[CODE]** | verified in this environment against the repository (package check, tests, code reading). |
| **[UNVERIFIED-AWS]** | not verifiable from here. |

## 1. Production image build environment

- **Environment:** the Claude Code cloud container, with Docker Engine 29.3.1 (BuildKit) started locally.
- **Command:** the pipeline's own, from `deploy/remote_deploy.sh`: `DOCKER_BUILDKIT=1 docker build --progress=plain -f deploy/Dockerfile -t udk-api:6d-validation .`
  - Real build context (repo root).
  - Real `deploy/Dockerfile`, unmodified and identical to 96ea038.
  - No build args, as in the pipeline when SSM has no Hugging Face token.
- **Egress:** through the environment's agent proxy, which intercepts TLS with its own CA (`/root/.ccr/ca-bundle.crt`).
- **Not done, per the rules:** TLS verification was not weakened, the Dockerfile was not changed or replaced, and no proxy models were substituted.

## 2. Build result

**FAILED at step 4/6.** Full log: `bench/results/production_build_attempt_6d.log`.

| Step | Result |
|---|---|
| 1/6 `FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime@sha256:c8268a92…` | pulled from Docker Hub (202 s) |
| 2/6 `WORKDIR /app` | ok |
| 3/6 `COPY deploy/requirements-deploy.txt deploy/` | ok |
| 4/6 `RUN pip install … torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124 && pip install -r deploy/requirements-deploy.txt …` | **exit 1** |
| 5/6 `COPY . .` and 6/6 `prefetch_models.py` | not reached |

The step 4 error was `SSLCertVerificationError: self-signed certificate in certificate chain` for `download.pytorch.org` and for `pypi.org`, then `No matching distribution found for fastapi`. The build container does not trust the interception CA.

Probed from the host with the CA trusted:

| Host | Result |
|---|---|
| `pypi.org` | 200 |
| `download.pytorch.org:443` | **proxy CONNECT → 403**, recorded by the proxy as `connect_rejected` ("policy denial") |
| `huggingface.co:443` | **proxy CONNECT → 403** (same) |

So even with the CA installed, step 4 (`torchaudio`) and step 6 (`snapshot_download` in `prefetch_models.py`) cannot succeed here. As instructed, no further workaround image was built.

**Retry after the Network access change** (log: `bench/results/production_build_attempt_6d_retry.log`):
- From the host, `download.pytorch.org` (torchaudio index), the `huggingface.co` model API and `pypi.org` all returned **200**. The egress denial is resolved.
- Same pipeline command, same unmodified Dockerfile: the base image was pulled again and steps 1–3 were ok.
- Step 4/6 **failed again**: `SSLCertVerificationError: self-signed certificate in certificate chain` for `download.pytorch.org` and `pypi.org`, then `No matching distribution found for fastapi`.
- Cause: build containers do not receive the environment's interception CA. Allowing domains cannot fix that. Fixing it inside the build would need a Dockerfile change (installing the CA) or disabling verification, and neither is allowed here.
- The only remaining infrastructure dependency is **a build environment whose TLS path Docker build containers trust**, i.e. no TLS interception. The real deploy host is expected to qualify **[UNVERIFIED-AWS]**.

**Blocking infrastructure dependencies:**
1. Egress to `download.pytorch.org` and `huggingface.co`. Change it under the environment's Network access settings: a broader level, or those domains allowed.
2. A build environment whose Docker builds trust its own TLS path. That means no interception, or an interception CA the pipeline itself provides. It must not come from a Dockerfile change made for this test.

The real deploy host (`remote_deploy.sh` on the sakhi-udk instance) is presumably such an environment. **[UNVERIFIED-AWS]**

## 3. Actual image contents

- **Not verifiable** in the actual production image. `COPY . .` was never reached.
- **[CODE]** `deploy/check_package.py` shows the whitelist ships 56 files. Shadow is 26 of them: 24 `.py` modules plus `udk_fusion/configs/production_equivalent.json` and `udk_context/configs/production_equivalent.json`. The check also shows every shipped shadow file is imported by shadow, and nothing shadow imports is missing.
- **[SMOKE-IMAGE]** In the Phase 6C smoke image, `find` over the five packages listed exactly those 26 files. No tests, `report.py`, `evaluation.py`, fixtures, docs, `bench/`, Kaggle tooling, results or scratch files; from `asr_bench`, only `__init__.py` and `textnorm.py`.

## 4. check_package result

**[CODE]** `deploy/check_package.py` passes: "56 files; api.py starts from them alone, with shadow mode OFF and ON". It checks:
- the static import checks: root modules, plus the shadow import closure and "nothing extra";
- that `api.py` starts from the whitelisted copy with shadow OFF, shadow ON (plus self-check), `udk_shadow` blocked, and a shadow dependency blocked.

This is a whitelisted-copy check, **not** the production image. It passed on the Kaggle T4 in Phase 6C as well.

## 5. Shadow OFF startup

- **[SMOKE-IMAGE] + [CODE]:** the service starts, answers `/metrics`, `api._shadow is None`, and `udk_shadow` is never imported. `_load_shadow()` returns before importing anything unless `UDK_SHADOW_MODE=1`.
- **[CODE]** The live path does not need the shadow package: removing or blocking it leaves the service serving.
- **Not verified in the production image** (with its GPU base, real models and real weights).

## 6. Shadow ON startup

- **[SMOKE-IMAGE] + [CODE]:** the runtime imports, the start-up self-check passes, and the effective configuration is recorded. The service and a real uvicorn server start and answer `/metrics`.
- With a missing package, a missing dependency or an invalid config, shadow fails closed to OFF and the service serves.
- **Not verified in the production image.**

## 7. Live-service smoke result

**[SMOKE-IMAGE]** `bench/smoke_live_service.py` inside the smoke image passed 11/11. It uses the real `api` module: REST start, websocket streaming through the real `_run_incremental_detection` and hook, 6 live alerts including two UDKs in one segment.

| Scenario | Result |
|---|---|
| shadow OFF | service serves, shadow not loaded |
| shadow ON | 9 observations, 0 errors, 0 drops, Phase 5 = live on 6/6 processed segments |
| shadow-stage failure | errors recorded at `phase5` |
| queue full | 2 drops counted |
| shadow package missing | shadow OFF |

In every scenario the live alerts were identical to shadow OFF.

This was **not run in the production image**: it needs the image. Its live path uses MockSTT, a fixed-block VAD, and no BEATs, intent model or Parakeet, because the smoke image has no weights.

## 8. Runtime configuration

**Baked into the image [CODE], from `deploy/Dockerfile`:**
- `ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app HF_HOME=/app/hf_cache UDK_DATA_DIR=/data`.
- Code: the whitelisted files, including the shadow runtime.
- Model weights prefetched at build.
- The intent model (`/app/models/intent_mdeberta`) is baked **only** when the build gets `UDK_INTENT_MODEL_REPO/REVISION` and the `hf_token` secret. `remote_deploy.sh` passes those only if SSM `/sakhi/udk/hf-token` exists, and then tags the image `<release>-intent`.
- No `UDK_ENABLE_*`, `UDK_DEVICE` or `UDK_SHADOW_*` value is baked.

**From the runtime environment [CODE], `remote_deploy.sh`:** `docker run --env-file run.env`, where `run.env` is SSM `/sakhi/udk/config` merged with `deploy/.env.example`.
- For every key `.env.example` sets, the repo value wins.
- `UDK_DEVICE` is excluded from the repo file, so it comes from SSM.
- Keys only in SSM, for example any `UDK_SHADOW_*`, pass through. `UDK_SHADOW_MODE` is not in `.env.example`.

**[UNVERIFIED-AWS]:**
- the contents of SSM `/sakhi/udk/config`, including `UDK_DEVICE` (the script comment gives `cpu`) and whether any `UDK_SHADOW_*` is set;
- whether `/sakhi/udk/hf-token` exists, which decides whether the live intent veto exists at all;
- which image tag is actually running.

**The diagnostic record [CODE]** (`effective_settings`; `test_shadow.py` asserts the fields) contains:
- `UDK_SHADOW_MODE` {env, effective_enabled};
- `UDK_ENABLE_SCREAM_TRIGGER` and `UDK_ENABLE_SCREAM_DETECTION`, each {env, live_flag, detector_loaded, effective};
- `sentence_veto`: {live: gate loaded, threshold, second STT, effective; shadow_phase3; phase5_sentence_veto_guard};
- `s4_status`;
- `UDK_DEVICE` {env (raw), live_resolved (the value `api._device()` resolved; read, never resolved by shadow)};
- `acoustic_policy`.

Values seen in the smoke image with no flags set **[SMOKE-IMAGE]**: shadow env `1` → enabled; both scream flags env None → effective False; live veto not loaded; Phase 5 guard False; S-4 `open`; `UDK_DEVICE` env None → resolved `cpu`. No defaults were changed.

## 9. Phase 6C resource-impact result

**[T4-SYNTH]** From Phase 6C; not re-run. Kaggle Tesla T4, proxy models, 3 repeats × 192 segments. Details are in `PHASE6C_VALIDATION.md` §3–4.

- **No-idle (continuous) workload:** full shadow ON **materially increases live latency**: p50 30 → 62 ms, p95 75 → 158 ms, live intent inference 25 → 48 ms/call, CPU 1.0 → 1.7 cores. Shadow and live share the same model instances and device. This was consistent in all 3 repeats.
- **0.5 s speech-to-text pacing:** **no measurable live-path effect** in this synthetic workload. The ranges overlap; GPU utilisation rises 3.3 → 6.8 %.
- **ON-lite** (`UDK_SHADOW_INTENT=0`, `UDK_SHADOW_SEMANTIC=off`): **substantially lower interference** (p50 +1–2 ms, no idle time), at lower replay fidelity (144/180 vs 180/180).
- No acceptance threshold exists in the project. A working image does not make shadow production-safe: the continuous-load interference has to be weighed in the deployment decision.

## 10. Known limitations

- **The actual production image was not built.** Contents, OFF/ON startup and the live-service smoke are verified only in the whitelisted copy and the smoke image.
- The smoke image lacks the production base (CUDA, torch), the real dependency versions and the model weights. So the effect of real Whisper, Parakeet, BEATs, MiniLM and mDeBERTa loading next to shadow is unverified in an image.
- The resource figures are synthetic (T4, proxy models) and cover neither the production device nor real speech-to-text latency.

## 11. Exact remaining prerequisites before controlled shadow deployment

1. **Build the production image** where Docker build containers have a trusted TLS path (no interception), preferably the real deploy host, running only the build command, not `remote_deploy.sh`, which also swaps the running container. Egress to `download.pytorch.org` and `huggingface.co` is now confirmed possible from this environment's host, but its build containers still fail TLS verification. Then run against **that** image:
   - `python deploy/check_package.py` (inside the build context);
   - `udk_shadow/bench/docker_smoke/run_smoke.sh` with its build step replaced by the production image tag (only `IMG` and the build line change);
   - `udk_shadow/bench/smoke_live_service.py` inside the image;
   - a start with shadow OFF and with `UDK_SHADOW_MODE=1`, checking the `shadow mode ON (udk_shadow, self-check ok)` log line.
2. **Read and record** SSM `/sakhi/udk/config` (`UDK_DEVICE`, scream flags, any `UDK_SHADOW_*`), whether `/sakhi/udk/hf-token` exists, and the running image tag.
3. **Measure** real speech-to-text time per segment on the production device, and re-run `bench/interference.py` there. Or at least confirm the device, since the continuous-load interference result depends on it.
4. **Define operational acceptance criteria** for live-path latency and resources. Choose the shadow configuration to evaluate against them (ON, ON-lite, sampling rate, log sink limits), explicitly accounting for the measured continuous-load interference.
5. **Enabling `UDK_SHADOW_MODE=1`** for any scope remains a separate, explicitly approved change. Nothing here enables it.
