(comparisons recomputed from runs/ with the current comparison code)

Components: `{"whisper": "UNAVAILABLE (ManifestPhraseSTT)", "whisper_model": "manifest-phrase-stub-whisper", "whisper_device": "?", "parakeet": "ManifestPhraseSTT", "parakeet_providers": null, "semantic": "UNAVAILABLE", "stt_confidence_gate": false, "beats": "UNAVAILABLE", "scream_trigger": false, "scream_corroboration": false, "intent_gate": "UNAVAILABLE", "intent_threshold": null, "kws": "off", "dual_asr": "off", "separation": "off", "language_id": "off", "device": "cpu", "processing_version": "pipeline-2026.09"}`

Rows: 186 (recording x chunk size); repeats per mode: 2; clock: virtual: monotonic() = audio seconds delivered

| Set | Chunk | Rows | Segments OFF / ON | ON == one-shot | Events OFF / ON | Unpaired events OFF-only / ON-only | TRIGGER_ALL OFF / ON | Repeat-induced ALL OFF / ON | Duplicate alerts OFF / ON (designed) | Repeat-stable OFF / ON | Not COMPLETE | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| media | 100 ms | 18 | 121 / 103 | 18/18 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 (0) | 18 / 18 | 0 | 0 |
| media | 1000 ms | 18 | 110 / 103 | 18/18 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 (0) | 18 / 18 | 0 | 0 |
| mixed | 20 ms | 30 | 159 / 50 | 30/30 | 72 / 46 | 26 / 0 | 62 / 35 | 10 / 0 | 49 / 6 (6) | 30 / 30 | 0 | 0 |
| mixed | 100 ms | 30 | 133 / 50 | 30/30 | 65 / 46 | 19 / 0 | 55 / 35 | 7 / 0 | 34 / 6 (6) | 30 / 30 | 0 | 0 |
| mixed | 250 ms | 30 | 103 / 50 | 30/30 | 59 / 46 | 13 / 0 | 49 / 35 | 6 / 0 | 26 / 6 (6) | 30 / 30 | 0 | 0 |
| mixed | 500 ms | 30 | 96 / 50 | 30/30 | 57 / 46 | 11 / 0 | 46 / 35 | 4 / 0 | 20 / 6 (6) | 30 / 30 | 0 | 0 |
| mixed | 1000 ms | 30 | 82 / 50 | 30/30 | 52 / 46 | 6 / 0 | 42 / 35 | 2 / 0 | 14 / 6 (6) | 30 / 30 | 0 | 0 |

Tier changes and per-utterance timing (virtual stream clock; delay = OFF - ON)
| Set | Chunk | Tier changes OFF->ON | Utterances decided >1 s later by OFF | Max decision delay s | Alerts >1 s later by OFF | Max alert delay s | Utterances alerted only by OFF / only by ON |
|---|---|---|---|---|---|---|---|
| media | 100 ms | 0 | 0 | 0.0 | 0 | 0.0 | 0 / 0 |
| media | 1000 ms | 0 | 0 | 0.0 | 0 | 0.0 | 0 / 0 |
| mixed | 20 ms | {'TRIGGER_ALL->TRIGGER_VERIFY': 1} | 6 | 21.5 | 6 | 21.5 | 0 / 0 |
| mixed | 100 ms | {'TRIGGER_ALL->TRIGGER_VERIFY': 1} | 6 | 21.6 | 6 | 21.6 | 0 / 0 |
| mixed | 250 ms | {'TRIGGER_ALL->TRIGGER_VERIFY': 1} | 7 | 21.8 | 7 | 21.8 | 0 / 0 |
| mixed | 500 ms | {'TRIGGER_ALL->TRIGGER_VERIFY': 1} | 7 | 22.0 | 7 | 22.0 | 0 / 0 |
| mixed | 1000 ms | {'TRIGGER_ALL->TRIGGER_VERIFY': 1} | 7 | 23.0 | 7 | 23.0 | 0 / 0 |

Tier changes (all rows):
- mix_clip_12_noisy 20 ms OFF ('21630-26490', 'TRIGGER_ALL', 'UDK_14', 'exact') -> ON ('21630-26460', 'TRIGGER_VERIFY', 'UDK_14', 'exact')
- mix_clip_12_noisy 100 ms OFF ('21630-26460', 'TRIGGER_ALL', 'UDK_14', 'exact') -> ON ('21630-26460', 'TRIGGER_VERIFY', 'UDK_14', 'exact')
- mix_clip_12_noisy 250 ms OFF ('21630-26460', 'TRIGGER_ALL', 'UDK_14', 'exact') -> ON ('21630-26460', 'TRIGGER_VERIFY', 'UDK_14', 'exact')
- mix_clip_12_noisy 500 ms OFF ('21630-26460', 'TRIGGER_ALL', 'UDK_14', 'exact') -> ON ('21630-26460', 'TRIGGER_VERIFY', 'UDK_14', 'exact')
- mix_clip_12_noisy 1000 ms OFF ('21630-26460', 'TRIGGER_ALL', 'UDK_14', 'exact') -> ON ('21630-26460', 'TRIGGER_VERIFY', 'UDK_14', 'exact')

Utterances OFF handled >1 s later than ON (all rows):
- mix_clip_02_noisy 20 ms utterance (0, 1620): decision +3.14 s, alert +3.14 s
- mix_clip_02_noisy 100 ms utterance (0, 1620): decision +3.2 s, alert +3.2 s
- mix_clip_02_noisy 250 ms utterance (0, 1620): decision +3.5 s, alert +3.5 s
- mix_clip_02_noisy 500 ms utterance (0, 1620): decision +3.5 s, alert +3.5 s
- mix_clip_02_noisy 1000 ms utterance (0, 1620): decision +4.0 s, alert +4.0 s
- mix_clip_06_noisy 20 ms utterance (0, 1620): decision +17.62 s, alert +17.62 s
- mix_clip_06_noisy 100 ms utterance (0, 1620): decision +17.7 s, alert +17.7 s
- mix_clip_06_noisy 250 ms utterance (0, 1620): decision +18.0 s, alert +18.0 s
- mix_clip_06_noisy 500 ms utterance (0, 1620): decision +18.0 s, alert +18.0 s
- mix_clip_06_noisy 1000 ms utterance (0, 1620): decision +19.0 s, alert +19.0 s
- mix_clip_10_noisy 20 ms utterance (0, 1620): decision +20.9 s, alert +20.9 s
- mix_clip_10_noisy 100 ms utterance (0, 1620): decision +21.0 s, alert +21.0 s
- mix_clip_10_noisy 250 ms utterance (0, 1620): decision +21.25 s, alert +21.25 s
- mix_clip_10_noisy 500 ms utterance (0, 1620): decision +21.5 s, alert +21.5 s
- mix_clip_10_noisy 1000 ms utterance (0, 1620): decision +22.0 s, alert +22.0 s
- mix_clip_12_noisy 20 ms utterance (0, 1620): decision +21.52 s, alert +21.52 s
- mix_clip_12_noisy 100 ms utterance (0, 1620): decision +21.6 s, alert +21.6 s
- mix_clip_12_noisy 250 ms utterance (0, 1620): decision +21.75 s, alert +21.75 s
- mix_clip_12_noisy 500 ms utterance (0, 1620): decision +22.0 s, alert +22.0 s
- mix_clip_12_noisy 1000 ms utterance (0, 1620): decision +23.0 s, alert +23.0 s
- mix_clip_14_noisy 20 ms utterance (0, 1620): decision +8.92 s, alert +8.92 s
- mix_clip_14_noisy 100 ms utterance (0, 1620): decision +9.0 s, alert +9.0 s
- mix_clip_14_noisy 250 ms utterance (0, 1620): decision +9.25 s, alert +9.25 s
- mix_clip_14_noisy 500 ms utterance (0, 1620): decision +9.5 s, alert +9.5 s
- mix_clip_14_noisy 1000 ms utterance (0, 1620): decision +10.0 s, alert +10.0 s
- mix_clip_18_noisy 20 ms utterance (0, 1620): decision +4.94 s, alert +4.94 s
- mix_clip_18_noisy 100 ms utterance (0, 1620): decision +5.0 s, alert +5.0 s
- mix_clip_18_noisy 250 ms utterance (0, 1620): decision +5.25 s, alert +5.25 s
- mix_clip_18_noisy 500 ms utterance (0, 1620): decision +5.5 s, alert +5.5 s
- mix_clip_18_noisy 1000 ms utterance (0, 1620): decision +6.0 s, alert +6.0 s
- mix_clip_30_noisy 250 ms utterance (0, 1620): decision +1.25 s, alert +1.25 s
- mix_clip_30_noisy 500 ms utterance (0, 1620): decision +1.5 s, alert +1.5 s
- mix_clip_30_noisy 1000 ms utterance (0, 1620): decision +2.0 s, alert +2.0 s

Difference classes: {'expected_vad_correction': 843}

Difference kinds: {'segment_only_off / spurious segment': 100, 'segment_only_off / re-processing': 240, 'segment_only_off / drifted boundary': 244, 'same_segment_different_output / engine history differs': 23, 'segment_only_on / ON processed the one-shot segment; OFF processed drifted boundaries instead': 236}

Same-boundary field differences (segments): {'udk_primary': 23, 'pre_veto': 23, 'final': 23, 'alerts': 23}

