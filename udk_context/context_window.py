"""Preceding-context window with explicit speaker/turn boundaries.

Rules:
  - PRECEDING ONLY: a turn is context only if it ENDS at or before the target starts (Phase 1 §15:
    context_before -> target; Phase 2 may use preceding context only). Nothing after the target.
  - Turns overlapping the target are not "context": they are reported as `concurrent` (overlap).
  - Speakers are never merged: each turn keeps its own speaker_id / role; relation to the target
    speaker is same_speaker / other_speaker / unattributed (speaker unknown on either side).
  - Window limits are explicit configuration: window_s (seconds before the target start) and
    max_turns. No defaults (Phase 0's rejected v2 context used 20 s / 60 words; not reused silently).
"""
from __future__ import annotations

from dataclasses import dataclass

from udk_context.scene import Scene, Turn


@dataclass(frozen=True)
class ContextTurn:
    turn: Turn
    relation: str  # same_speaker | other_speaker | unattributed
    seconds_before_target: float


@dataclass(frozen=True)
class ContextWindow:
    target: Turn
    turns: tuple[ContextTurn, ...]  # oldest first
    concurrent: tuple[Turn, ...]  # overlapping the target (not context)
    attribution_complete: bool  # every context turn and the target have a speaker_id

    def by_relation(self, relation: str) -> list[ContextTurn]:
        return [t for t in self.turns if t.relation == relation]

    @property
    def has_other_speaker(self) -> bool:
        return any(t.relation == "other_speaker" for t in self.turns)

    def render(self) -> str:
        """Text for a context-aware scorer: one line per turn, speaker boundaries explicit."""
        lines = [f"[{t.turn.speaker_id or 'unknown'}|{t.turn.role or '-'}|{t.relation}] {t.turn.text}" for t in self.turns]
        return "\n".join(lines + [f"[TARGET {self.target.speaker_id or 'unknown'}] {self.target.text}"])


def _relation(a: Turn, target: Turn) -> str:
    if a.speaker_id is None or target.speaker_id is None:
        return "unattributed"
    return "same_speaker" if a.speaker_id == target.speaker_id else "other_speaker"


def build_window(scene: Scene, window_s: float, max_turns: int) -> ContextWindow:
    if not (window_s >= 0 and isinstance(max_turns, int) and max_turns >= 0):
        raise ValueError("window_s >= 0 and integer max_turns >= 0 are required configuration")
    tgt = scene.target
    before, concurrent = [], []
    for t in scene.turns:
        if t.turn_index == tgt.turn_index:
            continue
        if t.end_s <= tgt.start_s and t.turn_index < tgt.turn_index:
            if tgt.start_s - t.end_s <= window_s:
                before.append(ContextTurn(t, _relation(t, tgt), round(tgt.start_s - t.end_s, 6)))
        elif t.start_s < tgt.end_s and t.end_s > tgt.start_s:
            concurrent.append(t)
    before = before[-max_turns:] if max_turns else []
    complete = tgt.speaker_id is not None and all(c.turn.speaker_id is not None for c in before)
    return ContextWindow(tgt, tuple(before), tuple(concurrent), complete)
