"""T2b spelling data: what ancient scribes actually wrote, from the editors' own regularizations in papyri.info.

The Duke Databank of Documentary Papyri (DDbDP, papyri.info, CC BY 3.0) and the Digital Corpus of Literary
Papyri (DCLP, CC BY 3.0) mark every spelling the editor regularized:
    <choice><reg>ποιητικόν</reg><orig>ποητικόν</orig></choice>
Each document is rendered twice, once as the scribe wrote it (orig) and once regularized (reg). Where the two
renderings have the same number of words they are aligned word by word, and every word whose scriptio-continua
key differs is one (orig, reg) pair. Only spelling regularizations are kept; `<corr>`/`<sic>` (scribal slips the
editor corrected) are a different thing and go to their own list, because a slip is what the flagger should
still flag.

Documents are split into train / test by a hash of the file name (seeded, 1 in 10 to test), so the rules are
learned on train papyri and measured on others.

  python -I -X utf8 pipeline/t2b_spelling_data.py [--idp data/external/idp.data]
Writes data/t2b_cache/spelling_pairs.jsonl (gitignored; regenerable) and outputs/t2b/spelling_data.json (counts).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t2b_scorer as T  # noqa: E402

TEI = "{http://www.tei-c.org/ns/1.0}"
SEED = "t2b-spelling-2026"
TEST_SHARE = 10      # 1 in 10 documents to test


def split_of(name: str) -> str:
    h = int(hashlib.sha256((SEED + name).encode()).hexdigest()[:8], 16)
    return "test" if h % TEST_SHARE == 0 else "train"


def _tag(el) -> str:
    return el.tag[len(TEI):] if isinstance(el.tag, str) and el.tag.startswith(TEI) else str(el.tag)


GAP = "…"   # a gap marker token: words touching it are not used
JOIN = "\x00"     # a line break inside a word: the whitespace around it is removed
_JOIN_RE = re.compile(r"\s*\x00\s*")


def render(el, mode: str, out: list[str]) -> None:
    """Append the text of `el` as `mode` ('orig' or 'reg') would read it. Abbreviations are expanded, editorial
    deletions dropped, supplements kept (the editor's reading), gaps marked."""
    t = _tag(el)
    if t == "choice":
        kids = {_tag(k): k for k in el}
        if "reg" in kids and "orig" in kids:
            pick = kids["orig"] if mode == "orig" else kids["reg"]
        elif "corr" in kids and "sic" in kids:
            pick = kids["sic"] if mode == "orig" else kids["corr"]
        elif "expan" in kids:
            pick = kids["expan"]
        else:
            pick = next(iter(el), None)
        if pick is not None:
            render(pick, mode, out)
        out.append(el.tail or "")
        return
    if t in ("note", "del", "certainty", "milestone", "figure", "g", "handShift", "desc", "rdg", "surplus", "head"):
        if t == "g":
            out.append(" " + GAP + " ")
        out.append(el.tail or "")
        return
    if t == "gap" or t == "space":
        out.append(" " + GAP + " ")
        out.append(el.tail or "")
        return
    if t == "lb":
        out.append(JOIN if el.get("break") == "no" else " ")
        out.append(el.tail or "")
        return
    if t == "app":
        lem = next((k for k in el if _tag(k) == "lem"), None)
        if lem is not None:
            render(lem, mode, out)
        out.append(el.tail or "")
        return
    if t == "subst":
        add = next((k for k in el if _tag(k) == "add"), None)
        if add is not None:
            render(add, mode, out)
        out.append(el.tail or "")
        return
    if t == "num":
        out.append(" " + GAP + " ")   # numerals are letters used as numbers: not words
        out.append(el.tail or "")
        return
    out.append(el.text or "")
    for k in el:
        render(k, mode, out)
    out.append(el.tail or "")


def edition_words(path: Path, mode: str) -> list[str]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    eds = [d for d in root.iter(TEI + "div") if d.get("type") == "edition"]
    words: list[str] = []
    for ed in eds:
        out: list[str] = []
        render(ed, mode, out)
        words += _JOIN_RE.sub("", "".join(out)).split()
    return words


def _key(tok: str) -> str:
    return T.to_continua(tok)


def doc_pairs(path: Path) -> tuple[list[dict], int, int]:
    """Aligned (orig, reg) word pairs of one document, and the number of usable words and of skipped docs."""
    o = edition_words(path, "orig")
    r = edition_words(path, "reg")
    if not o or len(o) != len(r):
        return [], 0, 1
    pairs = []
    n = 0
    for i, (a, b) in enumerate(zip(o, r)):
        if GAP in a or GAP in b:
            continue
        ka, kb = _key(a), _key(b)
        if not ka or not kb:
            continue
        n += 1
        if ka != kb:
            near_gap = (i > 0 and GAP in o[i - 1]) or (i + 1 < len(o) and GAP in o[i + 1])
            pairs.append({"orig": ka, "reg": kb, "near_gap": near_gap})
    return pairs, n, 0


def corr_pairs(path: Path) -> list[dict]:
    """<sic>/<corr> pairs (scribal slips), for the flagger's 'still flag this' check."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    out = []
    for ch in root.iter(TEI + "choice"):
        kids = {_tag(k): k for k in ch}
        if "sic" in kids and "corr" in kids:
            a = _key("".join(kids["sic"].itertext()))
            b = _key("".join(kids["corr"].itertext()))
            if a and b and a != b:
                out.append({"sic": a, "corr": b})
    return out


def reg_words(path: Path) -> list[str]:
    """Every regularized word key of a document (for rule opportunity counts)."""
    return [k for k in (_key(w) for w in edition_words(path, "reg") if GAP not in w) if k]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--idp", default=str(T.PROJECT / "data" / "external" / "idp.data"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    idp = Path(a.idp)
    files = sorted(list((idp / "DDbDP").rglob("*.xml")) + list((idp / "DCLP").rglob("*.xml")))
    if a.limit:
        files = files[: a.limit]
    cache = T.PROJECT / "data" / T.CACHE_DIR_NAME
    cache.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    with open(cache / "spelling_pairs.jsonl", "w", encoding="utf-8") as fh, \
            open(cache / "spelling_regwords.jsonl", "w", encoding="utf-8") as fw:
        for k, p in enumerate(files, 1):
            corpus = "DCLP" if "DCLP" in p.parts else "DDbDP"
            sp = split_of(p.name)
            pairs, n, skipped = doc_pairs(p)
            stats[f"{corpus}_docs"] += 1
            stats[f"{corpus}_docs_unaligned"] += skipped
            stats[f"{sp}_words"] += n
            stats[f"{sp}_pairs"] += len(pairs)
            for x in pairs:
                x.update({"doc": p.stem, "corpus": corpus, "split": sp})
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")
            for x in corr_pairs(p):
                stats[f"{sp}_sic_corr"] += 1
                x.update({"doc": p.stem, "corpus": corpus, "split": sp, "type": "sic"})
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")
            if n:
                fw.write(json.dumps({"doc": p.stem, "split": sp, "words": reg_words(p)}, ensure_ascii=False) + "\n")
            if k % 5000 == 0:
                print(k, len(files), dict(stats), file=sys.stderr, flush=True)
    stats["files"] = len(files)
    out = T.PROJECT / "outputs" / "t2b" / "spelling_data.json"
    out.write_text(json.dumps({"source": "papyri.info idp.data (DDbDP, DCLP), CC BY 3.0", "seed": SEED,
                               "test_share": f"1 in {TEST_SHARE} documents", **dict(stats)}, indent=1),
                   encoding="utf-8")
    print(json.dumps(dict(stats)))


if __name__ == "__main__":
    main()
