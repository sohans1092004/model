"""Phase 6B shadow-mode tests. The LIVE loop under test is the real api._run_incremental_detection (and the
real _either_stt_decisions / _strongest / _intent_veto / _decision_to_event / _load_shadow), extracted from
api.py with ast and executed against deterministic stubs for VAD, STT, BEATs and the intent model (api.py
itself cannot be imported here: it loads FastAPI and models at import time). The UDK engine is the real
udk_engine.UDKEngine. Everything is synthetic: nothing here is production behaviour or performance.
Needs rapidfuzz + numpy (the production matcher stack).

    python udk_shadow/test_shadow.py
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import sys
import tempfile
import time
import types
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from intent_gate import IntentGate
from udk_engine import TRIGGER_VERIFY_THRESHOLD, DecisionEvent, UDKEngine, match_transcript
from udks import GENERAL_UDKS, UDK
from udk_shadow import report
from udk_shadow.config import ShadowConfig, ShadowConfigError, runtime_snapshot
from udk_shadow.processor import IsolatedSemantic
from udk_shadow.runner import ShadowRunner, load

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


# ------------------------------------------------------------------ stubs for the live loop
@dataclass
class Seg:
    start_ms: int
    end_ms: int
    pcm: bytes


@dataclass
class Tx:
    text: str
    avg_logprob: float | None = -0.2
    temperature: float | None = 0.0


class Script:
    """Per-segment scripted inputs keyed by the segment's (fake) pcm label. Never real audio."""
    def __init__(self):
        self.primary, self.second, self.scream, self.score9, self.p = {}, {}, {}, {}, {}


class FakeVAD:
    def __init__(self, segs):
        self.segs = segs

    def segment_speech(self, pcm):
        return list(self.segs)

    def total_ms(self, pcm):
        return 10 ** 9


class FakeSTT:
    model_version = "fake-stt"

    def __init__(self, table):
        self.table = table

    def transcribe(self, pcm):
        return Tx(self.table.get(pcm, ""))


class FakeDetector:
    model_version = "fake-beats"

    def __init__(self, script):
        self.s = script

    def score(self, pcm):
        return self.s.score9.get(pcm, 0.01)


class FakeGate(IntentGate):
    """Real IntentGate.veto logic (heard_by_both, GENERAL text layers, threshold); scripted p_distress."""
    def __init__(self, script, threshold=0.02):
        self.s, self.threshold = script, threshold

    def p_distress(self, text):
        return self.s.p.get(text, 0.9)


@dataclass
class Journey:
    journey_id: str
    engine: UDKEngine
    stt: object
    vad: FakeVAD
    user_id: str = "U1"
    started_at: float = 1_000.0
    audio_buffer: bytearray = field(default_factory=lambda: bytearray(b"x"))
    processed_up_to_ms: int = 0
    kws: object = None
    events: list = field(default_factory=list)
    language: str | None = None


class FakeClock:
    """Deterministic stand-in for the `time` module inside the live loop (monotonic advances `step` s per call:
    20 s by default so separate segments fall outside the 15 s repetition window unless a test wants them in),
    so two runs of the same journey are comparable field for field."""
    def __init__(self, step=20.0):
        self.t, self.step = 100.0, step

    def monotonic(self):
        self.t += self.step
        return self.t

    def time(self):
        return 2_000_000.0


API_SRC = (ROOT / "api.py").read_text()
WANT = {"_run_incremental_detection", "_either_stt_decisions", "_strongest", "_intent_veto", "_decision_to_event", "_load_shadow"}


