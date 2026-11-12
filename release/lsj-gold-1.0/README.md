---
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

# LSJ-Gold 1.0: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek

**LSJ-Gold** measures Ancient Greek lemmatizers on the words the dictionary itself cites. Every citation in the Perseus Liddell–Scott–Jones XML that points, by CTS URN, into a free Greek edition we hold (First1KGreek and Perseus editions) is relocated to its exact token and validated by Morpheus (the surface's analyses contain the headword) or by the single word LSJ quotes at the citation. **1.0: 70,033 loci over 54 authors.**

A system is scored by comparing its lemma at `token_index` with `headword`: accent-blind (the headline figure), strict, and article-convention-neutral figures are all printed by the reference scorer. Wilson 95% intervals in `lsj_gold_scores.json`.

## What "stable" means here

1.0 is the first frozen release. **Every locus with a reason to doubt its gold was read**, blind, by two readers (Claude Opus and Claude Sonnet, each in its own session with nothing but the sheet), and a third (a fresh Claude Opus) decided every split: a locus stays only on two readers' yes. Each sheet carried 10 anchors and 10 near-miss plants at unmarked positions; every reader passed every sheet's gate in the two rounds that made 1.0 (in 0.1.2, one sheet had failed and was re-read here). The rules were committed before any answer was read. **What was not read one by one was sampled**, and its residual error is stated below. **1.0 is frozen**: the file will not change; any later correction will be a numbered erratum, decided the same way, with its own record.

The readers are language models, not Greek specialists. "Stable" means characterised and frozen, not certified by a scholar.

## How 1.0 was made from 0.1.1

1. A locus repeated in LSJ counts once: 1,364 repeated rows removed (`lsj_gold_0_1_2_duplicates.csv`).
2. The 652 weakest 0.1.1 loci (only LSJ's quoted word, Dilemma disagreeing) were read in 0.1.2; the 90 both readers rejected stay out.
3. Two further rounds read 3,249 loci (`ledger.csv`, every verdict of every reader):

| pool | loci | kept | dropped |
|---|---|---|---|
| every system misses the gold | 894 | 591 | 303 |
| a token gold under two headwords | 99 | 42 | 57 |
| sample: Dilemma matches, three of four context systems miss | 200 | 198 | 2 |
| Dilemma matches, every context system misses | 1,031 | 1,001 | 30 |
| quoted-route loci Dilemma misses, not read before | 2 | 2 | 0 |
| sample: Morpheus route, only Dilemma misses | 200 | 195 | 5 |
| sample: the same stratum, second draw | 200 | 198 | 2 |
| sample: the bulk | 100 | 99 | 1 |
| sample: the bulk, second draw | 300 | 299 | 1 |
| dropped by 0.1.2 only because its sheet failed the anchor gate | 163 | 116 | 47 |
| dropped by 0.1.2 on a split vote | 60 | 21 | 39 |

The largest pool is the most telling. Of the loci where every system misses the gold, about a third were wrong golds (a noun filed under its verb, the article under τις, ἂν under ἀνά) and two thirds were right: the hard words the benchmark exists for. Where Dilemma matched the gold and every context-reading system missed, the gold was right 97% of the time. Every dropped locus is in `lsj_gold_1_0_dropped.csv` with the reason and the readers' answers; 70,033 + 577 + 1,364 = 71,974, the rows of 0.1.1. Nothing was edited or added.

## Residual error (`residual_error.json`)

| stratum not read one by one | loci | sample drops | rate [95%] | expected wrong golds |
|---|---|---|---|---|
| bulk (Dilemma and at least two context systems match) | 61,280 | 2 of 400 | 0.5% [0.1–1.8] | about 306 (84–1,106) |
| Morpheus-validated, only Dilemma misses | 3,794 | 7 of 400 | 1.8% [0.9–3.6] | about 66 (32–135) |
| Dilemma matches, three of four context systems miss | 2,481 | 2 of 200 | 1.0% [0.3–3.6] | about 25 (7–89) |

In all, about 398 of 70,033 loci (95% range 123–1,330) may still carry a wrong gold, about 0.6%. They are spread thinly through the bulk, where finding them would mean reading it whole. The errors the samples found were forms of a neighbouring word that the validation accepted and the context rules out (χρῆν, from χρή, under χράω; φυλακῆς under φυλακεύς). Corrections are welcome and will be errata.

## Reference table (2026-11-11)

| system | loci | headword match % | once-cited headwords % | cited 6+ times % |
|---|---|---|---|---|
| Stoicheia tagger-parser (2026) | 67,479 | **93.1** [92.9–93.3] | 79.0 | 94.2 |
| Dilemma 1.3.15 (Open Greek, lexicon-first) | 70,001 | **93.0** [92.8–93.2] | 92.9 | 93.1 |
| Stanza 1.14 grc-perseus | 67,479 | **85.1** [84.8–85.3] | 60.4 | 87.3 |
| odyCy 0.7.0 (grc_odycy_joint_trf) | 67,479 | **82.8** [82.5–83.1] | 60.2 | 84.5 |
| Stanza 1.14 grc-proiel | 67,479 | **79.9** [79.6–80.2] | 60.5 | 81.5 |

The four neural rows are on the same 67,479 loci. Stoicheia and Dilemma are level within their intervals, as in every version. Per-author columns for every system are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/lsj-gold/.

## Files
- `lsj_gold.csv`: one row per locus; columns in `SCHEMA.md`.
- `lsj_gold_scores.json`, `leaderboard.json`: reference scores with strata and per-author figures.
- `ledger.csv`: every locus read in the rounds, its pool, every reader's verdict and the decision; `residual_error.json`: the sampled strata and their rates.
- `lsj_gold_1_0_dropped.csv` (577), `lsj_gold_0_1_2_duplicates.csv` (1,364): the 0.1.1 rows not in 1.0, same columns (the dropped file adds `why` and `readers_headword`).
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

Pepperman, W. (2026). *LSJ-Gold 1.0: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962 (concept DOI: it resolves to the newest version; earlier versions stay citable at their own releases)

Underlying texts: First1KGreek (CC BY-SA 4.0), Perseus Digital Library editions and LSJ XML (CC BY-SA 3.0), Morpheus analyses via Perseids. Data: CC BY 4.0.
