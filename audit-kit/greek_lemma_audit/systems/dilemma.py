"""``dilemma`` / ``dilemma-guess`` systems: Open Greek *Dilemma* (pip ``dilemma-nlp``).

**UNTESTED ADAPTER.** Written against the published API on PyPI (dilemma-nlp
1.3.15, 2026-11-05)::

    from dilemma import Dilemma
    greek = Dilemma(lang="grc", convention="lsj")
    greek.lemmatize("ἀνθρώπους", guess=False)   # "ἄνθρωπος"; None when unresolved

Two variants: ``guess=False`` (lexicon/rules only; unresolved -> empty lemma) and
``guess=True`` (also tries the transformer for unseen forms). Dilemma is a
token-level lemmatizer, so it reuses the anchor tokenisation (no alignment loss).
The data download is several gigabytes (``python -m dilemma download --no-tagger``,
to ``~/.cache/dilemma`` or ``DILEMMA_DATA_DIR``); this adapter never downloads it
and reports when the data directory is missing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..corpus import Token, Work
from .base import Availability, System, exc_text


def dilemma_data_dir() -> Path:
    env = os.environ.get("DILEMMA_DATA_DIR")
    return Path(env) if env else Path.home() / ".cache" / "dilemma"


class DilemmaSystem(System):
    kind = "lexicon"
    token_level = True

    def __init__(self, guess: bool = False, convention: str = "lsj") -> None:
        super().__init__()
        self.guess = guess
        self.convention = convention
        self.name = "dilemma-guess" if guess else "dilemma"
        self._lem: Any = None
        self._memo: dict[str, str] = {}  # surface -> lemma ("" = unresolved); Dilemma is context-free per token

    def probe(self) -> Availability:
        try:
            import dilemma
        except Exception as exc:
            return Availability(False, f"dilemma import failed: {exc_text(exc)} (pip install dilemma-nlp)", untested=True)
        version = getattr(dilemma, "__version__", "unknown")
        data = dilemma_data_dir()
        if not data.exists() or not any(data.iterdir()):
            return Availability(False, f"dilemma {version} importable but data dir {data} is empty/missing "
                                       "(python -m dilemma download --no-tagger; several GB, not done by the kit)",
                                {"dilemma": version, "data_dir": str(data)}, untested=True)
        return Availability(True, f"dilemma {version}, data at {data}, guess={self.guess}, convention={self.convention} "
                                  "(adapter untested)",
                            {"dilemma": version, "data_dir": str(data), "guess": self.guess, "convention": self.convention},
                            untested=True)

    def _load(self) -> Any:
        if self._lem is None:
            from dilemma import Dilemma

            self._lem = Dilemma(lang="grc", convention=self.convention)
        return self._lem

    def run(self, work: Work) -> list[Token] | None:
        try:
            lem = self._load()
        except Exception as exc:
            self.last_skip_reason = f"Dilemma() construction failed: {exc_text(exc)}"
            return None
        src = work.tokens if work.tokens is not None else None
        from ..corpus import tokenize_text

        if src is None:
            src = tokenize_text(work.text or "")
        out: list[Token] = []
        memo = self._memo
        for t in src:
            lemma = memo.get(t.surface)
            if lemma is None:
                try:
                    raw = lem.lemmatize(t.surface, guess=self.guess)
                except Exception as exc:
                    self.last_skip_reason = f"lemmatize() raised: {exc_text(exc)}"
                    return None
                if isinstance(raw, (list, tuple)):
                    raw = raw[0] if raw else None
                lemma = str(raw) if raw else ""
                memo[t.surface] = lemma
            out.append(Token(i=t.i, surface=t.surface, lemma=lemma, pos=""))
        return out
