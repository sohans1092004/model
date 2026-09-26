"""intent_gate wiring, no models: evaluate_full_system.apply_intent_gate (evals) and
api._intent_veto (live) with a stub scorer. python test_intent_gate.py"""
from types import SimpleNamespace as N

import intent_gate
from evaluate_full_system import apply_intent_gate
from udk_engine import DecisionEvent
from udks import UDK

gate = intent_gate.IntentGate.__new__(intent_gate.IntentGate)
gate.threshold = intent_gate.THRESHOLD
gate.p_distress = lambda t: 0.001 if "don't need" in t else 0.999  # stub: negation = not distress
gen = UDK("UDK_05", "I need help right now", "GENERAL")


def ev(t, layer="semantic"):
    return DecisionEvent(decision="TRIGGER_ALL", udk=gen, confidence=0.9, transcript=t, layer=layer, repeated=False, reason="")


# --- evals: both paths, per segment
w1, w2, w3, p1 = ev("I don't need help right now"), ev("Help me please"), ev("You do me!", "fuzzy"), ev("I don't need help right now.")
out = {"whisper": ([w1, w2, w3], [
    {"start_ms": 0, "transcript": "I don't need help right now", "decision": "TRIGGER_ALL", "_event": w1},
    {"start_ms": 5000, "transcript": "Help me please", "decision": "TRIGGER_ALL", "_event": w2},
    {"start_ms": 9000, "transcript": "You do me!", "decision": "TRIGGER_ALL", "_event": w3}], 0),
    "parakeet": ([p1], [
        {"start_ms": 0, "transcript": "I don't need help right now.", "decision": "TRIGGER_ALL", "_event": p1},
        {"start_ms": 5000, "transcript": "Help me, please.", "decision": "NO_ACTION", "_event": None},
        {"start_ms": 9000, "transcript": "You didn't mean.", "decision": "NO_ACTION", "_event": None}], 0)}
apply_intent_gate(out, gate)
wev, wrows, _ = out["whisper"]
assert [e.transcript for e in wev] == ["Help me please", "You do me!"], wev  # negation vetoed; danger kept
assert wrows[0]["decision"] == "NO_ACTION" and wrows[0]["veto_p"] == 0.001
assert out["parakeet"][0] == []  # vetoed on the other path too
assert wrows[2]["decision"] == "TRIGGER_ALL"  # STTs disagree -> never vetoed

# --- live API: whole-segment decision keeps its slot as NO_ACTION, extras are dropped
import api  # noqa: E402

api._intent_gate = gate
res = api._intent_veto([ev("I don't need help right now"), ev("Help me please")], "I don't need help right now, help me please")
assert res[0].decision == "NO_ACTION" and "intent veto" in res[0].reason and res[1].transcript == "Help me please", res
res = api._intent_veto([ev("Help me"), ev("I don't need help right now")], "help me i don't need help right now")
assert [d.transcript for d in res] == ["Help me"], res
vetoed = []
api._intent_veto([ev("I don't need help right now"), ev("Help me please")], "i don't need help right now help me please", vetoed)
assert [(d.decision, d.transcript) for d in vetoed] == [("TRIGGER_ALL", "I don't need help right now")], vetoed  # original decision kept for the audit record
assert "intent veto" in vetoed[0].reason

# vetoes are stored (VETOED) but hidden from /events unless include_vetoed
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api.app, headers={"X-Service-Token": api.DEV_SERVICE_TOKEN})
jid = client.post("/v1/journeys/start", json={"user_id": "U_veto"}).json()["journey_id"]
api._record_veto(api._store.get(jid), vetoed[0], N(start_ms=0, end_ms=1000), "i don't need help right now")
assert client.get(f"/v1/journeys/{jid}/events").json()["events"] == []
logged = client.get(f"/v1/journeys/{jid}/events", params={"include_vetoed": True}).json()["events"]
assert [(e["decision"], e["layer"]) for e in logged] == [("VETOED", "semantic")] and "intent veto" in logged[0]["reason"], logged
assert client.get("/metrics").json()["vetoed_by_layer"] == {"semantic": 1}
assert api._intent_veto([ev("I don't need help right now")], "")[0].decision == "TRIGGER_ALL"  # no second STT text
print("test_intent_gate: all checks passed")
