"""Feasibility: which cited L&S works have a Latin TEI edition in PerseusDL/canonical-latinLit.
Reads data/latin_feasibility/{ls_citation_counts.json,cll_tree.json}; fetches __cts__.xml names for the top-60 works
(0.3 s pause) and HEAD-probes the raw URLs for perseus-lat1/lat2 of those works; writes editions.json.
Run: python -X utf8 -I pipeline/lsjgold/latin_ls_editions.py"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

GDM = Path(__file__).resolve().parent.parent.parent
D = GDM / "data" / "latin_feasibility"
RAW = "https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/master/"


def get(url: str, method: str = "GET"):
    time.sleep(0.3)
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "galen-feasibility"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, (r.read() if method == "GET" else b"")
    except urllib.error.HTTPError as e:
        return e.code, b""


def names(xml: bytes) -> tuple[str, str]:
    s = xml.decode("utf-8", "replace")
    g = re.search(r"<ti:groupname[^>]*>([^<]*)", s)
    t = re.search(r"<ti:title[^>]*>([^<]*)", s)
    return (g.group(1).strip() if g else ""), (t.group(1).strip() if t else "")


def main() -> None:
    counts = json.loads((D / "ls_citation_counts.json").read_text(encoding="utf-8"))
    tree = json.loads((D / "cll_tree.json").read_text(encoding="utf-8"))["tree"]
    sizes = {i["path"]: i.get("size") for i in tree if i["type"] == "blob"}
    works = list(counts["per_work"].items())
    res = {}
    for rank, (w, n) in enumerate(works, 1):
        a, wk = w.split(".")
        pref = f"data/{a}/{wk}/"
        eds = {p[len(pref):]: s for p, s in sizes.items() if p.startswith(pref) and p.endswith(".xml") and not p.endswith("__cts__.xml")}
        lat = {k: v for k, v in eds.items() if "-lat" in k}
        res[w] = {"rank": rank, "citations": n, "in_repo_tree": f"{pref}__cts__.xml" in sizes,
                  "latin_editions": lat, "other_editions": {k: v for k, v in eds.items() if "-lat" not in k}}
    for w, r in list(res.items())[:60]:
        a, wk = w.split(".")
        s, x = get(f"{RAW}data/{a}/__cts__.xml")
        r["author"] = names(x)[0] if s == 200 else ""
        s, x = get(f"{RAW}data/{a}/{wk}/__cts__.xml")
        r["title"] = names(x)[1] if s == 200 else ""
        r["raw_probe"] = {}
        for ed in ("perseus-lat1", "perseus-lat2"):
            st, _ = get(f"{RAW}data/{a}/{wk}/{a}.{wk}.{ed}.xml", "HEAD")
            r["raw_probe"][ed] = st
    (D / "editions.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    top = list(res.values())[:60]
    print(sum(1 for r in top if r["latin_editions"]), "of top 60 have a Latin edition in the tree")
    print(sum(1 for r in res.values() if r["latin_editions"]), "of", len(res), "all works")


if __name__ == "__main__":
    main()
