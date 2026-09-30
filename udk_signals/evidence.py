"""Evidence with explicit availability states, shared by every Phase 4 signal.

  POSITIVE     the signal asserts the property (e.g. overlap present, distress sound, IS the target)
  NEGATIVE     the signal asserts its absence -- only sources that can reliably assert absence may
               emit it (e.g. BEATs cannot: it misses 28/57 real distress sounds, Phase 0 §9)
  UNCERTAIN    a measurement exists but does not decide (between thresholds, overlapped audio, degraded)
  UNAVAILABLE  no measurement: no model, no enrollment, audio never analysed, too short...
Downstream rule: UNCERTAIN and UNAVAILABLE carry no information about safety.
"""
from __future__ import annotations

from dataclasses import dataclass, field

POSITIVE, NEGATIVE, UNCERTAIN, UNAVAILABLE = "positive", "negative", "uncertain", "unavailable"
STATES = (POSITIVE, NEGATIVE, UNCERTAIN, UNAVAILABLE)
KINDS = ("target_speaker", "speaker_attribution", "overlap", "acoustic_distress", "condition")


@dataclass(frozen=True)
class Evidence:
    kind: str
    state: str
    source: str  # model / detector id; "annotation" for labels used only in evaluation
    reason: str
    score: float | None = None
    start_s: float | None = None
    end_s: float | None = None
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if self.state not in STATES:
            raise ValueError(f"state must be one of {STATES}")
        if self.state in (POSITIVE, NEGATIVE, UNCERTAIN) and not self.source:
            raise ValueError("a measured state needs its source")

    @property
    def informative(self) -> bool:
        return self.state in (POSITIVE, NEGATIVE)


def unavailable(kind: str, source: str, reason: str, **detail) -> Evidence:
    return Evidence(kind, UNAVAILABLE, source, reason, detail=detail)
