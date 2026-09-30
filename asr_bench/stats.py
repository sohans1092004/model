"""Speaker-level bootstrap confidence intervals and paired comparison (Phase 2A §6.4, stage S6).

"95% confidence intervals by speaker-level bootstrap (resample speakers, not utterances), 1,000
resamples. Differences between candidates are reported with paired bootstrap intervals on the
same utterances." Metrics are ratios of sums (scoring.METRICS), so each resample re-sums per-
speaker numerators and denominators. Rows without a speaker_id (eval_only) cannot be clustered
by speaker: each becomes its own cluster, and the result says how many there were.
Percentile intervals; deterministic for a given seed.
"""
from __future__ import annotations

import random
from collections import defaultdict

from asr_bench.scoring import METRICS


def _clusters(results: list[dict]) -> tuple[dict, int]:
    out, singletons = defaultdict(list), 0
    for r in results:
        key = r["speaker_id"]
        if key is None:
            key, singletons = ("utt", r["utt_id"]), singletons + 1
        out[key].append(r)
    return out, singletons


def _sums(clusters: dict, metric: str) -> list[tuple[float, float]]:
    num_f, den_f, _ = METRICS[metric]
    return [(sum(num_f(r) for r in rs), sum(den_f(r) for r in rs)) for _, rs in sorted(clusters.items(), key=lambda kv: str(kv[0]))]


def _pct(values: list[float], q: float) -> float:
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def bootstrap_ci(results: list[dict], metric: str, resamples: int, seed: int) -> dict:
    clusters, singletons = _clusters(results)
    sums = _sums(clusters, metric)
    num, den = sum(n for n, _ in sums), sum(d for _, d in sums)
    out = {"value": num / den if den else None, "num": num, "den": den, "speakers": len(clusters) - singletons,
           "unclustered_utterances": singletons, "ci95": None}
    if not den or len(sums) < 2:
        return out
    rng = random.Random(f"{seed}:{metric}")
    vals, k = [], len(sums)
    for _ in range(resamples):
        n = d = 0.0
        for _ in range(k):
            a, b = sums[rng.randrange(k)]
            n += a
            d += b
        if d:
            vals.append(n / d)
    if vals:
        out["ci95"] = [_pct(vals, 0.025), _pct(vals, 0.975)]
        out["resamples_used"] = len(vals)
    return out


def paired_difference(results_a: list[dict], results_b: list[dict], metric: str, resamples: int, seed: int) -> dict:
    """B minus A on the utterances both systems scored; speakers resampled jointly."""
    a_by, b_by = {r["utt_id"]: r for r in results_a}, {r["utt_id"]: r for r in results_b}
    common = sorted(set(a_by) & set(b_by))
    ca, singletons = _clusters([a_by[u] for u in common])
    cb, _ = _clusters([b_by[u] for u in common])
    sa, sb = _sums(ca, metric), _sums(cb, metric)
    na, da = sum(n for n, _ in sa), sum(d for _, d in sa)
    nb, db = sum(n for n, _ in sb), sum(d for _, d in sb)
    out = {"a": na / da if da else None, "b": nb / db if db else None, "utterances": len(common),
           "only_in_a": len(set(a_by) - set(b_by)), "only_in_b": len(set(b_by) - set(a_by)),
           "unclustered_utterances": singletons, "difference": None, "ci95": None}
    if not (da and db):
        return out
    out["difference"] = out["b"] - out["a"]
    if len(sa) < 2:
        return out
    rng = random.Random(f"{seed}:paired:{metric}")
    vals, k = [], len(sa)
    for _ in range(resamples):
        idx = [rng.randrange(k) for _ in range(k)]
        xa, ya = sum(sa[i][0] for i in idx), sum(sa[i][1] for i in idx)
        xb, yb = sum(sb[i][0] for i in idx), sum(sb[i][1] for i in idx)
        if ya and yb:
            vals.append(xb / yb - xa / ya)
    if vals:
        out["ci95"] = [_pct(vals, 0.025), _pct(vals, 0.975)]
    return out
