"""LSJ-Gold lexicon 0.1.2: set aside the weakest pairs of 0.1.1 for review (2026-11-11).

A pair in 0.1.1 rests either on Morpheus (the form analyses to the headword at one or more loci) or only on LSJ quoting
that single word at the citation. A reading of random samples found the quoted-only pairs on which Dilemma 1.3.15
gives a different lemma to be the weak group: LSJ often quotes a related or cross-referenced word in an entry
(δήμαρχος in the entry δημαρχέω, εὐκαρπείᾳ in εὐθαλής). Those pairs leave the lexicon for review_pairs.tsv.
Dilemma is used only to set pairs aside, never to add or change one: every pair left in the lexicon is LSJ-Gold's.

Inputs: the 0.1.1 folder and dilemma_lemmas.tsv (form, dilemma_lemma: Dilemma 1.3.15, lang grc, convention lsj,
guess=False, bare form, no context). Same held-out split as 0.1 and 0.1.1.

Usage: python -X utf8 lexicon_review.py <lexicon-0.1.1 dir> <dilemma_lemmas.tsv> <out dir>
"""
from __future__ import annotations

import csv
import json
import sys
import unicodedata as ud
from pathlib import Path


# Pairs found wrong by reading that the rule below does not catch (Morpheus validated them accent-blind). Each goes
# to review_pairs.tsv with its reason.
KNOWN_WRONG = {
    ("πόλεων", "πολύς"): "genitive plural of πόλις; matched Epic πολέων of πολύς only because the Morpheus check is accent-blind",
}


def base(s: str) -> str:
    return "".join(c for c in ud.normalize("NFD", (s or "").lower()) if not ud.combining(c)).replace("ς", "σ")


def read(p: Path) -> tuple[list[str], list[dict]]:
    with p.open(encoding="utf-8") as fh:
        r = csv.DictReader(fh, delimiter="\t")
        return list(r.fieldnames or []), list(r)


def write(p: Path, cols: list[str], rows: list[dict]) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    src, dil_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    _, drows = read(dil_path)
    dil = {r["form"]: r["dilemma_lemma"] for r in drows}

    def weak(r: dict) -> bool:
        if (r["form"], r["lemma"]) in KNOWN_WRONG:
            return True
        d = dil.get(r["form"], "")
        return r["morpheus_loci"] == "0" and bool(d) and base(d) != base(r["lemma"])

    def reason(r: dict) -> str:
        return KNOWN_WRONG.get((r["form"], r["lemma"]), "quoted-only; Dilemma gives another lemma")

    stats: dict = {"source": "lsj-gold-lexicon-0.1.1"}
    cols, allrows = read(src / "lexicon_all.tsv")
    review = [dict(r, dilemma_lemma=dil.get(r["form"], ""), reason=reason(r)) for r in allrows if weak(r)]
    keep_keys = {(r["form"], r["lemma"]) for r in allrows if not weak(r)}
    for name in ("lexicon_all.tsv", "lexicon_train.tsv", "lexicon_heldout.tsv"):
        c, rows = read(src / name)
        kept = [r for r in rows if (r["form"], r["lemma"]) in keep_keys]
        write(out / name, c, kept)
        stats[name.replace(".tsv", "_rows")] = len(kept)
    write(out / "review_pairs.tsv", cols + ["dilemma_lemma", "reason"], review)
    stats["review_pairs"] = len(review)
    kept_all = [r for r in allrows if (r["form"], r["lemma"]) in keep_keys]
    stats["lexicon_headwords"] = len({r["lemma"] for r in kept_all})
    stats["rows_with_morpheus_validation"] = sum(1 for r in kept_all if r["morpheus_loci"] != "0")
    _, held = read(src / "lexicon_heldout.tsv")
    hw = sorted({r["lemma"] for r in held if (r["form"], r["lemma"]) in keep_keys})
    (out / "heldout_headwords.txt").write_text("\n".join(hw) + "\n", encoding="utf-8")
    stats["heldout_headwords"] = len(hw)
    stats["train_headwords"] = len({r["lemma"] for r in kept_all}) - len(hw)
    for name in ("ambiguous_forms.tsv", "phrase_only_pairs.tsv"):
        (out / name).write_bytes((src / name).read_bytes())
    (out / "dilemma_lemmas.tsv").write_bytes(dil_path.read_bytes())
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
