"""LSJ-Gold lexicon: a form -> lemma list derived from LSJ-Gold, for lemmatizer dictionaries.

0.1 (2026-11-10) was built from LSJ-Gold 0.1; 0.1.1 (2026-11-11) from LSJ-Gold 0.1.1, same rules. The held-out salt below
stays "lsjgold-lexicon-0.1:" in every version, so a headword held out in one version is held out in all.

Asked for on stanfordnlp/stanza#1732 (2026-11-10). Every row is a surface form that LSJ cites for a headword and
that LSJ-Gold relocated into a real edition. Nothing is model-written and nothing is inferred: rows are counted,
filtered by fixed rules, and split by a fixed hash.

Rules (all counted in the README):
  - forms and headwords are NFC; forms keep their case as printed in the edition
  - LSJ's vowel-quantity marks in headwords (^ short, _ long, e.g. "γόνυ^") are removed; they are markup, not spelling
  - a headword with characters outside Greek letters and combining marks (malformed LSJ headwords,
    e.g. a capital written as a detached breathing) is left out, not repaired
  - a form carrying punctuation (8 forms) is left out
  - a form attested under two or more headwords is ambiguous: it goes to ambiguous_forms.tsv with every candidate
    and its count, never into the lexicon
  - held-out split by headword: sha256("lsjgold-lexicon-0.1:" + headword) mod 10 == 0 -> held out (about 10%).
    A model trained on lexicon_train.tsv can still be scored on the LSJ-Gold loci of the held-out headwords.

Usage: python -X utf8 make_lexicon.py <lsj_gold.csv> <out_dir>
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import unicodedata as ud
from collections import Counter, defaultdict
from pathlib import Path

SALT = "lsjgold-lexicon-0.1:"


def nfc(s: str) -> str:
    return ud.normalize("NFC", s.strip())


def greek_word(s: str) -> bool:
    if not s:
        return False
    for ch in ud.normalize("NFD", s):
        if ud.combining(ch):
            continue
        if not ("GREEK" in ud.name(ch, "") and ud.category(ch).startswith("L")):
            return False
    return True


def form_ok(s: str) -> bool:
    # Greek letters and combining marks, plus a final elision mark
    core = s.rstrip("'’ʼ᾽")
    return greek_word(core)


def held_out(headword: str) -> bool:
    return int(hashlib.sha256((SALT + headword).encode("utf-8")).hexdigest(), 16) % 10 == 0


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    stats = Counter(rows_in=len(rows))
    loci = defaultdict(Counter)          # (form, headword) -> validation route counts
    authors = defaultdict(set)
    entry = {}
    for r in rows:
        f, h = nfc(r["surface"]), nfc(r["headword"].replace("^", "").replace("_", ""))
        if h != nfc(r["headword"]):
            stats["rows_quantity_mark_stripped"] += 1
        if not greek_word(h):
            stats["rows_bad_headword"] += 1
            continue
        if not form_ok(f):
            stats["rows_form_with_punctuation"] += 1
            continue
        loci[(f, h)][r["validation"]] += 1
        authors[(f, h)].add(r["author"])
        entry[(f, h)] = r["entry_key"]
    by_form = defaultdict(list)
    for (f, h) in loci:
        by_form[f].append(h)

    cols = ["form", "lemma", "loci", "morpheus_loci", "quoted_loci", "n_authors", "authors", "lsj_entry"]
    lex, amb = [], []
    for f, hs in sorted(by_form.items()):
        if len(hs) > 1:
            amb.append([f, len(hs), " | ".join(f"{h} ({sum(loci[(f, h)].values())})" for h in sorted(hs, key=lambda h: -sum(loci[(f, h)].values())))])
            continue
        h = hs[0]
        c = loci[(f, h)]
        lex.append([f, h, sum(c.values()), c.get("morpheus", 0), c.get("quoted", 0), len(authors[(f, h)]), " ".join(sorted(authors[(f, h)])), entry[(f, h)]])

    def write(name, header, data):
        with (out / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(header)
            w.writerows(data)

    train = [r for r in lex if not held_out(r[1])]
    test = [r for r in lex if held_out(r[1])]
    write("lexicon_all.tsv", cols, lex)
    write("lexicon_train.tsv", cols, train)
    write("lexicon_heldout.tsv", cols, test)
    write("ambiguous_forms.tsv", ["form", "n_headwords", "headwords (loci)"], amb)
    heldout_hw = sorted({r[1] for r in test})
    (out / "heldout_headwords.txt").write_text("\n".join(heldout_hw) + "\n", encoding="utf-8")
    all_hw = {h for (_, h) in loci}
    heldout_set = set(heldout_hw) | {h for h in all_hw if held_out(h)}
    stats.update({
        "pairs": len(loci), "forms": len(by_form), "ambiguous_forms": len(amb), "lexicon_rows": len(lex),
        "lexicon_headwords": len({r[1] for r in lex}), "train_rows": len(train), "heldout_rows": len(test),
        "train_headwords": len({r[1] for r in train}), "heldout_headwords": len(heldout_hw),
        "lsjgold_loci_of_heldout_headwords": sum(1 for r in rows if nfc(r["headword"].replace("^", "").replace("_", "")) in heldout_set),
        "rows_with_morpheus_validation": sum(1 for r in lex if r[3] > 0),
    })
    (out / "stats.json").write_text(json.dumps(dict(stats), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(stats), ensure_ascii=False))


if __name__ == "__main__":
    main()
