(comparisons recomputed from runs/ with the current comparison code)

Components: `{"whisper": "FasterWhisperSTT", "whisper_model": "faster-whisper-small.en", "whisper_device": "cuda", "parakeet": "ParakeetSTT", "parakeet_providers": ["CUDAExecutionProvider", "CPUExecutionProvider"], "semantic": "SentenceTransformerSemanticMatcher", "stt_confidence_gate": true, "beats": "BEATsDistressDetector", "scream_trigger": true, "scream_corroboration": true, "intent_gate": "IntentGate", "intent_threshold": 0.02, "kws": "off", "dual_asr": "off", "separation": "off", "language_id": "off", "device": "cuda", "processing_version": "pipeline-2026.09"}`

Rows: 126 (recording x chunk size); repeats per mode: 2; clock: virtual: monotonic() = audio seconds delivered

| Set | Chunk | Rows | Segments OFF / ON | ON == one-shot | Events OFF / ON | Unpaired events OFF-only / ON-only | TRIGGER_ALL OFF / ON | Repeat-induced ALL OFF / ON | Duplicate alerts OFF / ON (designed) | Repeat-stable OFF / ON | Not COMPLETE | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| media | 100 ms | 18 | 121 / 103 | 18/18 | 5 / 4 | 3 / 2 | 2 / 0 | 1 / 0 | 1 / 1 (1) | 18 / 18 | 0 | 0 |
| media | 1000 ms | 18 | 110 / 103 | 18/18 | 5 / 4 | 3 / 2 | 2 / 0 | 1 / 0 | 1 / 1 (1) | 18 / 18 | 0 | 0 |
| mixed | 20 ms | 30 | 159 / 50 | 30/30 | 27 / 23 | 4 / 0 | 17 / 13 | 4 / 0 | 5 / 0 (0) | 30 / 30 | 0 | 0 |
| mixed | 100 ms | 30 | 133 / 50 | 30/30 | 27 / 23 | 4 / 0 | 17 / 13 | 4 / 0 | 5 / 0 (0) | 30 / 30 | 0 | 0 |
| mixed | 1000 ms | 30 | 82 / 50 | 30/30 | 26 / 23 | 3 / 0 | 16 / 13 | 3 / 0 | 3 / 0 (0) | 30 / 30 | 0 | 0 |

Tier changes and per-utterance timing (virtual stream clock; delay = OFF - ON)
| Set | Chunk | Tier changes OFF->ON | Utterances decided >1 s later by OFF | Max decision delay s | Alerts >1 s later by OFF | Max alert delay s | Utterances alerted only by OFF / only by ON |
|---|---|---|---|---|---|---|---|
| media | 100 ms | 0 | 0 | 0.0 | 0 | 0.0 | 0 / 0 |
| media | 1000 ms | 0 | 0 | 0.0 | 0 | 0.0 | 0 / 0 |
| mixed | 20 ms | 0 | 5 | 21.5 | 0 | 0.1 | 0 / 0 |
| mixed | 100 ms | 0 | 5 | 21.6 | 0 | 0.1 | 0 / 0 |
| mixed | 1000 ms | 0 | 5 | 23.0 | 0 | 0.0 | 0 / 0 |

Tier changes (all rows):

Utterances OFF handled >1 s later than ON (all rows):
- mix_clip_02_noisy 20 ms utterance (0, 1620): decision +3.14 s, alert +None s
- mix_clip_02_noisy 100 ms utterance (0, 1620): decision +3.2 s, alert +None s
- mix_clip_02_noisy 1000 ms utterance (0, 1620): decision +4.0 s, alert +None s
- mix_clip_10_noisy 20 ms utterance (0, 1620): decision +20.9 s, alert +None s
- mix_clip_10_noisy 100 ms utterance (0, 1620): decision +21.0 s, alert +None s
- mix_clip_10_noisy 1000 ms utterance (0, 1620): decision +22.0 s, alert +None s
- mix_clip_12_noisy 20 ms utterance (0, 1620): decision +21.52 s, alert +None s
- mix_clip_12_noisy 100 ms utterance (0, 1620): decision +21.6 s, alert +None s
- mix_clip_12_noisy 1000 ms utterance (0, 1620): decision +23.0 s, alert +None s
- mix_clip_14_noisy 20 ms utterance (0, 1620): decision +8.92 s, alert +None s
- mix_clip_14_noisy 100 ms utterance (0, 1620): decision +9.0 s, alert +None s
- mix_clip_14_noisy 1000 ms utterance (0, 1620): decision +10.0 s, alert +None s
- mix_clip_18_noisy 20 ms utterance (0, 1620): decision +4.94 s, alert +None s
- mix_clip_18_noisy 100 ms utterance (0, 1620): decision +5.0 s, alert +None s
- mix_clip_18_noisy 1000 ms utterance (0, 1620): decision +6.0 s, alert +None s

Difference classes: {'expected_vad_correction': 624, 'stt_nondeterminism': 6}

Difference kinds: {'segment_only_off / spurious segment': 60, 'segment_only_off / re-processing': 186, 'segment_only_off / drifted boundary': 188, 'segment_only_on / ON processed the one-shot segment; OFF processed drifted boundaries instead': 185, 'same_segment_different_output / engine history differs': 5, 'same_segment_different_output / ': 6}

Same-boundary field differences (segments): {'udk_primary': 5, 'pre_veto': 5, 'final': 5, 'alerts': 5, 'whisper_text': 6, 'whisper_meta': 6}

