"""LSJ-Gold medical-vocabulary gap package: Hippocrates (tlg0627) and Galen (tlg0057) loci where a neural lemmatizer misses the LSJ headword.

Reads data/qc/lsjgold/lsj_gold_scored.csv, the Galen punch list and real_headwords_no_perseus_lsj.csv; writes data/qc/lsjgold/medical_gap/.
Report only: nothing here patches anyone's model. No glosses or definitions are written; every number comes from a file.
The pattern classifier is imported from failure_catalogue.py (not reimplemented).
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from failure_catalogue import CLASSES, classify, md_table  # noqa: E402
from lsjgold_names import GDM, author_name  # noqa: E402
import relocate  # noqa: E402

QC = GDM / "data" / "qc" / "lsjgold"
SRC = QC / "lsj_gold_scored.csv"
OUT = QC / "medical_gap"
PUNCH = GDM / "outputs" / "phase3" / "punch_list_v3.csv"
REAL = GDM / "outputs" / "phase3" / "real_headwords_no_perseus_lsj.csv"
AUTHORS = {"tlg0627", "tlg0057"}
NEURAL = ["odycy", "stanza_perseus", "stanza_proiel", "stoicheia"]
WIDTH = 8


def scored(r: dict, s: str) -> bool:
    return bool(r[f"{s}_lemma"]) and r[f"{s}_blind"] != ""


def missed(r: dict, s: str) -> bool:
    return scored(r, s) and float(r[f"{s}_blind"]) == 0


def read(p: Path) -> list[dict]:
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    allrows = read(SRC)
    sub = [r for r in allrows if r["author"] in AUTHORS]
    print(f"{len(allrows)} rows read; {len(sub)} Hippocrates/Galen rows")

    # whole-subset score per system (denominators for the README)
    sub_scored = {s: sum(scored(r, s) for r in sub) for s in NEURAL + ["dilemma"]}
    sub_miss = {s: sum(missed(r, s) for r in sub) for s in NEURAL + ["dilemma"]}

    loci = []
    for r in sub:
        nm = [s for s in NEURAL if missed(r, s)]
        if nm:
            loci.append((r, nm))

    # ---- 1. loci
    hdr = ["headword", "surface", "author", "author_name", "work", "locator", "unit", "token_index", "validation", "cites_tier"]
    for s in NEURAL:
        hdr += [f"{s}_lemma", f"{s}_blind"]
    hdr += ["dilemma_lemma", "dilemma_blind", "n_neural_miss", "neural_systems_missing", "pattern_class"]
    pat_of = {}
    with open(OUT / "medical_gap_loci.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        for i, (r, nm) in enumerate(loci):
            # class is per the catalogue's rule on the first missing system's lemma (order odycy, stanza_perseus, stanza_proiel, stoicheia)
            cls = classify(r["headword"], r[f"{nm[0]}_lemma"], r["surface"])
            pat_of[i] = cls
            row = [r["headword"], r["surface"], r["author"], author_name(r["author"]), r["work"], r["locator"], r["unit"], r["token_index"], r["validation"], r["cites_tier"]]
            for s in NEURAL:
                row += [r[f"{s}_lemma"], r[f"{s}_blind"]]
            row += [r["dilemma_lemma"], r["dilemma_blind"], len(nm), "|".join(nm), cls]
            w.writerow(row)
    print(f"loci: {len(loci)}")

    # ---- 2. headwords
    punch = {}
    for r in read(PUNCH):
        punch.setdefault(r["lemma"], r["tier_v3"])
    real = {r["lemma"] for r in read(REAL)}
    per = defaultdict(lambda: {"n": 0, "dil": 0, "dil_scored": 0, "miss": Counter(), "lem": {s: Counter() for s in NEURAL}, "tot": 0})
    for r, nm in loci:
        h = per[r["headword"]]
        h["n"] += 1
        h["tot"] += len(nm)
        for s in nm:
            h["miss"][s] += 1
        for s in NEURAL:
            if scored(r, s):
                h["lem"][s][r[f"{s}_lemma"]] += 1
        if r["dilemma_blind"] != "":
            h["dil_scored"] += 1
            h["dil"] += float(r["dilemma_blind"]) == 1
    hw_rows = []
    for k, h in per.items():
        top = lambda s: "; ".join(f"{l} ({n})" for l, n in h["lem"][s].most_common(3))
        dil = "yes" if h["dil_scored"] and h["dil"] == h["n"] else ("partial" if h["dil"] else "no")
        hw_rows.append([k, h["n"], *[h["miss"][s] for s in NEURAL], h["tot"], *[top(s) for s in NEURAL], dil, f"{h['dil']}/{h['n']}",
                        "yes" if k in punch else "no", punch.get(k, ""), "yes" if k in real else "no"])
    hw_rows.sort(key=lambda x: (-x[6], -x[1], x[0]))
    with open(OUT / "medical_gap_headwords.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["headword", "n_loci", *[f"n_missed_{s}" for s in NEURAL], "total_neural_misses", *[f"top3_lemmas_{s}" for s in NEURAL],
                    "dilemma_gets_it", "dilemma_agree_loci", "in_galen_punch_list", "punch_list_tier_v3", "in_real_headwords_no_perseus_lsj"])
        w.writerows(hw_rows)
    print(f"headwords: {len(hw_rows)}")

    # ---- 3. training candidates (Dilemma agrees with LSJ)
    held = relocate.held_works()
    cache: dict = {}

    def toks(a: str, wk: str) -> list[str]:
        key = (a, wk)
        if key not in cache:
            p = held[key][1]
            cache[key] = [json.loads(l)["surface"] for l in p.open(encoding="utf-8")]
        return cache[key]

    n_cand = 0
    seen_keys = Counter()
    with open(OUT / "medical_gap_train_candidates.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r, nm in loci:
            if r["dilemma_blind"] == "" or float(r["dilemma_blind"]) != 1:
                continue
            t = toks(r["author"], r["work"])
            i = int(r["token_index"])
            assert t[i] == r["surface"], (r["author"], r["work"], i, t[i], r["surface"])
            ctx = {"left": t[max(0, i - WIDTH):i], "right": t[i + 1:i + 1 + WIDTH]}
            rec = {"surface": r["surface"], "headword": r["headword"], "context": ctx, "author": author_name(r["author"]), "work": r["work"],
                   "locator": r["locator"], "systems_missing": nm}
            seen_keys[(r["author"], r["work"], i, r["headword"])] += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_cand += 1
    dup = sum(v - 1 for v in seen_keys.values() if v > 1)
    print(f"train candidates: {n_cand} (duplicate token+headword lines: {dup})")

    # ---- 4. README
    gs = json.load(open(QC / "lsj_gold_scores.json", encoding="utf-8"))
    vs = json.load(open(QC / "validation_v03" / "validation_summary.json", encoding="utf-8"))
    rate_rows = []
    for s in NEURAL + ["dilemma"]:
        n, m = sub_scored[s], sub_miss[s]
        wb = gs["systems"][s]["match_blind"]
        rate_rows.append([s, n, m, f"{100 * m / n:.2f}" if n else "", wb["n"], wb["n"] - wb["k"], f"{100 - wb['pct']:.2f}"])
    cls_cnt = Counter(pat_of.values())
    cls_rows = [[c, cls_cnt.get(c, 0), f"{100 * cls_cnt.get(c, 0) / len(loci):.2f}"] for c in CLASSES]
    top30 = [[i + 1, r[0], r[1], r[6], r[2], r[3], r[4], r[5], r[11], r[12], r[14], r[15]] for i, r in enumerate(hw_rows[:30])]
    by_auth = Counter(r["author"] for r, _ in loci)
    nmiss_dist = Counter(len(nm) for _, nm in loci)
    r1, r2 = vs["readers"]["reader1_opus-5-5"], vs["readers"]["reader2_sonnet-5-5"]
    in_punch = sum(r[13] == "yes" for r in hw_rows)
    in_real = sum(r[15] == "yes" for r in hw_rows)
    dil_yes = sum(r[11] == "yes" for r in hw_rows)
    readme = f"""# Medical-vocabulary gap package (LSJ-Gold, Hippocrates and Galen)

