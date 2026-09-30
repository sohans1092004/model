"""Scene record: the Phase 1 §15 annotation schema for context data, one scene per target.

Phase 1 §15 fields -> this record:
  pair_id, problem_type, label, provenance            -> same names
  target_text / target_speaker_id / target_role        -> turns[target_turn].text / speaker_id / role
  context_before (text, speaker IDs, roles)            -> the turns BEFORE the target (never merged)
  context_after                                        -> accepted, never used (Phase 2+ uses preceding context only)
  turn_start/end per speaker turn, target_start/end    -> each turn's start_s / end_s, ordered by turn_index
  overlap_start/end, overlapping speaker IDs           -> overlap {start_s, end_s, speaker_ids}
Roles are Phase 1's: victim, attacker, friend, narrator, bystander, media (null = not annotated).
A speaker_id of null means attribution is unavailable for that turn; it is never invented.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROBLEM_TYPES = ("A_standard_udk", "B_custom_udk", "C_danger_no_udk")
LABELS = ("SAFE", "DANGER")
ROLES = ("victim", "attacker", "friend", "narrator", "bystander", "media")
PROVENANCE = ("acted_scripted", "acted_semi_scripted", "spontaneous_safe", "unknown", "fixture")
SPLITS = ("train", "dev", "test", "final_test", "eval_only")


class SceneError(ValueError):
    pass


@dataclass(frozen=True)
class Turn:
    turn_index: int
    speaker_id: str | None
    role: str | None
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Scene:
    scene_id: str
    pair_id: str | None
    problem_type: str
    label: str
    provenance: str
    split: str
    languages: tuple[str, ...]
    context_family: str | None  # e.g. "harmless_request", "quotation_story", "media_nearby", "negation" (Phase 1 §15)
    turns: tuple[Turn, ...]
    target_turn_index: int
    overlap: dict | None  # {"start_s", "end_s", "speaker_ids", "rel_db"} when the target overlaps another voice
    custom_phrase: str | None = None  # problem type B: the speaker's own enrolled phrase
    context_after: tuple | None = None  # stored only; never read by the context layer

    @property
    def target(self) -> Turn:
        return next(t for t in self.turns if t.turn_index == self.target_turn_index)


def scene_from_dict(d: dict) -> Scene:
    try:
        turns = tuple(Turn(int(t["turn_index"]), t.get("speaker_id"), t.get("role"), t["text"], float(t["start_s"]), float(t["end_s"]))
                      for t in d["turns"])
        s = Scene(d["scene_id"], d.get("pair_id"), d["problem_type"], d["label"], d["provenance"], d["split"],
                  tuple(d["languages"]), d.get("context_family"), turns, int(d["target_turn_index"]), d.get("overlap"),
                  d.get("custom_phrase"), tuple(d["context_after"]) if d.get("context_after") else None)
    except (KeyError, TypeError, ValueError) as e:
        raise SceneError(f"{d.get('scene_id')}: malformed scene ({type(e).__name__}: {e})") from e
    validate_scene(s)
    return s


def validate_scene(s: Scene) -> None:
    where = s.scene_id
    if s.problem_type not in PROBLEM_TYPES:
        raise SceneError(f"{where}: problem_type must be one of {PROBLEM_TYPES}")
    if s.label not in LABELS:
        raise SceneError(f"{where}: label must be SAFE or DANGER")
    if s.provenance not in PROVENANCE:
        raise SceneError(f"{where}: provenance must be one of {PROVENANCE}")
    if s.split not in SPLITS:
        raise SceneError(f"{where}: split must be one of {SPLITS}")
    idx = [t.turn_index for t in s.turns]
    if idx != sorted(set(idx)):
        raise SceneError(f"{where}: turn_index must be unique and ordered")
    if s.target_turn_index not in idx:
        raise SceneError(f"{where}: target_turn_index not among the turns")
    for t in s.turns:
        if t.role is not None and t.role not in ROLES:
            raise SceneError(f"{where}: turn {t.turn_index} role {t.role!r} not a Phase 1 role")
        if t.start_s > t.end_s:
            raise SceneError(f"{where}: turn {t.turn_index} starts after it ends")
        if t.speaker_id is None and t.role is not None:
            raise SceneError(f"{where}: turn {t.turn_index} has a role but no speaker attribution")
    if s.problem_type == "B_custom_udk" and not s.custom_phrase:
        raise SceneError(f"{where}: problem type B needs the speaker's custom_phrase")
    if s.overlap is not None and not {"start_s", "end_s"} <= set(s.overlap):
        raise SceneError(f"{where}: overlap needs start_s and end_s")


def load_scenes(path: str | Path) -> list[Scene]:
    scenes = [scene_from_dict(json.loads(l)) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = [s.scene_id for s in scenes]
    if len(ids) != len(set(ids)):
        raise SceneError("duplicate scene_id")
    return scenes


def assign_scene_splits(scenes: list[Scene], split_config, source_dataset: str, use_restriction: str) -> dict:
    """Speaker-disjoint scene splits through the existing S3 splitter (asr_bench.splits): one record per
    turn, all linked by the scene (session) and by speaker, so every speaker of a scene -- attacker and
    victim alike -- and every other scene they appear in land in ONE split. Unattributed turns stay
    unlinked; a scene whose target has no speaker goes to eval_only (S3 null-speaker rule).
    Returns {scene_id: split}; raises if the plan has errors."""
    from asr_bench.splits import SplitRecord, assign_splits

    recs = [SplitRecord(f"{source_dataset}:{s.scene_id}#{t.turn_index}", source_dataset, use_restriction,
                        t.speaker_id, f"{source_dataset}:scene:{s.scene_id}", None)
            for s in scenes for t in s.turns]
    plan = assign_splits(recs, split_config)
    if not plan.ok:
        raise SceneError("scene split plan has errors: " + "; ".join(str(i) for i in plan.issues if i.level == "error"))
    out = {}
    for s in scenes:
        splits = {plan.assignments[f"{source_dataset}:{s.scene_id}#{t.turn_index}"] for t in s.turns}
        out[s.scene_id] = splits.pop() if len(splits) == 1 else "eval_only"
    return out
