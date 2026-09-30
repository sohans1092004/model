"""Danger-intent scorers.

IntentScorer.score(target_text, window) -> IntentScore(p_danger, uses_context, scorer_id).

  SentenceIntentScorer   production: wraps intent_gate.IntentGate.p_distress (the live mDeBERTa v1,
                         HF rev 6131acc0). Sentence only: it ignores the window (uses_context=False),
                         exactly as the live veto does.
  (context-aware)        NO approved model exists. mDeBERTa v2 with context was rejected (Phase 0 §11:
                         it silenced cries after attacker speech). Any future one plugs in here; C-1.
  FixtureIntentScorer    TEST FIXTURE ONLY: a small deterministic lexicon so the decision logic can be
                         tested without models. Not a model; never a source of performance claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from asr_bench.textnorm import normalise


@dataclass(frozen=True)
class IntentScore:
    p_danger: float
    uses_context: bool
    scorer_id: str


class IntentScorer(Protocol):
    scorer_id: str
    uses_context: bool

    def score(self, target_text: str, window=None) -> IntentScore: ...


class SentenceIntentScorer:
    """The live sentence-level model (anything with .p_distress(text), e.g. intent_gate.IntentGate)."""
    uses_context = False

    def __init__(self, gate, scorer_id: str = "mdeberta-v1-sentence (HF sohans1092004/udk-intent-mdeberta@6131acc0)"):
        self._gate, self.scorer_id = gate, scorer_id

    def score(self, target_text: str, window=None) -> IntentScore:
        return IntentScore(float(self._gate.p_distress(target_text)), False, self.scorer_id)


def _has(words: list[str], phrase: str) -> bool:
    p = phrase.split()
    return any(words[i:i + len(p)] == p for i in range(len(words) - len(p) + 1))


class FixtureIntentScorer:
    """TEST FIXTURE ONLY. Target: strong danger cues -> 0.95, ambiguous safety words -> 0.6, harmless
    frames (story/film/game/news/household, explicit 'don't need help') -> 0.01 or lower, else 0.1.
    Context (if uses_context): threatening/pleading turns by ANOTHER speaker raise p to 0.97;
    narration/game/household framing by the SAME speaker lowers it to 0.01."""
    STRONG = ("hurt", "attack", "knife", "kill", "trying to hurt", "nobody is coming", "keep walking", "kapaadandi", "bachao")
    AMBIGUOUS = ("help", "police", "touch me", "let go", "get away", "stay away", "following", "not okay", "umbrella",
                 "vadalatledu")
    FRAMES = ("movie", "film", "game", "story", "news", "episode", "she shouted", "he shouted", "carry", "boxes", "bag",
              "uthane", "homework", "joking", "kitchen", "heavy")
    NEGATED_NEED = ("dont need help", "nahi chahiye", "i am fine", "im fine")
    THREAT_CONTEXT = ("nobody can hear", "nobody is coming", "dont move", "coming with me", "chup chaap", "mere saath",
                      "not leaving", "ekkadiki", "jaane nahi", "give me")
    PLEA_CONTEXT = ("please let me go", "let me go", "leave me")

    def __init__(self, uses_context: bool):
        self.uses_context = uses_context
        self.scorer_id = f"fixture-lexicon-{'context' if uses_context else 'sentence'} (TEST ONLY)"

    def score(self, target_text: str, window=None) -> IntentScore:
        w = normalise(target_text)[0]
        if any(_has(w, c) for c in self.NEGATED_NEED):
            p = 0.005
        elif any(_has(w, c) for c in self.FRAMES):
            p = 0.01
        elif any(_has(w, c) for c in self.STRONG):
            p = 0.95
        elif any(_has(w, c) for c in self.AMBIGUOUS):
            p = 0.6
        else:
            p = 0.1
        if self.uses_context and window is not None:
            for ct in window.turns:
                cw = normalise(ct.turn.text)[0]
                if ct.relation == "other_speaker" and any(_has(cw, c) for c in self.THREAT_CONTEXT + self.PLEA_CONTEXT):
                    p = max(p, 0.97)
                if ct.relation == "same_speaker" and any(_has(cw, c) for c in self.FRAMES) and p < 0.97:
                    p = min(p, 0.01)
        return IntentScore(p, self.uses_context, self.scorer_id)