def live_module(script, *, trigger=True, corroboration=True, gate=True, parakeet=True, shadow=None, clock_step=20.0):
    ns = types.ModuleType("fake_api")
    stt, second = FakeSTT(script.primary), FakeSTT(script.second)
    det = FakeDetector(script)

    def check_scream(detector, pcm):
        fired, peak, cls = script.scream.get(pcm, (False, 0.02, "Screaming"))
        return fired, peak, cls

    ns.__dict__.update({
        "DecisionEvent": DecisionEvent, "UDKEngine": UDKEngine, "match_transcript": match_transcript,
        "TRIGGER_VERIFY_THRESHOLD": TRIGGER_VERIFY_THRESHOLD, "time": FakeClock(clock_step), "hashlib": hashlib, "replace": __import__("dataclasses").replace,
        "PROCESSING_VERSION": "test", "os": os,
        "_maybe_update_language": lambda j: None, "_stt_backend": stt, "_parakeet_stt": second if parakeet else None,
        "_scream_trigger_enabled": trigger, "_scream_detector": det if (trigger or corroboration) else None,
        "scream_trigger": types.SimpleNamespace(check=check_scream), "_scream_corroboration_enabled": corroboration,
        "_stt_confidence_gate_enabled": False, "is_suspect": lambda t: False, "_dual_asr_guard": None,
        "_intent_gate": FakeGate(script) if gate else None, "_separator": None, "_shadow": shadow,
        "_DECISION_RANK": {"NO_ACTION": 0, "TRIGGER_VERIFY": 1, "TRIGGER_ALL": 2},
        "_metrics": types.SimpleNamespace(detection=lambda *a: None, stt_latency=lambda *a: None),
    })
    for node in ast.parse(API_SRC).body:
        if isinstance(node, ast.FunctionDef) and node.name in WANT:
            exec(compile(ast.Module([node], []), "api.py", "exec"), ns.__dict__)

    def emit(journey, decision, seg):  # the live _emit_event minus DB / queue / delivery
        e = ns._decision_to_event(journey, decision, seg)
        journey.events.append(e)
        return e
    ns._emit_event = emit
    return ns, stt


def new_journey(ns, stt, segs, personal=None, jid="J1"):
    udks = list(GENERAL_UDKS) + ([UDK("PUDK_U1", personal, "PERSONAL")] if personal else [])
    return Journey(jid, UDKEngine(udks), stt, FakeVAD(segs))


def strip(events):
    return [{k: v for k, v in e.items() if k != "server_received_ts"} for e in events]


def run_live(script, segs, shadow_factory=None, personal=None, **flags):
    """Run the real live loop; returns (events, engine snapshot, journey events, runner or shadow object)."""
    ns, stt = live_module(script, **flags)
    shadow = shadow_factory(ns) if shadow_factory else None
    ns._shadow = shadow
    j = new_journey(ns, stt, segs, personal)
    events = ns._run_incremental_detection(j, final=True)
    if isinstance(shadow, ShadowRunner):
        shadow.drain()
    return strip(events), j.engine.snapshot(), strip(j.events), j.processed_up_to_ms, shadow, ns


def cfg(**kw):
    base = dict(enabled=True)
    base.update(kw)
    return ShadowConfig(**base)


def sync_runner(**kw):
    stages = kw.pop("stages", None)
    started = kw.pop("process_started_at", None)
    return lambda ns: ShadowRunner(cfg(**kw), ns, ns._either_stt_decisions, ns._intent_gate, runtime_snapshot({}, {"test": True}),
                                   synchronous=True, stages=stages, process_started_at=started)


def async_runner(**kw):
    stages = kw.pop("stages", None)
    return lambda ns: ShadowRunner(cfg(**kw), ns, ns._either_stt_decisions, ns._intent_gate, runtime_snapshot({}, {}),
                                   synchronous=False, stages=stages)


# ------------------------------------------------------------------ scenarios
def scenario(name):
    s = Script()
    segs = []
    if name == "mixed":
        rows = [(b"s1", "Let go of me! Please don't hurt me!", "Let go of me! Please don't hurt me!", None, 0.05),
                (b"s2", "", "", (True, 0.4, "Screaming"), 0.5),           # scream-only
                (b"s3", "", "", None, None),                             # no text, no scream -> live skip
                (b"s4", "I don't feel safe here", "I don't feel safe here", None, 0.9),  # verify-by-default + corroboration
                (b"s5", "help me please", "help me please", None, 0.01),  # vetoed by the (scripted) intent model
                (b"s6", "nice weather today", "nice weather today", None, 0.01)]
        s.p["help me please"] = 0.001
    elif name == "stt_flip":
        rows = [(b"f1", "I don't feel safe here", "I need help right now", None, 0.9)]
    elif name == "repeat":
        rows = [(b"r1", "I don't feel safe here", "", None, 0.01), (b"r2", "I don't feel safe here", "", None, 0.01)]
    elif name == "personal":
        rows = [(b"p1", "blue umbrella", "blue umbrella", None, 0.9)]
    for i, (pcm, a, b, scr, s9) in enumerate(rows):
        segs.append(Seg(i * 3000, i * 3000 + 2000, pcm))
        s.primary[pcm], s.second[pcm] = a, b
        if scr:
            s.scream[pcm] = scr
        if s9 is not None:
            s.score9[pcm] = s9
    return s, segs


