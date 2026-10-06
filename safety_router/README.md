# safety_router: Hindi system + per-segment language routing

Hindi distress detection for the live service, and per-segment routing between it and the existing (English) path.
Design and measured results: `docs/hindi_distress_system.md`. **Off by default** (`UDK_ENABLE_HINDI=0`): with it
off, `api.py` imports nothing from this package and behaves exactly as before.

| file | what |
|---|---|
| `hindi.py` | `HindiSystem` (IndicConformer → LaBSE phrase match [A] → MuRIL live-danger model [B] → decision), `HindiStream` (per-journey 30 s context). Verified identical to the evaluated pipeline (40/40 decisions on real windows). |
| `router.py` | `route()` (most likely languages until 95 %, cap 3), `combine()`, `WhisperLanguageID`, `SegmentRouter` (stand-alone use) |
| `indic_stt.py` | IndicConformer 600M as an `STTBackend` |
| `test_router.py` | logic checks without models: `python -m safety_router.test_router` |

## How it runs in api.py (`UDK_ENABLE_HINDI=1`)
Per VAD segment in `_run_incremental_detection`:
1. Scream trigger (unchanged rule) on **every** segment.
   Then the per-user custom-UDK gate (`custom_udk.py`, its own Whisper medium.en + Parakeet): the user's own
   phrase -> `TRIGGER_ALL` and nothing below runs for that segment; otherwise steps 2-5, unchanged.
2. `_start_hindi`: Whisper-small language ID → English share of P(en)+P(hi) ≥ 0.95 → existing path only;
   ≤ 0.05 → Hindi only; otherwise both, Hindi in a worker thread while the existing path runs.
3. `_existing_alerts`: the per-segment steps exactly as before (Whisper + Parakeet → `decide_all` → either-STT →
   intent veto → separation retry), moved into a function, not changed.
4. `_merge_hindi`: the higher decision wins. A Hindi `ALERT` → `TRIGGER_ALL`, `VERIFY` → `TRIGGER_VERIFY`, event
   `layer: "hi_frame"`, the closest of the 20 Hindi UDKs as `udk_id`, and [A] / [B] / frame in `reason`.
5. Failure handling: if language ID or the Hindi system raises, the segment gets the existing path (logged as
   `udk.hindi`), so a Hindi-side problem never costs a detection. If Hindi is enabled but its models cannot load,
   the service refuses to start rather than run without Hindi silently.
Checks: `python test_hindi_routing.py` (fake models: routes, merging, scream on the Hindi route, both fallbacks).
The journey-level language switching (`_maybe_update_language`) is untouched.

## Requirements (only with `UDK_ENABLE_HINDI=1`)
- [B] weights (950 MB), versioned in the **private** HF repo `sohans1092004/hindi-distress-frame`:
  - `v2-2026-10-05` (commit `be81da55…`, SHA-256 `4359c62b…7478`): retrained with TV / phone-talk / drama negatives;
    **pinned in `hindi.HUB_REVISION`**, and `decide()` thresholds belong to it.
  - `v1-2026-10-03` (commit `5c8d90ad…`, SHA-256 `1d0ff14c…`): rollback only, with the old rule (no ask threshold,
    bystander 0.9).
  Downloaded and SHA-256-checked at startup; or set `UDK_HINDI_WEIGHTS=<local file>`.
- `HF_TOKEN` (runtime) with read access to that repo and to the gated `ai4bharat/indic-conformer-600m-multilingual`.
  Models (~3 GB: IndicConformer, LaBSE, MuRIL, Whisper small) download on the first start; `deploy/prefetch_models.py`
  does not prefetch them yet.
- GPU: `onnxruntime-gpu` built for the server's CUDA (CUDA 12 → `onnxruntime-gpu==1.22.x`). Without it IndicConformer
  silently runs on CPU (4–5× slower). Measured on a T4: Hindi route 0.43 s, English route 1.04 s median per segment.
- Verify on the first image built with it on: IndicConformer's remote code may need packages beyond
  `deploy/requirements-deploy.txt` (it ran on Kaggle's image; not yet on this one).

## Known limits
See `docs/hindi_distress_system.md` sections 4–5: danger without the 20 phrases is not detected; TV / phone-talk
false alarms are ~0–1 ALERT/h and ~0–2 asks/h, at the cost of one Hindi cry ("दूर हटो… पुलिस को कॉल कर रही हूं");
native-speaker check and server latency still to do. Research history (data, training, evaluation scripts) is on the
`phase2a-asr-benchmark` line of work, not in this branch.
