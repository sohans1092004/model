"""Fusion of the linguistic decision (production UDK path / Phase 3 layer) with Phase 4 signal evidence.

Hard rules (not configurable):
  G1 A linguistic alert is never lowered by any signal: not by acoustic absence, not by "not the
     target speaker" (Phase 0 product rule: any voice saying a UDK alerts), not by overlap or
     missing attribution.
  G2 Acoustic evidence alone can raise at most TRIGGER_VERIFY -- never TRIGGER_ALL.
  G3 Acoustic corroboration may lift TRIGGER_VERIFY to TRIGGER_ALL only when the linguistic alert
     came from the UDK path (source "udk_path..."), never a classifier-only "context_intent" alert.
  G4 UNCERTAIN / UNAVAILABLE evidence changes nothing and is reported as such.
  G5 On degraded audio (condition POSITIVE), NEGATIVE evidence is reported as UNCERTAIN.
  G6 Overlap evidence never creates an alert; with no alert it only annotates "UDK may be masked".
Configurable (configs/*.json, no defaults): which acoustic sources may raise the acoustic-alone
VERIFY and which may corroborate. production_equivalent.json mirrors the live 96ea038 flags
(scream-alone VERIFY from the 4-class trigger; 9-class >= 0.30 corroboration), which still use the
unverified BEATs signals; whether they stay is S-4.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from udk_signals.evidence import NEGATIVE, POSITIVE, UNCERTAIN, Evidence

CONFIG_FORMAT = "udk_signals.config/1"


class SignalConfigError(ValueError):
    pass


def load_config(path_or_dict) -> dict:
    raw = path_or_dict if isinstance(path_or_dict, dict) else json.loads(Path(path_or_dict).read_text(encoding="utf-8"))
    if raw.get("format") != CONFIG_FORMAT:
        raise SignalConfigError(f"format must be {CONFIG_FORMAT!r}")
    for sec, keys in {"acoustic_alone": ("enabled", "sources"), "corroboration": ("enabled", "sources"),
                      "condition": ("min_duration_s", "quiet_dbfs", "low_snr_db", "clipping_ratio", "muffled_hf_ratio"),
                      "target_speaker": ("accept", "reject", "min_duration_s"), "attribution": ("same_speaker",)}.items():
        if not isinstance(raw.get(sec), dict) or any(k not in raw[sec] for k in keys):
            raise SignalConfigError(f"{sec} needs {keys} (no defaults)")
    if "allow_acoustic_trigger_all" in json.dumps(raw):
        raise SignalConfigError("acoustic-only TRIGGER_ALL is a hard rule (G2), not configuration")
    return raw


@dataclass
class FusionResult:
    decision: str
    source: str
    linguistic_decision: str
    reasons: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)


def fuse(linguistic_decision: str, linguistic_source: str, signals: list[Evidence], cfg: dict) -> FusionResult:
    degraded = any(e.kind == "condition" and e.state == POSITIVE for e in signals)
    ev = []
    for e in signals:
        if degraded and e.state == NEGATIVE and e.kind != "condition":
            e = replace(e, state=UNCERTAIN, reason=e.reason + " [reported UNCERTAIN: degraded audio (G5)]")
        ev.append(e)
    out = FusionResult(linguistic_decision, linguistic_source, linguistic_decision,
                       evidence=[{"kind": e.kind, "state": e.state, "source": e.source, "score": e.score, "reason": e.reason} for e in ev])
    acoustic_pos = {e.source for e in ev if e.kind == "acoustic_distress" and e.state == POSITIVE}
    if linguistic_decision != "NO_ACTION":
        out.reasons.append("linguistic alert kept: signals never lower it (G1)")
        corr = cfg["corroboration"]
        if (corr["enabled"] and linguistic_decision == "TRIGGER_VERIFY" and acoustic_pos & set(corr["sources"])):
            if linguistic_source.startswith("udk_path"):
                out.decision, out.source = "TRIGGER_ALL", linguistic_source + "+acoustic_corroboration"
                out.reasons.append(f"acoustic corroboration from {sorted(acoustic_pos & set(corr['sources']))} (G3)")
            else:
                out.reasons.append("acoustic corroboration not applied: alert did not come from the UDK path (G3)")
    else:
        alone = cfg["acoustic_alone"]
        hits = acoustic_pos & set(alone["sources"])
        if alone["enabled"] and hits:
            out.decision, out.source = "TRIGGER_VERIFY", "acoustic_alone"
            out.reasons.append(f"acoustic evidence alone from {sorted(hits)}: TRIGGER_VERIFY at most (G2)")
        if any(e.kind == "overlap" and e.state == POSITIVE for e in ev) and out.decision == "NO_ACTION":
            out.reasons.append("overlap detected with no alert: a UDK may be masked by another voice (annotation only, G6)")
    for e in ev:
        if e.state not in (POSITIVE, NEGATIVE):
            out.reasons.append(f"{e.kind}/{e.source}: {e.state} -- no effect (G4)")
    if out.decision == "TRIGGER_ALL" and linguistic_decision == "NO_ACTION":
        raise AssertionError("G2 violated")  # unreachable by construction; guards future edits
    return out
