"""Tiny Levenshtein helpers (no third-party dependency)."""

from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Ensure a is the shorter string
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for i, cb in enumerate(b, 1):
        cur = [i]
        for j, ca in enumerate(a, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def has_neighbor_within(target: str, candidates: set[str], max_dist: int) -> bool:
    """True if any candidate is within edit distance ``max_dist`` of ``target``."""
    if target in candidates:
        return True
    tlen = len(target)
    for s in candidates:
        if abs(len(s) - tlen) > max_dist:
            continue
        if levenshtein(target, s) <= max_dist:
            return True
    return False
