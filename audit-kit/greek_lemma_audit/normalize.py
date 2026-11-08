"""Greek normalisation and lemma equality.

Copied, with attribution, from the Galen Density Project pipeline
(``galen-density-map/pipeline/lib/greek_normalize.py``,
``galen-density-map/pipeline/lib/beta_keys.py`` and
``galen-density-map/pipeline/h3m/lemma_eq.py``) so the kit is standalone and
its accent policy is byte-identical to the one documented in
``galen-density-map/data/qc/h3m/METHODS.md``:

- **Primary M1 membership** is accent-blind: ``lemma_to_lookup_key``
  (NFC + casefold + Beta Code + strip diacritics/digits/sigma variants). This is
  the H4b LSJ canonicalisation scheme.
- **Accent-strict diagnostic** compares NFC + casefold + lunate/final sigma with
  accents kept (``lemma_nfc``).
- **M2 lemma comparison** is accent-preserving (``lemma_nfc``).

If the ``beta_code`` package is missing the blind key falls back to a Unicode
diacritic strip; ``BLIND_KEY_BACKEND`` records which backend is in force so the
summary can say so.
"""

from __future__ import annotations

import re
import unicodedata

try:  # pinned in galen-density-map/requirements.txt (beta-code==1.1.1)
    import beta_code as _beta_code

    BLIND_KEY_BACKEND = "beta_code"
except Exception:  # pragma: no cover - exercised only when the package is absent
    _beta_code = None
    BLIND_KEY_BACKEND = "unicode_strip_fallback"

GREEK_RUN_RE = re.compile(r"[Ͱ-Ͽἀ-῿]+")
GREEK_LETTER_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def casefold_greek(text: str) -> str:
    """Lowercase for case-insensitive lemma counting (Ἱπποκράτης == ἱπποκράτης)."""
    return nfc(text).lower()


def strip_diacritics(text: str) -> str:
    """NFD then drop combining marks."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text or "") if unicodedata.category(ch) != "Mn"
    )


def normalize_lunate_sigma(text: str) -> str:
    """Map lunate ϲ/Ϲ -> σ/Σ; word-final σ -> ς (on Greek-letter runs)."""
    text = (text or "").replace("ϲ", "σ").replace("Ϲ", "Σ")

    def _final(m: re.Match[str]) -> str:
        word = m.group(0)
        if len(word) > 1 and word.endswith(("σ", "Σ")):
            return word[:-1] + "ς"
        return word

    return GREEK_RUN_RE.sub(_final, text)


def normalize_betacode_key(text: str) -> str:
    """Strip Beta Code diacritics / digits / capital marker for matching."""
    t = (text or "").lower().lstrip("*")
    t = re.sub(r"s[123]", "s", t)
    t = re.sub(r"[)(/\\=+|'*]", "", t)
    t = re.sub(r"\d+", "", t)
    t = re.sub(r"[^a-z]", "", t)
    return t


def lemma_to_lookup_key(lemma: str) -> str:
    """Accent-blind key (H4b scheme). Empty string when nothing Greek survives."""
    lemma_n = casefold_greek(nfc(lemma))
    if _beta_code is not None:
        try:
            beta = _beta_code.greek_to_beta_code(lemma_n)
        except Exception:
            beta = lemma_n
        return normalize_betacode_key(beta)
    # Fallback: strip diacritics, unify sigma, keep Greek letters only.
    bare = strip_diacritics(lemma_n).replace("ς", "σ").replace("ϲ", "σ")
    return "".join(ch for ch in bare if GREEK_LETTER_RE.match(ch))


# ---- equality helpers (h3m/lemma_eq.py) -------------------------------------


def surface_nfc(text: str) -> str:
    return normalize_lunate_sigma(nfc(text))


def lemma_nfc(text: str) -> str:
    """Accent-preserving canonical lemma/surface for equality."""
    return normalize_lunate_sigma(casefold_greek(text))


def lemma_blind_key(text: str) -> str:
    return lemma_to_lookup_key(text or "")


def lemmas_equal_strict(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and lemma_nfc(a) == lemma_nfc(b)


def lemmas_equal_blind(a: str | None, b: str | None) -> bool:
    ka, kb = lemma_blind_key(a or ""), lemma_blind_key(b or "")
    return bool(ka) and ka == kb


def analyses_have_lemma(lemma: str, analyses: list[str], *, accent_blind: bool) -> bool:
    if not lemma or not analyses:
        return False
    if accent_blind:
        key = lemma_blind_key(lemma)
        return bool(key) and any(lemma_blind_key(a) == key for a in analyses)
    target = lemma_nfc(lemma)
    return any(lemma_nfc(a) == target for a in analyses)


def admissibility_verdict(lemma: str, analyses: list[str]) -> str:
    """Three-way outcome: admissible / inadmissible / no_analysis."""
    if not analyses:
        return "no_analysis"
    if analyses_have_lemma(lemma, analyses, accent_blind=True):
        return "admissible"
    return "inadmissible"


def classify_lemma_disagreement(lemma_a: str | None, lemma_b: str | None) -> str:
    """Mechanical G2a class for a pairwise lemma disagreement."""
    if not lemma_a or not lemma_b:
        return "missing_lemma"
    if lemmas_equal_strict(lemma_a, lemma_b):
        return "encoding_artifact"
    if lemmas_equal_blind(lemma_a, lemma_b):
        return "accent_only"
    return "real_disagreement"


def is_greek(text: str) -> bool:
    return bool(GREEK_LETTER_RE.search(text or ""))


# Lemma *conventions* that differ between systems without either being wrong. Kept deliberately
# tiny and documented: the article (odyCy/Stanza: one headword ὁ; Dilemma lsj convention: ὁ/ἡ/τό).
# M2 reports strict agreement first and this convention-neutral figure beside it, never instead.
_ARTICLE_FORMS = ("ὁ ἡ τό τοῦ τῆς τῷ τῇ τόν τήν τώ τοῖν ταῖν οἱ αἱ τά τῶν τοῖς ταῖς τούς τάς "
                  "τὸ τὸν τὴν τὰ τὰς τοὺς ἥ")
ARTICLE_CONVENTION = {lemma_nfc(f): "ὁ" for f in _ARTICLE_FORMS.split()}


def convention_neutral(lemma: str | None) -> str | None:
    if lemma is None:
        return None
    k = lemma_nfc(lemma)
    return ARTICLE_CONVENTION.get(k, k)
