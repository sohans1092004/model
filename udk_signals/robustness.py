"""Condition signal: is this audio degraded (quiet / low SNR / clipped / muffled)?

ConditionEstimator.estimate(x, sr) -> Evidence(kind="condition"):
  POSITIVE (degraded, with flags), NEGATIVE (no degradation measured), UNAVAILABLE (too short).
Thresholds are explicit configuration (no defaults; configs/*.json). Muffling = low high-band /
voice-band energy ratio (pocket / bag / far-field all remove high frequencies). These measurements
support robustness evaluation and let fusion treat NEGATIVE evidence from other signals as
UNCERTAIN on degraded audio -- they never raise or lower an alert by themselves.
"""
from __future__ import annotations

from udk_signals.dsp import band_power, clipping_ratio, dbfs, snr_estimate_db
from udk_signals.evidence import NEGATIVE, POSITIVE, Evidence, unavailable

VOICE_BAND = tuple(range(100, 901, 10))   # dense grids: single-frequency probes depend on where harmonics fall
HIGH_BAND = tuple(range(2000, 3501, 50))


class ConditionEstimator:
    source = "dsp-condition-estimator/1"

    def __init__(self, cfg: dict):
        need = ("min_duration_s", "quiet_dbfs", "low_snr_db", "clipping_ratio", "muffled_hf_ratio")
        missing = [k for k in need if k not in cfg]
        if missing:
            raise ValueError(f"condition config needs {missing}")
        self.cfg = cfg

    def estimate(self, x, sr: int, start_s: float | None = None, end_s: float | None = None) -> Evidence:
        c = self.cfg
        if len(x) < c["min_duration_s"] * sr:
            return unavailable("condition", self.source, "segment too short to measure")
        level, clip, snr = dbfs(x), clipping_ratio(x), snr_estimate_db(x, sr)
        voice = band_power(x, sr, VOICE_BAND)
        hf = band_power(x, sr, [f for f in HIGH_BAND if f < sr / 2])
        hf_ratio = hf / voice if voice > 0 else None
        flags = []
        if level < c["quiet_dbfs"]:
            flags.append("quiet")
        if snr is not None and snr < c["low_snr_db"]:
            flags.append("low_snr")
        if clip >= c["clipping_ratio"]:
            flags.append("clipping")
        if hf_ratio is not None and hf_ratio < c["muffled_hf_ratio"]:
            flags.append("muffled")
        return Evidence("condition", POSITIVE if flags else NEGATIVE, self.source,
                        "degraded: " + ", ".join(flags) if flags else "no degradation measured",
                        start_s=start_s, end_s=end_s,
                        detail={"flags": flags, "level_dbfs": round(level, 2), "snr_db_est": None if snr is None else round(snr, 2),
                                "clipping_ratio": round(clip, 4), "hf_voice_ratio": None if hf_ratio is None else round(hf_ratio, 5)})
