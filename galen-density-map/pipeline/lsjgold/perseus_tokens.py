"""LSJ-Gold, Perseus editions — tokenise the downloaded Perseus TEI the way the project's pipeline does.

Reuses pipeline/02_extract.py (extract_raw_greek, same config flags) and lib.greek_normalize
(normalize_extracted_text, TOKEN_RE) via importlib; nothing is copied. Tokens = TOKEN_RE split of the normalised
text, edge punctuation glued to a word stripped (the project's JSONL comes from spaCy, which splits punctuation
off; elision marks are kept), only tokens containing a Greek letter are kept. lemma/pos/morph are left empty:
odyCy has not been run on these works; Dilemma scores the surface directly.
The extractor itself is unmodified.
Usage: python -X utf8 pipeline/lsjgold/perseus_tokens.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
GDM = PIPE.parent
sys.path.insert(0, str(PIPE))
from lib.config import load_config  # noqa: E402
from lib.greek_normalize import TOKEN_RE, normalize_extracted_text  # noqa: E402

RAW = GDM / "data" / "perseus_corpus" / "raw_xml"
LEM = GDM / "data" / "perseus_corpus" / "lemmatized"
_EDGE = re.compile(r"^[^\wͰ-Ͽἀ-῿]+|[^\wͰ-Ͽἀ-῿᾽᾿’ʼ']+$")
_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")


def _load_extract():
    spec = importlib.util.spec_from_file_location("extract02", PIPE / "02_extract.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ex = _load_extract()
    cfg = load_config(None).get("extract", {})
    sup, gap = bool(cfg.get("include_supplied", False)), bool(cfg.get("include_gap_placeholders", False))
    LEM.mkdir(parents=True, exist_ok=True)
    counts = {}
    for x in sorted(RAW.glob("urn_cts_greekLit_*.xml")):
        # 02_extract.walk() assumes every node has a string tag; Perseus files carry comments/PIs, so strip those
        # (tails are kept) into a temp copy and run the unchanged extractor on it.
        tree = etree.parse(str(x), etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True))
        etree.strip_tags(tree, etree.Comment, etree.ProcessingInstruction)
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td) / x.name
            tree.write(str(tp), encoding="utf-8")
            raw = ex.extract_raw_greek(tp, sup, gap)
        text, _ = normalize_extracted_text(raw)
        toks = []
        for t in TOKEN_RE.findall(text):
            t = unicodedata.normalize("NFC", _EDGE.sub("", t))
            if t and _GREEK.search(t):
                toks.append(t)
        with (LEM / f"{x.stem}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for i, t in enumerate(toks):
                fh.write(json.dumps({"i": i, "surface": t, "lemma": "", "pos": "", "morph": {}}, ensure_ascii=False) + "\n")
        counts[x.stem] = len(toks)
        print(f"{x.stem}: {len(toks)}", flush=True)
    print("total", sum(counts.values()))
    (GDM / "data" / "perseus_corpus" / "token_counts.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
