"""Phase 4 evidence for one observed segment, built from values the live path already computed.

BEATs: same states and sources as udk_signals.acoustic.BeatsScreamSignal (the live 4-class trigger result
and the live 9-class score are reused; BEATs is NOT run a second time):
  4-class  fired -> POSITIVE; ran and did not fire -> UNCERTAIN (never NEGATIVE); not enabled / not loaded ->
           UNAVAILABLE.
  9-class  score >= udk_signals.acoustic.LIVE_CORROBORATION_THRESHOLD -> POSITIVE, else UNCERTAIN; score None ->
           UNAVAILABLE (flag off, or segment skipped before it was computed). None is never 0.
Speaker / target speaker / overlap: UNAVAILABLE (no approved embedder S-1, no overlap detector S-2). No
speaker label is ever produced here.
Condition: UNAVAILABLE (not computed in shadow: pure-Python DSP over the segment costs too much and the
thresholds are provisional, S-5).
Every item carries the contract's join fields in `detail`: segment_id, clock="journey_audio_ms", start_ms, end_ms.
"""
from __future__ import annotations

from udk_signals.acoustic import KNOWN_FALSE_ALARM_SOURCES, LIVE_CORROBORATION_THRESHOLD
from udk_signals.evidence import POSITIVE, UNAVAILABLE, UNCERTAIN, Evidence

T4, T9 = "beats_4class_scream_trigger", "beats_9class_corroboration"
ATTRIBUTION_NAMESPACE = None  # no approved embedder (S-1): no clustering run exists, so no namespace


def _join(obs) -> dict:
    return {"segment_id": obs.segment_id, "clock": "journey_audio_ms", "start_ms": obs.start_ms, "end_ms": obs.end_ms}


def _ev(obs, kind, state, source, reason, score=None, **detail) -> Evidence:
    return Evidence(kind, state, source, reason, score=score, start_s=obs.start_ms / 1000.0, end_s=obs.end_ms / 1000.0,
                    detail={**_join(obs), **detail})


def build(obs) -> list[Evidence]:
    a = obs.acoustic
    out = []
    if not a["detector_loaded"]:
        out += [_ev(obs, "acoustic_distress", UNAVAILABLE, T4, "BEATs detector not loaded"),
                _ev(obs, "acoustic_distress", UNAVAILABLE, T9, "BEATs detector not loaded")]
    else:
        if not a["trigger_ran"]:
            out.append(_ev(obs, "acoustic_distress", UNAVAILABLE, T4, "4-class trigger not enabled (UDK_ENABLE_SCREAM_TRIGGER)"))
        else:
            fired = a["scream_fired"]
            out.append(_ev(obs, "acoustic_distress", POSITIVE if fired else UNCERTAIN, T4,
                           f"4-class rule {'fired' if fired else 'did not fire'} (live result reused)", score=a["scream_peak"],
                           **{"class": a["scream_class"], "reliability": "unverified", "known_false_alarm_sources": KNOWN_FALSE_ALARM_SOURCES,
                              "absence_is_not_evidence": "misses 28/57 real distress sounds (Phase 0 §9)"}))
        s9 = a["scream_score"]
        if s9 is None:
            why = ("corroboration not enabled (UDK_ENABLE_SCREAM_DETECTION)" if not a["corroboration_enabled"]
                   else "not computed: live skipped this segment before scoring")
            out.append(_ev(obs, "acoustic_distress", UNAVAILABLE, T9, why))
        else:
            out.append(_ev(obs, "acoustic_distress", POSITIVE if s9 >= LIVE_CORROBORATION_THRESHOLD else UNCERTAIN, T9,
                           f"9-class vocal score {s9:.3f} vs {LIVE_CORROBORATION_THRESHOLD} (live score reused)", score=s9,
                           reliability="unverified"))
    out += [_ev(obs, "speaker_attribution", UNAVAILABLE, "none", "no approved speaker embedder (S-1)",
                attribution_namespace=ATTRIBUTION_NAMESPACE),
            _ev(obs, "target_speaker", UNAVAILABLE, "none", "no approved speaker embedder / enrollment (S-1)"),
            _ev(obs, "overlap", UNAVAILABLE, "none", "no approved overlap detector (S-2)"),
            _ev(obs, "condition", UNAVAILABLE, "none", "not computed in shadow (cost; thresholds provisional, S-5)")]
    return out