Generated by `pipeline/lsjgold/medical_gap.py`. Source: `data/qc/lsjgold/lsj_gold_scored.csv` ({len(allrows)} rows; {len(sub)} are Hippocrates tlg0627 or Galen tlg0057). Report only: nothing here patches anyone's model, and no glosses or definitions are written by a model.

## Counts

- Subset rows (Hippocrates {sum(r['author']=='tlg0627' for r in sub)}, Galen {sum(r['author']=='tlg0057' for r in sub)}): {len(sub)}.
- Loci where at least one neural system (odycy, stanza_perseus, stanza_proiel, stoicheia) produced a lemma and missed (blind == 0): **{len(loci)}** (Hippocrates {by_auth['tlg0627']}, Galen {by_auth['tlg0057']}). File: `medical_gap_loci.csv`.
- Distinct headwords among them: **{len(hw_rows)}**. File: `medical_gap_headwords.csv`. Headwords where Dilemma agrees with LSJ at every one of their loci: {dil_yes}. In the Galen punch list: {in_punch}. In `real_headwords_no_perseus_lsj.csv`: {in_real}.
- Training candidates (Dilemma blind == 1 at the locus): **{n_cand}** lines in `medical_gap_train_candidates.jsonl` ({dup} of them repeat a token+headword pair already present, because the scored file keeps one row per quoted LSJ form).
- Loci by number of neural systems missing: {', '.join(f'{k} system(s): {v}' for k, v in sorted(nmiss_dist.items()))}.

