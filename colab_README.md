# UDK detection: whole pipeline on a Colab GPU

This runs the UDK detection pipeline with **every model on the GPU**:

| Model | Role |
| --- | --- |
| Whisper `small.en` | speech-to-text |
| wav2vec2 | keyword spotting (KWS) encoder |
| BEATs | scream/distress detector |
| MiniLM | semantic matching |

It uses per-sentence matching, on two test sets:

1. **`prepped_data/`**: 17 held-out test clips, **test only** (nothing is trained or tuned on them).
2. **`real_recordings/`**: 30 mixed clips, 7 real distress media clips, 23 real ordinary recordings.

The one part that stays on CPU is KWS's DTW matching (numpy). It was
rewritten this version to process a whole anti-diagonal at a time, giving
identical results about 4x faster than the old loop.

## What's in the zip

| Path | What it is |
| --- | --- |
| `evaluate_prepped_data.py` | Test on `prepped_data/`: transcripts, TRIGGER_ALL / TRIGGER_VERIFY / nothing per clip, confidence, recall / FPR / accuracy / precision, **time per component** |
| `evaluate_full_system.py` | Test on `real_recordings/` (the synthetic part is skipped: it needs Windows TTS) |
| `udk_engine.py`, `udks.py`, `stt.py`, `kws.py`, `semantic.py`, `vad.py`, `beats_distress_detector.py`, ... | The detection pipeline |
| `kws_references.npz` | Enrolled KWS reference embeddings for the 20 UDKs |
| `beats_vendor/` | Microsoft BEATs model code (weights download automatically) |
| `prepped_data/`, `real_recordings/` | The test audio |

Model weights (Whisper, wav2vec2, MiniLM, BEATs) download from HuggingFace on
first run, about 1.5 GB, with no token needed. WeSep isn't included: it
changed nothing on `prepped_data`, and it needs extra model sources.

## Steps

1. **Runtime > Change runtime type > T4 GPU** (or better), before running anything.

2. Upload `udk_colab_gpu.zip` to the Colab Files pane, then:
   ```
   !unzip -q -o udk_colab_gpu.zip -d /content/
   %cd /content/udk_colab_gpu
   ```
   (`-o` overwrites files left over from an earlier version of this zip.)

3. Install dependencies (about 1 minute):
   ```
   !pip install -q -r requirements_colab.txt
   ```

4. Confirm the GPU is visible. **Stop if this prints `False`**: go back to step 1.
   ```python
   import torch
   print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
   ```

5. **Test 1: `prepped_data`, whole pipeline on GPU** (a few minutes; the first run includes downloads).
   Set the options in their own cell first:
   ```
   %env PREPPED_STT_MODEL=small.en
   %env PREPPED_DEVICE=cuda
   ```
   Then run:
   ```
   !python evaluate_prepped_data.py 2>&1 | grep -v Warning | tee prepped_gpu_all.log
   ```
   **Check the first line of output reads `Device for all models: cuda   STT: faster-whisper small.en`.**
   If it says `cpu` or `tiny.en`, the `%env` cell didn't run.

   The end of the output shows the **ALERT-LEVEL RESULT** (TRIGGER_ALL /
   TRIGGER_VERIFY / nothing per clip, recall, FPR, accuracy, precision), then
   **Timing per clip**, one line per component:
   ```
   Whisper STT / KWS total (wav2vec2 + DTW) / KWS wav2vec2 / BEATs / Semantic MiniLM / rest / WHOLE PIPELINE
   ```
   "KWS wav2vec2" is the GPU part of "KWS total"; the difference is the CPU DTW.

6. **Test 2: real recordings, whole pipeline on GPU** (about 10-20 minutes):
   ```
   %env UDK_EVAL_STT_MODEL=small.en
   %env UDK_EVAL_DEVICE=cuda
   ```
   ```
   !python evaluate_full_system.py 2>&1 | grep -v Warning | tee real_gpu_all.log
   ```
   **Check the output starts with `Device for all models: cuda   STT: faster-whisper small.en`
   and `(synthetic corpus skipped: no PowerShell here ...)`.** The synthetic
   corpus needs Windows TTS, so it's skipped automatically on Colab. Without
   `UDK_EVAL_STT_MODEL`, the default is `tiny.en`, which matches the older local baselines.
   The end of the output has the **CONSOLIDATED REPORT**: correct, false
   positives and false negatives per corpus, plus latency.

7. *(Optional)* **Same test, everything on Colab's CPU**, for a like-for-like comparison on the same machine:
   ```
   %env PREPPED_DEVICE=cpu
   ```
   ```
   !python evaluate_prepped_data.py 2>&1 | grep -v Warning | tee prepped_cpu_all.log
   ```

8. Download `prepped_gpu_all.log` and `real_gpu_all.log` (and `prepped_cpu_all.log` if you ran step 7) from the Files pane and share them back.

## Numbers to compare against

| Run | Recall / FPR / accuracy / precision | Time per clip |
| --- | --- | --- |
| Local Windows CPU, `small.en`, all CPU | 9/9, 2/8, 15/17, 9/11 | 12.7 s total: Whisper 7.8, KWS 3.6 (wav2vec2 1.5 + DTW 2.1), BEATs 1.1, semantic 0.2 |
| Previous Colab run, **only Whisper on GPU** | 9/9, 2/8, 15/17, 9/11 | 6.0 s total: Whisper 0.34 s, the other ~5.7 s on CPU |
| Colab, **everything on GPU** (test 1, done) | 9/9, 2/8, 15/17, 9/11 | 1.66 s total: Whisper 0.28, KWS 1.19 (wav2vec2 0.07 + DTW 1.12 on CPU), BEATs 0.09, semantic 0.09 |

**Detection results should match** (same models, same code). GPU float16 and
CPU int8 Whisper can give slightly different transcripts. In the previous
Colab run that moved one clip from TRIGGER_ALL to TRIGGER_VERIFY without
changing any metric.

## Troubleshooting

- **`Could not load library libcudnn_ops.so.9`** (or another cuDNN error) from
  faster-whisper: Colab's cuDNN doesn't match CTranslate2's. Run this, then
  restart the runtime and repeat from step 2:
  ```
  !pip install -q nvidia-cudnn-cu12==9.*
  import os, nvidia.cudnn
  os.environ["LD_LIBRARY_PATH"] = os.path.dirname(nvidia.cudnn.__file__) + "/lib:" + os.environ.get("LD_LIBRARY_PATH", "")
  ```
  Or fall back to `pip install -q "ctranslate2==4.4.0"`, which uses cuDNN 8.
- **`No module named pkg_resources`** from webrtcvad: `!pip install -q "setuptools<81"`.
- **Out of GPU memory**: all four models together need about 3 GB, which fits a T4 (16 GB). Restart the runtime if earlier cells left models loaded.
- **`mpg123` / "Illegal Audio-MPEG-Header" messages**: harmless. 3 files are AAC audio named `.mp3`; librosa falls back to another decoder and reads them fine.
- A **FALSE ALARM on "Casual chat" and "Mock-annoyed"** is expected: they are byte-identical files, and "Don't touch my stuff" matches UDK_06 via fuzzy matching.
