"""Intent veto for text alerts: a fine-tuned mDeBERTa (intent_data/finetune.py) reads the
alert's transcript and silences it when it is confidently NOT a distress request, e.g.
"I don't need any help", a quote, "don't touch my stuff" -- but ONLY when both STT
engines heard the same words (veto-agree, 2026-09-26). When Whisper and Parakeet
disagree the audio was unclear, the text may not be what was said, and the alert stays.


Opt-in: UDK_INTENT_GATE=<model dir> (a finetune.py output folder); threshold
UDK_INTENT_THRESHOLD, default 0.02 = calibrate_veto.py's pick: the highest threshold that
keeps >= 99.5% of the intent dataset's DEV distress sentences (99.7% on test). A veto must
only fire when the model is confident the words are NOT distress; 0.99 (finetune.py's
detection threshold at 95% recall) silenced real cries on prepped ("don't touch me" p=0.24).
Kaggle, 2026-09-26, at 0.02: prepped danger vetoes 5 -> 1 (an STT mishearing), harmless
alerts 59 -> 43 of 162 vs the fragment rule alone; real_recordings recall same as gate off.
Only GENERAL UDKs' text alerts (exact/fuzzy/semantic) are judged: custom code words are
not distress sentences, and KWS / scream alerts carry no text to judge.
"""
from __future__ import annotations

import os

from rapidfuzz import fuzz

HYPOTHESIS = "The speaker is in immediate danger or is asking for help."  # as trained (intent_data/nli_eval.py)
MAX_LEN = 160  # as trained (intent_data/finetune.py)
AGREE = 80  # token_set_ratio: the other STT heard about the same words
THRESHOLD = 0.02  # see module docstring / calibrate_veto.py
TEXT_LAYERS = ("exact", "fuzzy", "semantic")


def heard_by_both(alert_text: str, other_text: str) -> bool:
    return bool(other_text) and fuzz.token_set_ratio(alert_text.lower(), other_text.lower()) >= AGREE


class IntentGate:
    def __init__(self, model_dir: str, device: str = "cpu", threshold: float = THRESHOLD):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch, self.device, self.threshold = torch, device, threshold
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(device).eval()

    def p_distress(self, text: str) -> float:
        enc = self.tok([text], [HYPOTHESIS], truncation=True, max_length=MAX_LEN, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            return float(self.torch.softmax(self.model(**enc).logits.float(), -1)[0, 1])

    def veto(self, decision, other_text: str) -> float | None:
        """P(distress) if this alert should be silenced, else None."""
        if (decision.decision == "NO_ACTION" or decision.udk is None or decision.udk.udk_type != "GENERAL"
                or not decision.layer.split("/")[0].startswith(TEXT_LAYERS)
                or not heard_by_both(decision.transcript, other_text)):
            return None
        p = self.p_distress(decision.transcript)
        return p if p < self.threshold else None


def from_env(device: str = "cpu") -> IntentGate | None:
    path = os.environ.get("UDK_INTENT_GATE")
    if not path:
        return None
    gate = IntentGate(path, device=device, threshold=float(os.environ.get("UDK_INTENT_THRESHOLD", THRESHOLD)))
    print(f"intent gate ON: {path} (threshold {gate.threshold}, {device})", flush=True)
    return gate


if __name__ == "__main__":  # self-check of the no-model parts
    from types import SimpleNamespace as N

    assert heard_by_both("It's fine, I'm safe.", "it's fine, i'm safe, nothing wrong")
    assert not heard_by_both("You do me!", "You didn't mean.")
    assert not heard_by_both("Help me", "")
    g = IntentGate.__new__(IntentGate)
    g.threshold, g.p_distress = THRESHOLD, lambda t: 0.001
    gen, custom = N(udk_type="GENERAL"), N(udk_type="PERSONAL")
    ev = lambda layer, udk=gen, t="I don't need any help": N(decision="TRIGGER_ALL", udk=udk, layer=layer, transcript=t)
    assert g.veto(ev("semantic"), "I don't need any help.") == 0.001
    assert g.veto(ev("exact/sentence"), "I don't need any help.") == 0.001
    assert g.veto(ev("semantic"), "I don't need any hell") == 0.001  # ASR noise still "the same words"
    assert g.veto(ev("semantic"), "") is None  # other STT heard nothing: keep
    assert g.veto(ev("kws"), "I don't need any help") is None  # no text to judge
    assert g.veto(ev("exact", udk=custom), "I don't need any help") is None  # code words exempt
    g.p_distress = lambda t: 0.05  # unsure, not confidently harmless
    assert g.veto(ev("semantic"), "I don't need any help") is None  # model not confident it is harmless: keep
    print("intent_gate self-check passed")
