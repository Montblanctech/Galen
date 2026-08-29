"""Binomial interval helpers (no scipy)."""

from __future__ import annotations

import math


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
