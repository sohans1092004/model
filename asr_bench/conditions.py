"""Synthetic robustness subsets (Phase 2A §4 "Synthetic recipe (labelled)"; stage S8).

Each recipe turns a manifest row (and, where needed, licence-clean noise or other-speaker speech)
into a NEW audio file and a NEW manifest row labelled condition_real_or_synthetic="synthetic"
with aug_recipe + an integer seed (§3). A synthetic result never stands in for a real one (§4).

  traffic   : speech + noise at snr_db            -> environment traffic, snr_db set
  crowd     : speech + babble from >=2 other rows -> environment crowd, snr_db set
  low_snr   : speech + noise at 5 / 0 / -5 dB     -> snr_db set (the "low_snr" subset is <= 0 dB)
  clipping  : hard clip at a fraction of peak     -> clipping_ratio MEASURED on the output
  phone     : 300-3400 Hz band-limit              -> condition_device phone_call (codec: not applied, M-3)
  pocket    : low-pass 1500 Hz, -6 dB (as Phase 0 audio_augment.muffle) -> condition_device pocket
  overlap   : target + other speaker, target at 0 / -6 / -12 dB relative to the other voice
              -> overlap true, overlap_rel_db = other relative to target (= -target_rel_db)

Leakage and licences: a derived row keeps the source row's speaker/session/recording IDs and
split (augmented copies stay in one group, Phase 1 §19). Other-speaker/babble rows must be in the
SAME split. Noise and speech inputs are manifest rows, so they already passed the registry gate;
the derived row's use_restriction is the strictest of all inputs (P-S2-3 order) and its licence
names every input. R-6 (FSD50K "noise mixes only") is exactly this use.
numpy and scipy are needed (the production stack already uses them); nothing is downloaded.
"""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

from asr_bench.adapters import RESTRICTION_ORDER
from asr_bench.audio_meta import read_audio_metadata
from asr_bench.schema import FIELDS, validate_row

RECIPES = ("traffic", "crowd", "low_snr", "clipping", "phone", "pocket", "overlap")


class ConditionError(ValueError):
    pass


def _np():
    import numpy as np
    return np


def read_wav_float(path: Path):
    """(mono float32 array, rate). PCM-16 WAV only: derived audio is always written that way."""
    np = _np()
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ConditionError(f"{path}: only 16-bit PCM WAV inputs are supported for synthesis")
        ch, rate, data = w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())
    x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    return (x.reshape(-1, ch).mean(axis=1) if ch > 1 else x), rate


def write_wav(path: Path, x, rate: int) -> None:
    np = _np()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def derived_seed(base_seed: int, utt_id: str, recipe: str) -> int:
    return int(hashlib.sha256(f"{base_seed}\x1f{utt_id}\x1f{recipe}".encode()).hexdigest()[:8], 16)


def _fit(x, n: int, rng):
    """Loop/trim `x` to length n from a seeded offset."""
    np = _np()
    if len(x) == 0:
        raise ConditionError("empty noise/speech input")
    reps = int(np.ceil((n + len(x)) / len(x)))
    tiled = np.tile(x, reps)
    start = int(rng.integers(0, len(x)))
    return tiled[start:start + n]


