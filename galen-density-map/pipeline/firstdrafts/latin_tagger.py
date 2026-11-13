"""Latin tagger worker for generic.py; runs in the Latin venv (.venv-lat: spaCy 3.8 + LatinCy la_core_web_lg + pycollatinus).

Input JSON  {"words": [pre-tokenised words, punctuation stripped], "model": "la_core_web_lg"}
Output JSON {"lemma": [...], "pos": [...], "collatinus": {lowercased surface: {"first": key, "all": [keys]}}, "versions": {...}}

LatinCy is run the way pipeline/lsgold/latin_caches.py runs it for LS-Gold (Doc of ~200 given words, every pipe but
parser/ner; its enclitic splitter's pieces are mapped back to the input word holding their first character, and the
word takes the lemma and UPOS of its first piece, the host word). Exactly one lemma + UPOS per input word, same order.
Collatinus (pycollatinus 0.1.6, context-free, every analysis) is run on each distinct NOUN/ADJ surface; generic.py uses
it only as the fallback route to a Lewis & Short headword when LatinCy's lemma has no entry. Keys are lsgold.latnorm.key.
Usage: .venv-lat/Scripts/python -X utf8 pipeline/firstdrafts/latin_tagger.py IN.json OUT.json
"""
from __future__ import annotations

import collections
import collections.abc
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lsgold"))
from latnorm import key  # noqa: E402

if not hasattr(collections, "Callable"):
    collections.Callable = collections.abc.Callable  # pycollatinus 0.1.6 on Python >= 3.10 (as lsgold/oracle.py)


def latincy(words: list[str], model: str) -> tuple[list[str], list[str]]:
    import spacy
    from spacy.tokens import Doc

    nlp = spacy.load(model, exclude=["parser", "ner"])
    pipes = list(nlp.pipeline)
    lemmas: list[str] = []
    poses: list[str] = []
    for c0 in range(0, len(words), 200):
        chunk = words[c0:c0 + 200]
        doc = Doc(nlp.vocab, words=chunk)
        for _, proc in pipes:
            doc = proc(doc)
        starts, p = [], 0
        for w in chunk:
            starts.append(p)
            p += len(w) + 1
        lem: list = [None] * len(chunk)
        pos: list = [None] * len(chunk)
        j = 0
        for t in doc:
            while j + 1 < len(chunk) and t.idx >= starts[j + 1]:
                j += 1
            if lem[j] is None:
                lem[j], pos[j] = t.lemma_, t.pos_
        if doc.text.rstrip() != " ".join(chunk) or any(x is None for x in lem):
            raise RuntimeError("latincy changed the text; cannot align tokens")
        lemmas += lem
        poses += pos
    return lemmas, poses


def collatinus(surfaces: list[str]) -> dict:
    from pycollatinus import Lemmatiseur

    lem = Lemmatiseur()
    out = {}
    for s in surfaces:
        first, allk = "", set()
        try:
            for d in lem.lemmatise(s):
                k = key(d.get("lemma", ""))
                if k:
                    first = first or k
                    allk.add(k)
        except Exception:  # noqa: BLE001
            pass
        out[s] = {"first": first, "all": sorted(allk)}
    return out


def main() -> None:
    fin, fout = Path(sys.argv[1]), Path(sys.argv[2])
    req = json.loads(fin.read_text(encoding="utf-8"))
    words = req["words"]
    model = req.get("model", "la_core_web_lg")
    lemmas, poses = latincy(words, model)
    # Collatinus for the NOUN/ADJ surfaces (front end), or for every word when asked (checks.py back-translation scoring)
    want = sorted({w.lower() for w, p in zip(words, poses) if req.get("collatinus_all") or p in {"NOUN", "ADJ"}})
    col = collatinus(want)
    from importlib.metadata import version

    vers = {"spacy": version("spacy"), model: version(model), "pycollatinus": version("pycollatinus")}
    fout.write_text(json.dumps({"lemma": lemmas, "pos": poses, "collatinus": col, "versions": vers}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
