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

# LSJ-Gold 0.1.1: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek

**LSJ-Gold** measures Ancient Greek lemmatizers on the words the dictionary itself cites. Every citation in the Perseus Liddell–Scott–Jones XML that points, by CTS URN, into a free Greek edition we hold (First1KGreek and 257 Perseus editions) is relocated to its exact token and validated by Morpheus (the surface's analyses contain the headword) or by the lexicon's own quoted form (LSJ quotes that single word beside the citation). **71,976 loci over 54 authors**, provenance on every row, relocation checked blind twice (60/60 on the first sheet; 57/60 and 56/60 with salted controls on the second).

A system is scored by comparing its lemma at `token_index` with `headword`: accent-blind (the headline figure), strict, and article-convention-neutral figures are all printed by the reference scorer. Wilson 95% intervals in `lsj_gold_scores.json`.

## Erratum: what changed from 0.1

In 0.1 a locus also counted as validated by LSJ's quoted form when the token matched any one word of a quoted *phrase*. So some golds were a neighbouring word, not the headword's own: the Iliad 9:130 token καὶ was gold κάμνω, because LSJ quotes "οἵ κέ σφιν καὶ νῆσον . . ἐκάμοντο" under κάμνω. 0.1.1 keeps a quoted locus only when LSJ quotes that single word. 21,950 of 0.1's 93,926 loci are dropped (listed in `lsj_gold_0_1_1_dropped.csv`); no kept row is edited. Every system is rescored on the same outputs as 0.1. All scores rise, and Stoicheia and Dilemma are now level within their intervals. Most dropped loci are probably right; a later version will re-validate them word by word. 0.1 stays available and citable at its DOI, 10.5281/zenodo.24046260.

## Reference table (2026-11-10)

| system | loci | headword match % | once-cited headwords % | cited 6+ times % |
|---|---|---|---|---|
| Stoicheia tagger-parser (2026) | 69,341 | **92.3** [92.1–92.5] | 75.9 | 93.6 |
| Dilemma 1.3.15 (Open Greek, lexicon-first) | 71,944 | **92.3** [92.1–92.5] | 89.0 | 92.6 |
| Stanza 1.14 grc-perseus | 69,341 | **84.3** [84.0–84.6] | 57.9 | 86.6 |
| odyCy 0.7.0 (grc_odycy_joint_trf) | 69,341 | **82.0** [81.8–82.3] | 57.8 | 83.9 |
| Stanza 1.14 grc-proiel | 69,341 | **79.1** [78.8–79.4] | 58.1 | 80.9 |

The four neural rows are on the same 69,341 loci. Stoicheia (92.34) and Dilemma (92.28) are a tie; on strict match Dilemma leads, 89.2 to 88.2. Per-author columns for every system are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/lsj-gold/.

## Files
- `lsj_gold.csv` (on Hugging Face as `lsj_gold.csv.gz`; the checksum in `CHECKSUMS.sha256` is for the uncompressed file) — one row per locus: `headword`, `headword_key` (accent-blind Beta Code), `author`, `work` (TLG ids), `cited_edition`, `locator` (CTS passage), `unit`, `token_index` (0-based, into the project's token JSONL for that edition), `surface`, `validation` (`morpheus` or `quoted`), `quoted_form`, `lsj_part`, `entry_key`, `status`. Columns are described in `SCHEMA.md`.
- `lsj_gold_scores.json` — the reference scores with strata (LSJ tier, validation route, citation frequency) and per-author figures.
- `leaderboard.json` — the table as the leaderboard page renders it.
- `lsj_gold_0_1_1_dropped.csv` — the 21,950 0.1 loci dropped in 0.1.1, same columns.
- `SCHEMA.md`, `CITATION.cff`, `LICENSE`, `CHECKSUMS.sha256`.

## How to score your lemmatizer
```
pip install "git+https://github.com/Montblanctech/Galen#subdirectory=audit-kit"
greek-lemma-audit lsjgold --system-cache DIR
```
`DIR` holds one `<system>/<stem>.jsonl` token file per covered edition, with your lemma on each token of the project's token stream (the stems and tokenisation are in the repository under `galen-density-map/pipeline/lsjgold/`). A pull request adding such caches under `submissions/<system>/` in the repository is scored by CI and gets its row.

## What the numbers mean, and what they do not
LSJ cites what a lexicographer found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy, and treebank test scores are not comparable with it. The Perseus LSJ XML is incomplete. Loci exist only for works held in a free edition; citations into works we do not hold, or by a locator scheme the edition does not carry, are counted but not located. Nothing here patches any system's output; every figure traces to a row.

## Source and citation
Repository and method: https://github.com/Montblanctech/Galen (release v3.0, DOI 10.5281/zenodo.24046260; concept DOI 10.5281/zenodo.21561962). Failure catalogues by system, the medical-vocabulary gap package (Hippocrates and Galen loci the neural systems miss) and the two blind validation sheets are in the repository under `galen-density-map/data/qc/lsjgold/`.

Pepperman, W. (2026). *LSJ-Gold 0.1.1: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962 (concept DOI: it resolves to the newest version; 0.1 is release v3.0, https://doi.org/10.5281/zenodo.24046260)

Underlying texts: First1KGreek (CC BY-SA 4.0), Perseus Digital Library editions and LSJ XML (CC BY-SA 3.0), Morpheus analyses via Perseids. Data: CC BY 4.0.
