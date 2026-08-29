import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from importlib import import_module

keyness = import_module("05_keyness")


def test_log_likelihood_symmetric_zero_when_proportional():
    # a/c == b/d => G2 ~ 0
    g2 = keyness.log_likelihood(10, 100, 1000, 10000)
    assert g2 < 1e-9


def test_log_likelihood_positive_when_overused():
    g2 = keyness.log_likelihood(50, 5, 1000, 10000)
    assert g2 > 15.13


def test_log_likelihood_handles_zero_reference():
    g2 = keyness.log_likelihood(20, 0, 1000, 10000)
    assert g2 > 0
    assert math.isfinite(g2)
