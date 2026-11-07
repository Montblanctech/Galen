"""``greta`` system: GreTa (Riemenschneider & Frank 2023, ACL; ``bowphs/GreTa``).

**Not runnable as a lemmatizer, and this adapter says so.** Checked 2026-11-06:
``bowphs/GreTa`` on Hugging Face is the *pretrained* T5-base encoder-decoder (223M params,
Apache-2.0); the lemmatization numbers on its card (91.14 Perseus) come from fine-tuned weights
that were not published. The authors' repo (``Heidelberg-NLP/ancient-language-models``,
``lemmatization.py``) gives the recipe: UD 2.10 Perseus + PROIEL, input = the token wrapped in
``<special_token_0> … <special_token_1>`` with two words of context either side, output = the
lemma, beam 20, "1–3 days" on a GTX 1080 Ti. ``bowphs/lemmatization-demo`` (0.4B, from
``PhilTa-v2``) has no model card and its ``main.py`` is a placeholder, so it is not treated as
a lemmatizer either. Stoicheia's paper (Table 5) reports GreTa at 91.17 on its harness, below
the subword baselines.

If someone fine-tunes GreTa for lemmatization and points ``GRETA_DIR`` at the result, this
adapter will load it as a seq2seq model with that input format. Until then it probes as
unavailable with the reason above, so the kit's report records *why* GreTa is missing from a
roster instead of silently dropping it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..corpus import Token, Work
from .base import Availability, System, exc_text

REASON = ("GreTa has no published lemmatization weights (bowphs/GreTa is the pretrained T5; the fine-tuned "
          "lemmatizer behind its card numbers was not released; bowphs/lemmatization-demo has no card and a "
          "placeholder main.py). Fine-tune per Heidelberg-NLP/ancient-language-models lemmatization.py "
          "(UD Perseus+PROIEL, 1-3 GPU-days) and set GRETA_DIR to use it.")


class GretaSystem(System):
    name = "greta"
    kind = "neural"
    token_level = True

    def __init__(self, local_dir: Path | None = None, context: int = 2, beams: int = 4) -> None:
        super().__init__()
        env = os.environ.get("GRETA_DIR")
        self.local_dir = Path(local_dir) if local_dir else (Path(env) if env else None)
        self.context = context
        self.beams = beams
        self._tok: Any = None
        self._model: Any = None

    def probe(self) -> Availability:
        if self.local_dir is None or not (self.local_dir / "config.json").exists():
            return Availability(False, REASON, untested=True)
        try:
            import transformers  # noqa: F401
        except Exception as exc:
            return Availability(False, f"transformers import failed: {exc_text(exc)}", untested=True)
        return Availability(True, f"GreTa-style seq2seq lemmatizer at {self.local_dir} (adapter untested)", {"dir": str(self.local_dir)}, untested=True)

    def _load(self) -> None:
        if self._model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._tok = AutoTokenizer.from_pretrained(str(self.local_dir))
            self._model = AutoModelForSeq2SeqLM.from_pretrained(str(self.local_dir)).eval()

    def run(self, work: Work) -> list[Token] | None:
        try:
            self._load()
        except Exception as exc:
            self.last_skip_reason = f"GreTa load failed: {exc_text(exc)}"
            return None
        from ..corpus import tokenize_text

        src = work.tokens if work.tokens is not None else tokenize_text(work.text or "")
        words = [t.surface for t in src]
        out: list[Token] = []
        try:
            import torch

            for i, t in enumerate(src):
                lo, hi = max(0, i - self.context), min(len(words), i + self.context + 1)
                left = " ".join(words[lo:i])
                right = " ".join(words[i + 1 : hi])
                text = f"{left} <special_token_0> {t.surface} <special_token_1> {right}".strip()
                enc = self._tok(text, return_tensors="pt", truncation=True, max_length=512)
                with torch.no_grad():
                    gen = self._model.generate(**enc, num_beams=self.beams, max_new_tokens=24)
                lemma = self._tok.decode(gen[0], skip_special_tokens=True).strip()
                out.append(Token(i=t.i, surface=t.surface, lemma=lemma, pos=""))
        except Exception as exc:
            self.last_skip_reason = f"GreTa inference failed on {work.stem}: {exc_text(exc)}"
            return None
        return out
