"""LSJ coverage map: every work the Perseus LSJ cites by CTS URN, with its citation count, whether a free edition is held
here (First1KGreek, Galen, Perseus), and how many citations became gold loci. The works not held are a ranked ask to the
digitisation projects: "this edition would add N citations to the benchmark". Writes docs/lsj-gold/coverage.json and
coverage.html from the LSJ XML, the held-works index and lsj_gold_v0.csv; nothing else.
Run: python -X utf8 pipeline/lsjgold/coverage.py
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsjgold"
DOCS = GDM.parent / "docs" / "lsj-gold"
sys.path.insert(0, str(HERE))
from lsjgold_names import NAMES  # noqa: E402
from relocate import URN_RE, held_works  # noqa: E402


def names() -> tuple[dict, dict]:
    """(author id -> group name, (author, work) -> work name) from the First1K catalog and the Perseus manifest."""
    author, work = {}, {}
    cat = GDM / "data" / "reference_corpus" / "_first1k_catalog.json"
    if cat.exists():
        for e in json.load(cat.open(encoding="utf-8")).get("catalog", []):
            m = re.match(r"urn:cts:greekLit:(tlg\d{4})\.(tlg\d{3})\.", e.get("urn", ""))
            if m:
                author.setdefault(m.group(1), e.get("group_name", ""))
                work.setdefault((m.group(1), m.group(2)), e.get("work_name", ""))
    man = GDM / "data" / "perseus_corpus" / "manifest.json"
    if man.exists():
        for e in json.load(man.open(encoding="utf-8")).get("works", []):
            a, w = e.get("author") or e.get("tlg_author"), e.get("work") or e.get("tlg_work")
            if a and w:
                author.setdefault(a, e.get("author_name", "") or e.get("group_name", ""))
                work.setdefault((a, w), e.get("title", "") or e.get("work_name", ""))
    for k, v in NAMES.items():
        if not author.get(k):
            author[k] = v
    return author, work


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cites: Counter = Counter()
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    for path in sorted((GDM / "data" / "lsj").glob("grc.lsj.perseus-eng*.xml")):
        tree = etree.parse(str(path), parser)
        for bibl in tree.xpath("//*[local-name()='bibl']"):
            m = URN_RE.search(bibl.get("n") or "")
            if m:
                cites[(m.group(1), m.group(2))] += 1
    held = held_works()
    located: Counter = Counter()
    if (QC / "lsj_gold_v0.csv").exists():
        for r in csv.DictReader((QC / "lsj_gold_v0.csv").open(encoding="utf-8")):
            located[(r["author"], r["work"])] += 1
    aname, wname = names()
    rows = []
    for (a, w), n in cites.most_common():
        h = (a, w) in held
        rows.append({"author": a, "author_name": aname.get(a, ""), "work": w, "work_name": wname.get((a, w), ""), "citations": n,
                     "held": h, "edition": held[(a, w)][0].stem.split(".")[-1] if h else "", "located": located.get((a, w), 0)})
    total = sum(cites.values())
    held_c = sum(r["citations"] for r in rows if r["held"])
    by_author_missing: dict = defaultdict(lambda: {"citations": 0, "works": 0})
    for r in rows:
        if not r["held"]:
            by_author_missing[r["author"]]["citations"] += r["citations"]
            by_author_missing[r["author"]]["works"] += 1
    missing_authors = sorted(by_author_missing.items(), key=lambda kv: -kv[1]["citations"])
    out = {"date": json.load((QC / "relocation_stats.json").open(encoding="utf-8")).get("date") if (QC / "relocation_stats.json").exists() else None,
           "lsj_citations_with_cts_urn": total, "cited_works": len(rows), "held_works": sum(1 for r in rows if r["held"]),
           "citations_into_held_works": held_c, "citations_located": sum(located.values()),
           "missing_by_author": [{"author": a, "author_name": aname.get(a, ""), **v} for a, v in missing_authors[:60]], "works": rows}
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "coverage.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    def nm(a, w):
        return html.escape(f"{aname.get(a) or a}, {wname.get((a, w)) or w}")

    h = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>LSJ coverage map</title>",
         "<style>body{font:15px/1.45 Georgia,serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border-bottom:1px solid #ccc;padding:.3rem .5rem;text-align:left;vertical-align:top}th{background:#f3f1ec}td.n{text-align:right}.small{color:#555;font-size:.9em}.no{color:#a33}</style></head><body>",
         f"<h1>LSJ coverage map</h1><p class=small>Every work the Perseus Liddell–Scott–Jones cites by CTS URN: {total:,} citations into {len(rows):,} works. "
         f"Held here in a free edition: {out['held_works']} works, {held_c:,} citations ({100*held_c/total:.1f}%); {out['citations_located']:,} of those became LSJ-Gold loci. "
         f"The rest is the ask: a free TEI edition of a missing work adds its citations to the benchmark. <a href='index.html'>Back to the leaderboard</a>.</p>",
         "<h2>Missing works, by author (top 60)</h2><table><tr><th>author</th><th>works cited, not held</th><th>citations</th></tr>"]
    for e in out["missing_by_author"]:
        h.append(f"<tr><td>{html.escape(e['author_name'] or e['author'])} <span class=small>{e['author']}</span></td><td class=n>{e['works']}</td><td class=n>{e['citations']:,}</td></tr>")
    h.append("</table><h2>All cited works (top 300 by citations)</h2><table><tr><th>work</th><th>citations</th><th>held edition</th><th>gold loci</th></tr>")
    for r in rows[:300]:
        h.append(f"<tr><td>{nm(r['author'], r['work'])} <span class=small>{r['author']}.{r['work']}</span></td><td class=n>{r['citations']:,}</td>"
                 f"<td>{html.escape(r['edition']) if r['held'] else '<span class=no>not held</span>'}</td><td class=n>{r['located']:,}</td></tr>")
    h.append("</table><p class=small>Source: Perseus LSJ XML (bibl/@n), the held editions' file names, and lsj_gold_v0.csv. Regenerate: <code>python pipeline/lsjgold/coverage.py</code>. The full list is in coverage.json.</p></body></html>")
    (DOCS / "coverage.html").write_text("\n".join(h), encoding="utf-8")
    print(f"citations {total:,} into {len(rows):,} works; held {out['held_works']} works / {held_c:,} citations; located {out['citations_located']:,}")
    for e in out["missing_by_author"][:12]:
        print(f"  missing: {e['author_name'] or e['author']} {e['works']} works {e['citations']:,} citations")


if __name__ == "__main__":
    main()