Unpaired events (all rows):
- mix_clip_01_clean 250 ms OFF-only ('19050-23430', 'TRIGGER_ALL', 'UDK_03', 'exact')
- mix_clip_02_noisy 20 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_04', 'exact')
- mix_clip_02_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_04', 'exact')
- mix_clip_02_noisy 100 ms OFF-only ('0-1650', 'TRIGGER_ALL', 'UDK_04', 'exact')
- mix_clip_02_noisy 100 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_04', 'exact')
- mix_clip_04_overlapping 20 ms OFF-only ('0-4800', 'TRIGGER_ALL', 'UDK_06', 'exact')
- mix_clip_04_overlapping 20 ms OFF-only ('0-4830', 'TRIGGER_ALL', 'UDK_06', 'exact')
- mix_clip_04_overlapping 100 ms OFF-only ('0-4800', 'TRIGGER_ALL', 'UDK_06', 'exact')
- mix_clip_04_overlapping 100 ms OFF-only ('0-4830', 'TRIGGER_ALL', 'UDK_06', 'exact')
- mix_clip_04_overlapping 250 ms OFF-only ('0-4800', 'TRIGGER_ALL', 'UDK_06', 'exact')
- mix_clip_04_overlapping 500 ms OFF-only ('0-4800', 'TRIGGER_ALL', 'UDK_06', 'exact')
- mix_clip_06_noisy 20 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 20 ms OFF-only ('0-1650', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 20 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 100 ms OFF-only ('0-1650', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 100 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 250 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 500 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_06_noisy 1000 ms OFF-only ('17730-22320', 'TRIGGER_ALL', 'UDK_08', 'exact')
- mix_clip_07_muffled 20 ms OFF-only ('24300-29250', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 20 ms OFF-only ('24300-29280', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 100 ms OFF-only ('24300-29220', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 100 ms OFF-only ('24300-29250', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 250 ms OFF-only ('24300-29220', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 500 ms OFF-only ('24300-29220', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_07_muffled 1000 ms OFF-only ('24300-29220', 'TRIGGER_ALL', 'UDK_09', 'exact')
- mix_clip_10_noisy 20 ms OFF-only ('0-1650', 'TRIGGER_ALL', 'UDK_12', 'exact')
- mix_clip_10_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_12', 'exact')
- mix_clip_10_noisy 100 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_12', 'exact')
- mix_clip_10_noisy 500 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_12', 'exact')
- mix_clip_12_noisy 20 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_14', 'exact')
- mix_clip_12_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_14', 'exact')
- mix_clip_12_noisy 100 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_14', 'exact')
- mix_clip_12_noisy 100 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_14', 'exact')
- mix_clip_12_noisy 250 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_14', 'exact')
- mix_clip_14_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_16', 'exact')
- mix_clip_14_noisy 100 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_16', 'exact')
- mix_clip_14_noisy 1000 ms OFF-only ('22860-30000', 'TRIGGER_ALL', 'UDK_16', 'exact')
- mix_clip_17_muffled 250 ms OFF-only ('1260-5820', 'TRIGGER_ALL', 'UDK_19', 'exact')
- mix_clip_17_muffled 500 ms OFF-only ('1260-5820', 'TRIGGER_ALL', 'UDK_19', 'exact')
- mix_clip_17_muffled 1000 ms OFF-only ('1260-5820', 'TRIGGER_ALL', 'UDK_19', 'exact')
- mix_clip_18_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 20 ms OFF-only ('28230-30000', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 100 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 100 ms OFF-only ('28230-30000', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 250 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 250 ms OFF-only ('28230-30000', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 500 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 500 ms OFF-only ('28230-30000', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 1000 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_18_noisy 1000 ms OFF-only ('28230-30000', 'TRIGGER_ALL', 'UDK_20', 'exact')
- mix_clip_19_muffled 100 ms OFF-only ('6510-10950', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_19_muffled 250 ms OFF-only ('6510-10950', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_19_muffled 500 ms OFF-only ('6510-10950', 'TRIGGER_VERIFY', 'UDK_08', 'semantic')
- mix_clip_21_clean 20 ms OFF-only ('12900-17610', 'TRIGGER_ALL', 'UDK_01', 'fuzzy')
- mix_clip_23_muffled 20 ms OFF-only ('9300-14610', 'TRIGGER_ALL', 'UDK_20', 'semantic')
- mix_clip_23_muffled 20 ms OFF-only ('9300-14670', 'TRIGGER_ALL', 'UDK_20', 'semantic')
- mix_clip_28_overlapping 20 ms OFF-only ('8250-13860', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_28_overlapping 20 ms OFF-only ('8250-13950', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_28_overlapping 100 ms OFF-only ('8250-13860', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_28_overlapping 100 ms OFF-only ('8250-13950', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_28_overlapping 250 ms OFF-only ('8250-13950', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_28_overlapping 500 ms OFF-only ('8250-13860', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_28_overlapping 500 ms OFF-only ('8250-13950', 'TRIGGER_ALL', 'UDK_04', 'semantic')
- mix_clip_29_clean 20 ms OFF-only ('2370-7410', 'TRIGGER_ALL', 'UDK_09', 'semantic')
- mix_clip_30_noisy 20 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 20 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 20 ms OFF-only ('1050-5880', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 100 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 100 ms OFF-only ('1050-5880', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 250 ms OFF-only ('0-1620', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 250 ms OFF-only ('0-1680', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 250 ms OFF-only ('1050-5880', 'TRIGGER_ALL', 'UDK_08', 'semantic')
- mix_clip_30_noisy 500 ms OFF-only ('1050-5880', 'TRIGGER_ALL', 'UDK_08', 'semantic')

Repeat-induced TRIGGER_ALL (all rows):
- mix_clip_01_clean 250 ms OFF (19050, 23430, 'UDK_03')
- mix_clip_04_overlapping 20 ms OFF (0, 4800, 'UDK_06')
- mix_clip_04_overlapping 20 ms OFF (0, 4830, 'UDK_06')
- mix_clip_04_overlapping 100 ms OFF (0, 4800, 'UDK_06')
- mix_clip_04_overlapping 100 ms OFF (0, 4830, 'UDK_06')
- mix_clip_04_overlapping 250 ms OFF (0, 4800, 'UDK_06')
- mix_clip_07_muffled 20 ms OFF (24300, 29250, 'UDK_09')
- mix_clip_07_muffled 20 ms OFF (24300, 29280, 'UDK_09')
- mix_clip_07_muffled 100 ms OFF (24300, 29220, 'UDK_09')
- mix_clip_07_muffled 100 ms OFF (24300, 29250, 'UDK_09')
- mix_clip_07_muffled 250 ms OFF (24300, 29220, 'UDK_09')
- mix_clip_07_muffled 500 ms OFF (24300, 29220, 'UDK_09')
- mix_clip_07_muffled 1000 ms OFF (24300, 29220, 'UDK_09')
- mix_clip_17_muffled 250 ms OFF (1260, 5820, 'UDK_19')
- mix_clip_17_muffled 500 ms OFF (1260, 5820, 'UDK_19')
- mix_clip_17_muffled 1000 ms OFF (1260, 5820, 'UDK_19')
- mix_clip_19_muffled 100 ms OFF (6510, 10950, 'UDK_08')
- mix_clip_19_muffled 250 ms OFF (6510, 10950, 'UDK_08')
- mix_clip_21_clean 20 ms OFF (12900, 17610, 'UDK_01')
- mix_clip_23_muffled 20 ms OFF (9300, 14610, 'UDK_20')
- mix_clip_23_muffled 20 ms OFF (9300, 14670, 'UDK_20')
- mix_clip_28_overlapping 20 ms OFF (8250, 13860, 'UDK_04')
- mix_clip_28_overlapping 20 ms OFF (8250, 13950, 'UDK_04')
- mix_clip_28_overlapping 100 ms OFF (8250, 13860, 'UDK_04')
- mix_clip_28_overlapping 100 ms OFF (8250, 13950, 'UDK_04')
- mix_clip_28_overlapping 250 ms OFF (8250, 13950, 'UDK_04')
- mix_clip_28_overlapping 500 ms OFF (8250, 13860, 'UDK_04')
- mix_clip_28_overlapping 500 ms OFF (8250, 13950, 'UDK_04')
- mix_clip_29_clean 20 ms OFF (2370, 7410, 'UDK_09')

Flagged for review (193): not 'expected_vad_correction', or an OFF-only segment that alerted
- ('mix_clip_01_clean', 250, 'segment_only_off', (19050, 23400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_01_clean', 500, 'segment_only_off', (19050, 23400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_01_clean', 1000, 'segment_only_off', (19050, 23400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_02_noisy', 20, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_02_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 20, 'segment_only_off', (7860, 18840), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_02_noisy', 20, 'segment_only_off', (17340, 27810), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 20, 'segment_only_off', (26400, 30000), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 100, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 100, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 100, 'segment_only_off', (7860, 18840), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_02_noisy', 100, 'segment_only_off', (17340, 27810), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 100, 'segment_only_off', (26400, 30000), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_02_noisy', 250, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_02_noisy', 500, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_02_noisy', 1000, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_04_overlapping', 20, 'segment_only_off', (0, 4710), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_04_overlapping', 20, 'segment_only_off', (0, 4800), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_04_overlapping', 20, 'segment_only_off', (0, 4830), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_04_overlapping', 100, 'segment_only_off', (0, 4710), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_04_overlapping', 100, 'segment_only_off', (0, 4800), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_04_overlapping', 100, 'segment_only_off', (0, 4830), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_04_overlapping', 250, 'segment_only_off', (0, 4710), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_04_overlapping', 250, 'segment_only_off', (0, 4800), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_04_overlapping', 500, 'segment_only_off', (0, 4710), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_04_overlapping', 500, 'segment_only_off', (0, 4800), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_04_overlapping', 1000, 'segment_only_off', (0, 4710), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 20, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 100, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 250, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 500, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_05_clean', 1000, 'segment_only_off', (5370, 9570), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 20, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 20, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_06_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_06_noisy', 20, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 20, 'segment_only_off', (22560, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 100, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_06_noisy', 100, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 250, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 250, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 500, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 500, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_06_noisy', 1000, 'segment_only_off', (17730, 22290), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 20, 'segment_only_off', (24300, 29190), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 20, 'segment_only_off', (24300, 29250), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 20, 'segment_only_off', (24300, 29280), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 100, 'segment_only_off', (24300, 29190), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 100, 'segment_only_off', (24300, 29220), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 100, 'segment_only_off', (24300, 29250), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 250, 'segment_only_off', (24300, 29190), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_07_muffled', 250, 'segment_only_off', (24300, 29220), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 500, 'segment_only_off', (24300, 29220), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_07_muffled', 1000, 'segment_only_off', (24300, 29220), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_08_overlapping', 20, 'segment_only_off', (1050, 6180), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_08_overlapping', 100, 'segment_only_off', (1050, 6180), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_08_overlapping', 250, 'segment_only_off', (1050, 6180), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_08_overlapping', 500, 'segment_only_off', (1050, 6180), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_08_overlapping', 1000, 'segment_only_off', (1050, 6180), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_10_noisy', 20, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_10_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_10_noisy', 20, 'segment_only_off', (25950, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_10_noisy', 100, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_10_noisy', 100, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_10_noisy', 100, 'segment_only_off', (26010, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_10_noisy', 250, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_10_noisy', 250, 'segment_only_off', (26010, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_10_noisy', 500, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_10_noisy', 1000, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_12_noisy', 20, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_12_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_12_noisy', 20, 'segment_only_off', (21630, 26490), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_12_noisy', 100, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_12_noisy', 100, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_12_noisy', 250, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_12_noisy', 250, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_12_noisy', 500, 'segment_only_off', (0, 1680), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_12_noisy', 1000, 'segment_only_off', (0, 1680), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 20, 'segment_only_off', (12990, 23970), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 20, 'segment_only_off', (22470, 30000), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 100, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 100, 'segment_only_off', (12990, 23970), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 100, 'segment_only_off', (22470, 30000), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 250, 'segment_only_off', (0, 1680), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 250, 'segment_only_off', (12990, 23970), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 250, 'segment_only_off', (22470, 30000), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 500, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 500, 'segment_only_off', (12990, 23970), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 500, 'segment_only_off', (22470, 30000), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 1000, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 1000, 'segment_only_off', (12990, 23970), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_14_noisy', 1000, 'segment_only_off', (13380, 24270), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_14_noisy', 1000, 'segment_only_off', (22860, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 20, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 100, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 250, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 500, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_15_muffled', 1000, 'segment_only_off', (13350, 18210), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_17_muffled', 20, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_17_muffled', 100, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_17_muffled', 250, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_17_muffled', 500, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_17_muffled', 1000, 'segment_only_off', (1260, 5820), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_18_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_18_noisy', 20, 'segment_only_off', (9720, 20160), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 20, 'segment_only_off', (18750, 29730), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 20, 'segment_only_off', (28230, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 100, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_18_noisy', 100, 'segment_only_off', (9720, 20160), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 100, 'segment_only_off', (18750, 29730), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 100, 'segment_only_off', (28230, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 250, 'segment_only_off', (0, 1650), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 250, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_18_noisy', 250, 'segment_only_off', (9720, 20160), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 250, 'segment_only_off', (18750, 29730), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 250, 'segment_only_off', (28230, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 500, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 500, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_18_noisy', 500, 'segment_only_off', (9720, 20160), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 500, 'segment_only_off', (18750, 29730), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 500, 'segment_only_off', (28230, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 1000, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 1000, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_18_noisy', 1000, 'segment_only_off', (9720, 20160), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 1000, 'segment_only_off', (18750, 29730), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_18_noisy', 1000, 'segment_only_off', (28230, 30000), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 20, 'segment_only_off', (6510, 10950), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 100, 'segment_only_off', (6510, 10920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 100, 'segment_only_off', (6510, 10950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_19_muffled', 250, 'segment_only_off', (6510, 10920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 250, 'segment_only_off', (6510, 10950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_19_muffled', 500, 'segment_only_off', (6510, 10920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_19_muffled', 500, 'segment_only_off', (6510, 10950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_19_muffled', 1000, 'segment_only_off', (6510, 10920), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 20, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 20, 'segment_only_off', (12900, 17610), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_21_clean', 100, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 250, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 500, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_21_clean', 1000, 'segment_only_off', (12900, 17580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 20, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 100, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 250, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 500, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_22_clean', 1000, 'segment_only_off', (16110, 20400), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_23_muffled', 20, 'segment_only_off', (9300, 14580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_23_muffled', 20, 'segment_only_off', (9300, 14610), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_23_muffled', 20, 'segment_only_off', (9300, 14670), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_23_muffled', 100, 'segment_only_off', (9300, 14580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_23_muffled', 250, 'segment_only_off', (9300, 14580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_23_muffled', 500, 'segment_only_off', (9300, 14580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_23_muffled', 1000, 'segment_only_off', (9300, 14580), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 20, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 100, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 250, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 500, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_27_muffled', 1000, 'segment_only_off', (21300, 26220), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_28_overlapping', 20, 'segment_only_off', (8250, 13830), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_28_overlapping', 20, 'segment_only_off', (8250, 13860), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 20, 'segment_only_off', (8250, 13950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 100, 'segment_only_off', (8250, 13830), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_28_overlapping', 100, 'segment_only_off', (8250, 13860), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 100, 'segment_only_off', (8250, 13950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 250, 'segment_only_off', (8250, 13830), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_28_overlapping', 250, 'segment_only_off', (8250, 13950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 500, 'segment_only_off', (8250, 13830), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_28_overlapping', 500, 'segment_only_off', (8250, 13860), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 500, 'segment_only_off', (8250, 13950), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_28_overlapping', 1000, 'segment_only_off', (8250, 13860), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_29_clean', 20, 'segment_only_off', (0, 3870), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_29_clean', 20, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_29_clean', 100, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_29_clean', 250, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_29_clean', 500, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_29_clean', 1000, 'segment_only_off', (2370, 7410), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 20, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 20, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 20, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 20, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 20, 'segment_only_off', (6330, 17310), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 100, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 100, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 100, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 100, 'segment_only_off', (6330, 17310), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 250, 'segment_only_off', (0, 1590), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 250, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 250, 'segment_only_off', (0, 1680), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 250, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 250, 'segment_only_off', (6330, 17310), 'expected_vad_correction', 'drifted boundary: OFF cut a one-shot utterance at a different frame', None)
- ('mix_clip_30_noisy', 500, 'segment_only_off', (0, 1650), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 500, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)
- ('mix_clip_30_noisy', 1000, 'segment_only_off', (1050, 5880), 'expected_vad_correction', 're-processing: OFF handed already-processed audio to STT again', None)

Performance (per recording x chunk, repeat 0): live-loop call latency and totals
| Recording | Chunk | Mode | Calls | p50 ms | p95 ms | max ms | Total s | Wall s | CPU s | Components s | GPU peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mix_clip_01_clean | 20 | OFF | 1501 | 8.18 | 17.23 | 53.74 | 13.523 | 13.534 | 12.279 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_01_clean | 20 | ON | 1501 | 7.73 | 15.55 | 26.67 | 12.106 | 12.119 | 10.875 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 100 | OFF | 301 | 3.56 | 8.4 | 12.67 | 1.23 | 1.232 | 1.125 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_01_clean | 100 | ON | 301 | 2.34 | 5.18 | 6.6 | 0.749 | 0.752 | 0.664 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 250 | OFF | 121 | 3.51 | 6.93 | 11.4 | 0.464 | 0.466 | 0.423 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 250 | ON | 121 | 1.85 | 2.52 | 4.31 | 0.226 | 0.227 | 0.191 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 500 | OFF | 61 | 4.02 | 7.72 | 8.66 | 0.265 | 0.266 | 0.218 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 500 | ON | 61 | 1.81 | 2.89 | 4.83 | 0.117 | 0.118 | 0.095 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 1000 | OFF | 31 | 3.32 | 7.63 | 8.48 | 0.128 | 0.128 | 0.115 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_01_clean | 1000 | ON | 31 | 2.25 | 3.29 | 4.76 | 0.071 | 0.072 | 0.057 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 20 | OFF | 1501 | 9.31 | 18.14 | 30.15 | 14.641 | 14.653 | 13.417 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 20 | ON | 1501 | 6.95 | 15.67 | 27.37 | 11.648 | 11.66 | 10.51 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 100 | OFF | 301 | 5.34 | 9.69 | 15.44 | 1.535 | 1.538 | 1.352 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 100 | ON | 301 | 2.77 | 5.35 | 43.05 | 0.907 | 0.909 | 0.757 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 250 | OFF | 121 | 3.88 | 8.58 | 17.92 | 0.546 | 0.547 | 0.471 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 250 | ON | 121 | 2.45 | 4.03 | 5.54 | 0.289 | 0.29 | 0.236 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 500 | OFF | 61 | 4.19 | 8.57 | 8.95 | 0.281 | 0.282 | 0.246 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 500 | ON | 61 | 2.19 | 3.9 | 4.95 | 0.147 | 0.148 | 0.113 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 1000 | OFF | 31 | 4.9 | 10.8 | 14.01 | 0.17 | 0.171 | 0.156 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_02_noisy | 1000 | ON | 31 | 2.25 | 3.99 | 4.92 | 0.077 | 0.078 | 0.067 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 20 | OFF | 1501 | 9.2 | 18.03 | 30.74 | 14.402 | 14.417 | 13.297 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_03_muffled | 20 | ON | 1501 | 7.51 | 15.98 | 31.59 | 12.178 | 12.19 | 11.056 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 100 | OFF | 301 | 5.44 | 8.64 | 14.36 | 1.596 | 1.603 | 1.371 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_03_muffled | 100 | ON | 301 | 3.35 | 6.72 | 34.5 | 1.082 | 1.086 | 0.836 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 250 | OFF | 121 | 3.86 | 6.35 | 8.36 | 0.465 | 0.466 | 0.396 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 250 | ON | 121 | 2.13 | 3.34 | 4.96 | 0.265 | 0.266 | 0.226 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 500 | OFF | 61 | 3.39 | 5.63 | 6.86 | 0.208 | 0.209 | 0.195 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 500 | ON | 61 | 2.1 | 2.73 | 4.1 | 0.125 | 0.125 | 0.103 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 1000 | OFF | 31 | 3.64 | 5.55 | 6.37 | 0.113 | 0.114 | 0.103 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_03_muffled | 1000 | ON | 31 | 1.81 | 2.28 | 3.46 | 0.058 | 0.059 | 0.052 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 20 | OFF | 1501 | 8.54 | 18.11 | 30.35 | 14.023 | 14.034 | 13.122 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 20 | ON | 1501 | 7.64 | 16.2 | 41.03 | 12.025 | 12.037 | 10.855 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 100 | OFF | 301 | 5.42 | 9.18 | 76.0 | 1.691 | 1.695 | 1.396 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 100 | ON | 301 | 2.95 | 4.21 | 7.25 | 0.832 | 0.835 | 0.694 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 250 | OFF | 121 | 5.16 | 7.44 | 8.52 | 0.609 | 0.61 | 0.535 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 250 | ON | 121 | 2.02 | 3.52 | 5.25 | 0.258 | 0.259 | 0.221 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 500 | OFF | 61 | 3.39 | 5.76 | 7.08 | 0.209 | 0.21 | 0.194 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 500 | ON | 61 | 1.75 | 2.89 | 4.25 | 0.113 | 0.114 | 0.097 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 1000 | OFF | 31 | 3.97 | 7.65 | 11.51 | 0.146 | 0.147 | 0.125 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_04_overlapping | 1000 | ON | 31 | 1.97 | 2.73 | 6.18 | 0.068 | 0.068 | 0.056 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 20 | OFF | 1501 | 10.88 | 20.52 | 42.39 | 15.845 | 15.858 | 14.387 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 20 | ON | 1501 | 8.03 | 18.59 | 37.43 | 13.308 | 13.324 | 11.958 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 100 | OFF | 301 | 3.99 | 9.09 | 11.85 | 1.373 | 1.375 | 1.239 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 100 | ON | 301 | 3.04 | 5.72 | 9.44 | 0.936 | 0.939 | 0.783 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 250 | OFF | 121 | 4.15 | 6.06 | 7.72 | 0.467 | 0.469 | 0.405 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 250 | ON | 121 | 1.97 | 2.76 | 9.03 | 0.248 | 0.25 | 0.198 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 500 | OFF | 61 | 5.0 | 7.43 | 14.79 | 0.305 | 0.306 | 0.25 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.002} | None |
| mix_clip_05_clean | 500 | ON | 61 | 2.13 | 3.35 | 4.35 | 0.135 | 0.136 | 0.108 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 1000 | OFF | 31 | 4.07 | 6.46 | 6.67 | 0.134 | 0.135 | 0.117 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_05_clean | 1000 | ON | 31 | 2.18 | 3.21 | 4.25 | 0.072 | 0.073 | 0.061 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 20 | OFF | 1501 | 9.73 | 22.82 | 83.15 | 16.535 | 16.548 | 15.09 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 20 | ON | 1501 | 8.35 | 16.06 | 32.5 | 12.681 | 12.694 | 11.402 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 100 | OFF | 301 | 5.02 | 10.81 | 28.08 | 1.593 | 1.596 | 1.383 | {'whisper.transcribe': 0.003, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 100 | ON | 301 | 2.83 | 4.82 | 9.9 | 0.89 | 0.893 | 0.719 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 250 | OFF | 121 | 4.5 | 8.7 | 10.74 | 0.579 | 0.58 | 0.493 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 250 | ON | 121 | 2.16 | 3.7 | 9.1 | 0.285 | 0.286 | 0.228 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 500 | OFF | 61 | 3.55 | 7.8 | 18.18 | 0.277 | 0.278 | 0.248 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 500 | ON | 61 | 2.15 | 4.43 | 7.09 | 0.149 | 0.15 | 0.111 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 1000 | OFF | 31 | 3.7 | 7.43 | 10.03 | 0.14 | 0.141 | 0.126 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_06_noisy | 1000 | ON | 31 | 2.21 | 3.83 | 9.9 | 0.079 | 0.08 | 0.067 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 20 | OFF | 1501 | 9.12 | 24.89 | 35.19 | 16.346 | 16.36 | 14.821 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.001} | None |
| mix_clip_07_muffled | 20 | ON | 1501 | 9.65 | 20.27 | 35.57 | 14.474 | 14.489 | 13.071 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 100 | OFF | 301 | 4.47 | 9.73 | 12.38 | 1.456 | 1.458 | 1.263 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_07_muffled | 100 | ON | 301 | 2.72 | 4.22 | 6.83 | 0.818 | 0.82 | 0.692 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 250 | OFF | 121 | 3.22 | 6.28 | 8.74 | 0.425 | 0.426 | 0.37 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 250 | ON | 121 | 1.92 | 4.22 | 7.16 | 0.271 | 0.272 | 0.222 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 500 | OFF | 61 | 3.21 | 6.08 | 11.25 | 0.206 | 0.206 | 0.179 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 500 | ON | 61 | 1.77 | 2.46 | 4.29 | 0.11 | 0.111 | 0.089 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_07_muffled | 1000 | OFF | 31 | 3.34 | 7.07 | 9.21 | 0.119 | 0.12 | 0.104 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_07_muffled | 1000 | ON | 31 | 2.25 | 3.22 | 11.38 | 0.079 | 0.08 | 0.056 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 20 | OFF | 1501 | 10.27 | 22.52 | 66.16 | 15.859 | 15.873 | 14.462 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_08_overlapping | 20 | ON | 1501 | 8.27 | 18.56 | 27.96 | 13.662 | 13.676 | 12.278 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 100 | OFF | 301 | 6.28 | 13.21 | 27.03 | 1.96 | 1.964 | 1.714 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 100 | ON | 301 | 4.2 | 7.53 | 14.52 | 1.278 | 1.281 | 1.05 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 250 | OFF | 121 | 4.51 | 6.67 | 11.78 | 0.562 | 0.564 | 0.494 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_08_overlapping | 250 | ON | 121 | 1.89 | 2.48 | 3.85 | 0.224 | 0.225 | 0.195 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 500 | OFF | 61 | 4.59 | 6.81 | 22.6 | 0.285 | 0.286 | 0.246 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 500 | ON | 61 | 2.96 | 4.11 | 6.62 | 0.18 | 0.181 | 0.15 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 1000 | OFF | 31 | 5.39 | 8.35 | 8.9 | 0.162 | 0.163 | 0.148 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_08_overlapping | 1000 | ON | 31 | 2.21 | 2.76 | 8.08 | 0.074 | 0.075 | 0.065 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_09_clean | 20 | OFF | 1501 | 11.32 | 27.74 | 36.88 | 18.596 | 18.612 | 16.948 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_09_clean | 20 | ON | 1501 | 9.87 | 17.62 | 58.8 | 14.445 | 14.46 | 12.908 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_09_clean | 100 | OFF | 301 | 5.13 | 10.12 | 16.33 | 1.531 | 1.534 | 1.335 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_09_clean | 100 | ON | 301 | 2.72 | 6.41 | 9.24 | 0.97 | 0.973 | 0.823 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_09_clean | 250 | OFF | 121 | 3.49 | 7.08 | 10.26 | 0.456 | 0.458 | 0.399 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_09_clean | 250 | ON | 121 | 1.88 | 2.93 | 7.45 | 0.254 | 0.256 | 0.214 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_09_clean | 500 | OFF | 61 | 3.98 | 7.8 | 9.45 | 0.25 | 0.25 | 0.227 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_09_clean | 500 | ON | 61 | 2.06 | 5.14 | 8.62 | 0.147 | 0.148 | 0.125 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_09_clean | 1000 | OFF | 31 | 3.6 | 10.34 | 20.65 | 0.15 | 0.151 | 0.137 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_09_clean | 1000 | ON | 31 | 2.66 | 6.46 | 8.31 | 0.101 | 0.101 | 0.087 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 20 | OFF | 1501 | 11.15 | 20.37 | 55.61 | 16.348 | 16.362 | 15.096 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 20 | ON | 1501 | 8.35 | 15.55 | 28.62 | 12.546 | 12.561 | 11.333 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 100 | OFF | 301 | 5.53 | 10.04 | 16.43 | 1.655 | 1.658 | 1.454 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 100 | ON | 301 | 2.98 | 4.85 | 10.43 | 0.915 | 0.917 | 0.76 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 250 | OFF | 121 | 5.13 | 9.53 | 18.98 | 0.685 | 0.687 | 0.587 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 250 | ON | 121 | 2.98 | 6.17 | 13.86 | 0.431 | 0.434 | 0.341 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 500 | OFF | 61 | 6.37 | 13.0 | 19.51 | 0.428 | 0.43 | 0.385 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 500 | ON | 61 | 3.62 | 4.82 | 25.76 | 0.248 | 0.249 | 0.218 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 1000 | OFF | 31 | 8.26 | 13.94 | 22.25 | 0.272 | 0.273 | 0.243 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_10_noisy | 1000 | ON | 31 | 4.04 | 7.82 | 11.07 | 0.141 | 0.142 | 0.114 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_11_muffled | 20 | OFF | 1501 | 10.91 | 22.63 | 43.06 | 17.308 | 17.325 | 15.803 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.001} | None |
| mix_clip_11_muffled | 20 | ON | 1501 | 9.23 | 25.07 | 60.13 | 16.397 | 16.414 | 14.78 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_11_muffled | 100 | OFF | 301 | 5.25 | 13.97 | 17.77 | 1.689 | 1.692 | 1.505 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_11_muffled | 100 | ON | 301 | 3.61 | 7.77 | 34.05 | 1.236 | 1.24 | 1.003 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_11_muffled | 250 | OFF | 121 | 3.7 | 8.45 | 12.33 | 0.542 | 0.543 | 0.477 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_11_muffled | 250 | ON | 121 | 2.17 | 3.75 | 7.08 | 0.296 | 0.298 | 0.247 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_11_muffled | 500 | OFF | 61 | 3.49 | 10.0 | 19.7 | 0.289 | 0.29 | 0.26 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_11_muffled | 500 | ON | 61 | 2.01 | 3.72 | 6.95 | 0.138 | 0.139 | 0.115 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_11_muffled | 1000 | OFF | 31 | 5.38 | 10.39 | 15.45 | 0.189 | 0.19 | 0.169 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_11_muffled | 1000 | ON | 31 | 3.6 | 7.31 | 10.46 | 0.128 | 0.129 | 0.101 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 20 | OFF | 1501 | 11.16 | 21.99 | 33.71 | 16.891 | 16.908 | 15.498 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 20 | ON | 1501 | 9.15 | 17.8 | 91.21 | 14.043 | 14.057 | 12.731 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 100 | OFF | 301 | 5.87 | 12.27 | 19.96 | 2.021 | 2.024 | 1.766 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 100 | ON | 301 | 3.51 | 5.88 | 11.46 | 1.08 | 1.083 | 0.903 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 250 | OFF | 121 | 4.62 | 7.51 | 18.13 | 0.58 | 0.582 | 0.488 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 250 | ON | 121 | 2.21 | 4.0 | 10.44 | 0.304 | 0.305 | 0.251 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 500 | OFF | 61 | 4.46 | 8.17 | 14.07 | 0.284 | 0.285 | 0.25 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 500 | ON | 61 | 2.82 | 7.32 | 10.38 | 0.217 | 0.218 | 0.161 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 1000 | OFF | 31 | 5.02 | 7.6 | 18.22 | 0.172 | 0.173 | 0.151 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_12_noisy | 1000 | ON | 31 | 3.3 | 4.73 | 12.13 | 0.105 | 0.106 | 0.09 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 20 | OFF | 1501 | 12.38 | 25.48 | 46.59 | 18.41 | 18.425 | 16.675 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_13_clean | 20 | ON | 1501 | 8.81 | 17.98 | 30.15 | 13.996 | 14.01 | 12.66 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 100 | OFF | 301 | 5.45 | 12.61 | 20.57 | 1.74 | 1.744 | 1.519 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 100 | ON | 301 | 2.94 | 8.3 | 11.94 | 1.155 | 1.159 | 0.94 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 250 | OFF | 121 | 4.67 | 8.91 | 13.86 | 0.597 | 0.599 | 0.542 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_13_clean | 250 | ON | 121 | 2.19 | 4.09 | 12.33 | 0.301 | 0.303 | 0.264 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 500 | OFF | 61 | 4.09 | 7.56 | 13.39 | 0.26 | 0.261 | 0.236 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 500 | ON | 61 | 2.32 | 3.66 | 10.46 | 0.156 | 0.157 | 0.138 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 1000 | OFF | 31 | 4.7 | 8.29 | 15.26 | 0.163 | 0.164 | 0.14 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_13_clean | 1000 | ON | 31 | 2.88 | 5.22 | 9.9 | 0.107 | 0.107 | 0.092 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 20 | OFF | 1501 | 11.68 | 26.29 | 57.31 | 18.302 | 18.32 | 16.656 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 20 | ON | 1501 | 9.12 | 19.48 | 59.83 | 14.569 | 14.589 | 13.016 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 100 | OFF | 301 | 6.67 | 13.29 | 16.65 | 2.079 | 2.083 | 1.883 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 100 | ON | 301 | 3.48 | 7.73 | 14.19 | 1.186 | 1.19 | 0.977 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 250 | OFF | 121 | 4.77 | 8.16 | 9.95 | 0.598 | 0.6 | 0.531 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 250 | ON | 121 | 2.09 | 4.27 | 10.91 | 0.298 | 0.299 | 0.252 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 500 | OFF | 61 | 4.4 | 7.56 | 14.0 | 0.275 | 0.276 | 0.252 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 500 | ON | 61 | 2.47 | 4.09 | 12.01 | 0.165 | 0.166 | 0.143 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 1000 | OFF | 31 | 5.31 | 8.24 | 8.86 | 0.16 | 0.161 | 0.145 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_14_noisy | 1000 | ON | 31 | 2.5 | 4.16 | 12.69 | 0.096 | 0.096 | 0.086 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 20 | OFF | 1501 | 11.46 | 21.12 | 45.2 | 17.049 | 17.065 | 15.521 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_15_muffled | 20 | ON | 1501 | 8.46 | 18.18 | 40.57 | 13.512 | 13.528 | 12.126 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 100 | OFF | 301 | 5.84 | 9.89 | 22.38 | 1.733 | 1.737 | 1.536 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_15_muffled | 100 | ON | 301 | 3.28 | 6.63 | 15.04 | 1.085 | 1.088 | 0.863 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 250 | OFF | 121 | 4.49 | 8.19 | 21.73 | 0.593 | 0.595 | 0.496 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 250 | ON | 121 | 2.39 | 4.43 | 22.13 | 0.342 | 0.344 | 0.287 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 500 | OFF | 61 | 4.35 | 6.91 | 11.71 | 0.264 | 0.265 | 0.231 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 500 | ON | 61 | 2.18 | 4.35 | 11.2 | 0.154 | 0.155 | 0.129 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_15_muffled | 1000 | OFF | 31 | 5.9 | 9.52 | 16.26 | 0.182 | 0.182 | 0.157 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.001} | None |
| mix_clip_15_muffled | 1000 | ON | 31 | 3.11 | 5.15 | 10.27 | 0.106 | 0.106 | 0.091 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 20 | OFF | 1501 | 9.6 | 23.52 | 38.32 | 15.997 | 16.011 | 14.814 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_16_overlapping | 20 | ON | 1501 | 9.46 | 21.92 | 32.35 | 15.33 | 15.345 | 13.948 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 100 | OFF | 301 | 5.07 | 11.93 | 22.88 | 1.682 | 1.685 | 1.512 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 100 | ON | 301 | 3.44 | 7.55 | 55.1 | 1.175 | 1.178 | 0.989 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 250 | OFF | 121 | 3.72 | 7.58 | 25.74 | 0.519 | 0.521 | 0.444 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 250 | ON | 121 | 2.6 | 5.97 | 38.95 | 0.395 | 0.397 | 0.323 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 500 | OFF | 61 | 3.66 | 8.7 | 15.56 | 0.272 | 0.272 | 0.233 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 500 | ON | 61 | 2.54 | 4.97 | 21.14 | 0.197 | 0.198 | 0.147 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 1000 | OFF | 31 | 3.61 | 6.68 | 11.79 | 0.129 | 0.129 | 0.121 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_16_overlapping | 1000 | ON | 31 | 2.16 | 3.12 | 8.78 | 0.075 | 0.076 | 0.069 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_17_muffled | 20 | OFF | 1501 | 11.03 | 24.98 | 88.78 | 17.418 | 17.433 | 15.824 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_17_muffled | 20 | ON | 1501 | 7.76 | 15.93 | 35.93 | 12.363 | 12.377 | 11.175 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_17_muffled | 100 | OFF | 301 | 4.55 | 11.64 | 18.18 | 1.517 | 1.52 | 1.32 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_17_muffled | 100 | ON | 301 | 3.25 | 5.03 | 37.9 | 0.968 | 0.971 | 0.765 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_17_muffled | 250 | OFF | 121 | 5.01 | 7.3 | 13.8 | 0.572 | 0.574 | 0.504 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_17_muffled | 250 | ON | 121 | 2.38 | 4.8 | 14.12 | 0.337 | 0.338 | 0.279 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_17_muffled | 500 | OFF | 61 | 4.27 | 7.42 | 9.28 | 0.297 | 0.298 | 0.255 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_17_muffled | 500 | ON | 61 | 2.21 | 3.13 | 4.6 | 0.137 | 0.138 | 0.115 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_17_muffled | 1000 | OFF | 31 | 4.27 | 6.36 | 12.4 | 0.141 | 0.141 | 0.127 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_17_muffled | 1000 | ON | 31 | 2.39 | 3.42 | 8.87 | 0.083 | 0.083 | 0.072 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 20 | OFF | 1501 | 9.21 | 23.38 | 99.24 | 16.059 | 16.073 | 14.528 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 20 | ON | 1501 | 8.16 | 17.03 | 59.26 | 12.863 | 12.877 | 11.588 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 100 | OFF | 301 | 5.07 | 8.4 | 15.44 | 1.496 | 1.499 | 1.36 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 100 | ON | 301 | 3.19 | 5.74 | 14.29 | 0.976 | 0.978 | 0.838 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 250 | OFF | 121 | 4.4 | 8.11 | 15.36 | 0.581 | 0.583 | 0.509 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 250 | ON | 121 | 3.02 | 5.33 | 12.84 | 0.397 | 0.398 | 0.299 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 500 | OFF | 61 | 6.32 | 10.54 | 13.49 | 0.352 | 0.353 | 0.308 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 500 | ON | 61 | 2.56 | 7.27 | 11.63 | 0.194 | 0.195 | 0.151 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 1000 | OFF | 31 | 6.48 | 8.1 | 12.06 | 0.189 | 0.189 | 0.175 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_18_noisy | 1000 | ON | 31 | 2.46 | 3.97 | 9.26 | 0.091 | 0.092 | 0.082 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_19_muffled | 20 | OFF | 1501 | 10.22 | 18.76 | 33.11 | 15.209 | 15.226 | 13.848 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_19_muffled | 20 | ON | 1501 | 7.78 | 15.46 | 28.42 | 12.332 | 12.345 | 11.171 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_19_muffled | 100 | OFF | 301 | 4.92 | 8.37 | 11.64 | 1.453 | 1.456 | 1.267 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_19_muffled | 100 | ON | 301 | 3.07 | 5.01 | 20.24 | 0.929 | 0.932 | 0.771 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_19_muffled | 250 | OFF | 121 | 4.08 | 5.64 | 12.2 | 0.457 | 0.459 | 0.398 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_19_muffled | 250 | ON | 121 | 1.89 | 4.56 | 14.96 | 0.288 | 0.289 | 0.231 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_19_muffled | 500 | OFF | 61 | 4.0 | 7.46 | 12.64 | 0.258 | 0.259 | 0.228 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_19_muffled | 500 | ON | 61 | 2.15 | 5.11 | 9.4 | 0.157 | 0.158 | 0.121 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_19_muffled | 1000 | OFF | 31 | 3.84 | 6.41 | 11.9 | 0.128 | 0.128 | 0.117 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_19_muffled | 1000 | ON | 31 | 2.42 | 3.59 | 9.19 | 0.084 | 0.084 | 0.072 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 20 | OFF | 1501 | 9.58 | 17.82 | 250.13 | 15.178 | 15.192 | 13.809 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.001} | None |
| mix_clip_20_muffled | 20 | ON | 1501 | 7.49 | 15.88 | 26.81 | 12.339 | 12.352 | 11.256 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 100 | OFF | 301 | 4.63 | 8.8 | 15.16 | 1.384 | 1.387 | 1.279 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_20_muffled | 100 | ON | 301 | 2.72 | 5.82 | 10.69 | 0.88 | 0.883 | 0.776 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 250 | OFF | 121 | 4.48 | 7.73 | 15.4 | 0.578 | 0.579 | 0.485 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 250 | ON | 121 | 2.07 | 3.11 | 11.27 | 0.268 | 0.269 | 0.221 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 500 | OFF | 61 | 3.65 | 9.09 | 12.0 | 0.264 | 0.265 | 0.23 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 500 | ON | 61 | 2.24 | 4.32 | 12.45 | 0.158 | 0.159 | 0.132 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 1000 | OFF | 31 | 4.94 | 7.42 | 13.1 | 0.159 | 0.16 | 0.148 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_20_muffled | 1000 | ON | 31 | 2.53 | 4.59 | 11.7 | 0.093 | 0.093 | 0.081 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_21_clean | 20 | OFF | 1501 | 9.06 | 20.86 | 41.22 | 15.506 | 15.519 | 14.125 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_21_clean | 20 | ON | 1501 | 7.7 | 15.62 | 25.72 | 12.036 | 12.048 | 10.866 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_21_clean | 100 | OFF | 301 | 5.59 | 8.72 | 15.34 | 1.572 | 1.575 | 1.381 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_21_clean | 100 | ON | 301 | 2.74 | 7.24 | 17.09 | 1.094 | 1.097 | 0.92 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_21_clean | 250 | OFF | 121 | 4.54 | 7.42 | 14.98 | 0.576 | 0.578 | 0.506 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_21_clean | 250 | ON | 121 | 2.72 | 4.29 | 12.57 | 0.331 | 0.332 | 0.275 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_21_clean | 500 | OFF | 61 | 4.44 | 10.2 | 16.53 | 0.317 | 0.318 | 0.276 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_21_clean | 500 | ON | 61 | 2.34 | 4.02 | 10.78 | 0.162 | 0.163 | 0.136 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_21_clean | 1000 | OFF | 31 | 6.38 | 8.67 | 10.94 | 0.2 | 0.201 | 0.18 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_21_clean | 1000 | ON | 31 | 3.91 | 5.72 | 8.47 | 0.127 | 0.127 | 0.113 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 20 | OFF | 1501 | 10.03 | 20.51 | 60.16 | 16.133 | 16.148 | 14.718 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_22_clean | 20 | ON | 1501 | 9.91 | 16.94 | 31.02 | 13.776 | 13.79 | 12.432 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 100 | OFF | 301 | 4.41 | 8.77 | 13.63 | 1.498 | 1.501 | 1.323 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_22_clean | 100 | ON | 301 | 2.76 | 7.47 | 26.52 | 1.035 | 1.039 | 0.876 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 250 | OFF | 121 | 4.84 | 9.77 | 29.52 | 0.592 | 0.594 | 0.503 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 250 | ON | 121 | 2.19 | 4.34 | 8.57 | 0.289 | 0.29 | 0.232 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 500 | OFF | 61 | 3.43 | 6.24 | 11.77 | 0.235 | 0.236 | 0.21 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 500 | ON | 61 | 2.12 | 2.99 | 8.18 | 0.138 | 0.139 | 0.113 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 1000 | OFF | 31 | 4.24 | 6.8 | 12.61 | 0.145 | 0.146 | 0.127 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_22_clean | 1000 | ON | 31 | 2.45 | 4.29 | 10.2 | 0.087 | 0.088 | 0.075 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 20 | OFF | 1501 | 9.36 | 19.71 | 37.47 | 15.269 | 15.283 | 13.928 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.002} | None |
| mix_clip_23_muffled | 20 | ON | 1501 | 8.17 | 15.93 | 33.26 | 12.75 | 12.762 | 11.461 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 100 | OFF | 301 | 4.66 | 11.64 | 15.76 | 1.623 | 1.626 | 1.429 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_23_muffled | 100 | ON | 301 | 2.99 | 4.74 | 12.16 | 0.929 | 0.932 | 0.777 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 250 | OFF | 121 | 4.57 | 8.69 | 18.57 | 0.603 | 0.605 | 0.52 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_23_muffled | 250 | ON | 121 | 2.22 | 6.08 | 16.6 | 0.346 | 0.347 | 0.252 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 500 | OFF | 61 | 4.48 | 8.4 | 20.17 | 0.297 | 0.298 | 0.241 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 500 | ON | 61 | 2.08 | 5.23 | 12.49 | 0.165 | 0.166 | 0.14 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 1000 | OFF | 31 | 4.6 | 7.01 | 12.7 | 0.151 | 0.151 | 0.132 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_23_muffled | 1000 | ON | 31 | 2.64 | 4.17 | 9.89 | 0.092 | 0.093 | 0.079 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 20 | OFF | 1501 | 10.54 | 22.42 | 68.64 | 16.398 | 16.412 | 15.056 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.001} | None |
| mix_clip_24_overlapping | 20 | ON | 1501 | 7.75 | 17.49 | 33.75 | 13.313 | 13.328 | 11.866 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 100 | OFF | 301 | 4.89 | 9.64 | 15.98 | 1.605 | 1.608 | 1.43 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_24_overlapping | 100 | ON | 301 | 2.89 | 4.72 | 7.43 | 0.86 | 0.863 | 0.723 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 250 | OFF | 121 | 4.69 | 7.93 | 14.09 | 0.585 | 0.587 | 0.508 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 250 | ON | 121 | 2.27 | 3.27 | 10.37 | 0.294 | 0.295 | 0.242 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 500 | OFF | 61 | 4.57 | 11.13 | 14.91 | 0.302 | 0.303 | 0.257 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 500 | ON | 61 | 2.33 | 3.22 | 9.64 | 0.153 | 0.154 | 0.127 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 1000 | OFF | 31 | 4.2 | 6.23 | 11.58 | 0.134 | 0.135 | 0.123 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_24_overlapping | 1000 | ON | 31 | 2.44 | 4.65 | 8.96 | 0.087 | 0.088 | 0.076 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 20 | OFF | 1501 | 11.26 | 21.01 | 69.87 | 16.43 | 16.445 | 14.928 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_25_clean | 20 | ON | 1501 | 8.26 | 18.74 | 35.68 | 13.427 | 13.443 | 12.176 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 100 | OFF | 301 | 4.58 | 8.69 | 14.29 | 1.47 | 1.472 | 1.274 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.002} | None |
| mix_clip_25_clean | 100 | ON | 301 | 3.52 | 6.03 | 15.05 | 1.079 | 1.083 | 0.902 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 250 | OFF | 121 | 4.89 | 7.24 | 15.29 | 0.561 | 0.562 | 0.492 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 250 | ON | 121 | 2.61 | 4.29 | 18.23 | 0.333 | 0.334 | 0.26 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 500 | OFF | 61 | 5.13 | 7.12 | 13.76 | 0.305 | 0.307 | 0.267 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 500 | ON | 61 | 2.49 | 4.5 | 10.3 | 0.168 | 0.169 | 0.131 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 1000 | OFF | 31 | 4.91 | 6.79 | 12.76 | 0.148 | 0.149 | 0.131 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_25_clean | 1000 | ON | 31 | 3.01 | 5.74 | 12.07 | 0.113 | 0.114 | 0.09 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 20 | OFF | 1501 | 10.53 | 24.0 | 37.06 | 16.879 | 16.895 | 15.364 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_26_clean | 20 | ON | 1501 | 8.74 | 18.46 | 58.85 | 13.712 | 13.727 | 12.336 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 100 | OFF | 301 | 6.11 | 12.71 | 14.73 | 1.839 | 1.842 | 1.61 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_26_clean | 100 | ON | 301 | 3.1 | 5.31 | 21.58 | 0.982 | 0.986 | 0.786 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 250 | OFF | 121 | 3.37 | 7.06 | 14.43 | 0.466 | 0.467 | 0.411 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 250 | ON | 121 | 2.21 | 3.99 | 10.65 | 0.297 | 0.298 | 0.242 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 500 | OFF | 61 | 3.45 | 6.96 | 9.14 | 0.236 | 0.237 | 0.206 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 500 | ON | 61 | 2.33 | 4.92 | 17.58 | 0.177 | 0.178 | 0.143 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 1000 | OFF | 31 | 4.03 | 9.5 | 15.17 | 0.154 | 0.154 | 0.14 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_26_clean | 1000 | ON | 31 | 3.19 | 4.14 | 11.45 | 0.107 | 0.108 | 0.096 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 20 | OFF | 1501 | 10.16 | 23.63 | 39.79 | 15.935 | 15.95 | 14.582 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.001} | None |
| mix_clip_27_muffled | 20 | ON | 1501 | 9.65 | 21.14 | 41.02 | 15.243 | 15.259 | 13.568 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 100 | OFF | 301 | 5.84 | 10.38 | 19.23 | 1.853 | 1.857 | 1.657 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_27_muffled | 100 | ON | 301 | 3.37 | 6.76 | 13.44 | 1.088 | 1.092 | 0.896 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 250 | OFF | 121 | 4.65 | 11.89 | 27.26 | 0.66 | 0.662 | 0.582 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 250 | ON | 121 | 3.64 | 5.52 | 5.8 | 0.463 | 0.465 | 0.399 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 500 | OFF | 61 | 4.59 | 8.83 | 13.17 | 0.302 | 0.304 | 0.276 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 500 | ON | 61 | 2.15 | 4.24 | 9.17 | 0.147 | 0.148 | 0.129 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 1000 | OFF | 31 | 4.61 | 8.55 | 17.27 | 0.156 | 0.156 | 0.139 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_27_muffled | 1000 | ON | 31 | 3.14 | 5.45 | 17.87 | 0.118 | 0.119 | 0.097 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_28_overlapping | 20 | OFF | 1501 | 11.04 | 23.98 | 100.59 | 17.449 | 17.464 | 15.875 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.002} | None |
| mix_clip_28_overlapping | 20 | ON | 1501 | 9.08 | 19.27 | 135.34 | 13.905 | 13.92 | 12.423 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_28_overlapping | 100 | OFF | 301 | 5.86 | 10.63 | 16.31 | 1.783 | 1.786 | 1.569 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_28_overlapping | 100 | ON | 301 | 3.82 | 8.81 | 13.31 | 1.251 | 1.255 | 1.062 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_28_overlapping | 250 | OFF | 121 | 6.76 | 9.87 | 19.74 | 0.769 | 0.771 | 0.71 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_28_overlapping | 250 | ON | 121 | 2.02 | 2.71 | 3.95 | 0.244 | 0.246 | 0.216 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_28_overlapping | 500 | OFF | 61 | 5.28 | 14.07 | 28.73 | 0.386 | 0.387 | 0.353 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_28_overlapping | 500 | ON | 61 | 4.3 | 5.87 | 17.9 | 0.278 | 0.279 | 0.257 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_28_overlapping | 1000 | OFF | 31 | 4.41 | 6.84 | 13.42 | 0.145 | 0.146 | 0.135 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_28_overlapping | 1000 | ON | 31 | 2.58 | 4.23 | 9.61 | 0.092 | 0.093 | 0.083 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 20 | OFF | 1501 | 11.02 | 23.33 | 34.0 | 16.988 | 17.005 | 15.859 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.002} | None |
| mix_clip_29_clean | 20 | ON | 1501 | 8.16 | 22.68 | 57.22 | 14.407 | 14.421 | 13.033 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 100 | OFF | 301 | 5.52 | 12.14 | 21.03 | 1.817 | 1.821 | 1.631 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_29_clean | 100 | ON | 301 | 3.57 | 7.52 | 8.59 | 1.205 | 1.208 | 1.034 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 250 | OFF | 121 | 4.74 | 9.85 | 19.02 | 0.617 | 0.618 | 0.541 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.001} | None |
| mix_clip_29_clean | 250 | ON | 121 | 2.34 | 5.29 | 11.08 | 0.341 | 0.343 | 0.276 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 500 | OFF | 61 | 5.22 | 9.53 | 14.19 | 0.327 | 0.328 | 0.286 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 500 | ON | 61 | 2.41 | 4.45 | 12.88 | 0.187 | 0.188 | 0.141 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 1000 | OFF | 31 | 6.91 | 11.35 | 23.19 | 0.238 | 0.239 | 0.193 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_29_clean | 1000 | ON | 31 | 2.62 | 3.75 | 10.46 | 0.095 | 0.095 | 0.082 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 20 | OFF | 1501 | 11.81 | 26.57 | 43.22 | 18.328 | 18.343 | 16.836 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 20 | ON | 1501 | 9.06 | 16.68 | 58.75 | 14.248 | 14.263 | 12.918 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 100 | OFF | 301 | 5.57 | 11.5 | 15.82 | 1.858 | 1.863 | 1.64 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 100 | ON | 301 | 3.04 | 5.85 | 10.95 | 1.0 | 1.003 | 0.825 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 250 | OFF | 121 | 5.28 | 13.84 | 68.21 | 0.902 | 0.904 | 0.799 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 250 | ON | 121 | 2.87 | 5.71 | 10.88 | 0.386 | 0.388 | 0.306 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 500 | OFF | 61 | 5.88 | 9.03 | 13.79 | 0.353 | 0.354 | 0.31 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 500 | ON | 61 | 3.15 | 4.13 | 6.82 | 0.197 | 0.198 | 0.165 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 1000 | OFF | 31 | 5.18 | 7.63 | 15.27 | 0.166 | 0.167 | 0.146 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| mix_clip_30_noisy | 1000 | ON | 31 | 2.86 | 4.78 | 13.62 | 0.107 | 0.107 | 0.09 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_01 | 100 | OFF | 539 | 9.4 | 22.11 | 48.87 | 5.348 | 5.356 | 4.824 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_01 | 100 | ON | 539 | 4.84 | 10.75 | 19.52 | 3.011 | 3.017 | 2.667 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_01 | 1000 | OFF | 55 | 8.25 | 18.31 | 25.39 | 0.521 | 0.523 | 0.491 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| pos_01 | 1000 | ON | 55 | 4.44 | 7.73 | 18.82 | 0.249 | 0.25 | 0.22 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| pos_02 | 100 | OFF | 506 | 8.67 | 17.11 | 24.38 | 4.503 | 4.51 | 4.102 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| pos_02 | 100 | ON | 506 | 5.48 | 10.47 | 34.49 | 2.823 | 2.829 | 2.428 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_02 | 1000 | OFF | 52 | 6.28 | 11.38 | 43.7 | 0.395 | 0.396 | 0.349 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| pos_02 | 1000 | ON | 52 | 3.61 | 4.6 | 16.6 | 0.195 | 0.196 | 0.178 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_03 | 100 | OFF | 565 | 11.16 | 20.04 | 49.92 | 6.179 | 6.187 | 5.658 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_03 | 100 | ON | 565 | 4.48 | 12.22 | 25.32 | 2.991 | 2.997 | 2.694 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_03 | 1000 | OFF | 58 | 8.39 | 16.7 | 24.56 | 0.538 | 0.54 | 0.492 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_03 | 1000 | ON | 58 | 4.91 | 9.21 | 37.31 | 0.324 | 0.326 | 0.304 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_04 | 100 | OFF | 353 | 8.79 | 14.67 | 24.69 | 3.0 | 3.005 | 2.71 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_04 | 100 | ON | 353 | 4.48 | 8.77 | 22.33 | 1.659 | 1.663 | 1.365 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_04 | 1000 | OFF | 37 | 5.52 | 8.54 | 13.43 | 0.22 | 0.221 | 0.204 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| pos_04 | 1000 | ON | 37 | 3.08 | 4.61 | 11.26 | 0.123 | 0.124 | 0.107 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_01 | 100 | OFF | 602 | 10.67 | 20.51 | 37.18 | 6.744 | 6.753 | 6.01 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| neg_01 | 100 | ON | 602 | 5.86 | 12.61 | 25.25 | 3.812 | 3.819 | 3.38 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_01 | 1000 | OFF | 62 | 11.75 | 17.13 | 32.81 | 0.726 | 0.728 | 0.667 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_01 | 1000 | ON | 62 | 5.56 | 11.4 | 23.36 | 0.407 | 0.409 | 0.351 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_02 | 100 | OFF | 501 | 9.38 | 21.99 | 42.39 | 5.159 | 5.168 | 4.638 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_02 | 100 | ON | 501 | 6.03 | 12.32 | 67.69 | 3.418 | 3.425 | 2.966 | {'whisper.transcribe': 0.001, 'parakeet.transcribe': 0.0} | None |
| neg_02 | 1000 | OFF | 51 | 7.52 | 17.12 | 21.64 | 0.438 | 0.44 | 0.4 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_02 | 1000 | ON | 51 | 5.0 | 7.84 | 31.82 | 0.295 | 0.297 | 0.252 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_03 | 100 | OFF | 478 | 9.12 | 16.46 | 26.3 | 4.381 | 4.387 | 3.999 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_03 | 100 | ON | 478 | 4.75 | 11.17 | 31.67 | 2.679 | 2.685 | 2.361 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_03 | 1000 | OFF | 49 | 6.9 | 12.09 | 20.6 | 0.342 | 0.343 | 0.317 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_03 | 1000 | ON | 49 | 3.8 | 7.37 | 14.96 | 0.221 | 0.222 | 0.201 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_04 | 100 | OFF | 315 | 5.58 | 11.31 | 26.18 | 1.877 | 1.881 | 1.656 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_04 | 100 | ON | 315 | 3.2 | 6.16 | 9.52 | 1.05 | 1.054 | 0.894 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_04 | 1000 | OFF | 33 | 7.21 | 9.48 | 14.27 | 0.23 | 0.231 | 0.207 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_04 | 1000 | ON | 33 | 3.35 | 8.77 | 12.66 | 0.129 | 0.13 | 0.102 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_05 | 100 | OFF | 512 | 8.71 | 17.91 | 34.22 | 4.648 | 4.654 | 4.252 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_05 | 100 | ON | 512 | 5.81 | 11.84 | 25.79 | 3.135 | 3.141 | 2.807 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_05 | 1000 | OFF | 53 | 10.44 | 19.68 | 31.76 | 0.551 | 0.552 | 0.479 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_05 | 1000 | ON | 53 | 5.31 | 7.84 | 22.82 | 0.296 | 0.298 | 0.273 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_06 | 100 | OFF | 174 | 5.45 | 9.08 | 17.59 | 0.974 | 0.977 | 0.88 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_06 | 100 | ON | 174 | 3.27 | 5.42 | 6.33 | 0.575 | 0.577 | 0.483 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_06 | 1000 | OFF | 19 | 6.75 | 8.31 | 8.9 | 0.117 | 0.118 | 0.104 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_06 | 1000 | ON | 19 | 2.63 | 3.27 | 3.49 | 0.051 | 0.052 | 0.042 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_07 | 100 | OFF | 3261 | 46.77 | 89.94 | 145.44 | 156.036 | 156.088 | 149.752 | {'whisper.transcribe': 0.003, 'parakeet.transcribe': 0.0} | None |
| neg_07 | 100 | ON | 3261 | 24.7 | 49.45 | 82.75 | 83.401 | 83.448 | 79.005 | {'whisper.transcribe': 0.002, 'parakeet.transcribe': 0.0} | None |
| neg_07 | 1000 | OFF | 327 | 38.62 | 84.5 | 103.24 | 13.134 | 13.143 | 12.636 | {'whisper.transcribe': 0.003, 'parakeet.transcribe': 0.001} | None |
| neg_07 | 1000 | ON | 327 | 18.06 | 27.73 | 40.92 | 5.402 | 5.41 | 5.102 | {'whisper.transcribe': 0.003, 'parakeet.transcribe': 0.001} | None |
| neg_08 | 100 | OFF | 352 | 7.14 | 13.3 | 19.48 | 2.561 | 2.566 | 2.371 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_08 | 100 | ON | 352 | 4.11 | 8.41 | 22.03 | 1.561 | 1.565 | 1.372 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_08 | 1000 | OFF | 37 | 6.01 | 8.47 | 13.95 | 0.227 | 0.228 | 0.2 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_08 | 1000 | ON | 37 | 3.96 | 8.33 | 9.92 | 0.163 | 0.164 | 0.139 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_09 | 100 | OFF | 364 | 6.11 | 14.06 | 39.05 | 2.524 | 2.529 | 2.239 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_09 | 100 | ON | 364 | 3.78 | 6.62 | 14.15 | 1.458 | 1.461 | 1.297 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_09 | 1000 | OFF | 38 | 5.97 | 12.53 | 12.89 | 0.27 | 0.271 | 0.244 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_09 | 1000 | ON | 38 | 4.96 | 6.88 | 8.44 | 0.181 | 0.183 | 0.152 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_10 | 100 | OFF | 166 | 3.74 | 8.1 | 18.48 | 0.691 | 0.693 | 0.603 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_10 | 100 | ON | 166 | 2.39 | 4.79 | 9.31 | 0.425 | 0.428 | 0.347 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_10 | 1000 | OFF | 18 | 3.69 | 4.66 | 4.8 | 0.066 | 0.066 | 0.061 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_10 | 1000 | ON | 18 | 2.04 | 2.88 | 3.13 | 0.039 | 0.039 | 0.035 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_11 | 100 | OFF | 86 | 2.06 | 3.52 | 13.47 | 0.198 | 0.199 | 0.177 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_11 | 100 | ON | 86 | 2.0 | 3.95 | 4.93 | 0.187 | 0.188 | 0.158 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_11 | 1000 | OFF | 10 | 2.86 | 3.28 | 3.87 | 0.029 | 0.029 | 0.026 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_11 | 1000 | ON | 10 | 2.51 | 3.36 | 3.59 | 0.027 | 0.028 | 0.025 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_12 | 100 | OFF | 86 | 2.41 | 3.2 | 11.01 | 0.214 | 0.215 | 0.189 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_12 | 100 | ON | 86 | 1.96 | 3.63 | 10.85 | 0.186 | 0.188 | 0.15 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_12 | 1000 | OFF | 10 | 2.37 | 3.01 | 3.86 | 0.026 | 0.027 | 0.023 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_12 | 1000 | ON | 10 | 2.18 | 2.65 | 2.97 | 0.022 | 0.023 | 0.02 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_13 | 100 | OFF | 51 | 1.79 | 2.28 | 2.46 | 0.092 | 0.092 | 0.078 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_13 | 100 | ON | 51 | 1.37 | 3.45 | 3.98 | 0.086 | 0.086 | 0.072 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_13 | 1000 | OFF | 6 | 2.13 | 2.51 | 2.64 | 0.013 | 0.013 | 0.011 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_13 | 1000 | ON | 6 | 1.8 | 1.88 | 2.43 | 0.011 | 0.011 | 0.009 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_14 | 100 | OFF | 272 | 6.7 | 12.02 | 19.18 | 1.722 | 1.727 | 1.485 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_14 | 100 | ON | 272 | 2.88 | 5.24 | 22.28 | 0.878 | 0.881 | 0.729 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_14 | 1000 | OFF | 29 | 5.88 | 11.91 | 14.69 | 0.185 | 0.186 | 0.167 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
| neg_14 | 1000 | ON | 29 | 3.99 | 5.58 | 7.5 | 0.12 | 0.122 | 0.099 | {'whisper.transcribe': 0.0, 'parakeet.transcribe': 0.0} | None |
