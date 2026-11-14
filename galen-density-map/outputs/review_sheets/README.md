# Review sheets for Galen First Drafts

Built by `pipeline/review_sheets.py build` from `outputs/firstdrafts/<slug>/` (units, renderings, `term_table.csv`,
`checks.json`); no model calls. Tests: `tests/test_review_sheets.py`.

## Files
- `index.html`: the list of works. `<slug>.html`: printable sheets, a cover and one passage per printed page.
- `<slug>.csv`: the same sheets as rows to fill (UTF-8 with BOM, so a spreadsheet shows the Greek); reviewer columns
  `reviewer, better, term_wrong, term_note, sense_wrong, sense_note, comment`; the text columns are for reading only.
- `reviewer_instructions.md`: one page for the reader, neutral wording.
- `key/sample_key.csv`: per sampled unit, its stratum, the stratum's size, which model is shown as 1 and as 2, and
  the machine check results. Not for the reader (the sheets hide strata, check results and model names), so it
  is not in the public repository; `review_sheets.py build` regenerates it from the same seed.
  `key/sampling.json`: parameters and per-work counts (kept with the key).
- `filled/` (put returned CSVs here) and `scores/` (written by the scorer).

## Sampling rule
Seed `20261113`; per work 10 units, 4 in D and 3 in F where possible.

(seed SEED, per-work stream random.Random(f"{SEED}:{slug}")), N_PER_WORK units in three strata:

- D (disagreement): the K_DISAGREE units with the most target terms on which renderings A and B disagree (check (b),
  term level: term_table.csv `agree` == "n"), ties broken by the higher disagreement rate, then by a seeded random
  key. Units with no disagreeing term are never in D. D is taken whole (a census of its stratum).
- F (check failure): units not in D that fail at least one of checks (a), (b), (c) (per-check verdict "fail" in
  checks.json; (c) counts only where the judge passed its gate). N_FAIL drawn at random without replacement.
- R (control): every other unit. The rest of the N_PER_WORK drawn at random without replacement; if R is too small,
  F takes the remainder. A work with N_PER_WORK units or fewer is taken whole.

Each stratum keeps its population size N_s and sample size n_s, so the scorer can weight a stratum by N_s / N and give
a whole-work estimate (stratified random sampling; D and small works are censuses).

| work | units | units with an A/B term disagreement | units failing a check | D n / N | F n / N | R n / N | sampled |
|---|---|---|---|---|---|---|---|
| adversus-lycum | 50 | 41 | 21 | 4 / 4 | 3 / 17 | 3 / 29 | 10 |
| comp-per-genera | 697 | 576 | 239 | 4 / 4 | 3 / 235 | 3 / 458 | 10 |
| hirudinibus | 6 | 3 | 1 | 3 / 3 | 0 / 0 | 3 / 3 | 6 |
| quos-quibus | 14 | 12 | 6 | 4 / 4 | 2 / 2 | 4 / 8 | 10 |
| purgantium-facultate | 20 | 16 | 12 | 4 / 4 | 3 / 8 | 3 / 8 | 10 |
| morbi-temporibus | 23 | 20 | 10 | 4 / 4 | 3 / 6 | 3 / 13 | 10 |
| adversus-typos | 38 | 28 | 8 | 4 / 4 | 3 / 4 | 3 / 30 | 10 |
| in-hipp-acut | 405 | 325 | 163 | 4 / 4 | 3 / 159 | 3 / 242 | 10 |
| de-plenitudine | 71 | 56 | 31 | 4 / 4 | 3 / 27 | 3 / 40 | 10 |
| de-comate | 23 | 17 | 9 | 4 / 4 | 3 / 5 | 3 / 14 | 10 |
| in-hipp-salubri | 51 | 37 | 23 | 4 / 4 | 3 / 19 | 3 / 28 | 10 |
| de-humero | 77 | 63 | 47 | 4 / 4 | 3 / 43 | 3 / 30 | 10 |
| difficultate-respirationis | 207 | 186 | 109 | 4 / 4 | 3 / 105 | 3 / 98 | 10 |

## Scoring
Put each filled CSV in `filled/` (or pass the paths) and run

    python -X utf8 pipeline/review_sheets.py score [CSV ...]

It maps 1 and 2 back to the models through the key, skips unread rows, reports unreadable values instead of guessing,
and writes `scores/scores.json` and `scores/summary.md`: per work the preference counts with a sign test, the share
of passages with a wrong term and with a wrong sense in each model's rendering (overall and by stratum, Wilson 95%
intervals), any error in flagged (D+F) vs control (R) passages, a stratum-weighted estimate for the whole work when
every stratum was read, and agreement between reviewers on passages read by more than one.

## What these numbers would support claiming

The numbers describe what the named reviewers found on the sampled passages of each work, with the sampling rule in
`key/sampling.json`. With about ten passages per work and one reader, every percentage has a confidence interval
tens of points wide (the Wilson intervals are printed); read them as a first measurement, not a quality rating.

- **Preference (1 vs 2, mapped back to the two models).** "On n passages of work W, reviewer R preferred model X's
  rendering k times, model Y's j times, and saw no difference m times." A sign test p is printed for information.
  It does not support "model X translates Galen better" beyond those passages and that reader.
- **Term wrong / sense wrong per rendering.** "Reviewer R marked at least one wrong term in k of n passages read." The
  control stratum (R) is a simple random sample of the work's unflagged units, so its rate (with its interval) is an
  estimate for those units. The work estimate weights the strata by their size (N_s / N); it is printed only when every
  stratum was read, and it inherits the reviewer's judgement as its definition of "wrong".
- **Flagged vs control (any error).** The comparison of D+F (passages the checks or the A/B disagreement singled out)
  with R is the one test of the machine apparatus: if flagged passages carry errors more often than controls, the flags
  point where a reader should look. With ten passages per work this is only suggestive; pooled over works it becomes a
  measurement. If controls show errors as often as flagged passages, a passage without a flag cannot be called checked.
- **What they never support.** That an unflagged passage is correct; that the whole work is usable without reading it;
  any claim about syntax, argument or attribution beyond what the reviewer wrote; and any comparison between works read
  by different reviewers (differences in reviewers and in works cannot be told apart).
