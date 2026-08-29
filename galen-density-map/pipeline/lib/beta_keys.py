"""Beta Code normalization for Perseus LSJ lookup."""

from __future__ import annotations

import re

import beta_code

from .greek_normalize import casefold_greek, nfc


def normalize_betacode_key(text: str) -> str:
    """
    Strip Beta Code diacritics / digits / capital marker for matching.

    Handles:
      - leading ``*`` capital marker
      - sigma variants ``s``, ``s1``, ``s2``, ``s3`` (lunate) → ``s`` after digit strip
      - breathings/accents ``) ( / \\ = | + '``
    """
    t = (text or "").lower()
    t = t.lstrip("*")
    # Normalize explicit sigma variant markers before digit strip
    t = re.sub(r"s[123]", "s", t)
    t = re.sub(r"[)(/\\=+|'*]", "", t)
    t = re.sub(r"\d+", "", t)
    t = re.sub(r"[^a-z]", "", t)
    return t


def lemma_to_lookup_key(lemma: str) -> str:
    lemma_n = casefold_greek(nfc(lemma))
    try:
        beta = beta_code.greek_to_beta_code(lemma_n)
    except Exception:
        beta = lemma_n
    return normalize_betacode_key(beta)


def betacode_headword_to_unicode(hw: str) -> str:
    hw_clean = re.sub(r"\d+$", "", hw or "")
    hw_clean = hw_clean.lstrip("*")
    try:
        return nfc(beta_code.beta_code_to_greek(hw_clean))
    except Exception:
        return hw_clean
