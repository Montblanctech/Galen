# LS-Gold 1.0: lemmatizer accuracy on the dictionary-cited stratum of Latin

**LS-Gold** measures Latin lemmatizers on the words Lewis & Short's *Latin Dictionary* (1879) cites. Every L&S citation that points, by CTS URN, into a Perseus canonical-latinLit edition is relocated to its exact token and validated by two independent offline analysers (Collatinus and Whitaker's Words), or by the form L&S quotes. The Latin twin of LSJ-Gold. **1.0: 157,855 loci over 33 authors.**

A system is scored by comparing its lemma at `token_index` with `headword`: blind (case, diacritics, u/v and i/j folded; the headline figure) and strict figures, with Wilson 95% intervals in `ls_gold_scores.json`.

## What "stable" means here

1.0 is the first frozen release. **Every locus with a reason to doubt its gold was read**, blind, by two readers (Claude Opus and Claude Sonnet, each in its own session with nothing but the sheet), and a third (a fresh Claude Opus) decided every split: a locus stays only on two readers' yes. Each sheet carried 10 anchors and 10 near-miss plants at unmarked positions; every one of the readers passed every gate. The rules, including the trigger that sent a whole stratum to round 2, were committed before any answer was read. **What was not read one by one was sampled**, and its residual error is stated below. **1.0 is frozen**: any later correction will be a numbered erratum, decided the same way. The readers are language models, not Latinists.

## How 1.0 was made from v0

1. A locus repeated in L&S counts once: 2,433 repeated rows removed (`ls_gold_1_0_duplicates.csv`).
2. Two rounds read 5,098 loci (`ledger.csv`, every verdict of every reader):

| pool | loci | kept | dropped |
|---|---|---|---|
| every system misses the gold (the lexicon baselines included) | 1,338 | 1,031 | 307 |
| a token gold under two headwords | 140 | 37 | 103 |
| a lexicon baseline matches, every neural system misses (read in full) | 2,353 | 2,077 | 276 |
| the same stratum, first sample (its drop rate triggered the full read) | 300 | 275 | 25 |
| validated only by the form Lewis & Short quotes | 467 | 437 | 30 |
| sample: the bulk | 400 | 399 | 1 |
| sample: Whitaker-validated loci | 100 | 98 | 2 |

Where every system, the lexicon baselines included, misses the gold, about a quarter of the golds were wrong (*ita* under *eo*, *sine* under *sino*, *virum* under *vis*) and three quarters were right: the hard stratum the benchmark is for. Where the analysers validated a gold that every neural system rejects, about one in eight was a homograph the context rules out (276 of 2,353 read). Every dropped locus is in `ls_gold_1_0_dropped.csv` with its reason; 157,855 + 744 + 2,433 = 161,032, the rows of v0. Nothing was edited or added.

## Residual error (`residual_error.json`)

| stratum not read one by one | loci | sample drops | rate [95%] | expected wrong golds |
|---|---|---|---|---|
| bulk (analyser-validated, some system matches) | 151,472 | 1 of 400 | 0.2% [0.0–1.4] | about 379 (67–2,124) |
| validated by Whitaker's Words only | 2,119 | 2 of 100 | 2.0% [0.5–7.0] | about 42 (12–148) |

In all, about 421 of 157,855 loci (95% range 79–2,273) may still carry a wrong gold, about 0.3%. Corrections are welcome and will be errata.

## Reference table (2026-11-11)

| system | loci | headword match % | once-cited headwords % |
|---|---|---|---|
| LatinCy la_core_web_lg | 157,855 | **85.3** [85.2–85.5] | 70.9 |
| CLTK | 157,855 | **84.4** [84.2–84.5] | 80.2 |
| Stanza la-proiel | 157,855 | **75.9** [75.7–76.1] | 55.7 |
| Stanza la-perseus | 157,855 | **65.8** [65.5–66.0] | 42.3 |
| Stanza la-ittb | 157,855 | **65.6** [65.4–65.8] | 46.8 |
| Stanza la-llct | 157,851 | **44.6** [44.4–44.9] | 33.2 |
| Collatinus, first analysis (baseline) | 156,841 | **82.5** [82.3–82.7] | 86.8 |
| Whitaker's Words, first analysis (baseline) | 144,719 | **81.7** [81.5–81.9] | 82.7 |

Every system rises 0.2–0.4 points from v0 and the order is unchanged. Per-author columns are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/ls-gold/.

## Files
- `ls_gold.csv`: one row per locus (`headword`, `headword_key`, `author`, `work`, `cited_edition`, `locator`, `edition_stem`, `unit`, `token_index` into the project's Latin token stream, `surface`, `validation`, `quoted_form`, `entry_key`, `entry_id`, `status`).
- `ls_gold_scores.json`, `leaderboard.json`: reference scores, strata and per-author figures.
- `ledger.csv`: every locus read in the rounds, its pool, every reader's verdict (A Opus, B Sonnet, C the third reader) and the decision; `residual_error.json`.
- `ls_gold_1_0_dropped.csv` (744, with `why` and `readers_headword`), `ls_gold_1_0_duplicates.csv` (2,433).
- `CITATION.cff`, `LICENSE`, `CHECKSUMS.sha256` (`sha256sum -c CHECKSUMS.sha256` passes on the archive and on any checkout).

## Source and citation
Repository and method: https://github.com/Montblanctech/Galen (concept DOI 10.5281/zenodo.21561962); the reading sheets, answers and keys are under `galen-density-map/data/qc/lsgold/grind/`.

Pepperman, W. (2026). *LS-Gold 1.0: lemmatizer accuracy on the dictionary-cited stratum of Latin* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962

Underlying data: Lewis & Short via PerseusDL/lexica and Perseus canonical-latinLit editions (CC BY-SA); Collatinus and Whitaker's Words as validators. Data: CC BY-SA 4.0.