print("-- live-path isolation (real api._run_incremental_detection)")


class Exploding:
    def observe(self, *a, **k):
        raise RuntimeError("shadow bug")


def boom(*a, **k):
    raise RuntimeError("injected")


for name, kw in (("mixed", {}), ("stt_flip", {}), ("repeat", {"clock_step": 1.0}), ("personal", {"personal": "blue umbrella"})):
    s, segs = scenario(name)
    base = run_live(s, segs, None, **kw)
    variants = {
        "sync shadow": run_live(s, segs, sync_runner(), **kw),
        "async shadow": run_live(s, segs, async_runner(), **kw),
        "observe() raises": run_live(s, segs, lambda ns: Exploding(), **kw),
        "every shadow stage raises": run_live(s, segs, sync_runner(stages={"replay": boom, "phase3": boom, "phase4": boom, "phase5": boom}), **kw),
        "queue of 1, slow worker": run_live(s, segs, async_runner(queue_max=1, stages={"phase4": lambda o: (time.sleep(0.05), [])[1]}), **kw),
    }
    for vname, v in variants.items():
        check(f"[{name}] {vname}: live events, engine window, journey events and progress identical to shadow OFF",
              v[:4] == base[:4], (v[0], base[0]))

s, segs = scenario("mixed")
base = run_live(s, segs)
check("live path under test really alerts: scream-only VERIFY, corroborated ALL, vetoed alert absent",
      [(e["decision"], e["udk_id"], e["layer"]) for e in base[0] if e["audio_segment_id"].endswith("3000-5000")] == [("TRIGGER_VERIFY", None, "acoustic_scream")]
      and any(e["decision"] == "TRIGGER_ALL" and e["udk_id"] == "UDK_14" for e in base[0])
      and not any(e["udk_id"] == "UDK_08" for e in base[0]), base[0])

print("-- shadow records")
_, _, _, _, R, _ = run_live(s, segs, sync_runner())
recs = {r["segment_id"].split(":")[1]: r for r in R.records}
check("one record per finalized segment (6), schema/version present",
      len(R.records) == 6 and all(r["schema"] == "udk_shadow.record/1" for r in R.records))
r1 = recs["0-2000"]
check("multiple UDK events in one segment: replay has >= 2 events, Phase 5 has one decision per event",
      len(r1["replay"]["events"]) >= 2 and len(r1["phase5_events"]) == len(r1["replay"]["events"]), r1.get("replay"))
check("multiple events: shadow Phase 5 == live (production-equivalent policy)", r1["shadow_phase5_decision"] == r1["live"]["live_decision"])
r2 = recs["3000-5000"]
check("scream-only segment: live scream-alone, replay NO_ACTION, Phase 5 segment-level acoustic-alone VERIFY (R6)",
      r2["live"]["live_scream_alone"] and r2["replay"]["events"][0]["decision"] == "NO_ACTION"
      and r2["phase5_segment_acoustic_alone"]["decision"] == "TRIGGER_VERIFY" and "R6" in r2["phase5_segment_acoustic_alone"]["rules_fired"]
      and r2["shadow_phase5_decision"] == "TRIGGER_VERIFY" and r2["shadow_phase3_decision"] == "NO_ALERT")
r3 = recs["6000-8000"]
check("no-text segment: recorded as skipped_live_no_text, no shadow decision, treatment recorded (exclude)",
      r3["status"] == "skipped_live_no_text" and r3["shadow_phase5_decision"] is None and r3["context"]["treatment"] == "exclude"
      and r3["scream_score"] is None)
r4 = recs["9000-11000"]
check("scream corroboration: live ALL; replay (scream_score=None) VERIFY; Phase 3 VERIFY; Phase 5 ALL via R5",
      r4["live"]["live_decision"] == "TRIGGER_ALL" and r4["replay"]["events"][0]["decision"] == "TRIGGER_VERIFY"
      and r4["shadow_phase3_decision"] == "TRIGGER_VERIFY" and r4["shadow_phase5_decision"] == "TRIGGER_ALL"
      and "R5" in r4["phase5_events"][0]["rules_fired"], (r4["replay"]["events"], r4["shadow_phase3_decision"]))
