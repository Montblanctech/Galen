"""Normalisation and citation parsing. Pure functions, no I/O."""
from __future__ import annotations

import re
import unicodedata

_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def is_greek(s: str) -> bool:
    return bool(_GREEK.search(s or ""))


def fold(s: str) -> str:
    """Accent-, breathing-, case- and punctuation-blind key (Greek or Latin).

    ὄνυξι, -> ονυξι ; consīdĕrātĭo -> consideratio ; ab-dico -> abdico ; final sigma -> σ.
    """
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = s.replace("ς", "σ").replace("ϲ", "σ")
    if not is_greek(s):
        s = s.replace("j", "i").replace("v", "u")
    return "".join(c for c in s if c.isalpha())


def fold_beta(s: str) -> str:
    """Letters-only key for an LSJ Beta Code key such as 'gnw/risma' -> 'gnwrisma'."""
    return "".join(c for c in (s or "").lower() if "a" <= c <= "z")


def words(s: str) -> list[str]:
    return [w for w in re.split(r"[^\w]+", (s or "").lower()) if w]


def stem_en(w: str) -> str:
    """Very light English stem so 'nerves' finds 'nerve' and 'humours' finds 'humour'."""
    if len(w) <= 4 or w.endswith("ss"):
        return w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("ses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    return w[:-1] if w.endswith("s") else w


def roman_to_int(r: str) -> int | None:
    r = r.lower()
    if not r or any(c not in _ROMAN for c in r):
        return None
    total, prev = 0, 0
    for c in reversed(r):
        v = _ROMAN[c]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


_KUHN = re.compile(
    r"""^\s*(?:k(?:ühn|uhn|uehn)?\.?\s*)?(?:vol\.?\s*)?
        (?P<vol>\d{1,2}|[ivxl]{1,7})\s*(?P<part>[ab])?   # 15, 18a, XV, XVIII A
        \s*[\s.,:]\s*(?:p{1,2}\.?\s*)?
        (?P<p1>\d{1,4})(?:\s*[-–]\s*(?P<p2>\d{1,4}))?\s*$""",
    re.X | re.I,
)


def parse_kuhn(s: str):
    """'K15.609', 'K. XV 609', 'Kühn 18a, 196', 'K XVIII A 196-197' -> ('15', 609, None) etc.

    Returns (vol_key, first_page, last_page_or_None) or None. vol_key is '15', '18a' ...
    """
    m = _KUHN.match(s or "")
    if not m:
        return None
    vol = m.group("vol")
    if vol.isdigit():
        n = int(vol)
    else:
        n = roman_to_int(vol)
        if n is None:
            return None
    part = (m.group("part") or "").lower()
    p2 = int(m.group("p2")) if m.group("p2") else None
    return f"{n}{part}", int(m.group("p1")), p2


def roman(n: int) -> str:
    out = []
    for v, sym in ((50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out.append(sym)
            n -= v
    return "".join(out)


def vol_label(vol_key: str) -> str:
    """'18a' -> 'XVIIIA', '15' -> 'XV' (Kühn's own style)."""
    m = re.match(r"(\d+)([ab]?)$", vol_key)
    return roman(int(m.group(1))) + m.group(2).upper() if m else vol_key


def clip(s: str, n: int) -> tuple[str, int]:
    """Clip to n chars at a word boundary; returns (text, chars_dropped)."""
    s = s or ""
    if len(s) <= n:
        return s, 0
    cut = s.rfind(" ", 0, n)
    cut = cut if cut > n * 0.8 else n
    return s[:cut].rstrip() + " …", len(s) - cut
