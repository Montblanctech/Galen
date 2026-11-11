"""LSJ-Gold 0.1.2: every weak locus of 0.1.1 read blind by two readers (2026-11-11).

The weak loci are the 651 LSJ-Gold 0.1.1 loci that rest only on the single word LSJ quotes at the citation, where that
(form, headword) pair is one the lexicon 0.1.2 set aside because Dilemma gives the form another lemma
(release/lsj-gold-lexicon-0.1.2/review_pairs.tsv), plus the one Morpheus-validated locus of the pair found wrong by
reading (πόλεων under πολύς). A sample read found about one in seven such pairs wrong: LSJ quotes a related or
cross-referenced word in an entry and that word passed as the headword's own form.

Protocol (fixed before any answer is read; the M5 convention of validation_sheet.py):
  - The loci are shuffled (seed 20261111) into 4 sheets. Each sheet adds 10 anchors (certain loci: Morpheus-validated,
    the surface equal to LSJ's quoted form) and 10 plants (a certain locus shown with a wrong headword that shares at
    least its first three letters, else its first letter: the kind of near miss the weak loci contain), shuffled in
    at unmarked positions. The key stays outside the repository until scoring.
  - Each sheet is read by two readers, each in its own session with nothing but the sheet and the instructions:
    reader A Claude Opus, reader B Claude Sonnet. No system output, no dictionary file, no web.
  - Gate, per sheet and reader: at least 9 of 10 anchors yes and 8 of 10 plants no. A reader who fails is replaced
    once by a fresh reader of the same model; a sheet that fails twice has all its loci dropped.
  - A locus is kept only if both readers answer yes. Any no or unsure drops it (to lsj_gold_0_1_2_dropped.csv, with
    both answers). Kept rows are the 0.1.1 rows, unedited, in the same order; nothing is repaired or added.
  - After scoring, the build session reads a seeded sample of kept and dropped loci and reports what it finds.

  python -X utf8 recheck_0_1_2.py sheet --key-out <file outside the repo>
  python -X utf8 recheck_0_1_2.py score --key <that file>        (after the answers_*.csv files are in place)
  python -X utf8 recheck_0_1_2.py apply                          (writes lsj_gold_v0_1_2.csv and the dropped file)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import unicodedata as ud
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
REPO = GDM.parent
QC = GDM / "data" / "qc" / "lsjgold"
OUT = QC / "recheck_0_1_2"
GOLD = QC / "lsj_gold_v0_1_1.csv"
REVIEW = REPO / "release" / "lsj-gold-lexicon-0.1.2" / "review_pairs.tsv"
SEED, N_SHEETS, N_ANCHOR, N_PLANT, WIDTH = 20261111, 4, 10, 10, 12
READERS = {"A": "opus", "B": "sonnet"}
GATE = {"anchors_min_yes": 9, "plants_min_no": 8}

INSTRUCTIONS = """LSJ-GOLD 0.1.2 READING SHEET

