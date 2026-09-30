"""Phase 3 tests: scene schema, preceding-only context windows, decision rules H1-H6, production
equivalence, negation features, evaluation metrics -- on the deterministic toy fixture
(fixtures/scenes_toy.jsonl) with the TEST-ONLY lexicon scorer. No model, no real data; nothing here
is a performance claim. Production-matcher checks need rapidfuzz + numpy (SKIP otherwise).

    python udk_context/test_context.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.textnorm import normalise
from udk_context.context_window import build_window
from udk_context.decision import ContextConfig, ContextConfigError, UdkEvidence, decide
from udk_context.evaluation import evaluate, recall_check, run_layer
from udk_context.intent import FixtureIntentScorer, SentenceIntentScorer
from udk_context.negation import negation_features
from udk_context.scene import SceneError, load_scenes, scene_from_dict
from udks import GENERAL_UDKS

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


SCENES = load_scenes(HERE / "fixtures" / "scenes_toy.jsonl")
BY = {s.scene_id: s for s in SCENES}
PROD = ContextConfig.load(HERE / "configs" / "production_equivalent.json")
FIX = ContextConfig.load(HERE / "configs" / "fixture_context.json")
SENT, CTX = FixtureIntentScorer(False), FixtureIntentScorer(True)


def fixture_evidence(scene, heard_by_both=True):
    """TEST ONLY: whole-word containment of a UDK phrase (the production matcher is checked separately)."""
    text = scene.target.text
    w = " " + " ".join(normalise(text)[0]) + " "
    phrases = [(u.udk_id, u.phrase, "GENERAL") for u in GENERAL_UDKS]
    if scene.custom_phrase:
        phrases.insert(0, ("PUDK_U0", scene.custom_phrase, "PERSONAL"))
    for uid, ph, typ in phrases:
        if " " + " ".join(normalise(ph)[0]) + " " in w:
            return UdkEvidence("TRIGGER_ALL", uid, typ, ph, "exact", 1.0, heard_by_both, text)
    return UdkEvidence("NO_ACTION", None, None, None, "none", 0.0, heard_by_both, text)


def run(cfg, sent=SENT, ctx=CTX):
    return run_layer(SCENES, cfg, fixture_evidence, sent, ctx if cfg is FIX else None)


fx, pr = run(FIX), run(PROD)
alert = lambda d, sid: d[sid].decision != "NO_ACTION"

# --- scene schema -------------------------------------------------------------------------------------
check("toy fixture: 26 valid Phase 1 §15 scenes", len(SCENES) == 26)
base = {"scene_id": "x", "problem_type": "A_standard_udk", "label": "SAFE", "provenance": "fixture", "split": "dev",
        "languages": ["en"], "turns": [{"turn_index": 0, "speaker_id": "s", "role": None, "text": "hi", "start_s": 0, "end_s": 1}],
        "target_turn_index": 0}
check("unknown label rejected", raises(lambda: scene_from_dict({**base, "label": "MAYBE"}), SceneError))
check("role without speaker attribution rejected",
      raises(lambda: scene_from_dict({**base, "turns": [{**base["turns"][0], "speaker_id": None, "role": "victim"}]}), SceneError))
check("custom-UDK scene without its phrase rejected", raises(lambda: scene_from_dict({**base, "problem_type": "B_custom_udk"}), SceneError))
check("non-Phase-1 role rejected", raises(lambda: scene_from_dict({**base, "turns": [{**base["turns"][0], "role": "hero"}]}), SceneError))

# --- context window --------------------------------------------------------------------------------------
w8 = build_window(BY["a08_danger_multi_speaker"], 20, 6)
check("multi-speaker window keeps every speaker's turn separate, oldest first",
      [(c.turn.speaker_id, c.relation) for c in w8.turns] == [("fx:spkC", "other_speaker"), ("fx:spkB", "other_speaker"), ("fx:spkD", "other_speaker")])
check("rendered context marks speaker, role and relation per turn (never one merged string)",
      w8.render().splitlines()[1].startswith("[fx:spkB|attacker|other_speaker]"))
check("max_turns keeps only the most recent turns", [c.turn.speaker_id for c in build_window(BY["a08_danger_multi_speaker"], 20, 1).turns] == ["fx:spkD"])
check("window_s drops turns ending too long before the target", build_window(BY["a07_danger_misleading_context"], 2.0, 6).turns == ())
check("preceding only: nothing at or after the target", all(c.turn.end_s <= w8.target.start_s for c in w8.turns))
wo = build_window(BY["a09_danger_overlap_attributed"], 20, 6)
check("a turn overlapping the target is 'concurrent', not context", wo.turns == () and len(wo.concurrent) == 1)
wu = build_window(BY["a09_danger_overlap_unattributed"], 20, 6)
check("no speaker attribution -> attribution_complete false", wu.attribution_complete is False)
check("same speaker relation", build_window(BY["a01_safe_request"], 20, 6).turns[0].relation == "same_speaker")
check("context_after is never read (not even stored in the fixture)", all(s.context_after is None for s in SCENES))
check("window size is required configuration", raises(lambda: build_window(BY["a01_safe_request"], -1, 6), ValueError))

# --- config ---------------------------------------------------------------------------------------------
raw = copy.deepcopy(FIX.raw)
check("config: an enabled feature needs a threshold",
      raises(lambda: ContextConfig.from_dict({**raw, "danger_without_udk": {**raw["danger_without_udk"], "threshold": None}}), ContextConfigError))
check("config: hard rule H3 cannot be configured away",
      raises(lambda: ContextConfig.from_dict({**raw, "context_veto": {**raw["context_veto"], "block_if_other_speaker": False}}), ContextConfigError))
check("config: missing section -> error (no defaults)", raises(lambda: ContextConfig.from_dict({k: v for k, v in raw.items() if k != "negation"}), ContextConfigError))
check("config: context veto needs a sentence ceiling",
      raises(lambda: ContextConfig.from_dict({**raw, "context_veto": {"enabled": True, "threshold": 0.02, "sentence_ceiling": None}}), ContextConfigError))

# --- production equivalence -----------------------------------------------------------------------------------
check("production-equivalent config: final decision == UDK path on every scene (sentence scorer never < 0.02 here)",
      all(pr[s.scene_id].decision == fixture_evidence(s).decision for s in SCENES))
low = type("G", (), {"p_distress": lambda self, t: 0.001})()
ev = fixture_evidence(BY["a01_safe_request"])
check("production-equivalent: sentence veto fires exactly as intent_gate (p < 0.02, both STTs agree)",
      decide(ev, build_window(BY["a01_safe_request"], 20, 6), PROD, SentenceIntentScorer(low)).source == "vetoed:sentence")
check("production-equivalent: no veto when the other STT did not hear the same words (H2)",
      decide(fixture_evidence(BY["a01_safe_request"], heard_by_both=False), build_window(BY["a01_safe_request"], 20, 6), PROD,
             SentenceIntentScorer(low)).decision == "TRIGGER_ALL")
check("PERSONAL alert never vetoed, even with p = 0.001 (H1)",
      decide(fixture_evidence(BY["b01_safe_custom"]), build_window(BY["b01_safe_custom"], 20, 6), FIX, SentenceIntentScorer(low), CTX).decision == "TRIGGER_ALL")
check("context scorer must actually use context", raises(lambda: decide(ev, build_window(BY["a01_safe_request"], 20, 6), FIX, SENT, SENT), ContextConfigError))

# --- behaviour on the fixture (context config) ---------------------------------------------------------------
for pair in ("p01", "p02", "p03", "p04"):
    safe = next(s for s in SCENES if s.pair_id == pair and s.label == "SAFE")
    dang = next(s for s in SCENES if s.pair_id == pair and s.label == "DANGER")
    check(f"same target text ({dang.target.text!r}, {'+'.join(dang.languages)}): SAFE context silent, DANGER context alerts",
          not alert(fx, safe.scene_id) and alert(fx, dang.scene_id) and safe.target.text == dang.target.text,
          (fx[safe.scene_id].reasons, fx[dang.scene_id].reasons))
check("attacker -> victim: other-speaker context blocks any context veto (H3)",
      any("another speaker" in r for r in fx["a01_danger_attacker_victim"].reasons))
check("victim -> attacker (no UDK): raised as TRIGGER_VERIFY", fx["c02_danger_victim_to_attacker"].decision == "TRIGGER_VERIFY")
check("story/movie narration silenced only through same-speaker context", fx["a02_safe_movie_quote"].source == "vetoed:context")
check("news report of strong danger words is NOT silenced (sentence ceiling) -- a known false alarm",
      alert(fx, "a05_safe_news") and any("ceiling" in r for r in fx["a05_safe_news"].reasons))
check("genuine danger despite misleading same-speaker 'game' context stays an alert",
      alert(fx, "a07_danger_misleading_context") and fx["a07_danger_misleading_context"].scores["p_context"] < 0.02)
check("negation-but-danger stays an alert; negation recorded as evidence only (H5)",
      alert(fx, "a06_danger_negation_but_danger") and fx["a06_danger_negation_but_danger"].negation["negator_scopes_udk"])
check("negated request ('I don't need help') raises nothing", not alert(fx, "a06_safe_negation") and not alert(pr, "a06_safe_negation"))
check("mixed Hindi/English danger without UDK -> TRIGGER_VERIFY; same words in a game -> nothing",
      fx["c03_danger_hinglish"].decision == "TRIGGER_VERIFY" and not alert(fx, "c04_safe_hinglish_game"))
check("danger without UDK never TRIGGER_ALL from a classifier (H6)",
      all(d.decision != "TRIGGER_ALL" for d in fx.values() if d.source == "context_intent"))
check("multi-speaker danger alerts", alert(fx, "a08_danger_multi_speaker"))
check("argument between two speakers: context cannot silence it (H3) -- a known false alarm", alert(fx, "a08_safe_argument"))
check("overlap, attributed and unattributed: alerts kept; context veto blocked (H4)",
      alert(fx, "a09_danger_overlap_attributed") and alert(fx, "a09_danger_overlap_unattributed")
      and any("overlaps" in r for r in fx["a09_danger_overlap_unattributed"].reasons))
check("media voice saying a UDK still alerts (Phase 0 product rule vs Phase 1 SAFE label: C-2)", alert(fx, "a10_safe_media_nearby"))
check("custom-UDK SAFE mention still alerts (H1) -- a known false alarm", alert(fx, "b01_safe_custom"))
check("without heard_by_both, danger-without-UDK is not raised",
      decide(fixture_evidence(BY["c01_danger_knife"], heard_by_both=False), build_window(BY["c01_danger_knife"], 20, 6), FIX, SENT, CTX).decision == "NO_ACTION")

# --- negation features ------------------------------------------------------------------------------------
negs = {"not", "dont", "nahi"}
check("negator inside the UDK phrase is not negation ('Don't touch me')",
      negation_features("Don't touch me", "Don't touch me", negs, 3)["extra_negators"] == 0)
check("negator scoping the UDK phrase detected", negation_features("I'm not okay, help me please", "Help me, please", negs, 3)["negator_scopes_udk"])

# --- speaker-disjoint scene splits (reuses the S3 splitter) ---------------------------------------------------
from asr_bench.splits import SplitConfig
from udk_context.scene import assign_scene_splits
scfg = SplitConfig.from_dict({"format": "asr_bench.split_config/1", "salt": "udk-phase2a-v1", "sources": {
    "fixture": {"policy": "hash", "ratios": {"train": 0.4, "dev": 0.2, "test": 0.2, "final_test": 0.2}}}})
ss = assign_scene_splits(SCENES, scfg, "fixture", "train_ok")
spk_split = {}
for s_ in SCENES:
    for t_ in s_.turns:
        if t_.speaker_id:
            spk_split.setdefault(t_.speaker_id, set()).add(ss[s_.scene_id])
check("scene splits: every speaker (attacker and victim alike) in exactly one split", all(len(v) == 1 for v in spk_split.values()), spk_split)
check("scene splits: scene with no target speaker -> eval_only", ss["a09_danger_overlap_unattributed"] == "eval_only")
check("scene splits deterministic", assign_scene_splits(SCENES, scfg, "fixture", "train_ok") == ss)

# --- evaluation ------------------------------------------------------------------------------------------
ef, ep = evaluate(SCENES, fx, "dev"), evaluate(SCENES, pr, "dev")
A_f, A_p = ef["by_problem_type"]["A_standard_udk"], ep["by_problem_type"]["A_standard_udk"]
check("metrics reported per problem type, never pooled", set(ef["by_problem_type"]) == {"A_standard_udk", "B_custom_udk", "C_danger_no_udk"})
check("toy A: DANGER recall 10/10 with and without context", A_f["danger_recall"]["num"] == A_p["danger_recall"]["num"] == 10)
check("toy A: SAFE false alarms 7/8 production-equivalent -> 3/8 with fixture context",
      (A_p["safe_false_alarm_rate"]["num"], A_f["safe_false_alarm_rate"]["num"], A_f["safe_false_alarm_rate"]["den"]) == (7, 3, 8))
check("toy C: danger without UDK 0/3 -> 3/3; SAFE C 0/2 both",
      (ep["by_problem_type"]["C_danger_no_udk"]["danger_recall"]["num"], ef["by_problem_type"]["C_danger_no_udk"]["danger_recall"]["num"],
       ef["by_problem_type"]["C_danger_no_udk"]["safe_false_alarm_rate"]["num"]) == (0, 3, 0))
check("pair separation: 4 of 5 A pairs with context, 0 of 5 without", (A_f["pair_separation"]["num"], A_p["pair_separation"]["num"], A_f["pair_separation"]["den"]) == (4, 0, 5))
check("role-conditioned recall and turn-order reported",
      A_f["role_conditioned_recall"]["attacker"]["value"] == 1.0 and "victim_to_attacker" in ef["by_problem_type"]["C_danger_no_udk"]["turn_order_correct"])
check("overlap recall split by level and attribution", len(A_f["overlap_recall"]) == 2)
check("speaker-attribution accuracy UNAVAILABLE (no runtime attribution)", "UNAVAILABLE" in ef["target_speaker_identification_accuracy"])
check("failure listing names the known false alarms", {f["scene_id"] for f in ef["failures"]} == {"a05_safe_news", "a08_safe_argument", "a10_safe_media_nearby", "b01_safe_custom"})
rc = recall_check(SCENES, pr, fx, "dev")
check("recall-first: fixture context loses no DANGER scene vs production-equivalent", rc["passes_recall_first"] and rc["lost_danger"] == [])
check("recall-first check catches a lost danger", not recall_check(SCENES, fx, {**fx, "a01_danger_attacker_victim": pr["a06_safe_negation"]}, "dev")["passes_recall_first"])
ft = evaluate(SCENES, fx, "final_test")
check("final_test: totals only, no per-scene failures", ft["totals_only"] and "failures" not in ft and "role_conditioned_recall" not in ft["by_problem_type"]["A_standard_udk"])

# --- production matcher / adapter (needs rapidfuzz + numpy) -------------------------------------------------
try:
    import numpy  # noqa: F401
    import rapidfuzz  # noqa: F401
    ok = True
except ImportError:
    ok = False
if not ok:
    for n in ("production matcher on every scene", "adapter vs intent_gate.IntentGate.veto"):
        skip(n, "rapidfuzz/numpy not installed here")
else:
    import intent_gate
    from udk_context.production_adapter import production_matcher
    agree = []
    for s in SCENES:
        evp = production_matcher(s.custom_phrase)(s.target.text, s.target.text)
        dec = decide(evp, build_window(s, 20, 6), PROD, None)
        agree.append(dec.decision == evp.decision)
    check("production matcher + production-equivalent config: decision unchanged on every scene", all(agree))
    g = intent_gate.IntentGate.__new__(intent_gate.IntentGate)
    g.threshold, g.p_distress = 0.02, (lambda t: 0.001)
    same = []
    for s in SCENES:
        m = production_matcher(s.custom_phrase)
        from udk_engine import UDKEngine
        from udks import UDK
        evp = m(s.target.text, s.target.text)
        if evp.decision == "NO_ACTION":
            continue
        ours = decide(evp, build_window(s, 20, 6), PROD, SentenceIntentScorer(g)).decision == "NO_ACTION"
        udks = list(GENERAL_UDKS) + ([UDK("PUDK_U0", s.custom_phrase, "PERSONAL")] if s.custom_phrase else [])
        best = max(UDKEngine(udks).decide_all(s.target.text, now_s=0.0), key=lambda d: (d.decision != "NO_ACTION", d.confidence))
        same.append(ours == (g.veto(best, s.target.text) is not None))
    check("vetoes identical to the live intent_gate.IntentGate.veto on every alerting scene", same and all(same), same)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "")
      + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
