"""Levenshtein alignment with a deterministic backtrace (stage S4).

align(ref, hyp) -> [(op, ref_index, hyp_index)] with op in C (correct), S, D, I; index is None
where a side has no token. Unit costs. Ties prefer the diagonal (C/S), then D, then I, so the
same pair always gives the same alignment.
"""
from __future__ import annotations


def align(ref: list, hyp: list) -> list[tuple[str, int | None, int | None]]:
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i
    for j in range(1, m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        ri, row, prev = ref[i - 1], d[i], d[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prev[j - 1] + (ri != hyp[j - 1]), prev[j] + 1, row[j - 1] + 1)
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            ops.append(("C" if ref[i - 1] == hyp[j - 1] else "S", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            ops.append(("D", i - 1, None))
            i -= 1
        else:
            ops.append(("I", None, j - 1))
            j -= 1
    ops.reverse()
    return ops


def counts(ops) -> dict:
    c = {"C": 0, "S": 0, "D": 0, "I": 0}
    for op, _, _ in ops:
        c[op] += 1
    return c
