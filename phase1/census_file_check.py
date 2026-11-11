"""Check every census row against the TEI file it describes (2026-11-11).

The census copies each edition's title and word count from Open Greek and Latin's catalog. Reading the files showed
that the catalog is wrong for a few editions: titles with a book range that the file does not match, and word counts
far from what the file holds. This script adds three columns to galen_ogl_census.csv and to every work in
galen_ogl_census.json, without changing the catalog's own values:

  greek_words_in_file   Greek words in the TEI <body> (runs of Greek letters), counted from the file in data/raw_xml
  books_in_file         number of book divisions (div subtype="book") in the file; 0 if the file is not divided in books
  catalog_note          where the catalog's title or count disagrees with the file, what the file holds

It also adds to the JSON summary the total of greek_words_in_file beside the catalog's total.

  python -X utf8 phase1/census_file_check.py      (needs the TEI files in galen-density-map/data/raw_xml, or GALEN_RAW_XML)
"""
from __future__ import annotations

import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = Path(os.environ.get("GALEN_RAW_XML", HERE.parent / "galen-density-map" / "data" / "raw_xml"))   # the fetched TEI (not in git)
CSV = HERE / "galen_ogl_census.csv"
JSON = HERE / "galen_ogl_census.json"
NS = "{http://www.tei-c.org/ns/1.0}"
COLS = ["greek_words_in_file", "books_in_file", "catalog_note"]
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
         "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17}
ROMAN_OUT = {v: k for k, v in ROMAN.items()}


def measure(urn: str) -> tuple[int, int]:
    root = ET.parse(RAW / (urn.replace(":", "_") + ".xml")).getroot()
    body = root.find(f".//{NS}body")
    words = len(re.findall(r"[Ͱ-Ͽἀ-῿]+", " ".join(body.itertext()))) if body is not None else 0
    books = sum(1 for d in root.iter(NS + "div") if d.get("subtype") == "book")
    return words, books


def note(title: str, catalog_words: int, words: int, books: int) -> str:
    out = []
    m = re.search(r"\b([IVX]+)\s*[-–]\s*([IVX]+)\s*$", title)
    if m and books and ROMAN.get(m.group(2)) and ROMAN[m.group(2)] != books:
        out.append(f"the catalog title gives books {m.group(1)}-{m.group(2)}; the file holds books I-{ROMAN_OUT.get(books, books)}")
    if catalog_words and words and abs(words - catalog_words) / max(words, 1) > 0.10:
        out.append(f"the catalog gives {catalog_words:,} words; the file holds {words:,} Greek words")
    return "; ".join(out)


def main() -> None:
    with CSV.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = [f for f in reader.fieldnames if f not in COLS]
        rows = list(reader)
    by_urn = {}
    for r in rows:
        w, b = measure(r["urn"])
        r["greek_words_in_file"], r["books_in_file"] = w, b
        r["catalog_note"] = note(r["title"], int(r["wordcount"] or 0), w, b)
        by_urn[r["urn"]] = r
    with CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields + COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    data = json.loads(JSON.read_text(encoding="utf-8"))
    for e in data["works"]:
        r = by_urn.get(e.get("urn"))
        if r:
            for c in COLS:
                e[c] = r[c]
    data["summary"]["total_greek_words_in_files"] = sum(int(r["greek_words_in_file"]) for r in rows)
    data["summary"]["catalog_errors_found"] = sum(1 for r in rows if r["catalog_note"])
    JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in rows:
        if r["catalog_note"]:
            print(r["urn"].split(":")[-1], "|", r["catalog_note"])
    print("catalog total", data["summary"].get("total_wordcount_grc_editions"), "| counted in files", data["summary"]["total_greek_words_in_files"])


if __name__ == "__main__":
    main()
