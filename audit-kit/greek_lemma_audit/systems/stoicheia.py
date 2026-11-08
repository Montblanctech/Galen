"""``stoicheia`` system: Stoicheia tagger-parser (Cullhed & Thörn Cleland 2026, arXiv 2608.07249).

Checkpoint ``Ericu950/Stoicheia-tagger-parser`` (Hugging Face, Apache-2.0): a 405M-parameter
character-level encoder with four heads, one of them an **edit-script lemmatizer** rescored
against a lexicon (``decode_lemma(..., use_lexicon=True)``). Loaded through ``transformers``
with ``trust_remote_code=True`` from a LOCAL snapshot directory (``STOICHEIA_DIR`` or
``--stoicheia-dir``); the kit never downloads it. The snapshot's custom code was read before
first use (2026-11-06): no network, shell or file side effects.

Needs ``transformers >= 4.45`` (older releases cannot read its safetensors metadata), which
conflicts with ``spacy-transformers 1.3.5`` (odyCy); run Stoicheia in its own venv.

Token-level in the sense that it takes pre-split words: the anchor surfaces of each work are fed
as pseudo-sentences of at most ``words_per_sentence`` words (the model's window is 2,048
characters), so there is no alignment loss. Lemma = ``decode(..., ud=True)[..]["lemma"]``;
``upos`` is kept as pos. Reported with the model's own convention caveats (AGDT-style lemmas:
e.g. the article is ὁ, comparatives are their own lemma, proper names capitalised).
"""

from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path
from typing import Any

from ..corpus import Token, Work
from .base import Availability, System, exc_text

REPO = "Ericu950/Stoicheia-tagger-parser"


def nfc(t: str) -> str:
    return unicodedata.normalize("NFC", t or "")


def stoicheia_dir() -> Path | None:
    env = os.environ.get("STOICHEIA_DIR")
    return Path(env) if env else None


