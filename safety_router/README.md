# safety_router: Hindi, Telugu / Tamil / Kannada, and per-segment language routing

The non-English branches of the live service and the per-segment routing between them and the English path.
Whole system (all branches, settings, measured results, limits): `docs/system.md`. Hindi design and history:
`docs/hindi_distress_system.md`. **Off by default**: with `UDK_ENABLE_HINDI` unset and `UDK_ENABLE_INDIC_EXACT`
unset, `api.py` imports nothing from this package and behaves exactly as before. Both are HOST settings (the
host's SSM config, `deploy/README.md`), on only on the GPU host.

| file | what |
|---|---|
| `hindi.py` | `HindiSystem` (IndicConformer → [A] LaBSE phrase similarity → [B] MuRIL live-danger model → rule `decide`, plus a word-for-word phrase check that asks), `HindiStream` (per-journey 30 s context) |
| `indic_exact.py` | Telugu / Tamil / Kannada: exact / fuzzy phrase match only (no meaning fallback), ≥ half the phrase's words, safe-context cue words |
| `indic_stt.py` | IndicConformer 600M multilingual (RNN-T). Encodes a segment once and decodes it per language; thread budget and GPU memory pool via `stt.ort_session_defaults` |
| `router.py` | `route()` (most likely languages until 95 %, cap 3), `route_with_indic()` (te/ta/kn-led: all three + en/hi at ≥ 20 %), `WhisperLanguageID`, `SegmentRouter` (stand-alone use) |
| `test_router.py` | logic checks without models: `python -m safety_router.test_router` |

## How it runs in api.py (`_run_incremental_detection`, per VAD segment)
1. Scream trigger on every segment (unchanged rule).
2. Custom-UDK gate: with its own model (GPU host, medium.en) it starts in parallel with everything below and shares
   the segment's Parakeet run; on the CPU host (small.en, shared) it runs after language ID. A hit → `TRIGGER_ALL`
   and the other branches' result for that segment is dropped.
3. Language ID (Whisper small) → `route_with_indic`: English-routed → `_existing_alerts` (the English model,
   unchanged); Hindi-routed → `HindiSystem` on a worker thread; te/ta/kn-routed → `_indic_exact` per language.
4. `_merge_hindi` / `_merge_indic`: a branch's decision is used only when it outranks every alert already raised.
   Events: Hindi `layer: "hi_frame"` ([A] / [B] / frame in `reason`; frame `PHRASE_EXACT` for the word-for-word
   check), te/ta/kn `layer: "te_exact"` / `"ta_fuzzy"`…, ask only.
5. Failures: language ID, Hindi or te/ta/kn raising → the segment keeps the English path's result (logged);
   enabled but not loadable → the service refuses to start.
Checks: `test_hindi_routing.py`, `test_indic_exact.py`, `test_multilingual.py` (fake models).

## Requirements (only with the switches on)
- [B] weights (950 MB) in the **private** HF repo `sohans1092004/hindi-distress-frame`, pinned in `hindi.HUB_REVISION`
  (`v2-2026-10-05`, commit `be81da55…`, SHA-256 `4359c62b…7478`; `v1-2026-10-03` for rollback only, with the old rule).
  SHA-256-checked when loaded; or `UDK_HINDI_WEIGHTS=<local file>`.
- The gated `ai4bharat/indic-conformer-600m-multilingual` (accept its terms with the HF account).
- Both, plus Whisper small, LaBSE and MuRIL, are **baked into the image** at build (`deploy/prefetch_models.py`,
  `UDK_PREFETCH_MULTILINGUAL=1`, set by `deploy/remote_deploy.sh` from the host's settings) with the HF token from
  SSM `/sakhi/udk/hf-token`; the GPU host runs with `HF_HUB_OFFLINE=1`.
- GPU: `onnxruntime-gpu` for CUDA 12 (the Dockerfile installs it). One 16 GB T4 fits the whole system with
  `UDK_TEXT_MODELS_DEVICE=cpu` (11.9 GB peak measured).
- Not yet verified: the first Docker build with the multilingual models (IndicConformer's remote code ran on
  Kaggle's image, not yet on this one).

## Known limits
Hindi detects the 20 phrases (and asks on a word-for-word match), not danger in other words; te/ta/kn are phrase
matching only and only ever ask; see `docs/system.md` section 4.
