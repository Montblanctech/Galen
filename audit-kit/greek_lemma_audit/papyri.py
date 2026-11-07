"""Papyrological pre-processing (T2b, first line): make edited papyrus/inscription tokens lemmatizable
and SAY what was changed.

First1K's Philodemus carries the Leiden conventions inside tokens: ``κα[ὶς`` (supplement open),
``δ[εῖ]σθαι`` (restored letters), ``θε〈ῖ〉σιν`` (editorial insertion), ``.ν`` (unread letter), ``σω]‖τηρίαν``
(line break), ``εἰρη||[μένα`` (column break), iota adscript ``τῶι`` for ``τῷ``. 13% of his tokens are
affected (2026-11-06 scan). No lemmatizer in the kit handles them: odyCy emits ``κα[ὶς`` as a lemma.

``normalize_token`` returns the bare reading plus flags; it never guesses letters. Restored and
inserted letters are KEPT (they are the editor's reading) but flagged; unread-letter dots are kept
as ``.`` placeholders only in the flags, removed from the form; breaks are removed. Adscript ωι/ηι at
word end becomes ῳ/ῃ (flagged), αι is left alone (a real diphthong). ``scan_tokens`` counts what a
corpus would be touched by, so the step is reported, not silent.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

SUPPLEMENT = re.compile(r"\[[^\]]*\]")          # [abc]
INSERT = re.compile(r"[〈<][^〉>]*[〉>]")           # 〈abc〉 or <abc>
DELETE = re.compile(r"\{[^}]*\}|⟦[^⟧]*⟧")        # {abc} ⟦abc⟧ editorial deletions: dropped
BREAKS = "‖|"
UNREAD = "."
QUOTES = "“”„\"‘’'ʼ"
ADSCRIPT = {"ωι": "ῳ", "ῶι": "ῷ", "ώι": "ῴ", "ὼι": "ῲ", "ηι": "ῃ", "ῆι": "ῇ", "ήι": "ῄ", "ὴι": "ῂ",
            "Ωι": "ῼ", "Ηι": "ῌ"}


@dataclass
class Normalized:
    form: str
    original: str
    flags: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.form != self.original


def _strip_brackets_keep_letters(s: str, flags: list[str]) -> str:
    # unmatched open/close brackets inside a token (κα[ὶς, σικὴ]ν): the letters are the edition's reading
    if "[" in s or "]" in s:
        if SUPPLEMENT.search(s):
            flags.append("restored_letters")
        else:
            flags.append("supplement_boundary")
        s = s.replace("[", "").replace("]", "")
    if INSERT.search(s) or any(c in s for c in "〈〉<>"):
        flags.append("editorial_insertion")
        s = re.sub(r"[〈〉<>]", "", s)
    if DELETE.search(s):
        flags.append("editorial_deletion_dropped")
        s = DELETE.sub("", s)
    s = s.replace("{", "").replace("}", "").replace("⟦", "").replace("⟧", "")
    return s


def normalize_token(token: str) -> Normalized:
    orig = token
    flags: list[str] = []
    s = unicodedata.normalize("NFC", token or "")
    if any(c in s for c in BREAKS):
        flags.append("line_or_column_break")
        s = "".join(c for c in s if c not in BREAKS)
    if UNREAD in s:
        n = s.count(UNREAD)
        flags.append(f"unread_letters:{n}")
        s = s.replace(UNREAD, "")
    s = _strip_brackets_keep_letters(s, flags)
    if any(c in s for c in QUOTES):
        # keep elision apostrophes (δ’ καθ’) only when final; drop quotation marks anywhere else
        core = s.rstrip("’'ʼ")
        if core != s and len(core) < len(s):
            tail = s[len(core):]
            s = core + ("’" if tail else "")
            if any(c in core for c in QUOTES):
                flags.append("quotation_marks")
                s = "".join(c for c in core if c not in QUOTES) + "’"
        else:
            flags.append("quotation_marks")
            s = "".join(c for c in s if c not in QUOTES)
    if s.startswith("-"):
        flags.append("word_fragment_hyphen")
        s = s.lstrip("-")
    s = s.rstrip("·,;?!")
    for src, dst in ADSCRIPT.items():
        if s.endswith(src):
            flags.append("iota_adscript")
            s = s[: -len(src)] + dst
            break
    s = re.sub(r"\d+$", "", s)  # footnote digit glued to a word (ποιητικήν.1)
    return Normalized(form=s, original=orig, flags=flags)


def scan_tokens(tokens: Iterable[str]) -> dict:
    """Counts for a report: how many tokens the step would touch, by flag."""
    n = touched = 0
    flags: Counter = Counter()
    examples: dict[str, list[str]] = {}
    for t in tokens:
        n += 1
        r = normalize_token(t)
        if r.changed or r.flags:
            touched += 1
            for f in r.flags:
                key = f.split(":")[0]
                flags[key] += 1
                examples.setdefault(key, [])
                if len(examples[key]) < 4:
                    examples[key].append(f"{t} -> {r.form}")
    return {"tokens": n, "touched": touched, "touched_pct": round(100 * touched / n, 2) if n else 0.0,
            "by_flag": dict(flags.most_common()), "examples": examples,
            "policy": "letters inside brackets are kept (the editor's reading) and flagged; unread-letter dots, breaks and quotation "
                      "marks are removed; deletions are dropped; final ωι/ηι become ῳ/ῃ; no letter is ever guessed"}
