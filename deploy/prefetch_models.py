"""Download every model the live service loads, at image build time, through the
same classes api.py uses (so the cache paths match). CPU is enough to download."""
from stt import FasterWhisperSTT, ParakeetSTT
from semantic import SentenceTransformerSemanticMatcher
from kws import Wav2Vec2DTWSpotter
from beats_distress_detector import BEATsDistressDetector
import os
from pathlib import Path

FasterWhisperSTT(model_size="small.en")
ParakeetSTT()
SentenceTransformerSemanticMatcher()
Wav2Vec2DTWSpotter().load_references("kws_references.npz")
BEATsDistressDetector()
# Fine-tuned intent model (intent_gate.py): not public, so it comes from the private HF repo
# named at build time (--build-arg UDK_INTENT_MODEL_REPO=..., token via --secret hf_token).
# Built without it, the image runs with the intent gate off.
repo = os.environ.get("UDK_INTENT_MODEL_REPO")
if repo:
    from huggingface_hub import snapshot_download
    from intent_gate import IntentGate

    target = Path(__file__).resolve().parent.parent / "models" / "intent_mdeberta"
    snapshot_download(repo, revision=os.environ.get("UDK_INTENT_MODEL_REVISION") or None, local_dir=target)
    IntentGate(str(target))  # proves it loads with this image's libraries
    print(f"intent model {repo} -> {target}")

# Host-dependent models (deploy/Dockerfile ARGs, set by remote_deploy.sh from the host's settings).
custom_stt = os.environ.get("UDK_PREFETCH_CUSTOM_STT", "")
if custom_stt and custom_stt != "small.en":  # small.en is the general model, cached above
    FasterWhisperSTT(model_size=custom_stt)
    print(f"prefetched custom-UDK gate Whisper {custom_stt}")
if os.environ.get("UDK_PREFETCH_MULTILINGUAL") == "1":
    from safety_router.hindi import HindiSystem
    from safety_router.indic_stt import IndicConformerSTT
    from safety_router.router import WhisperLanguageID

    WhisperLanguageID("cpu")              # language ID (Whisper small)
    IndicConformerSTT()                   # gated ai4bharat model + its remote code
    HindiSystem(device="cpu", stt=object())  # LaBSE, MuRIL, [B] weights at the pinned revision (SHA-checked)
    print("prefetched multilingual models (language ID, IndicConformer, LaBSE, MuRIL, [B] weights)")
print("all models cached")
