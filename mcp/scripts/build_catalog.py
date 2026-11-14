"""Build the small bundled works catalog (src/galen_mcp/catalog.json) from the published data.

Run from the repo root after the drafts change:  python mcp/scripts/build_catalog.py
It reads docs/first-drafts/<slug>/data.json and docs/method/vitruvius-3/data.json (the same files
GitHub Pages serves) and keeps only what the server needs to route a citation to a work without
downloading every work: titles, Kühn volume and page span, books, unit count and the check summary.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "mcp" / "src" / "galen_mcp" / "catalog.json"


def _pct(summary: dict, key: str):
    s = summary.get(key) or {}
    return s.get("pass_pct")


def entry(path: Path, kind: str) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    w, units = d["work"], d["units"]
    slug = path.parent.name
    summ = (d.get("checks") or {}).get("summary") or {}
    e = {
        "slug": slug,
        "kind": kind,
        "lang": w.get("lang", "grc"),
        "author": w.get("author", "Galen"),
        "title_lat": w.get("title_lat"),
        "title_eng": w.get("title_eng"),
        "authorship": w.get("authorship") or "",
        "prior_translations": w.get("prior_translations") or "",
        "n_units": len(units),
        "n_terms": len(d.get("term_table") or []),
        "first_unit": units[0]["unit_id"],
        "last_unit": units[-1]["unit_id"],
        "unit_verdicts": summ.get("unit_verdicts") or {},
        "checks_pass_pct": {k: _pct(summ, k) for k in ("a", "b", "c")},
        "b_term_agree_pct": (summ.get("b_term_level") or {}).get("pct"),
        "models": {k: (d["renderings"][k][0].get("model") if d["renderings"].get(k) else None) for k in ("A", "B")},
    }
    books = sorted({b for u in units for b in (u.get("books") or [])}, key=lambda x: int(x) if x.isdigit() else 0)
    book_pages = sorted(int(m.group(1)) for p in path.parent.glob("book-*.html") if (m := re.match(r"book-(\d+)\.html$", p.name)))
    e["books"] = books
    e["book_pages"] = book_pages
    if kind == "galen":
        m = re.match(r"K(\d+[ab]?)\.", units[0]["unit_id"])
        e["kuhn_vol"] = w.get("kuhn_vol")
        e["vol"] = m.group(1)
        pages = [int(p) for u in units for p in u.get("pages") or [] if str(p).isdigit()]
        e["page_first"], e["page_last"] = min(pages), max(pages)
    else:
        e["citation"] = w.get("citation")
        e["text_credit"] = w.get("text_credit")
        e["claim"] = w.get("claim")
    return e


def main() -> int:
    works = [entry(p, "galen") for p in sorted((ROOT / "docs" / "first-drafts").glob("*/data.json"))]
    works += [entry(p, "method") for p in sorted((ROOT / "docs" / "method").glob("*/data.json"))]
    OUT.write_text(json.dumps({"works": works}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(works)} works, {OUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
