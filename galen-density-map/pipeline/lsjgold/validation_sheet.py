"""LSJ-Gold, stage 4 — blind validation sheet for the relocation itself (M5 convention).

Question put to a reader, locus by locus, with nothing from any system shown: *is the bracketed token an
instance of this LSJ headword?* 60 random loci (seed 20261107) + 20 salted controls: 10 anchors (loci whose
surface equals LSJ's quoted form exactly, so the relocation is certain) and 10 plants (the same context, but the
headword replaced by another headword cited in the same LSJ part with a different accent-blind key and the same
first letter: expected `no`). Shuffled; key to --key-out (outside the repo) until scored by validation_score.py.
Output: data/qc/lsjgold/validation/validation_sheet.csv + reader_instructions.txt + sheet_meta.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsjgold"
OUT = QC / "validation"
SEED = 20261107
N_RANDOM, N_ANCHOR, N_PLANT, WIDTH = 60, 10, 10, 8


def context(stem: str, idx: int, cache: dict) -> str:
    if stem not in cache:
        for lem_dir in (GDM / "data" / "lemmatized" / "reference", GDM / "data" / "lemmatized" / "galen"):
            p = lem_dir / f"{stem}.jsonl"
            if p.exists():
                cache[stem] = [json.loads(l)["surface"] for l in p.open(encoding="utf-8")]
                break
    toks = cache.get(stem, [])
    lo, hi = max(0, idx - WIDTH), min(len(toks), idx + WIDTH + 1)
    return " ".join(f"[{toks[j]}]" if j == idx else toks[j] for j in range(lo, hi))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    gold = list(csv.DictReader((QC / "lsj_gold_v0.csv").open(encoding="utf-8")))
    held = {}
    for xml_dir in (GDM / "data" / "reference_corpus" / "raw_xml", GDM / "data" / "raw_xml"):
        for x in xml_dir.glob("urn_cts_greekLit_tlg*.xml"):
            parts = x.stem.split("_")[3].split(".")
            held.setdefault((parts[0], parts[1]), x.stem)
    cache: dict = {}
    sample = rng.sample(gold, N_RANDOM)
    exact = [g for g in gold if g["validation"] == "morpheus" and g["quoted_form"] and g["quoted_form"].strip() == g["surface"].strip() and g not in sample]
    anchors = rng.sample(exact, N_ANCHOR)
    # plants: a certain locus shown with a wrong headword (same first letter, other key, from the same LSJ part)
    by_part: dict[str, list[dict]] = {}
    for g in gold:
        by_part.setdefault(g["lsj_part"], []).append(g)
    plant_src = rng.sample([g for g in exact if g not in anchors], N_PLANT)
    plants = []
    for g in plant_src:
        cands = [h for h in by_part[g["lsj_part"]] if h["headword_key"] != g["headword_key"] and h["headword"][:1] == g["headword"][:1]]
        if not cands:
            cands = [h for h in gold if h["headword_key"] != g["headword_key"]]
        wrong = rng.choice(cands)
        plants.append((g, wrong["headword"]))
    rows, key = [], []
    for g in sample:
        rows.append((g["headword"], g, "")); key.append({"kind": "random", "expected": "", **g})
    for g in anchors:
        rows.append((g["headword"], g, "")); key.append({"kind": "anchor", "expected": "yes", **g})
    for g, wrong in plants:
        rows.append((wrong, g, g["headword"])); key.append({"kind": "plant", "expected": "no", "shown_headword": wrong, **g})
    order = list(range(len(rows)))
    rng.shuffle(order)
    with (OUT / "validation_sheet.csv").open("w", encoding="utf-8", newline="") as fs, a.key_out.open("w", encoding="utf-8", newline="") as fk:
        ws = csv.writer(fs)
        ws.writerow(["row_id", "headword_shown", "surface", "context", "author", "is_instance(yes/no/unsure)", "right_headword_if_no", "note"])
        kcols = ["row_id"] + list(key[0].keys()) + ["shown_headword"]
        wk = csv.DictWriter(fk, fieldnames=kcols, extrasaction="ignore")
        wk.writeheader()
        for n, i in enumerate(order, 1):
            hw, g, _ = rows[i]
            stem = held[(g["author"], g["work"])]
            ws.writerow([f"V{n:03d}", hw, g["surface"], context(stem, int(g["token_index"]), cache), g["author"], "", "", ""])
            wk.writerow({"row_id": f"V{n:03d}", **key[i], "shown_headword": key[i].get("shown_headword", key[i]["headword"])})
    (OUT / "reader_instructions.txt").write_text(
        "LSJ-GOLD VALIDATION SHEET\n\nEach row shows a dictionary headword and a Greek token in brackets inside its context (First1KGreek text, "
        "tokenised stream without punctuation). Answer is_instance = yes if the bracketed token is a form of that headword (any inflection, "
        "any accent variant), no if it is a form of some other word, unsure if the context does not let you decide. If no, give the headword "
        "the token really belongs to. Use only the sheet and your knowledge of Greek: no lemmatizer, no dictionary file, no web, no other file. "
        f"Answer every row. Rows {len(rows)}: random loci plus salted controls at unmarked positions.\n", encoding="utf-8")
    meta = {"date": "2026-11-07", "seed": a.seed, "n_rows": len(rows), "n_random": N_RANDOM, "n_anchors": N_ANCHOR, "n_plants": N_PLANT,
            "gate": {"anchors_min_yes": 9, "plants_min_no": 8}, "key": "PRIVATE until scored"}
    (OUT / "sheet_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
