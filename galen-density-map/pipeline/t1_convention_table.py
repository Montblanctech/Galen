"""T1 — the convention table: where two lemmatizers disagree by *convention* rather than by error.

Input: the per-author `disagreements.csv` files of the 50-author runs (odyCy reference vs Dilemma). Output:
outputs/t1/convention_pairs.csv — every (odyCy lemma, Dilemma lemma) pair seen >= 20 times, with its token count,
number of authors, a mechanical class, and three example surfaces; outputs/t1/convention_summary.json with the share
of all disagreement tokens each class explains. Classes (regex heuristics, documented, no judgment of who is right):
  article          one side is a form of the article (ὁ / ἡ / τό / τῶν ...)
  adverb_vs_adj    one side ends in -ῶς / -ως and the other is the adjective (-ος)
  comparative      one side is a comparative/superlative (-τερος/-τατος/-ίων/-ιστος) and the other its positive or another grade
  pronoun_form     one side is a pronoun surface kept as lemma (αὐτοῦ, ἡμεῖς, τι/τί, ὅσα ...)
  sigma_tau        σσ ↔ ττ (Attic/Ionic spelling of the same word)
  accent_only      same letters, different accent/breathing
  gender_form      -ος ↔ -η/-α or -ον of the same stem (gender/number of an adjective kept as lemma)
  stem_shared      first five letters shared (likely the same word, one side inflected or mis-formed)
  other            none of the above (the real review queue)
Report only. Usage: python t1_convention_table.py --runs-dir <dir of <tlg>/disagreements.csv>
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

OUT = ROOT / "outputs" / "t1"
ARTICLE = {"ὁ", "ἡ", "τό", "τοῦ", "τῆς", "τῷ", "τῇ", "τόν", "τήν", "οἱ", "αἱ", "τά", "τῶν", "τοῖς", "ταῖς", "τούς", "τάς", "τὸ", "τὴν", "τὸν", "τὰ", "τὰς", "τοὺς", "τώ", "τοῖν"}
PRON = {"αὐτοῦ", "αὐτῆς", "αὐτῶν", "ἡμεῖς", "ὑμεῖς", "τι", "τί", "τίς", "τις", "ὅσα", "ὅσον", "ὅσος", "τοιαῦτα", "ταῦτα", "τοῦτο", "ἐγώ", "σύ", "σός", "ὅπερ", "ὅσπερ", "τινί", "τινά"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def strip_acc(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()


def classify(a: str, b: str) -> str:
    A, B = nfc(a), nfc(b)
    if A in ARTICLE or B in ARTICLE:
        return "article"
    sa, sb = strip_acc(A), strip_acc(B)
    if sa == sb:
        return "accent_only"
    if A in PRON or B in PRON:
        return "pronoun_form"
    if (sa.endswith("ως") and sb.endswith("ος") and sa[:-2] == sb[:-2]) or (sb.endswith("ως") and sa.endswith("ος") and sb[:-2] == sa[:-2]):
        return "adverb_vs_adj"
    comp = re.compile(r"(τερος|τατος|τερον|τατον|ιων|ιστος|ττων|σσων)$")
    if comp.search(sa) != comp.search(sb) and (comp.search(sa) or comp.search(sb)):
        return "comparative"
    if sa.replace("σσ", "ττ") == sb.replace("σσ", "ττ"):
        return "sigma_tau"
    if sa[:-2] == sb[:-2] and len(sa) > 4 and {sa[-2:], sb[-2:]} <= {"ος", "ον", "ης", "ας", "ην", "αν", "ια", "ιη"}:
        return "gender_form"
    if sa[:5] == sb[:5] and len(sa) >= 5:
        return "stem_shared"
    return "other"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--min-count", type=int, default=20)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    pairs: Counter = Counter()
    authors: dict = defaultdict(set)
    examples: dict = defaultdict(Counter)
    total = 0
    cols = None
    for sub in sorted(a.runs_dir.iterdir()):
        f = sub / "disagreements.csv"
        if not f.exists():
            continue
        with f.open(encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            if cols is None:
                cols = rd.fieldnames
            for r in rd:
                la, lb = nfc(r.get("lemma_reference", "")), nfc(r.get("lemma_dilemma", ""))
                if not la or not lb or la == lb:
                    continue
                total += 1
                pairs[(la, lb)] += 1
                authors[(la, lb)].add(r.get("author", sub.name))
                examples[(la, lb)][nfc(r.get("surface", ""))] += 1
    rows = []
    cls_tokens: Counter = Counter()
    for (la, lb), n in pairs.items():
        c = classify(la, lb)
        cls_tokens[c] += n
        if n >= a.min_count:
            rows.append({"odycy_lemma": la, "dilemma_lemma": lb, "tokens": n, "authors": len(authors[(la, lb)]), "class": c,
                         "surfaces": "; ".join(f"{s}:{k}" for s, k in examples[(la, lb)].most_common(3))})
    rows.sort(key=lambda r: -r["tokens"])
    with (OUT / "convention_pairs.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = {"date": "2026-11-07", "disagreement_tokens": total, "distinct_pairs": len(pairs), "pairs_listed_min_count": a.min_count, "pairs_listed": len(rows),
               "tokens_by_class": dict(cls_tokens.most_common()), "share_by_class_pct": {k: round(100 * v / total, 2) for k, v in cls_tokens.most_common()},
               "top_pairs": [{"odycy": r["odycy_lemma"], "dilemma": r["dilemma_lemma"], "tokens": r["tokens"], "class": r["class"]} for r in rows[:25]],
               "note": "classes are regex heuristics over the two lemma strings; they name a convention difference, not who is right; 'other' is the review queue"}
    (OUT / "convention_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("disagreement_tokens", "distinct_pairs", "pairs_listed", "share_by_class_pct")}, indent=1, ensure_ascii=False))
    for t in summary["top_pairs"][:15]:
        print(t)


if __name__ == "__main__":
    main()
