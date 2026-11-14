# Cross-work term index of the Galen First Drafts (2026-11-13)

Built by `pipeline/firstdrafts/term_index.py` (tests: `tests/test_firstdrafts_term_index.py`, 21 pass). No model call.
It reads each Galen work's `term_table.csv` and the published drafts pages (only to find each unit's anchor).

## Files

| file | what |
|---|---|
| `term_index.json` | `summary`, `most_inconsistent` (keys, ranked), `lemmas`: one record per lemma with LSJ entry, first sense (cleaned and raw), group, per-work renderings of A and B with counts, Kühn loci with page file and anchor, and the flags |
| `term_index.csv` | one row per lemma × work: usual rendering, A and B renderings with counts, Kühn loci, flags |
| `term_occurrences.csv` | one row per target occurrence (12,411): unit, Kühn citation, `anchor` (`<slug>/<file>#<unit>`), A, B, agree |
| `anchors_check.json` | units cited (1,680) and the units whose anchor is missing (none) |

The page is built with `--page DIR` (into scratch, not `docs/`). Its links are `../<slug>/[book-N.html]#<unit>`, so it
belongs in a sibling folder of the drafts, e.g. `docs/first-drafts/terms/index.html`. The page is 936 KB (241 KB gzipped).
All data is embedded; search covers Greek (accents optional), LSJ beta key, the LSJ gloss and every English rendering; it shows 60 cards at a time and builds each
work table only when a card is opened. It also takes `#q=<term>` in the URL.

## Counts (from `term_index.json` summary)

- 13 works, 12,411 target occurrences, **2,320 lemmas** (2,248 keyed by LSJ entry, 72 by an accent-blind Dilemma lemma).
- NOUN 1,417, ADJ 903.
- Lemmas by number of works: 1: 1,336 · 2: 538 · 3: 247 · 4: 100 · 5: 48 · 6: 27 · 7: 10 · 8: 4 · 9: 6 · 10: 3 · 12: 1.
- Groups (keyword heuristic): drugs 152, anatomy 79, diseases 91, qualities 107, other 1,891.
- In two or more works: 984. Of these, **478 have a different usual rendering in at least one work** (514 before setting
  degree forms aside); A alone changes across works for 486, B alone for 506.
- Units cited: 1,680; **anchors missing: 0** (checked against `docs/first-drafts/<slug>/*.html`, book pages included; the test re-reads every cited file).

## Method

- Lemma key: the LSJ entry id, else the accent-blind Dilemma lemma.
- Renderings are compared by the term table's `norm_A` / `norm_B`: the same key check (b) uses. For divergence, a coarser
  `core` key also sets aside degree words and endings, so rare / rarer / more rarely count as one rendering.
- Usual rendering of a lemma in a work: the commonest core key over A and B pooled (ties go to the alphabetically first).
  `diverges`: the works' usual renderings differ. `flag_A` / `flag_B`: the same for one model.
- Ranking (`inconsistency_rank`): only works where the lemma occurs at least twice count, and at least three such works
  are needed. Adjectives of the group 'other' (πάμπολυς, μικρός, ἑκάτερος…) are left out. Order: lowest share of works on the
  commonest usual rendering. 23 lemmas qualify.
- Groups: cue words matched in the usual renderings (weight 2), the LSJ first sense (1) and the start of the LSJ entry (1).
  A group needs a score of 2 and at least one hit in the renderings. **Spot-check (my reading, not a scholar's; seeded
  sample of 15 per group): about 51 of 60 look right.** Misses: σκεῦος "vessel", ἕξις "habit of body", κρέας "meat" and
  σπληνικός (spleen patients) under anatomy; προπετής "rash" (hasty) and καταγματικός (fracture plasters) under diseases;
  καταφορά (heavy sleep) under qualities; φηρμάκιτς (lemmatizer debris) under drugs.

## Most inconsistent terms across works (ranked; usual rendering per work, occurrences in brackets)

Worth showing scholars. Each row is a place where the two models, each with a term memory of one work only, settled on
different English for the same Galenic term in different works:

- **ἀραιός** (LSJ "thin"): *of looser texture* / *loose-textured* in the Hippocratic commentaries, but *rare* (51) in De
  difficultate respirationis. There A says "rare" 47 times and B "sparse" 45 times. The word means *infrequent* breathing there, which neither "rare" nor "sparse" says plainly.
- **δριμύς** ("piercing"): *acrid* in Comp. per genera (45) but *pungent* in In Hipp. acut. (31). These are the two standard English terms
  for one Galenic drug quality.
- **φῦμα** ("growth"): transliterated *phymata* (Comp. per genera), *growths* (De salubri), *tumours* (De diff. resp.).
- **συνάγχη** ("sore throat"): *synanche* in two works, *anginas* in De diff. resp.
- **νεῦρον** ("sinew"): *nerves* in three works, *sinews* in De humero. This is the classic nerve/tendon ambiguity of the word.
- **χυμός** ("like χυλός"): *flavour* in Adversus Lycum, *humour* in In Hipp. acut. and De plenitudine.
- **κεφάλαιον**: *main point* / *chief point* / *summary* / *heading*. **γνώρισμα**: *sign* / *mark* / *distinguishing mark* / *recognisable sign* across seven works.
- **ὑπόθεσις**: *hypotheses* in three works, *supposition* in De diff. resp. **κατάστασις**: *state* / *constitution*.

The same list shows faults in the data rather than in the translation:

- **σπλήν**: *compresses* in De humero. That is σπληνίον (compress) lemmatized as σπλήν.
- **κῶλον**: *limb* vs *colon*. The accent-blind LSJ key merges κῶλον (limb) and κόλον (colon).
- The same merging gives ἀδήν (gland) the gloss of ἄδην ("to one's fill"), and joins ποσός/πόσος and ποιός/ποῖος under one entry.
- 166 lemmas have an LSJ entry but no usable first sense: the index stored a fragment such as "cf", "etc" or "is dub.)". The page shows
  "no LSJ gloss" for these, and the raw value is kept in `lsj_first_sense_raw`.

## Ready to publish?

The data and the page are complete and checked: counts reconcile with the term tables, and every locus links to an existing anchor.
The page works at phone width (checked in the app browser at 375 px: search, the per-work table and a link into
`in-hipp-acut/book-2.html#K15.609-610`). Points for the build session to weigh:

1. The groups are a heuristic (about 85% right on my 60-item read). The banner says so. They could be hidden instead.
2. Glosses come from the drafts' LSJ index, so its accent-blind collisions show here too (ἀδήν, κῶλον).
3. Publishing means copying the built page to `docs/first-drafts/terms/` and adding a link on the drafts index (`page.py` / `landing.py`). Neither was done here: the sprint rules keep this session out of `docs/`.
