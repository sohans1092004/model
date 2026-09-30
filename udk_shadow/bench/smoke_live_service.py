"""Phase 6C live-service smoke test (test tooling; not in the image). Drives the REAL api module in-process --
REST journey start + websocket frame streaming through the real _run_incremental_detection and the real shadow
hook -- with MockSTT transcripts and a fixed-block VAD (as test_m3.py does), once per scenario in a fresh process:

  off            UDK_SHADOW_MODE unset
  on             UDK_SHADOW_MODE=1 (records drained and inspected)
  stage_error    ON, every Phase 5 call raises inside the shadow worker
  queue_full     ON, UDK_SHADOW_QUEUE_MAX=1 and a slow shadow stage -> observations dropped
  missing_pkg    ON, but the udk_shadow package cannot be imported -> shadow must stay OFF

For every scenario the live events (decision, udk_id, layer, segment) must be identical to "off".
Usage:  python smoke_live_service.py            (runs all scenarios, prints JSON summary, exit 1 on any failure)
        python smoke_live_service.py --scenario on   (one scenario, used internally)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCENARIOS = ("off", "on", "stage_error", "queue_full", "missing_pkg")
BLOCK = 3200  # bytes per fake segment (the fixed-block VAD reads ms == bytes, as test_m3.py)
TEXTS = ["help me please", "", "the weather is nice today", "I don't feel safe here", "let go of me! please don't hurt me!",
         "call the police I need help", "", "we are late for the movie"]


def scenario(name: str) -> dict:
    if name == "missing_pkg":
        import importlib.abc

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == "udk_shadow":
                    raise ImportError("blocked for the smoke test: " + fullname)
        sys.meta_path.insert(0, Block())
    tmp = Path(tempfile.mkdtemp(prefix="udk_smoke_"))
    os.environ["UDK_DATA_DIR"] = str(tmp / "data")
    import api
    from db import JourneyDB
    from event_delivery import EventDeliveryQueue
    from fastapi.testclient import TestClient
    from storage import AudioStore
    from vad import SpeechSegment

    api._audio_store = AudioStore(tmp / "audio")
    api._event_queue = EventDeliveryQueue(tmp / "events")
    api._db = JourneyDB(tmp / "journeys.sqlite3")
    api._store = api.JourneyStore(db=api._db)
    sh = api._shadow
    if sh is not None and name == "stage_error":
        def boom(*a, **k):
            raise RuntimeError("injected shadow stage failure")
        sh.processor.stages["phase5"] = boom
    if sh is not None and name == "queue_full":
        real = sh.processor.stages["phase4"]
        sh.processor.stages["phase4"] = lambda obs: (time.sleep(0.3), real(obs))[1]

    class FixedBlockVAD:
        def segment_speech(self, pcm):
            return [SpeechSegment(start_ms=i * BLOCK, end_ms=(i + 1) * BLOCK, pcm=pcm[i * BLOCK:(i + 1) * BLOCK])
                    for i in range(len(pcm) // BLOCK)]

        def total_ms(self, pcm):
            return len(pcm)

    client = TestClient(api.app, headers={"X-Service-Token": os.environ["UDK_SERVICE_TOKEN"]})
    r = client.post("/v1/journeys/start", json={"user_id": "U_SMOKE"})
    assert r.status_code == 200, r.text
    jid, tok = r.json()["journey_id"], r.json()["session_token"]
    journey = api._store.get(jid)
    journey.vad = FixedBlockVAD()
    blocks = []
    for i, t in enumerate(TEXTS + ["", ""]):  # two trailing silent blocks so every text block is finalized
        pcm = bytes([(i * 7 + k) % 251 for k in range(BLOCK)])
        blocks.append(pcm)
        if t:
            journey.stt.register(pcm, t)
    with client.websocket_connect(f"/v1/journeys/{jid}/stream?session_token={tok}") as ws:
        for seq, pcm in enumerate(blocks):
            ws.send_bytes(api.FRAME_HEADER.pack(seq, time.time()) + pcm)
            while ws.receive_json().get("type") != "ack":  # event messages precede/follow acks; the REST list is authoritative
                pass
    events = [{"decision": e["decision"], "udk_id": e["udk_id"], "layer": e["layer"], "segment": e["audio_segment_id"].split(":")[1]}
              for e in client.get(f"/v1/journeys/{jid}/events").json()["events"]]
    alive = client.get("/metrics", headers={"X-Service-Token": os.environ["UDK_SERVICE_TOKEN"]}).status_code == 200
    out = {"scenario": name, "shadow_loaded": sh is not None, "live_events": events, "service_alive_after": alive}
    if sh is not None:
        sh.drain(60)
        recs = list(sh.records)
        out.update(stats={k: v for k, v in sh.stats.items()}, records=len(recs),
                   statuses=sorted({r.get("status") for r in recs}),
                   error_stages=sorted({e["stage"] for r in recs for e in r.get("errors", [])}),
                   effective=recs[0].get("effective") if recs else None,
                   phase5_matches_live=sum(1 for r in recs if r.get("shadow_phase5_decision") == r.get("live", {}).get("live_decision")),
                   replay_semantics_labelled=all(r.get("replay", {}).get("semantics", "").startswith("counterfactual") for r in recs if r.get("replay")))
    return out


def main() -> None:
    if "--scenario" in sys.argv:
        print("RESULT " + json.dumps(scenario(sys.argv[sys.argv.index("--scenario") + 1]), default=str))
        return
    here = Path(__file__).resolve()
    root = next(p for p in here.parents if (p / "api.py").exists())
    base_env = {k: v for k, v in os.environ.items() if not (k.startswith("UDK_ENABLE_") or k.startswith("UDK_SHADOW") or k == "UDK_INTENT_GATE")}
    base_env.update(UDK_SERVICE_TOKEN="smoke-token", UDK_WEBHOOK_URL="https://example.invalid/hook", UDK_WEBHOOK_SECRET="s",
                    PYTHONPATH=str(root) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    env_for = {"off": {}, "on": {"UDK_SHADOW_MODE": "1"}, "stage_error": {"UDK_SHADOW_MODE": "1"},
               "queue_full": {"UDK_SHADOW_MODE": "1", "UDK_SHADOW_QUEUE_MAX": "1"}, "missing_pkg": {"UDK_SHADOW_MODE": "1"}}
    res = {}
    for s in SCENARIOS:
        p = subprocess.run([sys.executable, str(here), "--scenario", s], cwd=root, env={**base_env, **env_for[s]},
                           capture_output=True, text=True, timeout=900)
        line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT ")), None)
        res[s] = json.loads(line[7:]) if line else {"error": (p.stdout + p.stderr)[-1500:]}
    ref = res["off"].get("live_events")
    checks = {
        "off: service serves, shadow not loaded": res["off"].get("service_alive_after") and res["off"].get("shadow_loaded") is False and bool(ref),
        "on: shadow loaded, every observed segment processed without errors, effective config recorded":
            res["on"].get("shadow_loaded") and res["on"].get("records", 0) >= 1 and res["on"].get("error_stages") == []
            and res["on"].get("effective", {}).get("s4_status") == "open" and res["on"].get("stats", {}).get("dropped_queue_full", 0) == 0,
        "on: replay records carry the counterfactual label": res["on"].get("replay_semantics_labelled") is True,
        "stage_error: phase5 errors recorded, live unaffected": res["stage_error"].get("error_stages") == ["phase5"],
        "queue_full: drops counted, live unaffected": res["queue_full"].get("stats", {}).get("dropped_queue_full", 0) >= 1,
        "missing_pkg: shadow stays OFF, service serves": res["missing_pkg"].get("shadow_loaded") is False and res["missing_pkg"].get("service_alive_after"),
    }
    for s in SCENARIOS:
        checks[f"{s}: live events identical to shadow OFF"] = res[s].get("live_events") == ref
    print(json.dumps({"checks": checks, "results": res}, indent=1, default=str))
    ok = all(checks.values())
    print(f"\nlive-service smoke: {sum(map(bool, checks.values()))}/{len(checks)} checks passed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