class StoicheiaSystem(System):
    name = "stoicheia"
    kind = "neural"
    token_level = True

    def __init__(self, local_dir: Path | None = None, words_per_sentence: int = 40, batch_sentences: int = 16,
                 use_lexicon: bool = True, partial_dir: Path | None = None) -> None:
        super().__init__()
        self.local_dir = Path(local_dir) if local_dir else stoicheia_dir()
        self.partial_dir = Path(partial_dir) if partial_dir else None  # per-work checkpoints: a native crash loses one batch, not the work
        self.words_per_sentence = words_per_sentence
        self.batch_sentences = batch_sentences
        self.use_lexicon = use_lexicon
        self._model: Any = None
        self._proc: Any = None
        self.dropped = 0  # tokens the processor did not return a form for (kept with empty lemma)

    def probe(self) -> Availability:
        if self.local_dir is None:
            return Availability(False, f"no STOICHEIA_DIR / --stoicheia-dir (local snapshot of {REPO}; the kit does not download it)")
        need = ["config.json", "model.safetensors", "vocab.json", "deprel_vocab.json", "processing_char_bert_joint.py", "modeling_char_bert_joint.py"]
        missing = [f for f in need if not (self.local_dir / f).exists()]
        if missing:
            return Availability(False, f"snapshot at {self.local_dir} incomplete: missing {', '.join(missing)}")
        try:
            import torch  # noqa: F401
            import transformers
        except Exception as exc:
            return Availability(False, f"torch/transformers import failed: {exc_text(exc)}")
        ver = tuple(int(x) for x in transformers.__version__.split(".")[:2])
        if ver < (4, 45):
            return Availability(False, f"transformers {transformers.__version__} too old for this checkpoint's safetensors (needs >= 4.45; use a separate venv)",
                                {"transformers": transformers.__version__})
        return Availability(True, f"Stoicheia tagger-parser snapshot at {self.local_dir}, transformers {transformers.__version__} (loaded lazily, CPU unless CUDA present)",
                            {"transformers": transformers.__version__, "repo": REPO, "dir": str(self.local_dir),
                             "words_per_sentence": self.words_per_sentence, "use_lexicon": self.use_lexicon})

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModel

        local = str(self.local_dir)
        if local not in sys.path:
            sys.path.insert(0, local)
        from processing_char_bert_joint import CharBertJointProcessor  # type: ignore

        self._model = AutoModel.from_pretrained(local, trust_remote_code=True).eval()
        self._proc = CharBertJointProcessor.from_pretrained(local)
        self._torch = torch
        meta = self.local_dir / "training_metadata.json"
        if meta.exists():
            self.availability().version["training_metadata"] = meta.name

    def run(self, work: Work) -> list[Token] | None:
        try:
            self._load()
        except Exception as exc:
            self.last_skip_reason = f"Stoicheia load failed: {exc_text(exc)}"
            return None
        from ..corpus import tokenize_text

        src = work.tokens if work.tokens is not None else tokenize_text(work.text or "")
        words = [t.surface for t in src]
        sents = [words[i : i + self.words_per_sentence] for i in range(0, len(words), self.words_per_sentence)]
        out: list[Token] = []
        import json as _json

        partial = (self.partial_dir / f"{work.stem}.partial.jsonl") if self.partial_dir else None
        if partial and partial.exists():
            for line in partial.open(encoding="utf-8"):
                line = line.strip()
                if line:
                    r = _json.loads(line)
                    out.append(Token(i=int(r["i"]), surface=r["surface"], lemma=r.get("lemma") or "", pos=r.get("pos") or ""))
            if len(out) > len(src) or any(o.surface != s.surface for o, s in zip(out, src)):
                out = []  # stale checkpoint from another text: start over
        done_sents = len(out) // self.words_per_sentence
        torch = self._torch
        try:
            for b in range(done_sents, len(sents), self.batch_sentences):
                chunk = sents[b : b + self.batch_sentences]
                before = len(out)
                batch = self._proc(chunk)
                with torch.no_grad():
                    res = self._model(**batch)
                dec = self._proc.decode(res, batch, use_lexicon=self.use_lexicon, ud=True)
                for sent_words, sent in zip(chunk, dec):
                    # The processor may drop a token it cannot encode (numeral signs, stray symbols):
                    # realign by form within the sentence; a dropped token keeps an empty lemma.
                    ptr = 0
                    for word in sent_words:
                        i = len(out)
                        lemma, pos = "", ""
                        if ptr < len(sent) and nfc(sent[ptr].get("form", "")) == nfc(word):
                            lemma, pos = sent[ptr].get("lemma") or "", sent[ptr].get("upos") or ""
                            ptr += 1
                        elif ptr + 1 < len(sent) and nfc(sent[ptr + 1].get("form", "")) == nfc(word):
                            ptr += 1  # the processor emitted an extra piece; skip it
                            lemma, pos = sent[ptr].get("lemma") or "", sent[ptr].get("upos") or ""
                            ptr += 1
                        else:
                            self.dropped += 1
                        out.append(Token(i=src[i].i, surface=src[i].surface, lemma=lemma, pos=pos))
                if partial:
                    partial.parent.mkdir(parents=True, exist_ok=True)
                    with partial.open("a", encoding="utf-8") as fh:
                        for t in out[before:]:
                            fh.write(_json.dumps({"i": t.i, "surface": t.surface, "lemma": t.lemma, "pos": t.pos}, ensure_ascii=False) + chr(10))
        except Exception as exc:
            self.last_skip_reason = f"Stoicheia inference failed on {work.stem}: {exc_text(exc)}"
            return None
        if len(out) != len(src):
            self.last_skip_reason = f"Stoicheia returned {len(out)} words for {len(src)} tokens on {work.stem}"
            return None
        if partial and partial.exists():
            try:
                partial.unlink()
            except OSError:
                pass
        return out
