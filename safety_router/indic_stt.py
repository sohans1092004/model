"""IndicConformer 600M (AI4Bharat) as an STTBackend: transcribe(pcm16k_int16_bytes) -> Transcript.

Gated model: needs HF_TOKEN with access to ai4bharat/indic-conformer-600m-multilingual. Custom ONNX code via
trust_remote_code; on GPU it needs onnxruntime-gpu built for the server's CUDA (else it silently runs on CPU).
"""
from __future__ import annotations

from stt import Transcript

INDIC_CONFORMER_ID = "ai4bharat/indic-conformer-600m-multilingual"


def _audio(pcm: bytes):
    import numpy as np
    return np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0


def _split_quiet(audio, max_s: float, sr: int = 16000, frame: int = 480):
    """Cut audio longer than max_s at the lowest-energy 30 ms frame in the back half of each window.
    Measured: IndicConformer returns '' (RNNT) or garbage (CTC) on some inputs of ~9.5-11 s that it
    transcribes correctly when cut to <= 8 s; production VAD segments reach 11 s (8 s cap + rolls)."""
    import numpy as np
    out, lim = [], int(max_s * sr)
    while audio.size > lim:
        lo = lim // 2
        frames = audio[lo:lo + (lim - lo) // frame * frame].reshape(-1, frame)
        cut = lo + int(np.argmin((frames ** 2).mean(axis=1))) * frame
        out.append(audio[:cut])
        audio = audio[cut:]
    return out + [audio]


class IndicConformerSTT:
    MAX_S = 8.0

    def __init__(self, language: str = "hi", decoding: str = "rnnt"):
        import threading

        from stt import ort_cpu_threads
        from transformers import AutoModel
        with ort_cpu_threads():
            self._model = AutoModel.from_pretrained(INDIC_CONFORMER_ID, trust_remote_code=True)
        self._language, self._decoding = language, decoding
        self.model_version = f"indic-conformer-600m-multilingual-{decoding}"
        # Encode once, decode per language: the encoder (the heavy part) does not depend on the language, so the
        # Hindi and Telugu / Tamil / Kannada calls on the same segment reuse one encoding. Identical text. Falls
        # back to the model's own forward() if its remote code ever stops exposing encode() / the decoders.
        self._split = all(hasattr(self._model, a) for a in ("encode", "_rnnt_decode", "_ctc_decode"))
        self._cache = None  # (segment pcm, [(encoder outputs, lengths) per piece]) of the last segment
        self._lock = threading.Lock()

    def transcribe(self, pcm: bytes, language: str | None = None) -> Transcript:
        """`language` overrides the default one (te, ta, kn, ...): one loaded model serves every Indic language."""
        import torch
        lang = language or self._language
        pieces = [p for p in _split_quiet(_audio(pcm), self.MAX_S) if p.size >= 1600]  # <0.1 s: no encoder frames
        texts = []
        with torch.no_grad():
            if not self._split:
                texts = [str(self._model(torch.from_numpy(p).unsqueeze(0), lang, self._decoding)).strip() for p in pieces]
            else:
                with self._lock:
                    if self._cache is None or (self._cache[0] is not pcm and self._cache[0] != pcm):
                        self._cache = (pcm, [self._model.encode(torch.from_numpy(p).unsqueeze(0)) for p in pieces])
                    encoded = self._cache[1]
                for enc, lens in encoded:
                    out = (self._model._rnnt_decode(enc, lens, lang) if self._decoding == "rnnt"
                           else self._model._ctc_decode(enc, lens, lang))
                    texts.append(str(out).strip())
        return Transcript(text=" ".join(t for t in texts if t), model_version=self.model_version)
