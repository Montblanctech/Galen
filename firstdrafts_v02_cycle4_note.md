# Galen First Drafts — cycle 4: three works (pre-registered note)

**Date:** 2026-11-11. Written and committed on the lab branch before any model call for these works. The spec is `firstdrafts_v02_spec.md` (thresholds unchanged), with check (c) under judge v0.3 (`firstdrafts_v03_judge_note.md`). Translators, prompts, alignment, back-translation and scoring are exactly as in cycles 2 and 3.

## Why these three
In the census and in a literature check made on 2026-11-11 (catalogues, publishers, theses and in-preparation lists, by a research agent told to falsify), each of these works has no English translation and no announced English translation. The same check ruled out five other candidates:
- *De differentiis febrium*: complete English in Ware's 1928 Edinburgh thesis.
- The pulse *Synopsis*: complete English in Johnston & Papavramidou 2024.
- *De crisibus*: Cooper's English of the Arabic version is announced.
- *De antidotis*: Mucci 2023 translated part of book 1, and more may be planned.
- *In Hippocratis Aphorismos*: every book has some modern translation, and a project is editing it with translation.

| slug | work | Kühn | units | Greek words | targets | earlier translations |
|---|---|---|---|---|---|---|
| `de-comate` | *De comate secundum Hippocratem* (On Coma according to Hippocrates), tlg0057.tlg052 | VII 643–665 | 23 | 3,258 | 175 | Spanish, Nieto Ibáñez 2005 |
| `de-plenitudine` | *De plenitudine* (On Plethora), tlg0057.tlg050 | VII 513–583 | 71 | 11,096 | 525 | German, Otte 2001 (edition with translation) |
| `in-hipp-acut` | *In Hippocratis De victu acutorum commentaria*, books II–IV (Commentary on Regimen in Acute Diseases), tlg0057.tlg087 | XV 515–919 | 405 | 54,030 | 2,820 | Book I only: French, Pietrobelli 2019. Book II, ch. 20–23: German excerpt, Müri 1979. No English of books II–IV found |

Book I of the commentary is left out because it already has a modern translation. `units.py` gained a book filter: a work entry may list `books`, and only units wholly inside those books are kept. The units-meta word count of `in-hipp-acut` (67,039) is that of the whole TEI before the filter; the units hold 54,030 tokens.

## Mode and order
- **Mode.** Batch mode (Message Batches) for every stage. Timestamps are batch-scoped, and the rows say so.
- **Order.** Smallest first: `de-comate`, `de-plenitudine`, `in-hipp-acut`.
- **If the run stops.** Nothing more is sent, and every stage resumes from its files. A work is not published until all of its stages are complete.

## Checks and claims (fixed here)
- **Checks.** (a) back-translation, (b) A–B term agreement, (c) the salted LSJ judge under v0.3 (gate 20/20, seed 20261111), and unit verdicts, all as in the spec.
- **Reference check (d).** No human reference translation exists for these works, so no (d) is computed. That gap goes in each README.
- **Claim wording.** "The first complete English translation we know of", followed by each work's earlier translations as in the table above. For the commentary the claim is about books II–IV only.
- **Before publishing.** Nothing goes public until Will says so. Before that, the scrub scripts run and the public diff is read.
