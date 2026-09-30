"""Acoustic distress signal interface.

  AcousticDistressSource (protocol)  assess(...) -> [Evidence(kind="acoustic_distress")].
  BeatsScreamSignal                  the LIVE BEATs path, wrapped -- not trusted blindly:
     * 4-class scream trigger fired (scream_trigger.check)   -> POSITIVE, source "beats_4class_scream_trigger",
       reliability "unverified" with the Phase 0 false-alarm sources attached (media / gameplay screams:
       2.4/h sealed, 18.7/h gameplay; cheering, crowd, laughter).
     * not fired                                              -> UNCERTAIN, never NEGATIVE: the rule misses
       28/57 real distress sounds and scores frightened speech ~0.02 (Phase 0 §9).
     * 9-class corroboration score (detector.score)           -> POSITIVE if >= 0.30 (live corroboration
       threshold), else UNCERTAIN; source "beats_9class_corroboration".
     * audio outside VAD segments / no detector               -> UNAVAILABLE (Phase 0: never analysed).
  fixtures.FixtureAcousticSource                              TEST ONLY.
"""
from __future__ import annotations

from typing import Protocol

from udk_signals.evidence import POSITIVE, UNCERTAIN, Evidence, unavailable

LIVE_CORROBORATION_THRESHOLD = 0.30  # beats_distress_detector.DISTRESS_SCORE_THRESHOLD at 96ea038
KNOWN_FALSE_ALARM_SOURCES = ("recorded screams in media / video games (2.4/h sealed, 18.7/h gameplay)",
                             "cheering, crowd, laughter (1-3 of ~25 each in calibration)")


class AcousticDistressSource(Protocol):
    source_id: str

    def assess(self, pcm: bytes | None, in_vad_segment: bool, start_s=None, end_s=None) -> list[Evidence]: ...


class BeatsScreamSignal:
    source_id = "beats_iter3_as2m (live, 96ea038)"

    def __init__(self, detector=None):
        self.detector = detector  # beats_distress_detector.BEATsDistressDetector, or None

    def assess(self, pcm: bytes | None, in_vad_segment: bool, start_s=None, end_s=None) -> list[Evidence]:
        if self.detector is None:
            return [unavailable("acoustic_distress", "beats_4class_scream_trigger", "BEATs detector not loaded"),
                    unavailable("acoustic_distress", "beats_9class_corroboration", "BEATs detector not loaded")]
        if not in_vad_segment or not pcm:
            return [unavailable("acoustic_distress", "beats_4class_scream_trigger", "audio outside VAD segments is never analysed"),
                    unavailable("acoustic_distress", "beats_9class_corroboration", "audio outside VAD segments is never analysed")]
        import scream_trigger
        fired, peak, cls = scream_trigger.check(self.detector, pcm)
        trig = Evidence("acoustic_distress", POSITIVE if fired else UNCERTAIN, "beats_4class_scream_trigger",
                        f"4-class rule {'fired' if fired else 'did not fire'} (peak {peak:.3f} {cls})", score=peak,
                        start_s=start_s, end_s=end_s,
                        detail={"class": cls, "reliability": "unverified", "known_false_alarm_sources": KNOWN_FALSE_ALARM_SOURCES,
                                "absence_is_not_evidence": "misses 28/57 real distress sounds (Phase 0 §9)"})
        s9 = float(self.detector.score(pcm))
        corr = Evidence("acoustic_distress", POSITIVE if s9 >= LIVE_CORROBORATION_THRESHOLD else UNCERTAIN,
                        "beats_9class_corroboration", f"9-class vocal score {s9:.3f} vs {LIVE_CORROBORATION_THRESHOLD}",
                        score=s9, start_s=start_s, end_s=end_s, detail={"reliability": "unverified"})
        return [trig, corr]
