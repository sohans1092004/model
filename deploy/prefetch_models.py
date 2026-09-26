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
print("all models cached")
