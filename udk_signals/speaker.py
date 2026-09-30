"""Speaker/voice representation, target-speaker identification and speaker attribution.

  SpeakerEmbedder (protocol)  embed(x, sr) -> tuple[float, ...] | None. NO approved production
                              embedder exists (ECAPA / WavLM were experiments; S-1). Test-only:
                              fixtures.FixtureEmbedder.
  TargetSpeakerVerifier       is this segment the enrolled user? POSITIVE >= accept, NEGATIVE <= reject,
                              UNCERTAIN between; UNCERTAIN whenever the segment overlaps another voice
                              (one embedding over two voices is meaningless) or is too short;
                              UNAVAILABLE with no embedder or no enrollment. A NEGATIVE ("not the
                              user") never implies safety (Phase 0 product rule: any voice saying a UDK
                              alerts).
  SpeakerAttributor           segment -> speaker label by online clustering (explicit threshold).
                              Overlapped segments get NO single label (state UNCERTAIN, detail
                              "overlap: not merged"); speakers are never merged into one.
Thresholds are configuration (configs/*.json); no defaults.
"""
from __future__ import annotations

import math
from typing import Protocol

from udk_signals.evidence import NEGATIVE, POSITIVE, UNCERTAIN, Evidence, unavailable


class SpeakerEmbedder(Protocol):
    embedder_id: str

    def embed(self, x, sr: int) -> tuple[float, ...] | None: ...


def cosine(a, b) -> float:
    na, nb = math.sqrt(sum(v * v for v in a)), math.sqrt(sum(v * v for v in b))
    return sum(p * q for p, q in zip(a, b)) / (na * nb) if na and nb else 0.0


def _overlapped(overlap: Evidence | None) -> bool:
    return overlap is not None and overlap.state == POSITIVE


class TargetSpeakerVerifier:
    def __init__(self, embedder: SpeakerEmbedder | None, enrollment: list | None, cfg: dict):
        for k in ("accept", "reject", "min_duration_s"):
            if k not in cfg:
                raise ValueError(f"target-speaker config needs {k}")
        if not cfg["reject"] < cfg["accept"]:
            raise ValueError("reject threshold must be below accept")
        self.embedder, self.cfg = embedder, cfg
        self.enrollment = [e for e in (enrollment or []) if e]

    def identify(self, x, sr: int, overlap: Evidence | None = None, start_s=None, end_s=None) -> Evidence:
        src = getattr(self.embedder, "embedder_id", "none")
        if self.embedder is None:
            return unavailable("target_speaker", src, "no speaker embedder available")
        if not self.enrollment:
            return unavailable("target_speaker", src, "no enrollment sample for this user")
        if len(x) < self.cfg["min_duration_s"] * sr:
            return Evidence("target_speaker", UNCERTAIN, src, "segment too short", start_s=start_s, end_s=end_s)
        if _overlapped(overlap):
            return Evidence("target_speaker", UNCERTAIN, src, "segment overlaps another voice; not attributed",
                            start_s=start_s, end_s=end_s, detail={"overlap": True})
        emb = self.embedder.embed(x, sr)
        if emb is None:
            return unavailable("target_speaker", src, "embedder produced no embedding")
        sim = max(cosine(emb, e) for e in self.enrollment)
        state = POSITIVE if sim >= self.cfg["accept"] else NEGATIVE if sim <= self.cfg["reject"] else UNCERTAIN
        return Evidence("target_speaker", state, src, f"similarity {sim:.3f} vs accept {self.cfg['accept']} / reject {self.cfg['reject']}",
                        score=sim, start_s=start_s, end_s=end_s)


class SpeakerAttributor:
    def __init__(self, embedder: SpeakerEmbedder | None, cfg: dict):
        if "same_speaker" not in cfg:
            raise ValueError("attribution config needs same_speaker")
        self.embedder, self.cfg = embedder, cfg

    def attribute(self, segments) -> list[Evidence]:
        """segments: [(x, sr, start_s, end_s, overlap_evidence_or_None)] in time order."""
        src = getattr(self.embedder, "embedder_id", "none")
        if self.embedder is None:
            return [unavailable("speaker_attribution", src, "no speaker embedder available") for _ in segments]
        centroids: list[tuple[str, tuple]] = []
        out = []
        for x, sr, a, b, ov in segments:
            if _overlapped(ov):
                out.append(Evidence("speaker_attribution", UNCERTAIN, src, "overlap: speakers not merged into one label",
                                    start_s=a, end_s=b, detail={"label": None, "overlap": True}))
                continue
            emb = self.embedder.embed(x, sr)
            if emb is None:
                out.append(unavailable("speaker_attribution", src, "no embedding"))
                continue
            best = max(((cosine(emb, c), lab) for lab, c in centroids), default=(-1.0, None))
            if best[0] >= self.cfg["same_speaker"]:
                label, sim = best[1], best[0]
            else:
                label, sim = f"spk{len(centroids) + 1}", None
                centroids.append((label, emb))
            out.append(Evidence("speaker_attribution", POSITIVE, src, "attributed", score=sim, start_s=a, end_s=b,
                                detail={"label": label}))
        return out
