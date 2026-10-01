"""
Custom UDK Detection — Test on Your Project Datasets
Extracted from custom_udk_enrol_detect_v2.ipynb
Runs on prepped_data/, real_world/, real_recordings/ your project has
"""
import re, json, warnings, os, sys, glob
import numpy as np
import librosa
import soundfile as sf
from rapidfuzz import fuzz
from scipy.signal import butter, sosfilt
import torch
from faster_whisper import WhisperModel

warnings.filterwarnings("ignore")

SR, MODE, WHISPER_MODEL, USE_PARAKEET, MIN_WORDS, MAX_CHARS, MARGIN = (
    16000, "text", "small.en", True, 3, 40, 0.03
)

def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9ఀ-౿ ]", "", t.lower())).strip()

def load(path):
    y, _ = librosa.load(path, sr=SR, mono=True)
    return (y / (np.max(np.abs(y)) + 1e-9) * 0.5).astype(np.float32)

def feats(y):
    y = y / (np.max(np.abs(y)) + 1e-9)
    m = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=13, n_fft=400, hop_length=160)
    d = librosa.feature.delta(m)
    f = np.vstack([m[1:], d[1:]])
    return (f - f.mean(1, keepdims=True)) / (f.std(1, keepdims=True) + 1e-9)

def dtw_cost(tpl, seg):
    D, _ = librosa.sequence.dtw(X=tpl, Y=seg, subseq=True, metric="cosine")
    return D[-1, :].min() / tpl.shape[1]

def audio_score(seg_f, tpls):
    return float(np.median([dtw_cost(t, seg_f) for t in tpls]))

def init_whisper():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel(WHISPER_MODEL, device=dev, compute_type="float16" if dev == "cuda" else "int8")

_whisper, _parakeet = None, None

def stt_whisper(y, w):
    segs, _ = w.transcribe(y.astype(np.float32), language="en", beam_size=5, vad_filter=False)
    return norm(" ".join(s.text for s in segs))

def stt_parakeet(y):
    global _parakeet
    if _parakeet is None:
        try:
            import nemo.collections.asr as nemo_asr
            _parakeet = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
        except Exception as e:
            return ""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, y, SR)
    try:
        out = _parakeet.transcribe([f.name])
        t = out[0].text if hasattr(out[0], "text") else out[0]
        return norm(t)
    finally:
        os.unlink(f.name)

def stt_all(y, w):
    out = [stt_whisper(y, w)]
    if USE_PARAKEET:
        p = stt_parakeet(y)
        if p: out.append(p)
    return out

def build_profile(raw, transcripts):
    F = [feats(librosa.effects.trim(y, top_db=30)[0]) for y in raw]
    n = len(F)
    variants = sorted({ts[0] for ts in transcripts if ts})
    first = [ts[0] for ts in transcripts if ts]
    sims = [fuzz.ratio(a, b) for i, a in enumerate(first) for b in first[i+1:]]
    stab = float(np.mean(sims)) if sims else 0.0
    medoid = max(first, key=lambda a: sum(fuzz.ratio(a, b) for b in first)) if first else ""
    loo = [audio_score(F[i], [F[j] for j in range(n) if j != i]) for i in range(n)]
    return {
        "variants": variants, "phrase": medoid, "text_stability": stab,
        "loo_scores": loo, "audio_thr": max(loo) * (1 + MARGIN) if loo else 0,
        "tpls": F, "ok": bool(len(medoid.split()) >= MIN_WORDS and len(medoid) <= MAX_CHARS and stab >= 80)
    }

def detect_core(y, transcripts, prof):
    tx = [norm(t) for t in transcripts if t]
    text_hit = any(re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", t) for t in tx for v in prof["variants"])
    s = audio_score(feats(y), prof["tpls"])
    audio_hit = s <= prof["audio_thr"]
    hit = text_hit if MODE == "text" else (text_hit or audio_hit if MODE == "or" else text_hit and audio_hit)
    return {
        "detected": int(hit), "text_hit": int(text_hit), "audio_hit": int(audio_hit),
        "audio_score": round(s, 3), "transcripts": tx
    }

def main():
    sample_only = "--sample-only" in sys.argv
    print("Loading Whisper model...")
    whisper = init_whisper()

    # Enrollment: look in Downloads for your custom clips (your 4-6 enrollment files)
    enrol_dir = os.path.expanduser("~/Downloads")
    enrol_files = sorted(glob.glob(os.path.join(enrol_dir, "Masjid Banda Road [5-9]*.m4a")))[:5]

    if not enrol_files:
        print("ERROR: No enrollment clips found in ~/Downloads/")
        print("  Place your 4-6 custom UDK phrase clips there (e.g., 'Masjid Banda Road 58.m4a')")
        return

    print(f"\nEnrollment: {len(enrol_files)} clips")
    raw = [load(p) for p in enrol_files]
    tr = [[stt_whisper(y, whisper)] + ([stt_parakeet(y)] if USE_PARAKEET else []) for y in raw]
    tr = [[t for t in ts if t] for ts in tr]
    for p, t in zip(enrol_files, tr):
        print(f"  {os.path.basename(p)} -> {t}")

    prof = build_profile(raw, tr)
    print(f"\nPhrase: {prof['phrase']}")
    print(f"Stability: {prof['text_stability']:.0f}% | ok: {prof['ok']}")

    if not prof["ok"]:
        print("REJECT: re-record enrollment clips (need ≥3 words, ≤40 chars, ≥80% stability)")
        return

    # Test: look in your project's existing datasets
    test_sources = [
        ("prepped_data", "Prepared test dataset"),
        ("real_world", "Real-world recordings"),
        ("real_recordings/mixed", "Mixed real recordings"),
    ]

    test_files, test_source = [], None
    for src, desc in test_sources:
        if os.path.isdir(src):
            found = sorted(glob.glob(os.path.join(src, "*.mp3"))) + sorted(glob.glob(os.path.join(src, "*.wav")))
            if found:
                test_files = found[:10 if sample_only else len(found)]
                test_source = f"{src} ({desc})"
                break

    if not test_files:
        print(f"\nWARNING: No test data in prepped_data/, real_world/, or real_recordings/mixed/")
        print("  Skipping test phase.")
        return

    print(f"\nTesting on {len(test_files)} clips from {test_source}:")
    results = []
    for p in test_files:
        try:
            y = load(p)
            tx = stt_all(y, whisper)
            res = detect_core(y, tx, prof)
            results.append({"file": os.path.basename(p), "detected": res["detected"],
                          "transcripts": res["transcripts"], "audio_score": res["audio_score"]})
            marker = "✓" if res["detected"] else "✗"
            print(f"{marker} {os.path.basename(p)[:55]:55s} {res['detected']} | {res['transcripts'][:1] if res['transcripts'] else '(silence)'}")
        except Exception as e:
            print(f"✗ {os.path.basename(p)[:55]:55s} ERROR: {str(e)[:40]}")

    detected = sum(1 for r in results if r["detected"])
    print(f"\nResults: {detected}/{len(results)} detected")

    # Save outputs
    with open("custom_udk_profile.json", "w") as f:
        meta = {k: prof[k] for k in ["variants", "phrase", "text_stability", "loo_scores", "audio_thr", "ok"]}
        json.dump(meta, f, indent=2)
    np.savez("custom_udk_templates.npz", *prof["tpls"])
    with open("test_results.json", "w") as f:
        json.dump({"phrase": prof["phrase"], "test_source": test_source, "results": results}, f, indent=2)

    print(f"✓ Saved: custom_udk_profile.json, test_results.json, custom_udk_templates.npz")

if __name__ == "__main__":
    main()
