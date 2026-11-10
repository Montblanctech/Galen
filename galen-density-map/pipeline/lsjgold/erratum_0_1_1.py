"""LSJ-Gold 0.1.1 — drop the loci whose only evidence is one word inside a quoted phrase.

    python pipeline/lsjgold/erratum_0_1_1.py            # writes the two csv files below
    python pipeline/lsjgold/erratum_0_1_1.py --check    # rebuilds in memory and compares

In 0.1 a locus is validated either by Morpheus (its analyses of the surface contain the headword) or as
"quoted" (the surface matches the form LSJ quotes beside the citation; used when Morpheus had no analysis).
When LSJ quotes a phrase, the quoted route accepted any word of it: the Iliad 9:130 token καὶ is gold κάμνω
because LSJ quotes "οἵ κέ σφιν καὶ νῆσον . . ἐκάμοντο". 0.1.1 keeps a quoted locus only when the quoted form
is that single word, compared on letters only (no accents, breathings, carets or case). Nothing else changes:
the kept rows are the 0.1 rows, unedited, in the same order.

In:  data/qc/lsjgold/lsj_gold_v0.csv (0.1, 93,926 loci)
Out: data/qc/lsjgold/lsj_gold_v0_1_1.csv (kept rows)
     data/qc/lsjgold/lsj_gold_0_1_1_dropped.csv (dropped rows, 0.1 columns)
Then: score.py --gold data/qc/lsjgold/lsj_gold_v0_1_1.csv --from-scored <0.1 lsj_gold_scored.csv>
"""
from __future__ import annotations

import csv
import io
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
QC = HERE.parent.parent / "data" / "qc" / "lsjgold"
SRC = QC / "lsj_gold_v0.csv"
KEEP = QC / "lsj_gold_v0_1_1.csv"
DROP = QC / "lsj_gold_0_1_1_dropped.csv"


def fold(s: str) -> str:
    """Letters only: no accents, breathings, carets or case; final sigma as sigma."""
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c).startswith("L")).lower().replace("ς", "σ")


def phrase_only(row: dict) -> bool:
    """True when the locus's only evidence is one word inside a quoted phrase."""
    if row["validation"] == "morpheus":
        return False
    words = row["quoted_form"].split()
    return not (len(words) == 1 and fold(words[0]) == fold(row["surface"]))


def render(rows: list[dict], cols: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\r\n")  # csv's default, as the 0.1 file was written
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with SRC.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        cols, rows = list(r.fieldnames or []), list(r)
    keep = [x for x in rows if not phrase_only(x)]
    drop = [x for x in rows if phrase_only(x)]
    out = {KEEP: render(keep, cols), DROP: render(drop, cols)}
    if "--check" in sys.argv:
        ok = all(p.read_bytes() == t.encode("utf-8") for p, t in out.items())
        print("OK" if ok else "MISMATCH", {p.name: p.exists() for p in out})
        sys.exit(0 if ok else 1)
    for p, t in out.items():
        p.write_bytes(t.encode("utf-8"))
    print(f"{len(rows)} loci in 0.1 -> {len(keep)} kept ({KEEP.name}), {len(drop)} phrase-only dropped ({DROP.name})")


if __name__ == "__main__":
    main()
