"""UDK + contextual-intent decision logic.

The production UDK path decides first; this layer complements it and can only act through the rules
below, each explicit in ContextConfig (no defaults; `configs/production_equivalent.json` reproduces
the live behaviour exactly: only the existing sentence veto, 0.02, both STTs must agree).

Hard rules (not configurable -- Phase 0 recall-first, veto design and the v2 failure):
  H1 PERSONAL, keyword-spotting and scream alerts are never vetoed (Phase 0 §8, §12).
  H2 An alert whose words the other STT did not also hear is never vetoed (Phase 0 §12).
  H3 Context from ANOTHER speaker can never lower danger (v2 silenced cries after attacker speech).
  H4 Context cannot veto when attribution is incomplete or another voice overlaps the target.
  H5 Negation features never veto on their own ("I'm not okay, help" stays an alert).
  H6 A classifier alone (danger without a UDK) can only raise TRIGGER_VERIFY, never TRIGGER_ALL.
Configurable, all OFF in the production-equivalent config:
  context_veto        same-speaker-only context scorer may silence a GENERAL text alert (p < threshold),
                      and only while the SENTENCE-level danger score is <= sentence_ceiling, so strongly
                      dangerous wording is never silenced by context (genuine danger despite misleading context)
  context_escalation  context scorer may lift TRIGGER_VERIFY to TRIGGER_ALL (p >= threshold)
  danger_without_udk  scorer may raise TRIGGER_VERIFY when no UDK alert exists (p >= threshold)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from udk_context.context_window import ContextWindow
from udk_context.negation import negation_features

CONFIG_FORMAT = "udk_context.config/1"
TEXT_LAYERS = ("exact", "fuzzy", "semantic")  # as intent_gate.TEXT_LAYERS
RANK = {"NO_ACTION": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2}


class ContextConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ContextConfig:
    raw: dict
    sha256: str

    @classmethod
    def from_dict(cls, raw) -> ContextConfig:
        if not isinstance(raw, dict) or raw.get("format") != CONFIG_FORMAT:
            raise ContextConfigError(f"format must be {CONFIG_FORMAT!r}")
        need = {"window": ("window_s", "max_turns"), "sentence_veto": ("enabled", "threshold", "require_heard_by_both"),
                "context_veto": ("enabled", "threshold", "sentence_ceiling"), "context_escalation": ("enabled", "threshold"),
                "danger_without_udk": ("enabled", "threshold", "require_heard_by_both"),
                "negation": ("negators", "scope_tokens")}
        for sec, keys in need.items():
            if not isinstance(raw.get(sec), dict) or any(k not in raw[sec] for k in keys):
                raise ContextConfigError(f"{sec} needs {keys} (no defaults)")
        for sec in ("sentence_veto", "context_veto", "context_escalation", "danger_without_udk"):
            s = raw[sec]
            if not isinstance(s["enabled"], bool):
                raise ContextConfigError(f"{sec}.enabled must be true/false")
            if s["enabled"] and not (isinstance(s["threshold"], (int, float)) and 0 <= s["threshold"] <= 1):
                raise ContextConfigError(f"{sec} is enabled: threshold must be in [0, 1]")
        cv = raw["context_veto"]
        if cv["enabled"] and not (isinstance(cv["sentence_ceiling"], (int, float)) and 0 <= cv["sentence_ceiling"] <= 1):
            raise ContextConfigError("context_veto is enabled: sentence_ceiling must be in [0, 1]")
        for k in ("block_if_other_speaker", "allow_classifier_trigger_all"):
            if k in raw.get("context_veto", {}) or k in raw.get("danger_without_udk", {}):
                raise ContextConfigError(f"{k} is a hard rule (H3/H6), not configuration")
        return cls(raw, hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest())

    @classmethod
    def load(cls, path) -> ContextConfig:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def sec(self, name: str) -> dict:
        return self.raw[name]


@dataclass(frozen=True)
class UdkEvidence:
    """What the production UDK path produced for the target utterance."""
    decision: str  # TRIGGER_ALL | TRIGGER_VERIFY | NO_ACTION (after production escalation rules)
    udk_id: str | None
    udk_type: str | None  # GENERAL | PERSONAL | None
    udk_phrase: str | None
    layer: str  # exact / fuzzy / semantic / kws / acoustic_scream / none (+ "/sentence")
    confidence: float
    heard_by_both: bool | None  # None = unknown (only one STT)
    transcript: str


@dataclass
class FinalDecision:
    decision: str
    source: str  # udk_path | udk_path+context_escalation | context_intent | vetoed:sentence | vetoed:context
    udk_decision: str
    reasons: list[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    negation: dict = field(default_factory=dict)


def decide(ev: UdkEvidence, window: ContextWindow, cfg: ContextConfig, sentence_scorer=None, context_scorer=None) -> FinalDecision:
    neg_cfg = cfg.sec("negation")
    neg = negation_features(ev.transcript, ev.udk_phrase, set(neg_cfg["negators"]), neg_cfg["scope_tokens"])
    out = FinalDecision(ev.decision, "udk_path", ev.decision, negation=neg)
    alerting = ev.decision != "NO_ACTION"
    text_general = ev.udk_type == "GENERAL" and ev.layer.split("/")[0].startswith(TEXT_LAYERS)
    p_sent = sentence_scorer.score(ev.transcript).p_danger if sentence_scorer is not None else None
    p_ctx = None
    if context_scorer is not None:
        if not context_scorer.uses_context:
            raise ContextConfigError("context_scorer must use context; the sentence model belongs in sentence_scorer")
        p_ctx = context_scorer.score(ev.transcript, window).p_danger
    out.scores = {"p_sentence": p_sent, "p_context": p_ctx}
    if neg["negator_scopes_udk"]:
        out.reasons.append("negation scopes the UDK phrase (evidence only, H5)")

    if alerting:
        if not text_general:
            out.reasons.append("PERSONAL / KWS / scream alert: never vetoed (H1)")
            return out
        sv = cfg.sec("sentence_veto")
        if sv["enabled"] and p_sent is not None:
            if sv["require_heard_by_both"] and ev.heard_by_both is not True:
                out.reasons.append("sentence veto not applied: the other STT did not hear the same words (H2)")
            elif p_sent < sv["threshold"]:
                out.decision, out.source = "NO_ACTION", "vetoed:sentence"
                out.reasons.append(f"sentence veto: P(danger) {p_sent:.3f} < {sv['threshold']} (production rule)")
                return out
        cv = cfg.sec("context_veto")
        if cv["enabled"] and p_ctx is not None:
            blockers = []
            if ev.heard_by_both is not True:
                blockers.append("other STT did not hear the same words (H2)")
            if window.has_other_speaker:
                blockers.append("another speaker in the preceding context (H3)")
            if not window.attribution_complete:
                blockers.append("speaker attribution incomplete (H4)")
            if window.concurrent:
                blockers.append("another voice overlaps the target (H4)")
            if p_sent is None or p_sent > cv["sentence_ceiling"]:
                blockers.append(f"sentence-level danger {p_sent} above the ceiling {cv['sentence_ceiling']}")
            if blockers:
                out.reasons.append("context veto blocked: " + "; ".join(blockers))
            elif p_ctx < cv["threshold"]:
                out.decision, out.source = "NO_ACTION", "vetoed:context"
                out.reasons.append(f"context veto: same-speaker context, P(danger|context) {p_ctx:.3f} < {cv['threshold']}")
                return out
        ce = cfg.sec("context_escalation")
        if ce["enabled"] and p_ctx is not None and out.decision == "TRIGGER_VERIFY" and p_ctx >= ce["threshold"]:
            out.decision, out.source = "TRIGGER_ALL", "udk_path+context_escalation"
            out.reasons.append(f"context escalation: P(danger|context) {p_ctx:.3f} >= {ce['threshold']}")
        return out

    dw = cfg.sec("danger_without_udk")
    p = p_ctx if p_ctx is not None else p_sent
    if dw["enabled"] and p is not None:
        if dw["require_heard_by_both"] and ev.heard_by_both is not True:
            out.reasons.append("danger-without-UDK not raised: the other STT did not hear the same words")
        elif p >= dw["threshold"]:
            out.decision, out.source = "TRIGGER_VERIFY", "context_intent"
            out.reasons.append(f"danger without UDK: P(danger) {p:.3f} >= {dw['threshold']} -> TRIGGER_VERIFY only (H6)")
    return out