def _resample(x, src: int, dst: int):
    if src == dst:
        return x
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(src, dst)
    return resample_poly(x, dst // g, src // g).astype("float32")


def _rms(x) -> float:
    np = _np()
    return float(np.sqrt(np.mean(np.square(x)))) + 1e-12


def mix_at_snr(speech, noise, snr_db: float):
    return speech + noise * (_rms(speech) / (_rms(noise) * 10 ** (snr_db / 20)))


def synthesize(recipe: str, speech, rate: int, params: dict, seed: int, others: list | None = None):
    """(audio, updates to the derived row)."""
    np = _np()
    rng = np.random.default_rng(seed)
    if recipe in ("traffic", "low_snr"):
        noise = _fit(_resample(others[0][0], others[0][1], rate), len(speech), rng)
        out = mix_at_snr(speech, noise, params["snr_db"])
        upd = {"snr_db": float(params["snr_db"])}
        if recipe == "traffic":
            upd["environment"] = "traffic"
        return out, upd
    if recipe == "crowd":
        if len(others) < 2:
            raise ConditionError("crowd babble needs speech from at least 2 other rows")
        babble = sum(_fit(_resample(x, r, rate), len(speech), rng) for x, r in others)
        return mix_at_snr(speech, babble, params["snr_db"]), {"environment": "crowd", "snr_db": float(params["snr_db"])}
    if recipe == "clipping":
        lim = float(np.max(np.abs(speech))) * params["clip_level"]
        out = np.clip(speech, -lim, lim)
        return out, {"clipping_ratio": float(np.mean(np.abs(speech) >= lim)) if lim > 0 else 0.0}
    if recipe == "phone":
        from scipy.signal import butter, sosfiltfilt
        sos = butter(4, [300, 3400], btype="band", fs=rate, output="sos")
        return sosfiltfilt(sos, speech).astype("float32"), {"condition_device": "phone_call"}
    if recipe == "pocket":
        from scipy.signal import butter, sosfiltfilt
        sos = butter(4, 1500, btype="low", fs=rate, output="sos")
        return (sosfiltfilt(sos, speech) * 10 ** (-6 / 20)).astype("float32"), {"condition_device": "pocket"}
    if recipe == "overlap":
        other = _resample(others[0][0], others[0][1], rate)
        n = max(len(speech), len(other))
        t = np.pad(speech, (0, n - len(speech)))
        o = np.pad(other, (0, n - len(other)))
        target_rel_db = float(params["target_rel_db"])
        o = o * (_rms(speech) / (_rms(other) * 10 ** (target_rel_db / 20)))
        both = min(len(speech), len(other)) / rate
        return (t + o) * 0.5, {"overlap": True, "overlap_rel_db": -target_rel_db,
                               "overlap_spans": [{"start_s": 0.0, "end_s": round(both, 6)}]}
    raise ConditionError(f"unknown recipe {recipe!r}; one of {RECIPES}")


def recipe_string(recipe: str, params: dict, inputs: list[str]) -> str:
    return f"{recipe}:" + json.dumps({**params, "inputs": inputs}, sort_keys=True, separators=(",", ":"))


def derive_row(row: dict, recipe: str, params: dict, *, base_seed: int, roots: dict, inputs: list[dict] = ()) -> dict:
    """A new synthetic manifest row from real `row`. `inputs` are MANIFEST ROWS (noise clips or
    other speakers), so their licence/use_restriction already passed the registry gate (incl.
    per-clip licences). Speech inputs must share `row`'s split; no-speech inputs (transcript_ref
    "") are noise. Audio is written under the SOURCE's root (roots[source_dataset]/synthetic/),
    where the runner looks for it."""
    if row.get("condition_real_or_synthetic") != "real":
        raise ConditionError(f"{row['utt_id']}: only real rows are augmented")
    for other in inputs:
        if other.get("transcript_ref") and other.get("split") != row.get("split"):
            raise ConditionError(f"{row['utt_id']}: other-speaker input {other['utt_id']} is in split {other.get('split')!r}, "
                                 f"not {row.get('split')!r} (its speaker would leak across splits)")

    def path_of(r):
        root = roots.get(r["source_dataset"])
        if root is None:
            raise ConditionError(f"no audio root for source {r['source_dataset']!r}")
        return Path(root) / r["audio_path"]

    tag = recipe + "".join(f"_{k}{v}" for k, v in sorted(params.items()))
    utt_id = f"{row['utt_id']}~{tag}"
    seed = derived_seed(base_seed, row["utt_id"], tag)
    speech, rate = read_wav_float(path_of(row))
    audio, upd = synthesize(recipe, speech, rate, params, seed, [read_wav_float(path_of(o)) for o in inputs])
    rel = Path("synthetic") / (utt_id.replace(":", "_").replace("~", "__") + ".wav")
    out = Path(roots[row["source_dataset"]]) / rel
    if out.exists():
        raise ConditionError(f"{out} exists; refusing to overwrite derived audio")
    write_wav(out, audio, rate)
    meta = read_audio_metadata(out)
    restriction = max([row["use_restriction"]] + [o["use_restriction"] for o in inputs], key=lambda u: RESTRICTION_ORDER[u])
    new = {**row, **upd, "utt_id": utt_id, "audio_path": rel.as_posix(), "audio_sha256": meta.audio_sha256,
           "sample_rate_hz": meta.sample_rate_hz, "duration_s": meta.duration_s, "channels": meta.channels,
           "condition_real_or_synthetic": "synthetic",
           "aug_recipe": recipe_string(recipe, params, [o["utt_id"] for o in inputs]), "seed": seed,
           "use_restriction": restriction, "licence": row["licence"] + "".join(f" + {o['utt_id']}: {o['licence']}" for o in inputs)}
    new = {f: new[f] for f in FIELDS} | {k: v for k, v in new.items() if k not in FIELDS}
    errors = [i for i in validate_row(new) if i.level == "error"]
    if errors:
        out.unlink()
        raise ConditionError(f"{utt_id}: derived row invalid: " + "; ".join(str(i) for i in errors))
    return new