Each row shows a headword from the Liddell-Scott-Jones lexicon (LSJ) and a Greek token in [brackets] inside its context
(the edition's text as a token stream, punctuation removed). Decide whether the bracketed token is a form of that
headword.

Answer is_instance:
  yes     the token is a form of the headword: any inflection, dialect form, accent or breathing variant, elided or
          crasis form. Count as yes what LSJ itself files under the headword: an adverb under its adjective (σαφῶς
          under σαφής), a comparative or superlative under its positive, a participle under its verb.
  no      the token is a different word: a compound or simple form of it, a derivative (a noun under its verb, a
          verb under its noun), a proper name under a common noun or the reverse, or an unrelated word.
  unsure  the context does not let you decide.
If no, give the headword the token really belongs to.

Use only this sheet and your own knowledge of Greek: no lemmatizer, no dictionary file, no web search, no other file.
Answer every row. Some rows are controls placed at unmarked positions.

Write your answers as CSV with exactly these columns: row_id,is_instance,right_headword_if_no,note
"""


def nfc(s: str) -> str:
    return ud.normalize("NFC", (s or "").replace("^", "").replace("_", ""))


def base(s: str) -> str:
    return "".join(c for c in ud.normalize("NFD", (s or "").lower()) if not ud.combining(c)).replace("ς", "σ").replace("^", "").replace("_", "")


def weak_rows(gold: list[dict]) -> list[dict]:
    rev = {(r["form"], r["lemma"]) for r in csv.DictReader(REVIEW.open(encoding="utf-8"), delimiter="\t")}
    return [r for r in gold if (nfc(r["surface"]), nfc(r["headword"])) in rev]


def locus_id(r: dict) -> str:
    return f'{r["author"]}.{r["work"]}:{r["token_index"]}:{r["headword_key"]}'


def locus_id_of(d: dict) -> str:
    return d["locus"]


def sheet(key_out: Path) -> None:
    sys.path.insert(0, str(HERE))
    from relocate import held_works
    hw = held_works()
    streams: dict = {}

    def context(r: dict) -> str:
        x, j = hw[(r["author"], r["work"])]
        if j not in streams:
            streams[j] = [json.loads(l)["surface"] for l in j.open(encoding="utf-8")]
        toks, i = streams[j], int(r["token_index"])
        if toks[i] != r["surface"]:
            raise SystemExit(f"token stream mismatch at {locus_id(r)}: {toks[i]} != {r['surface']}")
        lo, hi = max(0, i - WIDTH), min(len(toks), i + WIDTH + 1)
        return " ".join(f"[{toks[k]}]" if k == i else toks[k] for k in range(lo, hi))

    rng = random.Random(SEED)
    gold = list(csv.DictReader(GOLD.open(encoding="utf-8")))
    weak = weak_rows(gold)
    weak_ids = {locus_id(r) for r in weak}
    rng.shuffle(weak)
    certain = [g for g in gold if g["validation"] == "morpheus" and g["quoted_form"].strip() == g["surface"].strip()
               and locus_id(g) not in weak_ids and (g["author"], g["work"]) in hw]
    heads = sorted({(g["headword"], g["headword_key"]) for g in gold})
    used: set = set()
    OUT.mkdir(parents=True, exist_ok=True)
    keys = []
    for s in range(N_SHEETS):
        part = weak[s::N_SHEETS]
        rows = [("weak", r, r["headword"]) for r in part]
        pool = [g for g in certain if locus_id(g) not in used]
        for g in rng.sample(pool, N_ANCHOR):
            used.add(locus_id(g)); rows.append(("anchor", g, g["headword"]))
        pool = [g for g in certain if locus_id(g) not in used]
        for g in rng.sample(pool, N_PLANT):
            used.add(locus_id(g))
            b = base(g["headword"])
            near = [h for h, k in heads if k != g["headword_key"] and base(h)[:3] == b[:3] and base(h) != b]
            far = [h for h, k in heads if k != g["headword_key"] and base(h)[:1] == b[:1] and base(h) != b]
            rows.append(("plant", g, rng.choice(near or far)))
        rng.shuffle(rows)
        with (OUT / f"sheet_{s + 1}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_id", "headword_shown", "surface", "context", "author"])
            for n, (kind, r, shown) in enumerate(rows, 1):
                rid = f"S{s + 1}-{n:03d}"
                w.writerow([rid, shown, r["surface"], context(r), r["author"]])
                keys.append({"row_id": rid, "sheet": s + 1, "kind": kind, "shown_headword": shown, "locus": locus_id(r),
                             "headword": r["headword"], "surface": r["surface"]})
    (OUT / "reader_instructions.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    with key_out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(keys[0]))
        w.writeheader(); w.writerows(keys)
    meta = {"date": "2026-11-11", "seed": SEED, "weak_loci": len(weak), "sheets": N_SHEETS, "anchors_per_sheet": N_ANCHOR,
            "plants_per_sheet": N_PLANT, "context_tokens_each_side": WIDTH, "readers": READERS, "gate": GATE,
            "rule": "keep only if both readers answer yes; any no or unsure drops the locus", "key": "PRIVATE until scored"}
    (OUT / "protocol.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))


def read_answers(p: Path) -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(p.open(encoding="utf-8-sig")):
        out[r["row_id"].strip()] = {"a": (r.get("is_instance") or "").strip().lower(), "right": (r.get("right_headword_if_no") or "").strip(),
                                    "note": (r.get("note") or "").strip()}
    return out


def score(key_path: Path) -> None:
    key = list(csv.DictReader(key_path.open(encoding="utf-8")))
    by_sheet: dict[int, list] = {}
    for k in key:
        by_sheet.setdefault(int(k["sheet"]), []).append(k)
    gates, decisions = {}, []
    for s, ks in sorted(by_sheet.items()):
        ans, ok = {}, True
        for rd in READERS:
            # a reader who fails the gate is replaced once by a fresh reader of the same model (answers_<s>_<rd>_r2.csv)
            for attempt, suffix in ((1, ""), (2, "_r2")):
                p = OUT / f"answers_{s}_{rd}{suffix}.csv"
                if not p.exists():
                    if attempt == 1:
                        raise SystemExit(f"missing {p.name}")
                    break
                a = read_answers(p)
                miss = [k["row_id"] for k in ks if k["row_id"] not in a]
                anc = sum(a.get(k["row_id"], {}).get("a") == "yes" for k in ks if k["kind"] == "anchor")
                pla = sum(a.get(k["row_id"], {}).get("a") == "no" for k in ks if k["kind"] == "plant")
                passed = not miss and anc >= GATE["anchors_min_yes"] and pla >= GATE["plants_min_no"]
                last = f"{s}{rd}{suffix}"
                gates[last] = {"anchors_yes": anc, "plants_no": pla, "missing": len(miss), "pass": passed}
                ans[rd] = a
                if passed:
                    break
            ok &= gates[last]["pass"]
        for k in ks:
            if k["kind"] != "weak":
                continue
            A, B = ans["A"].get(k["row_id"], {}), ans["B"].get(k["row_id"], {})
            keep = ok and A.get("a") == "yes" and B.get("a") == "yes"
            decisions.append({"locus": k["locus"], "row_id": k["row_id"], "headword": k["headword"], "surface": k["surface"],
                              "reader_A": A.get("a", ""), "reader_A_headword": A.get("right", ""), "reader_A_note": A.get("note", ""),
                              "reader_B": B.get("a", ""), "reader_B_headword": B.get("right", ""), "reader_B_note": B.get("note", ""),
                              "sheet_gate": "pass" if ok else "fail", "decision": "keep" if keep else "drop"})
    with (OUT / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(decisions[0]))
        w.writeheader(); w.writerows(decisions)
    pair = Counter((d["reader_A"], d["reader_B"]) for d in decisions)
    summ = {"gates": gates, "weak_loci": len(decisions), "kept": sum(d["decision"] == "keep" for d in decisions),
            "dropped": sum(d["decision"] == "drop" for d in decisions), "answer_pairs_A_B": {f"{a}/{b}": n for (a, b), n in pair.most_common()}}
    (OUT / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    import shutil
    shutil.copy(key_path, OUT / "key_PUBLISHED_AFTER_SCORING.csv")
    print(json.dumps(summ, ensure_ascii=False, indent=1))


def apply() -> None:
    """0.1.2 = 0.1.1, one row per locus (the first of any repeats), minus the loci the re-check drops."""
    dec: dict[str, dict] = {}
    for d in csv.DictReader((OUT / "decisions.csv").open(encoding="utf-8")):
        # a locus listed twice in 0.1.1 can sit on two sheets: it is dropped if either copy is
        if locus_id_of(d) not in dec or d["decision"] == "drop":
            dec[locus_id_of(d)] = d
    with GOLD.open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        cols, gold = list(rd.fieldnames or []), list(rd)
    seen, first, dups = set(), [], []
    for g in gold:
        (dups if locus_id(g) in seen else first).append(g)
        seen.add(locus_id(g))
    with (QC / "lsj_gold_0_1_2_duplicates.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(dups)
    keep = [g for g in first if dec.get(locus_id(g), {}).get("decision") != "drop"]
    drop = [g for g in first if dec.get(locus_id(g), {}).get("decision") == "drop"]
    assert len(drop) == sum(d["decision"] == "drop" for d in dec.values()), "a decision did not match a gold row"
    # a token gold under two different headwords cannot be both: every row of such a token leaves, for review
    heads: dict = {}
    for g in keep:
        heads.setdefault((g["author"], g["work"], g["token_index"]), set()).add(g["headword_key"])
    clash = {k for k, v in heads.items() if len(v) > 1}
    conflicts = [g for g in keep if (g["author"], g["work"], g["token_index"]) in clash]
    keep = [g for g in keep if (g["author"], g["work"], g["token_index"]) not in clash]
    with (QC / "lsj_gold_0_1_2_conflicts.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(conflicts)
    print(f"tokens gold under two or more headwords: {len(clash)} ({len(conflicts)} rows) set aside")
    print(f"0.1.1 rows {len(gold)}; repeated loci removed {len(dups)}; distinct loci {len(first)}")
    with (QC / "lsj_gold_v0_1_2.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(keep)
    dcols = cols + ["reader_A", "reader_A_headword", "reader_B", "reader_B_headword"]
    with (QC / "lsj_gold_0_1_2_dropped.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=dcols, lineterminator="\n", extrasaction="ignore"); w.writeheader()
        for g in drop:
            d = dec[locus_id(g)]
            w.writerow({**g, **{k: d[k] for k in ("reader_A", "reader_A_headword", "reader_B", "reader_B_headword")}})
    print(f"0.1.2: {len(keep)} loci kept, {len(drop)} dropped by the re-check")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sheet", "score", "apply"])
    ap.add_argument("--key-out", type=Path)
    ap.add_argument("--key", type=Path)
    a = ap.parse_args()
    if a.cmd == "sheet":
        sheet(a.key_out)
    elif a.cmd == "score":
        score(a.key)
    else:
        apply()
