"""LS-Gold, stage 4 — blind validation sheet for the Latin relocation itself (same protocol as lsjgold/validation_sheet.py).

Question put to a reader, locus by locus, with nothing from any system shown: *is the bracketed token an instance of
this Lewis & Short headword?* 60 random loci (seed 20261108) + 20 salted controls: 10 anchors (loci whose surface
equals L&S's quoted form exactly and that both oracles validate, so the relocation is certain) and 10 plants (the same
context, but the headword replaced by another headword with the same first letter and a different key: expected `no`).
Shuffled; key to --key-out (outside the repo) until scored by lsjgold/validation_score.py (same columns).
Output: data/qc/lsgold/validation/validation_sheet.csv + reader_instructions.txt + sheet_meta.json.

Run: python -X utf8 -I pipeline/lsgold/validation_sheet_la.py --key-out <private path>
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsgold"
TOKENS = GDM / "data" / "latin_corpus" / "tokens"
SEED = 20261108
N_RANDOM, N_ANCHOR, N_PLANT, WIDTH = 60, 10, 10, 8


def context(stem: str, idx: int, cache: dict) -> str:
    if stem not in cache:
        p = TOKENS / f"{stem}.jsonl"
        if not p.exists():
            raise SystemExit(f"no token stream for {stem}")
        cache[stem] = [json.loads(l)["surface"] for l in p.open(encoding="utf-8")]
    toks = cache[stem]
    lo, hi = max(0, idx - WIDTH), min(len(toks), idx + WIDTH + 1)
    return " ".join(f"[{toks[j]}]" if j == idx else toks[j] for j in range(lo, hi))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=QC / "validation")
    a = ap.parse_args()
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    gold = list(csv.DictReader((QC / "ls_gold_v0.csv").open(encoding="utf-8")))
    cache: dict = {}
    sample = rng.sample(gold, N_RANDOM)
    sample_ids = {id(g) for g in sample}
    exact = [g for g in gold if g["validation"] in ("collatinus", "whitaker") and g["quoted_form"] and g["quoted_form"].strip().lower() == g["surface"].strip().lower() and id(g) not in sample_ids]
    if len(exact) < N_ANCHOR + N_PLANT:
        exact = [g for g in gold if g["validation"] in ("collatinus", "whitaker") and id(g) not in sample_ids]
    anchors = rng.sample(exact, N_ANCHOR)
    anchor_ids = {id(g) for g in anchors}
    plant_src = rng.sample([g for g in exact if id(g) not in anchor_ids], N_PLANT)
    plants = []
    for g in plant_src:
        cands = [h for h in gold if h["headword_key"] != g["headword_key"] and h["headword"][:1].lower() == g["headword"][:1].lower() and h["headword_key"][:3] != g["headword_key"][:3]]
        if not cands:
            cands = [h for h in gold if h["headword_key"] != g["headword_key"]]
        plants.append((g, rng.choice(cands)["headword"]))
    rows, key = [], []
    for g in sample:
        rows.append((g["headword"], g)); key.append({"kind": "random", "expected": "", **g})
    for g in anchors:
        rows.append((g["headword"], g)); key.append({"kind": "anchor", "expected": "yes", **g})
    for g, wrong in plants:
        rows.append((wrong, g)); key.append({"kind": "plant", "expected": "no", "shown_headword": wrong, **g})
    order = list(range(len(rows)))
    rng.shuffle(order)
    with (out / "validation_sheet.csv").open("w", encoding="utf-8", newline="") as fs, a.key_out.open("w", encoding="utf-8", newline="") as fk:
        ws = csv.writer(fs)
        ws.writerow(["row_id", "headword_shown", "surface", "context", "author", "is_instance(yes/no/unsure)", "right_headword_if_no", "note"])
        kcols = ["row_id"] + list(key[0].keys()) + ["shown_headword"]
        wk = csv.DictWriter(fk, fieldnames=kcols, extrasaction="ignore")
        wk.writeheader()
        for n, i in enumerate(order, 1):
            hw, g = rows[i]
            ws.writerow([f"L{n:03d}", hw, g["surface"], context(g["edition_stem"], int(g["token_index"]), cache), g["author"], "", "", ""])
            wk.writerow({"row_id": f"L{n:03d}", **key[i], "shown_headword": key[i].get("shown_headword", key[i]["headword"])})
    (out / "reader_instructions.txt").write_text(
        "LS-GOLD VALIDATION SHEET (Latin)\n\nEach row shows a Lewis & Short headword and a Latin token in brackets inside its context (Perseus canonical-latinLit "
        "text, tokenised stream without punctuation). Answer is_instance = yes if the bracketed token is a form of that headword (any inflection; u/v and i/j "
        "spelling differences do not matter; an enclitic -que/-ne/-ve on the token does not matter), no if it is a form of some other word, unsure if the context "
        "does not let you decide. If no, give the headword the token really belongs to. Use only the sheet and your knowledge of Latin: no lemmatizer, no dictionary "
        f"file, no web, no other file. Answer every row. Rows {len(rows)}: random loci plus salted controls at unmarked positions.\n", encoding="utf-8")
    meta = {"date": datetime.date.today().isoformat(), "seed": a.seed, "gold_rows": len(gold), "n_rows": len(rows), "n_random": N_RANDOM, "n_anchors": N_ANCHOR,
            "n_plants": N_PLANT, "gate": {"anchors_min_yes": 9, "plants_min_no": 8}, "key": "PRIVATE until scored"}
    (out / "sheet_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
