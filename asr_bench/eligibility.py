"""Whether a manifest row may be USED, kept separate from whether it is a valid manifest row.

Three different questions, answered in three places:
  a) the manifest contains the source -- any row that passes schema.validate_row, including
     use_restriction=blocked rows kept as inventory/provenance (split "eval_only");
  b) the source is legally usable -- legally_usable(): use_restriction is train_ok or eval_only
     (Phase 1 §20); blocked is not;
  c) the row is eligible for a particular split -- eligible_for(): legally usable, assigned to
     that split, train_ok if the split is train, and a valid row.

Every benchmark or training consumer selects its rows through select_eligible(), so a blocked
row can never be executed even though it stays in the manifest.
"""
from __future__ import annotations

from asr_bench.schema import SPLITS, USE_RESTRICTION, validate_row

USABLE_RESTRICTIONS = ("train_ok", "eval_only")


def legally_usable(row: dict) -> bool:
    """(b): licence/legal cleared for at least evaluation."""
    return row.get("use_restriction") in USABLE_RESTRICTIONS


def eligible_for(row: dict, split: str) -> list[str]:
    """(c): reasons `row` may NOT be used as part of `split`; [] = eligible."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {SPLITS}")
    reasons = []
    errors = [i for i in validate_row(row) if i.level == "error"]
    if errors:
        reasons.append(f"fails schema validation ({len(errors)} errors)")
    restriction = row.get("use_restriction") if isinstance(row, dict) else None
    if restriction == "blocked":
        reasons.append("use_restriction=blocked: licence/legal not cleared (Phase 1 §20); inventory only")
    elif restriction not in USE_RESTRICTION:
        reasons.append(f"use_restriction {restriction!r} unknown")
    elif split == "train" and restriction != "train_ok":
        reasons.append(f"use_restriction={restriction}: never for training")
    assigned = row.get("split") if isinstance(row, dict) else None
    if assigned != split:
        reasons.append(f"assigned to split {assigned!r}, not {split!r}")
    return reasons


def select_eligible(rows: list[dict], split: str) -> tuple[list[dict], list[tuple[dict, list[str]]]]:
    """(eligible rows, [(rejected row, reasons)]) for `split`. Rejections are returned, not
    hidden, so a consumer can report what it excluded and why."""
    eligible, rejected = [], []
    for row in rows:
        reasons = eligible_for(row, split)
        (rejected.append((row, reasons)) if reasons else eligible.append(row))
    return eligible, rejected
