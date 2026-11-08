"""Greedy NFC-surface alignment of two token streams.

Copied, with attribution, from ``galen-density-map/pipeline/h3m/align.py`` so
alignment loss is computed exactly as in the H3-M M2 run (resync window 8;
divergent regions skipped and counted; loss = unmatched tokens of stream A over
len(A); flag when loss > 5%).
"""

from __future__ import annotations

from typing import Sequence

from .normalize import lemma_nfc

ALIGN_LOSS_FLAG = 0.05


def align_surfaces(
    a: Sequence[str],
    b: Sequence[str],
    window: int = 8,
) -> tuple[list[tuple[int, int]], dict]:
    """Return aligned index pairs (i_a, i_b) and loss stats."""
    i = j = 0
    n, m = len(a), len(b)
    pairs: list[tuple[int, int]] = []
    skipped_a = skipped_b = 0

    na = [lemma_nfc(x) for x in a]
    nb = [lemma_nfc(x) for x in b]

    def eq(x: int, y: int) -> bool:
        return bool(na[x]) and na[x] == nb[y]

    while i < n and j < m:
        if eq(i, j):
            pairs.append((i, j))
            i += 1
            j += 1
            continue
        found = False
        for d in range(1, window + 1):
            if i + d < n and eq(i + d, j):
                skipped_a += d
                i += d
                found = True
                break
            if j + d < m and eq(i, j + d):
                skipped_b += d
                j += d
                found = True
                break
        if not found:
            skipped_a += 1
            skipped_b += 1
            i += 1
            j += 1

    skipped_a += n - i
    skipped_b += m - j
    loss_a = (skipped_a / n) if n else 0.0
    stats = {
        "n_a": n,
        "n_b": m,
        "n_aligned": len(pairs),
        "skipped_a": skipped_a,
        "skipped_b": skipped_b,
        "alignment_loss_a": loss_a,
        "flag_alignment_loss": loss_a > ALIGN_LOSS_FLAG,
    }
    return pairs, stats
