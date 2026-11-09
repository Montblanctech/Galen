"""Shared paths, work table and helpers for Galen First Drafts v0 (spec: firstdrafts_v0_spec.md)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
GDM = PIPE.parent
REPO = GDM.parent
sys.path.insert(0, str(PIPE))

WORKS = {
    "adversus-lycum": {
        "tlg": "tlg093",
        "urn": "urn:cts:greekLit:tlg0057.tlg093.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg093.1st1K-grc1",
        "title_lat": "Adversus Lycum",
        "title_eng": "Against Lycus",
        "kuhn_vol": "XVIIIA",
        "kuhn_vol_short": "18a",
        "kuhn_pages": "196-245",
        "lemmatized_dir": "galen_nonmedical",
        "source_note": "First1KGreek tlg0057.tlg093.1st1K-grc1 (Kühn 1829, vol. 18.1 pp. 196-245; keyboarded by Digital Divide Data for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
}

PUNCT_RE = re.compile(r"[\.\,\;\:\·\!\?\(\)\[\]«»“”\"'’‘]")
SENTENCE_END = (".", ";")  # Greek full stop and question mark; the raised dot is a colon


def out_dir(slug: str) -> Path:
    p = GDM / "outputs" / "firstdrafts" / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def strip_punct(tok: str) -> str:
    return PUNCT_RE.sub("", tok)


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def write_jsonl(p: Path, rows) -> int:
    n = 0
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def token_proxy_greek(words: int) -> int:
    """Pre-registered proxy (spec): Greek words x 4.5 tokens."""
    return int(round(words * 4.5))


def token_proxy_english(words: int) -> int:
    return int(round(words * 1.3))


PRICES_PER_MTOK = {  # claude-api skill table, cached 2026-10-06
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
}
