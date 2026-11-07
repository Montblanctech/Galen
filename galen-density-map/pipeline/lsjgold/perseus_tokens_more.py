"""LSJ-Gold round 2 - fetch Perseus / First1KGreek editions of cited-but-unheld works and tokenise them.

Reads docs/lsj-gold/coverage.json (held=false works with citations >= --min-citations), tries per work
perseus-grc1, perseus-grc2, perseus-grc3 (PerseusDL/canonical-greekLit) then 1st1K-grc1
(OpenGreekAndLatin/First1KGreek), saves the first that exists, tokenises it exactly as perseus_tokens.py does,
and appends to manifest.json (round: 2) and token_counts.json. Existing files are never touched.
Usage: python -X utf8 pipeline/lsjgold/perseus_tokens_more.py [--min-citations 50] [--authors tlg0006,tlg0014]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import perseus_tokens as pt  # noqa: E402
from lib.config import load_config  # noqa: E402
from lib.greek_normalize import TOKEN_RE, normalize_extracted_text  # noqa: E402

GDM = pt.GDM
COV = GDM.parent / "docs" / "lsj-gold" / "coverage.json"
MAN = GDM / "data" / "perseus_corpus" / "manifest.json"
CNT = GDM / "data" / "perseus_corpus" / "token_counts.json"
PERSEUS = "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/{a}/{w}/{a}.{w}.{e}.xml"
F1K = "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data/{a}/{w}/{a}.{w}.{e}.xml"
EDITIONS = [("perseus-grc1", PERSEUS), ("perseus-grc2", PERSEUS), ("perseus-grc3", PERSEUS), ("1st1K-grc1", F1K)]


def fetch(url: str):
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "galen-lsjgold"}), timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # network hiccup: treat as a non-200 and log
        return f"err:{type(e).__name__}", None


def tokenise(ex, x: Path, sup: bool, gap: bool) -> list[str]:
    tree = etree.parse(str(x), etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True))
    etree.strip_tags(tree, etree.Comment, etree.ProcessingInstruction)
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / x.name
        tree.write(str(tp), encoding="utf-8")
        raw = ex.extract_raw_greek(tp, sup, gap)
    text, _ = normalize_extracted_text(raw)
    toks = []
    for t in TOKEN_RE.findall(text):
        t = unicodedata.normalize("NFC", pt._EDGE.sub("", t))
        if t and pt._GREEK.search(t):
            toks.append(t)
    return toks


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-citations", type=int, default=50)
    ap.add_argument("--authors", default="")
    a = ap.parse_args()
    auth = {s.strip() for s in a.authors.split(",") if s.strip()}
    cov = json.loads(COV.read_text(encoding="utf-8"))
    targets = [w for w in cov["works"] if not w["held"] and w["citations"] >= a.min_citations and (not auth or w["author"] in auth)]
    targets.sort(key=lambda w: -w["citations"])
    ex = pt._load_extract()
    cfg = load_config(None).get("extract", {})
    sup, gap = bool(cfg.get("include_supplied", False)), bool(cfg.get("include_gap_placeholders", False))
    pt.RAW.mkdir(parents=True, exist_ok=True)
    pt.LEM.mkdir(parents=True, exist_ok=True)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    counts = json.loads(CNT.read_text(encoding="utf-8"))
    done = {(w["author"], w["work"]) for w in man["works"]}
    nf = []
    for w in targets:
        au, wk = w["author"], w["work"]
        if (au, wk) in done or list(pt.RAW.glob(f"urn_cts_greekLit_{au}.{wk}.*.xml")):
            print(f"SKIP {au}.{wk} (already have XML)", flush=True)
            continue
        tried, body, used, url = [], None, None, None
        for ed, tmpl in EDITIONS:
            url = tmpl.format(a=au, w=wk, e=ed)
            st, data = fetch(url)
            tried.append({"edition": ed, "status": st})
            if st == 200 and data:
                body, used = data, ed
                break
        if body is None:
            print(f"404 {au}.{wk} {w.get('author_name','')} cites={w['citations']}", flush=True)
            nf.append({"author": au, "work": wk, "author_name": w.get("author_name", ""), "citations": w["citations"], "tried": tried})
            continue
        stem = f"urn_cts_greekLit_{au}.{wk}.{used}"
        xp = pt.RAW / f"{stem}.xml"
        xp.write_bytes(body)
        try:
            toks = tokenise(ex, xp, sup, gap)
        except Exception as e:
            print(f"ERR {stem}: {e}", flush=True)
            nf.append({"author": au, "work": wk, "author_name": w.get("author_name", ""), "citations": w["citations"], "tried": tried, "error": str(e)})
            continue
        with (pt.LEM / f"{stem}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for i, t in enumerate(toks):
                fh.write(json.dumps({"i": i, "surface": t, "lemma": "", "pos": "", "morph": {}}, ensure_ascii=False) + "\n")
        counts[stem] = len(toks)
        man["works"].append({"author": au, "work": wk, "citations": w["citations"], "listed_edition": "perseus-grc1",
                             "tried": tried, "edition_used": used, "bytes": len(body), "http_status": 200, "url": url,
                             "tokens": len(toks), "used_by_relocate": False, "round": 2})
        MAN.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        CNT.write_text(json.dumps(counts, indent=1), encoding="utf-8")
        print(f"OK  {au}.{wk} {w.get('author_name','')} cites={w['citations']} {used} tokens={len(toks)}", flush=True)
    man.setdefault("summary", {})["round2_not_found"] = nf
    MAN.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    (GDM / "data" / "perseus_corpus" / "round2_not_found.json").write_text(json.dumps(nf, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