check("replay keeps the live window state (recording precedes corroboration)", r4["replay"]["window_state_matches_live"])
r5 = recs["12000-14000"]
check("intent veto: live NO alert; Phase 3 vetoed:sentence (live gate, heard by both); Phase 5 NO_ALERT",
      r5["live"]["live_decision"] == "NO_ALERT" and r5["phase3"][0]["source"] == "vetoed:sentence" and r5["shadow_phase5_decision"] == "NO_ALERT"
      and r5["live"]["intent_vetoed"], r5.get("phase3"))
check("veto other_text recorded exactly as live used it", r5["live"]["veto_other_text"] == "help me please" and r5["replay"]["other_text"] == "help me please")
ev_kinds = {(e["kind"], e["state"]) for e in r4["phase4_evidence"]}
check("missing speaker/overlap evidence stays UNAVAILABLE (never NEGATIVE) and carries segment_id / clock",
      {("speaker_attribution", "unavailable"), ("target_speaker", "unavailable"), ("overlap", "unavailable")} <= ev_kinds
      and all(e["detail"]["segment_id"] == r4["segment_id"] and e["detail"]["clock"] == "journey_audio_ms" for e in r4["phase4_evidence"]))
check("unavailable evidence listed as ignored with reasons in the Phase 5 provenance",
      any(i["kind"] == "overlap" and "no information" in i["why"] for i in r4["phase5_events"][0]["ignored"]))
check("context buffer: later segments see earlier turns (unattributed, attribution incomplete)",
      recs["12000-14000"]["context"]["buffered_segments"] >= 3 and recs["12000-14000"]["context"]["attribution_complete"] is False
      and all(t["speaker_id"] is None and t["relation"] == "unattributed" for t in recs["12000-14000"]["context"]["context_turns"]))
check("records carry shadow config, runtime snapshot, policy / context-config hashes and S-4 status",
      r1["shadow_config"]["enabled"] and "flags" in r1["runtime"] and r1["fusion_policy_sha256"] and r1["s4_status"] == "open")
check("no raw audio anywhere in the records (the fake pcm labels never appear)",
      not any(lab in json.dumps(r, default=str) for r in R.records for lab in ("b's1'", "b's4'", "pcm")))

# missing scream score: corroboration flag off
s2, segs2 = scenario("mixed")
_, _, _, _, R2, _ = run_live(s2, segs2, sync_runner(), corroboration=False)
r = [x for x in R2.records if x["segment_id"].endswith("9000-11000")][0]
t9 = [e for e in r["phase4_evidence"] if e["source"] == "beats_9class_corroboration"][0]
check("missing scream score: None preserved (not 0), 9-class evidence UNAVAILABLE with reason, live stays VERIFY",
      r["scream_score"] is None and t9["state"] == "unavailable" and "not enabled" in t9["reason"] and r["live"]["live_decision"] == "TRIGGER_VERIFY"
      and r["shadow_phase5_decision"] == "TRIGGER_VERIFY")

# STT selection flipped by the scream score (contract §3)
s3, segs3 = scenario("stt_flip")
_, _, _, _, R3, _ = run_live(s3, segs3, sync_runner())
rf = R3.records[0]
check("STT choice changed by scream: live kept Whisper (UDK_14), replay keeps Parakeet (UDK_05)",
      rf["live"]["live_chosen_stt"] == "primary" and rf["replay"]["chosen_stt"] == "second"
      and rf["replay"]["events"][0]["udk_id"] == "UDK_05", (rf["live"]["live_chosen_stt"], rf["replay"]))
check("... and the replay window state differs from live there (recorded, not hidden)", rf["replay"]["window_state_matches_live"] is False)
check("STT-flip labelled: replay.semantics says counterfactual (not live-with-BEATs-disabled); stt_choice_differs_from_live True",
      rf["replay"]["semantics"].startswith("counterfactual_linguistic_replay") and "NOT a reconstruction" in rf["replay"]["semantics"]
      and rf["replay"]["stt_choice_differs_from_live"] is True and R.records and True)
check("records carry EFFECTIVE settings: shadow mode, both scream flags (env + effective), sentence veto (live/shadow/Phase 5 guard), S-4",
      {"UDK_SHADOW_MODE", "UDK_ENABLE_SCREAM_TRIGGER", "UDK_ENABLE_SCREAM_DETECTION", "sentence_veto", "s4_status"} <= set(rf["effective"])
      and rf["effective"]["sentence_veto"]["phase5_sentence_veto_guard"] is False and rf["effective"]["s4_status"] == "open"
      and rf["effective"]["UDK_ENABLE_SCREAM_TRIGGER"]["effective"] is True
      and set(rf["effective"]["UDK_DEVICE"]) == {"env", "live_resolved"})
