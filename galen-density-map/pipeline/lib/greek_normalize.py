"""Unicode / orthographic normalization for extracted Greek text."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Known crasis / elision expansions (surface -> expanded tokens).
# Auditable map — unknown matches of the patterns below are filtered + logged.
CRASIS_EXPANSIONS: dict[str, list[str]] = {
    "κᾀνταῦθα": ["καὶ", "ἐνταῦθα"],
    "κἀνταῦθα": ["καὶ", "ἐνταῦθα"],
    "κᾀνταῦθεν": ["καὶ", "ἐνταῦθεν"],
    "κἀνταῦθεν": ["καὶ", "ἐνταῦθεν"],
    "κᾀπί": ["καὶ", "ἐπί"],
    "κἀπί": ["καὶ", "ἐπί"],
    "κᾀπὶ": ["καὶ", "ἐπί"],
    "κἀπὶ": ["καὶ", "ἐπί"],
    "κᾀγώ": ["καὶ", "ἐγώ"],
    "κἀγώ": ["καὶ", "ἐγώ"],
    "κᾀγὼ": ["καὶ", "ἐγώ"],
    "κἀγὼ": ["καὶ", "ἐγώ"],
    "κᾀκεῖνος": ["καὶ", "ἐκεῖνος"],
    "κἀκεῖνος": ["καὶ", "ἐκεῖνος"],
    "κᾀκεῖ": ["καὶ", "ἐκεῖ"],
    "κἀκεῖ": ["καὶ", "ἐκεῖ"],
    "κᾀν": ["καὶ", "ἐν"],
    "κἀν": ["καὶ", "ἐν"],
    "κοὐ": ["καὶ", "οὐ"],
    "κοὐκ": ["καὶ", "οὐκ"],
    "χὤτι": ["καὶ", "ὅτι"],
    "τοὔνομα": ["τὸ", "ὄνομα"],
    "τοὐναντίον": ["τὸ", "ἐναντίον"],
    "ταὐτό": ["τὸ", "αὐτό"],
    "ταὐτὸ": ["τὸ", "αὐτό"],
    "ταὐτά": ["τὰ", "αὐτά"],
    "ταὐτὰ": ["τὰ", "αὐτά"],
    "ταὐτόν": ["τὸ", "αὐτόν"],
    "ταὐτὸν": ["τὸ", "αὐτόν"],
    "οὐδ'": ["οὐδέ"],
    "οὐδʼ": ["οὐδέ"],
    "οὐδ᾽": ["οὐδέ"],
    "οὐδ": ["οὐδέ"],  # apostrophe lost in some TEI
    "οὔτ'": ["οὔτε"],
    "οὔτʼ": ["οὔτε"],
    "οὔτ᾽": ["οὔτε"],
    "οὔτ": ["οὔτε"],
    "μήτ'": ["μήτε"],
    "μήτʼ": ["μήτε"],
    "μήτ᾽": ["μήτε"],
    "μήτ": ["μήτε"],
    "μηδ'": ["μηδέ"],
    "μηδʼ": ["μηδέ"],
    "μηδ᾽": ["μηδέ"],
    "ἀλλ'": ["ἀλλά"],
    "ἀλλʼ": ["ἀλλά"],
    "ἀλλ᾽": ["ἀλλά"],
    "δ'": ["δέ"],
    "δʼ": ["δέ"],
    "δ᾽": ["δέ"],
    "θ'": ["τε"],
    "θʼ": ["τε"],
    "θ᾽": ["τε"],
    "καθ'": ["κατά"],
    "καθʼ": ["κατά"],
    "καθ᾽": ["κατά"],
    "μεθ'": ["μετά"],
    "μεθʼ": ["μετά"],
    "μεθ᾽": ["μετά"],
    "ὑφ'": ["ὑπό"],
    "ὑφʼ": ["ὑπό"],
    "ὑφ᾽": ["ὑπό"],
    "ἐφ'": ["ἐπί"],
    "ἐφʼ": ["ἐπί"],
    "ἐφ᾽": ["ἐπί"],
    "ἀφ'": ["ἀπό"],
    "ἀφʼ": ["ἀπό"],
    "ἀφ᾽": ["ἀπό"],
}

# Tight patterns only — unknown matches are dropped + logged.
# Do NOT use loose character classes like τ[οὐαὐ] (that nukes το-/τα- words).
CRASIS_UNKNOWN_RE = re.compile(
    r"^(?:"
    r"κ[ἀἁἄἅἆἇᾀᾁᾂᾃᾄᾅᾆᾇ]"  # καί-crasis (κἀ… / κᾀ…)
    r"|χ[ὠὤ]"                 # καί + ὅ- crasis
    r"|το[ὐὔὖὗ]"              # τὸ + vowel (τοὔνομα)
    r"|τα[ὐὔὖὗ]"              # τὰ + vowel (ταὐτό)
    r"|οὐδ['ʼ᾽']"
    r"|μηδ['ʼ᾽']"
    r"|ἀλλ['ʼ᾽']"
    r"|[δθ]['ʼ᾽']"
    r"|καθ['ʼ᾽']|μεθ['ʼ᾽']|ὑφ['ʼ᾽']|ἐφ['ʼ᾽']|ἀφ['ʼ᾽']"
    r")",
    re.UNICODE,
)

GREEK_LETTER_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
TOKEN_RE = re.compile(r"\S+", re.UNICODE)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def casefold_greek(text: str) -> str:
    """Lowercase for case-insensitive lemma counting (ἱπποκράτης == Ἱπποκράτης)."""
    return nfc(text).lower()


def _strip_diacritics(text: str) -> str:
    """NFD then drop combining marks — for orthography pattern match only."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def normalize_lemma_orthography(lemma: str) -> tuple[str, list[str]]:
    """Apply documented orthographic lemma normalizations. Returns (lemma, rules_fired).

    Semantic lemma corrections are out of scope (plan §3). Match patterns on
    diacritic-stripped text so accents do not block (γίγγνομαι ≈ γιγγνομαι).
    """
    out = casefold_greek(lemma) if lemma else lemma
    fired: list[str] = []
    if not out:
        return out, fired
    bare = _strip_diacritics(out)
    # odyCy sometimes doubles γ in γίγνομαι → γίγγνομαι
    if "γιγγν" in bare:
        out2, n = re.subn(r"γγν", "γν", out, count=1)
        if n:
            out = out2
            fired.append("doubled_gamma_gignomai")
    return out, fired


