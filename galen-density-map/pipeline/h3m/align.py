"""Greedy NFC-surface alignment of two token streams (odyCy vs Stanza)."""

from __future__ import annotations

from typing import Sequence

from .lemma_eq import lemma_nfc


def align_surfaces(
    a: Sequence[str],
    b: Sequence[str],
    window: int = 8,
) -> tuple[list[tuple[int, int]], dict]:
    """Return aligned index pairs (i_a, i_b) and loss stats.

    Divergent regions are skipped until the streams resync within ``window``.
    Alignment loss is unmatched tokens in stream A over len(A).
    """
    i = j = 0
    n, m = len(a), len(b)
    pairs: list[tuple[int, int]] = []
    skipped_a = skipped_b = 0

    def eq(x: str, y: str) -> bool:
        return lemma_nfc(x) == lemma_nfc(y) and bool(lemma_nfc(x))

    while i < n and j < m:
        if eq(a[i], b[j]):
            pairs.append((i, j))
            i += 1
            j += 1
            continue
        found = False
        for d in range(1, window + 1):
            if i + d < n and eq(a[i + d], b[j]):
                skipped_a += d
                i += d
                found = True
                break
            if j + d < m and eq(a[i], b[j + d]):
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
        "flag_alignment_loss": loss_a > 0.05,
    }
    return pairs, stats
