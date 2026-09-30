# Phase 6C checks (Kaggle GPU)

environment: `{"python": "3.12.13", "torch": "2.10.0+cu128", "cuda": true, "gpu": "Tesla T4"}`

| test | 96ea038 baseline | branch | verdict |
|---|---|---|---|
| test_api_device.py | rc=0 api device switch: all checks passed | rc=0 api device switch: all checks passed | pass both |
| test_beats_on_real_distress_overlap.py | rc=1 FileNotFoundError: [Errno 2] No such file or directory: 'powershell' | rc=1 FileNotFoundError: [Errno 2] No such file or directory: 'powershell' | fails on both (baseline failure) |
| test_clap_distress_scoring.py | rc=0 Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads. | rc=0 Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads. | pass both |
| test_class_specific_scoring.py | rc=0 Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads. | rc=0 Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads. | pass both |
| test_dual_asr_guard.py | rc=0 6/6 TOTAL PASSED -- ALL PASSED | rc=0 6/6 TOTAL PASSED -- ALL PASSED | pass both |
| test_emotion_distress.py | rc=1 FileNotFoundError: [Errno 2] No such file or directory: '/kaggle/working/udk_checks/baseline/prepped_data_eval_output_sentences_small.en.log' | rc=1 FileNotFoundError: [Errno 2] No such file or directory: '/kaggle/working/udk_checks/branch/prepped_data_eval_output_sentences_small.en.log' | fails on both (baseline failure) -- output differs, check logs |
| test_intent_gate.py | rc=0 test_intent_gate: all checks passed | rc=0 test_intent_gate: all checks passed | pass both |
| test_kws.py | rc=0 20/20 TOTAL PASSED -- ALL PASSED | rc=0 20/20 TOTAL PASSED -- ALL PASSED | pass both |
| test_m2.py | rc=0 13/13 TOTAL PASSED -- ALL PASSED | rc=0 13/13 TOTAL PASSED -- ALL PASSED | pass both |
| test_m3.py | rc=0 24/24 TOTAL PASSED -- ALL PASSED | rc=0 24/24 TOTAL PASSED -- ALL PASSED | pass both |
| test_m4.py | rc=0 20/20 TOTAL PASSED -- ALL PASSED | rc=0 20/20 TOTAL PASSED -- ALL PASSED | pass both |
| test_m5.py | rc=0 15/15 TOTAL PASSED -- ALL PASSED | rc=0 15/15 TOTAL PASSED -- ALL PASSED | pass both |
| test_m6.py | rc=0 38/38 TOTAL PASSED -- ALL PASSED | rc=0 38/38 TOTAL PASSED -- ALL PASSED | pass both |
| test_m7.py | rc=0 16/16 TOTAL PASSED -- ALL PASSED | rc=0 16/16 TOTAL PASSED -- ALL PASSED | pass both |
| test_multilingual.py | rc=0 30/30 TOTAL PASSED -- ALL PASSED | rc=0 30/30 TOTAL PASSED -- ALL PASSED | pass both |
| test_parakeet_either.py | rc=0 12/12 TOTAL PASSED -- ALL PASSED | rc=0 12/12 TOTAL PASSED -- ALL PASSED | pass both |
| test_pipeline.py | rc=0 7/7 single-transcript cases passed. | rc=0 7/7 single-transcript cases passed. | pass both |
| test_porcupine_kws.py | rc=0 Confirmed: every UDK phrase is longer than any built-in Porcupine keyword -- architectural mismatch. | rc=0 Confirmed: every UDK phrase is longer than any built-in Porcupine keyword -- architectural mismatch. | pass both |
| test_scream_detector.py | rc=0 10/10 TOTAL PASSED -- ALL PASSED | rc=0 10/10 TOTAL PASSED -- ALL PASSED | pass both |
| test_scream_trigger.py | rc=0 9/9 TOTAL PASSED -- ALL PASSED | rc=0 9/9 TOTAL PASSED -- ALL PASSED | pass both |
| test_semantic.py | rc=0 53/53 TOTAL PASSED -- ALL PASSED | rc=0 53/53 TOTAL PASSED -- ALL PASSED | pass both |
| test_separation.py | rc=0 19/19 TOTAL PASSED -- ALL PASSED | rc=0 19/19 TOTAL PASSED -- ALL PASSED | pass both |
| test_ser_arousal_scoring.py | rc=0 Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads. | rc=0 Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads. | pass both |
| test_speaker_verification.py | rc=1 ModuleNotFoundError: No module named 'speechbrain' | rc=1 ModuleNotFoundError: No module named 'speechbrain' | fails on both (baseline failure) |
| test_stt_confidence_gate.py | rc=0 10/10 TOTAL PASSED -- ALL PASSED | rc=0 10/10 TOTAL PASSED -- ALL PASSED | pass both |
| test_udk_endpoint.py | rc=0 udk_endpoint: all checks passed | rc=0 udk_endpoint: all checks passed | pass both |
| test_vad.py | rc=0 10/10 TOTAL PASSED -- ALL PASSED | rc=0 10/10 TOTAL PASSED -- ALL PASSED | pass both |
| test_wavlm_speaker_verification.py | rc=1 FileNotFoundError: [Errno 2] No such file or directory: 'powershell' | rc=1 FileNotFoundError: [Errno 2] No such file or directory: 'powershell' | fails on both (baseline failure) |
| test_webhook_delivery.py | rc=0 webhook_delivery: all checks passed | rc=0 webhook_delivery: all checks passed | pass both |
| test_wesep_corroboration.py | rc=1 ModuleNotFoundError: No module named 'wespeaker.models' | rc=1 ModuleNotFoundError: No module named 'wespeaker.models' | fails on both (baseline failure) |
| test_wesep_target_extraction.py | rc=1 ModuleNotFoundError: No module named 'wespeaker.models' | rc=1 ModuleNotFoundError: No module named 'wespeaker.models' | fails on both (baseline failure) |
| asr_bench/test_audio_meta_adapters.py | rc=–  | rc=0 74/74 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_kathbath.py | rc=–  | rc=0 25/25 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_manifest_schema.py | rc=–  | rc=0 133/133 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_phase2b.py | rc=–  | rc=0 53/53 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_pipeline_e2e.py | rc=–  | rc=0 48/48 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_registry.py | rc=–  | rc=0 51/51 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_scoring_stats.py | rc=–  | rc=0 45/45 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| asr_bench/test_splits_freeze.py | rc=–  | rc=0 105/105 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| udk_context/test_context.py | rc=–  | rc=0 62/62 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| udk_fusion/test_fusion.py | rc=–  | rc=0 86/86 TOTAL PASSED -- ALL PASSED | new (branch only): pass |
| udk_shadow/test_shadow.py | rc=–  | rc=0   warnings.warn(f"shadow mode requested but failed to start ({type(e).__name__}: {e}) -- shadow OFF, live unaffected") | new (branch only): pass |
| udk_signals/test_signals.py | rc=–  | rc=0 55/55 TOTAL PASSED -- ALL PASSED | new (branch only): pass |

baseline_check_package: rc=0 deploy package OK: 30 files; api.py starts from them alone

branch_check_package: rc=0 deploy package OK: 56 files; api.py starts from them alone, with shadow mode OFF and ON

## shadow smoke
```
[FAIL] whitelist ships shadow runtime only (26 files)
       ['asr_bench/__init__.py', 'asr_bench/textnorm.py']
[PASS] shadow OFF (default): service starts, udk_shadow not imported
[PASS] shadow ON: loads, self-check ok, S-4 open, Phase 5 sentence-veto guard False, scream flags recorded as-is
[PASS] shadow ON + real semantic model on GPU: isolated replay leaves the live cache untouched
[PASS] shadow ON + udk_fusion removed: fails closed (shadow OFF), service serves
[PASS] shadow ON + shadow dependency removed (asr_bench/textnorm.py): fails closed (shadow OFF), service serves
[PASS] shadow ON + invalid shadow config: fails closed, service serves
[PASS] uvicorn server with shadow ON answers /metrics and logs the self-check

smoke: 7/8 passed

```