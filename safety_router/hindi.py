"""Hindi distress system as one class: speech segment in, ALERT / VERIFY / none out.

Same pipeline that was evaluated (docs/hindi_distress_system.md):
  IndicConformer 600M RNNT  ->  [A] LaBSE max cosine to the 20 Hindi phrases (udks.general_udks("hi"))
  ->  [B] MuRIL frame classifier on "CURRENT [SEP] last 30 s of this stream's transcript"  ->  decide()

One HindiSystem (models, ~3 GB) is shared; keep one HindiStream per audio session for the 30 s context.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# [B] weights: private HF repo, pinned commit (tag v2-2026-10-05), checked by SHA-256 after download.
# Rollback: tag v1-2026-10-03 (sha256 1d0ff14c4f29e8b404b24c1bb224046e71bebf1b0a750b45ed227502bba94ba0) + the old rule.
HUB_REPO = "sohans1092004/hindi-distress-frame"
HUB_REVISION = "be81da55f40d6ea3fc1dca859ac85ed218eca32d"  # commit of tag v2-2026-10-05 (v1: 5c8d90ad24a5f364...)
WEIGHTS_SHA256 = "4359c62b7bc1cb29cf2f42262a6b83f2260bcc8afc599d91efb1371ab0d27478"
MURIL = "google/muril-base-cased"
LABSE = "sentence-transformers/LaBSE"
MAX_LEN, CTX_CHARS, CONTEXT_MS = 256, 600, 30_000
# frame head size must match the trained weights (train_frames.FRAMES)
FRAMES = ["LIVE_DIRECT", "LIVE_MIXED", "CONTEXT_THREAT", "LIVE_BYSTANDER", "LIVE_UNRELATED_CLAUSE", "NEGATED", "QUESTION",
          "PAST_REPORT", "FUTURE_PLAN", "REPORTED_QUOTE", "STORY_MEDIA", "INSTRUCTION_ADVICE", "IDIOM_EXAGGERATION",
          "LITERAL_ORDINARY", "PLAY_JOKE", "HEATED_BUT_SAFE"]
_ENG = set("आई यू द दैट इज इट बट ऑल एंड वेरी लाइक बिकॉज ऑफ इफ वॉट दिस सो एवरी विल हैव नॉट वन पीपल थिंग".split())
_PUNCT = re.compile(r"[।?!,\"'.;:—…-]+")


def english_ratio(text: str) -> float:
    w = text.split()
    return sum(x in _ENG for x in w) / max(1, len(w))


ASK_MIN_B = 0.02     # no VERIFY when [B] is near-certain benign: cut TV / phone-talk asks ~30/h -> ~1/h (2026-10-05)
BYSTANDER_B = 0.8    # companion cries ("कोई रोको वरना मारपीट हो जाएगी") score 0.84 with the TV/phone-retrained [B]


def decide(a: float, b: float, text: str) -> str:
    """Rule for frame_model_updated.pt (TV/phone-retrained [B], 2026-10-05): skip mostly-English text;
    [A] > 0.55 -> ALERT if [B] >= 0.7, VERIFY if [B] >= ASK_MIN_B; [A] > 0.45 and [B] >= BYSTANDER_B -> ALERT."""
    if english_ratio(text) >= 0.15:
        return "none"
    if a > 0.55:
        return "ALERT" if b >= 0.7 else ("VERIFY" if b >= ASK_MIN_B else "none")
    return "ALERT" if a > 0.45 and b >= BYSTANDER_B else "none"


@dataclass
class HindiResult:
    decision: str          # "ALERT" | "VERIFY" | "none"
    text: str              # IndicConformer transcript of this segment
    a: float               # [A] phrase similarity
    b: float               # [B] P(live danger)
    frame: str             # [B]'s named frame (why), e.g. PAST_REPORT
    udk_id: str | None     # closest of the 20 phrases


@dataclass
class HindiStream:
    """Per-session state: recent transcripts for [B]'s 30 s context."""
    history: list[tuple[int, str]] = field(default_factory=list)  # (start_ms, text)

    def context(self, start_ms: int) -> str:
        return " | ".join(t for s, t in self.history if s >= start_ms - CONTEXT_MS and t)

    def add(self, start_ms: int, text: str) -> None:
        self.history.append((start_ms, text))
        self.history = [(s, t) for s, t in self.history if s >= start_ms - CONTEXT_MS]


