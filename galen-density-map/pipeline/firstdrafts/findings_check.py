"""Galen First Drafts — findings catalogue: check and merge the model readers' items (2026-11-11).

Each reader wrote JSONL items {work?, category, title, summary, unit_id, locus, quote, greek, checks, confidence, note}
from the drafts' rendering A. An item is kept only if:
  1. its unit_id exists in the work's units.jsonl;
  2. its quote occurs verbatim (whitespace-normalised) in that unit's rendering A;
  3. every word of its greek occurs in that unit's greek_plain (accent-sensitive, punctuation stripped).
Kept items go to outputs/firstdrafts/findings/findings.jsonl (+ findings.csv); dropped items and reasons to dropped.jsonl.
Nothing is edited: an item is kept or dropped as the reader wrote it.

  python -X utf8 pipeline/firstdrafts/findings_check.py <reader jsonl> ... [--default-work comp-per-genera ...]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GDM, WORKS, read_jsonl  # noqa: E402

OUT = GDM / "outputs" / "firstdrafts"


def ws(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").replace("­", "")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def gwords(s: str) -> list[str]:
    return [w for w in re.findall(r"[Ͱ-Ͽἀ-῿’']+", unicodedata.normalize("NFC", s or "")) if re.search(r"[Ͱ-Ͽἀ-῿]", w)]


_cache: dict = {}


def work_data(slug: str):
    if slug not in _cache:
        units = {u["unit_id"]: u for u in read_jsonl(OUT / slug / "units.jsonl")}
        ren = {}
        for r in read_jsonl(OUT / slug / "renderings_fable-5-1.jsonl"):
            if r.get("ok") or ("ok" not in r and (r.get("response") or {}).get("translation")):   # cycle 1 rows carry no "ok" key
                ren[r["unit_id"]] = ws((r.get("response") or {}).get("translation", ""))
        _cache[slug] = (units, ren)
    return _cache[slug]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--default-work", action="append", default=[], help="file=slug for readers that wrote no 'work' key")
    a = ap.parse_args()
    default = dict(x.split("=", 1) for x in a.default_work)
    kept, dropped = [], []
    for f in a.files:
        for n, it in enumerate(read_jsonl(f), 1):
            slug = it.get("work") or default.get(f.name)
            why = None
            if slug not in WORKS:
                why = f"unknown work {slug!r}"
            else:
                units, ren = work_data(slug)
                uid = it.get("unit_id", "")
                if uid not in units:
                    why = f"unknown unit {uid!r}"
                elif ws(it.get("quote", "")) not in ren.get(uid, ""):
                    why = "quote not verbatim in rendering A of the unit"
                else:
                    gp = unicodedata.normalize("NFC", units[uid]["greek_plain"])
                    gw = gwords(it.get("greek", ""))
                    if not gw:
                        why = "no Greek given"
                    elif any(w.strip("'’") not in gp for w in gw):
                        why = "greek not in the unit's Greek"
            rec = {"work": slug, **{k: it.get(k, "") for k in ("category", "title", "summary", "unit_id", "locus", "quote", "greek", "checks", "confidence", "note")},
                   "reader_file": f.name, "reader_line": n}
            if why:
                dropped.append({**rec, "why": why})
            else:
                rec["title_work"] = WORKS[slug]["title_eng"]
                kept.append(rec)
    dest = OUT / "findings"
    dest.mkdir(exist_ok=True)
    with (dest / "findings.jsonl").open("w", encoding="utf-8") as fh:
        for r in kept:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (dest / "dropped.jsonl").open("w", encoding="utf-8") as fh:
        for r in dropped:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cols = ["work", "title_work", "category", "title", "summary", "unit_id", "locus", "quote", "greek", "checks", "confidence", "note"]
    with (dest / "findings.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)
    print(json.dumps({"kept": len(kept), "dropped": len(dropped), "by_category": Counter(r["category"] for r in kept),
                      "by_work": Counter(r["work"] for r in kept), "drop_reasons": Counter(r["why"].split(" '")[0] for r in dropped)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
