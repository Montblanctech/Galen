"""How often LSJ cites each headword: entry key -> number of <bibl> citations with a CTS URN, from the Perseus LSJ XML.
Writes data/qc/lsjgold/lsj_citation_counts.json; score.py uses it for the citation-frequency stratum (cited once /
2–5 times / 6 or more). Run: python -X utf8 pipeline/lsjgold/lsj_citation_counts.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
sys.path.insert(0, str(HERE))
from relocate import URN_RE  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    counts: Counter = Counter()
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    for path in sorted((GDM / "data" / "lsj").glob("grc.lsj.perseus-eng*.xml"), key=lambda p: int(re.sub(r"\D", "", p.stem.split("eng")[-1]) or 0)):
        tree = etree.parse(str(path), parser)
        for entry in tree.xpath("//*[local-name()='entryFree'] | //*[local-name()='entry']"):
            key = entry.get("key") or ""
            if not key:
                continue
            n = sum(1 for b in entry.xpath(".//*[local-name()='bibl']") if URN_RE.search(b.get("n") or ""))
            if n:
                counts[key] += n
    out = GDM / "data" / "qc" / "lsjgold" / "lsj_citation_counts.json"
    out.write_text(json.dumps(dict(counts), ensure_ascii=False), encoding="utf-8")
    dist = Counter("1" if n == 1 else "2-5" if n <= 5 else "6+" for n in counts.values())
    print(f"{len(counts):,} entries with a CTS citation; {sum(counts.values()):,} citations; entries cited once {dist['1']:,}, 2-5 {dist['2-5']:,}, 6+ {dist['6+']:,}")


if __name__ == "__main__":
    main()
