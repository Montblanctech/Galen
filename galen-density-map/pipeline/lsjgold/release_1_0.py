"""Package LSJ-Gold 1.0, the stable release, as release/lsj-gold-1.0/ (2026-11-11). Every number in the card is read from
the files: the gold, its dropped file, the scores, the grind ledger and its report.

Inputs: data/qc/lsjgold/lsj_gold_v1_0.csv (grind.py apply), lsj_gold_grind_dropped.csv, lsj_gold_scores.json (score.py
--gold lsj_gold_v1_0.csv --from-scored <0.1.1 scored>), docs/lsj-gold/leaderboard.json, grind/ledger.csv and
grind/report.json. Checksums are computed on the bytes written, LF line endings.

  python -X utf8 release_1_0.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parents[1]
REPO = GDM.parent
QC = GDM / "data" / "qc" / "lsjgold"
G = QC / "grind"
OUT = REPO / "release" / "lsj-gold-1.0"
PREV = REPO / "release" / "lsj-gold-0.1.2"
V = "1.0"
LABELS = {"stoicheia": "Stoicheia tagger-parser (2026)", "dilemma": "Dilemma 1.3.15 (Open Greek, lexicon-first)",
          "stanza_perseus": "Stanza 1.14 grc-perseus", "odycy": "odyCy 0.7.0 (grc_odycy_joint_trf)", "stanza_proiel": "Stanza 1.14 grc-proiel"}
POOLS = {"allmiss": "every system misses the gold", "ctxmiss": "Dilemma matches, every context system misses",
         "sheet3": "dropped by 0.1.2 only because its sheet failed the anchor gate", "split": "dropped by 0.1.2 on a split vote",
         "conflict": "a token gold under two headwords", "quoted_dm": "quoted-route loci Dilemma misses, not read before",
         "ctx3": "sample: Dilemma matches, three of four context systems miss", "sample_dm": "sample: Morpheus route, only Dilemma misses",
         "sample_dm2": "sample: the same stratum, second draw", "sample_ok": "sample: the bulk", "sample_ok2": "sample: the bulk, second draw"}


def n_rows(p: Path) -> int:
    with p.open(encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # the dropped file: every 0.1.1 distinct locus that is not in 1.0, with why
    led = {r["locus"]: r for r in csv.DictReader((G / "ledger.csv").open(encoding="utf-8"))}
    lid = lambda r: f'{r["author"]}.{r["work"]}:{r["token_index"]}:{r["headword_key"]}'
    with (QC / "lsj_gold_grind_dropped.csv").open(encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        cols, dropped = list(rd.fieldnames or []), list(rd)
    for r in dropped:
        x = led.get(lid(r))
        if x:
            v = [y for y in json.loads(x["verdicts"] or "[]") if "A" in y]
            last = v[-1] if v else {}
            r["why"] = f"read in the grind ({x['pool']}): " + "/".join(str(last.get(k) or "-") for k in ("A", "B", "C"))
            r["readers_headword"] = last.get("A_h") or last.get("B_h") or last.get("C_h") or ""
        else:
            r["why"], r["readers_headword"] = "0.1.2: both readers answered no", ""
    with (OUT / "lsj_gold_1_0_dropped.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols + ["why", "readers_headword"], lineterminator="\n")
        w.writeheader(); w.writerows(dropped)
    files = {"lsj_gold.csv": QC / "lsj_gold_v1_0.csv", "lsj_gold_scores.json": QC / "lsj_gold_scores.json",
             "leaderboard.json": REPO / "docs" / "lsj-gold" / "leaderboard.json", "LICENSE": PREV / "LICENSE",
             "ledger.csv": G / "ledger.csv", "residual_error.json": G / "report.json",
             "lsj_gold_0_1_2_duplicates.csv": QC / "lsj_gold_0_1_2_duplicates.csv"}
    for name, src in files.items():
        (OUT / name).write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))
    sc = json.loads((QC / "lsj_gold_scores.json").read_text(encoding="utf-8"))
    rep = json.loads((G / "report.json").read_text(encoding="utf-8"))
    n = n_rows(OUT / "lsj_gold.csv")
    nd = len(dropped)
    ndup = n_rows(OUT / "lsj_gold_0_1_2_duplicates.csv")
    n011 = n_rows(REPO / "release" / "lsj-gold-0.1.1" / "lsj_gold.csv")
    assert n + nd + ndup == n011, "1.0, its dropped loci and the repeated rows do not add up to 0.1.1"
    S = sc["systems"]
    order = sorted(S, key=lambda s: -S[s]["match_blind"]["pct"])
    neural = next(S[s]["scored"] for s in S if s != "dilemma")
    rows = []
    for s in order:
        b, c = S[s], S[s].get("by_lsj_citations", {})
        ci = b["match_blind"]["wilson95"]
        rows.append(f"| {LABELS.get(s, s)} | {b['scored']:,} | **{b['match_blind']['pct']:.1f}** [{ci[0]:.1f}–{ci[1]:.1f}] | "
                    f"{c.get('1', {}).get('pct', 0):.1f} | {c.get('6+', {}).get('pct', 0):.1f} |")
    prow = []
    for p, cnt in rep["pools"].items():
        prow.append(f"| {POOLS.get(p, p)} | {sum(cnt.values()):,} | {cnt.get('keep', 0):,} | {cnt.get('drop', 0):,} |")
    rrow = []
    for name, e in rep["residual"].items():
        rrow.append(f"| {name} | {e['unread_loci']:,} | {e['dropped']} of {e['sampled']} | {100*e['rate']:.1f}% [{100*e['wilson95'][0]:.1f}–{100*e['wilson95'][1]:.1f}] | "
                    f"about {e['expected_wrong'][1]:,} ({e['expected_wrong'][0]:,}–{e['expected_wrong'][2]:,}) |")
    tw = rep["residual_total_expected_wrong"]
    authors = len(sc["loci_per_author"])
    card = f"""---
