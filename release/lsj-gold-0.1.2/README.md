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

# LSJ-Gold 0.1.2: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek

**LSJ-Gold** measures Ancient Greek lemmatizers on the words the dictionary itself cites. Every citation in the Perseus Liddell–Scott–Jones XML that points, by CTS URN, into a free Greek edition we hold (First1KGreek and Perseus editions) is relocated to its exact token and validated by Morpheus (the surface's analyses contain the headword) or by the single word LSJ quotes at the citation. 0.1.2: **70,198 loci over 54 authors.**

A system is scored by comparing its lemma at `token_index` with `headword`: accent-blind (the headline figure), strict, and article-convention-neutral figures are all printed by the reference scorer. Wilson 95% intervals in `lsj_gold_scores.json`.

## What changed from 0.1.1

1. **The weakest loci were read.** 652 loci rested only on the single word LSJ quotes, where Dilemma gives that form another lemma (and one Morpheus-validated locus of πόλεων under πολύς, found wrong earlier). A sample read had found about one in seven of their pairs wrong: LSJ often quotes a related or cross-referenced word in an entry, and that word passed as the headword's own form (θυμιήματα under θυμιάω, σπονδήν under σπένδω, Πατρέες under πάτραι). Each locus was read blind by two readers (Claude Opus and Claude Sonnet, each in its own session with only the sheet), with 10 anchors and 10 near-miss plants per sheet of 163 at unmarked positions, under a rule fixed before any answer was read: a locus stays only if both readers say yes. **339 stay; 313 are dropped** (`lsj_gold_0_1_2_dropped.csv`, with both readers' answers). One sheet failed its anchor gate twice and, as the rule says, all 163 of its loci are dropped, including 117 that both its readers accepted; the two anchors every reader of that sheet rejected are LSJ filing conventions (τῷ "in what way" under τις, whose accent-blind key it shares with τίς; ὅπουπερ under ὅπου) that the instructions did not state.
2. **A locus counts once.** 1,364 rows repeated a locus already listed (the same token under the same headword, where LSJ cites the passage more than once in the entry). They are removed (`lsj_gold_0_1_2_duplicates.csv`); in 0.1.1 those loci weighed double.
3. **A token cannot be gold for two headwords.** 49 tokens were gold under two different headwords (ἀγών and ἀγωνάρχης, κλίνω and κλίνη); at most one can be right, so all 99 of their rows are set aside (`lsj_gold_0_1_2_conflicts.csv`).

70,198 + 313 + 1,364 + 99 = 71,974, the rows of 0.1.1. Nothing was edited or added: the kept rows are 0.1.1 rows, in the same order. Every system is rescored on the same outputs as 0.1.1.

**What a reader should know.** The read only touched loci where Dilemma disagreed with the gold, so every dropped locus is a Dilemma miss; most were also missed by the other systems (the dropped golds were mostly wrong for everyone), and every system's figure rises. Dilemma's figure on once-cited headwords rises most (89.0 to 92.3), because the dropped loci sit mostly under headwords LSJ cites once and were chosen by Dilemma's disagreement. A sample of 50 dropped loci read afterwards held about 29 wrong golds, about 13 right ones lost to a split vote, and 8 unclear; 50 of 50 kept loci read were right. Keeping the failed sheet's 117 doubly accepted loci would give Stoicheia 92.71 and Dilemma 92.61 instead of the figures below: the two are level within their intervals either way. The readers are language models, not Greek specialists. Record: `galen-density-map/data/qc/lsjgold/recheck_0_1_2/` in the repository.

## Reference table (2026-11-11)

| system | loci | headword match % | once-cited headwords % | cited 6+ times % |
|---|---|---|---|---|
| Stoicheia tagger-parser (2026) | 67,639 | **92.8** [92.6–93.0] | 78.4 | 93.9 |
| Dilemma 1.3.15 (Open Greek, lexicon-first) | 70,166 | **92.8** [92.6–93.0] | 92.3 | 92.9 |
| Stanza 1.14 grc-perseus | 67,639 | **84.8** [84.5–85.0] | 60.0 | 87.0 |
| odyCy 0.7.0 (grc_odycy_joint_trf) | 67,639 | **82.5** [82.2–82.8] | 59.7 | 84.3 |
| Stanza 1.14 grc-proiel | 67,639 | **79.6** [79.3–79.9] | 60.0 | 81.2 |

The four neural rows are on the same 67,639 loci. Per-author columns for every system are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/lsj-gold/.

## Files
- `lsj_gold.csv` — one row per locus: `headword`, `headword_key` (accent-blind Beta Code), `author`, `work` (TLG ids), `cited_edition`, `locator` (CTS passage), `unit`, `token_index` (0-based, into the project's token JSONL for that edition), `surface`, `validation` (`morpheus` or `quoted`), `quoted_form`, `lsj_part`, `entry_key`, `status`. Columns are described in `SCHEMA.md`.
- `lsj_gold_scores.json` — the reference scores with strata (LSJ tier, validation route, citation frequency) and per-author figures.
- `leaderboard.json` — the table as the leaderboard page renders it.
- `lsj_gold_0_1_2_dropped.csv` (313), `lsj_gold_0_1_2_duplicates.csv` (1,364), `lsj_gold_0_1_2_conflicts.csv` (99) — the 0.1.1 rows set aside, same columns (the dropped file adds both readers' answers).
- `SCHEMA.md`, `CITATION.cff`, `LICENSE`, `CHECKSUMS.sha256` (computed on the files as stored; `sha256sum -c CHECKSUMS.sha256` passes on the archive and on any checkout).

## How to score your lemmatizer
```
pip install "git+https://github.com/Montblanctech/Galen#subdirectory=audit-kit"
greek-lemma-audit lsjgold --system-cache DIR
```
`DIR` holds one `<system>/<stem>.jsonl` token file per covered edition, with your lemma on each token of the project's token stream (the stems and tokenisation are in the repository under `galen-density-map/pipeline/lsjgold/`). A pull request adding such caches under `submissions/<system>/` in the repository is scored by CI and gets its row.

## What the numbers mean, and what they do not
LSJ cites what a lexicographer found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy, and treebank test scores are not comparable with it. The Perseus LSJ XML is incomplete. Loci exist only for works held in a free edition; citations into works we do not hold, or by a locator scheme the edition does not carry, are counted but not located. Nothing here patches any system's output; every figure traces to a row.

## Source and citation
Repository and method: https://github.com/Montblanctech/Galen (concept DOI 10.5281/zenodo.21561962). Failure catalogues by system, the medical-vocabulary gap package and the blind reading sheets are in the repository under `galen-density-map/data/qc/lsjgold/`.

Pepperman, W. (2026). *LSJ-Gold 0.1.2: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962 (concept DOI: it resolves to the newest version; 0.1 and 0.1.1 stay citable at their own releases)

Underlying texts: First1KGreek (CC BY-SA 4.0), Perseus Digital Library editions and LSJ XML (CC BY-SA 3.0), Morpheus analyses via Perseids. Data: CC BY 4.0.
