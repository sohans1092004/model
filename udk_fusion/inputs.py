"""Typed fusion input.

LinguisticEvidence  the Phase 3 output for one target utterance, with its origin classified:
    standard_udk        GENERAL phrase via a text layer (exact / fuzzy / semantic)
    personal_udk        PERSONAL (custom) phrase -- never vetoed (Phase 3 H1)
    kws_udk             keyword-spotting match -- never vetoed (H1)
    danger_without_udk  classifier-only alert (Phase 3 source "context_intent") -- TRIGGER_VERIFY at most (H6)
    none                no linguistic alert and no veto
  A vetoed alert keeps its origin (standard_udk) with `vetoed` set ("sentence" / "context").
FusionInput         linguistic evidence + Phase 4 Evidence list + the utterance span.

from_phase3() validates the Phase 3 output against the Phase 3 hard rules and raises ContractError on
anything that could only come from a broken or bypassed upstream (a vetoed PERSONAL alert, a classifier
TRIGGER_ALL, a scream alert passed in as linguistic evidence, ...). Nothing is silently repaired.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from udk_signals.evidence import KINDS, Evidence

DECISIONS = ("NO_ALERT", "TRIGGER_VERIFY", "TRIGGER_ALL")
RANK = {"NO_ALERT": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2}
TEXT_LAYERS = ("exact", "fuzzy", "semantic")  # as udk_context.decision / intent_gate
ORIGINS = ("standard_udk", "personal_udk", "kws_udk", "danger_without_udk", "none")
PHASE3_SOURCES = ("udk_path", "udk_path+context_escalation", "context_intent", "vetoed:sentence", "vetoed:context")


class ContractError(ValueError):
    pass


def from_production(decision: str) -> str:
    """Production / Phase 3 vocabulary (NO_ACTION) -> Phase 5 (NO_ALERT)."""
    if decision not in ("NO_ACTION", "TRIGGER_VERIFY", "TRIGGER_ALL"):
        raise ContractError(f"unknown decision {decision!r}")
    return "NO_ALERT" if decision == "NO_ACTION" else decision


def to_production(decision: str) -> str:
    return "NO_ACTION" if decision == "NO_ALERT" else decision


@dataclass(frozen=True)
class LinguisticEvidence:
    origin: str
    udk_decision: str  # production UDK path, Phase 5 vocabulary
    phase3_decision: str  # after Phase 3 (vetoes / escalation / danger-without-UDK), Phase 5 vocabulary
    phase3_source: str
    vetoed: str | None  # "sentence" | "context" | None
    udk_id: str | None
    layer: str
    heard_by_both: bool | None
    negation: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    phase3_reasons: tuple = ()

    @property
    def udk_path(self) -> bool:
        return self.origin in ("standard_udk", "personal_udk", "kws_udk")


def _origin(udk_type, layer: str) -> str:
    base = layer.split("/")[0]
    if base == "kws":
        return "kws_udk"
    if udk_type == "PERSONAL":
        return "personal_udk"
    if udk_type == "GENERAL" and base.startswith(TEXT_LAYERS):
        return "standard_udk"
    raise ContractError(f"cannot classify UDK alert (udk_type={udk_type!r}, layer={layer!r})")


def from_phase3(udk_ev, final) -> LinguisticEvidence:
    """udk_context.decision.UdkEvidence + FinalDecision -> LinguisticEvidence (validated)."""
    if udk_ev.layer.split("/")[0] == "acoustic_scream":
        raise ContractError("a live scream alert is acoustic evidence: pass it as a Phase 4 acoustic_distress "
                            "Evidence, not as linguistic evidence (double counting)")
    if final.source not in PHASE3_SOURCES:
        raise ContractError(f"unknown Phase 3 source {final.source!r}")
    udk_dec, p3 = from_production(udk_ev.decision), from_production(final.decision)
    if from_production(final.udk_decision) != udk_dec:
        raise ContractError("Phase 3 udk_decision does not match the UdkEvidence it was given")
    vetoed = final.source.split(":")[1] if final.source.startswith("vetoed:") else None
    if udk_dec == "NO_ALERT":
        if final.source == "context_intent":
            if p3 != "TRIGGER_VERIFY":
                raise ContractError("classifier-only (context_intent) alert above TRIGGER_VERIFY violates Phase 3 H6")
            origin = "danger_without_udk"
        elif final.source == "udk_path" and p3 == "NO_ALERT":
            origin = "none"
        else:
            raise ContractError(f"Phase 3 source {final.source!r} / decision {p3} impossible without a UDK alert")
    else:
        origin = _origin(udk_ev.udk_type, udk_ev.layer)
        if vetoed:
            if origin != "standard_udk":
                raise ContractError(f"{origin} alert was vetoed: violates Phase 3 H1")
            if p3 != "NO_ALERT":
                raise ContractError("a vetoed alert must be NO_ACTION")
        elif final.source == "udk_path+context_escalation":
            if not (udk_dec == "TRIGGER_VERIFY" and p3 == "TRIGGER_ALL"):
                raise ContractError("context escalation must lift TRIGGER_VERIFY to TRIGGER_ALL")
        elif final.source == "udk_path":
            if p3 != udk_dec:
                raise ContractError("Phase 3 changed the UDK decision without a recorded rule")
        else:
            raise ContractError(f"Phase 3 source {final.source!r} impossible with a UDK alert")
    return LinguisticEvidence(origin, udk_dec, p3, final.source, vetoed, udk_ev.udk_id, udk_ev.layer, udk_ev.heard_by_both,
                              dict(final.negation), dict(final.scores), tuple(final.reasons))


@dataclass(frozen=True)
class FusionInput:
    linguistic: LinguisticEvidence
    signals: tuple[Evidence, ...] = ()
    start_s: float | None = None  # utterance span; evidence with a span entirely outside it is ignored
    end_s: float | None = None
    utterance_id: str | None = None

    def __post_init__(self):
        for e in self.signals:
            if not isinstance(e, Evidence) or e.kind not in KINDS:
                raise ContractError("signals must be udk_signals.evidence.Evidence")
