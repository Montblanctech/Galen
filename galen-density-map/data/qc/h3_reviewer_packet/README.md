# H3 reviewer packet — Galen Density Map (Phase 2)

## Ask
Greek-literate spot-check of lemmatizer output. For each row: **confirm or correct the lemma column**, and **flag merges** where two rows are the same headword under variant mislemmas.

## Scope
- About **50–100 items** across the files below (start with the random sample + irregular carryover + fragmentation pairs; dip into sense pools as needed).
- Estimated time: **~2 hours**.
- Results feed the methods accuracy rate (**H3**). Do **not** expect the pipeline to auto-correct from this packet — corrections stay on the human side.

## Machine-bounded worklists (H3-M, prefer these)

Human review should start from the machine-ranked queues, not the older suspect list:

- `../h3m/m1_inadmissible.csv` — surfaces whose odyCy lemma is not among Morpheus's morphological readings (error floor; frequency-ranked).
- `../h3m/m2_disagreements.csv` — tokens where odyCy and Stanza (perseus/proiel) disagree (priority queue for any future reader).
- `../suspect_high_freq_lemmas.csv` — earlier gate-6 heuristics; **superseded as the handoff** by the two files above (kept for provenance).

The frozen `accuracy_sample_random60.csv` remains the only unbiased human rate sample.

## Files
| File | What it is | Why it is here |
|------|------------|----------------|
| `accuracy_sample_random60.csv` | Uniform random sample of 60 lemmatized tokens (seed **20260725**) | Blind accuracy rate for methods |
| `h3_irregular_carryover.csv` | C4a blind-spot misses (consistently-wrong irregular lemmas the suspect gate did not catch) | Explicit carry-over onto the human list |
| `h3_fragmentation_pairs.csv` | P3-4 same-headword splits that reach the punch list (e.g. ἀρτηριόν/ἀρτηριός) | Flag merges; ranking is distorted until resolved |
| `h3_punch_sense1.csv` | Punch-list terms with LSJ `sense_count == 1` | **Cleaner candidate pool** (P3-3) — prefer this for domain-term review |
| `h3_punch_sense0.csv` | Punch-list terms with LSJ `sense_count == 0` | Noisier pool (hallucinations + mislemmas + accent mismatches); review separately |

## How to mark
- `accuracy_sample_random60.csv`: fill `lemma_correct(y/n)` and `correct_lemma_if_wrong`.
- Other CSVs: add/correct intended lemma; note merges in a comment column or side list if you prefer.
- Mislemmatizations are Greek lexical judgment — report only; do not patch the frozen lemma JSONL.

## Discipline
Pipeline is frozen-pending. This packet is diagnose/report only. No re-lemmatization from review results until a later methods pass.
