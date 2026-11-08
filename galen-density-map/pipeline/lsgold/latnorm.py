"""LS-Gold — Latin normalisation shared by every stage (the Latin counterpart of lib/beta_keys.lemma_to_lookup_key).

key(s): the comparison key for headwords and lemmas. Lowercase; macrons, breves and every other diacritic stripped
(Lewis & Short prints ăbăcus, Collatinus prints ăbăcŭs); v -> u and j -> i (L&S heads 'volo', Perseus texts print
'uolo'/'volo', systems differ); ligatures æ/œ expanded; a trailing homograph digit removed (L&S keys 'a1', 'a2';
Collatinus 'sero2'); anything that is not a letter dropped. Empty string when nothing is left.

TOKEN_RE: a Latin word in a TEI passage: letters (with diacritics) only; numerals, sigla and punctuation are not tokens.
Enclitic -que/-ne/-ve stay on the word (so do the systems' tokens; a lemmatizer that splits them is scored on the
host word, documented in the scorer).
"""
from __future__ import annotations

import re
import unicodedata

TOKEN_RE = re.compile(r"[A-Za-zÀ-ɏḀ-ỿ]+")
_DIGITS = re.compile(r"\d+$")
_NONLETTER = re.compile(r"[^a-z]")


def strip_marks(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", s)


def key(s: str) -> str:
    s = strip_marks((s or "").strip()).lower()
    s = s.replace("æ", "ae").replace("œ", "oe").replace("ſ", "s")
    s = _DIGITS.sub("", s)
    s = s.replace("v", "u").replace("j", "i")
    s = _NONLETTER.sub("", s)
    return s


def strict(s: str) -> str:
    """Strict comparison form: diacritics and homograph digits off, case folded, u/v and i/j kept as printed."""
    s = strip_marks((s or "").strip()).lower()
    return _DIGITS.sub("", s)


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text or "")
