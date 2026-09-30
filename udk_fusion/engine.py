"""Deterministic Phase 5 decision policy.

decide(FusionInput, FusionPolicy) -> FusedDecision. Rules run in this fixed order; each that fires is
recorded by id in `rules_fired`:

  R0 CONTRACT      input validated (inputs.from_phase3); every signal classified as used / ignored.
  R1 NORMALISE     evidence whose span lies outside the utterance is ignored; on degraded audio (condition
                   POSITIVE) any other NEGATIVE is reported UNCERTAIN (Phase 4 G5). UNCERTAIN / UNAVAILABLE
                   evidence is never read as NEGATIVE (listed in `ignored`, with its reason).
  R2 LINGUISTIC    start from the Phase 3 decision. Phase 3 H1-H6 (never-veto for PERSONAL / KWS, H2 heard-
                   by-both, H3 other-speaker context, H4 attribution / overlap, H5 negation, H6 classifier
                   VERIFY-only) are already applied upstream and are not re-decided here.
  R3 CONTEXT-VETO GUARD (hard)  a Phase 3 context veto stands only if Phase 4 evidence positively shows
                   what H4 assumed: every speaker_attribution item POSITIVE (>= 1) and every overlap item
                   NEGATIVE (>= 1). Otherwise the production UDK decision is reinstated: missing / uncertain
                   attribution and unknown overlap never suppress danger.
  R4 SENTENCE-VETO GUARD (policy)  if veto_guard.sentence_veto_requires_clean_overlap, a Phase 3 sentence
                   veto is reinstated unless overlap is a clean NEGATIVE. Off in the production-equivalent
                   policy (the live veto is unchanged).
  R5 CORROBORATION (S-4 boundary)  a UDK-path TRIGGER_VERIFY becomes TRIGGER_ALL when a configured
                   corroboration source is POSITIVE. Never a classifier-only alert (Phase 4 G3).
  R6 ACOUSTIC-ALONE (S-4 boundary) with no alert left, a configured acoustic_alone source POSITIVE raises
                   TRIGGER_VERIFY (never TRIGGER_ALL). Mirrors live order: the scream fires only when no
                   alert is left after the veto.
  R7 ANNOTATE      overlap POSITIVE / UNCERTAIN with no alert -> "a UDK may be masked" (G6); target_speaker
                   NEGATIVE never lowers anything ("any voice saying a UDK alerts"); conflicts recorded.
  R8 INVARIANTS    checked on every result (AssertionError = engine bug, never a silent downgrade):
                   I1 no TRIGGER_ALL without a UDK-path linguistic alert; I2 never below the Phase 3
                   decision except nothing (Phase 5 never lowers); I3 classifier-only <= TRIGGER_VERIFY;
                   I4 PERSONAL / KWS alerts are never NO_ALERT.

No DEFER / UNCERTAIN output tier: the live system and Phases 3-4 have none, and TRIGGER_VERIFY already is
the "ask the user" tier. Incomplete evidence is reported in `evidence_status` / `ignored` instead, so a
consumer can see it without a fourth tier silently absorbing alerts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from udk_fusion.inputs import RANK, FusionInput, to_production
from udk_fusion.policy import FusionPolicy
from udk_signals.evidence import NEGATIVE, POSITIVE, UNAVAILABLE, UNCERTAIN, Evidence


@dataclass
class FusedDecision:
    decision: str  # NO_ALERT | TRIGGER_VERIFY | TRIGGER_ALL
    basis: str  # none | linguistic | acoustic | fused
    rules_fired: list[str] = field(default_factory=list)
    contributing: list[dict] = field(default_factory=list)  # evidence that changed or determined the decision
    considered: list[dict] = field(default_factory=list)  # informative evidence with no effect (and why)
    ignored: list[dict] = field(default_factory=list)  # uncertain / unavailable / out of span / unconfigured
    annotations: list[str] = field(default_factory=list)
    evidence_status: str = "complete"  # complete | partial (something uncertain / unavailable)
    linguistic_origin: str = "none"
    phase3_decision: str = "NO_ALERT"
    phase3_source: str = "udk_path"
    policy_sha256: str = ""
    utterance_id: str | None = None

    @property
    def production_decision(self) -> str:
        return to_production(self.decision)

    def record(self) -> dict:
        """JSON-serialisable provenance record (for shadow logging / evaluation)."""
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["production_decision"] = self.production_decision
        return d


def _ev(e: Evidence, why: str) -> dict:
    return {"kind": e.kind, "state": e.state, "source": e.source, "score": e.score, "reason": e.reason, "why": why}


def _outside(e: Evidence, a, b) -> bool:
    return (a is not None and b is not None and e.start_s is not None and e.end_s is not None
            and (e.end_s <= a or e.start_s >= b))


def _clean(items: list[Evidence], state: str) -> bool:
    return bool(items) and all(e.state == state for e in items)


def decide(inp: FusionInput, policy: FusionPolicy) -> FusedDecision:
    lx = inp.linguistic
    out = FusedDecision(lx.phase3_decision, "linguistic" if lx.phase3_decision != "NO_ALERT" else "none",
                        linguistic_origin=lx.origin, phase3_decision=lx.phase3_decision, phase3_source=lx.phase3_source,
                        policy_sha256=policy.sha256, utterance_id=inp.utterance_id)
    out.rules_fired.append("R0")

    # R1 normalise
    live, degraded = [], False
    for e in inp.signals:
        if _outside(e, inp.start_s, inp.end_s):
            out.ignored.append(_ev(e, "span outside the utterance"))
        else:
            live.append(e)
    degraded = any(e.kind == "condition" and e.state == POSITIVE for e in live)
    ev = []
    for e in live:
        if degraded and e.state == NEGATIVE and e.kind != "condition":
            e = replace(e, state=UNCERTAIN, reason=e.reason + " [UNCERTAIN: degraded audio, G5]")
        ev.append(e)
        if e.state in (UNCERTAIN, UNAVAILABLE):
            out.ignored.append(_ev(e, f"{e.state}: carries no information about safety"))
    if degraded:
        out.rules_fired.append("R1:degraded")
        out.contributing += [_ev(e, "degraded audio: NEGATIVE evidence downgraded to UNCERTAIN") for e in ev
                             if e.kind == "condition" and e.state == POSITIVE]
    if any(e.state in (UNCERTAIN, UNAVAILABLE) for e in ev) or not ev:
        out.evidence_status = "partial"
    by = {k: [e for e in ev if e.kind == k] for k in ("overlap", "speaker_attribution", "target_speaker", "acoustic_distress")}

    # R2 linguistic
    out.rules_fired.append("R2")
    if lx.origin != "none":
        out.contributing.append({"kind": "linguistic", "origin": lx.origin, "udk_id": lx.udk_id, "layer": lx.layer,
                                 "phase3_source": lx.phase3_source, "phase3_decision": lx.phase3_decision,
                                 "why": "Phase 3 linguistic decision (H1-H6 applied upstream)"})
    if lx.negation.get("negator_scopes_udk"):
        out.annotations.append("negation scopes the UDK phrase: evidence only, never suppresses (H5)")

    # R3 context-veto guard (hard)
    if lx.vetoed == "context":
        ok = _clean(by["speaker_attribution"], POSITIVE) and _clean(by["overlap"], NEGATIVE)
        if ok:
            out.rules_fired.append("R3:veto_stands")
            out.contributing += [_ev(e, "supports the context veto's H4 precondition") for e in by["speaker_attribution"] + by["overlap"]]
        else:
            out.decision, out.basis = lx.udk_decision, "fused"
            out.rules_fired.append("R3:veto_reinstated")
            out.annotations.append("context veto reinstated: speaker attribution / overlap not positively established "
                                   "by Phase 4 evidence (missing or uncertain evidence never suppresses danger)")
    # R4 sentence-veto guard (policy)
    if lx.vetoed == "sentence" and policy.sec("veto_guard")["sentence_veto_requires_clean_overlap"]:
        if _clean(by["overlap"], NEGATIVE):
            out.rules_fired.append("R4:veto_stands")
        else:
            out.decision, out.basis = lx.udk_decision, "fused"
            out.rules_fired.append("R4:veto_reinstated")
            out.annotations.append("sentence veto reinstated: overlap not a clean NEGATIVE (policy veto_guard)")

    # acoustic evidence by configured role
    acoustic_pos = [e for e in by["acoustic_distress"] if e.state == POSITIVE]
    corr, alone = policy.sec("corroboration"), policy.sec("acoustic_alone")
    corr_hits = [e for e in acoustic_pos if corr["enabled"] and e.source in corr["sources"]]
    alone_hits = [e for e in acoustic_pos if alone["enabled"] and e.source in alone["sources"]]
    used = set()

    # R5 corroboration
    if out.decision == "TRIGGER_VERIFY" and corr_hits:
        if lx.udk_path:
            out.decision, out.basis = "TRIGGER_ALL", "fused"
            out.rules_fired.append("R5")
            out.contributing += [_ev(e, "acoustic corroboration of a UDK-path TRIGGER_VERIFY") for e in corr_hits]
            used |= {id(e) for e in corr_hits}
        else:
            out.rules_fired.append("R5:blocked_classifier_only")
            out.annotations.append("acoustic corroboration not applied: classifier-only alert (G3 / H6)")
    # R6 acoustic alone
    if out.decision == "NO_ALERT" and alone_hits:
        out.decision, out.basis = "TRIGGER_VERIFY", "acoustic"
        out.rules_fired.append("R6")
        out.contributing += [_ev(e, "acoustic evidence alone: TRIGGER_VERIFY at most") for e in alone_hits]
        used |= {id(e) for e in alone_hits}

    # R7 annotations / considered evidence
    for e in acoustic_pos:
        if id(e) in used:
            continue
        if e.source not in corr["sources"] + alone["sources"]:
            why = "source not named in the acoustic policy"
        elif out.decision == "TRIGGER_ALL":
            why = "decision already TRIGGER_ALL"
        elif e.source in corr["sources"] and not corr["enabled"]:
            why = "corroboration disabled by policy (S-4 boundary)"
        elif e.source in alone["sources"] and not alone["enabled"]:
            why = "acoustic-alone disabled by policy (S-4 boundary)"
        else:
            why = "role does not apply to this decision state"
        (out.ignored if why.startswith("source not") else out.considered).append(_ev(e, why))
    for e in ev:
        if e.state == NEGATIVE and e.kind in ("acoustic_distress", "target_speaker"):
            out.considered.append(_ev(e, "NEGATIVE never lowers a decision"))
    if any(e.state == POSITIVE for e in by["acoustic_distress"]) and any(e.state == NEGATIVE for e in by["acoustic_distress"]):
        out.annotations.append("conflicting acoustic evidence: POSITIVE kept, NEGATIVE does not cancel it")
    ov_states = {e.state for e in by["overlap"]}
    if POSITIVE in ov_states and NEGATIVE in ov_states:
        out.annotations.append("conflicting overlap evidence: treated as not clean")
    if out.decision == "NO_ALERT" and ov_states & {POSITIVE, UNCERTAIN}:
        out.rules_fired.append("R7:overlap_masking")
        out.annotations.append("overlap present or uncertain with no alert: a UDK may be masked by another voice (G6)")
    if any(e.state == NEGATIVE for e in by["target_speaker"]) and out.decision != "NO_ALERT":
        out.annotations.append("speaker is not the enrolled user: alert kept (any voice saying a UDK alerts)")
    if lx.origin != "none" and out.decision != "NO_ALERT" and out.basis == "linguistic" and not acoustic_pos:
        if any(e.state in (UNCERTAIN, UNAVAILABLE) for e in by["acoustic_distress"]) or not by["acoustic_distress"]:
            out.annotations.append("no acoustic confirmation: linguistic alert unchanged (absence is not evidence of safety)")

    # R8 invariants
    out.rules_fired.append("R8")
    _invariants(out, lx)
    return out


def _invariants(out: FusedDecision, lx) -> None:
    if out.decision == "TRIGGER_ALL":
        assert lx.udk_path, "I1: TRIGGER_ALL without a UDK-path linguistic alert"
    assert RANK[out.decision] >= RANK[lx.phase3_decision], "I2: Phase 5 lowered the Phase 3 decision"
    if lx.origin == "danger_without_udk":
        assert out.decision != "TRIGGER_ALL", "I3: classifier-only TRIGGER_ALL"
    if lx.origin in ("personal_udk", "kws_udk"):
        assert out.decision != "NO_ALERT", "I4: PERSONAL / KWS alert suppressed"
    if out.basis == "acoustic":
        assert out.decision == "TRIGGER_VERIFY", "I1: acoustic-only above TRIGGER_VERIFY"
