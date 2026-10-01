"""
Run custom UDK test on prepped_data (enrollment + test from same dataset)
Uses UDK_03 clips for enrollment, tests on all clips
"""
import re, json, warnings, os, sys, glob
import numpy as np
import librosa
from rapidfuzz import fuzz
import torch
from faster_whisper import WhisperModel

warnings.filterwarnings("ignore")

SR, WHISPER_MODEL = 16000, "small.en"

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
    return float(np.median([dtw_cost(t, seg_f) for t in tpls])) if tpls else 0

def stt_whisper(y, whisper):
    segs, _ = whisper.transcribe(y.astype(np.float32), language="en", beam_size=5, vad_filter=False)
    return norm(" ".join(s.text for s in segs))

def build_profile(raw, transcripts):
    F = [feats(librosa.effects.trim(y, top_db=30)[0]) for y in raw]
    n = len(F)
    variants = sorted({ts for ts in transcripts if ts})
    first = [ts for ts in transcripts if ts]
    sims = [fuzz.ratio(a, b) for i, a in enumerate(first) for b in first[i+1:]]
    stab = float(np.mean(sims)) if sims else 0.0
    medoid = max(first, key=lambda a: sum(fuzz.ratio(a, b) for b in first)) if first else ""
    loo = [audio_score(F[i], [F[j] for j in range(n) if j != i]) for i in range(n)]
    return {
        "variants": variants, "phrase": medoid, "text_stability": stab,
        "audio_thr": max(loo) * 1.03 if loo else 0, "tpls": F,
        "ok": bool(len(medoid.split()) >= 2 and len(medoid) <= 80 and stab >= 60)
    }

def detect(y, transcripts, prof):
    tx = [norm(t) for t in [transcripts] if t]
    text_hit = any(re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", t) for t in tx for v in prof["variants"])
    return int(text_hit)

# Main
print("Loading Whisper...")
whisper = WhisperModel(WHISPER_MODEL, device="cuda" if torch.cuda.is_available() else "cpu",
                       compute_type="float16" if torch.cuda.is_available() else "int8")

prepped_dir = "prepped_data"
if not os.path.isdir(prepped_dir):
    print(f"ERROR: {prepped_dir}/ not found")
    sys.exit(1)

# Enrollment: use UDK_03 clips
all_files = sorted(glob.glob(os.path.join(prepped_dir, "*.mp3")))
enrol_files = [f for f in all_files if "UDK_03" in f][:4]
test_files = all_files

if not enrol_files:
    print(f"WARNING: No UDK_03 clips found, using first 4 clips as enrollment")
    enrol_files = all_files[:4]

print(f"\n=== ENROLLMENT ===")
print(f"Using {len(enrol_files)} clips:")
raw = []
for p in enrol_files:
    try:
        y = load(p)
        raw.append(y)
        tx = stt_whisper(y, whisper)
        print(f"  {os.path.basename(p)[:60]:60s} -> {tx[:60]}")
    except Exception as e:
        print(f"  {os.path.basename(p)[:60]:60s} -> ERROR: {str(e)[:30]}")

if raw:
    tr = [stt_whisper(y, whisper) for y in raw]
    prof = build_profile(raw, tr)
    print(f"\nPhrase: {prof['phrase']}")
    print(f"Variants: {prof['variants']}")
    print(f"Stability: {prof['text_stability']:.0f}% | ok: {prof['ok']}")

    if not prof["ok"]:
        print("REJECT: inconsistent enrollment")
        sys.exit(1)

    # Test
    print(f"\n=== TEST ({len(test_files)} clips) ===")
    results = []
    for p in test_files:
        try:
            y = load(p)
            tx = stt_whisper(y, whisper)
            det = detect(y, tx, prof)
            results.append({
                "file": os.path.basename(p),
                "detected": det,
                "transcript": tx[:80]
            })
            marker = "[OK]" if det else "[NO]"
            print(f"{marker} {os.path.basename(p)[:60]:60s} {det} | {tx[:45]}")
        except Exception as e:
            print(f"[ER] {os.path.basename(p)[:60]:60s} ERROR")

    # Summary
    detected = sum(1 for r in results if r["detected"])
    print(f"\n=== RESULTS ===")
    print(f"Detected: {detected}/{len(results)}")

    # Save
    with open("test_results_prepped.json", "w") as f:
        json.dump({
            "enrollment": [os.path.basename(p) for p in enrol_files],
            "phrase": prof["phrase"],
            "results": results
        }, f, indent=2)

    print(f"[OK] Saved: test_results_prepped.json")
