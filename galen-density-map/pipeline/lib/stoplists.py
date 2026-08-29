from __future__ import annotations

import re
from pathlib import Path

from .greek_normalize import casefold_greek, nfc

# Explicit numeral pattern (Kühn-style letter + prime). Auditable units rule,
# not a fuzzy short-token filter.
NUMERAL_LEMMA_RE = re.compile(
    r"^[αβγδεζηθικλμνξοπρστυφχψωϛστ]{1,4}[΄ʹ′']$",
    re.UNICODE,
)


def load_stoplist(path: Path) -> set[str]:
    """Load a one-lemma-per-line stoplist; ignore blanks and # comments."""
    items: set[str] = set()
    if not path.exists():
        raise FileNotFoundError(f"Stoplist not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        items.add(casefold_greek(nfc(line)))
    return items


def is_numeral_lemma(lemma: str) -> bool:
    return bool(NUMERAL_LEMMA_RE.match(casefold_greek(nfc(lemma))))


def default_stoplist_dir(project_root: Path) -> Path:
    return project_root / "data" / "stoplists"
