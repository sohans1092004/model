"""VAD `cache_classifications` prototype (OFF by default; nothing enables it).

OFF must be the pre-prototype vad.py exactly; ON must be the experiment's candidate D: each complete 30 ms frame is
classified once, the unchanged segmentation runs over kept flags, so streaming == one-shot segmentation. See
udk_shadow/bench/results/segmentation_candidates/SEGMENTATION_CANDIDATES.md and VAD_FLAG_PROTOTYPE.md there.

    python test_vad_classification_cache.py
"""
from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "udk_shadow" / "bench"))

import segmentation_candidates as sc  # noqa: E402
import segmentation_integrity as si  # noqa: E402
import vad_flag_equivalence as eq  # noqa: E402
from vad import FRAME_BYTES, FRAME_MS, VAD  # noqa: E402

passed = failed = skipped = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {str(detail)[:600]}" if detail != "" else ""))


def skip(name, why):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


def spans(segs):
    return [(s.start_ms, s.end_ms, s.pcm) for s in segs]


class Counting:
    """Wraps a classifier; records the index of every frame it is asked about."""
    def __init__(self, inner):
        self.inner, self.seen = inner, []

    def is_speech(self, frame, sr):
        self.seen.append(sc.frame_index(frame))
        return self.inner.is_speech(frame, sr)


orig = eq.load_original()
ns = si.live_loop_namespace()
S, Q = True, False
SCENARIOS = {
    "silence->speech->silence": [(Q, 3000), (S, 1200), (Q, 3000)],
    "speech at t=0": [(S, 900), (Q, 3000)],
    "speech ends exactly at buffer end": [(Q, 2000), (S, 1500)],
    "short gap (<post-roll) inside one utterance": [(Q, 2000), (S, 900), (Q, 600), (S, 900), (Q, 3000)],
    "long gap between two utterances": [(Q, 2000), (S, 900), (Q, 4000), (S, 900), (Q, 3000)],
    "one-frame speech": [(Q, 2000), (S, 30), (Q, 3000)],
    "long speech with forced 8 s cuts": [(Q, 1000), (S, 20000), (Q, 3000)],
    "frame-misaligned boundaries": [(Q, 3010), (S, 1210), (Q, 2990)],
}
CHUNKS = (20, 30, 90, 100, 250, 1000, 1500)


def make(cls, flag=None, classifier=None):
    def f():
        v = cls() if flag is None else cls(cache_classifications=flag)
        if classifier is not None:
            v._vad = classifier()
        return v
    return f


def trace_stream(pcm, chunk, factory):
    procs, t, _ = eq.stream(pcm, chunk, ns, factory)
    return procs, t


# ----------------------------------------------------------------------------------------------------------- defaults
print("-- defaults / integration boundary")
check("the frozen reference is byte-for-byte the 96ea038 vad.py (sha256 checked on load)", orig.VAD.__module__ == "vad_original_96ea038")
check("default is OFF: VAD().cache_classifications is False", VAD().cache_classifications is False)
api_src = (ROOT / "api.py").read_text()
check("api.py is not wired to the flag (JourneyState still uses the default VAD; flag never enabled)",
      "vad: VAD = field(default_factory=VAD)" in api_src and "cache_classifications" not in api_src)
check("the VAD integration surface is unchanged (segment_speech, total_ms; SpeechSegment fields)",
      all(hasattr(VAD, m) for m in ("segment_speech", "total_ms"))
      and list(orig.SpeechSegment.__dataclass_fields__) == ["start_ms", "end_ms", "pcm"])

# ----------------------------------------------------------------------------------------------------------- OFF
print("-- OFF mode == original implementation (static)")
import ast  # noqa: E402
import inspect  # noqa: E402


def method_ast(module_src, cls, name):
    for node in ast.walk(ast.parse(module_src)):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    return f
    raise KeyError(name)


new_src = (ROOT / "vad.py").read_text()
old_src = eq.ORIGINAL_PATH.read_text()
ORIGINAL_FLAGS = "flags = [self._vad.is_speech(f, SAMPLE_RATE) for f in frames]"
new_seg, old_seg = method_ast(new_src, "VAD", "segment_speech"), method_ast(old_src, "VAD", "segment_speech")
new_body = [ast.dump(s) for s in new_seg.body]
old_body = [ast.dump(s) for s in old_seg.body]
flag_stmt = ast.dump(ast.parse("flags = self._classify(frames)").body[0])
diff_idx = [i for i, (a, b) in enumerate(zip(new_body, old_body)) if a != b]
check("segment_speech is AST-identical to the original except the single flags line (segmentation loop untouched)",
      len(new_body) == len(old_body) and len(diff_idx) == 1 and new_body[diff_idx[0]] == flag_stmt
      and old_body[diff_idx[0]] == ast.dump(ast.parse(ORIGINAL_FLAGS).body[0]), diff_idx)
