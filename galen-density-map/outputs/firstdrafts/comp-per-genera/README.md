# Galen, *De compositione medicamentorum per genera* (On the Composition of Drugs by Kind) — Galen First Drafts v0.2, cycle 2: PREPARED, NOT RUN (2026-11-09)

**State.** Everything that does not need a model has been built and committed; **no model has been called for this work.** The spec that governs the run is `firstdrafts_v02_spec.md` at the repository root (pre-registered thresholds, order of the run, calibration gate, cost rule, exact commands). This README is the pre-run record; the run's README replaces it.

## Source and units (`units.py`, deterministic)
- Greek: First1KGreek `tlg0057.tlg077.1st1K-grc1` (Kühn XIII 362–1058, seven books, 113 chapters; Kühn has a chapter 3a, recorded as `book.chapter`), CC BY-SA 4.0; all 697 page breaks present.
- **697 units**, 104,760 Greek words (38–241 per unit, median 154); 607 units span two Kühn pages, 90 one; 7 carry a book title line. Alignment to the odyCy stream of the density map: loss 1.26%.
- **5,476 targets** (NOUN/ADJ; every punch-list token first, then four-way `genuinely_hard` rarest-first; cap 8 per unit, 657 units at the cap): punch-list 3,737 (thin 1,877, absent 1,860), four-way-only 1,739. Dilemma 1.3.15 lemma for each.
- Difficulty terciles (punch-list NOUN/ADJ per 100 tokens): ≤3.66 low, ≤6.29 mid, above high (234/232/231 units). *Against Lycus* had terciles 0.56/1.75: this work is six times denser in the map's thin and absent vocabulary.

## LSJ index (`lsj_index.py`, v0.2: whole entries)
- 1,165 of 1,869 lemma keys resolve to a Perseus-LSJ entry; **5,350 of 5,476 targets (97.7%) have an entry.** `lsj_entries_missing.json` lists the 704 keys without one (drug and plant names, compound adjectives, lemmatizer forms LSJ does not head).
- Entries are stored whole (median 423, mean 898, p90 2,062, max 16,384 characters) with every sense's text and a first-sense gloss; 35 entries yield no gloss.

## Calibration set (`reference.py`)
- Zainaldin et al. 2026, github.com/campattison/galen_project (commit ad2d611): Manuela Marai's reference English of ten passages of this work, **CC BY 4.0**; copies, the upstream README and LICENSE, and our `LICENCE.md` (attribution, checksum check against the upstream REFERENCES.md: match) in `reference/`.
- `calibration_map.json`: the ten passages (Kühn XIII 367–369, 431–432, 499–500, 569–570, 635–636, 703–704, 771–773, 840–842, 909–911, 983–984) mapped by page to **33 units**, confirmed by Greek token recall 0.987–1.000. These units go first in the run and are scored on check (d), reference agreement, before anything else is sent.

## Cost (`cost_estimate.json`, before the run)
Direct mode **$218.53** (A $123.84, B $49.54, back-translation $22.10, judge $23.05), batch mode $109.26; both figures include a thinking allowance (2,500 / 800 / 600 output tokens per translation unit / back-translation unit / judge group) that the cycle 1 proxy lacked; without it $78.82 / $39.40. Cap $500 (Will, 2026-11-09). The real cost is written call by call to `usage.jsonl`; the spec's projection rule after the calibration step picks direct or batch mode for the remaining 664 units.

## Files present now
`units.jsonl`, `units_meta.json`, `targets.csv`, `cost_estimate.json`, `requests.jsonl` (base prompts, no term memory) + `requests_README.md`, `lsj_entries.json`, `lsj_entries_missing.json`, `reference/` (`on_comp.txt`, `passage_locations.csv`, `REFERENCES.md`, `README_upstream.md`, `LICENSE_code_MIT.txt`, `LICENCE.md`, `calibration_map.json`, `passages.jsonl`). Everything else named in the spec's file list is produced by the run.

## Dry run (no model)
The whole pipeline after the renderings (align → build-bt → build-judge → score with (a)–(d) and memory consistency) was exercised on a scratch copy with synthetic renderings for the 33 calibration units (`FIRSTDRAFTS_OUT` override); the scratch copy is not in the repository. The API backend's key handling, resume, pricing and parsers were tested offline; `load_api_key` was exercised once and reported only that a key is present.

## Results (v0.2 run, 2026-11-09; Claude API, direct mode; `checks.json`, `usage.jsonl`)

**Run.** 697 units of *De compositione medicamentorum per genera* (Kühn XIII 362–1058, 104,760 Greek words), every unit rendered by claude-fable-5-1 (A) and claude-opus-5-5 (B) with the same neutral prompt and term memory as context, back-translated by claude-sonnet-5-5, and 5,476 target terms judged against whole LSJ entries. The run paused once at 03:01 when the API account's prepaid balance ran out (rendering B at 194 of 697) and resumed from its files at 09:40 after the account was funded; no unit was sent twice.

**Spend: $186.87** (A $104.77, B $36.78, back-translations $28.14, judge $17.20; 3,690 calls). The pre-run estimate was $218.53 with a thinking allowance and $78.82 without; the calibration projection was $189.

**Checks (thresholds pre-registered in `firstdrafts_v02_spec.md`).**
- (a) back-translation: 663 of 692 units pass (95.8%, Wilson 94.1–97.1); mean term recall A 0.80, B 0.80.
- (b) A/B term agreement: 4,259 of 5,476 terms (77.8%, 76.7–78.9); punch-list terms 78.5%, others 76.3%; 502 of 697 units pass the 70% rule (72.0%).
- (c) salted LSJ judge: **failed its 20/20 gate (12/20)**. Four of the eight misses are planted errors the judge did not answer at all ("missing"), and about a fifth of all items came back without an answer (A 1,054 and B 1,075 of about 5,350): the judge, fed whole LSJ entries in groups of ten, drops items. The four anchor misses ("shedding", "of the date-palm", "somewhat wet", "previous to") are valid first-sense glosses the judge would not accept. Check (c) is reported unused, as in cycles 1 and 2's calibration; the exploratory unit-level figure (297 pass / 400 fail) is not used for verdicts.
- (d) agreement with the human reference (Marai's English of ten passages, 33 units): A 63.5% (55.2–71.1), B 66.4% (58.2–73.8), both above the pre-registered expectation of 60% and well above the 40% halt line.
- Term memory: the same lemma rendered as before in 94.3% (A) and 94.0% (B) of later occurrences.
- Difficulty: punch-list density does not predict A/B disagreement at unit level (Spearman ρ 0.02, n 697).

**Unit verdicts:** 478 pass, 206 mixed, 9 fail, 4 insufficient (both checks a and b need a value). Every unit is published and marked; nothing is dropped.

**Page.** `docs/first-drafts/comp-per-genera/`: a contents page and one page per book (seven, about 1 MB each), with the Greek, both renderings, the term table and the check marks per unit; `data.json` holds everything machine-readable.

**What this run shows and does not.** Two independent models agree on four of five technical terms in the hardest Greek pharmacology we hold, and both land about two thirds of the reference translator's term choices, which is the expectation we wrote before the run. The judge, the one check that compares a rendering with the dictionary rather than with another model, has failed its own control gate three times now and needs a different design (v0.3: one item per request, or anchors drawn from attested translations, and a check that every item is answered). No scholar has read these pages.

