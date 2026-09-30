# Shadow-mode interference, OFF vs ON (proxy models, synthetic workload)

Random-weight models with the production architectures; stubbed STT/VAD/BEATs. Measures interference only, not detection quality. Medians across repeats.

| metric | off (cuda, STT 0.0s, n=3) | on (cuda, STT 0.0s, n=3) | on_lite (cuda, STT 0.0s, n=3) | off (cuda, STT 0.5s, n=3) | on (cuda, STT 0.5s, n=3) | on_lite (cuda, STT 0.5s, n=3) |
|---|---|---|---|---|---|---|
| live loop latency p50 (ms) | 30.4 | 61.8 | 31.8 | 532.2 | 532.1 | 532.0 |
| live loop latency p95 (ms) | 75.2 | 158.7 | 76.8 | 575.0 | 575.7 | 576.7 |
| live loop latency max (ms) | 347.2 | 369.0 | 317.8 | 826.8 | 820.2 | 830.5 |
| call start -> alert emitted p50 (ms) | 30.7 | 64.3 | 32.1 | 532.5 | 532.4 | 532.3 |
| call start -> alert emitted p95 (ms) | 77.6 | 164.6 | 79.2 | 577.9 | 579.7 | 580.3 |
| live semantic similarity per call (ms) | 0.2 | 0.5 | 0.2 | 0.2 | 0.2 | 0.2 |
| live intent p_distress per call (ms) | 24.6 | 48.9 | 24.7 | 26.0 | 24.3 | 26.2 |
| CPU cores used (cpu_s / wall_s) | 1.0 | 1.7 | 1.0 | 0.1 | 0.1 | 0.1 |
| peak RSS (MB) | 2158.0 | 2158.7 | 2158.2 | 2159.0 | 2158.6 | 2158.4 |
| shadow processing per record p50 (ms) | – | 60.9 | 0.9 | – | 30.8 | 1.0 |
| shadow processing p95 (ms) | – | 158.0 | 2.9 | – | 74.0 | 2.9 |
| shadow queue wait p50 (ms) | – | 369.9 | 0.4 | – | 0.2 | 0.2 |
| shadow queue wait p95 (ms) | – | 555.6 | 3.2 | – | 0.2 | 0.2 |
| shadow queue wait max (ms) | – | 639.4 | 3.9 | – | 0.3 | 0.3 |
| drain after last live segment (s) | – | 0.3 | 0.0 | – | 0.0 | 0.0 |
| shadow intent calls | 0 | 192 | 0 | 0 | 192 | 0 |
| dropped observations | – | 0 | 0 | – | 0 | 0 |
| records Phase5 == live | – | 180 | 144 | – | 180 | 144 |
| live events emitted | 192 | 192 | 192 | 192 | 192 | 192 |
| GPU utilisation mean (%) | 34.6 | 35.3 | 35.2 | 3.3 | 6.7 | 3.3 |
| GPU utilisation p95 (%) | 43.0 | 42.0 | 43.0 | 9.0 | 18.0 | 9.0 |
| GPU memory used max (MB, whole device) | 1709.0 | 1719.0 | 1709.0 | 1709.0 | 1717.0 | 1709.0 |
| torch peak allocated (MB) | 1530.4 | 1548.2 | 1530.4 | 1530.4 | 1539.1 | 1530.4 |

cpu_count=4 torch_threads=2 cuda_available=True gpu=Tesla T4 torch=2.10.0+cu128