off_branch = method_ast(new_src, "VAD", "_classify").body[0]
check("the OFF branch of _classify is exactly the original expression, reached by `if not self.cache_classifications`",
      isinstance(off_branch, ast.If) and ast.unparse(off_branch.test) == "not self.cache_classifications"
      and ast.dump(off_branch.body[0].value) == ast.dump(ast.parse(ORIGINAL_FLAGS).body[0].value) and len(off_branch.body) == 1)
check("_frames and total_ms are AST-identical to the original",
      all(ast.dump(method_ast(new_src, "VAD", m)) == ast.dump(method_ast(old_src, "VAD", m)) for m in ("_frames", "total_ms")))
new_sig, old_sig = inspect.signature(VAD.__init__), inspect.signature(orig.VAD.__init__)
check("constructor: original parameters keep their order and defaults; the only new one is keyword cache_classifications=False, last",
      list(new_sig.parameters)[:-1] == list(old_sig.parameters)
      and all(new_sig.parameters[p].default == old_sig.parameters[p].default for p in old_sig.parameters)
      and list(new_sig.parameters)[-1] == "cache_classifications" and new_sig.parameters["cache_classifications"].default is False)
init_new = [ast.dump(s) for s in method_ast(new_src, "VAD", "__init__").body[1:]]  # [0] = docstring
init_old = [ast.dump(s) for s in method_ast(old_src, "VAD", "__init__").body[1:]]
check("constructor keeps the original statements first, unchanged; the added ones only assign ON-mode state",
      init_new[:len(init_old)] == init_old
      and all(isinstance(s, ast.Assign) for s in method_ast(new_src, "VAD", "__init__").body[1 + len(init_old):]))
check("module constants unchanged (SAMPLE_RATE, FRAME_MS, FRAME_BYTES)",
      (orig.SAMPLE_RATE, orig.FRAME_MS, orig.FRAME_BYTES) == (16_000, 30, 960) and (FRAME_MS, FRAME_BYTES) == (orig.FRAME_MS, orig.FRAME_BYTES))
a_off = VAD()
check("a default VAD() constructs its webrtcvad classifier exactly as before (same type, aggressiveness path)",
      type(a_off._vad) is type(orig.VAD()._vad) and (a_off.pre_roll_frames, a_off.post_roll_frames, a_off.max_segment_frames)
      == (lambda o: (o.pre_roll_frames, o.post_roll_frames, o.max_segment_frames))(orig.VAD()))

print("-- OFF mode == original implementation (behaviour)")
rng = random.Random(1234)
bad = []
for trial in range(300):
    n = rng.randint(0, 900)
    flags = [rng.random() < p for p in [rng.choice((0.05, 0.3, 0.7, 0.97))] * n]
    pcm = sc.scripted_pcm([(f, FRAME_MS) for f in flags]) + bytes(rng.randint(0, FRAME_BYTES - 1))  # random partial tail
    kw = dict(pre_roll_ms=rng.choice((0, 60, 1500)), post_roll_ms=rng.choice((0, 60, 1500)), max_segment_ms=rng.choice((300, 3000, 8000)))
    a, b = VAD(**kw), orig.VAD(**kw)
    a._vad, b._vad = Counting(sc.ContentClassifier()), Counting(sc.ContentClassifier())
    if spans(a.segment_speech(pcm)) != spans(b.segment_speech(pcm)) or a._vad.seen != b._vad.seen:
        bad.append((trial, kw))
check("300 random flag patterns x roll/cap settings: identical segments and identical classifier calls", not bad, bad[:3])

bad = []
for name, pat in SCENARIOS.items():
    pcm = sc.scripted_pcm(pat)
    for c in CHUNKS:
        po, to = trace_stream(pcm, c, make(orig.VAD, classifier=sc.DriftClassifier))
        pf, tf = trace_stream(pcm, c, make(VAD, classifier=sc.DriftClassifier))
        if po != pf or to.trace != tf.trace or tf.vad._flag_cache or tf.vad.cache_resets:
            bad.append((name, c))
check(f"live loop, state-carrying classifier, {len(SCENARIOS)} scenarios x {len(CHUNKS)} chunks: OFF gives the original's "
      "every-call segments and STT spans (the current defect included) and never touches the cache", not bad, bad[:3])

