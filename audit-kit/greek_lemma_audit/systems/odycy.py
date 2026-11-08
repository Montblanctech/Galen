"""``odycy`` system: spaCy ``grc_odycy_joint_trf`` (odyCy transformer).

Loads the model the way ``galen-density-map/pipeline/03_lemmatize.py`` does
(``spacy.load("grc_odycy_joint_trf")``, frequency_lemmatizer kept enabled,
text fed in <=4000-character chunks split on sentence punctuation) when only running text is
available; with token input it runs token-level over Docs built from the anchor words (no
re-tokenization, no alignment loss). Skips
cleanly when spaCy or the model wheel is missing or broken (the probe records
the import error verbatim, e.g. a numpy ABI mismatch).
"""

from __future__ import annotations

import re
from typing import Any

from ..corpus import Token, Work
from .base import Availability, System, exc_text

MODEL = "grc_odycy_joint_trf"
SENT_SPLIT_RE = re.compile(r"(?<=[.;·])\s+")


def split_chunks(text: str, max_chars: int = 4000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for piece in SENT_SPLIT_RE.split(text):
        add = len(piece) + 1
        if size + add > max_chars and buf:
            out.append(" ".join(buf))
            buf, size = [], 0
        buf.append(piece)
        size += add
    if buf:
        out.append(" ".join(buf))
    final: list[str] = []
    for ch in out:
        if len(ch) <= max_chars:
            final.append(ch)
        else:
            final.extend(ch[i : i + max_chars] for i in range(0, len(ch), max_chars))
    return final


class OdycySystem(System):
    name = "odycy"
    kind = "neural"

    def __init__(self, model: str = MODEL, max_chars: int = 4000, words_per_doc: int = 400) -> None:
        super().__init__()
        self.model = model
        self.max_chars = max_chars
        self.words_per_doc = words_per_doc
        self._nlp = None

    def probe(self) -> Availability:
        try:
            import spacy  # noqa: F401
        except Exception as exc:
            return Availability(False, f"spaCy import failed: {exc_text(exc)}")
        try:
            from spacy.util import is_package

            if not is_package(self.model):
                return Availability(
                    False,
                    f"spaCy model {self.model} not installed (pip install the odyCy 0.7.0 wheel from huggingface.co/chcaa)",
                    {"spacy": spacy.__version__},
                )
        except Exception as exc:
            return Availability(False, f"spaCy model check failed: {exc_text(exc)}")
        return Availability(True, f"spaCy {spacy.__version__}, model {self.model} installed (loaded lazily)",
                            {"spacy": spacy.__version__, "model": self.model})

    def _load(self) -> Any:
        if self._nlp is None:
            import spacy

            self._nlp = spacy.load(self.model)
            meta = getattr(self._nlp, "meta", {}) or {}
            av = self.availability()
            av.version.update({"model_version": meta.get("version"), "pipes": list(self._nlp.pipe_names)})
        return self._nlp

    def run(self, work: Work) -> list[Token] | None:
        try:
            nlp = self._load()
        except Exception as exc:
            self.last_skip_reason = f"model load failed: {exc_text(exc)}"
            return None
        out: list[Token] = []
        if work.tokens is not None and not work.text:
            # Token-level mode: the anchor tokens ARE the tokenization. Build spaCy Docs from the words
            # (context preserved, in windows of words_per_doc) so odyCy never re-tokenizes a surface
            # (brackets, elision marks, hyphens would otherwise split tokens and break alignment).
            from spacy.tokens import Doc

            words_all = [t.surface for t in work.tokens]
            for b in range(0, len(words_all), self.words_per_doc):
                words = words_all[b : b + self.words_per_doc]
                doc = Doc(nlp.vocab, words=words, spaces=[True] * len(words))
                for _name, proc in nlp.pipeline:
                    doc = proc(doc)
                for src, tok in zip(work.tokens[b : b + self.words_per_doc], doc):
                    out.append(Token(i=src.i, surface=src.surface, lemma=tok.lemma_ or "", pos=tok.pos_ or ""))
            return out
        for chunk in split_chunks(work.running_text(), self.max_chars):
            doc = nlp(chunk)
            for tok in doc:
                if tok.is_space or not tok.text.strip():
                    continue
                out.append(Token(i=len(out), surface=tok.text, lemma=tok.lemma_ or "", pos=tok.pos_ or ""))
        return out