check("records carry queue wait time", isinstance(rf["runner"]["queue_wait_s"], float))

# repetition from the live pre_state
s4, segs4 = scenario("repeat")
_, _, _, _, R4, _ = run_live(s4, segs4, sync_runner(), parakeet=False, clock_step=1.0)
check("repetition window reproduced from live pre_state: second segment ALL 'repeated' in live and replay",
      R4.records[1]["live"]["live_decision"] == "TRIGGER_ALL" and R4.records[1]["replay"]["events"][0]["repeated"] is True)
check("no second STT: heard_by_both None (veto cannot run), not False/True",
      R4.records[0]["phase3"][0]["udk_evidence"]["heard_by_both"] is None and R4.records[0]["replay"]["other_text"] is None)

# personal UDK
s5, segs5 = scenario("personal")
_, _, _, _, R5, _ = run_live(s5, segs5, sync_runner(), personal="blue umbrella")
p = R5.records[0]
check("custom UDK flows through as PERSONAL; never vetoed (Phase 3 H1); shadow == live",
      p["phase3"][0]["udk_evidence"]["udk_type"] == "PERSONAL" and p["phase3"][0]["source"] == "udk_path"
      and p["shadow_phase5_decision"] == p["live"]["live_decision"], p.get("phase3"))

print("-- failure isolation inside shadow")
def only(stage, fn):
    s, segs = scenario("mixed")
    _, _, _, _, R, _ = run_live(s, segs, sync_runner(stages={stage: fn}))
    return [r for r in R.records if r["status"] != "skipped_live_no_text"]

rr = only("replay", boom)
check("replay throws: every processed record 'failed' with stage=replay, no shadow decision",
      all(r["status"] == "failed" and r["errors"][0]["stage"] == "replay" and r["shadow_phase5_decision"] is None for r in rr))
rr = only("phase3", boom)
check("Phase 3 throws: 'partial', Phase 3 and Phase 5 decisions None, Phase 4 evidence still recorded",
      all(r["status"] == "partial" and r["shadow_phase3_decision"] is None and r["shadow_phase5_decision"] is None and r["phase4_evidence"] for r in rr))
rr = only("phase4", boom)
check("Phase 4 throws: 'partial', Phase 5 still runs with NO signals (missing never negative); linguistic kept",
      all(r["status"] == "partial" and r["phase4_evidence"] == [] and r["shadow_phase5_decision"] is not None for r in rr)
      and [r for r in rr if r["segment_id"].endswith("9000-11000")][0]["shadow_phase5_decision"] == "TRIGGER_VERIFY")
rr = only("phase5", boom)
check("Phase 5 throws: 'partial', Phase 3 decision kept, Phase 5 None", all(r["status"] == "partial" and r["shadow_phase3_decision"] is not None
                                                                         and r["shadow_phase5_decision"] is None for r in rr))
rr = only("phase4", lambda obs: ["junk", {"kind": "overlap"}])
check("malformed evidence: dropped and recorded (phase4_validation), never read as negative; Phase 5 still decides",
      all(r["status"] == "partial" and any(e["stage"] == "phase4_validation" for e in r["errors"]) and r["shadow_phase5_decision"] is not None
          for r in rr) and all(e.get("malformed") for e in rr[0]["phase4_evidence"]))

# capture failure: a live frame missing expected names
R6 = sync_runner()(live_module(Script())[0])
j = new_journey(*live_module(Script()), [])
R6.observe(j, Seg(0, 10, b"z"), {"transcript": Tx("help")}, skipped=False, n_alerts=0, new_events=[])
check("capture error (malformed live locals) is swallowed and counted", R6.stats["capture_errors"] == 1 and not R6.records)

print("-- restart / bounds / sink / config")
s, segs = scenario("mixed")
_, _, _, _, R7, _ = run_live(s, segs, sync_runner(process_started_at=5_000.0))  # journey started_at=1000 < process start
first = R7.records[0]["context"]
check("server restart / empty shadow state: first segment cold_start, possible_restart flagged, no context invented",
      first["cold_start"] and first["possible_restart"] and first["buffered_segments"] == 0 and first["context_turns"] == [])
