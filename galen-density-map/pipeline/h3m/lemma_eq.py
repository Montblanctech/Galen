"""Lemma / surface equality for H3-M.

Accent policy (documented in data/qc/h3m/METHODS.md):

- **Primary M1 membership** is accent-blind: H4b ``lemma_to_lookup_key``
  (NFC + casefold + Beta Code + strip diacritics/digits/sigma variants).
- **Accent-strict diagnostic** compares NFC + casefold + lunate/final sigma
  with accents kept.
- **M2 lemma comparison** is accent-preserving (NFC + casefold + sigma).
"""

from __future__ import annotations

from lib.beta_keys import lemma_to_lookup_key
from lib.greek_normalize import casefold_greek, nfc, normalize_lunate_sigma


def surface_nfc(text: str) -> str:
    return normalize_lunate_sigma(nfc(text or ""))


def lemma_nfc(text: str) -> str:
    """Accent-preserving canonical lemma/surface for equality."""
    return normalize_lunate_sigma(casefold_greek(text or ""))


def lemma_blind_key(text: str) -> str:
    return lemma_to_lookup_key(text or "")


def lemmas_equal_strict(a: str, b: str) -> bool:
    return bool(a) and bool(b) and lemma_nfc(a) == lemma_nfc(b)


def lemmas_equal_blind(a: str, b: str) -> bool:
    ka, kb = lemma_blind_key(a), lemma_blind_key(b)
    return bool(ka) and ka == kb


def analyses_have_lemma(odycy_lemma: str, analyses: list[str], *, accent_blind: bool) -> bool:
    if not odycy_lemma or not analyses:
        return False
    if accent_blind:
        key = lemma_blind_key(odycy_lemma)
        if not key:
            return False
        return any(lemma_blind_key(a) == key for a in analyses)
    target = lemma_nfc(odycy_lemma)
    return any(lemma_nfc(a) == target for a in analyses)


def admissibility_verdict(odycy_lemma: str, analyses: list[str]) -> str:
    """Three-way outcome: admissible / inadmissible / no_analysis."""
    if not analyses:
        return "no_analysis"
    if analyses_have_lemma(odycy_lemma, analyses, accent_blind=True):
        return "admissible"
    return "inadmissible"


def classify_lemma_disagreement(lemma_a: str, lemma_b: str) -> str:
    """Mechanical G2a class for a pairwise lemma disagreement."""
    if not lemma_a or not lemma_b:
        return "missing_lemma"
    if lemmas_equal_strict(lemma_a, lemma_b):
        return "encoding_artifact"
    if lemmas_equal_blind(lemma_a, lemma_b):
        return "accent_only"
    return "real_disagreement"
