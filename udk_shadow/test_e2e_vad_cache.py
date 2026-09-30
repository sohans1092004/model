"""Tests for the end-to-end VAD-cache impact harness (udk_shadow/bench/e2e_vad_cache.py).

The real api module and live path run here with deterministic FAKE models (no weights on this machine): the fakes test
the harness, not detection quality. Checked: the production env is read from deploy/.env.example unmodified; the only
per-mode difference is the journey's VAD flag; the virtual clock; capture of every stage; persisted output carries no
transcript text; the comparison and its difference classification; and a real clip end to end (OFF re-processes,
ON == one-shot and == its own repeat).

    python udk_shadow/test_e2e_vad_cache.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "bench"))

import e2e_vad_cache as e2e  # noqa: E402

passed = failed = skipped = 0


def find_clip(stem: str):
    """real_recordings/mixed/<stem>.mp3 in the repo, or audio/mix_<stem>.mp3 in a Kaggle bundle part."""
    repo = ROOT / "real_recordings" / "mixed" / f"{stem}.mp3"
    if repo.exists():
        return repo
    for base in (ROOT, ROOT.parent, Path("/kaggle/input")):
        if base.exists():
            hit = next(base.rglob(f"mix_{stem}.mp3"), None)
            if hit is not None:
                return hit
    return repo


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {str(detail)[:700]}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


# ------------------------------------------------------------------------------------------------ configuration
print("-- configuration")
env_file = ROOT / "deploy" / ".env.example"
before = hashlib.sha256(env_file.read_bytes()).hexdigest()
env, notes = e2e.production_env(env_file, "cpu", None)
check("production env = the detection keys of deploy/.env.example (STT small.en, Parakeet, semantic, confidence gate, "
      "BEATs corroboration + scream trigger ON; KWS OFF; intent threshold 0.02)",
      env.get("UDK_ENABLE_STT") == "1" and env.get("UDK_STT_MODEL") == "small.en" and env.get("UDK_ENABLE_PARAKEET") == "1"
      and env.get("UDK_ENABLE_KWS") == "0" and env.get("UDK_ENABLE_SEMANTIC") == "1" and env.get("UDK_ENABLE_STT_CONFIDENCE_GATE") == "1"
      and env.get("UDK_ENABLE_SCREAM_DETECTION") == "1" and env.get("UDK_ENABLE_SCREAM_TRIGGER") == "1"
      and env.get("UDK_INTENT_THRESHOLD") == "0.02", env)
check("only the device and intent-model path are set per machine; secrets/storage keys are never taken",
      env["UDK_DEVICE"] == "cpu" and not any(k in env for k in ("UDK_SERVICE_TOKEN", "UDK_WEBHOOK_URL", "UDK_WEBHOOK_SECRET", "UDK_DATABASE_URL")))
check("no intent model -> gate left unset and recorded UNAVAILABLE (not 'negative')",
      "UDK_INTENT_GATE" not in env and "UNAVAILABLE" in notes.get("intent_gate", ""))
env2, _ = e2e.production_env(env_file, "cuda", "/models/intent")
check("with an intent model directory the gate path is set; threshold unchanged", env2["UDK_INTENT_GATE"] == "/models/intent"
      and env2["UDK_INTENT_THRESHOLD"] == "0.02" and env2["UDK_DEVICE"] == "cuda")
check("deploy/.env.example is read, never modified", hashlib.sha256(env_file.read_bytes()).hexdigest() == before)

# ------------------------------------------------------------------------------------------------ comparison logic
print("-- comparison / classification (synthetic runs)")


def seg(s, e, text="t", pk="t", alerts=(), pcm="a", primary=None, final=None):
    return {"start_ms": s, "end_ms": e, "pcm": pcm, "skipped": False, "now_s": 0, "whisper": {"text": text, "avg_logprob": -0.1,
            "temperature": 0.0, "compression_ratio": 1.0, "model": "w"}, "parakeet": pk, "kws": None, "scream_trigger": None,
            "scream_score": 0.0, "stt_suspect": False, "primary": primary or [], "pre_veto": primary or [], "final": final,
            "alerts": list(alerts), "events": [], "intent": [], "component_s": []}


def run_of(segs, events=()):
    return {"segments": segs, "events": list(events), "error": None}


A = {"decision": "TRIGGER_VERIFY", "udk_id": "UDK_08", "confidence": 1.0, "layer": "exact", "repeated": False, "reason": "x"}
ALL = dict(A, decision="TRIGGER_ALL", repeated=True, reason="repeated within window")
ev = lambda s, d="TRIGGER_VERIFY": {"segment": s, "decision": d, "udk_id": "UDK_08", "layer": "exact", "confidence": 1.0}  # noqa: E731
off = run_of([seg(0, 3000, alerts=[A]), seg(0, 3030, alerts=[ALL]), seg(9000, 12000)], [ev("0-3000"), ev("0-3030", "TRIGGER_ALL")])
on = run_of([seg(0, 3000, alerts=[A]), seg(9000, 12000)], [ev("0-3000")])
c = e2e.compare_runs(off, on, off, on, [(0, 3000), (9000, 12000)])
d = {x["kind"]: x for x in c["differences"]}
check("an OFF segment re-covering already-processed audio -> 'expected_vad_correction' with its overlap",
      d["segment_only_off"]["class"] == "expected_vad_correction" and d["segment_only_off"]["overlap_with_earlier_off_ms"] == 3000)
check("the OFF-only repeat-escalated TRIGGER_ALL is reported as repeat-induced for OFF, none for ON",
      c["repeat_induced_trigger_all_off"] == [(0, 3030, "UDK_08")] and c["repeat_induced_trigger_all_on"] == [])
check("duplicate alerts: same UDK from overlapping segments reported (OFF 1, ON 0)",
      len(c["duplicate_alerts_off"]) == 1 and c["duplicate_alerts_on"] == [])
check("events only in OFF listed; ON == one-shot boundaries", c["events_only_off"] == [("0-3030", "TRIGGER_ALL", "UDK_08", "exact")]
      and c["events_only_on"] == [] and c["on_equals_oneshot"] and not c["off_equals_oneshot"])
ev2 = lambda s, d="TRIGGER_ALL": {"segment": s, "decision": d, "udk_id": "UDK_03", "layer": "exact", "confidence": 1.0}  # noqa: E731
c8 = e2e.compare_runs(run_of([seg(19050, 23400, alerts=[A])], [ev2("19050-23400")]), run_of([seg(19050, 23430, alerts=[A])], [ev2("19050-23430")]),
                      None, None, [(19050, 23430)])
check("events are paired by utterance: the same alert on a one-frame-drifted OFF segment is NOT reported missing/new",
      c8["events_only_off"] == [] and c8["events_only_on"] == [] and len(c8["events_exact_key_only_on"]) == 1)
c9 = e2e.compare_runs(run_of([]), run_of([seg(0, 8010), seg(6510, 14520)], [ev2("0-8010"), ev2("6510-14520")]), None, None,
                      [(0, 8010), (6510, 14520)])
check("ON overlapping same-UDK alerts from the designed 8 s-cut overlap are marked designed (existing intentional behaviour)",
      c9["duplicate_alerts_on"] and all(x["designed"] for x in c9["duplicate_alerts_on"]))
def tseg(s, e, now, alerts=()):
    x = seg(s, e, alerts=alerts)
    x["now_s"] = now
    return x


o10 = run_of([tseg(0, 1590, 1023.3, [A]), tseg(0, 1620, 1023.5, [ALL]), tseg(21630, 26460, 1026.5, [ALL])],
             [ev("0-1590"), ev("0-1620", "TRIGGER_ALL"), ev("21630-26460", "TRIGGER_ALL")])
n10 = run_of([tseg(0, 1620, 1001.7, [A]), tseg(21630, 26460, 1026.5, [A])], [ev("0-1620"), ev("21630-26460")])
c10 = e2e.compare_runs(o10, n10, o10, n10, [(0, 1620), (21630, 26460)])
check("same utterance + UDK at a different tier is a TIER CHANGE (OFF ALL -> ON VERIFY), not a missing + a new alert",
      c10["tier_changes"] == [(("21630-26460", "TRIGGER_ALL", "UDK_08", "exact"), ("21630-26460", "TRIGGER_VERIFY", "UDK_08", "exact"))]
      and c10["events_only_on"] == [], c10["tier_changes"])
tm = {r["utterance"]: r for r in c10["timing"]}
check("per-utterance delay: OFF decided/alerted on the first utterance 21.6 s after ON; the later one at the same time",
      tm[(0, 1620)]["first_decision_delay_s"] == 21.6 and tm[(0, 1620)]["first_alert_delay_s"] == 21.6
      and tm[(21630, 26460)]["first_alert_delay_s"] == 0.0, tm)
# fixes found on the real-model run
o11 = run_of([tseg(0, 1590, 0, []), tseg(1050, 5880, 1006.0, [A])], [ev("1050-5880")])
n11 = run_of([tseg(0, 1620, 0, []), tseg(1620, 5880, 1006.0, [A])], [ev("1620-5880")])
t11 = {r["utterance"]: r for r in e2e.compare_runs(o11, n11, o11, n11, [(0, 1620), (1620, 5880)])["timing"]}
check("an alert is credited to the one utterance its segment overlaps MOST (mix_clip_30: no false 'alert only OFF')",
      not t11[(0, 1620)]["alert_only_off"] and not t11[(1620, 5880)]["alert_only_off"] and t11[(1620, 5880)]["first_alert_delay_s"] == 0.0, t11)
AC = dict(A, udk_id=None, layer="acoustic_scream")
evx = lambda s, d, u, l: {"segment": s, "decision": d, "udk_id": u, "layer": l, "confidence": 1.0}  # noqa: E731
o14 = run_of([tseg(26400, 30000, 1030.0, [A])], [ev("26400-30000")])
n14 = run_of([tseg(17880, 28860, 1028.9, [A]), tseg(27540, 30000, 1030.0, [A])], [ev("17880-28860"), ev("27540-30000")])
t14 = {r["utterance"]: r for r in e2e.compare_runs(o14, n14, None, None, [(17880, 28860), (27540, 30000)])["timing"]}
check("equal-overlap ties go to the closest utterance (clip_02 tail: no false 'alert only ON')",
      not t14[(27540, 30000)]["alert_only_on"], t14[(27540, 30000)])
o12 = run_of([], [evx("26940-37920", "TRIGGER_ALL", "UDK_01", "exact"), evx("36420-47400", "TRIGGER_VERIFY", None, "acoustic_scream")])
n12 = run_of([], [evx("27060-38040", "TRIGGER_VERIFY", None, "acoustic_scream"), evx("36540-47520", "TRIGGER_VERIFY", None, "acoustic_scream")])
c12 = e2e.compare_runs(o12, n12, None, None, [])
check("events pair with the LARGEST-overlap counterpart (pos_02: the two acoustic alerts pair; the UDK_01 ALL vs acoustic VERIFY "
      "on the earlier window stays visible)",
      c12["events_only_off"] == [("26940-37920", "TRIGGER_ALL", "UDK_01", "exact")]
      and c12["events_only_on"] == [("27060-38040", "TRIGGER_VERIFY", None, "acoustic_scream")], (c12["events_only_off"], c12["events_only_on"]))
o13 = run_of([seg(7980, 18960), seg(17460, 28440)])
n13 = run_of([seg(8010, 18990), seg(17490, 28470)])
k13 = {x["segment"]: x for x in e2e.compare_runs(o13, n13, None, None, [(8010, 18990), (17490, 28470)])["differences"]
       if x["kind"] == "segment_only_off"}
check("an OFF segment that only carries the DESIGNED 8 s-cut overlap is a drifted boundary, not re-processing (pos_01)",
      "drifted" in k13[(17460, 28440)]["detail"], k13[(17460, 28440)]["detail"])
c2 = e2e.compare_runs(run_of([seg(0, 3000)]), run_of([seg(0, 2970)]), None, None, [(0, 3000)])
c1 = e2e.compare_runs(run_of([seg(0, 1620), seg(6510, 10950, alerts=[A])]), run_of([seg(6510, 10980, alerts=[A])]), None, None, [(6510, 10980)])
k1 = {x["segment"]: x for x in c1["differences"] if x["kind"] == "segment_only_off"}
check("OFF-only shapes named: spurious (not speech in single pass) and drifted boundary; an alerting one needs review",
      "spurious" in k1[(0, 1620)]["detail"] and "drifted" in k1[(6510, 10950)]["detail"]
      and not k1[(0, 1620)]["needs_review"] and k1[(6510, 10950)]["needs_review"])
check("an ON segment that is NOT a one-shot segment -> 'genuine_regression' (never silently accepted)",
      any(x["kind"] == "segment_only_on" and x["class"] == "genuine_regression" for x in c2["differences"]))
o1, n1 = run_of([seg(0, 3000, text="please leave me alone")]), run_of([seg(0, 3000, text="please leave me along")])
c3 = e2e.compare_runs(o1, n1, run_of([seg(0, 3000, text="please leave me alone!")]), n1, [(0, 3000)])
x = c3["differences"][0]
check("same segment, different Whisper text, and OFF differs from its own repeat -> 'stt_nondeterminism'; text kept for review",
      x["class"] == "stt_nondeterminism" and x["text"]["off_whisper"] == "please leave me alone")
c4 = e2e.compare_runs(o1, n1, o1, n1, [(0, 3000)])
check("same segment, different STT text, both modes stable on repeat -> 'unable_to_determine' (flagged, not discarded)",
      c4["differences"][0]["class"] == "unable_to_determine")
c5 = e2e.compare_runs(run_of([seg(0, 3000, pcm="a")]), run_of([seg(0, 3000, pcm="b")]), None, None, [(0, 3000)])
check("same boundaries but different audio -> 'environment_tooling'", c5["differences"][0]["class"] == "environment_tooling")
o6 = run_of([seg(0, 3000, alerts=[A]), seg(0, 3030, alerts=[A]), seg(9000, 12000, final=ALL, alerts=[ALL])])
n6 = run_of([seg(0, 3000, alerts=[A]), seg(9000, 12000, final=A, alerts=[A])])
x6 = [y for y in e2e.compare_runs(o6, n6, o6, n6, [(0, 3000), (9000, 12000)])["differences"] if y["kind"] == "same_segment_different_output"][0]
check("identical inputs but different decision AFTER an OFF-only alerting re-process -> 'expected_vad_correction' (engine history)",
      x6["class"] == "expected_vad_correction" and set(x6["fields"]) <= {"final", "alerts"})
o7 = run_of([seg(9000, 12000, final=ALL, alerts=[ALL])])
n7 = run_of([seg(9000, 12000, final=A, alerts=[A])])
check("different decision on identical inputs with no earlier difference -> 'unable_to_determine'",
      e2e.compare_runs(o7, n7, o7, n7, [(9000, 12000)])["differences"][0]["class"] == "unable_to_determine")
run = {"segments": [seg(0, 3000, text="call the police", pk="call police")], "events": [], "error": None}
s = json.dumps(e2e.strip_text(run))
check("persisted runs carry transcript digests only (no text)", "call the police" not in s and "call police" not in s and "text_digest" in s)
check("percentiles: p50/p95/max/total", e2e.percentiles([0.001, 0.002, 0.003, 0.010]) ==
      {"n": 4, "p50_ms": 2.0, "p95_ms": 3.0, "max_ms": 10.0, "total_s": 0.016})
vc = e2e.VirtualClock()
vc.now = 1234.5
check("virtual clock: monotonic() is the audio clock; other time functions are real", vc.monotonic() == 1234.5 and vc.time() > 1e9)

# ------------------------------------------------------------------------------------------------ real api, fake models
print("-- real api live path with fake models (real clip, webrtcvad + PyAV)")
try:
    import av  # noqa: F401
    import numpy as np
    import webrtcvad
    clip = find_clip("clip_19_muffled")
    have = clip.exists()
except ImportError:
    have = False
if not have:
    skip("real-api harness checks", "needs webrtcvad + PyAV + numpy + real_recordings/mixed/clip_19_muffled.mp3")
else:
    import segmentation_integrity as si
    from intent_gate import IntentGate
    from stt import Transcript
    PHRASE = "Please leave me alone"

    def has_speech(pcm):
        v = webrtcvad.Vad(1)
        return any(v.is_speech(pcm[i:i + 960], 16000) for i in range(0, len(pcm) - 959, 960))

    class FakeWhisper:
        model_version = "fake-whisper"

        def transcribe(self, pcm):
            return Transcript(PHRASE if has_speech(pcm) else "", self.model_version, -0.2, 0.0, 1.1)

    class FakeParakeet(FakeWhisper):
        model_version = "fake-parakeet"

    class FakeBEATs:
        model_version = "fake-beats"

        def score(self, pcm):
            return 0.01

        def label_probs(self, pcm):
            return np.zeros(600, dtype=np.float32)

    gate = object.__new__(IntentGate)
    gate.threshold = 0.02
    gate.p_distress = lambda text: 0.9  # distress -> no veto

    def prepare(api):
        api._stt_backend, api._parakeet_stt, api._scream_detector, api._intent_gate = FakeWhisper(), FakeParakeet(), FakeBEATs(), gate
        api._scream_trigger_enabled = api._scream_corroboration_enabled = True

    import os
    env_off = {k: "0" for k in env if k.startswith("UDK_ENABLE_")}  # no real model loads on this machine
    h = e2e.Harness(env_off, prepare=prepare)
    api = h.api
    comp = h.components
    check("describe_components reports what ACTUALLY loaded (fakes by class name; nothing claimed that is not there)",
          comp["whisper"] == "UNAVAILABLE (FakeWhisper)" and comp["parakeet"] == "FakeParakeet" and comp["beats"] == "FakeBEATs"
          and comp["intent_gate"] == "IntentGate" and comp["kws"] == "off", comp)
    pcm = si.decode(clip)
    oneshot = [(x.start_ms, x.end_ms) for x in h.VAD().segment_speech(pcm)]
    r_off, r_on = h.run(pcm, 20, False, "t-off"), h.run(pcm, 20, True, "t-on")
    r_off2, r_on2 = h.run(pcm, 20, False, "t-off2"), h.run(pcm, 20, True, "t-on2")
    check("no run errored", not any(r["error"] for r in (r_off, r_on, r_off2, r_on2)), [r["error"] for r in (r_off, r_on)])
    check("every journey ends COMPLETE (per-frame heartbeat as the WebSocket handler sends it; no timeout skips the final flush)",
          all(r["final_status"] == "COMPLETE" for r in (r_off, r_on, r_off2, r_on2)), [r["final_status"] for r in (r_off, r_on)])
    g0, g1 = api.HEARTBEAT_GRACE_S, api.POST_TRIGGER_HEARTBEAT_GRACE_S
    try:  # control: a 0.5 s grace, far shorter than one 20 ms-chunk run
        api.HEARTBEAT_GRACE_S = api.POST_TRIGGER_HEARTBEAT_GRACE_S = 0.5
        r_hb = h.run(pcm, 20, True, "t-hb")
        h.heartbeat = False
        r_nohb = h.run(pcm, 20, True, "t-nohb")
    finally:
        h.heartbeat = True
        api.HEARTBEAT_GRACE_S, api.POST_TRIGGER_HEARTBEAT_GRACE_S = g0, g1
    check("control: with per-frame heartbeats a run far longer than the grace still ends COMPLETE and keeps its final flush",
          r_hb["final_status"] == "COMPLETE" and [(s["start_ms"], s["end_ms"]) for s in r_hb["segments"]] == oneshot,
          (r_hb["final_status"], r_hb["wall_s"]))
    check("control: WITHOUT heartbeats the same run times out, so stop_journey skips the final flush (the dry-run artefact); "
          "the harness now records the status and flags any non-COMPLETE journey as environment_tooling",
          r_nohb["final_status"].startswith("TIMED_OUT"), (r_nohb["final_status"], len(r_nohb["segments"])))
    check("the ONLY per-mode difference is the journey's VAD flag (OFF False, ON True)",
          (r_off["flag_in_journey"], r_on["flag_in_journey"]) == (False, True) and api.VAD is not None
          and not os.environ.get("UDK_VAD_CACHE"))
    check("the stubbed-in backends were really used through the live path (every processed segment has both STT outputs)",
          r_on["segments"] and all(s["whisper"]["model"] == "fake-whisper" for s in r_on["segments"])
          and any(s["parakeet"] == PHRASE for s in r_on["segments"]))
    check("capture: BEATs trigger evidence, corroboration score, decisions, intent calls and per-component timings recorded",
          all(s["scream_trigger"] is not None and s["scream_score"] == 0.01 for s in r_on["segments"] if not s["skipped"])
          and any(s["alerts"] for s in r_on["segments"]) and any(s["intent"] for s in r_on["segments"])
          and any(n.startswith("whisper.") for s in r_on["segments"] for n, _ in s["component_s"]))
    nows = [s["now_s"] for s in r_on["segments"] if s["now_s"] is not None]
    check("decisions are stamped with the virtual audio clock (monotone, within the audio duration)",
          nows == sorted(nows) and all(1000.0 < t <= 1000.0 + len(pcm) / 32000 + 1e-6 for t in nows), nows)
    c = e2e.compare_runs(r_off, r_on, r_off2, r_on2, oneshot)
    check("ON == one-shot segmentation through the real service path; OFF is not (the defect, at 20 ms chunks)",
          c["on_equals_oneshot"] and not c["off_equals_oneshot"], (c["segments_off"], c["segments_on"]))
    check("OFF re-processing is detected and classified as expected VAD correction; no unexplained difference",
          any(x["kind"] == "segment_only_off" for x in c["differences"])
          and all(x["class"] == "expected_vad_correction" for x in c["differences"]), [(x["kind"], x["class"]) for x in c["differences"]])
    check("determinism with deterministic models: OFF == OFF repeat, ON == ON repeat (segments and events)",
          all(c["determinism"].values()), c["determinism"])
    check("ON has no duplicate alerts and no repeat-induced TRIGGER_ALL", c["duplicate_alerts_on"] == [] and c["repeat_induced_trigger_all_on"] == [])
    print(f"       (fake-model run, virtual clock: OFF events {c['events_off']} / ON {c['events_on']}; "
          f"OFF repeat-induced ALL {len(c['repeat_induced_trigger_all_off'])}; OFF duplicates {len(c['duplicate_alerts_off'])})")
    c06 = find_clip("clip_06_noisy")
    if not c06.exists():
        skip("late-detection check (clip_06)", "clip not present")
    else:
        p06 = si.decode(c06)
        one06 = [(x.start_ms, x.end_ms) for x in h.VAD().segment_speech(p06)]
        a06, b06 = h.run(p06, 100, False, "t06-off"), h.run(p06, 100, True, "t06-on")
        t06 = {u["utterance"]: u for u in e2e.compare_runs(a06, b06, None, None, one06)["timing"]}
        first = t06[one06[0]]
        check("measured defect: a noisy clip's opening utterance is decided >15 s late with the cache OFF (the persistent "
              "classifier re-reads it as non-speech until later speech shifts its state); ON decides it on time",
              first["first_decision_delay_s"] is not None and first["first_decision_delay_s"] > 15, first)
    check("api.py on disk is untouched by the harness (patches are in-process only)",
          "cache_classifications" not in (ROOT / "api.py").read_text() and "VirtualClock" not in (ROOT / "api.py").read_text())

print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "") + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
