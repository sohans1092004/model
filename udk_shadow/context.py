"""Rolling per-journey context buffer for Phase 3 (contract §4).

One finalized VAD segment = one Phase 3 turn: turn_index = the segment's ordinal as seen by this process,
start_s / end_s from the journey-audio clock, text = the transcript of the STT list the shadow replay kept.
speaker_id is None and role is None unless a POSITIVE speaker_attribution Evidence with a namespace exists
for that segment -- which cannot happen today (S-1), so every turn is unattributed and Phase 3 H4 blocks any
context veto. Nothing is inferred.

Bounded: at most `max_journeys` journeys (least-recently-used evicted) x `max_segments` segments each, and
segments older than the Phase 3 window are pruned. Server restart: the buffer is in-process memory only, so
after a restart (or an eviction) a journey's first observed segment is flagged cold_start with the reason.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass

from udk_context.context_window import build_window
from udk_context.scene import Scene, Turn


@dataclass
class _Journey:
    segments: deque
    ordinal: int = 0
    gaps: int = 0  # observations dropped before reaching the buffer (queue full)


class ContextBuffer:
    def __init__(self, max_journeys: int, max_segments: int, window_s: float, max_turns: int, process_started_at: float):
        self.max_journeys, self.max_segments = max_journeys, max_segments
        self.window_s, self.max_turns = window_s, max_turns
        self.process_started_at = process_started_at
        self._j: OrderedDict[str, _Journey] = OrderedDict()
        self._evicted: set[str] = set()
        self.evictions = 0

    def _get(self, journey_id: str) -> tuple[_Journey, str | None]:
        j = self._j.get(journey_id)
        cold = None
        if j is None:
            cold = "evicted_from_buffer" if journey_id in self._evicted else "new_to_this_process"
            j = self._j[journey_id] = _Journey(deque(maxlen=self.max_segments))
            if len(self._j) > self.max_journeys:
                old, _ = self._j.popitem(last=False)
                self._evicted.add(old)
                self.evictions += 1
                if len(self._evicted) > 4 * self.max_journeys:  # bounded memory for the eviction set too
                    self._evicted.clear()
        self._j.move_to_end(journey_id)
        return j, cold

    def note_gap(self, journey_id: str) -> None:
        j = self._j.get(journey_id)
        if j is not None:
            j.gaps += 1

    def window_for(self, obs, target_text: str):
        """(ContextWindow, context_info) for this segment, BEFORE it is appended."""
        j, cold = self._get(obs.journey_id)
        info = {"cold_start": cold is not None or not j.segments, "cold_reason": cold,
                "possible_restart": cold is not None and obs.journey_started_at < self.process_started_at,
                "gaps_so_far": j.gaps, "buffered_segments": len(j.segments)}
        tgt_idx = j.ordinal
        turns = [Turn(s["turn_index"], None, None, s["text"], s["start_ms"] / 1000.0, s["end_ms"] / 1000.0) for s in j.segments]
        target = Turn(tgt_idx, None, None, target_text, obs.start_ms / 1000.0, obs.end_ms / 1000.0)
        turns = [t for t in turns if t.turn_index < tgt_idx] + [target]
        # Runtime scene: only turns/target are read by build_window; label/problem_type are NOT labels.
        scene = Scene(obs.segment_id, None, "runtime_unlabelled", "UNLABELLED", "runtime_shadow", "none", (), None,
                      tuple(turns), tgt_idx, None)
        win = build_window(scene, self.window_s, self.max_turns)
        info["context_turns"] = [{"segment_id": s["segment_id"], "start_ms": s["start_ms"], "end_ms": s["end_ms"], "text": s["text"],
                                  "speaker_id": None, "relation": ct.relation}
                                 for ct in win.turns for s in j.segments if s["turn_index"] == ct.turn.turn_index]
        info["attribution_complete"] = win.attribution_complete
        return win, info

    def append(self, obs, text: str | None) -> None:
        j, _ = self._get(obs.journey_id)
        if text is not None:
            j.segments.append({"turn_index": j.ordinal, "segment_id": obs.segment_id, "start_ms": obs.start_ms,
                               "end_ms": obs.end_ms, "text": text})
        j.ordinal += 1
        cutoff = obs.end_ms - self.window_s * 1000.0
        while j.segments and j.segments[0]["end_ms"] < cutoff:
            j.segments.popleft()