def normalize_lunate_sigma(text: str) -> str:
    """Map lunate ϲ/Ϲ → σ/Σ; word-final σ → ς."""
    text = text.replace("\u03f2", "σ").replace("\u03f9", "Σ")  # ϲ, Ϲ

    def _final_sigma(m: re.Match[str]) -> str:
        word = m.group(0)
        if word.endswith("σ") and len(word) > 1:
            return word[:-1] + "ς"
        if word.endswith("Σ") and len(word) > 1:
            # title-case final: rare after our header strip; still normalize
            return word[:-1] + "ς"
        return word

    # Operate on Greek-letter runs
    return re.sub(r"[\u0370-\u03FF\u1F00-\u1FFF]+", _final_sigma, text)


def is_all_caps_greek_token(token: str) -> bool:
    """True if token is a title/header-like ALL-CAPS Greek word (e.g. ΓΑΛΗΝΟΥ)."""
    letters = [ch for ch in token if GREEK_LETTER_RE.match(ch)]
    if len(letters) < 3:
        return False
    # Must have letters; all letters uppercase; no lowercase Greek
    has_lower = any("\u03b1" <= ch <= "\u03c9" or "\u1f00" <= ch <= "\u1fff" for ch in letters)
    if has_lower:
        return False
    # Uppercase Greek ranges + capital with diacritics in 1Fxx are uncommon in titles;
    # First1K titles are typically plain uppercase Α-Ω / Ϊ Ϋ
    upperish = all(
        ("\u0391" <= ch <= "\u03a9") or ch in "ΪΫΆΈΉΊΌΎΏ"
        or unicodedata.category(ch) == "Lu"
        for ch in letters
    )
    return upperish


def expand_or_filter_crasis(
    token: str, unknown_log: list[str] | None = None
) -> list[str]:
    """Expand known crasis/elision, or drop+log unknown crasis-looking forms."""
    key = nfc(token)
    key_cf = casefold_greek(key)
    # Try exact then casefolded lookup in expansion map
    for candidate in (key, key_cf):
        if candidate in CRASIS_EXPANSIONS:
            return list(CRASIS_EXPANSIONS[candidate])
    # Also try without trailing punctuation
    bare = key.rstrip(".,;:·")
    bare_cf = casefold_greek(bare)
    for candidate in (bare, bare_cf):
        if candidate in CRASIS_EXPANSIONS:
            return list(CRASIS_EXPANSIONS[candidate])

    if CRASIS_UNKNOWN_RE.search(key_cf) or CRASIS_UNKNOWN_RE.search(key):
        if unknown_log is not None:
            unknown_log.append(token)
        return []
    return [token]


def normalize_extracted_text(text: str) -> tuple[str, dict]:
    """
    Full Stage-02 normalization pass.
    Returns (normalized_text, stats).
    """
    stats = {
        "lunate_sigma_chars": text.count("\u03f2") + text.count("\u03f9"),
        "all_caps_tokens_stripped": 0,
        "crasis_expanded": 0,
        "crasis_unknown_dropped": 0,
    }
    unknown_crasis: list[str] = []

    text = nfc(text)
    text = normalize_lunate_sigma(text)

    out_tokens: list[str] = []
    # Preserve newlines as token boundaries
    parts = re.split(r"(\n+)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("\n"):
            if out_tokens and not out_tokens[-1].endswith("\n"):
                out_tokens.append(part)
            elif out_tokens:
                out_tokens[-1] = out_tokens[-1].rstrip("\n") + part
            else:
                out_tokens.append(part)
            continue
        for m in TOKEN_RE.finditer(part):
            tok = m.group(0)
            if is_all_caps_greek_token(tok):
                stats["all_caps_tokens_stripped"] += 1
                continue
            expanded = expand_or_filter_crasis(tok, unknown_crasis)
            if not expanded:
                stats["crasis_unknown_dropped"] += 1
                continue
            if len(expanded) > 1 or (len(expanded) == 1 and expanded[0] != tok):
                if tok in CRASIS_EXPANSIONS or casefold_greek(tok) in CRASIS_EXPANSIONS or casefold_greek(tok.rstrip(".,;:·")) in CRASIS_EXPANSIONS:
                    stats["crasis_expanded"] += 1
            out_tokens.extend(expanded)

    # Re-join: tokens separated by space; keep newline markers
    rebuilt: list[str] = []
    for tok in out_tokens:
        if tok.startswith("\n"):
            if rebuilt:
                rebuilt[-1] = rebuilt[-1].rstrip(" ")
            rebuilt.append(tok)
        else:
            if rebuilt and not rebuilt[-1].endswith("\n"):
                rebuilt.append(" ")
            rebuilt.append(tok)
    result = nfc("".join(rebuilt))
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r" *\n+ *", "\n", result)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    stats["crasis_unknown_examples"] = sorted(set(unknown_crasis))[:50]
    stats["crasis_unknown_types"] = len(set(unknown_crasis))
    return result, stats
