"""Negation features for the target utterance (evidence only; never a decision on its own).

Several UDK phrases themselves contain negators ("Don't touch me", "I'm not safe", "Please don't
hurt me"), so a negator INSIDE the matched phrase is not negation of the danger. Counted here:
  extra_negators     negators in the utterance beyond those in the UDK phrase
  negator_scopes_udk an extra negator within `scope_tokens` words before the first UDK word
Negator lists come from the benchmark config (Q7: provisional, Latin-script only today).
The decision layer never suppresses an alert because of these features: "I'm not okay, help me"
must stay an alert (negation-but-danger, Phase 1 §15).
"""
from __future__ import annotations

from asr_bench.textnorm import normalise


def negation_features(target_text: str, udk_phrase: str | None, negators: set[str], scope_tokens: int) -> dict:
    words = normalise(target_text)[0]
    phrase = normalise(udk_phrase or "")[0]
    in_phrase = sum(1 for w in phrase if w in negators)
    total = sum(1 for w in words if w in negators)
    extra = max(0, total - in_phrase)
    first = next((i for i, w in enumerate(words) if w in set(phrase) and w not in negators), None)
    scopes = False
    if extra and first is not None:
        window = words[max(0, first - scope_tokens):first]
        scopes = any(w in negators for w in window) and not all(w in phrase for w in window if w in negators)
    return {"negators_total": total, "negators_in_udk_phrase": in_phrase, "extra_negators": extra,
            "negator_scopes_udk": scopes}