Unpaired events (all rows):
- mix_clip_06_noisy 20 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 100 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 1000 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_07_muffled 20 ms OFF-only ('24300-29250', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 20 ms OFF-only ('24300-29280', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 100 ms OFF-only ('24300-29220', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 100 ms OFF-only ('24300-29250', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 1000 ms OFF-only ('24300-29220', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_17_muffled 1000 ms OFF-only ('1260-5820', 'TRIGGER_ALL', 'UDK_19', 'exact')
- mix_clip_19_muffled 100 ms OFF-only ('6510-10950', 'TRIGGER_ALL', 'UDK_03', 'semantic')
- mix_clip_21_clean 20 ms OFF-only ('12900-17610', 'TRIGGER_ALL', 'UDK_01', 'fuzzy')
- pos_01 100 ms OFF-only ('17460-28440', 'TRIGGER_VERIFY', 'UDK_20', 'semantic')
- pos_01 100 ms ON-only ('17490-28470', 'TRIGGER_VERIFY', 'UDK_10', 'semantic')
- pos_01 1000 ms OFF-only ('17460-28440', 'TRIGGER_VERIFY', 'UDK_20', 'semantic')
- pos_01 1000 ms ON-only ('17490-28470', 'TRIGGER_VERIFY', 'UDK_10', 'semantic')
- pos_02 100 ms OFF-only ('26940-37920', 'TRIGGER_ALL', 'UDK_01', 'exact')
- pos_02 100 ms ON-only ('27060-38040', 'TRIGGER_VERIFY', None, 'acoustic_scream')
- pos_02 1000 ms OFF-only ('26940-37920', 'TRIGGER_ALL', 'UDK_01', 'exact')
- pos_02 1000 ms ON-only ('27060-38040', 'TRIGGER_VERIFY', None, 'acoustic_scream')
- neg_10 100 ms OFF-only ('0-9510', 'TRIGGER_ALL', 'UDK_03', 'fuzzy')
- neg_10 1000 ms OFF-only ('0-9510', 'TRIGGER_ALL', 'UDK_03', 'fuzzy')

Repeat-induced TRIGGER_ALL (all rows):
- mix_clip_06_noisy 20 ms OFF (17730, 22320, 'UDK_08')
- mix_clip_06_noisy 100 ms OFF (17730, 22320, 'UDK_08')
- mix_clip_06_noisy 1000 ms OFF (17730, 22320, 'UDK_08')
- mix_clip_07_muffled 20 ms OFF (24300, 29250, 'UDK_09')
- mix_clip_07_muffled 20 ms OFF (24300, 29280, 'UDK_09')
- mix_clip_07_muffled 100 ms OFF (24300, 29220, 'UDK_09')
- mix_clip_07_muffled 100 ms OFF (24300, 29250, 'UDK_09')
- mix_clip_07_muffled 1000 ms OFF (24300, 29220, 'UDK_09')
- mix_clip_17_muffled 1000 ms OFF (1260, 5820, 'UDK_19')
- mix_clip_19_muffled 100 ms OFF (6510, 10950, 'UDK_03')
- mix_clip_21_clean 20 ms OFF (12900, 17610, 'UDK_01')
- neg_10 100 ms OFF (0, 9510, 'UDK_03')
- neg_10 1000 ms OFF (0, 9510, 'UDK_03')

Flagged for review (55): not 'expected_vad_correction', or an OFF-only segment that alerted
- ('mix_clip_01_clean', 1000, 'segment_only_off', (19050, 23400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 20, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 100, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 1000, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 20, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 100, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 1000, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 20, 'segment_only_off', (24300, 29190), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 20, 'segment_only_off', (24300, 29250), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 20, 'segment_only_off', (24300, 29280), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 100, 'segment_only_off', (24300, 29190), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 100, 'segment_only_off', (24300, 29220), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 100, 'segment_only_off', (24300, 29250), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 1000, 'segment_only_off', (24300, 29220), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_12_noisy', 20, 'segment_only_off', (21630, 26490), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 20, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 100, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 1000, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_17_muffled', 20, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_17_muffled', 100, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_17_muffled', 1000, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_19_muffled', 20, 'segment_only_off', (6510, 10950), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 100, 'segment_only_off', (6510, 10920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 100, 'segment_only_off', (6510, 10950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_19_muffled', 1000, 'segment_only_off', (6510, 10920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 20, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 20, 'segment_only_off', (12900, 17610), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_21_clean', 100, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 1000, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 20, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 100, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 1000, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 20, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 100, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 1000, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_29_clean', 20, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_29_clean', 100, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_29_clean', 1000, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 20, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 100, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 1000, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('pos_01', 100, 'segment_only_off', (17460, 28440), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('pos_01', 1000, 'segment_only_off', (17460, 28440), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('pos_02', 100, 'segment_only_off', (26940, 37920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('pos_02', 100, 'segment_only_off', (36420, 47400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('pos_02', 1000, 'segment_only_off', (26940, 37920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('pos_02', 1000, 'segment_only_off', (36420, 47400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('pos_04', 100, 'same_segment_different_output', (17580, 28560), 'stt_nondeterminism', None, ['whisper_text', 'whisper_meta'])
- ('pos_04', 1000, 'same_segment_different_output', (17580, 28560), 'stt_nondeterminism', None, ['whisper_text', 'whisper_meta'])
- ('neg_03', 100, 'same_segment_different_output', (36450, 47430), 'stt_nondeterminism', None, ['whisper_text', 'whisper_meta'])
- ('neg_03', 1000, 'same_segment_different_output', (36450, 47430), 'stt_nondeterminism', None, ['whisper_text', 'whisper_meta'])
- ('neg_05', 100, 'same_segment_different_output', (26940, 37920), 'stt_nondeterminism', None, ['whisper_text', 'whisper_meta'])
- ('neg_05', 1000, 'same_segment_different_output', (26940, 37920), 'stt_nondeterminism', None, ['whisper_text', 'whisper_meta'])
- ('neg_10', 100, 'segment_only_off', (0, 9480), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('neg_10', 1000, 'segment_only_off', (0, 9480), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)

Performance (per recording x chunk, repeat 0): live-loop call latency and totals
| Recording | Chunk | Mode | Calls | p50 ms | p95 ms | max ms | Total s | Wall s | CPU s | Components s | GPU peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mix_clip_01_clean | 20 | OFF | 1501 | 15.13 | 20.13 | 971.21 | 24.576 | 24.586 | 16.588 | {'whisper.transcribe': 0.705, 'parakeet.transcribe': 0.708, 'beats.label_probs': 0.53, 'beats.score': 0.101} | 3705.6 |
| mix_clip_01_clean | 20 | ON | 1501 | 11.17 | 15.8 | 582.11 | 16.783 | 16.793 | 10.586 | {'whisper.transcribe': 0.205, 'parakeet.transcribe': 0.051, 'beats.label_probs': 0.127, 'beats.score': 0.022} | 3705.6 |
| mix_clip_01_clean | 100 | OFF | 301 | 6.76 | 11.47 | 424.87 | 3.409 | 3.411 | 4.638 | {'whisper.transcribe': 0.628, 'parakeet.transcribe': 0.395, 'beats.label_probs': 0.183, 'beats.score': 0.091} | 3705.6 |
| mix_clip_01_clean | 100 | ON | 301 | 4.27 | 7.86 | 369.95 | 1.856 | 1.858 | 1.604 | {'whisper.transcribe': 0.141, 'parakeet.transcribe': 0.042, 'beats.label_probs': 0.121, 'beats.score': 0.021} | 3705.6 |
| mix_clip_01_clean | 1000 | OFF | 31 | 4.74 | 9.63 | 431.45 | 0.865 | 0.866 | 1.875 | {'whisper.transcribe': 0.289, 'parakeet.transcribe': 0.19, 'beats.label_probs': 0.141, 'beats.score': 0.046} | 3705.6 |
| mix_clip_01_clean | 1000 | ON | 31 | 3.35 | 6.22 | 359.51 | 0.468 | 0.468 | 0.983 | {'whisper.transcribe': 0.145, 'parakeet.transcribe': 0.039, 'beats.label_probs': 0.112, 'beats.score': 0.022} | 3705.6 |
| mix_clip_02_noisy | 20 | OFF | 1501 | 13.02 | 19.88 | 835.09 | 22.265 | 22.273 | 19.519 | {'whisper.transcribe': 1.29, 'parakeet.transcribe': 0.768, 'beats.label_probs': 1.116, 'beats.score': 0.116} | 3705.7 |
| mix_clip_02_noisy | 20 | ON | 1501 | 10.81 | 16.23 | 812.49 | 18.702 | 18.71 | 15.067 | {'whisper.transcribe': 0.991, 'parakeet.transcribe': 0.571, 'beats.label_probs': 1.013, 'beats.score': 0.073} | 3705.7 |
| mix_clip_02_noisy | 100 | OFF | 301 | 7.31 | 12.39 | 759.52 | 5.251 | 5.253 | 8.58 | {'whisper.transcribe': 1.074, 'parakeet.transcribe': 0.709, 'beats.label_probs': 1.113, 'beats.score': 0.12} | 3705.7 |
| mix_clip_02_noisy | 100 | ON | 301 | 4.55 | 8.42 | 742.08 | 4.059 | 4.061 | 6.352 | {'whisper.transcribe': 0.815, 'parakeet.transcribe': 0.553, 'beats.label_probs': 1.038, 'beats.score': 0.068} | 3705.7 |
| mix_clip_02_noisy | 1000 | OFF | 31 | 6.34 | 432.67 | 736.73 | 2.646 | 2.647 | 5.721 | {'whisper.transcribe': 0.791, 'parakeet.transcribe': 0.535, 'beats.label_probs': 1.029, 'beats.score': 0.068} | 3705.7 |
| mix_clip_02_noisy | 1000 | ON | 31 | 3.74 | 443.27 | 737.45 | 2.628 | 2.629 | 5.675 | {'whisper.transcribe': 0.817, 'parakeet.transcribe': 0.542, 'beats.label_probs': 1.019, 'beats.score': 0.07} | 3705.7 |
| mix_clip_03_muffled | 20 | OFF | 1501 | 13.11 | 19.35 | 458.39 | 20.53 | 20.538 | 15.913 | {'whisper.transcribe': 0.696, 'parakeet.transcribe': 0.459, 'beats.label_probs': 0.238, 'beats.score': 0.115} | 3705.7 |
| mix_clip_03_muffled | 20 | ON | 1501 | 11.14 | 15.66 | 796.8 | 16.887 | 16.895 | 10.488 | {'whisper.transcribe': 0.207, 'parakeet.transcribe': 0.041, 'beats.label_probs': 0.152, 'beats.score': 0.022} | 3705.7 |
| mix_clip_03_muffled | 100 | OFF | 301 | 7.0 | 11.8 | 438.68 | 3.489 | 3.491 | 4.572 | {'whisper.transcribe': 0.629, 'parakeet.transcribe': 0.371, 'beats.label_probs': 0.201, 'beats.score': 0.089} | 3705.7 |
| mix_clip_03_muffled | 100 | ON | 301 | 4.45 | 8.15 | 471.11 | 1.999 | 2.001 | 1.727 | {'whisper.transcribe': 0.21, 'parakeet.transcribe': 0.047, 'beats.label_probs': 0.143, 'beats.score': 0.026} | 3705.7 |
| mix_clip_03_muffled | 1000 | OFF | 31 | 5.5 | 9.27 | 456.4 | 0.891 | 0.891 | 1.916 | {'whisper.transcribe': 0.285, 'parakeet.transcribe': 0.182, 'beats.label_probs': 0.167, 'beats.score': 0.046} | 3705.7 |
| mix_clip_03_muffled | 1000 | ON | 31 | 3.55 | 3.95 | 395.56 | 0.503 | 0.503 | 1.034 | {'whisper.transcribe': 0.146, 'parakeet.transcribe': 0.036, 'beats.label_probs': 0.143, 'beats.score': 0.022} | 3705.7 |
| mix_clip_04_overlapping | 20 | OFF | 1501 | 13.05 | 19.42 | 476.62 | 20.116 | 20.124 | 14.875 | {'whisper.transcribe': 0.488, 'parakeet.transcribe': 0.24, 'beats.label_probs': 0.413, 'beats.score': 0.072} | 3705.8 |
| mix_clip_04_overlapping | 20 | ON | 1501 | 11.02 | 15.95 | 512.97 | 16.752 | 16.76 | 10.314 | {'whisper.transcribe': 0.238, 'parakeet.transcribe': 0.098, 'beats.label_probs': 0.136, 'beats.score': 0.023} | 3705.7 |
| mix_clip_04_overlapping | 100 | OFF | 301 | 7.0 | 11.64 | 521.28 | 3.433 | 3.435 | 4.288 | {'whisper.transcribe': 0.558, 'parakeet.transcribe': 0.228, 'beats.label_probs': 0.415, 'beats.score': 0.066} | 3705.8 |
| mix_clip_04_overlapping | 100 | ON | 301 | 4.34 | 7.78 | 432.45 | 1.91 | 1.911 | 1.679 | {'whisper.transcribe': 0.159, 'parakeet.transcribe': 0.095, 'beats.label_probs': 0.141, 'beats.score': 0.023} | 3705.7 |
| mix_clip_04_overlapping | 1000 | OFF | 31 | 5.7 | 10.01 | 440.61 | 0.616 | 0.617 | 1.149 | {'whisper.transcribe': 0.16, 'parakeet.transcribe': 0.107, 'beats.label_probs': 0.138, 'beats.score': 0.021} | 3705.7 |
| mix_clip_04_overlapping | 1000 | ON | 31 | 3.51 | 3.94 | 436.0 | 0.539 | 0.539 | 1.082 | {'whisper.transcribe': 0.161, 'parakeet.transcribe': 0.095, 'beats.label_probs': 0.14, 'beats.score': 0.022} | 3705.7 |
| mix_clip_05_clean | 20 | OFF | 1501 | 12.39 | 18.96 | 422.79 | 19.403 | 19.41 | 14.294 | {'whisper.transcribe': 0.481, 'parakeet.transcribe': 0.279, 'beats.label_probs': 0.16, 'beats.score': 0.069} | 3705.6 |
| mix_clip_05_clean | 20 | ON | 1501 | 10.76 | 15.87 | 438.66 | 16.151 | 16.159 | 10.057 | {'whisper.transcribe': 0.197, 'parakeet.transcribe': 0.054, 'beats.label_probs': 0.113, 'beats.score': 0.024} | 3705.6 |
| mix_clip_05_clean | 100 | OFF | 301 | 6.5 | 11.36 | 412.35 | 3.103 | 3.105 | 3.873 | {'whisper.transcribe': 0.481, 'parakeet.transcribe': 0.304, 'beats.label_probs': 0.165, 'beats.score': 0.066} | 3705.6 |
| mix_clip_05_clean | 100 | ON | 301 | 4.31 | 8.04 | 435.1 | 1.909 | 1.911 | 1.66 | {'whisper.transcribe': 0.189, 'parakeet.transcribe': 0.053, 'beats.label_probs': 0.125, 'beats.score': 0.023} | 3705.6 |
| mix_clip_05_clean | 1000 | OFF | 31 | 5.84 | 10.02 | 425.95 | 0.865 | 0.865 | 1.871 | {'whisper.transcribe': 0.277, 'parakeet.transcribe': 0.183, 'beats.label_probs': 0.143, 'beats.score': 0.047} | 3705.6 |
| mix_clip_05_clean | 1000 | ON | 31 | 3.66 | 5.95 | 371.44 | 0.481 | 0.482 | 0.993 | {'whisper.transcribe': 0.144, 'parakeet.transcribe': 0.04, 'beats.label_probs': 0.12, 'beats.score': 0.023} | 3705.6 |
| mix_clip_06_noisy | 20 | OFF | 1501 | 12.8 | 19.97 | 594.51 | 21.398 | 21.406 | 18.144 | {'whisper.transcribe': 1.213, 'parakeet.transcribe': 0.583, 'beats.label_probs': 0.636, 'beats.score': 0.046} | 3705.7 |
| mix_clip_06_noisy | 20 | ON | 1501 | 11.09 | 16.03 | 580.12 | 17.428 | 17.436 | 12.13 | {'whisper.transcribe': 0.549, 'parakeet.transcribe': 0.293, 'beats.label_probs': 0.415, 'beats.score': 0.023} | 3705.7 |
| mix_clip_06_noisy | 100 | OFF | 301 | 7.2 | 12.92 | 511.03 | 3.955 | 3.957 | 5.773 | {'whisper.transcribe': 0.708, 'parakeet.transcribe': 0.364, 'beats.label_probs': 0.565, 'beats.score': 0.044} | 3705.7 |
| mix_clip_06_noisy | 100 | ON | 301 | 4.52 | 8.12 | 519.87 | 2.778 | 2.78 | 3.607 | {'whisper.transcribe': 0.43, 'parakeet.transcribe': 0.289, 'beats.label_probs': 0.431, 'beats.score': 0.021} | 3705.7 |
| mix_clip_06_noisy | 1000 | OFF | 31 | 5.6 | 396.74 | 503.63 | 1.73 | 1.731 | 3.946 | {'whisper.transcribe': 0.584, 'parakeet.transcribe': 0.313, 'beats.label_probs': 0.53, 'beats.score': 0.043} | 3705.7 |
| mix_clip_06_noisy | 1000 | ON | 31 | 3.66 | 252.84 | 507.22 | 1.296 | 1.296 | 2.925 | {'whisper.transcribe': 0.435, 'parakeet.transcribe': 0.278, 'beats.label_probs': 0.406, 'beats.score': 0.021} | 3705.7 |
| mix_clip_07_muffled | 20 | OFF | 1501 | 11.97 | 18.81 | 534.78 | 20.087 | 20.095 | 16.74 | {'whisper.transcribe': 0.958, 'parakeet.transcribe': 0.524, 'beats.label_probs': 0.584, 'beats.score': 0.135} | 3705.8 |
| mix_clip_07_muffled | 20 | ON | 1501 | 10.86 | 15.4 | 519.3 | 16.11 | 16.118 | 9.977 | {'whisper.transcribe': 0.203, 'parakeet.transcribe': 0.092, 'beats.label_probs': 0.143, 'beats.score': 0.024} | 3705.8 |
| mix_clip_07_muffled | 100 | OFF | 301 | 6.02 | 12.17 | 468.82 | 4.097 | 4.099 | 6.579 | {'whisper.transcribe': 0.899, 'parakeet.transcribe': 0.474, 'beats.label_probs': 0.54, 'beats.score': 0.138} | 3705.8 |
| mix_clip_07_muffled | 100 | ON | 301 | 4.47 | 8.22 | 473.78 | 2.008 | 2.01 | 1.727 | {'whisper.transcribe': 0.147, 'parakeet.transcribe': 0.119, 'beats.label_probs': 0.137, 'beats.score': 0.02} | 3705.8 |
| mix_clip_07_muffled | 1000 | OFF | 31 | 4.84 | 286.15 | 438.83 | 1.294 | 1.295 | 2.887 | {'whisper.transcribe': 0.427, 'parakeet.transcribe': 0.285, 'beats.label_probs': 0.284, 'beats.score': 0.066} | 3705.8 |
| mix_clip_07_muffled | 1000 | ON | 31 | 3.47 | 4.1 | 449.89 | 0.559 | 0.559 | 1.079 | {'whisper.transcribe': 0.146, 'parakeet.transcribe': 0.092, 'beats.label_probs': 0.14, 'beats.score': 0.021} | 3705.8 |
| mix_clip_08_overlapping | 20 | OFF | 1501 | 12.49 | 18.86 | 485.35 | 19.863 | 19.871 | 15.762 | {'whisper.transcribe': 0.715, 'parakeet.transcribe': 0.432, 'beats.label_probs': 0.257, 'beats.score': 0.113} | 3705.8 |
| mix_clip_08_overlapping | 20 | ON | 1501 | 10.58 | 15.14 | 562.44 | 15.891 | 15.899 | 10.004 | {'whisper.transcribe': 0.244, 'parakeet.transcribe': 0.113, 'beats.label_probs': 0.163, 'beats.score': 0.023} | 3705.8 |
| mix_clip_08_overlapping | 100 | OFF | 301 | 6.69 | 11.1 | 464.72 | 3.151 | 3.153 | 3.92 | {'whisper.transcribe': 0.504, 'parakeet.transcribe': 0.299, 'beats.label_probs': 0.21, 'beats.score': 0.067} | 3705.8 |
| mix_clip_08_overlapping | 100 | ON | 301 | 4.3 | 7.64 | 538.69 | 1.998 | 2.0 | 1.808 | {'whisper.transcribe': 0.238, 'parakeet.transcribe': 0.102, 'beats.label_probs': 0.163, 'beats.score': 0.022} | 3705.8 |
| mix_clip_08_overlapping | 1000 | OFF | 31 | 6.03 | 9.76 | 449.64 | 0.893 | 0.893 | 1.929 | {'whisper.transcribe': 0.305, 'parakeet.transcribe': 0.186, 'beats.label_probs': 0.174, 'beats.score': 0.045} | 3705.8 |
| mix_clip_08_overlapping | 1000 | ON | 31 | 3.48 | 6.36 | 444.91 | 0.552 | 0.552 | 1.091 | {'whisper.transcribe': 0.164, 'parakeet.transcribe': 0.095, 'beats.label_probs': 0.152, 'beats.score': 0.021} | 3705.8 |
| mix_clip_09_clean | 20 | OFF | 1501 | 11.94 | 18.5 | 528.05 | 18.943 | 18.951 | 14.461 | {'whisper.transcribe': 0.697, 'parakeet.transcribe': 0.37, 'beats.label_probs': 0.21, 'beats.score': 0.093} | 3705.7 |
| mix_clip_09_clean | 20 | ON | 1501 | 10.74 | 15.36 | 491.18 | 15.991 | 15.999 | 9.946 | {'whisper.transcribe': 0.206, 'parakeet.transcribe': 0.058, 'beats.label_probs': 0.145, 'beats.score': 0.025} | 3705.7 |
| mix_clip_09_clean | 100 | OFF | 301 | 6.13 | 10.9 | 443.71 | 2.989 | 2.991 | 3.717 | {'whisper.transcribe': 0.478, 'parakeet.transcribe': 0.274, 'beats.label_probs': 0.185, 'beats.score': 0.067} | 3705.7 |
| mix_clip_09_clean | 100 | ON | 301 | 4.22 | 7.52 | 426.07 | 1.867 | 1.869 | 1.658 | {'whisper.transcribe': 0.169, 'parakeet.transcribe': 0.044, 'beats.label_probs': 0.144, 'beats.score': 0.021} | 3705.7 |
| mix_clip_09_clean | 1000 | OFF | 31 | 4.94 | 8.98 | 458.3 | 0.894 | 0.894 | 1.91 | {'whisper.transcribe': 0.29, 'parakeet.transcribe': 0.18, 'beats.label_probs': 0.172, 'beats.score': 0.047} | 3705.7 |
| mix_clip_09_clean | 1000 | ON | 31 | 3.21 | 5.45 | 395.09 | 0.494 | 0.495 | 1.031 | {'whisper.transcribe': 0.145, 'parakeet.transcribe': 0.038, 'beats.label_probs': 0.143, 'beats.score': 0.024} | 3705.7 |
| mix_clip_10_noisy | 20 | OFF | 1501 | 13.37 | 19.45 | 515.65 | 20.809 | 20.817 | 16.193 | {'whisper.transcribe': 0.905, 'parakeet.transcribe': 0.407, 'beats.label_probs': 0.331, 'beats.score': 0.09} | 3705.8 |
| mix_clip_10_noisy | 20 | ON | 1501 | 10.55 | 15.3 | 519.44 | 16.557 | 16.565 | 11.605 | {'whisper.transcribe': 0.561, 'parakeet.transcribe': 0.286, 'beats.label_probs': 0.262, 'beats.score': 0.045} | 3705.8 |
| mix_clip_10_noisy | 100 | OFF | 301 | 6.72 | 12.04 | 463.59 | 3.446 | 3.448 | 4.68 | {'whisper.transcribe': 0.583, 'parakeet.transcribe': 0.38, 'beats.label_probs': 0.277, 'beats.score': 0.066} | 3705.8 |
| mix_clip_10_noisy | 100 | ON | 301 | 4.29 | 7.9 | 456.98 | 2.552 | 2.556 | 3.339 | {'whisper.transcribe': 0.427, 'parakeet.transcribe': 0.292, 'beats.label_probs': 0.251, 'beats.score': 0.042} | 3705.8 |
| mix_clip_10_noisy | 1000 | OFF | 31 | 5.37 | 276.68 | 438.7 | 1.224 | 1.225 | 2.761 | {'whisper.transcribe': 0.44, 'parakeet.transcribe': 0.277, 'beats.label_probs': 0.252, 'beats.score': 0.043} | 3705.8 |
| mix_clip_10_noisy | 1000 | ON | 31 | 3.35 | 273.67 | 441.07 | 1.16 | 1.161 | 2.705 | {'whisper.transcribe': 0.436, 'parakeet.transcribe': 0.279, 'beats.label_probs': 0.251, 'beats.score': 0.042} | 3705.8 |
| mix_clip_11_muffled | 20 | OFF | 1501 | 11.9 | 18.52 | 497.4 | 19.807 | 19.815 | 16.469 | {'whisper.transcribe': 0.944, 'parakeet.transcribe': 0.592, 'beats.label_probs': 0.389, 'beats.score': 0.149} | 3705.6 |
| mix_clip_11_muffled | 20 | ON | 1501 | 10.62 | 15.41 | 444.83 | 15.832 | 15.84 | 9.912 | {'whisper.transcribe': 0.197, 'parakeet.transcribe': 0.053, 'beats.label_probs': 0.122, 'beats.score': 0.022} | 3705.6 |
| mix_clip_11_muffled | 100 | OFF | 301 | 6.64 | 11.49 | 413.64 | 3.687 | 3.689 | 5.437 | {'whisper.transcribe': 0.733, 'parakeet.transcribe': 0.466, 'beats.label_probs': 0.309, 'beats.score': 0.112} | 3705.6 |
| mix_clip_11_muffled | 100 | ON | 301 | 4.34 | 7.73 | 437.33 | 1.881 | 1.883 | 1.656 | {'whisper.transcribe': 0.197, 'parakeet.transcribe': 0.049, 'beats.label_probs': 0.123, 'beats.score': 0.023} | 3705.6 |
| mix_clip_11_muffled | 1000 | OFF | 31 | 5.1 | 11.91 | 420.02 | 0.854 | 0.855 | 1.842 | {'whisper.transcribe': 0.286, 'parakeet.transcribe': 0.179, 'beats.label_probs': 0.137, 'beats.score': 0.045} | 3705.6 |
| mix_clip_11_muffled | 1000 | ON | 31 | 3.44 | 6.37 | 374.18 | 0.48 | 0.48 | 0.989 | {'whisper.transcribe': 0.15, 'parakeet.transcribe': 0.037, 'beats.label_probs': 0.125, 'beats.score': 0.021} | 3705.6 |
| mix_clip_12_noisy | 20 | OFF | 1501 | 12.83 | 19.28 | 553.31 | 20.02 | 20.028 | 15.946 | {'whisper.transcribe': 0.863, 'parakeet.transcribe': 0.459, 'beats.label_probs': 0.303, 'beats.score': 0.087} | 3705.8 |
| mix_clip_12_noisy | 20 | ON | 1501 | 10.8 | 15.71 | 533.67 | 16.883 | 16.891 | 11.697 | {'whisper.transcribe': 0.557, 'parakeet.transcribe': 0.301, 'beats.label_probs': 0.239, 'beats.score': 0.047} | 3705.8 |
| mix_clip_12_noisy | 100 | OFF | 301 | 6.53 | 12.44 | 446.68 | 3.686 | 3.688 | 5.407 | {'whisper.transcribe': 0.719, 'parakeet.transcribe': 0.463, 'beats.label_probs': 0.269, 'beats.score': 0.091} | 3705.8 |
| mix_clip_12_noisy | 100 | ON | 301 | 4.58 | 8.27 | 434.58 | 2.54 | 2.544 | 3.259 | {'whisper.transcribe': 0.416, 'parakeet.transcribe': 0.272, 'beats.label_probs': 0.225, 'beats.score': 0.042} | 3705.8 |
| mix_clip_12_noisy | 1000 | OFF | 31 | 5.96 | 272.29 | 431.55 | 1.183 | 1.184 | 2.722 | {'whisper.transcribe': 0.415, 'parakeet.transcribe': 0.278, 'beats.label_probs': 0.23, 'beats.score': 0.043} | 3705.8 |
| mix_clip_12_noisy | 1000 | ON | 31 | 3.26 | 263.67 | 438.28 | 1.123 | 1.124 | 2.673 | {'whisper.transcribe': 0.426, 'parakeet.transcribe': 0.275, 'beats.label_probs': 0.226, 'beats.score': 0.041} | 3705.8 |
| mix_clip_13_clean | 20 | OFF | 1501 | 12.31 | 18.25 | 483.87 | 19.005 | 19.012 | 14.731 | {'whisper.transcribe': 0.655, 'parakeet.transcribe': 0.358, 'beats.label_probs': 0.189, 'beats.score': 0.11} | 3705.6 |
| mix_clip_13_clean | 20 | ON | 1501 | 10.31 | 14.92 | 466.13 | 15.436 | 15.443 | 9.754 | {'whisper.transcribe': 0.2, 'parakeet.transcribe': 0.07, 'beats.label_probs': 0.12, 'beats.score': 0.023} | 3705.6 |
| mix_clip_13_clean | 100 | OFF | 301 | 6.52 | 11.23 | 415.45 | 3.055 | 3.056 | 3.701 | {'whisper.transcribe': 0.48, 'parakeet.transcribe': 0.266, 'beats.label_probs': 0.165, 'beats.score': 0.067} | 3705.6 |
| mix_clip_13_clean | 100 | ON | 301 | 4.36 | 7.78 | 418.71 | 1.898 | 1.9 | 1.64 | {'whisper.transcribe': 0.198, 'parakeet.transcribe': 0.042, 'beats.label_probs': 0.113, 'beats.score': 0.022} | 3705.6 |
| mix_clip_13_clean | 1000 | OFF | 31 | 6.28 | 15.94 | 423.25 | 0.866 | 0.867 | 1.863 | {'whisper.transcribe': 0.273, 'parakeet.transcribe': 0.187, 'beats.label_probs': 0.142, 'beats.score': 0.041} | 3705.6 |
| mix_clip_13_clean | 1000 | ON | 31 | 3.45 | 6.44 | 354.11 | 0.458 | 0.459 | 0.959 | {'whisper.transcribe': 0.141, 'parakeet.transcribe': 0.036, 'beats.label_probs': 0.115, 'beats.score': 0.021} | 3705.6 |
| mix_clip_14_noisy | 20 | OFF | 1501 | 12.6 | 19.24 | 805.97 | 20.999 | 21.007 | 17.197 | {'whisper.transcribe': 1.02, 'parakeet.transcribe': 0.506, 'beats.label_probs': 0.828, 'beats.score': 0.097} | 3726.3 |
| mix_clip_14_noisy | 20 | ON | 1501 | 10.9 | 15.78 | 761.79 | 17.914 | 17.923 | 13.537 | {'whisper.transcribe': 0.863, 'parakeet.transcribe': 0.434, 'beats.label_probs': 0.724, 'beats.score': 0.073} | 3723.0 |
| mix_clip_14_noisy | 100 | OFF | 301 | 7.19 | 12.08 | 695.6 | 4.397 | 4.399 | 6.433 | {'whisper.transcribe': 0.812, 'parakeet.transcribe': 0.541, 'beats.label_probs': 0.774, 'beats.score': 0.09} | 3726.3 |
| mix_clip_14_noisy | 100 | ON | 301 | 4.6 | 8.33 | 729.39 | 3.502 | 3.504 | 5.123 | {'whisper.transcribe': 0.681, 'parakeet.transcribe': 0.431, 'beats.label_probs': 0.755, 'beats.score': 0.07} | 3723.0 |
| mix_clip_14_noisy | 1000 | OFF | 31 | 6.23 | 625.04 | 716.34 | 2.862 | 2.862 | 6.029 | {'whisper.transcribe': 0.838, 'parakeet.transcribe': 0.573, 'beats.label_probs': 1.17, 'beats.score': 0.074} | 3725.1 |
| mix_clip_14_noisy | 1000 | ON | 31 | 3.59 | 362.2 | 702.49 | 2.042 | 2.042 | 4.437 | {'whisper.transcribe': 0.675, 'parakeet.transcribe': 0.43, 'beats.label_probs': 0.736, 'beats.score': 0.072} | 3723.0 |
| mix_clip_15_muffled | 20 | OFF | 1501 | 12.15 | 18.52 | 503.06 | 19.461 | 19.469 | 15.543 | {'whisper.transcribe': 0.798, 'parakeet.transcribe': 0.449, 'beats.label_probs': 0.234, 'beats.score': 0.113} | 3705.8 |
| mix_clip_15_muffled | 20 | ON | 1501 | 10.49 | 15.24 | 501.81 | 15.788 | 15.796 | 9.889 | {'whisper.transcribe': 0.197, 'parakeet.transcribe': 0.089, 'beats.label_probs': 0.14, 'beats.score': 0.023} | 3705.8 |
| mix_clip_15_muffled | 100 | OFF | 301 | 6.7 | 11.49 | 442.12 | 3.372 | 3.374 | 4.59 | {'whisper.transcribe': 0.604, 'parakeet.transcribe': 0.376, 'beats.label_probs': 0.206, 'beats.score': 0.091} | 3705.8 |
| mix_clip_15_muffled | 100 | ON | 301 | 4.45 | 7.84 | 482.67 | 2.009 | 2.011 | 1.723 | {'whisper.transcribe': 0.189, 'parakeet.transcribe': 0.09, 'beats.label_probs': 0.137, 'beats.score': 0.022} | 3705.8 |
| mix_clip_15_muffled | 1000 | OFF | 31 | 5.56 | 274.66 | 416.74 | 1.115 | 1.115 | 2.634 | {'whisper.transcribe': 0.413, 'parakeet.transcribe': 0.263, 'beats.label_probs': 0.173, 'beats.score': 0.064} | 3705.8 |
| mix_clip_15_muffled | 1000 | ON | 31 | 3.12 | 6.23 | 429.46 | 0.53 | 0.53 | 1.054 | {'whisper.transcribe': 0.146, 'parakeet.transcribe': 0.088, 'beats.label_probs': 0.132, 'beats.score': 0.022} | 3705.8 |
| mix_clip_16_overlapping | 20 | OFF | 1501 | 11.93 | 18.41 | 595.13 | 19.119 | 19.126 | 15.366 | {'whisper.transcribe': 0.847, 'parakeet.transcribe': 0.46, 'beats.label_probs': 0.248, 'beats.score': 0.133} | 3705.9 |
| mix_clip_16_overlapping | 20 | ON | 1501 | 10.2 | 14.73 | 575.67 | 15.563 | 15.571 | 9.903 | {'whisper.transcribe': 0.248, 'parakeet.transcribe': 0.07, 'beats.label_probs': 0.195, 'beats.score': 0.022} | 3705.9 |
| mix_clip_16_overlapping | 100 | OFF | 301 | 6.67 | 11.76 | 506.73 | 3.212 | 3.214 | 3.89 | {'whisper.transcribe': 0.498, 'parakeet.transcribe': 0.307, 'beats.label_probs': 0.208, 'beats.score': 0.068} | 3705.9 |
| mix_clip_16_overlapping | 100 | ON | 301 | 4.58 | 8.33 | 460.21 | 2.01 | 2.012 | 1.718 | {'whisper.transcribe': 0.174, 'parakeet.transcribe': 0.057, 'beats.label_probs': 0.158, 'beats.score': 0.022} | 3705.9 |
| mix_clip_16_overlapping | 1000 | OFF | 31 | 5.24 | 8.48 | 517.44 | 0.954 | 0.954 | 1.99 | {'whisper.transcribe': 0.315, 'parakeet.transcribe': 0.196, 'beats.label_probs': 0.187, 'beats.score': 0.044} | 3705.9 |
| mix_clip_16_overlapping | 1000 | ON | 31 | 3.35 | 4.22 | 452.3 | 0.559 | 0.559 | 1.098 | {'whisper.transcribe': 0.177, 'parakeet.transcribe': 0.053, 'beats.label_probs': 0.156, 'beats.score': 0.023} | 3705.9 |
| mix_clip_17_muffled | 20 | OFF | 1501 | 14.16 | 20.41 | 428.99 | 22.017 | 22.026 | 16.623 | {'whisper.transcribe': 0.704, 'parakeet.transcribe': 0.496, 'beats.label_probs': 0.247, 'beats.score': 0.111} | 3705.7 |
| mix_clip_17_muffled | 20 | ON | 1501 | 11.7 | 17.0 | 494.01 | 17.551 | 17.56 | 10.608 | {'whisper.transcribe': 0.19, 'parakeet.transcribe': 0.107, 'beats.label_probs': 0.153, 'beats.score': 0.024} | 3705.7 |
| mix_clip_17_muffled | 100 | OFF | 301 | 7.79 | 12.97 | 426.1 | 4.044 | 4.046 | 5.574 | {'whisper.transcribe': 0.775, 'parakeet.transcribe': 0.529, 'beats.label_probs': 0.239, 'beats.score': 0.116} | 3705.7 |
| mix_clip_17_muffled | 100 | ON | 301 | 4.98 | 9.22 | 486.2 | 2.196 | 2.198 | 1.81 | {'whisper.transcribe': 0.201, 'parakeet.transcribe': 0.093, 'beats.label_probs': 0.153, 'beats.score': 0.023} | 3705.7 |
| mix_clip_17_muffled | 1000 | OFF | 31 | 6.24 | 293.13 | 433.47 | 1.326 | 1.326 | 2.948 | {'whisper.transcribe': 0.438, 'parakeet.transcribe': 0.284, 'beats.label_probs': 0.323, 'beats.score': 0.072} | 3705.7 |
| mix_clip_17_muffled | 1000 | ON | 31 | 3.71 | 7.51 | 429.45 | 0.546 | 0.546 | 1.069 | {'whisper.transcribe': 0.15, 'parakeet.transcribe': 0.092, 'beats.label_probs': 0.148, 'beats.score': 0.023} | 3705.7 |
| mix_clip_18_noisy | 20 | OFF | 1501 | 13.57 | 21.54 | 861.84 | 23.23 | 23.239 | 19.137 | {'whisper.transcribe': 1.148, 'parakeet.transcribe': 0.672, 'beats.label_probs': 1.122, 'beats.score': 0.099} | 3705.7 |
| mix_clip_18_noisy | 20 | ON | 1501 | 11.6 | 17.38 | 942.11 | 19.591 | 19.6 | 14.733 | {'whisper.transcribe': 0.941, 'parakeet.transcribe': 0.485, 'beats.label_probs': 1.098, 'beats.score': 0.046} | 3705.7 |
| mix_clip_18_noisy | 100 | OFF | 301 | 7.39 | 12.75 | 750.35 | 4.988 | 4.99 | 7.664 | {'whisper.transcribe': 0.888, 'parakeet.transcribe': 0.634, 'beats.label_probs': 1.035, 'beats.score': 0.094} | 3705.7 |
| mix_clip_18_noisy | 100 | ON | 301 | 4.79 | 8.89 | 865.77 | 3.987 | 3.989 | 5.698 | {'whisper.transcribe': 0.708, 'parakeet.transcribe': 0.471, 'beats.label_probs': 1.055, 'beats.score': 0.045} | 3705.7 |
| mix_clip_18_noisy | 1000 | OFF | 31 | 7.12 | 491.77 | 739.58 | 2.904 | 2.904 | 6.405 | {'whisper.transcribe': 0.906, 'parakeet.transcribe': 0.619, 'beats.label_probs': 1.013, 'beats.score': 0.103} | 3705.7 |
| mix_clip_18_noisy | 1000 | ON | 31 | 3.74 | 444.34 | 829.57 | 2.423 | 2.423 | 5.012 | {'whisper.transcribe': 0.7, 'parakeet.transcribe': 0.466, 'beats.label_probs': 1.034, 'beats.score': 0.049} | 3705.7 |
| mix_clip_19_muffled | 20 | OFF | 1501 | 12.83 | 18.78 | 471.04 | 20.296 | 20.305 | 15.175 | {'whisper.transcribe': 0.63, 'parakeet.transcribe': 0.403, 'beats.label_probs': 0.3, 'beats.score': 0.094} | 3705.7 |
| mix_clip_19_muffled | 20 | ON | 1501 | 11.17 | 16.37 | 463.25 | 17.048 | 17.057 | 10.317 | {'whisper.transcribe': 0.196, 'parakeet.transcribe': 0.054, 'beats.label_probs': 0.135, 'beats.score': 0.026} | 3705.7 |
| mix_clip_19_muffled | 100 | OFF | 301 | 6.87 | 11.57 | 426.81 | 3.851 | 3.853 | 5.626 | {'whisper.transcribe': 0.759, 'parakeet.transcribe': 0.459, 'beats.label_probs': 0.352, 'beats.score': 0.114} | 3705.7 |
| mix_clip_19_muffled | 100 | ON | 301 | 4.58 | 8.19 | 428.88 | 1.991 | 1.993 | 1.676 | {'whisper.transcribe': 0.202, 'parakeet.transcribe': 0.044, 'beats.label_probs': 0.116, 'beats.score': 0.022} | 3705.7 |
| mix_clip_19_muffled | 1000 | OFF | 31 | 5.25 | 8.93 | 424.0 | 0.847 | 0.847 | 1.863 | {'whisper.transcribe': 0.277, 'parakeet.transcribe': 0.187, 'beats.label_probs': 0.14, 'beats.score': 0.044} | 3705.7 |
| mix_clip_19_muffled | 1000 | ON | 31 | 3.48 | 5.64 | 360.51 | 0.471 | 0.472 | 0.967 | {'whisper.transcribe': 0.142, 'parakeet.transcribe': 0.039, 'beats.label_probs': 0.115, 'beats.score': 0.021} | 3705.7 |
| mix_clip_20_muffled | 20 | OFF | 1501 | 12.32 | 19.87 | 542.97 | 20.849 | 20.858 | 16.873 | {'whisper.transcribe': 0.977, 'parakeet.transcribe': 0.606, 'beats.label_probs': 0.478, 'beats.score': 0.14} | 3705.7 |
| mix_clip_20_muffled | 20 | ON | 1501 | 11.5 | 16.37 | 504.38 | 17.357 | 17.366 | 10.494 | {'whisper.transcribe': 0.224, 'parakeet.transcribe': 0.092, 'beats.label_probs': 0.137, 'beats.score': 0.025} | 3705.7 |
| mix_clip_20_muffled | 100 | OFF | 301 | 6.41 | 11.65 | 433.1 | 3.444 | 3.446 | 4.701 | {'whisper.transcribe': 0.62, 'parakeet.transcribe': 0.398, 'beats.label_probs': 0.313, 'beats.score': 0.09} | 3705.7 |
| mix_clip_20_muffled | 100 | ON | 301 | 4.43 | 8.26 | 502.62 | 2.028 | 2.03 | 1.743 | {'whisper.transcribe': 0.211, 'parakeet.transcribe': 0.095, 'beats.label_probs': 0.155, 'beats.score': 0.023} | 3705.7 |
| mix_clip_20_muffled | 1000 | OFF | 31 | 4.97 | 284.88 | 418.11 | 1.139 | 1.139 | 2.659 | {'whisper.transcribe': 0.43, 'parakeet.transcribe': 0.281, 'beats.label_probs': 0.179, 'beats.score': 0.064} | 3705.7 |
| mix_clip_20_muffled | 1000 | ON | 31 | 3.4 | 6.53 | 430.14 | 0.537 | 0.537 | 1.069 | {'whisper.transcribe': 0.155, 'parakeet.transcribe': 0.099, 'beats.label_probs': 0.134, 'beats.score': 0.023} | 3705.7 |
| mix_clip_21_clean | 20 | OFF | 1501 | 12.81 | 19.45 | 516.07 | 20.446 | 20.454 | 16.23 | {'whisper.transcribe': 0.86, 'parakeet.transcribe': 0.425, 'beats.label_probs': 0.366, 'beats.score': 0.111} | 3705.7 |
| mix_clip_21_clean | 20 | ON | 1501 | 10.81 | 15.93 | 519.13 | 16.463 | 16.471 | 10.226 | {'whisper.transcribe': 0.192, 'parakeet.transcribe': 0.103, 'beats.label_probs': 0.149, 'beats.score': 0.025} | 3705.7 |
| mix_clip_21_clean | 100 | OFF | 301 | 6.76 | 11.57 | 455.9 | 3.139 | 3.141 | 3.863 | {'whisper.transcribe': 0.467, 'parakeet.transcribe': 0.307, 'beats.label_probs': 0.189, 'beats.score': 0.07} | 3705.7 |
| mix_clip_21_clean | 100 | ON | 301 | 4.49 | 8.31 | 500.68 | 2.051 | 2.053 | 1.757 | {'whisper.transcribe': 0.197, 'parakeet.transcribe': 0.089, 'beats.label_probs': 0.147, 'beats.score': 0.023} | 3705.7 |
| mix_clip_21_clean | 1000 | OFF | 31 | 5.88 | 11.82 | 445.51 | 0.882 | 0.883 | 1.902 | {'whisper.transcribe': 0.283, 'parakeet.transcribe': 0.181, 'beats.label_probs': 0.162, 'beats.score': 0.043} | 3705.7 |
| mix_clip_21_clean | 1000 | ON | 31 | 3.47 | 4.01 | 452.19 | 0.559 | 0.559 | 1.065 | {'whisper.transcribe': 0.144, 'parakeet.transcribe': 0.095, 'beats.label_probs': 0.141, 'beats.score': 0.021} | 3705.7 |
| mix_clip_22_clean | 20 | OFF | 1501 | 12.78 | 19.2 | 501.5 | 19.947 | 19.955 | 14.937 | {'whisper.transcribe': 0.657, 'parakeet.transcribe': 0.359, 'beats.label_probs': 0.187, 'beats.score': 0.089} | 3705.6 |
| mix_clip_22_clean | 20 | ON | 1501 | 11.04 | 16.06 | 484.89 | 16.64 | 16.648 | 10.166 | {'whisper.transcribe': 0.19, 'parakeet.transcribe': 0.092, 'beats.label_probs': 0.126, 'beats.score': 0.024} | 3705.6 |
| mix_clip_22_clean | 100 | OFF | 301 | 6.69 | 11.75 | 425.01 | 3.14 | 3.142 | 3.8 | {'whisper.transcribe': 0.502, 'parakeet.transcribe': 0.299, 'beats.label_probs': 0.154, 'beats.score': 0.065} | 3705.6 |
| mix_clip_22_clean | 100 | ON | 301 | 4.61 | 8.24 | 482.24 | 2.009 | 2.011 | 1.728 | {'whisper.transcribe': 0.191, 'parakeet.transcribe': 0.092, 'beats.label_probs': 0.128, 'beats.score': 0.023} | 3705.6 |
| mix_clip_22_clean | 1000 | OFF | 31 | 5.38 | 13.41 | 425.59 | 0.875 | 0.876 | 1.869 | {'whisper.transcribe': 0.282, 'parakeet.transcribe': 0.182, 'beats.label_probs': 0.138, 'beats.score': 0.047} | 3705.6 |
| mix_clip_22_clean | 1000 | ON | 31 | 3.46 | 6.18 | 456.07 | 0.567 | 0.567 | 1.028 | {'whisper.transcribe': 0.165, 'parakeet.transcribe': 0.106, 'beats.label_probs': 0.116, 'beats.score': 0.023} | 3705.6 |
| mix_clip_23_muffled | 20 | OFF | 1501 | 12.67 | 19.44 | 559.39 | 21.654 | 21.662 | 19.318 | {'whisper.transcribe': 1.332, 'parakeet.transcribe': 0.75, 'beats.label_probs': 0.803, 'beats.score': 0.188} | 3705.9 |
| mix_clip_23_muffled | 20 | ON | 1501 | 10.95 | 15.95 | 532.61 | 16.446 | 16.454 | 10.118 | {'whisper.transcribe': 0.227, 'parakeet.transcribe': 0.09, 'beats.label_probs': 0.172, 'beats.score': 0.022} | 3705.9 |
| mix_clip_23_muffled | 100 | OFF | 301 | 7.17 | 11.33 | 464.88 | 3.861 | 3.863 | 5.629 | {'whisper.transcribe': 0.781, 'parakeet.transcribe': 0.539, 'beats.label_probs': 0.287, 'beats.score': 0.117} | 3705.9 |
| mix_clip_23_muffled | 100 | ON | 301 | 4.49 | 7.74 | 501.24 | 2.003 | 2.005 | 1.777 | {'whisper.transcribe': 0.223, 'parakeet.transcribe': 0.075, 'beats.label_probs': 0.163, 'beats.score': 0.023} | 3705.9 |
| mix_clip_23_muffled | 1000 | OFF | 31 | 5.91 | 10.31 | 446.84 | 0.892 | 0.892 | 1.923 | {'whisper.transcribe': 0.298, 'parakeet.transcribe': 0.184, 'beats.label_probs': 0.183, 'beats.score': 0.046} | 3705.9 |
| mix_clip_23_muffled | 1000 | ON | 31 | 3.65 | 7.15 | 420.95 | 0.532 | 0.533 | 1.077 | {'whisper.transcribe': 0.155, 'parakeet.transcribe': 0.054, 'beats.label_probs': 0.174, 'beats.score': 0.024} | 3705.9 |
| mix_clip_24_overlapping | 20 | OFF | 1501 | 12.81 | 19.26 | 644.41 | 21.8 | 21.809 | 18.804 | {'whisper.transcribe': 1.301, 'parakeet.transcribe': 0.718, 'beats.label_probs': 0.794, 'beats.score': 0.17} | 3709.6 |
| mix_clip_24_overlapping | 20 | ON | 1501 | 11.12 | 16.33 | 652.73 | 16.991 | 16.999 | 10.406 | {'whisper.transcribe': 0.291, 'parakeet.transcribe': 0.12, 'beats.label_probs': 0.188, 'beats.score': 0.024} | 3709.6 |
| mix_clip_24_overlapping | 100 | OFF | 301 | 6.7 | 11.63 | 572.57 | 4.724 | 4.726 | 7.438 | {'whisper.transcribe': 1.082, 'parakeet.transcribe': 0.588, 'beats.label_probs': 0.809, 'beats.score': 0.137} | 3709.6 |
| mix_clip_24_overlapping | 100 | ON | 301 | 4.5 | 7.81 | 565.4 | 2.052 | 2.054 | 1.874 | {'whisper.transcribe': 0.192, 'parakeet.transcribe': 0.127, 'beats.label_probs': 0.195, 'beats.score': 0.023} | 3709.6 |
| mix_clip_24_overlapping | 1000 | OFF | 31 | 5.38 | 280.29 | 539.77 | 1.279 | 1.28 | 2.827 | {'whisper.transcribe': 0.471, 'parakeet.transcribe': 0.314, 'beats.label_probs': 0.228, 'beats.score': 0.067} | 3709.6 |
| mix_clip_24_overlapping | 1000 | ON | 31 | 3.38 | 4.46 | 487.07 | 0.589 | 0.589 | 1.155 | {'whisper.transcribe': 0.188, 'parakeet.transcribe': 0.067, 'beats.label_probs': 0.186, 'beats.score': 0.023} | 3709.6 |
| mix_clip_25_clean | 20 | OFF | 1501 | 12.47 | 19.33 | 430.03 | 19.596 | 19.605 | 15.047 | {'whisper.transcribe': 0.609, 'parakeet.transcribe': 0.395, 'beats.label_probs': 0.186, 'beats.score': 0.088} | 3705.7 |
| mix_clip_25_clean | 20 | ON | 1501 | 10.93 | 15.82 | 457.4 | 16.386 | 16.395 | 10.09 | {'whisper.transcribe': 0.205, 'parakeet.transcribe': 0.057, 'beats.label_probs': 0.123, 'beats.score': 0.022} | 3705.7 |
| mix_clip_25_clean | 100 | OFF | 301 | 6.79 | 11.85 | 418.38 | 3.567 | 3.569 | 5.262 | {'whisper.transcribe': 0.74, 'parakeet.transcribe': 0.399, 'beats.label_probs': 0.2, 'beats.score': 0.114} | 3705.7 |
| mix_clip_25_clean | 100 | ON | 301 | 4.55 | 8.09 | 447.18 | 1.958 | 1.96 | 1.696 | {'whisper.transcribe': 0.198, 'parakeet.transcribe': 0.067, 'beats.label_probs': 0.116, 'beats.score': 0.022} | 3705.7 |
| mix_clip_25_clean | 1000 | OFF | 31 | 5.74 | 12.39 | 403.95 | 0.849 | 0.85 | 1.842 | {'whisper.transcribe': 0.276, 'parakeet.transcribe': 0.182, 'beats.label_probs': 0.134, 'beats.score': 0.043} | 3705.7 |
| mix_clip_25_clean | 1000 | ON | 31 | 3.38 | 3.91 | 370.9 | 0.474 | 0.474 | 0.99 | {'whisper.transcribe': 0.142, 'parakeet.transcribe': 0.039, 'beats.label_probs': 0.124, 'beats.score': 0.023} | 3705.7 |
| mix_clip_26_clean | 20 | OFF | 1501 | 12.16 | 18.98 | 524.61 | 19.514 | 19.522 | 14.961 | {'whisper.transcribe': 0.689, 'parakeet.transcribe': 0.367, 'beats.label_probs': 0.215, 'beats.score': 0.091} | 3705.7 |
| mix_clip_26_clean | 20 | ON | 1501 | 10.8 | 16.25 | 463.38 | 16.344 | 16.352 | 10.12 | {'whisper.transcribe': 0.212, 'parakeet.transcribe': 0.054, 'beats.label_probs': 0.147, 'beats.score': 0.023} | 3705.8 |
| mix_clip_26_clean | 100 | OFF | 301 | 6.57 | 11.49 | 448.03 | 3.085 | 3.087 | 3.763 | {'whisper.transcribe': 0.48, 'parakeet.transcribe': 0.286, 'beats.label_probs': 0.195, 'beats.score': 0.066} | 3705.8 |
| mix_clip_26_clean | 100 | ON | 301 | 4.33 | 7.8 | 470.23 | 1.98 | 1.982 | 1.647 | {'whisper.transcribe': 0.226, 'parakeet.transcribe': 0.056, 'beats.label_probs': 0.15, 'beats.score': 0.021} | 3705.8 |
| mix_clip_26_clean | 1000 | OFF | 31 | 4.72 | 274.11 | 425.92 | 1.124 | 1.124 | 2.651 | {'whisper.transcribe': 0.43, 'parakeet.transcribe': 0.27, 'beats.label_probs': 0.188, 'beats.score': 0.067} | 3705.8 |
| mix_clip_26_clean | 1000 | ON | 31 | 3.12 | 4.37 | 368.45 | 0.468 | 0.469 | 0.996 | {'whisper.transcribe': 0.155, 'parakeet.transcribe': 0.04, 'beats.label_probs': 0.138, 'beats.score': 0.023} | 3705.8 |
| mix_clip_27_muffled | 20 | OFF | 1501 | 12.25 | 19.76 | 526.16 | 20.392 | 20.4 | 16.768 | {'whisper.transcribe': 0.968, 'parakeet.transcribe': 0.578, 'beats.label_probs': 0.389, 'beats.score': 0.14} | 3705.8 |
| mix_clip_27_muffled | 20 | ON | 1501 | 11.28 | 16.27 | 502.97 | 17.017 | 17.026 | 10.271 | {'whisper.transcribe': 0.213, 'parakeet.transcribe': 0.055, 'beats.label_probs': 0.152, 'beats.score': 0.023} | 3705.8 |
| mix_clip_27_muffled | 100 | OFF | 301 | 6.44 | 12.07 | 462.19 | 3.751 | 3.753 | 5.506 | {'whisper.transcribe': 0.737, 'parakeet.transcribe': 0.516, 'beats.label_probs': 0.28, 'beats.score': 0.113} | 3705.8 |
| mix_clip_27_muffled | 100 | ON | 301 | 4.44 | 8.12 | 398.85 | 1.939 | 1.941 | 1.655 | {'whisper.transcribe': 0.145, 'parakeet.transcribe': 0.041, 'beats.label_probs': 0.143, 'beats.score': 0.022} | 3705.8 |
| mix_clip_27_muffled | 1000 | OFF | 31 | 4.94 | 16.48 | 442.4 | 0.872 | 0.872 | 1.884 | {'whisper.transcribe': 0.284, 'parakeet.transcribe': 0.178, 'beats.label_probs': 0.152, 'beats.score': 0.046} | 3705.8 |
| mix_clip_27_muffled | 1000 | ON | 31 | 3.11 | 6.63 | 380.72 | 0.484 | 0.484 | 1.004 | {'whisper.transcribe': 0.151, 'parakeet.transcribe': 0.039, 'beats.label_probs': 0.129, 'beats.score': 0.02} | 3705.8 |
| mix_clip_28_overlapping | 20 | OFF | 1501 | 12.97 | 19.1 | 595.85 | 21.702 | 21.71 | 19.113 | {'whisper.transcribe': 1.308, 'parakeet.transcribe': 0.779, 'beats.label_probs': 0.771, 'beats.score': 0.189} | 3708.0 |
| mix_clip_28_overlapping | 20 | ON | 1501 | 10.89 | 15.76 | 632.28 | 16.539 | 16.548 | 10.222 | {'whisper.transcribe': 0.232, 'parakeet.transcribe': 0.117, 'beats.label_probs': 0.198, 'beats.score': 0.025} | 3707.2 |
| mix_clip_28_overlapping | 100 | OFF | 301 | 6.97 | 11.6 | 506.72 | 4.556 | 4.558 | 7.01 | {'whisper.transcribe': 0.977, 'parakeet.transcribe': 0.588, 'beats.label_probs': 0.69, 'beats.score': 0.136} | 3708.0 |
| mix_clip_28_overlapping | 100 | ON | 301 | 4.6 | 8.17 | 569.71 | 2.089 | 2.091 | 1.883 | {'whisper.transcribe': 0.225, 'parakeet.transcribe': 0.118, 'beats.label_probs': 0.176, 'beats.score': 0.023} | 3707.2 |
| mix_clip_28_overlapping | 1000 | OFF | 31 | 5.87 | 9.76 | 506.88 | 0.939 | 0.939 | 2.015 | {'whisper.transcribe': 0.305, 'parakeet.transcribe': 0.186, 'beats.label_probs': 0.216, 'beats.score': 0.044} | 3707.2 |
| mix_clip_28_overlapping | 1000 | ON | 31 | 3.36 | 4.0 | 459.72 | 0.561 | 0.561 | 1.117 | {'whisper.transcribe': 0.167, 'parakeet.transcribe': 0.06, 'beats.label_probs': 0.184, 'beats.score': 0.022} | 3707.2 |
| mix_clip_29_clean | 20 | OFF | 1501 | 12.6 | 18.89 | 486.75 | 20.067 | 20.075 | 16.039 | {'whisper.transcribe': 0.707, 'parakeet.transcribe': 0.483, 'beats.label_probs': 0.355, 'beats.score': 0.112} | 3705.9 |
| mix_clip_29_clean | 20 | ON | 1501 | 10.82 | 15.3 | 513.69 | 16.119 | 16.128 | 10.036 | {'whisper.transcribe': 0.221, 'parakeet.transcribe': 0.055, 'beats.label_probs': 0.165, 'beats.score': 0.023} | 3705.9 |
| mix_clip_29_clean | 100 | OFF | 301 | 6.82 | 11.97 | 468.04 | 3.197 | 3.199 | 3.893 | {'whisper.transcribe': 0.48, 'parakeet.transcribe': 0.277, 'beats.label_probs': 0.205, 'beats.score': 0.065} | 3705.9 |
| mix_clip_29_clean | 100 | ON | 301 | 4.33 | 8.0 | 515.7 | 2.014 | 2.016 | 1.784 | {'whisper.transcribe': 0.226, 'parakeet.transcribe': 0.06, 'beats.label_probs': 0.165, 'beats.score': 0.021} | 3705.9 |
| mix_clip_29_clean | 1000 | OFF | 31 | 5.42 | 9.44 | 475.25 | 0.899 | 0.899 | 1.95 | {'whisper.transcribe': 0.291, 'parakeet.transcribe': 0.182, 'beats.label_probs': 0.181, 'beats.score': 0.044} | 3705.9 |
| mix_clip_29_clean | 1000 | ON | 31 | 3.69 | 6.21 | 421.71 | 0.532 | 0.533 | 1.077 | {'whisper.transcribe': 0.155, 'parakeet.transcribe': 0.041, 'beats.label_probs': 0.16, 'beats.score': 0.022} | 3705.9 |
| mix_clip_30_noisy | 20 | OFF | 1501 | 13.61 | 20.21 | 824.12 | 22.726 | 22.734 | 20.438 | {'whisper.transcribe': 1.435, 'parakeet.transcribe': 0.793, 'beats.label_probs': 1.204, 'beats.score': 0.049} | 3705.8 |
| mix_clip_30_noisy | 20 | ON | 1501 | 11.77 | 18.22 | 852.31 | 20.542 | 20.551 | 16.513 | {'whisper.transcribe': 1.095, 'parakeet.transcribe': 0.62, 'beats.label_probs': 1.238, 'beats.score': 0.049} | 3705.7 |
| mix_clip_30_noisy | 100 | OFF | 301 | 7.53 | 12.26 | 735.41 | 5.318 | 5.32 | 8.587 | {'whisper.transcribe': 1.095, 'parakeet.transcribe': 0.698, 'beats.label_probs': 1.207, 'beats.score': 0.044} | 3705.8 |
| mix_clip_30_noisy | 100 | ON | 301 | 5.0 | 9.52 | 766.38 | 4.303 | 4.305 | 6.653 | {'whisper.transcribe': 0.834, 'parakeet.transcribe': 0.543, 'beats.label_probs': 1.196, 'beats.score': 0.046} | 3705.7 |
| mix_clip_30_noisy | 1000 | OFF | 31 | 6.58 | 479.11 | 778.77 | 2.893 | 2.894 | 6.095 | {'whisper.transcribe': 0.842, 'parakeet.transcribe': 0.558, 'beats.label_probs': 1.209, 'beats.score': 0.046} | 3705.8 |
| mix_clip_30_noisy | 1000 | ON | 31 | 3.93 | 482.25 | 753.15 | 2.779 | 2.779 | 5.94 | {'whisper.transcribe': 0.837, 'parakeet.transcribe': 0.563, 'beats.label_probs': 1.162, 'beats.score': 0.046} | 3705.7 |
| pos_01 | 100 | OFF | 539 | 11.72 | 19.39 | 3728.55 | 19.838 | 19.842 | 26.315 | {'whisper.transcribe': 10.176, 'parakeet.transcribe': 0.664, 'beats.label_probs': 2.318, 'beats.score': 0.258} | 3757.1 |
| pos_01 | 100 | ON | 539 | 8.37 | 12.01 | 2827.94 | 16.43 | 16.434 | 21.184 | {'whisper.transcribe': 8.572, 'parakeet.transcribe': 0.71, 'beats.label_probs': 2.434, 'beats.score': 0.25} | 3757.1 |
| pos_01 | 1000 | OFF | 55 | 8.39 | 1445.76 | 3599.57 | 14.155 | 14.156 | 22.49 | {'whisper.transcribe': 10.321, 'parakeet.transcribe': 0.625, 'beats.label_probs': 2.281, 'beats.score': 0.248} | 3757.1 |
| pos_01 | 1000 | ON | 55 | 4.18 | 2146.97 | 2769.34 | 11.451 | 11.451 | 17.731 | {'whisper.transcribe': 7.791, 'parakeet.transcribe': 0.621, 'beats.label_probs': 2.24, 'beats.score': 0.249} | 3757.2 |
| pos_02 | 100 | OFF | 506 | 10.96 | 16.4 | 4055.07 | 19.831 | 19.835 | 24.867 | {'whisper.transcribe': 10.707, 'parakeet.transcribe': 0.766, 'beats.label_probs': 2.449, 'beats.score': 0.284} | 3757.2 |
| pos_02 | 100 | ON | 506 | 7.2 | 10.44 | 4749.57 | 19.944 | 19.947 | 26.062 | {'whisper.transcribe': 13.099, 'parakeet.transcribe': 0.68, 'beats.label_probs': 2.045, 'beats.score': 0.239} | 3757.2 |
| pos_02 | 1000 | OFF | 52 | 7.28 | 1009.15 | 3834.72 | 11.35 | 11.351 | 17.352 | {'whisper.transcribe': 7.754, 'parakeet.transcribe': 0.664, 'beats.label_probs': 2.088, 'beats.score': 0.239} | 3757.3 |
| pos_02 | 1000 | ON | 52 | 3.87 | 2142.02 | 4575.3 | 15.995 | 15.996 | 23.86 | {'whisper.transcribe': 12.513, 'parakeet.transcribe': 0.681, 'beats.label_probs': 2.031, 'beats.score': 0.247} | 3757.3 |
| pos_03 | 100 | OFF | 565 | 12.27 | 18.08 | 4142.56 | 21.214 | 21.218 | 25.526 | {'whisper.transcribe': 11.431, 'parakeet.transcribe': 0.645, 'beats.label_probs': 2.287, 'beats.score': 0.219} | 3757.4 |
| pos_03 | 100 | ON | 565 | 7.89 | 11.12 | 3321.8 | 19.33 | 19.334 | 25.672 | {'whisper.transcribe': 11.734, 'parakeet.transcribe': 0.647, 'beats.label_probs': 2.351, 'beats.score': 0.217} | 3757.4 |
| pos_03 | 1000 | OFF | 58 | 8.54 | 2278.1 | 3786.19 | 13.765 | 13.766 | 20.338 | {'whisper.transcribe': 9.704, 'parakeet.transcribe': 0.681, 'beats.label_probs': 2.39, 'beats.score': 0.265} | 3757.4 |
| pos_03 | 1000 | ON | 58 | 4.41 | 2080.12 | 3449.13 | 13.652 | 13.653 | 21.932 | {'whisper.transcribe': 9.86, 'parakeet.transcribe': 0.664, 'beats.label_probs': 2.449, 'beats.score': 0.22} | 3757.4 |
| pos_04 | 100 | OFF | 353 | 8.7 | 14.04 | 2357.5 | 9.435 | 9.437 | 11.999 | {'whisper.transcribe': 3.187, 'parakeet.transcribe': 0.743, 'beats.label_probs': 1.858, 'beats.score': 0.197} | 3757.5 |
| pos_04 | 100 | ON | 353 | 5.76 | 9.89 | 2960.7 | 8.015 | 8.018 | 9.905 | {'whisper.transcribe': 3.504, 'parakeet.transcribe': 0.579, 'beats.label_probs': 1.485, 'beats.score': 0.158} | 3757.5 |
| pos_04 | 1000 | OFF | 37 | 6.83 | 918.79 | 1245.14 | 4.432 | 4.432 | 7.401 | {'whisper.transcribe': 1.823, 'parakeet.transcribe': 0.597, 'beats.label_probs': 1.491, 'beats.score': 0.16} | 3757.5 |
| pos_04 | 1000 | ON | 37 | 3.88 | 948.49 | 2502.54 | 5.647 | 5.648 | 8.646 | {'whisper.transcribe': 3.089, 'parakeet.transcribe': 0.572, 'beats.label_probs': 1.546, 'beats.score': 0.161} | 3757.5 |
| neg_01 | 100 | OFF | 602 | 13.38 | 19.84 | 4785.84 | 23.242 | 23.246 | 27.716 | {'whisper.transcribe': 11.508, 'parakeet.transcribe': 0.973, 'beats.label_probs': 2.562, 'beats.score': 0.29} | 3757.5 |
| neg_01 | 100 | ON | 602 | 8.6 | 12.75 | 4189.72 | 24.612 | 24.617 | 27.49 | {'whisper.transcribe': 15.217, 'parakeet.transcribe': 1.007, 'beats.label_probs': 2.521, 'beats.score': 0.29} | 3757.6 |
| neg_01 | 1000 | OFF | 62 | 9.55 | 1176.83 | 4066.59 | 15.168 | 15.168 | 22.123 | {'whisper.transcribe': 10.444, 'parakeet.transcribe': 0.965, 'beats.label_probs': 2.631, 'beats.score': 0.292} | 3757.7 |
| neg_01 | 1000 | ON | 62 | 4.46 | 1781.83 | 4193.84 | 16.896 | 16.897 | 22.112 | {'whisper.transcribe': 12.266, 'parakeet.transcribe': 1.0, 'beats.label_probs': 2.575, 'beats.score': 0.288} | 3757.7 |
| neg_02 | 100 | OFF | 501 | 11.53 | 17.9 | 2881.36 | 15.763 | 15.767 | 19.798 | {'whisper.transcribe': 5.43, 'parakeet.transcribe': 0.965, 'beats.label_probs': 2.943, 'beats.score': 0.324} | 3757.7 |
| neg_02 | 100 | ON | 501 | 8.13 | 11.36 | 1433.33 | 10.121 | 10.125 | 12.563 | {'whisper.transcribe': 2.849, 'parakeet.transcribe': 0.758, 'beats.label_probs': 2.13, 'beats.score': 0.241} | 3757.7 |
| neg_02 | 1000 | OFF | 51 | 8.99 | 1002.48 | 2849.27 | 8.564 | 8.565 | 12.988 | {'whisper.transcribe': 4.806, 'parakeet.transcribe': 0.726, 'beats.label_probs': 2.157, 'beats.score': 0.245} | 3757.7 |
| neg_02 | 1000 | ON | 51 | 4.23 | 1001.31 | 1621.04 | 6.651 | 6.651 | 11.055 | {'whisper.transcribe': 3.069, 'parakeet.transcribe': 0.788, 'beats.label_probs': 2.135, 'beats.score': 0.24} | 3757.7 |
| neg_03 | 100 | OFF | 478 | 11.68 | 17.49 | 4622.78 | 25.774 | 25.777 | 30.753 | {'whisper.transcribe': 16.829, 'parakeet.transcribe': 0.677, 'beats.label_probs': 2.409, 'beats.score': 0.265} | 3757.7 |
| neg_03 | 100 | ON | 478 | 7.67 | 10.91 | 4196.56 | 18.69 | 18.694 | 22.687 | {'whisper.transcribe': 12.054, 'parakeet.transcribe': 0.6, 'beats.label_probs': 2.057, 'beats.score': 0.221} | 3757.7 |
| neg_03 | 1000 | OFF | 49 | 8.41 | 3321.41 | 3713.32 | 19.322 | 19.323 | 27.612 | {'whisper.transcribe': 15.24, 'parakeet.transcribe': 0.693, 'beats.label_probs': 2.449, 'beats.score': 0.266} | 3757.7 |
| neg_03 | 1000 | ON | 49 | 4.31 | 2486.44 | 4355.38 | 17.201 | 17.202 | 22.887 | {'whisper.transcribe': 13.828, 'parakeet.transcribe': 0.596, 'beats.label_probs': 2.007, 'beats.score': 0.22} | 3757.7 |
| neg_04 | 100 | OFF | 315 | 7.84 | 14.09 | 3255.28 | 13.77 | 13.772 | 17.948 | {'whisper.transcribe': 7.042, 'parakeet.transcribe': 0.979, 'beats.label_probs': 2.468, 'beats.score': 0.278} | 3757.7 |
| neg_04 | 100 | ON | 315 | 5.41 | 10.6 | 2672.51 | 7.128 | 7.13 | 8.93 | {'whisper.transcribe': 2.905, 'parakeet.transcribe': 0.597, 'beats.label_probs': 1.371, 'beats.score': 0.153} | 3757.7 |
| neg_04 | 1000 | OFF | 33 | 6.78 | 945.04 | 3030.79 | 8.356 | 8.356 | 11.969 | {'whisper.transcribe': 5.277, 'parakeet.transcribe': 0.709, 'beats.label_probs': 1.798, 'beats.score': 0.198} | 3757.7 |
| neg_04 | 1000 | ON | 33 | 3.94 | 827.38 | 3149.12 | 5.661 | 5.662 | 8.493 | {'whisper.transcribe': 3.382, 'parakeet.transcribe': 0.574, 'beats.label_probs': 1.324, 'beats.score': 0.15} | 3757.7 |
| neg_05 | 100 | OFF | 512 | 11.97 | 17.75 | 3088.66 | 12.382 | 12.385 | 14.784 | {'whisper.transcribe': 3.68, 'parakeet.transcribe': 0.605, 'beats.label_probs': 2.212, 'beats.score': 0.152} | 3757.7 |
| neg_05 | 100 | ON | 512 | 8.35 | 11.43 | 2295.17 | 9.842 | 9.847 | 12.317 | {'whisper.transcribe': 3.01, 'parakeet.transcribe': 0.617, 'beats.label_probs': 2.138, 'beats.score': 0.153} | 3757.7 |
| neg_05 | 1000 | OFF | 53 | 8.86 | 742.25 | 1625.14 | 5.96 | 5.961 | 10.292 | {'whisper.transcribe': 2.41, 'parakeet.transcribe': 0.627, 'beats.label_probs': 2.258, 'beats.score': 0.154} | 3757.7 |
| neg_05 | 1000 | ON | 53 | 4.52 | 706.83 | 3430.84 | 7.626 | 7.627 | 12.008 | {'whisper.transcribe': 4.239, 'parakeet.transcribe': 0.626, 'beats.label_probs': 2.291, 'beats.score': 0.154} | 3757.7 |
| neg_06 | 100 | OFF | 174 | 5.25 | 9.48 | 3330.78 | 5.836 | 5.837 | 6.883 | {'whisper.transcribe': 3.661, 'parakeet.transcribe': 0.262, 'beats.label_probs': 0.747, 'beats.score': 0.076} | 3743.0 |
| neg_06 | 100 | ON | 174 | 3.69 | 7.6 | 4558.16 | 8.127 | 8.128 | 11.072 | {'whisper.transcribe': 6.202, 'parakeet.transcribe': 0.254, 'beats.label_probs': 0.705, 'beats.score': 0.074} | 3743.0 |
| neg_06 | 1000 | OFF | 19 | 4.99 | 3152.83 | 3160.65 | 6.392 | 6.392 | 7.851 | {'whisper.transcribe': 5.19, 'parakeet.transcribe': 0.254, 'beats.label_probs': 0.686, 'beats.score': 0.073} | 3743.0 |
| neg_06 | 1000 | ON | 19 | 3.37 | 4041.06 | 5093.7 | 9.195 | 9.195 | 12.646 | {'whisper.transcribe': 7.962, 'parakeet.transcribe': 0.254, 'beats.label_probs': 0.726, 'beats.score': 0.073} | 3743.0 |
| neg_07 | 100 | OFF | 3261 | 45.32 | 83.8 | 1335.43 | 188.775 | 188.804 | 199.054 | {'whisper.transcribe': 15.584, 'parakeet.transcribe': 4.079, 'beats.label_probs': 15.972, 'beats.score': 1.751} | 3757.7 |
| neg_07 | 100 | ON | 3261 | 26.31 | 45.14 | 1253.01 | 118.375 | 118.407 | 126.327 | {'whisper.transcribe': 13.077, 'parakeet.transcribe': 3.657, 'beats.label_probs': 15.015, 'beats.score': 1.586} | 3757.7 |
| neg_07 | 1000 | OFF | 327 | 35.14 | 939.33 | 1201.42 | 44.096 | 44.101 | 71.547 | {'whisper.transcribe': 11.598, 'parakeet.transcribe': 3.774, 'beats.label_probs': 15.098, 'beats.score': 1.671} | 3757.7 |
| neg_07 | 1000 | ON | 327 | 12.14 | 908.69 | 1083.02 | 34.745 | 34.75 | 60.593 | {'whisper.transcribe': 10.706, 'parakeet.transcribe': 3.487, 'beats.label_probs': 14.054, 'beats.score': 1.561} | 3757.7 |
| neg_08 | 100 | OFF | 352 | 8.64 | 13.83 | 2309.67 | 10.17 | 10.173 | 13.711 | {'whisper.transcribe': 4.751, 'parakeet.transcribe': 0.535, 'beats.label_probs': 1.443, 'beats.score': 0.161} | 3757.7 |
| neg_08 | 100 | ON | 352 | 5.79 | 9.79 | 3814.58 | 10.203 | 10.206 | 13.823 | {'whisper.transcribe': 5.726, 'parakeet.transcribe': 0.535, 'beats.label_probs': 1.458, 'beats.score': 0.161} | 3757.7 |
| neg_08 | 1000 | OFF | 37 | 6.9 | 1118.66 | 2685.17 | 7.142 | 7.143 | 11.873 | {'whisper.transcribe': 4.547, 'parakeet.transcribe': 0.53, 'beats.label_probs': 1.517, 'beats.score': 0.161} | 3757.7 |
| neg_08 | 1000 | ON | 37 | 3.88 | 1068.73 | 5293.88 | 9.825 | 9.826 | 14.568 | {'whisper.transcribe': 7.294, 'parakeet.transcribe': 0.524, 'beats.label_probs': 1.502, 'beats.score': 0.16} | 3757.7 |
| neg_09 | 100 | OFF | 364 | 8.53 | 13.55 | 2045.91 | 11.022 | 11.024 | 16.891 | {'whisper.transcribe': 3.475, 'parakeet.transcribe': 0.927, 'beats.label_probs': 2.607, 'beats.score': 0.291} | 3757.7 |
| neg_09 | 100 | ON | 364 | 5.61 | 9.17 | 1159.28 | 5.666 | 5.669 | 7.567 | {'whisper.transcribe': 1.217, 'parakeet.transcribe': 0.511, 'beats.label_probs': 1.479, 'beats.score': 0.162} | 3757.7 |
| neg_09 | 1000 | OFF | 38 | 6.57 | 939.12 | 1985.79 | 5.961 | 5.961 | 11.488 | {'whisper.transcribe': 2.747, 'parakeet.transcribe': 0.654, 'beats.label_probs': 1.909, 'beats.score': 0.207} | 3757.7 |
| neg_09 | 1000 | ON | 38 | 3.95 | 780.63 | 1186.33 | 3.782 | 3.782 | 6.765 | {'whisper.transcribe': 1.211, 'parakeet.transcribe': 0.518, 'beats.label_probs': 1.576, 'beats.score': 0.165} | 3757.7 |
| neg_10 | 100 | OFF | 166 | 4.79 | 9.23 | 1041.87 | 3.633 | 3.634 | 5.384 | {'whisper.transcribe': 1.012, 'parakeet.transcribe': 0.383, 'beats.label_probs': 0.99, 'beats.score': 0.111} | 3743.0 |
| neg_10 | 100 | ON | 166 | 3.69 | 7.37 | 1016.11 | 2.455 | 2.457 | 3.494 | {'whisper.transcribe': 0.641, 'parakeet.transcribe': 0.274, 'beats.label_probs': 0.66, 'beats.score': 0.07} | 3743.0 |
| neg_10 | 1000 | OFF | 18 | 5.01 | 976.37 | 1698.72 | 2.754 | 2.754 | 4.886 | {'whisper.transcribe': 1.033, 'parakeet.transcribe': 0.384, 'beats.label_probs': 0.977, 'beats.score': 0.106} | 3743.0 |
| neg_10 | 1000 | ON | 18 | 3.6 | 759.65 | 997.66 | 1.816 | 1.816 | 3.257 | {'whisper.transcribe': 0.646, 'parakeet.transcribe': 0.296, 'beats.label_probs': 0.648, 'beats.score': 0.07} | 3743.0 |
| neg_11 | 100 | OFF | 86 | 3.7 | 7.32 | 798.58 | 1.15 | 1.151 | 1.682 | {'whisper.transcribe': 0.271, 'parakeet.transcribe': 0.121, 'beats.label_probs': 0.317, 'beats.score': 0.033} | 3734.0 |
| neg_11 | 100 | ON | 86 | 3.05 | 6.96 | 716.37 | 1.031 | 1.031 | 1.54 | {'whisper.transcribe': 0.275, 'parakeet.transcribe': 0.08, 'beats.label_probs': 0.306, 'beats.score': 0.033} | 3734.0 |
| neg_11 | 1000 | OFF | 10 | 3.91 | 7.2 | 685.03 | 0.723 | 0.723 | 1.398 | {'whisper.transcribe': 0.264, 'parakeet.transcribe': 0.078, 'beats.label_probs': 0.286, 'beats.score': 0.032} | 3734.0 |
| neg_11 | 1000 | ON | 10 | 3.49 | 3.95 | 697.59 | 0.729 | 0.729 | 1.416 | {'whisper.transcribe': 0.268, 'parakeet.transcribe': 0.077, 'beats.label_probs': 0.297, 'beats.score': 0.033} | 3734.0 |
| neg_12 | 100 | OFF | 86 | 3.58 | 7.21 | 711.89 | 1.048 | 1.049 | 1.572 | {'whisper.transcribe': 0.265, 'parakeet.transcribe': 0.079, 'beats.label_probs': 0.31, 'beats.score': 0.033} | 3734.0 |
| neg_12 | 100 | ON | 86 | 2.88 | 6.39 | 689.37 | 0.987 | 0.988 | 1.497 | {'whisper.transcribe': 0.259, 'parakeet.transcribe': 0.074, 'beats.label_probs': 0.301, 'beats.score': 0.033} | 3734.0 |
| neg_12 | 1000 | OFF | 10 | 3.88 | 7.26 | 695.49 | 0.733 | 0.733 | 1.405 | {'whisper.transcribe': 0.261, 'parakeet.transcribe': 0.076, 'beats.label_probs': 0.292, 'beats.score': 0.034} | 3734.0 |
| neg_12 | 1000 | ON | 10 | 3.61 | 6.68 | 685.22 | 0.72 | 0.72 | 1.396 | {'whisper.transcribe': 0.259, 'parakeet.transcribe': 0.079, 'beats.label_probs': 0.294, 'beats.score': 0.032} | 3734.0 |
| neg_13 | 100 | OFF | 51 | 3.13 | 6.76 | 475.82 | 0.643 | 0.643 | 1.136 | {'whisper.transcribe': 0.175, 'parakeet.transcribe': 0.107, 'beats.label_probs': 0.132, 'beats.score': 0.022} | 3706.5 |
| neg_13 | 100 | ON | 51 | 2.93 | 6.48 | 409.62 | 0.57 | 0.57 | 1.06 | {'whisper.transcribe': 0.181, 'parakeet.transcribe': 0.056, 'beats.label_probs': 0.137, 'beats.score': 0.023} | 3706.5 |
| neg_13 | 1000 | OFF | 6 | 3.31 | 3.55 | 408.69 | 0.425 | 0.425 | 0.99 | {'whisper.transcribe': 0.179, 'parakeet.transcribe': 0.053, 'beats.label_probs': 0.143, 'beats.score': 0.021} | 3706.5 |
| neg_13 | 1000 | ON | 6 | 3.53 | 6.73 | 391.28 | 0.412 | 0.412 | 0.972 | {'whisper.transcribe': 0.172, 'parakeet.transcribe': 0.052, 'beats.label_probs': 0.133, 'beats.score': 0.022} | 3706.5 |
| neg_14 | 100 | OFF | 272 | 6.99 | 13.25 | 3287.5 | 9.897 | 9.899 | 12.864 | {'whisper.transcribe': 4.895, 'parakeet.transcribe': 0.619, 'beats.label_probs': 1.881, 'beats.score': 0.204} | 3757.7 |
| neg_14 | 100 | ON | 272 | 4.54 | 9.12 | 895.14 | 3.893 | 3.895 | 5.331 | {'whisper.transcribe': 0.679, 'parakeet.transcribe': 0.363, 'beats.label_probs': 1.181, 'beats.score': 0.121} | 3757.7 |
| neg_14 | 1000 | OFF | 29 | 6.06 | 866.2 | 3555.3 | 8.148 | 8.148 | 11.183 | {'whisper.transcribe': 5.58, 'parakeet.transcribe': 0.543, 'beats.label_probs': 1.559, 'beats.score': 0.166} | 3757.7 |
| neg_14 | 1000 | ON | 29 | 3.94 | 701.48 | 910.85 | 2.55 | 2.55 | 4.738 | {'whisper.transcribe': 0.701, 'parakeet.transcribe': 0.377, 'beats.label_probs': 1.184, 'beats.score': 0.119} | 3757.7 |
