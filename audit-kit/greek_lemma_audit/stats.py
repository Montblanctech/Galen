"""Binomial intervals and agreement statistics (no scipy).

``wilson_ci`` and ``pct`` are copied from
``galen-density-map/pipeline/h3m/stats_util.py``; ``cohen_kappa`` from
``galen-density-map/pipeline/h3m/m5_score.py`` (same rounding, same categories).
"""

from __future__ import annotations

import math
from typing import Any


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval at ~95% (z=1.96). Returns (lo, hi) in [0, 1]."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def pct(k: int, n: int, digits: int = 2) -> float | None:
    if n <= 0:
        return None
    return round(100.0 * k / n, digits)


def rate_block(k: int, n: int, label: str = "rate") -> dict[str, Any]:
    """Every number with its N and CI: {k, n, pct, wilson95_lo_pct, wilson95_hi_pct}."""
    lo, hi = wilson_ci(k, n) if n else (float("nan"), float("nan"))
    return {
        "k": k,
        "n": n,
        f"{label}_pct": pct(k, n),
        "wilson95_lo_pct": None if n == 0 else round(100.0 * lo, 2),
        "wilson95_hi_pct": None if n == 0 else round(100.0 * hi, 2),
    }


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    cats = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0
