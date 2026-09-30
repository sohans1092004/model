"""Explicit fusion policy (configs/*.json, format "udk_fusion.config/1"; no defaults).

  acoustic_alone     {enabled, sources}  sources whose POSITIVE may raise TRIGGER_VERIFY with no linguistic
                                         alert (live: 4-class scream trigger). Never TRIGGER_ALL (hard, I1).
  corroboration      {enabled, sources}  sources whose POSITIVE may lift a UDK-path TRIGGER_VERIFY to
                                         TRIGGER_ALL (live: 9-class >= 0.30). Never a classifier-only alert (I7).
  s4_status          must be "open" until the owner closes S-4 (udk_signals/DECISION_S4_BEATS_ROLE.md).
  veto_guard.sentence_veto_requires_clean_overlap
                     true: the live sentence veto is honoured only when overlap evidence is a clean
                     NEGATIVE. false (production-equivalent): the live veto stands as it does today.
                     (The context veto guard is a hard rule, R3.)

s4_acoustic_policy(option, trigger_sources, corroboration_sources) builds the acoustic sections of the
four S-4 options A-D so they can be evaluated side by side on real data later. It does NOT choose one.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_FORMAT = "udk_fusion.config/1"
FORBIDDEN = ("allow_acoustic_trigger_all", "allow_classifier_trigger_all", "allow_lowering", "allow_signal_veto")
S4_OPTIONS = {"A": (True, False), "B": (False, True), "C": (True, True), "D": (False, False)}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class FusionPolicy:
    raw: dict
    sha256: str

    @classmethod
    def from_dict(cls, raw) -> FusionPolicy:
        if not isinstance(raw, dict) or raw.get("format") != CONFIG_FORMAT:
            raise PolicyError(f"format must be {CONFIG_FORMAT!r}")
        blob = json.dumps(raw)
        for k in FORBIDDEN:
            if k in blob:
                raise PolicyError(f"{k}: safety invariants are hard rules, not configuration")
        for sec in ("acoustic_alone", "corroboration"):
            s = raw.get(sec)
            if not isinstance(s, dict) or set(s) - {"enabled", "sources"} or not {"enabled", "sources"} <= set(s):
                raise PolicyError(f"{sec} needs exactly enabled, sources (no defaults)")
            if not isinstance(s["enabled"], bool) or not isinstance(s["sources"], list):
                raise PolicyError(f"{sec}: enabled must be bool, sources a list")
            if s["enabled"] and not s["sources"]:
                raise PolicyError(f"{sec} is enabled with no sources")
        if raw.get("s4_status") != "open":
            raise PolicyError("s4_status must be 'open': S-4 is an owner decision not yet taken")
        vg = raw.get("veto_guard")
        if not isinstance(vg, dict) or not isinstance(vg.get("sentence_veto_requires_clean_overlap"), bool):
            raise PolicyError("veto_guard.sentence_veto_requires_clean_overlap must be true/false (no default)")
        return cls(raw, hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest())

    @classmethod
    def load(cls, path) -> FusionPolicy:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def sec(self, name: str) -> dict:
        return self.raw[name]


def s4_acoustic_policy(base: FusionPolicy, option: str) -> FusionPolicy:
    """Same policy with the acoustic sections switched to S-4 option A/B/C/D (sources kept). For
    side-by-side evaluation only; which option applies is the owner's decision (S-4)."""
    if option not in S4_OPTIONS:
        raise PolicyError("option must be A, B, C or D")
    alone, corr = S4_OPTIONS[option]
    raw = copy.deepcopy(base.raw)
    raw["acoustic_alone"]["enabled"], raw["corroboration"]["enabled"] = alone, corr
    raw["_s4_option_under_evaluation"] = option
    return FusionPolicy.from_dict(raw)
