"""Overlap detection / characterisation.

  OverlapDetector (protocol)  detect(x, sr) -> Evidence(kind="overlap"): POSITIVE (>= 2 voices; detail
                              n_speakers, rel_db = weaker voice relative to stronger), NEGATIVE (one voice),
                              UNCERTAIN, UNAVAILABLE (no speech energy / no detector). NO approved production
                              detector exists (pyannote / WeSep / SepFormer were experiments; separation was
                              rejected in Phase 0 for false positives; S-2). Test-only: fixtures.FixtureOverlapDetector.
  from_annotation()           overlap metadata from a manifest row or a Phase 1 scene -- ground truth for
                              EVALUATION only (source "annotation"); never a runtime signal.
"""
from __future__ import annotations

from typing import Protocol

from udk_signals.evidence import NEGATIVE, POSITIVE, Evidence, unavailable


class OverlapDetector(Protocol):
    detector_id: str

    def detect(self, x, sr: int) -> Evidence: ...


def from_annotation(overlap: bool | None, rel_db: float | None = None, spans=None, speaker_ids=None) -> Evidence:
    if overlap is None:
        return unavailable("overlap", "annotation", "overlap not annotated")
    return Evidence("overlap", POSITIVE if overlap else NEGATIVE, "annotation", "ground truth (evaluation only)",
                    detail={"rel_db": rel_db, "spans": spans, "speaker_ids": speaker_ids})