def sha256_of(path: str | Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_weights(revision: str = HUB_REVISION, sha256: str = WEIGHTS_SHA256) -> Path:
    """Download the pinned [B] weights (needs an HF token with access to the private repo) and verify them."""
    from huggingface_hub import hf_hub_download
    path = Path(hf_hub_download(HUB_REPO, "frame_model.pt", revision=revision))
    if sha256_of(path) != sha256:
        raise RuntimeError(f"[B] weights at {path} do not match sha256 {sha256}; refusing to load")
    return path


class HindiSystem:
    def __init__(self, weights: str | Path | None = None, device: str | None = None, stt=None):
        """weights: local path, or None to download the pinned version from the private HF repo."""
        import torch
        weights = weights or fetch_weights()
        from transformers import AutoModel, AutoTokenizer
        from udks import general_udks
        self.torch = torch
        self.dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if stt is None:
            try:  # onnxruntime-gpu >= 1.21 loads CUDA/cuDNN from torch's libs; the build must match the CUDA version
                import onnxruntime
                onnxruntime.preload_dlls()
            except Exception:
                pass
            from safety_router.indic_stt import IndicConformerSTT
            stt = IndicConformerSTT()
        self.stt = stt
        self.l_tok = AutoTokenizer.from_pretrained(LABSE)
        self.l_model = AutoModel.from_pretrained(LABSE).to(self.dev).eval()
        self.udks = general_udks("hi")
        self.U = np.stack([self._labse(u.phrase) for u in self.udks])
        self.m_tok = AutoTokenizer.from_pretrained(MURIL)
        self.frame_model = _FrameModel(torch).to(self.dev)
        self.frame_model.load_state_dict(torch.load(weights, map_location=self.dev))
        self.frame_model.eval()

    def _labse(self, text: str) -> np.ndarray:
        torch = self.torch
        x = self.l_tok(text, padding=True, truncation=True, max_length=64, return_tensors="pt").to(self.dev)
        with torch.no_grad():
            h = self.l_model(**x)[0]
        m = x["attention_mask"].unsqueeze(-1).float()
        e = (h * m).sum(1) / m.sum(1).clamp(min=1e-9)
        return torch.nn.functional.normalize(e, p=2, dim=1)[0].cpu().numpy()

    def score_text(self, text: str, context: str = "") -> HindiResult:
        """[A] + [B] + rule on an already-transcribed segment (used by process(); also handy for tests)."""
        torch = self.torch
        if not text.strip():
            return HindiResult("none", text, 0.0, 0.0, "", None)
        sims = self.U @ self._labse(text)
        a = float(sims.max())
        cur, ctx = _PUNCT.sub(" ", text), _PUNCT.sub(" ", context)
        enc = self.m_tok([cur], [ctx[-CTX_CHARS:] or "-"], truncation="only_second", max_length=MAX_LEN,
                         padding=True, return_tensors="pt").to(self.dev)
        with torch.no_grad(), torch.autocast(self.dev.split(":")[0], enabled=self.dev.startswith("cuda")):
            dl, fl = self.frame_model(**enc)
        b = float(torch.sigmoid(dl.float())[0])
        return HindiResult(decide(a, b, text), text, round(a, 3), round(b, 3), FRAMES[int(fl.argmax(-1)[0])],
                           self.udks[int(sims.argmax())].udk_id)

    def process(self, pcm: bytes, start_ms: int, stream: HindiStream) -> HindiResult:
        """One VAD segment (16 kHz mono int16 PCM) of a session."""
        text = self.stt.transcribe(pcm, language="hi").text.strip()
        r = self.score_text(text, stream.context(start_ms))
        stream.add(start_ms, text)
        if r.decision == "none":
            # Word-for-word phrase check ([A] is a whole-segment meaning similarity: a phrase said inside a longer
            # sentence stays under its gate). Exact match covering >= half the phrase's words -> at least an ask.
            # Measured: 0 asks on 29 h of benign Hindi (TV, phone, crime, street vlog, podcast); real acted scenes
            # +1 ("कोई मेरा पीछा कर रहा है" inside a phone call). Fuzzy matching was 0.7-1.4 asks/h there: not used.
            from safety_router.indic_exact import exact_phrase
            udk = exact_phrase(text, self.udks)
            if udk is not None:
                return HindiResult("VERIFY", r.text, r.a, r.b, "PHRASE_EXACT", udk.udk_id)
        return r


def _FrameModel(torch):
    from transformers import AutoModel

    class FrameModel(torch.nn.Module):  # same layout as train_frames.FrameModel (weights load into it)
        def __init__(self):
            super().__init__()
            self.enc = AutoModel.from_pretrained(MURIL)
            h = self.enc.config.hidden_size
            self.drop = torch.nn.Dropout(0.1)
            self.danger = torch.nn.Linear(h, 1)
            self.frame = torch.nn.Linear(h, len(FRAMES))

        def forward(self, **enc):
            cls = self.drop(self.enc(**enc).last_hidden_state[:, 0])
            return self.danger(cls).squeeze(-1), self.frame(cls)
    return FrameModel()