_, _, _, _, R8, _ = run_live(s, segs, sync_runner(no_text_turns="include_empty"))
r = [x for x in R8.records if x["segment_id"].endswith("9000-11000")][0]
check("no-text treatment configurable: include_empty keeps the skipped segment as an empty context turn",
      any(t["segment_id"].endswith("6000-8000") and t["text"] == "" for t in r["context"]["context_turns"]))
r = [x for x in R.records if x["segment_id"].endswith("9000-11000")][0]
check("... default exclude does not", not any(t["segment_id"].endswith("6000-8000") for t in r["context"]["context_turns"]))
_, _, _, _, R9, _ = run_live(s, segs, sync_runner(records_max=2))
check("records bounded: records_max=2 keeps 2, evictions counted", len(R9.records) == 2 and R9.stats["evicted_records"] == 4)
_, _, _, _, R10, _ = run_live(s, segs, async_runner(queue_max=1, stages={"phase4": lambda o: (time.sleep(0.05), [])[1]}))
check("queue bounded: full queue drops NEW observations and counts them (live never waits)",
      R10.stats["dropped_queue_full"] >= 1 and R10.stats["observed"] == 6)
from udk_shadow.context import ContextBuffer
cb = ContextBuffer(2, 3, 20.0, 6, 0.0)
for jid in ("a", "b", "c"):
    cb.append(types.SimpleNamespace(journey_id=jid, segment_id=f"{jid}:0-1", start_ms=0, end_ms=1000, journey_started_at=1.0), "x")
check("journey buffers bounded (LRU): 3 journeys with max 2 -> 1 eviction; evicted journey returns as cold 'evicted_from_buffer'",
      cb.evictions == 1 and cb.window_for(types.SimpleNamespace(journey_id="a", segment_id="a:2-3", start_ms=2000, end_ms=3000,
                                                                 journey_started_at=1.0), "y")[1]["cold_reason"] == "evicted_from_buffer")
with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, "shadow.jsonl")
    _, _, _, _, R11, _ = run_live(s, segs, sync_runner(log_path=path, log_max_bytes=6000))
    body = open(path).read() + (open(path + ".1").read() if os.path.exists(path + ".1") else "")
    check("JSONL sink redacts transcripts by default (no plaintext phrase on disk)",
          "Let go of me" not in body and "sha256" in body)
    check("sink size-capped: rotation to .1 happened and the live file stays under the cap",
          R11.sink.rotations >= 1 and os.path.getsize(path) <= 6000 + 20000)
check("config: OFF by default (no env) -> load() returns None", load(None, None, None, {}, env={}) is None)
try:
    ShadowConfig.from_env({"UDK_SHADOW_MODE": "1", "UDK_SHADOW_SAMPLE_RATE": "2"})
    bad = False
except ShadowConfigError:
    bad = True
check("config: sample rate outside [0,1] refused", bad)
check("config: invalid env with shadow requested -> load() returns None (service unaffected)",
      load(None, None, None, {}, env={"UDK_SHADOW_MODE": "1", "UDK_SHADOW_QUEUE_MAX": "0"}) is None)
snap = runtime_snapshot({"UDK_ENABLE_SCREAM_TRIGGER": "1"}, {"x": 1})
check("runtime snapshot records the ACTUAL flags (unset -> None, never a guessed default)",
      snap["flags"]["UDK_ENABLE_SCREAM_TRIGGER"] == "1" and snap["flags"]["UDK_ENABLE_SEPARATION"] is None)
ns_off, _ = live_module(Script())
check("api._load_shadow: OFF without UDK_SHADOW_MODE -> None, nothing imported", ns_off._load_shadow() is None)
_, _, _, _, R12, _ = run_live(s, segs, sync_runner(sample_rate=0.0))
check("sampling 0.0: records 'not_sampled' (context still updated), no shadow decisions",
      all(r["status"] in ("not_sampled", "skipped_live_no_text") for r in R12.records)
      and R12.records[-1]["context"]["buffered_segments"] >= 3)

print("-- Phase 4 evidence equivalence (BEATs values reused, not re-run)")
import numpy as np
import scream_trigger
from udk_shadow import evidence as shadow_ev
from udk_signals.acoustic import BeatsScreamSignal


class ProbDetector:
    model_version = "fake"

    def __init__(self, p4, p9):
        self.p4, self.p9 = p4, p9

    def label_probs(self, pcm, sample_rate=16000):
        v = np.zeros(527, dtype=np.float32)
        v[34] = self.p4
        return v

    def score(self, pcm, sample_rate=16000):
        return self.p9


