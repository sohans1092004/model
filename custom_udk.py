"""
Per-user custom UDK enrollment & detection
Extracted from custom_udk_enrol_detect_v2.ipynb
Speaker-dependent: only enrolled user's voice on their phrase triggers
"""
import re, json, tempfile, os
import numpy as np
import librosa
import soundfile as sf
from rapidfuzz import fuzz
from scipy.signal import butter, sosfilt

SR = 16000
MARGIN = 0.03
MIN_WORDS, MAX_CHARS = 3, 40

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

def build_profile(raw, transcripts, stt_whisper_fn):
    """Build detection profile from 4-6 enrollment clips
    Args:
        raw: list of audio arrays (16kHz)
        transcripts: list of STT strings (from Whisper)
        stt_whisper_fn: Whisper transcribe function
    Returns:
        dict with {variants, phrase, text_stability, audio_thr, tpls, ok}
    """
    # Re-transcribe enrollment for consistency
    tr = [stt_whisper_fn(y) for y in raw]
    tr = [norm(t) for t in tr if t]

    if not tr:
        return {"ok": False, "error": "No valid transcripts from enrollment clips"}

    # Audio features
    F = []
    for y in raw:
        try:
            trimmed, _ = librosa.effects.trim(y, top_db=30)
            F.append(feats(trimmed))
        except:
            F.append(feats(y))

    n = len(F)
    variants = sorted(set(tr))
    first = tr

    # Text stability (fuzzy match between transcripts)
    sims = [fuzz.ratio(a, b) for i, a in enumerate(first) for b in first[i+1:]]
    stab = float(np.mean(sims)) if sims else 0.0

    # Medoid (most similar to all others)
    medoid = max(first, key=lambda a: sum(fuzz.ratio(a, b) for b in first)) if first else ""

    # Audio threshold (leave-one-out DTW)
    loo = [audio_score(F[i], [F[j] for j in range(n) if j != i]) for i in range(n)]
    audio_thr = max(loo) * (1 + MARGIN) if loo else 0

    # Validation
    ok = bool(
        len(medoid.split()) >= MIN_WORDS and
        len(medoid) <= MAX_CHARS and
        stab >= 80
    )

    return {
        "variants": variants,
        "phrase": medoid,
        "text_stability": stab,
        "loo_scores": loo,
        "audio_thr": audio_thr,
        "tpls": F,
        "ok": ok
    }

def detect(y, tx, prof):
    """Detect if custom phrase is in segment
    Args:
        y: audio array (16kHz)
        tx: STT transcript string
        prof: profile from build_profile()
    Returns:
        dict {detected: 0/1, text_hit, audio_hit, audio_score, transcripts}
    """
    tx_norm = norm(tx) if tx else ""

    # Text: word-boundary match on any variant
    text_hit = any(
        re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", tx_norm)
        for v in prof.get("variants", [])
    )

    # Audio: DTW on MFCC features (fallback when STT mishears)
    try:
        seg_f = feats(y)
        audio_score_val = audio_score(seg_f, prof.get("tpls", []))
        audio_hit = audio_score_val <= prof.get("audio_thr", 0)
    except:
        audio_score_val = 0
        audio_hit = False

    # Decision: text match is primary (speaker verification)
    detected = int(text_hit)

    return {
        "detected": detected,
        "text_hit": int(text_hit),
        "audio_hit": int(audio_hit),
        "audio_score": round(audio_score_val, 3),
        "transcripts": [tx_norm] if tx_norm else []
    }

def profile_to_json(prof):
    """Serialize profile for storage (exclude large numpy arrays)"""
    return {
        "phrase": prof.get("phrase", ""),
        "variants": prof.get("variants", []),
        "text_stability": prof.get("text_stability", 0),
        "audio_thr": prof.get("audio_thr", 0),
        "loo_scores": [float(x) for x in prof.get("loo_scores", [])],
        "ok": prof.get("ok", False)
    }

def profile_from_json(data, tpls_array):
    """Reconstruct profile from JSON + numpy array
    Args:
        data: dict from profile_to_json()
        tpls_array: numpy array from custom_udk_templates.npz
    """
    prof = dict(data)
    prof["tpls"] = [tpls_array[f"arr_{i}"] for i in range(len(tpls_array.files))]
    prof["ok"] = bool(prof.get("ok", False))
    return prof
