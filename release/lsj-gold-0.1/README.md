---
license: cc-by-4.0
language:
  - grc
tags:
  - ancient-greek
  - lemmatization
  - evaluation
  - lexicography
  - galen
pretty_name: LSJ-Gold and the Galen punch list
size_categories:
  - 10K<n<100K
---

# LSJ-Gold 0.1 (rule v0.3.1, 93,926 loci over 54 authors) + the Galen Density Project punch list (v3)

**LSJ-Gold** is a benchmark for Ancient Greek lemmatizers on the *dictionary-cited stratum*: every row is a token in a First1KGreek or Perseus edition that the Liddell–Scott–Jones lexicon (Perseus XML) cites for a headword, relocated to its exact token index with the method and validation route recorded (`morpheus`: the surface's Morpheus analyses contain the headword; `quoted`: the surface equals LSJ's quoted form). Score any lemmatizer by comparing its lemma at that token with the LSJ headword (accent-blind, strict, and article-convention-neutral figures are all printed by the reference scorer).

**The punch list (v3)** is the Galen Density Project's 1,433 Galenic key lemmas with LSJ sense tiers, Dilemma headword map, two blind readers' verdicts and the 108 real headwords missing from the Perseus LSJ.

## Files
- `lsj_gold_v0.csv` — headword, headword_key (accent-blind Beta Code), author, work, cited_edition, locator, unit, token_index (into the First1K edition's odyCy token stream, `<stem>.jsonl` of the project), surface, validation, quoted_form, lsj_part, entry_key.
- `lsj_gold_table.md` / `lsj_gold_scores.json` — the reference table (Dilemma 1.3.15 90.1% on 93,750 loci; Stoicheia 87.7%, Stanza 1.14 grc-perseus 79.6%, odyCy 0.7.0 75.7% and Stanza grc-proiel 72.0% on the same 90,452 loci; once-cited headwords: 83.8 / 67.6 / 53.3 / 52.6 / 50.8).
- `validation/`, `validation_v03/` — the two blind salted sheets, answers, keys (published after scoring) and summaries; `failures/` — the failure catalogue by pattern and headword; `lsj_citation_counts.json` — how often LSJ cites each entry.
- `punch_list_v3.csv`, `real_headwords_no_perseus_lsj.csv`, `absent_tier_headword_map.csv`, `reader_pass/` — the Galen deliverables with keys published after scoring.

## How to score your lemmatizer
```
pip install greek-lemma-audit
# produce <stem>.jsonl token files for the covered works with your lemmas, then
python pipeline/lsjgold/score.py --system-cache <dir-with-<system>/<stem>.jsonl>
```

## Honesty
LSJ cites what a lexicographer found interesting in 1940: this is the rare, dictionary-worthy stratum, not overall accuracy. The Perseus LSJ XML is incomplete. Loci exist only for works held in First1K editions (v0: Hippocrates, Sophocles, Aeschylus (3 plays), Galen). No human reader has validated the relocation yet; the blind salted sheet for that is in the repository.

## Citation
Pepperman, W. (2026). greek-lemma-audit and LSJ-Gold. Zenodo. DOI: [fill in]. Preprint: 10.5281/zenodo.22162810.
