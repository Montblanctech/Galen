"""Normalisation, equality, statistics and alignment."""

from __future__ import annotations

import math

from greek_lemma_audit.align import align_surfaces
from greek_lemma_audit.normalize import (
    admissibility_verdict,
    classify_lemma_disagreement,
    lemma_blind_key,
    lemma_nfc,
    lemmas_equal_blind,
    lemmas_equal_strict,
    normalize_lunate_sigma,
    surface_nfc,
)
from greek_lemma_audit.stats import cohen_kappa, pct, rate_block, wilson_ci


def test_lunate_and_final_sigma():
    assert normalize_lunate_sigma("ϲῶμα") == "σῶμα"
    assert normalize_lunate_sigma("λόγοσ") == "λόγος"
    assert surface_nfc("λόγοσ") == "λόγος"


def test_strict_vs_blind_equality():
    assert lemmas_equal_strict("Λόγος", "λόγος")
    assert not lemmas_equal_strict("νεύρον", "νεῦρον")  # accent counts strictly
    assert lemmas_equal_blind("νεύρον", "νεῦρον")  # accent-blind key
    assert lemma_blind_key("νεύρον") == lemma_blind_key("νεῦρον") != ""
    assert lemma_nfc("ΓΑΣΤΗΡ") == "γαστηρ"
    assert not lemmas_equal_strict("", "λόγος")


def test_admissibility_three_way():
    assert admissibility_verdict("ὁ", ["ὁ"]) == "admissible"
    assert admissibility_verdict("γαήτσρ", ["γαστήρ"]) == "inadmissible"
    assert admissibility_verdict("γαστήρ", []) == "no_analysis"
    # accent-blind primary membership (METHODS.md): νεύρον admissible when analyzer lists νεῦρον
    assert admissibility_verdict("νεύρον", ["νεῦρον"]) == "admissible"


def test_g2a_classes():
    assert classify_lemma_disagreement("δέ", "δέ") == "encoding_artifact"
    assert classify_lemma_disagreement("νεύρον", "νεῦρον") == "accent_only"
    assert classify_lemma_disagreement("δέ", "ὁ") == "real_disagreement"
    assert classify_lemma_disagreement("δέ", "") == "missing_lemma"


def test_wilson_matches_project_numbers():
    # m2_agreement_summary.json: 40/50 -> 66.96–88.76
    lo, hi = wilson_ci(40, 50)
    assert round(100 * lo, 2) == 66.96 and round(100 * hi, 2) == 88.76
    # m5: 50/60 -> 71.97–90.69
    lo, hi = wilson_ci(50, 60)
    assert round(100 * lo, 2) == 71.97 and round(100 * hi, 2) == 90.69
    assert pct(1, 0) is None
    assert math.isnan(wilson_ci(0, 0)[0])
    blk = rate_block(3, 4, "agree")
    assert blk["agree_pct"] == 75.0 and blk["n"] == 4


def test_kappa():
    assert cohen_kappa(["y", "y", "n", "n"], ["y", "y", "n", "n"]) == 1.0
    assert cohen_kappa(["y", "y", "n", "n"], ["y", "n", "y", "n"]) == 0.0
    assert math.isnan(cohen_kappa([], []))


def test_alignment_resync_and_loss():
    a = ["καὶ", "τὸ", "σῶμα", "δέ", "ἐστι"]
    b = ["καὶ", "τὸ", "σῶμ", "α", "δέ", "ἐστι"]  # one split token
    pairs, stats = align_surfaces(a, b)
    assert (0, 0) in pairs and (1, 1) in pairs and (3, 4) in pairs and (4, 5) in pairs
    assert stats["n_aligned"] == 4 and stats["skipped_a"] == 1
    assert stats["flag_alignment_loss"] is True  # 1/5 > 5%
    pairs, stats = align_surfaces(a, a)
    assert stats["n_aligned"] == 5 and stats["alignment_loss_a"] == 0.0
