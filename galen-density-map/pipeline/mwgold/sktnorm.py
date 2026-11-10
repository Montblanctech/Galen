"""MW-Gold — Sanskrit normalisation shared by every stage (the Sanskrit counterpart of lsgold/latnorm.py).

All comparison happens in IAST (NFC). Monier-Williams headwords arrive in SLP1 (Cologne k1); DCS lemmas, GRETIL
texts, Stanza and ByT5 output are IAST; vidyut speaks SLP1 (slp1_to_iast / iast_to_slp1 wrap indic_transliteration).

key(s): the BLIND comparison key for headwords and lemmas. NFC, lower case, Vedic accents and avagraha removed,
anusvāra / candrabindu / any nasal before a stop folded to one symbol (MW prints saṃ-, DCS prints sam- or saṃ-,
Stanza whatever it saw), ḻ/ḷh -> ḍ/ḍh (Vedic retroflex l), ṁ -> ṃ, trailing homonym digits removed, hyphens and
spaces dropped. Vowel length is NOT folded: it is phonemic. Empty string when nothing is left.

strict(s): NFC, lower case, accents off, digits off; nasals as printed.

join_members(members): the sandhi-joined compound from its members (a + a -> ā, a + i/ī -> e, a + u/ū -> o,
a + ṛ -> ar, a + e/ai -> ai, a + o/au -> au, i + i -> ī, u + u -> ū, final -n/-s/-ḥ left alone), used to compare
a DCS compound span (members are separate tokens with Case=Cpd) with an MW compound headword.
"""
from __future__ import annotations

import re
import unicodedata

from indic_transliteration import sanscript

_DIGITS = re.compile(r"\d+$")
_ACCENTS = re.compile(r"[̱̲̩̣̤̀́̂̍]?")  # handled via NFD filter below
_NASAL_STOP = re.compile(r"(ṅ(?=[kg])|ñ(?=[cj])|ṇ(?=[ṭḍ])|n(?=[td])|m(?=[pb]))")
_SPACE = re.compile(r"[\s\-–—·|]+")
VOWELS = "aāiīuūṛṝḷḹeaioau"

# combining marks that are diacritics of IAST letters (keep) vs accents (drop)
_KEEP_MARKS = {"̄", "̣", "́", "̃", "̍", "̥"}  # macron, dot below, acute (ś), tilde (ñ), vertical line, ring below


def slp1_to_iast(s: str) -> str:
    return unicodedata.normalize("NFC", sanscript.transliterate(s or "", sanscript.SLP1, sanscript.IAST))


def iast_to_slp1(s: str) -> str:
    return sanscript.transliterate(unicodedata.normalize("NFC", s or ""), sanscript.IAST, sanscript.SLP1)


def _strip_accents(s: str) -> str:
    """Remove Vedic accent marks (udātta acute on vowels, svarita grave, anudātta underline) but keep the
    diacritics that are part of IAST letters (ā ṛ ṣ ṭ ñ ś ...)."""
    out = []
    for ch in unicodedata.normalize("NFD", s):
        cat = unicodedata.category(ch)
        if cat == "Mn":
            if ch == "́":            # acute: part of ś, an accent on vowels
                if out and out[-1] in "sS":
                    out.append(ch)
                continue
            if ch in ("̀", "̂", "̱", "̲", "̩", "̍", "̤", "̐"):
                continue
            out.append(ch)
        else:
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def base(s: str) -> str:
    s = unicodedata.normalize("NFC", (s or "").strip())
    s = s.replace("'", "").replace("’", "").replace("ऽ", "")        # avagraha
    s = s.replace("m̐", "ṃ").replace("ṁ", "ṃ").replace("ẏ", "y")
    s = _strip_accents(s).lower()
    s = _DIGITS.sub("", s)
    s = _SPACE.sub("", s)
    return s


def key(s: str) -> str:
    s = base(s)
    s = s.replace("ḻh", "ḍh").replace("ḻ", "ḍ").replace("ḷh", "ḍh")
    s = _NASAL_STOP.sub("ṃ", s)
    return s


def strict(s: str) -> str:
    return base(s)


def join_members(members: list[str]) -> str:
    """Join compound members with external vowel sandhi at each boundary; consonant finals are left as the
    members print them (MW prints the pausa form of a member, DCS too: 'tapas' + 'vin' -> tapasvin is not touched;
    'vāc' + 'pati' is left 'vācpati' and will not match 'vākpati' — such pairs are reported, not patched)."""
    out = ""
    for m in members:
        m = base(m)
        if not out:
            out = m
            continue
        if not m:
            continue
        a, b = out[-1], m[0]
        if a in "aā" and b in "aā":
            out = out[:-1] + "ā" + m[1:]
        elif a in "aā" and b in "iī":
            out = out[:-1] + "e" + m[1:]
        elif a in "aā" and b in "uū":
            out = out[:-1] + "o" + m[1:]
        elif a in "aā" and b == "ṛ":
            out = out[:-1] + "ar" + m[1:]
        elif a in "aā" and m[:2] in ("ai",) or (a in "aā" and b == "e"):
            out = out[:-1] + "ai" + m[1:]
        elif a in "aā" and (b == "o" or m[:2] == "au"):
            out = out[:-1] + "au" + m[1:]
        elif a in "iī" and b in "iī":
            out = out[:-1] + "ī" + m[1:]
        elif a in "uū" and b in "uū":
            out = out[:-1] + "ū" + m[1:]
        elif a in "iī" and b in VOWELS:
            out = out[:-1] + "y" + m
        elif a in "uū" and b in VOWELS:
            out = out[:-1] + "v" + m
        else:
            out = out + m
    return out


TOKEN_RE = re.compile(r"[a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṅṄñÑṭṬḍḌṇṆśŚṣṢḥḤṃṂṁḻ']+")


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text or "")
