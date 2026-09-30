"""Tests for the v2 GPU-discrepancy investigation (udk_shadow/bench/e2e_investigate.py) and the Kaggle runner's credential
handling. Fake models (no weights here); the live decision path is the real api._run_incremental_detection.

  * replay == live: re-running the live segments of a streamed journey through the replay path reproduces every
    recorded stage (audio digest, transcripts, confidence flag, decisions, alerts, events)
  * v1 bug: the whole-text matcher missed a per-sentence exact UDK_01 that the live engine emits; v2 records the engine
  * the confidence gate outcome is recorded and decides the pos_02 pattern (same text: confident -> UDK_01 TRIGGER_ALL
    with BEATs corroboration, suspect -> vetoed, acoustic VERIFY only)
  * sequence replay reproduces repeat-window state (the neg_10 pattern: re-processed utterance -> TRIGGER_ALL)
  * sweep windows, redaction of credentials, no token on any command line

    python udk_shadow/test_e2e_investigate.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "bench"))
sys.path.insert(0, str(HERE / "bench" / "kaggle"))

import e2e_investigate as inv  # noqa: E402
import e2e_vad_cache as e2e  # noqa: E402
import run_e2e_kaggle as runner  # noqa: E402

passed = failed = skipped = 0


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


# ---------------------------------------------------------------------------------------------------- credentials
print("-- credential handling (runner)")
FAKE = "hf_" + "Ab3" * 10  # a token-shaped string; never a real credential
check("redact() removes an explicit secret and any hf_ token pattern",
      FAKE not in runner.redact(f"x {FAKE} y", FAKE) and FAKE not in runner.redact(f"token={FAKE}") and "hf_***REDACTED***" in runner.redact(FAKE))
with tempfile.TemporaryDirectory() as d:
    p = Path(d)
    (p / "a.log").write_text(f"download ok {FAKE}\n")
    (p / "b.json").write_text('{"t": "' + FAKE + '"}')
    (p / "c.log").write_text("clean\n")
    changed = runner.redact_tree(p, FAKE)
    check("redact_tree() scrubs every text artefact before zipping and reports which files changed",
          len(changed) == 2 and all(FAKE not in f.read_text() for f in p.iterdir()))
    log = p / "run.log"
    runner.sh([sys.executable, "-c", "pass", FAKE], log)
    check("sh() never writes a token that appears on a command line", FAKE not in log.read_text())
src = (HERE / "bench" / "kaggle" / "run_e2e_kaggle.py").read_text()
check("the intent-model download passes the token through the child's environment, not argv",
      "token=os.environ.get('HF_TOKEN')" in src and "sys.argv[4]" not in src and "tok or \"\"" not in src)

# ---------------------------------------------------------------------------------------------------- sweep windows
print("-- sweep geometry")
w = inv.sweep_windows(inv.CASES["pos_02"]["sweep"])
kinds = {k: [x for x in w if x[0] == k] for k in ("both", "start_only", "end_only")}
check("pos_02 sweep: both edges 26880..27120 (9 steps of 30 ms, fixed 10 980 ms length), start-only 26940..27060, "
      "end-only 37920..38040 -- covering the OFF and ON boundaries",
      len(kinds["both"]) == 9 and all(e - s == 10980 for _, s, e in kinds["both"])
      and (26940, 37920) in [(s, e) for _, s, e in kinds["both"]] and (27060, 38040) in [(s, e) for _, s, e in kinds["both"]]
      and [s for _, s, _ in kinds["start_only"]] == [26940, 26970, 27000, 27030, 27060]
      and [e for _, _, e in kinds["end_only"]] == [37920, 37950, 37980, 38010, 38040])
check("case definitions match the live windows in gpu_t4_real_models (OFF/ON boundaries, stream times)",
      inv.CASES["pos_02"]["exact"] == {"off": (26940, 37920), "on": (27060, 38040)}
      and inv.CASES["pos_01"]["exact"] == {"off": (17460, 28440), "on": (17490, 28470)}
      and inv.CASES["neg_10"]["sequence"]["off"] == [((0, 9480), 9.6), ((0, 9510), 14.7)])

# ---------------------------------------------------------------------------------------------------- live path
print("-- replay through the real live path (fake models)")
try:
    import av  # noqa: F401
    import numpy as np
    import webrtcvad  # noqa: F401
    have = True
except ImportError:
    have = False
clip = None
if have:
    for base in (ROOT / "real_recordings" / "mixed", ROOT.parent, Path("/kaggle/input")):
        if base.exists():
            clip = next((c for c in base.rglob("*clip_19_muffled.mp3")), None)
            if clip:
                break
if not have or clip is None:
    skip("replay checks", "needs webrtcvad + PyAV + numpy + clip_19_muffled.mp3")
else:
    import segmentation_integrity as si
    from intent_gate import IntentGate
    from stt import Transcript
    state = {"text": "Please leave me alone", "temperature": 0.0, "logprob": -0.3, "beats": 0.01}

    def has_speech(pcm):
        v = webrtcvad.Vad(1)
        return any(v.is_speech(pcm[i:i + 960], 16000) for i in range(0, len(pcm) - 959, 960))

    class FakeWhisper:
        model_version = "fake-whisper"

        def transcribe(self, pcm):
            return Transcript(state["text"] if has_speech(pcm) else "", self.model_version, state["logprob"], state["temperature"], 1.1)

    class FakeParakeet:
        model_version = "fake-parakeet"

        def transcribe(self, pcm):
            return Transcript("", self.model_version)  # empty, as Parakeet was on the pos_02 windows

    class FakeBEATs:
        model_version = "fake-beats"

        def score(self, pcm):
            return state["beats"]

        def label_probs(self, pcm):
            p = np.zeros(600, dtype=np.float32)
            import scream_trigger
            if state["beats"] > 0.2:
                for c in list(scream_trigger.CLASSES):
                    p[c] = state["beats"]
            return p

    gate = object.__new__(IntentGate)
    gate.threshold = 0.02
    gate.p_distress = lambda text: 0.9

    def prepare(api):
        api._stt_backend, api._parakeet_stt, api._scream_detector, api._intent_gate = FakeWhisper(), FakeParakeet(), FakeBEATs(), gate
        api._scream_trigger_enabled = api._scream_corroboration_enabled = api._stt_confidence_gate_enabled = True

    h = e2e.Harness({k: "0" for k in ("UDK_ENABLE_STT", "UDK_ENABLE_PARAKEET", "UDK_ENABLE_SEMANTIC")}, prepare=prepare)
    pcm = si.decode(clip)

    live = h.run(pcm, 100, True, "live")
    schedule, last_t = [], 0.1
    for s in live["segments"]:
        last_t = (s["now_s"] - 1000.0) if s["now_s"] is not None else last_t
        schedule.append(((s["start_ms"], s["end_ms"]), last_t))
    segs, events = inv.replay(h, pcm, schedule, "rp")
    keys = ("start_ms", "end_ms", "pcm", "skipped", "stt_suspect", "primary", "pre_veto", "final", "alerts")
    check("replay == live: every segment of a streamed journey, replayed in one journey at its stream time, reproduces "
          "audio digest, confidence flag, Whisper-based and either-STT decisions and alerts",
          [{k: s[k] for k in keys} for s in segs] == [{k: s[k] for k in keys} for s in live["segments"]]
          and [s["whisper"]["text"] for s in segs] == [s["whisper"]["text"] for s in live["segments"]], (len(segs), len(live["segments"])))
    check("replay == live: identical emitted events (decision, UDK, layer)",
          [(e["decision"], e["udk_id"], e["layer"]) for e in events] == [(e["decision"], e["udk_id"], e["layer"]) for e in live["events"]])

    # the pos_02 pattern, from the transcripts observed on the T4
    win = next(s for s in live["segments"] if not s["skipped"])
    W = [((win["start_ms"], win["end_ms"]), 38.0)]
    state.update(text="Help! Help! Help! Help! I can't believe it! I can't believe it! Please! Please! I can't believe it!",
                 temperature=0.0, logprob=-0.727, beats=0.36)
    from udk_engine import match_transcript
    from udks import all_udks
    whole = match_transcript(state["text"], all_udks())
    confident = inv.summarise_record(inv.replay(h, pcm, W, "conf")[0][0])
    check("v1 BUG reproduced: the whole-text matcher cannot yield the per-sentence exact UDK_01 (it gives no UDK on the "
          "T4 with MiniLM; here, without MiniLM, the built-in scorer's semantic UDK_08) ...",
          whole.udk is None or (whole.udk.udk_id != "UDK_01" and whole.layer != "exact"), (whole.udk, whole.layer))
    check("... while the live path (v2) records the per-sentence exact UDK_01 -> TRIGGER_ALL, corroborated by BEATs",
          ("TRIGGER_ALL", "UDK_01", "exact") in [(a["decision"], a["udk_id"], a["layer"]) for a in confident["alerts"]]
          and confident["stt_suspect"] is False, confident["alerts"])
    state.update(temperature=0.2, logprob=-0.93)  # ON-window decoding: temperature fallback
    suspect = inv.summarise_record(inv.replay(h, pcm, W, "sus")[0][0])
    check("same text, suspect decoding -> text match vetoed by the STT-confidence guardrail; only the acoustic "
          "TRIGGER_VERIFY remains (the observed ON outcome); the flag is recorded",
          suspect["stt_suspect"] is True and all(a["layer"] == "acoustic_scream" for a in suspect["alerts"]) and suspect["alerts"]
          and all("vetoed" in (d["reason"] or "") for d in suspect["whisper_decisions"] if d["udk_id"]), (suspect["alerts"], suspect["whisper_decisions"]))
    out = inv.outcome(suspect)
    check("sweep outcome records suspect flag, temperature, alerts and text UDKs (v1 recorded none of the first two)",
          out["suspect"] is True and out["temperature"] == 0.2 and out["alerts"])

    # the neg_10 pattern: same utterance processed twice, 5.1 s apart
    state.update(text="I need to get out of here", temperature=0.0, logprob=-0.39, beats=0.01)
    off_segs, off_ev = inv.replay(h, pcm, [(W[0][0], 9.6), ((win["start_ms"], win["end_ms"] + 30), 14.7)], "seq-off")
    on_segs, on_ev = inv.replay(h, pcm, [((win["start_ms"], win["end_ms"] + 30), 9.6)], "seq-on")
    check("sequence replay reproduces repeat-window state: OFF (utterance re-processed 5.1 s later) -> VERIFY then "
          "TRIGGER_ALL 'repeated'; ON (processed once) -> one VERIFY",
          [(e["decision"], e["udk_id"]) for e in off_ev] == [("TRIGGER_VERIFY", "UDK_20"), ("TRIGGER_ALL", "UDK_20")]
          and off_segs[1]["alerts"][0]["repeated"] and [(e["decision"], e["udk_id"]) for e in on_ev] == [("TRIGGER_VERIFY", "UDK_20")],
          (off_ev, on_ev))
    reps = inv.investigate(h, pcm, {"exact": {"on": W[0][0]}, "times": {"on": 9.6}}, repeats=3)
    x = reps["exact"]["on"]
    check("repeats run on identical bytes (one audio digest) and report output identity (deterministic fakes -> identical)",
          x["same_audio_every_repeat"] and x["whisper_identical"] and x["parakeet_identical"] and x["alerts_identical"])

print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "") + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
