"""Targeted investigation of real-model OFF-vs-ON differences, through the REAL live decision path.

v2 (replaces v1): every window is replayed through api._run_incremental_detection itself -- a fresh journey whose VAD
returns exactly that window, with the harness's recorder and virtual clock. The record per replay is therefore the live
chain, not a re-implementation of it:

  window (start, end ms) -> audio digest -> Whisper text + decoding metadata -> STT confidence gate (suspect flag)
  -> Parakeet text -> Whisper-based engine decision (whole segment + per-sentence) -> either-STT decision -> intent
  scores / veto -> BEATs scream trigger and corroboration -> final alerts

v1 defects fixed here, each with a regression test in udk_shadow/test_e2e_vad_cache.py:
  * v1 scored transcripts with the whole-text matcher (match_transcript), not the live per-sentence decision, so it
    reported "no UDK" on a window where the live run emitted an exact UDK_01 sentence match;
  * v1's boundary sweep recorded neither Whisper's decoding metadata nor the confidence-gate flag, so it could not show
    whether a boundary shift flips the gate;
  * v1 did not record the audio digest, so "same input" could not be proven.

Modes per case:
  exact      the OFF and ON windows of the live run, N repeats each on identical bytes (nondeterminism test)
  sequence   several windows in ONE journey at their live stream times (reproduces repeat-window state, e.g. neg_10)
  sweep      boundary slides in 30 ms steps: both edges together, start only, end only

Transcripts are kept only for these investigated windows (needed to explain the difference); everything else is digests.

    python udk_shadow/bench/e2e_investigate.py --recordings recordings.json --out investigate_v2.json [--device cuda]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

# live windows and stream times (s since journey start) from gpu_t4_real_models/runs.zip (100 ms chunks)
CASES = {
    "pos_02": {
        "exact": {"off": (26940, 37920), "on": (27060, 38040)},
        "times": {"off": 38.0, "on": 38.1},
        "sweep": {"both": (26880, 27120), "start_only": (26940, 27060), "end_only": (37920, 38040),
                  "fixed_start": 26940, "fixed_end": 37920, "length": 10980},
    },
    "pos_01": {
        "exact": {"off": (17460, 28440), "on": (17490, 28470)},
        "times": {"off": 28.5, "on": 28.5},
        "sweep": {"both": (17400, 17550), "length": 10980},
    },
    "neg_10": {
        "exact": {"off": (0, 9480), "on": (0, 9510)},
        "times": {"off": 9.6, "on": 9.6},
        "sequence": {"off": [((0, 9480), 9.6), ((0, 9510), 14.7)], "on": [((0, 9510), 9.6)]},
    },
}


class WindowVAD:
    """Returns exactly the scheduled window(s); total_ms is the whole buffer, so every window is finalizable."""
    def __init__(self, vad_cls):
        self._frames_total = vad_cls().total_ms
        self.windows = []

    def segment_speech(self, pcm):
        from vad import SpeechSegment
        return [SpeechSegment(s, e, pcm[s * 32:e * 32]) for s, e in self.windows]

    def total_ms(self, pcm):
        return self._frames_total(pcm)


def replay(h, pcm, schedule, label):
    """schedule: [((start_ms, end_ms), stream_time_s), ...] replayed in ONE fresh journey through the live loop."""
    api = h.api
    h.recorder.segments = []
    jid = f"inv-{label}"
    api.start_journey(api.StartRequest(user_id="inv", journey_id=jid))
    j = api._store.get(jid)
    j.vad = WindowVAD(h.VAD)
    j.audio_buffer.extend(pcm)
    for (s, e), t in schedule:
        h.clock.now = 1000.0 + t
        j.vad.windows = [(s, e)]
        api._run_incremental_detection(j, final=True)
    events = [{k: ev.get(k) for k in ("decision", "udk_id", "layer", "confidence")} for ev in j.events]
    segs = [dict(r) for r in h.recorder.segments]
    api._store._journeys.pop(jid, None)
    return segs, events


def summarise_record(r):
    """One replayed segment -> the chain, with text (investigated windows only)."""
    w = r["whisper"] or {}
    return {"window": (r["start_ms"], r["end_ms"]), "audio_digest": r["pcm"], "skipped": r["skipped"],
            "whisper": {"text": w.get("text"), "temperature": w.get("temperature"), "avg_logprob": w.get("avg_logprob"),
                        "compression_ratio": w.get("compression_ratio")},
            "stt_suspect": r["stt_suspect"], "parakeet": r["parakeet"], "whisper_decisions": r["primary"],
            "either_stt_decisions": r["pre_veto"], "intent": r["intent"], "scream_trigger": r["scream_trigger"],
            "scream_score": r["scream_score"], "final": r["final"], "alerts": r["alerts"]}


def outcome(rec):
    """Compact per-replay outcome used by the sweeps."""
    return {"suspect": rec["stt_suspect"], "temperature": rec["whisper"]["temperature"],
            "alerts": [(a["decision"], a["udk_id"], a["layer"]) for a in rec["alerts"]],
            "text_udks": sorted({(d["udk_id"], d["layer"]) for d in rec["either_stt_decisions"] if d["udk_id"]})}


def sweep_windows(spec):
    L = spec["length"]
    out = []
    a, b = spec["both"]
    out += [("both", s, s + L) for s in range(a, b + 1, 30)]
    if "start_only" in spec:
        a, b = spec["start_only"]
        out += [("start_only", s, spec["fixed_end"]) for s in range(a, b + 1, 30)]
        a, b = spec["end_only"]
        out += [("end_only", spec["fixed_start"], e) for e in range(a, b + 1, 30)]
    return out


def investigate(h, pcm, spec, repeats=5, sweep_repeats=3):
    res = {"exact": {}, "sequence": {}, "sweep": []}
    for mode, (s, e) in spec["exact"].items():
        reps = []
        for i in range(repeats):
            segs, _ = replay(h, pcm, [((s, e), spec["times"][mode])], f"{mode}-{i}")
            reps.append(summarise_record(segs[0]))
        texts = [r["whisper"]["text"] for r in reps]
        ptexts = [r["parakeet"] for r in reps]
        res["exact"][mode] = {"window": (s, e), "repeats": reps,
                              "same_audio_every_repeat": len({r["audio_digest"] for r in reps}) == 1,
                              "whisper_identical": len(set(texts)) == 1, "parakeet_identical": len(set(ptexts)) == 1,
                              "suspect_flags": [r["stt_suspect"] for r in reps],
                              "alerts_identical": len({json.dumps(r["alerts"], sort_keys=True) for r in reps}) == 1}
    for mode, sched in spec.get("sequence", {}).items():
        segs, events = replay(h, pcm, [(tuple(w), t) for w, t in sched], f"seq-{mode}")
        res["sequence"][mode] = {"schedule": sched, "segments": [summarise_record(x) for x in segs], "events": events}
    if "sweep" in spec:
        for kind, s, e in sweep_windows(spec["sweep"]):
            outs = [outcome(summarise_record(replay(h, pcm, [((s, e), 40.0)], f"sw-{kind}-{s}-{e}-{i}")[0][0]))
                    for i in range(sweep_repeats)]
            res["sweep"].append({"kind": kind, "window": (s, e), "runs": outs})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--intent-dir", default=None)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--sweep-repeats", type=int, default=3)
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--allow-missing-whisper", action="store_true", help="plumbing checks only; not a real-model result")
    a = ap.parse_args()
    import e2e_vad_cache as e2e
    import segmentation_integrity as si
    env, notes = e2e.production_env(ROOT / "deploy" / ".env.example", a.device, a.intent_dir)
    h = e2e.Harness(env)
    print("components", json.dumps(h.components), flush=True)
    if h.components["whisper"].startswith("UNAVAILABLE") and not a.allow_missing_whisper:
        raise SystemExit("Whisper did not load (api.py fell back to MockSTT): refusing to run a real-model investigation")
    recs = {r["id"]: r for r in json.loads(Path(a.recordings).read_text())}
    report = {"version": 2, "components": h.components, "notes": notes, "repeats": a.repeats, "cases": {}}
    for rid in a.cases.split(","):
        pcm = si.decode(Path(recs[rid]["path"]))
        r = investigate(h, pcm, CASES[rid], a.repeats, a.sweep_repeats)
        report["cases"][rid] = r
        print(f"\n===== {rid}")
        for mode, x in r["exact"].items():
            print(f"-- exact {mode} {x['window']} audio={x['repeats'][0]['audio_digest']} same_audio={x['same_audio_every_repeat']} "
                  f"whisper_identical={x['whisper_identical']} parakeet_identical={x['parakeet_identical']} "
                  f"suspect={x['suspect_flags']} alerts_identical={x['alerts_identical']}")
            for rep in x["repeats"][:3]:
                print(f"   W T={rep['whisper']['temperature']} lp={rep['whisper']['avg_logprob']} suspect={rep['stt_suspect']} :: {rep['whisper']['text']}")
                print(f"   P :: {rep['parakeet']}")
                print(f"   either-STT={[(d['decision'], d['udk_id'], d['layer'], d['confidence']) for d in rep['either_stt_decisions']]} "
                      f"intent={rep['intent']} scream={rep['scream_trigger']} alerts={[(d['decision'], d['udk_id'], d['layer']) for d in rep['alerts']]}")
        for mode, x in r["sequence"].items():
            print(f"-- sequence {mode}: events {[(e['decision'], e['udk_id'], e['layer']) for e in x['events']]}")
        for sw in r["sweep"]:
            print(f"   sweep {sw['kind']:10s} {sw['window']}  suspect={[o['suspect'] for o in sw['runs']]}  "
                  f"T={[o['temperature'] for o in sw['runs']]}  alerts={[o['alerts'] for o in sw['runs']]}", flush=True)
    Path(a.out).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    print("DONE", a.out)


if __name__ == "__main__":
    main()
