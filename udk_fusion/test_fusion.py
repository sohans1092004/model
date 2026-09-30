"""Phase 5 tests: input contract, policy loading, every rule R0-R8, the safety invariants over an exhaustive
grid of linguistic x signal combinations under S-4 options A-D, conformance with the Phase 4 fusion rules,
end-to-end runs on the Phase 3 toy scenes, and the evaluation interface. Deterministic; no model, no data.
Everything here is TOY: it checks decision logic, never performance.

    python udk_fusion/test_fusion.py
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from asr_bench.textnorm import normalise
from udk_context.context_window import build_window
from udk_context.decision import ContextConfig, FinalDecision, UdkEvidence
from udk_context.decision import decide as phase3_decide
from udk_context.intent import FixtureIntentScorer
from udk_context.scene import load_scenes
from udk_fusion.engine import decide
from udk_fusion.evaluation import compare, evaluate
from udk_fusion.inputs import RANK, ContractError, FusionInput, LinguisticEvidence, from_phase3
from udk_fusion.policy import FusionPolicy, PolicyError, s4_acoustic_policy
from udk_signals.evidence import NEGATIVE, POSITIVE, UNAVAILABLE, UNCERTAIN, Evidence
from udk_signals.fusion import fuse as phase4_fuse
from udk_signals.fusion import load_config as phase4_config
from udks import GENERAL_UDKS

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


PROD = FusionPolicy.load(HERE / "configs" / "production_equivalent.json")
FIXP = FusionPolicy.load(HERE / "configs" / "fixture_fusion.json")
P4_PROD = phase4_config(ROOT / "udk_signals" / "configs" / "production_equivalent.json")
C3_PROD = ContextConfig.load(ROOT / "udk_context" / "configs" / "production_equivalent.json")
C3_FIX = ContextConfig.load(ROOT / "udk_context" / "configs" / "fixture_context.json")
T4, T9 = "beats_4class_scream_trigger", "beats_9class_corroboration"


def E(kind, state, source="src", **kw):
    return Evidence(kind, state, source, "test", **kw)


# ---- linguistic evidence built through the REAL Phase 3 decide() wherever Phase 3 can produce it ----
def udk(decision, udk_type="GENERAL", layer="exact", text="help me please", hbb=True, phrase="help me please"):
    return UdkEvidence(decision, "UDK_X" if udk_type else None, udk_type, phrase if udk_type else None, layer,
                       0.9 if decision != "NO_ACTION" else 0.0, hbb, text)


def final(ev, decision, source, reasons=()):
    return FinalDecision(decision, source, ev.decision, list(reasons), {}, {"negator_scopes_udk": False})


def L(kind):
    """Canonical linguistic cases. Built as Phase 3 output (FinalDecision) and validated by from_phase3."""
    table = {
        "std_verify": (udk("TRIGGER_VERIFY"), "TRIGGER_VERIFY", "udk_path"),
        "std_all": (udk("TRIGGER_ALL"), "TRIGGER_ALL", "udk_path"),
        "personal_verify": (udk("TRIGGER_VERIFY", "PERSONAL", phrase="blue umbrella"), "TRIGGER_VERIFY", "udk_path"),
        "personal_all": (udk("TRIGGER_ALL", "PERSONAL", phrase="blue umbrella"), "TRIGGER_ALL", "udk_path"),
        "kws_verify": (udk("TRIGGER_VERIFY", "GENERAL", layer="kws"), "TRIGGER_VERIFY", "udk_path"),
        "ctx_escalated": (udk("TRIGGER_VERIFY"), "TRIGGER_ALL", "udk_path+context_escalation"),
        "danger_no_udk": (udk("NO_ACTION", None, "none", text="he has a knife"), "TRIGGER_VERIFY", "context_intent"),
        "none": (udk("NO_ACTION", None, "none", text="nice weather"), "NO_ACTION", "udk_path"),
        "vetoed_sentence_verify": (udk("TRIGGER_VERIFY"), "NO_ACTION", "vetoed:sentence"),
        "vetoed_sentence_all": (udk("TRIGGER_ALL"), "NO_ACTION", "vetoed:sentence"),
        "vetoed_context_verify": (udk("TRIGGER_VERIFY"), "NO_ACTION", "vetoed:context"),
        "vetoed_context_all": (udk("TRIGGER_ALL"), "NO_ACTION", "vetoed:context"),
    }
    ev, dec, src = table[kind]
    return from_phase3(ev, final(ev, dec, src))


def run(kind, signals=(), policy=PROD, **kw):
    return decide(FusionInput(L(kind), tuple(signals), **kw), policy)


# =========================================================== contract
print("-- input contract (R0)")
ev = udk("TRIGGER_VERIFY", "GENERAL", layer="acoustic_scream")
check("live scream alert passed as linguistic evidence -> ContractError (double counting)",
      raises(lambda: from_phase3(ev, final(ev, "TRIGGER_VERIFY", "udk_path")), ContractError))
ev = udk("TRIGGER_ALL", "PERSONAL")
check("vetoed PERSONAL alert -> ContractError (Phase 3 H1)",
      raises(lambda: from_phase3(ev, final(ev, "NO_ACTION", "vetoed:sentence")), ContractError))
ev = udk("TRIGGER_VERIFY", layer="kws")
check("vetoed KWS alert -> ContractError (H1)", raises(lambda: from_phase3(ev, final(ev, "NO_ACTION", "vetoed:context")), ContractError))
ev = udk("NO_ACTION", None, "none")
check("classifier-only TRIGGER_ALL -> ContractError (H6)",
      raises(lambda: from_phase3(ev, final(ev, "TRIGGER_ALL", "context_intent")), ContractError))
ev = udk("TRIGGER_VERIFY")
check("Phase 3 changing a decision without a recorded rule -> ContractError",
      raises(lambda: from_phase3(ev, final(ev, "NO_ACTION", "udk_path")), ContractError))
check("unknown Phase 3 source -> ContractError", raises(lambda: from_phase3(ev, final(ev, "TRIGGER_VERIFY", "magic")), ContractError))
bad = FinalDecision("TRIGGER_ALL", "udk_path", "TRIGGER_VERIFY", [], {}, {})
check("udk_decision mismatch between UdkEvidence and FinalDecision -> ContractError",
      raises(lambda: from_phase3(udk("TRIGGER_ALL"), bad), ContractError))
check("non-Evidence signal -> ContractError", raises(lambda: FusionInput(L("none"), ({"kind": "overlap"},)), ContractError))
check("origins classified", [L(k).origin for k in ("std_verify", "personal_all", "kws_verify", "danger_no_udk", "none", "vetoed_context_all")]
      == ["standard_udk", "personal_udk", "kws_udk", "danger_without_udk", "none", "standard_udk"])

print("-- policy")
raw = json.loads((HERE / "configs" / "production_equivalent.json").read_text())


def mut(f):
    r = json.loads(json.dumps(raw))
    f(r)
    return r


check("production-equivalent policy loads; S-4 open", PROD.raw["s4_status"] == "open")
check("production-equivalent mirrors live flags (acoustic-alone 4-class, corroboration 9-class, veto guard off)",
      PROD.sec("acoustic_alone") == {"enabled": True, "sources": [T4]} and PROD.sec("corroboration") == {"enabled": True, "sources": [T9]}
      and PROD.sec("veto_guard")["sentence_veto_requires_clean_overlap"] is False)
check("production-equivalent acoustic sections equal the Phase 4 production-equivalent config",
      PROD.sec("acoustic_alone") == P4_PROD["acoustic_alone"] and PROD.sec("corroboration") == P4_PROD["corroboration"])
for k in ("allow_acoustic_trigger_all", "allow_classifier_trigger_all", "allow_lowering", "allow_signal_veto"):
    check(f"policy rejects {k} (hard rule)", raises(lambda: FusionPolicy.from_dict(mut(lambda r: r.__setitem__(k, True))), PolicyError))
check("policy rejects a closed S-4", raises(lambda: FusionPolicy.from_dict(mut(lambda r: r.__setitem__("s4_status", "C"))), PolicyError))
check("policy rejects missing veto_guard (no defaults)", raises(lambda: FusionPolicy.from_dict(mut(lambda r: r.pop("veto_guard"))), PolicyError))
check("policy rejects enabled acoustic role with no sources",
      raises(lambda: FusionPolicy.from_dict(mut(lambda r: r["acoustic_alone"].__setitem__("sources", []))), PolicyError))
check("policy rejects unknown keys in an acoustic role (e.g. a threshold smuggled in)",
      raises(lambda: FusionPolicy.from_dict(mut(lambda r: r["corroboration"].__setitem__("threshold", 0.1))), PolicyError))
OPTS = {o: s4_acoustic_policy(PROD, o) for o in "ABCD"}
check("S-4 options A-D expressible; C == production-equivalent flags",
      [(OPTS[o].sec("acoustic_alone")["enabled"], OPTS[o].sec("corroboration")["enabled"]) for o in "ABCD"]
      == [(True, False), (False, True), (True, True), (False, False)] and OPTS["C"].raw["s4_status"] == "open")
check("S-4 helper rejects unknown option", raises(lambda: s4_acoustic_policy(PROD, "E"), PolicyError))

# =========================================================== named scenarios
print("-- scenarios")
r = run("std_verify", [E("acoustic_distress", POSITIVE, T9)])
check("UDK VERIFY + acoustic corroboration POSITIVE -> TRIGGER_ALL, basis fused, R5",
      (r.decision, r.basis) == ("TRIGGER_ALL", "fused") and "R5" in r.rules_fired and any(c.get("source") == T9 for c in r.contributing))
r = run("std_verify", [E("acoustic_distress", UNCERTAIN, T9), E("acoustic_distress", UNCERTAIN, T4)])
check("UDK VERIFY + acoustic UNCERTAIN -> unchanged VERIFY, both listed as ignored",
      r.decision == "TRIGGER_VERIFY" and r.basis == "linguistic" and len([i for i in r.ignored if i["kind"] == "acoustic_distress"]) == 2
      and r.evidence_status == "partial")
r = run("std_all", [E("acoustic_distress", UNAVAILABLE, T4)])
check("UDK ALL + acoustic UNAVAILABLE -> TRIGGER_ALL kept; 'absence is not safety' annotated",
      r.decision == "TRIGGER_ALL" and any("absence is not evidence of safety" in a for a in r.annotations))
r = run("std_verify", [E("acoustic_distress", NEGATIVE, "fixture-acoustic (TEST ONLY)")], FIXP)
check("UDK VERIFY + acoustic NEGATIVE -> unchanged (NEGATIVE never lowers)", r.decision == "TRIGGER_VERIFY"
      and any(c["why"].startswith("NEGATIVE never lowers") for c in r.considered))
r = run("std_all", [E("speaker_attribution", UNCERTAIN), E("target_speaker", UNAVAILABLE)])
check("UDK + speaker attribution UNCERTAIN / target UNAVAILABLE -> alert kept", r.decision == "TRIGGER_ALL")
r = run("std_verify", [E("target_speaker", NEGATIVE)])
check("UDK + 'not the enrolled user' -> alert kept (any voice saying a UDK alerts)",
      r.decision == "TRIGGER_VERIFY" and any("any voice" in a for a in r.annotations))
r = run("std_verify", [E("overlap", POSITIVE)])
check("UDK + overlap POSITIVE -> alert kept, no masking annotation needed", r.decision == "TRIGGER_VERIFY")
r = run("none", [E("overlap", POSITIVE)])
check("no UDK + overlap POSITIVE -> NO_ALERT with 'UDK may be masked' (overlap never a clean negative)",
      r.decision == "NO_ALERT" and "R7:overlap_masking" in r.rules_fired)
r = run("none", [E("overlap", UNCERTAIN)])
check("no UDK + overlap UNCERTAIN -> masking annotation too", "R7:overlap_masking" in r.rules_fired)
r = run("danger_no_udk", [E("acoustic_distress", POSITIVE, T9), E("acoustic_distress", POSITIVE, T4)])
check("danger-without-UDK + acoustic POSITIVE -> TRIGGER_VERIFY only (classifier + acoustic never ALL)",
      r.decision == "TRIGGER_VERIFY" and "R5:blocked_classifier_only" in r.rules_fired)
r = run("danger_no_udk", [E("overlap", NEGATIVE), E("speaker_attribution", POSITIVE)])
check("danger-without-UDK + clean context evidence -> TRIGGER_VERIFY (classifier-only never ALL)", r.decision == "TRIGGER_VERIFY")
r = run("none", [E("acoustic_distress", POSITIVE, T4)])
check("safe phrase / no UDK + scream trigger POSITIVE -> TRIGGER_VERIFY, basis acoustic, R6",
      (r.decision, r.basis) == ("TRIGGER_VERIFY", "acoustic") and "R6" in r.rules_fired)
r = run("none", [E("acoustic_distress", POSITIVE, T9)])
check("no UDK + 9-class POSITIVE only -> NO_ALERT (corroboration never creates an alert)",
      r.decision == "NO_ALERT" and any(c["source"] == T9 for c in r.considered))
r = run("none", [E("acoustic_distress", POSITIVE, "some-new-model")])
check("acoustic source not named in policy -> ignored, recorded", r.decision == "NO_ALERT"
      and any(i["why"] == "source not named in the acoustic policy" for i in r.ignored))
r = run("vetoed_sentence_verify", [E("acoustic_distress", POSITIVE, T4)])
check("sentence-vetoed UDK + scream -> TRIGGER_VERIFY acoustic (live order: scream fires when no alert is left)",
      (r.decision, r.basis) == ("TRIGGER_VERIFY", "acoustic"))
r = run("vetoed_context_all")
check("context veto with NO speaker/overlap evidence -> reinstated TRIGGER_ALL (missing attribution never suppresses)",
      r.decision == "TRIGGER_ALL" and "R3:veto_reinstated" in r.rules_fired and r.basis == "fused")
r = run("vetoed_context_all", [E("speaker_attribution", POSITIVE), E("overlap", NEGATIVE)])
check("context veto + attribution POSITIVE + overlap NEGATIVE -> veto stands (NO_ALERT)",
      r.decision == "NO_ALERT" and "R3:veto_stands" in r.rules_fired)
r = run("vetoed_context_all", [E("speaker_attribution", POSITIVE), E("speaker_attribution", UNCERTAIN), E("overlap", NEGATIVE)])
check("context veto + one attribution UNCERTAIN -> reinstated", r.decision == "TRIGGER_ALL")
r = run("vetoed_context_all", [E("speaker_attribution", POSITIVE), E("overlap", NEGATIVE), E("overlap", POSITIVE)])
check("conflicting overlap (NEGATIVE + POSITIVE) -> not clean -> veto reinstated; conflict annotated",
      r.decision == "TRIGGER_ALL" and any("conflicting overlap" in a for a in r.annotations))
r = run("vetoed_context_all", [E("speaker_attribution", POSITIVE), E("overlap", NEGATIVE), E("condition", POSITIVE, "dsp")])
check("degraded audio: overlap NEGATIVE reported UNCERTAIN -> context veto reinstated (G5)",
      r.decision == "TRIGGER_ALL" and "R1:degraded" in r.rules_fired)
r = run("vetoed_context_verify", [E("acoustic_distress", POSITIVE, T9)])
check("reinstated VERIFY + corroboration -> TRIGGER_ALL (fused)", r.decision == "TRIGGER_ALL")
r = run("vetoed_sentence_all", [E("overlap", POSITIVE)], FIXP)
check("sentence-veto guard ON + overlap POSITIVE -> reinstated", r.decision == "TRIGGER_ALL" and "R4:veto_reinstated" in r.rules_fired)
r = run("vetoed_sentence_all", [E("overlap", NEGATIVE)], FIXP)
check("sentence-veto guard ON + overlap clean NEGATIVE -> veto stands", r.decision == "NO_ALERT" and "R4:veto_stands" in r.rules_fired)
r = run("vetoed_sentence_all", [E("overlap", POSITIVE)])
check("production-equivalent (guard off): live sentence veto unchanged even with overlap", r.decision == "NO_ALERT")
for k in ("personal_verify", "personal_all", "kws_verify"):
    r = run(k, [E("target_speaker", NEGATIVE), E("overlap", UNCERTAIN), E("speaker_attribution", UNAVAILABLE), E("condition", POSITIVE, "dsp")])
    check(f"{k}: kept under every adverse signal (Phase 3 H1 protections intact)", RANK[r.decision] >= RANK[L(k).phase3_decision])
r = run("personal_verify", [E("acoustic_distress", POSITIVE, T9)])
check("custom UDK VERIFY + corroboration -> TRIGGER_ALL (UDK path, as live)", r.decision == "TRIGGER_ALL")
r = run("ctx_escalated", [E("acoustic_distress", UNAVAILABLE, T9)])
check("Phase 3 context escalation (VERIFY->ALL on a UDK) passes through unchanged", r.decision == "TRIGGER_ALL" and r.basis == "linguistic")
r = run("std_all", [E("acoustic_distress", POSITIVE, T4, start_s=10.0, end_s=12.0)], start_s=0.0, end_s=2.0)
check("evidence outside the utterance span -> ignored", any(i["why"] == "span outside the utterance" for i in r.ignored))
r = run("none", [E("acoustic_distress", POSITIVE, T4, start_s=10.0, end_s=12.0)], start_s=0.0, end_s=2.0)
check("out-of-span scream does not raise an alert", r.decision == "NO_ALERT")
r = run("none", [E("acoustic_distress", POSITIVE, T4), E("acoustic_distress", NEGATIVE, "fixture-acoustic (TEST ONLY)")], FIXP)
check("conflicting acoustic (POSITIVE + NEGATIVE) -> POSITIVE kept, conflict annotated",
      r.decision == "TRIGGER_VERIFY" and any("conflicting acoustic" in a for a in r.annotations))
r = run("none")
check("no evidence at all -> NO_ALERT, evidence_status partial", r.decision == "NO_ALERT" and r.evidence_status == "partial")
rec = run("std_verify", [E("acoustic_distress", POSITIVE, T9)]).record()
check("provenance record is JSON-serialisable and complete",
      json.loads(json.dumps(rec))["production_decision"] == "TRIGGER_ALL"
      and all(k in rec for k in ("rules_fired", "contributing", "considered", "ignored", "basis", "policy_sha256")))

# negation: build through the real Phase 3 decide (negation is evidence only there, H5)
nev = UdkEvidence("TRIGGER_VERIFY", "UDK_7", "GENERAL", "help me", "exact", 0.8, True, "I'm not okay, don't just stand there, help me")
nfin = phase3_decide(nev, build_window(load_scenes(ROOT / "udk_context" / "fixtures" / "scenes_toy.jsonl")[0], 20, 6), C3_PROD)
r = decide(FusionInput(from_phase3(nev, nfin), (E("acoustic_distress", UNCERTAIN, T4),)), PROD)
check("negation alone never suppresses (through real Phase 3 decide)", r.decision == "TRIGGER_VERIFY")

# =========================================================== exhaustive grid + invariants
print("-- exhaustive grid (invariants)")
LKINDS = ["std_verify", "std_all", "personal_verify", "personal_all", "kws_verify", "ctx_escalated", "danger_no_udk", "none",
          "vetoed_sentence_verify", "vetoed_sentence_all", "vetoed_context_verify", "vetoed_context_all"]
A_ST = [POSITIVE, UNCERTAIN, UNAVAILABLE, None]
OV_ST = [POSITIVE, NEGATIVE, UNCERTAIN, UNAVAILABLE, None]
AT_ST = [POSITIVE, UNCERTAIN, UNAVAILABLE, None]
CO_ST = [POSITIVE, NEGATIVE, None]
TS_ST = [POSITIVE, NEGATIVE, UNCERTAIN, None]
POLS = {**{f"S4-{o}": OPTS[o] for o in "ABCD"}, "fixture": FIXP}
LX = {k: L(k) for k in LKINDS}


def sig(a4, a9, ov, at, co, ts):
    s = []
    if a4: s.append(E("acoustic_distress", a4, T4))
    if a9: s.append(E("acoustic_distress", a9, T9))
    if ov: s.append(E("overlap", ov))
    if at: s.append(E("speaker_attribution", at))
    if co: s.append(E("condition", co, "dsp"))
    if ts: s.append(E("target_speaker", ts))
    return tuple(s)


viol = {k: [] for k in ("I1_acoustic_only_all", "I1_all_without_udk", "I2_lowered", "I3_classifier_all", "I4_protected_suppressed",
                        "attr_missing_suppresses", "overlap_as_clean_negative", "uncertain_changes_decision", "phase4_conformance",
                        "nondeterministic", "negative_lowers")}
n = 0
RES = {}
for pname, pol in POLS.items():
    p4cfg = dict(P4_PROD, acoustic_alone=pol.sec("acoustic_alone"), corroboration=pol.sec("corroboration"))
    for k, combo in itertools.product(LKINDS, itertools.product(A_ST, A_ST, OV_ST, AT_ST, CO_ST, TS_ST)):
        lx = LX[k]
        s = sig(*combo)
        r = decide(FusionInput(lx, s), pol)
        RES[(pname, k, combo)] = r.decision
        n += 1
        if r.decision == "TRIGGER_ALL" and r.basis == "acoustic":
            viol["I1_acoustic_only_all"].append((pname, k, combo))
        if r.decision == "TRIGGER_ALL" and not lx.udk_path:
            viol["I1_all_without_udk"].append((pname, k, combo))
        if RANK[r.decision] < RANK[lx.phase3_decision]:
            viol["I2_lowered"].append((pname, k, combo))
        if lx.origin == "danger_without_udk" and r.decision == "TRIGGER_ALL":
            viol["I3_classifier_all"].append((pname, k, combo))
        if lx.origin in ("personal_udk", "kws_udk") and r.decision == "NO_ALERT":
            viol["I4_protected_suppressed"].append((pname, k, combo))
        # Phase 4 conformance wherever Phase 5 adds no veto guard of its own
        if lx.vetoed is None or (lx.vetoed == "sentence" and not pol.sec("veto_guard")["sentence_veto_requires_clean_overlap"]):
            p4 = phase4_fuse({"NO_ALERT": "NO_ACTION"}.get(lx.phase3_decision, lx.phase3_decision), lx.phase3_source, list(s), p4cfg).decision
            if {"NO_ACTION": "NO_ALERT"}.get(p4, p4) != r.decision:
                viol["phase4_conformance"].append((pname, k, combo, p4, r.decision))
        if n % 997 == 0 and decide(FusionInput(lx, s), pol).record() != r.record():
            viol["nondeterministic"].append((pname, k, combo))
# pairwise monotonicity properties over the grid
for (pname, k, (a4, a9, ov, at, co, ts)), d in RES.items():
    if at == POSITIVE:
        for alt in (UNCERTAIN, UNAVAILABLE, None):
            if RANK[RES[(pname, k, (a4, a9, ov, alt, co, ts))]] < RANK[d]:
                viol["attr_missing_suppresses"].append((pname, k, alt))
    if ov == NEGATIVE:
        for alt in (POSITIVE, UNCERTAIN, UNAVAILABLE, None):
            if RANK[RES[(pname, k, (a4, a9, alt, at, co, ts))]] < RANK[d]:
                viol["overlap_as_clean_negative"].append((pname, k, alt))
    if a4 is None and a9 is None:
        for u4, u9 in itertools.product((UNCERTAIN, UNAVAILABLE, None), repeat=2):
            if RES[(pname, k, (u4, u9, ov, at, co, ts))] != d:
                viol["uncertain_changes_decision"].append((pname, k, u4, u9))
    if ts == NEGATIVE and RANK[d] < RANK[RES[(pname, k, (a4, a9, ov, at, co, None))]]:
        viol["negative_lowers"].append((pname, k, "target_speaker"))
check(f"grid covered {n} decisions (12 linguistic cases x 3840 signal combinations x 5 policies)", n == 12 * 3840 * 5)
for name, v in viol.items():
    check(f"invariant {name}: 0 violations", not v, v[:3])

# S-4 options behave as documented (no choice made)
g = lambda o, k, a4, a9: RES[(f"S4-{o}", k, (a4, a9, None, None, None, None))]
check("S-4 A: scream-alone VERIFY yes, corroboration no", g("A", "none", POSITIVE, None) == "TRIGGER_VERIFY" and g("A", "std_verify", None, POSITIVE) == "TRIGGER_VERIFY")
check("S-4 B: scream-alone no, corroboration yes", g("B", "none", POSITIVE, None) == "NO_ALERT" and g("B", "std_verify", None, POSITIVE) == "TRIGGER_ALL")
check("S-4 C: both (live)", g("C", "none", POSITIVE, None) == "TRIGGER_VERIFY" and g("C", "std_verify", None, POSITIVE) == "TRIGGER_ALL")
check("S-4 D: neither; linguistic alerts untouched", g("D", "none", POSITIVE, POSITIVE) == "NO_ALERT" and g("D", "std_all", POSITIVE, POSITIVE) == "TRIGGER_ALL")

# =========================================================== Phase 3 toy scenes end to end
print("-- Phase 3 toy scenes -> Phase 5 (TOY)")
SCENES = load_scenes(ROOT / "udk_context" / "fixtures" / "scenes_toy.jsonl")
SENT, CTX = FixtureIntentScorer(False), FixtureIntentScorer(True)


def fixture_evidence(scene):
    """TEST ONLY (same rule as udk_context/test_context.py): whole-word UDK containment."""
    text = scene.target.text
    w = " " + " ".join(normalise(text)[0]) + " "
    phrases = [(u.udk_id, u.phrase, "GENERAL") for u in GENERAL_UDKS]
    if scene.custom_phrase:
        phrases.insert(0, ("PUDK_U0", scene.custom_phrase, "PERSONAL"))
    for uid, ph, typ in phrases:
        if " " + " ".join(normalise(ph)[0]) + " " in w:
            return UdkEvidence("TRIGGER_ALL", uid, typ, ph, "exact", 1.0, True, text)
    return UdkEvidence("NO_ACTION", None, None, None, "none", 0.0, True, text)


def annotation_signals(scene):
    """Evaluation-only oracle evidence from the scene labels (source 'annotation')."""
    win = build_window(scene, 20.0, 6)
    ov = scene.overlap is not None or bool(win.concurrent)
    at = POSITIVE if win.attribution_complete else UNAVAILABLE
    return (E("overlap", POSITIVE if ov else NEGATIVE, "annotation"), E("speaker_attribution", at, "annotation"))


items_none, items_ann, p3_alerts, lost = [], [], {}, []
for sc in SCENES:
    uev = fixture_evidence(sc)
    fin = phase3_decide(uev, build_window(sc, 20.0, 6), C3_FIX, SENT, CTX)
    lx = from_phase3(uev, fin)
    p3_alerts[sc.scene_id] = lx.phase3_decision
    r0 = decide(FusionInput(lx, (), utterance_id=sc.scene_id), PROD)
    r1 = decide(FusionInput(lx, annotation_signals(sc), utterance_id=sc.scene_id), PROD)
    items_none.append((r0, sc.label, "no_signals", sc.problem_type))
    items_ann.append((r1, sc.label, "annotation_signals", sc.problem_type))
    if sc.label == "DANGER" and RANK[r0.decision] < RANK[lx.phase3_decision]:
        lost.append(sc.scene_id)
check("all 26 Phase 3 toy scenes pass the Phase 5 input contract", len(items_none) == 26)
check("no Phase 3 DANGER alert is lowered by Phase 5", not lost, lost)
ctx_vetoed = [d.utterance_id for d, *_ in items_none if d.phase3_source == "vetoed:context"]
check("Phase 3 context vetoes with no Phase 4 evidence are all reinstated (R3)",
      ctx_vetoed and all(d.decision != "NO_ALERT" for d, *_ in items_none if d.phase3_source == "vetoed:context"), ctx_vetoed)
stand = {d.utterance_id for d, *_ in items_ann if "R3:veto_stands" in d.rules_fired}
check("with annotation evidence, context vetoes stand only where attribution is complete and no overlap",
      all(annotation_signals(next(s for s in SCENES if s.scene_id == u))[0].state == NEGATIVE for u in stand), stand)
check("attacker/victim scenes (a0x_danger with attacker context) keep their alert",
      all(d.decision != "NO_ALERT" for d, lab, *_ in items_ann if lab == "DANGER" and d.utterance_id.startswith(("a01_danger", "a02_danger", "a03_danger"))))
REP0, REP1 = evaluate(items_none, "fixture"), evaluate(items_ann, "fixture")
t0, t1 = REP0["by_condition"]["all"], REP1["by_condition"]["all"]
check(f"TOY report (no signals): danger alert {t0['danger_alert_recall']['num']}/{t0['danger_alert_recall']['den']}, "
      f"safe alert {t0['safe_false_alert']['num']}/{t0['safe_false_alert']['den']}, reinstated {t0['vetoes_reinstated']} -- TOY, not performance",
      REP0["banner"].startswith("TOY") and REP0["performance_claims_allowed"] is False)
check(f"TOY report (annotation signals): danger alert {t1['danger_alert_recall']['num']}/{t1['danger_alert_recall']['den']}, "
      f"safe alert {t1['safe_false_alert']['num']}/{t1['safe_false_alert']['den']}, reinstated {t1['vetoes_reinstated']} -- TOY",
      t1["danger_alert_recall"]["num"] == t1["danger_alert_recall"]["den"])

# =========================================================== evaluation interface
print("-- evaluation interface")
check("evaluate requires provenance; final_test is refused", raises(lambda: evaluate(items_none, "final_test"), ValueError))
check("real_dev provenance allows claims, synthetic does not",
      evaluate(items_none, "real_dev")["performance_claims_allowed"] and not evaluate(items_none, "synthetic")["performance_claims_allowed"])
check("bad label refused", raises(lambda: evaluate([(items_none[0][0], "MAYBE", "c", "g")], "fixture"), ValueError))
cmp_ = compare({o: [(decide(FusionInput(LX["none"], (E("acoustic_distress", POSITIVE, T4),)), OPTS[o]), "DANGER", "c", "g")] for o in "ABCD"}, "fixture")
check("compare() reports S-4 options side by side without selecting one",
      set(cmp_["policies"]) == set("ABCD") and "owner decision" in cmp_["note"] and "selected" not in json.dumps(cmp_))

# =========================================================== isolation
print("-- isolation")
imports = [p for p in ROOT.glob("*.py") if "udk_fusion" in p.read_text(encoding="utf-8", errors="ignore")]
check("no production module imports udk_fusion", not imports, imports)
check("Phase 3 / Phase 4 packages do not import udk_fusion",
      not any("udk_fusion" in p.read_text() for p in list((ROOT / "udk_context").glob("*.py")) + list((ROOT / "udk_signals").glob("*.py"))))

print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
