"""Download every model the live service loads, at image build time, through the
same classes api.py uses (so the cache paths match). CPU is enough to download."""
from stt import FasterWhisperSTT, ParakeetSTT
from semantic import SentenceTransformerSemanticMatcher
from kws import Wav2Vec2DTWSpotter
from beats_distress_detector import BEATsDistressDetector

FasterWhisperSTT(model_size="small.en")
ParakeetSTT()
SentenceTransformerSemanticMatcher()
Wav2Vec2DTWSpotter().load_references("kws_references.npz")
BEATsDistressDetector()
print("all models cached")
