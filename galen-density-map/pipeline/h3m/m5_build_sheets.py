"""M5 — build the blind reviewer sheets for machine (LLM) adjudication.

Report-only. Nothing under outputs/ or data/lemmatized/ changes.

Sheet A (`m5_reviewer_sheet.csv`): the frozen random-60 (seed 20260725) salted with the
13 known-answer controls per h3_qc_protocol.md §2, shuffled with a documented seed. Reviewer
columns only. The private key (row_id -> control_id + expected answers) is written OUTSIDE
the repo so a reader cannot see it.

Sheet B (`m5_disagreement_sheet.csv`): every M2 disagreement token with ±6 tokens of context
and the candidate lemmas presented as A/B/C in a shuffled, system-blind order. The mapping
(row_id -> which letter is odyCy/perseus/proiel) is written next to the private key.

Usage: python m5_build_sheets.py --key-dir <private dir outside repo> [--seed 20261105]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # galen-density-map/
QC = ROOT / "data" / "qc"
H3M = QC / "h3m"
OUT = H3M / "m5"
LEMMATIZED = ROOT / "data" / "lemmatized"

REVIEWER_COLS = ["surface_form", "lemma_produced", "pos", "one_line_context", "work_stem", "token_index"]


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def load_tokens(work_stem: str) -> list[dict]:
    for sub in ("galen", "galen_nonmedical", "reference"):
        p = LEMMATIZED / sub / f"{work_stem}.jsonl"
        if p.exists():
            with p.open(encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
    raise FileNotFoundError(work_stem)


def context(tokens: list[dict], i: int, width: int = 6) -> str:
    lo, hi = max(0, i - width), min(len(tokens), i + width + 1)
    parts = []
    for j in range(lo, hi):
        s = tokens[j]["surface"]
        parts.append(f"[{s}]" if j == i else s)
    return " ".join(parts)


def build_sheet_a(rng: random.Random, key_dir: Path) -> None:
    random60 = list(csv.DictReader((QC / "accuracy_sample_random60.csv").open(encoding="utf-8")))
    controls = list(csv.DictReader((QC / "accuracy_controls.csv").open(encoding="utf-8")))
    assert len(random60) == 60, len(random60)
    assert len(controls) == 13, len(controls)

    rows = []
    for r in random60:
        rows.append({"kind": "random", "control_id": "", "expected": "", "expected_lemma": "",
                     **{c: r[c] for c in REVIEWER_COLS}})
    for c in controls:
        rows.append({"kind": "control", "control_id": c["control_id"], "expected": c["EXPECTED_answer"],
                     "expected_lemma": c["EXPECTED_correct_lemma"], **{k: c[k] for k in REVIEWER_COLS}})
    rng.shuffle(rows)

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "m5_reviewer_sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row_id", *REVIEWER_COLS, "lemma_correct(y/n/unsure)", "correct_lemma_if_wrong", "note"])
        for n, r in enumerate(rows, 1):
            w.writerow([f"A{n:03d}", *[r[c] for c in REVIEWER_COLS], "", "", ""])
    with (key_dir / "m5_private_key_sheet_a.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row_id", "kind", "control_id", "expected", "expected_lemma", "surface_form", "lemma_produced"])
        for n, r in enumerate(rows, 1):
            w.writerow([f"A{n:03d}", r["kind"], r["control_id"], r["expected"], r["expected_lemma"],
                        r["surface_form"], r["lemma_produced"]])
    print(f"sheet A: {len(rows)} rows (60 random + 13 controls) -> {OUT / 'm5_reviewer_sheet.csv'}")


def build_sheet_b(rng: random.Random, key_dir: Path) -> None:
    dis = list(csv.DictReader((H3M / "m2_disagreements.csv").open(encoding="utf-8")))
    cache: dict[str, list[dict]] = {}
    out_rows, key_rows = [], []
    skipped = 0
    for n, d in enumerate(dis, 1):
        ws, ti = d["work_stem"], int(d["token_index"])
        if ws not in cache:
            try:
                cache[ws] = load_tokens(ws)
            except FileNotFoundError:
                cache[ws] = []
        toks = cache[ws]
        if not toks or ti >= len(toks) or nfc(toks[ti]["surface"]) != nfc(d["surface"]):
            skipped += 1
            continue
        cands = {"odycy": nfc(d["lemma_odycy"]), "perseus": nfc(d["lemma_perseus"]), "proiel": nfc(d["lemma_proiel"])}
        # distinct candidate lemmas, blind letters
        distinct = []
        for sysname, lem in cands.items():
            if lem and lem not in distinct:
                distinct.append(lem)
        rng.shuffle(distinct)
        letters = "ABC"[: len(distinct)]
        letter_of = {lem: letters[i] for i, lem in enumerate(distinct)}
        row_id = f"B{n:04d}"
        out_rows.append([row_id, d["surface"], d["pos"], context(toks, ti), ws, ti,
                         *(distinct + [""] * (3 - len(distinct))), "", "", ""])
        key_rows.append([row_id, d["sample"], *(letter_of.get(cands[s], "") for s in ("odycy", "perseus", "proiel")),
                         cands["odycy"], cands["perseus"], cands["proiel"], d.get("g2a_odycy_perseus", ""), d.get("g2a_odycy_proiel", "")])
    with (OUT / "m5_disagreement_sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row_id", "surface_form", "pos", "context", "work_stem", "token_index",
                    "candidate_A", "candidate_B", "candidate_C", "correct_candidate(A/B/C/none/unsure)",
                    "correct_lemma_if_none", "note"])
        w.writerows(out_rows)
    with (key_dir / "m5_private_key_sheet_b.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row_id", "sample", "letter_odycy", "letter_perseus", "letter_proiel",
                    "lemma_odycy", "lemma_perseus", "lemma_proiel", "g2a_odycy_perseus", "g2a_odycy_proiel"])
        w.writerows(key_rows)
    print(f"sheet B: {len(out_rows)} disagreement rows ({skipped} skipped: token not re-locatable) -> {OUT / 'm5_disagreement_sheet.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-dir", required=True, help="directory OUTSIDE the repo for the private keys")
    ap.add_argument("--seed", type=int, default=20261105)
    a = ap.parse_args()
    key_dir = Path(a.key_dir)
    key_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    build_sheet_a(rng, key_dir)
    build_sheet_b(rng, key_dir)
    (OUT / "m5_sheets_meta.json").write_text(json.dumps({
        "seed": a.seed, "sheet_a": "random60 (seed 20260725) + 13 controls, shuffled",
        "sheet_b": "m2_disagreements.csv with ±6-token context, candidates A/B/C system-blind",
        "private_key_location": "outside the repository; published with the results",
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