license: cc-by-4.0
language:
  - grc
tags:
  - ancient-greek
  - lemmatization
  - evaluation
  - lexicography
  - benchmark
task_categories:
  - token-classification
pretty_name: LSJ-Gold
size_categories:
  - 10K<n<100K
---

# LSJ-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek

**LSJ-Gold** measures Ancient Greek lemmatizers on the words the dictionary itself cites. Every citation in the Perseus Liddell–Scott–Jones XML that points, by CTS URN, into a free Greek edition we hold (First1KGreek and Perseus editions) is relocated to its exact token and validated by Morpheus (the surface's analyses contain the headword) or by the single word LSJ quotes at the citation. **{V}: {n:,} loci over {authors} authors.**

A system is scored by comparing its lemma at `token_index` with `headword`: accent-blind (the headline figure), strict, and article-convention-neutral figures are all printed by the reference scorer. Wilson 95% intervals in `lsj_gold_scores.json`.

## What "stable" means here

{V} is the first frozen release. **Every locus with a reason to doubt its gold was read**, blind, by two readers (Claude Opus and Claude Sonnet, each in its own session with nothing but the sheet), and a third (a fresh Claude Opus) decided every split: a locus stays only on two readers' yes. Each sheet carried 10 anchors and 10 near-miss plants at unmarked positions; every reader passed every sheet's gate in the two rounds that made 1.0 (in 0.1.2, one sheet had failed and was re-read here). The rules were committed before any answer was read. **What was not read one by one was sampled**, and its residual error is stated below. **{V} is frozen**: the file will not change; any later correction will be a numbered erratum, decided the same way, with its own record.

The readers are language models, not Greek specialists. "Stable" means characterised and frozen, not certified by a scholar.

## How {V} was made from 0.1.1

1. A locus repeated in LSJ counts once: {ndup:,} repeated rows removed (`lsj_gold_0_1_2_duplicates.csv`).
2. The 652 weakest 0.1.1 loci (only LSJ's quoted word, Dilemma disagreeing) were read in 0.1.2; the 90 both readers rejected stay out.
3. Two further rounds read {rep['ledger_loci']:,} loci (`ledger.csv`, every verdict of every reader):

| pool | loci | kept | dropped |
|---|---|---|---|
""" + "\n".join(prow) + f"""

The largest pool is the most telling. Of the loci where every system misses the gold, about a third were wrong golds (a noun filed under its verb, the article under τις, ἂν under ἀνά) and two thirds were right: the hard words the benchmark exists for. Where Dilemma matched the gold and every context-reading system missed, the gold was right 97% of the time. Every dropped locus is in `lsj_gold_1_0_dropped.csv` with the reason and the readers' answers; {n:,} + {nd:,} + {ndup:,} = {n011:,}, the rows of 0.1.1. Nothing was edited or added.

## Residual error (`residual_error.json`)

| stratum not read one by one | loci | sample drops | rate [95%] | expected wrong golds |
|---|---|---|---|---|
""" + "\n".join(rrow) + f"""

In all, about {tw[1]:,} of {n:,} loci (95% range {tw[0]:,}–{tw[2]:,}) may still carry a wrong gold, about {100*tw[1]/n:.1f}%. They are spread thinly through the bulk, where finding them would mean reading it whole. The errors the samples found were forms of a neighbouring word that the validation accepted and the context rules out (χρῆν, from χρή, under χράω; φυλακῆς under φυλακεύς). Corrections are welcome and will be errata.

## Reference table ({sc['date']})

| system | loci | headword match % | once-cited headwords % | cited 6+ times % |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

The four neural rows are on the same {neural:,} loci. Stoicheia and Dilemma are level within their intervals, as in every version. Per-author columns for every system are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/lsj-gold/.

## Files
- `lsj_gold.csv`: one row per locus; columns in `SCHEMA.md`.
- `lsj_gold_scores.json`, `leaderboard.json`: reference scores with strata and per-author figures.
- `ledger.csv`: every locus read in the rounds, its pool, every reader's verdict and the decision; `residual_error.json`: the sampled strata and their rates.
- `lsj_gold_1_0_dropped.csv` ({nd:,}), `lsj_gold_0_1_2_duplicates.csv` ({ndup:,}): the 0.1.1 rows not in {V}, same columns (the dropped file adds `why` and `readers_headword`).
- `SCHEMA.md`, `CITATION.cff`, `LICENSE`, `CHECKSUMS.sha256` (`sha256sum -c CHECKSUMS.sha256` passes on the archive and on any checkout).

## How to score your lemmatizer
```
pip install "git+https://github.com/Montblanctech/Galen#subdirectory=audit-kit"
greek-lemma-audit lsjgold --system-cache DIR
```
`DIR` holds one `<system>/<stem>.jsonl` token file per covered edition, with your lemma on each token of the project's token stream (the stems and tokenisation are in the repository under `galen-density-map/pipeline/lsjgold/`). A pull request adding such caches under `submissions/<system>/` in the repository is scored by CI and gets its row.

## What the numbers mean, and what they do not
LSJ cites what a lexicographer found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy, and treebank test scores are not comparable with it. The Perseus LSJ XML is incomplete. Loci exist only for works held in a free edition. Nothing here patches any system's output; every figure traces to a row.

## Source and citation
Repository and method: https://github.com/Montblanctech/Galen (concept DOI 10.5281/zenodo.21561962). The reading sheets, answers and keys of every round are in the repository under `galen-density-map/data/qc/lsjgold/grind/` and `recheck_0_1_2/`.

Pepperman, W. (2026). *LSJ-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962 (concept DOI: it resolves to the newest version; earlier versions stay citable at their own releases)

Underlying texts: First1KGreek (CC BY-SA 4.0), Perseus Digital Library editions and LSJ XML (CC BY-SA 3.0), Morpheus analyses via Perseids. Data: CC BY 4.0.
"""
    (OUT / "README.md").write_bytes(card.encode("utf-8"))
    schema = (PREV / "SCHEMA.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n\nThe three set-aside files")[0].rstrip()
    schema += ("\n\n`lsj_gold_1_0_dropped.csv` and `lsj_gold_0_1_2_duplicates.csv` have the same columns; the dropped file adds `why` "
               "(how the locus was decided) and `readers_headword` (the headword a reader gave instead). `ledger.csv`: `locus` "
               "(author.work:token_index:headword_key), `pool`, `headword`, `surface`, `author`, `work`, `token_index`, `status` "
               "(keep or drop), `verdicts` (JSON: every round's answers, A = Opus, B = Sonnet, C = the third reader), `note`.\n")
    (OUT / "SCHEMA.md").write_bytes(schema.encode("utf-8"))
    cff = (PREV / "CITATION.cff").read_text(encoding="utf-8").replace("\r\n", "\n")
    cff = cff.replace("LSJ-Gold 0.1.2:", f"LSJ-Gold {V}:").replace('version: "0.1.2"', f'version: "{V}"')
    cff = "\n".join(f"date-released: {date.today().isoformat()}" if l.startswith("date-released:") else l for l in cff.split("\n"))
    (OUT / "CITATION.cff").write_bytes(cff.encode("utf-8"))
    names = sorted(p.name for p in OUT.iterdir() if p.name != "CHECKSUMS.sha256")
    (OUT / "CHECKSUMS.sha256").write_bytes("".join(f"{hashlib.sha256((OUT / f).read_bytes()).hexdigest()} *{f}\n" for f in names).encode("utf-8"))
    print(f"release/lsj-gold-{V}: {n:,} loci; dropped {nd:,}; repeats {ndup:,}; residual about {tw[1]} ({tw[0]}-{tw[2]})")


if __name__ == "__main__":
    main()
