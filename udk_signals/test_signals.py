"""Phase 4 tests on deterministic TOY signals (fixtures.py): evidence states, target-speaker
identification, attribution (never merging overlapped speakers), overlap characterisation,
acoustic distress (live-BEATs wrapper with a fake detector + toy source), robustness conditions,
fusion hard rules G1-G6, and evaluation hooks. Nothing here measures real-world performance.
The BEATs-wrapper checks need numpy (SKIP otherwise). check() style.

    python udk_signals/test_signals.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from udk_signals.acoustic import BeatsScreamSignal
from udk_signals.evaluation import acoustic_metrics, attribution_metrics, overlap_metrics, target_speaker_metrics
from udk_signals.evidence import NEGATIVE, POSITIVE, UNAVAILABLE, UNCERTAIN, Evidence
from udk_signals.fixtures import (SR, FixtureAcousticSource, FixtureEmbedder, FixtureOverlapDetector, clip, crowd, cry, far_field,
                                  mix, pocket, scale_db, scream, silence, traffic, voice)
from udk_signals.fusion import SignalConfigError, fuse, load_config
from udk_signals.overlap import from_annotation
from udk_signals.robustness import ConditionEstimator
from udk_signals.speaker import SpeakerAttributor, TargetSpeakerVerifier

passed = failed = skipped = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


FIX = load_config(HERE / "configs" / "fixture_signals.json")
PROD = load_config(HERE / "configs" / "production_equivalent.json")
EMB, OVL, AC = FixtureEmbedder(), FixtureOverlapDetector(), FixtureAcousticSource()
COND = ConditionEstimator(FIX["condition"])
USER, ATTACKER = 120, 220  # toy victim/user (male-ish) and attacker (female-ish) fundamentals
enrol = [EMB.embed(voice(USER, 0.6, 0.25), SR)]
VER = TargetSpeakerVerifier(EMB, enrol, FIX["target_speaker"])

# --- evidence ------------------------------------------------------------------------------------------
check("evidence: unknown state rejected", raises(lambda: Evidence("overlap", "maybe", "x", "r"), ValueError))
check("evidence: measured state needs a source", raises(lambda: Evidence("overlap", POSITIVE, "", "r"), ValueError))
check("evidence: uncertain/unavailable are not informative",
      not Evidence("overlap", UNCERTAIN, "x", "r").informative and Evidence("overlap", NEGATIVE, "x", "r").informative)

# --- single speaker / attacker-victim / target speaker ---------------------------------------------------------
A, B = voice(USER), voice(ATTACKER)
check("single speaker, enrolled user: target POSITIVE", VER.identify(A, SR, OVL.detect(A, SR)).state == POSITIVE)
check("attacker voice: target NEGATIVE (not the user)", VER.identify(B, SR, OVL.detect(B, SR)).state == NEGATIVE)
check("no embedder: UNAVAILABLE (not negative)", TargetSpeakerVerifier(None, enrol, FIX["target_speaker"]).identify(A, SR).state == UNAVAILABLE)
check("no enrollment: UNAVAILABLE (not negative)", TargetSpeakerVerifier(EMB, [], FIX["target_speaker"]).identify(A, SR).state == UNAVAILABLE)
check("too short: UNCERTAIN", VER.identify(voice(USER, 0.1), SR).state == UNCERTAIN)
check("thresholds are configuration: reject must be below accept",
      raises(lambda: TargetSpeakerVerifier(EMB, enrol, {"accept": 0.3, "reject": 0.8, "min_duration_s": 0.1}), ValueError))
scene = [(voice(ATTACKER), SR, 0.0, 0.5, None), (voice(USER), SR, 0.6, 1.1, None), (voice(ATTACKER, 0.5, 0.2), SR, 1.2, 1.7, None),
         (voice(USER, 0.5, 0.35), SR, 1.8, 2.3, None)]
att = SpeakerAttributor(EMB, FIX["attribution"]).attribute(scene)
check("attacker/victim scene: two distinct labels, consistent per speaker",
      [e.detail["label"] for e in att] == ["spk1", "spk2", "spk1", "spk2"], [e.detail["label"] for e in att])
check("no embedder: every segment UNAVAILABLE", all(e.state == UNAVAILABLE for e in SpeakerAttributor(None, FIX["attribution"]).attribute(scene)))

# --- overlap (simultaneous male + female) -------------------------------------------------------------------
for db in (0, -6, -12):
    x = mix(voice(USER), scale_db(voice(ATTACKER), db))
    o = OVL.detect(x, SR)
    check(f"simultaneous male+female at {db} dB: overlap POSITIVE, 2 voices, level ~{db} dB",
          o.state == POSITIVE and o.detail["n_speakers"] == 2 and abs(o.detail["rel_db"] - db) < 1, o.detail)
    check(f"overlapped {db} dB: target speaker UNCERTAIN (one embedding over two voices is not attribution)",
          VER.identify(x, SR, o).state == UNCERTAIN)
ov_seg = mix(voice(USER), voice(ATTACKER))
att_ov = SpeakerAttributor(EMB, FIX["attribution"]).attribute([(voice(USER), SR, 0, .5, None), (ov_seg, SR, .5, 1, OVL.detect(ov_seg, SR))])
check("overlapped segment gets NO single speaker label (never merged)", att_ov[1].state == UNCERTAIN and att_ov[1].detail["label"] is None)
check("overlap from annotation is evaluation-only ground truth", from_annotation(True, -6).source == "annotation"
      and from_annotation(None).state == UNAVAILABLE)
check("silence: overlap UNAVAILABLE", OVL.detect(silence(), SR).state == UNAVAILABLE)
check("scream (non-voice sound): overlap UNCERTAIN, not a speaker count", OVL.detect(scream(), SR).state == UNCERTAIN)

# --- robustness conditions -------------------------------------------------------------------------------
conds = {"clean": voice(USER), "pocket": pocket(voice(USER)), "far_field": far_field(voice(USER)), "traffic": mix(voice(USER), traffic()),
         "crowd": mix(voice(USER), crowd()), "clipped": clip(voice(USER))}
flags = {k: COND.estimate(x, SR).detail["flags"] for k, x in conds.items()}
check("condition flags: clean none, pocket muffled, far-field quiet, traffic/crowd low SNR, clipping",
      flags == {"clean": [], "pocket": ["muffled"], "far_field": ["quiet"], "traffic": ["low_snr"], "crowd": ["low_snr"], "clipped": ["clipping"]}, flags)
check("condition: too short -> UNAVAILABLE", COND.estimate(voice(USER, 0.05), SR).state == UNAVAILABLE)
check("condition config has no defaults", raises(lambda: ConditionEstimator({"quiet_dbfs": -26}), ValueError))
for k in ("pocket", "far_field", "traffic"):
    check(f"target user still identified under {k} (toy)", VER.identify(conds[k], SR, OVL.detect(conds[k], SR)).state == POSITIVE)

# --- acoustic distress ------------------------------------------------------------------------------------
check("scream: acoustic POSITIVE", AC.assess(scream(), SR)[0].state == POSITIVE)
check("crying: acoustic POSITIVE", AC.assess(cry(), SR)[0].state == POSITIVE)
check("ordinary loud speech: acoustic NEGATIVE (fixture), not distress", AC.assess(voice(USER, 0.5, 0.95), SR)[0].state == NEGATIVE)
check("silence: acoustic UNAVAILABLE", AC.assess(silence(), SR)[0].state == UNAVAILABLE)
b0 = BeatsScreamSignal(None).assess(b"\x00\x00" * 16000, True)
check("live BEATs wrapper without a loaded detector: UNAVAILABLE", all(e.state == UNAVAILABLE for e in b0))
try:
    import numpy as np
except ImportError:
    np = None
if np is None:
    for n in ("BEATs fired -> POSITIVE (unverified)", "BEATs not fired -> UNCERTAIN, never NEGATIVE", "outside VAD -> UNAVAILABLE"):
        skip(n, "numpy not installed here")
else:
    class FakeBeats:
        def __init__(self, p4, p9):
            self.p4, self.p9 = p4, p9

        def label_probs(self, pcm, sample_rate=16000):
            v = np.zeros(527)
            v[34] = self.p4
            return v

        def score(self, pcm, sample_rate=16000):
            return self.p9
    pcm = b"\x00\x00" * 48000
    fired = BeatsScreamSignal(FakeBeats(0.5, 0.4)).assess(pcm, True)
    check("BEATs 4-class fired -> POSITIVE, marked unverified with known false-alarm sources",
          fired[0].state == POSITIVE and fired[0].detail["reliability"] == "unverified" and fired[0].detail["known_false_alarm_sources"])
    check("BEATs 9-class >= 0.30 -> corroboration POSITIVE", fired[1].state == POSITIVE)
    quiet = BeatsScreamSignal(FakeBeats(0.01, 0.02)).assess(pcm, True)
    check("BEATs not fired / low score -> UNCERTAIN, never NEGATIVE (misses real distress)", [e.state for e in quiet] == [UNCERTAIN, UNCERTAIN])
    check("audio outside VAD segments -> UNAVAILABLE", all(e.state == UNAVAILABLE for e in BeatsScreamSignal(FakeBeats(0.5, 0.4)).assess(pcm, False)))

# --- fusion ----------------------------------------------------------------------------------------------
sc = AC.assess(scream(), SR)
check("acoustic distress without UDK -> TRIGGER_VERIFY only (G2)", fuse("NO_ACTION", "udk_path", sc, FIX).decision == "TRIGGER_VERIFY")
check("crying without UDK -> TRIGGER_VERIFY only", fuse("NO_ACTION", "udk_path", AC.assess(cry(), SR), FIX).decision == "TRIGGER_VERIFY")
check("UDK danger with acoustic evidence absent (NEGATIVE / UNCERTAIN / UNAVAILABLE) stays TRIGGER_ALL (G1)",
      all(fuse("TRIGGER_ALL", "udk_path", [Evidence("acoustic_distress", s, "x", "r") if s != UNAVAILABLE else
                                           Evidence("acoustic_distress", s, "", "r")], FIX).decision == "TRIGGER_ALL"
          for s in (NEGATIVE, UNCERTAIN, UNAVAILABLE)))
check("UDK TRIGGER_VERIFY + acoustic distress -> TRIGGER_ALL (UDK-path corroboration, G3)",
      fuse("TRIGGER_VERIFY", "udk_path", sc, FIX).decision == "TRIGGER_ALL")
check("classifier-only VERIFY + acoustic distress stays VERIFY (G3)", fuse("TRIGGER_VERIFY", "context_intent", sc, FIX).decision == "TRIGGER_VERIFY")
not_user = VER.identify(B, SR, OVL.detect(B, SR))
check("UDK spoken by a non-user voice is never lowered (G1, product rule)", fuse("TRIGGER_ALL", "udk_path", [not_user], FIX).decision == "TRIGGER_ALL")
ordinary = AC.assess(voice(USER, 0.5, 0.95), SR)
check("ordinary loud speech, no UDK: nothing raised", fuse("NO_ACTION", "udk_path", ordinary, FIX).decision == "NO_ACTION")
deg = [COND.estimate(conds["pocket"], SR), VER.identify(pocket(B), SR, OVL.detect(pocket(B), SR))]
fz = fuse("TRIGGER_ALL", "udk_path", deg, FIX)
check("degraded (pocket) audio: NEGATIVE target evidence reported as UNCERTAIN (G5)",
      [e["state"] for e in fz.evidence if e["kind"] == "target_speaker"] == [UNCERTAIN])
ovx = mix(voice(USER), scale_db(voice(ATTACKER), -12))
fo = fuse("NO_ACTION", "udk_path", [OVL.detect(ovx, SR)], FIX)
check("overlap with no alert: annotation only, no alert (G6)", fo.decision == "NO_ACTION" and any("masked" in r for r in fo.reasons))
check("unavailable evidence has no effect and is reported (G4)",
      any("no effect" in r for r in fuse("NO_ACTION", "udk_path", [TargetSpeakerVerifier(None, [], FIX["target_speaker"]).identify(A, SR)], FIX).reasons))
check("acoustic-only TRIGGER_ALL cannot be configured", raises(lambda: load_config({**FIX, "acoustic_alone": {**FIX["acoustic_alone"],
                                                                                   "allow_acoustic_trigger_all": True}}), SignalConfigError))
check("config has no defaults", raises(lambda: load_config({k: v for k, v in FIX.items() if k != "condition"}), SignalConfigError))
check("fixture acoustic source is ignored by the production-equivalent config", fuse("NO_ACTION", "udk_path", sc, PROD).decision == "NO_ACTION")
live_trig = Evidence("acoustic_distress", POSITIVE, "beats_4class_scream_trigger", "fired")
live_corr = Evidence("acoustic_distress", POSITIVE, "beats_9class_corroboration", ">= 0.30")
check("production-equivalent mirrors live: scream-alone VERIFY, 9-class corroboration lifts a UDK alert",
      fuse("NO_ACTION", "udk_path", [live_trig], PROD).decision == "TRIGGER_VERIFY"
      and fuse("TRIGGER_VERIFY", "udk_path", [live_corr], PROD).decision == "TRIGGER_ALL"
      and fuse("NO_ACTION", "udk_path", [live_corr], PROD).decision == "NO_ACTION")

# hand-off from the Phase 3 layer (FinalDecision.decision / .source)
from udk_context.context_window import build_window
from udk_context.decision import ContextConfig, UdkEvidence, decide
from udk_context.scene import load_scenes
s3 = {s.scene_id: s for s in load_scenes(HERE.parent / "udk_context" / "fixtures" / "scenes_toy.jsonl")}["a01_danger_attacker_victim"]
p3 = decide(UdkEvidence("TRIGGER_ALL", "UDK_08", "GENERAL", "Help me, please", "exact", 1.0, True, s3.target.text),
            build_window(s3, 20, 6), ContextConfig.load(HERE.parent / "udk_context" / "configs" / "production_equivalent.json"))
check("Phase 3 decision + missing acoustic/speaker evidence -> unchanged TRIGGER_ALL",
      fuse(p3.decision, p3.source, BeatsScreamSignal(None).assess(None, True), PROD).decision == "TRIGGER_ALL")

# --- toy evaluation --------------------------------------------------------------------------------------------
ts_items = []
for cname, fn in (("clean", lambda x: x), ("pocket", pocket), ("far_field", far_field), ("traffic", lambda x: mix(x, traffic())),
                  ("crowd", lambda x: mix(x, crowd()))):
    for f0, is_user in ((USER, True), (ATTACKER, False), (150, False)):
        x = fn(voice(f0))
        ts_items.append((VER.identify(x, SR, OVL.detect(x, SR)), is_user, cname))
    x = fn(mix(voice(USER), voice(ATTACKER)))
    ts_items.append((VER.identify(x, SR, OVL.detect(x, SR)), True, cname))
TS = target_speaker_metrics(ts_items)
check("toy target-speaker: 15/15 decided items correct, overlapped items UNCERTAIN (not scored negative)",
      TS["all"]["identification_accuracy"]["num"] == TS["all"]["identification_accuracy"]["den"] == 15 and TS["all"]["uncertain"] == 5, TS["all"])
at_items = [(e, [s], "clean") for e, s in zip(att, ["atk", "usr", "atk", "usr"])] + [(att_ov[1], ["usr", "atk"], "clean")]
AT = attribution_metrics(at_items)
check("toy attribution: 4/4 single-speaker segments correct; 0 merged overlaps", AT["all"]["attribution_accuracy"]["num"] == 4
      and AT["all"]["merged_overlap_violations"] == 0)
ov_items = [(OVL.detect(mix(voice(USER), scale_db(voice(ATTACKER), db)), SR), True, f"{db}dB") for db in (0, -6, -12)] + \
           [(OVL.detect(voice(f), SR), False, "single") for f in (USER, ATTACKER, 150)]
OV = overlap_metrics(ov_items)
check("toy overlap: precision 3/3, recall 3/3", (OV["all"]["precision"]["num"], OV["all"]["recall"]["num"]) == (3, 3))
ac_items = [(AC.assess(scream(), SR), True, "clean", "scream"), (AC.assess(cry(), SR), True, "clean", "cry"),
            (AC.assess(voice(USER, 0.5, 0.95), SR), False, "clean", "loud_speech"), (AC.assess(voice(USER), SR), False, "clean", "speech"),
            (AC.assess(mix(voice(USER), traffic()), SR), False, "traffic", "speech+traffic")]
AM = acoustic_metrics(ac_items)["all"]["fixture-acoustic (TEST ONLY)"]
check("toy acoustic: distress recall 2/2, hard-negative false positives 0/3",
      (AM["distress_recall"]["num"], AM["distress_recall"]["den"], AM["hard_negative_false_positive"]["num"]) == (2, 2, 0))

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "")
      + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
