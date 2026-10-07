"""Memory settings (stt.ort_session_defaults, api._text_models_device): ONNX Runtime CUDA sessions get the
grow-by-request pool, CPU sessions are untouched, and the text-model device setting. No models.
    python test_memory_options.py
"""
import os

import onnxruntime as ort

import stt

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name} {detail}")


seen = []
real = ort.InferenceSession
ort.InferenceSession = lambda path, sess_options=None, providers=None, provider_options=None, **k: seen.append(
    (sess_options, providers, provider_options))
try:
    os.environ.pop("UDK_CPU_THREADS", None)
    os.environ.pop("UDK_DEVICE", None)
    with stt.ort_session_defaults():
        ort.InferenceSession("m.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])  # IndicConformer
        ort.InferenceSession("m.onnx", None, ["CUDAExecutionProvider", "CPUExecutionProvider"],
                             [{"device_id": 1}, {}])  # parallel-lists form
        ort.InferenceSession("m.onnx", providers=[("CUDAExecutionProvider", {"arena_extend_strategy": "kNextPowerOfTwo"})])
        ort.InferenceSession("m.onnx", providers=["CPUExecutionProvider"])
    check("CUDA provider gets the grow-by-request pool",
          seen[0][1] == [("CUDAExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"}), "CPUExecutionProvider"]
          and seen[0][2] is None, str(seen[0]))
    check("parallel-lists form keeps its own CUDA options and adds the pool setting",
          seen[1][2] == [{"arena_extend_strategy": "kSameAsRequested", "device_id": 1}, {}], str(seen[1]))
    check("an option the caller set wins", seen[2][1][0][1]["arena_extend_strategy"] == "kNextPowerOfTwo", str(seen[2]))
    check("CPU-only session unchanged, no thread budget without one set",
          seen[3] == (None, ["CPUExecutionProvider"], None), str(seen[3]))
    os.environ["UDK_CPU_THREADS"] = "2"
    with stt.ort_session_defaults():
        ort.InferenceSession("m.onnx", providers=["CPUExecutionProvider"])
    check("thread budget still applied", seen[4][0].intra_op_num_threads == 2, str(seen[4]))
finally:
    ort.InferenceSession = real
    os.environ.pop("UDK_CPU_THREADS", None)
check("ONNX Runtime restored after the block", ort.InferenceSession is real)

os.environ.update(UDK_ENABLE_STT="0", UDK_ENABLE_SEMANTIC="0", UDK_ENABLE_SCREAM_DETECTION="0", UDK_ENABLE_PARAKEET="0",
                  UDK_DEVICE="cuda", UDK_TEXT_MODELS_DEVICE="cpu")
import api  # noqa: E402

check("text models device setting", api._text_models_device() == "cpu")
os.environ.pop("UDK_TEXT_MODELS_DEVICE")
check("unset = where the rest runs", api._text_models_device() == api._device())
check("PyTorch expandable segments set by default", os.environ.get("PYTORCH_CUDA_ALLOC_CONF") == "expandable_segments:True")

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))
if failed:
    raise SystemExit(1)