pcm = b"\x00\x00" * 16000 * 3
for p4, p9 in ((0.5, 0.5), (0.05, 0.1), (0.2, 0.29)):
    d = ProbDetector(p4, p9)
    ref = {(e.source, e.state, round(e.score, 6)) for e in BeatsScreamSignal(d).assess(pcm, True)}
    fired, peak, cls = scream_trigger.check(d, pcm)
    o = types.SimpleNamespace(segment_id="J:0-3000", start_ms=0, end_ms=3000,
                              acoustic={"detector_loaded": True, "trigger_ran": True, "corroboration_enabled": True,
                                        "scream_fired": fired, "scream_peak": peak, "scream_class": cls, "scream_score": d.score(pcm)})
    got = {(e.source, e.state, round(e.score, 6)) for e in shadow_ev.build(o) if e.kind == "acoustic_distress"}
    check(f"shadow BEATs evidence == Phase 4 BeatsScreamSignal (p4={p4}, p9={p9})", got == ref, (got, ref))

print("-- start-up self-check (fail closed)")
from udk_shadow import selfcheck
ns_sc, _ = live_module(Script())
chk = selfcheck.run(ns_sc, ns_sc._either_stt_decisions)
check("self-check passes through every stage on the real engine", chk["ok"] and chk["phase5"] == "TRIGGER_ALL", chk)
env_on = {"UDK_SHADOW_MODE": "1"}
check("load(): shadow ON + self-check ok -> runner", isinstance(load(ns_sc, ns_sc._either_stt_decisions, None, {}, env=env_on), ShadowRunner))
import udk_shadow.selfcheck as _sc
_orig = _sc.run
_sc.run = lambda *a: {"ok": False, "status": "failed", "errors": [{"stage": "phase5", "type": "ImportError"}]}
check("load(): self-check failing (e.g. a module missing from the image) -> None (shadow OFF, fail closed)",
      load(ns_sc, ns_sc._either_stt_decisions, None, {}, env=env_on) is None)
_sc.run = _orig

print("-- semantic isolation")
import functools


class LiveMatcherLike:
    threshold, fuzzy_threshold = 0.65, 0.5

    def __init__(self):
        self._encode = functools.lru_cache(maxsize=512)(lambda t: len(t))


lm = LiveMatcherLike()
view = IsolatedSemantic(lm)
view._encode("help me please")
check("isolated semantic view never touches the live encode cache", lm._encode.cache_info().currsize == 0 and view._encode.cache_info().currsize == 1)
try:
    IsolatedSemantic(types.SimpleNamespace(threshold=0.6, fuzzy_threshold=0.5, _encode=lambda t: t))
    ok = False
except TypeError:
    ok = True
check("a matcher without an uncached encoder is refused (replay then fails, recorded) rather than touching live state", ok)

print("-- comparison report (synthetic, operational only)")
rep = report.compare(list(R.records) + list(R3.records), dict(R.stats))
check("report banner says not a performance measurement", "NOT a performance measurement" in rep["banner"])
check("report labels the replay as counterfactual and counts STT-choice flips", "COUNTERFACTUAL" in rep["replay_semantics"]
      and rep["stt_choice_differs_from_live"] == 1)
check("report counts statuses incl. skipped/no-data", rep["status_counts"].get("skipped_live_no_text") == 1 and rep["no_data"])
check("report: live vs Phase 5 on the synthetic 'mixed' journey all match; STT-flip segment shows a UDK-set difference",
      rep["live_vs_phase5"].get("match") == 6 and rep["udk_set_differences"] >= 1, rep["live_vs_phase5"])
check("report attributes the STT-flip difference to the scream (stt_selection_changed_by_scream, scream_correlated)",
      rep["difference_causes"].get("stt_selection_changed_by_scream") == 1 and rep["difference_causes"].get("scream_correlated", 0) >= 1,
      rep["difference_causes"])
check("report: live vs Phase 3 shows Phase 3 lower where only the scream lifted live (s4)", rep["live_vs_phase3"].get("shadow_lower", 0) >= 1)
fail_rep = report.compare(only("replay", boom))
check("report counts failed shadows by stage", fail_rep["status_counts"].get("failed") == 5 and fail_rep["failures_by_stage"].get("replay") == 5)
print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
