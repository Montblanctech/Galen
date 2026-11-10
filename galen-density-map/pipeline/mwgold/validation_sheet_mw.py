"""MW-Gold, stage 4 — blind validation sheet for the Sanskrit relocation (the protocol of lsjgold/validation_sheet.py).

Question put to a reader, locus by locus, with nothing from any system shown: *is the bracketed DCS word (or span) an
instance of this Monier-Williams headword?* 60 random loci (seed 20261109) + 20 salted controls: 10 anchors (loci
validated by the DCS lemma whose unsandhied form IS the headword's citation form, so the relocation is certain) and
10 plants (the same context with the headword replaced by another gold headword of the same first letter and a
different key: expected `no`). Shuffled; key to --key-out (outside the repo) until scored by
lsjgold/validation_score.py (same columns: row_id, is_instance(yes/no/unsure), right_headword_if_no, note).
Context: the DCS sentence in unsandhied words (±8 words around the locus), the token or span in brackets; the
headword in IAST with MW's hyphenation of compounds.
Output: data/qc/mwgold/validation/validation_sheet.csv + reader_instructions.txt + sheet_meta.json.

Run (.venv-skt): python -X utf8 -I pipeline/mwgold/validation_sheet_mw.py --key-out <private path>
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
sys.path.insert(0, str(HERE))
from sktnorm import key as skey, slp1_to_iast  # noqa: E402

GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "mwgold"
TOKENS = GDM / "data" / "sanskrit_corpus" / "tokens"
SEED = 20261109
N_RANDOM, N_ANCHOR, N_PLANT, WIDTH = 60, 10, 10, 8


def context(stem: str, idx: int, span: int, cache: dict) -> str:
    if stem not in cache:
        p = TOKENS / f"{stem}.jsonl"
        cache[stem] = [(json.loads(l)["unsandhied"] or json.loads(l)["surface"]) for l in p.open(encoding="utf-8")]
    toks = cache[stem]
    lo, hi = max(0, idx - WIDTH), min(len(toks), idx + span + WIDTH)
    out = []
    for j in range(lo, hi):
        if j == idx:
            out.append("[" + " ".join(toks[idx: idx + span]) + "]")
        elif idx < j < idx + span:
            continue
        else:
            out.append(toks[j])
    return " ".join(out)


def shown_headword(g: dict) -> str:
    """IAST with MW's hyphenation (k2: a—kAra / pra-sidh), accents dropped."""
    k2 = g["k2"].replace("/", "").replace("\\", "").replace("^", "")
    parts = [slp1_to_iast(x) for x in k2.replace("—", "-").split("-") if x]
    return "-".join(parts) if parts else g["headword"]


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
    gold = list(csv.DictReader((QC / "mw_gold_v0.csv").open(encoding="utf-8")))
    cache: dict = {}
    sample = rng.sample(gold, N_RANDOM)
    sample_ids = {id(g) for g in sample}
    exact = [g for g in gold if g["validation"] == "dcs" and int(g["span"]) == 1 and skey(g["unsandhied"] or g["surface"]) == skey(g["headword"]) and id(g) not in sample_ids]
    if len(exact) < N_ANCHOR + N_PLANT:
        exact = [g for g in gold if g["validation"] == "dcs" and id(g) not in sample_ids]
    anchors = rng.sample(exact, N_ANCHOR)
    anchor_ids = {id(g) for g in anchors}
    plant_src = rng.sample([g for g in exact if id(g) not in anchor_ids], N_PLANT)
    plants = []
    for g in plant_src:
        hk = skey(g["headword"])
        cands = [h for h in gold if skey(h["headword"]) != hk and h["headword"][:1] == g["headword"][:1] and skey(h["headword"])[:3] != hk[:3]]
        if not cands:
            cands = [h for h in gold if skey(h["headword"]) != hk]
        plants.append((g, rng.choice(cands)))
    rows, key = [], []
    for g in sample:
        rows.append((shown_headword(g), g)); key.append({"kind": "random", "expected": "", **g})
    for g in anchors:
        rows.append((shown_headword(g), g)); key.append({"kind": "anchor", "expected": "yes", **g})
    for g, wrong in plants:
        rows.append((shown_headword(wrong), g)); key.append({"kind": "plant", "expected": "no", "shown_headword": shown_headword(wrong), **g})
    order = list(range(len(rows)))
    rng.shuffle(order)
    with (out / "validation_sheet.csv").open("w", encoding="utf-8", newline="") as fs, a.key_out.open("w", encoding="utf-8", newline="") as fk:
        ws = csv.writer(fs)
        ws.writerow(["row_id", "headword_shown", "surface", "context", "text", "is_instance(yes/no/unsure)", "right_headword_if_no", "note"])
        kcols = ["row_id"] + list(key[0].keys()) + ["shown_headword"]
        wk = csv.DictWriter(fk, fieldnames=kcols, extrasaction="ignore")
        wk.writeheader()
        for n, i in enumerate(order, 1):
            hw, g = rows[i]
            span = int(g["span"])
            surf = " ".join(context(g["text"], int(g["token_index"]), span, cache).split("[")[1].split("]")[0].split())
            ws.writerow([f"S{n:03d}", hw, surf, context(g["text"], int(g["token_index"]), span, cache), g["text"], "", "", ""])
            wk.writerow({"row_id": f"S{n:03d}", **key[i], "shown_headword": key[i].get("shown_headword", shown_headword(g))})
    (out / "reader_instructions.txt").write_text(
        "MW-GOLD VALIDATION SHEET (Sanskrit)\n\nEach row shows a Monier-Williams headword (IAST; compounds hyphenated as MW prints them) and a Sanskrit word in "
        "brackets inside its sentence. The sentence is given in sandhi-resolved words as the Digital Corpus of Sanskrit segments it: compounds appear as "
        "separate members, so a bracketed span of two or more words is one compound. Answer is_instance = yes if the bracketed word (or the compound the "
        "bracketed members form) is a form of that headword (any inflection, any gender; a derivative entered separately by MW, such as a past participle or "
        "an adverb, counts as its own headword), no if it is a form of some other word, unsure if the context does not let you decide. If no, give the "
        "headword the word really belongs to. Use only the sheet and your knowledge of Sanskrit: no lemmatizer, no dictionary file, no web, no other file. "
        f"Answer every row. Rows {len(rows)}: random loci plus salted controls at unmarked positions.\n", encoding="utf-8")
    meta = {"date": datetime.date.today().isoformat(), "seed": a.seed, "gold_rows": len(gold), "n_rows": len(rows), "n_random": N_RANDOM, "n_anchors": N_ANCHOR,
            "n_plants": N_PLANT, "gate": {"anchors_min_yes": 9, "plants_min_no": 8}, "key": "PRIVATE until scored"}
    (out / "sheet_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
