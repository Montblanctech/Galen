"""Corpus discovery and loading.

Input is a directory tree of either

* token JSONL files in the Galen Density Project format, one object per line:
  ``{"i", "surface", "lemma", "pos", "morph"}`` (``morph`` ignored), or
* plain-text ``.txt`` files (one work per file), tokenised here on whitespace
  with leading/trailing punctuation stripped.

File stems that are CTS URN safe filenames (``urn_cts_greekLit_tlg0057.tlg008.1st1K-grc1``)
carry the author id (``tlg0057``); ``--author`` filters on it and the summary
stratifies by it. The first directory level under the corpus root is the
*subcorpus* (``galen``, ``galen_nonmedical``, ``reference`` in the project).
Works are loaded one at a time; nothing is held corpus-wide.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .normalize import GREEK_LETTER_RE, nfc

AUTHOR_RE = re.compile(r"(?<![a-z])((?:tlg|stoa|ogl|phi|urn)\d{4})", re.I)
# A token is a maximal run of non-space characters; leading/trailing punctuation
# (anything that is not a Greek letter, Latin letter, digit or an apostrophe) is stripped.
TOKEN_RE = re.compile(r"\S+")
EDGE_PUNCT_RE = re.compile(
    r"^[^\wͰ-Ͽἀ-῿'’᾽᾿]+|[^\wͰ-Ͽἀ-῿'’᾽᾿]+$"
)


@dataclass(slots=True)
class Token:
    i: int
    surface: str
    lemma: str
    pos: str


@dataclass
class WorkRef:
    stem: str
    path: Path
    kind: str  # "jsonl" | "text"
    subcorpus: str
    author: str


@dataclass
class Work:
    ref: WorkRef
    tokens: list[Token] | None = None  # present for JSONL input
    text: str | None = None  # present for text input or when a --text-root file exists
    text_source: str = ""  # "file" | "surfaces_joined" | ""
    notes: list[str] = field(default_factory=list)

    @property
    def stem(self) -> str:
        return self.ref.stem

    @property
    def author(self) -> str:
        return self.ref.author

    @property
    def subcorpus(self) -> str:
        return self.ref.subcorpus

    def surfaces(self) -> list[str]:
        if self.tokens is not None:
            return [t.surface for t in self.tokens]
        return [t.surface for t in tokenize_text(self.text or "")]

    def running_text(self) -> str:
        """Text to feed a lemmatizer that wants running text."""
        if self.text:
            return self.text
        return " ".join(self.surfaces())


def author_of(stem: str) -> str:
    m = AUTHOR_RE.search(stem)
    return m.group(1).lower() if m else "unknown"


def discover_works(
    root: Path,
    *,
    authors: list[str] | None = None,
    subcorpora: list[str] | None = None,
    max_works: int = 0,
) -> list[WorkRef]:
    """Find JSONL/TXT works under ``root`` (recursive), sorted by subcorpus then stem."""
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"corpus root not found: {root}")
    wanted_authors = {a.lower() for a in (authors or [])}
    wanted_sub = set(subcorpora or [])
    refs: list[WorkRef] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".jsonl", ".txt"}:
            continue
        if path.name.startswith("_"):
            continue  # pipeline logs/summaries (_lemmatize_summary_*.json etc.)
        rel = path.relative_to(root)
        subcorpus = rel.parts[0] if len(rel.parts) > 1 else "."
        if wanted_sub and subcorpus not in wanted_sub:
            continue
        author = author_of(path.stem)
        if wanted_authors and author not in wanted_authors:
            continue
        refs.append(
            WorkRef(
                stem=path.stem,
                path=path,
                kind="jsonl" if path.suffix.lower() == ".jsonl" else "text",
                subcorpus=subcorpus,
                author=author,
            )
        )
    refs.sort(key=lambda r: (r.subcorpus, r.stem))
    if max_works:
        refs = refs[:max_works]
    return refs


def read_token_jsonl(path: Path) -> Iterator[Token]:
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            yield Token(
                i=int(row.get("i", n)),
                surface=row.get("surface") or "",
                lemma=row.get("lemma") or "",
                pos=row.get("pos") or "",
            )


def tokenize_text(text: str) -> list[Token]:
    out: list[Token] = []
    for m in TOKEN_RE.finditer(nfc(text)):
        tok = EDGE_PUNCT_RE.sub("", m.group(0))
        if not tok or not GREEK_LETTER_RE.search(tok):
            continue
        out.append(Token(i=len(out), surface=tok, lemma="", pos=""))
    return out


def load_work(ref: WorkRef, text_root: Path | list[Path] | None = None) -> Work:
    """``text_root`` may be one directory or a list searched in order for ``<stem>.txt``."""
    work = Work(ref=ref)
    if ref.kind == "jsonl":
        work.tokens = list(read_token_jsonl(ref.path))
        roots = [] if text_root is None else ([text_root] if isinstance(text_root, (str, Path)) else list(text_root))
        txt = next((Path(r) / f"{ref.stem}.txt" for r in roots if (Path(r) / f"{ref.stem}.txt").exists()), None)
        if txt is not None:
            work.text = txt.read_text(encoding="utf-8")
            work.text_source = "file"
        else:
            work.text_source = "surfaces_joined"
    else:
        work.text = ref.path.read_text(encoding="utf-8")
        work.text_source = "file"
    return work


def context_window(tokens: list[Token], i: int, width: int = 6) -> str:
    """``±width`` surfaces with the target bracketed (M5 sheet convention)."""
    lo, hi = max(0, i - width), min(len(tokens), i + width + 1)
    parts = []
    for j in range(lo, hi):
        s = tokens[j].surface
        parts.append(f"[{s}]" if j == i else s)
    return " ".join(parts)
