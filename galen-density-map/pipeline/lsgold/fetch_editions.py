"""LS-Gold, stage 0 — fetch the Latin TEI editions that Lewis & Short cites from PerseusDL/canonical-latinLit.

Reads data/latin_feasibility/editions.json (every cited work with its Latin files in the repo tree) and downloads
each `*-lat*.xml` into data/latin_corpus/raw_xml/<file> (skips files already present with the listed size), plus the
author/work `__cts__.xml` names into data/latin_corpus/editions_manifest.json. Read-only GETs, 0.3 s apart.
Licence of the texts: CC BY-SA 4.0 (Perseus Digital Library); the manifest records it.

Run (.venv): python -X utf8 -I pipeline/lsgold/fetch_editions.py [--top N]
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

GDM = Path(__file__).resolve().parent.parent.parent
FEAS = GDM / "data" / "latin_feasibility"
OUT = GDM / "data" / "latin_corpus"
RAW = "https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/master/"


def get(url: str) -> tuple[int, bytes]:
    time.sleep(0.3)
    req = urllib.request.Request(url, headers={"User-Agent": "galen-lsgold-fetch"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def names(xml: bytes) -> tuple[str, str]:
    s = xml.decode("utf-8", "replace")
    g = re.search(r"<ti:groupname[^>]*>([^<]*)", s)
    t = re.search(r"<ti:title[^>]*>([^<]*)", s)
    return (g.group(1).strip() if g else ""), (t.group(1).strip() if t else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=0, help="only the N most-cited works (0 = all with a Latin edition)")
    a = ap.parse_args()
    eds = json.loads((FEAS / "editions.json").read_text(encoding="utf-8"))
    (OUT / "raw_xml").mkdir(parents=True, exist_ok=True)
    man_path = OUT / "editions_manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    works = [(w, r) for w, r in eds.items() if r.get("latin_editions")]
    if a.top:
        works = works[: a.top]
    t0 = time.time()
    n_ok = n_skip = n_fail = 0
    for w, r in works:
        au, wk = w.split(".")
        m = manifest.setdefault(w, {"author": r.get("author", ""), "title": r.get("title", ""), "citations": r["citations"],
                                    "licence": "CC BY-SA 4.0, Perseus Digital Library (PerseusDL/canonical-latinLit)", "files": {}})
        if not m["author"] or not m["title"]:
            s, x = get(f"{RAW}data/{au}/__cts__.xml")
            if s == 200:
                m["author"] = names(x)[0]
            s, x = get(f"{RAW}data/{au}/{wk}/__cts__.xml")
            if s == 200:
                m["title"] = names(x)[1]
        for fname, size in r["latin_editions"].items():
            dest = OUT / "raw_xml" / fname
            if dest.exists() and dest.stat().st_size == size:
                m["files"][fname] = size
                n_skip += 1
                continue
            s, x = get(f"{RAW}data/{au}/{wk}/{fname}")
            if s == 200 and x:
                dest.write_bytes(x)
                m["files"][fname] = len(x)
                n_ok += 1
            else:
                m["files"][fname] = f"HTTP {s}"
                n_fail += 1
        man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{w} {m['author'][:30]!s:30} {m['title'][:40]!s:40} files={len(r['latin_editions'])} ({time.time()-t0:.0f}s)", flush=True)
    print(f"done: fetched {n_ok}, kept {n_skip}, failed {n_fail}, works {len(works)} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
