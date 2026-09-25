"""Acoustic-only trigger: a sustained scream / cry / shout raises TRIGGER_VERIFY
("Are you safe?") even when no UDK words were heard -- the one thing word matching
can never catch. Opt-in in api.py via UDK_ENABLE_SCREAM_TRIGGER=1.

Validated 2026-09-24 (distress_detector/eval_combined.py; thresholds chosen on
calibration data -- real_recordings + FSD50K eval -- never on prepped_data):
  real screams 1/25 -> 11/25, real crying 5/25 -> 16/25, real distress media 5/7 -> 6/7,
  0 false alarms/hour on 18 min of long real speech; cost: a few alerts on loud happy
  sounds (cheering/crowd/laughter ~+1-3 of 25 each), 3/96 held-out prepped control runs
  (all the "Playful" clip). emotion2vec fear was tested as an extra trigger and rejected
  (it reads sirens as fear: 12-14/25 siren clips).

The rule must stay EXACTLY as validated: the 9 classes below, 2 s windows every 0.5 s,
max class probability >= 0.10 in 2 consecutive windows.
"""
from __future__ import annotations

import numpy as np

SR = 16_000
WIN, HOP = 2 * SR, SR // 2
THRESHOLD = 0.10
CONSECUTIVE = 2
# BEATs_iter3_finetuned_on_AS2M_cpt1 output index -> AudioSet class (resolved from the
# checkpoint's label_dict, same as distress_detector.config.ZERO_SHOT_CLASSES)
CLASSES = {34: "Screaming", 498: "Crying, sobbing", 81: "Whimper", 431: "Wail, moan", 410: "Groan",
           50: "Yell", 344: "Shout", 433: "Children shouting", 334: "Battle cry"}


def check(detector, pcm: bytes) -> tuple[bool, float, str]:
    """(fired, peak score, peak class) over one segment's 16 kHz int16 PCM, using the
    live BEATsDistressDetector's label_probs (no second model)."""
    n = len(pcm) // 2
    starts = range(0, max(n - WIN, 0) + 1, HOP) if n >= WIN else [0]
    run, peak, peak_cls, fired = 0, 0.0, "", False
    idx = list(CLASSES)
    for s in starts:
        probs = detector.label_probs(pcm[2 * s: 2 * (s + WIN)])
        vals = np.asarray(probs)[idx]
        v = float(vals.max())
        if v > peak:
            peak, peak_cls = v, CLASSES[idx[int(vals.argmax())]]
        run = run + 1 if v >= THRESHOLD else 0
        fired = fired or run >= CONSECUTIVE
    return fired, peak, peak_cls