v = VAD()
v._vad = sc.ContentClassifier()
pcm = sc.scripted_pcm(SCENARIOS["long gap between two utterances"])
v.segment_speech(pcm)
v.segment_speech(pcm[: len(pcm) // 2])  # a shrinking buffer is not special in OFF mode (as before)
check("OFF mode keeps no per-frame state and never resets (shrinking buffer handled exactly as before)",
      len(v._flag_cache) == 0 and v._flag_cache_last_frame == b"" and v.cache_resets == 0)

# OFF-mode return type of the per-frame flags is the original list[bool] (not the ON-mode bytearray)
v = VAD()
v._vad = sc.ContentClassifier()
fl = v._classify(list(v._frames(sc.scripted_pcm(SCENARIOS["one-frame speech"]))))
check("OFF: per-frame flags are the original list[bool] (ON-mode bytearray never reaches OFF segmentation)",
      type(fl) is list and all(type(x) is bool for x in fl))

# a state-carrying classifier with exotic truthy/falsy returns: OFF passes them through untouched, like the original
class Weird:
    def __init__(self):
        self.i = 0

    def is_speech(self, frame, sr):
        self.i += 1
        return (0, 1, "", "x", None, 2)[self.i % 6]


pcm = sc.scripted_pcm(SCENARIOS["long speech with forced 8 s cuts"])
a, b = VAD(), orig.VAD()
a._vad, b._vad = Weird(), Weird()
res_a = [spans(a.segment_speech(pcm[:e])) for e in range(0, len(pcm) + 1, 200 * 32)]
res_b = [spans(b.segment_speech(pcm[:e])) for e in range(0, len(pcm) + 1, 200 * 32)]
check("OFF: classifier returning non-bool truthy/falsy values across re-scans -> identical to the original", res_a == res_b)

# ----------------------------------------------------------------------------------------------------------- ON
print("-- ON mode == candidate D == one-shot segmentation")
bad_d, bad_ref = [], []
for name, pat in SCENARIOS.items():
    pcm = sc.scripted_pcm(pat)
    ref, speech = sc.reference_flags(pcm, sc.ContentClassifier)
    for c in CHUNKS:
        pd, td = trace_stream(pcm, c, lambda: sc.CandidateD(sc.DriftClassifier()))
        pn, tn = trace_stream(pcm, c, make(VAD, True, sc.DriftClassifier))
        if pd != pn or td.trace != tn.trace:
            bad_d.append((name, c))
        e = sc.evaluate(pn, ref, speech)
        if not (e["inv_no_reprocessing"] and e["inv_no_skipped_speech"] and e["inv_boundaries_equal_reference"]):
            bad_ref.append((name, c, e["excess_overlap_ms"], e["not_in_reference"][:2]))
check("ON == experiment candidate D: identical every-call segments and STT spans in all boundary cases", not bad_d, bad_d[:3])
check("ON: no re-processing, no skipped speech, boundaries == one-shot, in all boundary cases (drifting classifier)", not bad_ref, bad_ref[:3])

pcm = sc.scripted_pcm(SCENARIOS["long speech with forced 8 s cuts"])
ref, speech = sc.reference_flags(pcm, sc.ContentClassifier)
designed = sc.evaluate(ref, ref, speech)["designed_overlap_ms"]
got = [sc.evaluate(trace_stream(pcm, c, make(VAD, True, sc.DriftClassifier))[0], ref, speech)["overlap_ms"] for c in CHUNKS]
check(f"ON keeps the designed 8 s-cut overlap exactly ({designed} ms, > 0) at every chunk size", designed > 0 and all(g == designed for g in got), got)

print("-- ON mode: cache lifecycle")
pcm = sc.scripted_pcm(SCENARIOS["long gap between two utterances"])
n = len(pcm) // FRAME_BYTES
cnt = Counting(sc.ContentClassifier())
v = VAD(cache_classifications=True)
v._vad = cnt
for end in range(0, len(pcm) + 1, 7 * 32):  # 7 ms steps: almost every call ends in a partial frame
    v.segment_speech(pcm[:end])
v.segment_speech(pcm)
check("each complete frame classified exactly once, in order, across hundreds of re-scans",
      cnt.seen == list(range(n)), (len(cnt.seen), n))
check("partial tail frames are never classified early (cache holds complete frames only)", len(v._flag_cache) == n)
before = list(cnt.seen)
r1 = spans(v.segment_speech(pcm))
r2 = spans(v.segment_speech(pcm))
check("re-scanning an unchanged buffer classifies nothing and returns identical segments", cnt.seen == before and r1 == r2)
check("memory: one byte per complete frame (bytearray), nothing per call",
      isinstance(v._flag_cache, bytearray) and len(v._flag_cache) == n)
check("kept flags == a single fresh pass over the whole buffer",
      list(v._flag_cache) == [int(sc.ContentClassifier().is_speech(pcm[k * FRAME_BYTES:(k + 1) * FRAME_BYTES], 16000)) for k in range(n)])

records = []
h = logging.Handler()
h.emit = records.append
logging.getLogger("vad").addHandler(h)
v.segment_speech(pcm[: len(pcm) // 2])
shrink_ok = v.cache_resets == 1 and len(v._flag_cache) == (len(pcm) // 2) // FRAME_BYTES and records
check("buffer shrink (trimming is NOT supported): kept flags discarded, re-classified, logged, counted -- no crash", shrink_ok,
      (v.cache_resets, len(v._flag_cache), len(records)))
w = VAD(cache_classifications=True)
w._vad = sc.ContentClassifier()
w.segment_speech(pcm)
fresh = VAD()
fresh._vad = sc.ContentClassifier()
changed = bytearray(pcm)
k = len(pcm) // FRAME_BYTES - 1
changed[k * FRAME_BYTES] = 1 - changed[k * FRAME_BYTES]  # rewrite the last kept frame in place (same length)
out = spans(w.segment_speech(bytes(changed)))
check("in-place rewrite of the last kept frame detected: flags rebuilt, result == fresh segmentation of the new buffer",
      w.cache_resets == 1 and out == spans(fresh.segment_speech(bytes(changed))))
logging.getLogger("vad").removeHandler(h)
x = VAD(cache_classifications=True)
x._vad = Counting(sc.ContentClassifier())
x.segment_speech(pcm)
x.reset_classification_cache()
x.segment_speech(pcm)
check("explicit reset_classification_cache(): next scan classifies every frame again", x._vad.seen == list(range(n)) * 2)
j1, j2 = VAD(cache_classifications=True), VAD(cache_classifications=True)
check("no cross-instance (cross-journey) sharing of kept flags", j1._flag_cache is not j2._flag_cache)
check("empty and sub-frame buffers: no frames, no classification, no segments",
      VAD(cache_classifications=True).segment_speech(b"\x00" * (FRAME_BYTES - 1)) == [])

print("-- ON mode: determinism")
pcm = sc.scripted_pcm(SCENARIOS["frame-misaligned boundaries"])
runs = [trace_stream(pcm, 90, make(VAD, True, sc.DriftClassifier)) for _ in range(3)]
check("identical input -> identical every-call segments, STT spans and kept flags (3 runs)",
      all(r[0] == runs[0][0] and r[1].trace == runs[0][1].trace and r[1].vad._flag_cache == runs[0][1].vad._flag_cache for r in runs))

# ----------------------------------------------------------------------------------------------------------- real audio
print("-- real audio (webrtcvad + PyAV, else SKIP)")
try:
    import av  # noqa: F401
    import webrtcvad  # noqa: F401
    clips = [ROOT / "real_recordings" / "mixed" / f for f in ("clip_01_clean.mp3", "clip_19_muffled.mp3")]
    have = all(c.exists() for c in clips)
except ImportError:
    have = False
if not have:
    skip("real-audio OFF/ON checks", "needs webrtcvad + PyAV + real_recordings/mixed clips")
else:
    phrases = si.manifest_phrases()
    for clip in clips:
        audio = si.decode(clip)
        ref, speech = si.reference(audio)
        for c in (20, 250, 1000):
            po, to = trace_stream(audio, c, orig.VAD)
            pf, tf = trace_stream(audio, c, VAD)
            pn, tn = trace_stream(audio, c, lambda: VAD(cache_classifications=True))
            pd, td = trace_stream(audio, c, sc.CandidateD)
            e = sc.evaluate(pn, ref, speech)
            check(f"{clip.name} {c} ms: OFF == original (every call); ON == candidate D (every call, flags) == one-shot",
                  po == pf and to.trace == tf.trace and pn == pd and tn.trace == td.trace
                  and list(tn.vad._flag_cache) == [int(b) for b in td.vad._cache.flags]
                  and e["inv_boundaries_equal_reference"] and e["inv_no_reprocessing"] and e["inv_no_skipped_speech"], e)
    audio = si.decode(clips[1])
    ref, speech = si.reference(audio)
    ph = phrases[("mixed", "clip_19_muffled")]
    co = si.consequences(audio, 100, ph, speech, ns, vad_factory=orig.VAD)
    cf = si.consequences(audio, 100, ph, speech, ns, vad_factory=VAD)
    cn = si.consequences(audio, 100, ph, speech, ns, vad_factory=lambda: VAD(cache_classifications=True))
    check(f"alerts ('{ph}', 100 ms, real UDKEngine): OFF == original (incl. its repeat-induced TRIGGER_ALL); "
          "ON has no extra event and == one pass",
          [e[:4] for e in cf["stream_events"]] == [e[:4] for e in co["stream_events"]] and cf["repeat_induced_trigger_all"] >= 1
          and cn["extra_events"] == 0 and cn["repeat_induced_trigger_all"] == 0
          and [e[:2] for e in cn["stream_events"]] == [e[:2] for e in cn["oneshot_events"]], (cf["stream_events"], cn["stream_events"]))

print("\n" + "=" * 40)
print(f"{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "") + (" -- ALL PASSED" if not failed else f" -- {failed} FAILED"))
sys.exit(1 if failed else 0)