## Miss rates: this subset vs whole benchmark

Miss = scored row with `<sys>_blind == 0`. Whole-benchmark figures come from `lsj_gold_scores.json` (`match_blind`, miss = n - k).

{md_table(['system', 'subset scored', 'subset misses', 'subset miss %', 'benchmark scored', 'benchmark misses', 'benchmark miss %'], rate_rows)}

## Pattern classes (medical subset)

Classes are the failure catalogue's string rules (`failure_catalogue.classify`, imported, order: {', '.join(CLASSES)}; see `failures/README.md`). One class per locus, computed on the first missing system's lemma in the order odycy, stanza_perseus, stanza_proiel, stoicheia. These are string rules, not linguistic judgements; `other` does not mean unexplained.

{md_table(['class', 'loci', 'share %'], cls_rows)}

## Top 30 headwords by total neural misses

Columns: loci, total neural misses, then misses per system, whether Dilemma agrees at all its loci, punch-list tier (v3), and presence in the real-headwords-without-Perseus-LSJ list.

{md_table(['#', 'headword', 'loci', 'total neural misses', 'odycy', 'stanza_perseus', 'stanza_proiel', 'stoicheia', 'Dilemma gets it', 'in punch list', 'tier_v3', 'in real-no-LSJ list'], [[a, b, c, d, e, f, g, h, i, j, k, l] for a, b, c, d, e, f, g, h, i, j, k, l in top30])}

## The honest frame

- This is the LSJ-cited stratum: loci exist only where LSJ cites Hippocrates or Galen under a headword and the citation could be relocated in the token stream. It says nothing about words LSJ does not cite. Galen contributes only {by_auth['tlg0057']} loci here (LSJ cites little of him).
- Dilemma's agreement is a lexicon's, not a human's: `dilemma_blind == 1` means Dilemma's lemma equals the LSJ headword, accent-blind. Both can be wrong about the token. The training candidates are therefore candidates.
- Relocation was validated blind on a random sample of 60 loci (whole benchmark, not this subset) by two readers (`validation_v03/validation_summary.json`): reader 1 {r1['random']['yes']['k']}/60 yes ({r1['relocation_precision_excl_unsure']['pct']}%, Wilson 95% {r1['relocation_precision_excl_unsure']['wilson95'][0]}-{r1['relocation_precision_excl_unsure']['wilson95'][1]}), reader 2 {r2['random']['yes']['k']}/60 yes ({r2['relocation_precision_excl_unsure']['pct']}%, {r2['relocation_precision_excl_unsure']['wilson95'][0]}-{r2['relocation_precision_excl_unsure']['wilson95'][1]}); both passed their anchor/plant gates; kappa {vs['between_readers']['kappa']}. The sample was not stratified by author, so it is not a medical-subset precision.

## Licence

Data: CC BY 4.0. Underlying texts: CC BY-SA (First1K / Perseus editions). Cite the benchmark and keep the share-alike on any redistribution of the text contexts.

## For maintainers

`medical_gap_loci.csv` lists every Hippocrates and Galen locus where one of four neural lemmatizers disagrees with LSJ, with each system's lemma. `medical_gap_headwords.csv` aggregates it per headword. `medical_gap_train_candidates.jsonl` is the subset where Dilemma also agrees with LSJ, shaped as surface + gold headword + {WIDTH} tokens of context either side + provenance, in case you want training or test material. These files are a report: not a patch, not a gold standard certified by a human, not a claim that LSJ is right where a system differs (a system may be right and the LSJ headword a variant or alternative lemmatisation), and not covering words LSJ does not cite. Use them to test, to find your own errors, or to ignore. Nothing here was sent to anyone.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print("top 10:")
    for r in hw_rows[:10]:
        print(r[0], r[1], r[6], r[11])
    # checks
    assert sum(cls_cnt.values()) == len(loci)
    assert sum(r[1] for r in hw_rows) == len(loci)
    assert sum(r[6] for r in hw_rows) == sum(len(nm) for _, nm in loci)
    for s in NEURAL:
        assert sum(r[2 + NEURAL.index(s)] for r in hw_rows) == sub_miss[s]
    print("checks ok", sub_scored, sub_miss)


if __name__ == "__main__":
    main()
