"""Feasibility: count CTS citations (urn:cts:latinLit:...) in Perseus Lewis & Short.
Run: python -X utf8 -I pipeline/lsjgold/latin_ls_counts.py   (reads data/latin_feasibility/lat.ls.perseus-eng2.xml,
writes data/latin_feasibility/ls_citation_counts.json)."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

GDM = Path(__file__).resolve().parent.parent.parent
D = GDM / "data" / "latin_feasibility"
URN = re.compile(r"^urn:cts:latinLit:((?:phi|stoa)\d{4})\.((?:phi|stoa)\d{3})(?:\.([\w-]+))?(?::(.*))?$")


def main() -> None:
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, recover=True, huge_tree=True)
    tree = etree.parse(str(D / "lat.ls.perseus-eng2.xml"), parser)
    entries = tree.xpath("//entryFree")
    per_entry: Counter = Counter()
    per_work: Counter = Counter()
    per_author: Counter = Counter()
    work_versions: dict = {}
    loc_depth: dict = {}
    author_only: Counter = Counter()
    plain: Counter = Counter()
    no_n = 0
    bare = other_urn = greek = nolocator = 0
    total = 0
    for e in entries:
        key = e.get("key") or e.get("id") or ""
        eid = e.get("id")
        for b in e.xpath(".//bibl"):
            n = b.get("n") or ""
            if n.startswith("urn:cts:greekLit"):
                greek += 1
                continue
            if re.fullmatch(r"urn:cts:latinLit:(?:phi|stoa)\d{4}", n):
                author_only[n.rsplit(":",1)[-1]] += 1
                continue
            m = URN.match(n)
            if not m:
                if n:
                    other_urn += 1
                    plain[re.sub(r"[\d.]+$", "", n).strip()] += 1
                else:
                    no_n += 1
                continue
            a, w, ver, loc = m.groups()
            total += 1
            per_entry[eid] += 1
            per_work[f"{a}.{w}"] += 1
            per_author[a] += 1
            work_versions.setdefault(f"{a}.{w}", Counter())[ver or "-"] += 1
            if not loc:
                nolocator += 1
            d = len(loc.split(":")) if loc else 0
            loc_depth.setdefault(f"{a}.{w}", Counter())[d] += 1
    dist = Counter("1" if n == 1 else "2-5" if n <= 5 else "6+" for n in per_entry.values())
    out = {
        "entries_total": len(entries),
        "entries_with_latin_cts_citation": len(per_entry),
        "citations_total": total,
        "citations_without_locator": nolocator,
        "greek_urn_bibls_skipped": greek,
        "bibls_author_only_urn": sum(author_only.values()),
        "bibls_author_only_by_author": dict(author_only.most_common()),
        "bibls_plain_text_n_no_urn": other_urn,
        "bibls_plain_text_by_label_top60": dict(plain.most_common(60)),
        "bibls_without_n": no_n,
        "entry_distribution": dict(dist),
        "per_work": dict(per_work.most_common()),
        "per_author": dict(per_author.most_common()),
        "work_versions": {k: dict(v) for k, v in work_versions.items()},
        "locator_depth_by_work": {k: dict(v) for k, v in loc_depth.items()},
    }
    (D / "ls_citation_counts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in out.items() if not isinstance(v, dict) or k == "entry_distribution"})
    print(len(per_work), "works", len(per_author), "authors")


if __name__ == "__main__":
    main()
