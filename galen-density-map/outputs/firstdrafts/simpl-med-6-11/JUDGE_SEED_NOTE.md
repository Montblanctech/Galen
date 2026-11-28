# Simple Drugs 6-11: check (c) judge draw, note written before any model call

**Date:** 2026-11-27, committed with the prep, before the first back-translation or judge call of these checks.

## The draw
- Judge v0.3 (`firstdrafts_v03_judge_note.md`), as Simple Drugs 1-5: `checks.py build-judge --work simpl-med-6-11
  --anchors v03 --seed 20261128`.
- **Seed 20261128**, chosen now and not changed afterwards. It is a new seed: 20261109 (1-5 first run and the v0.2 works),
  20261111 (the v0.3 re-judging) and 20261127 (1-5 repair run) are not reused.
- Key outside the repository until every item is scored;
  then it is copied into this folder as `judge_key_PUBLISHED_AFTER_SCORING.csv` by `checks.py score`.

## Unchanged from Simple Drugs 1-5
Prompt, model (`claude-sonnet-5-5`, effort high, cc backend), groups of ten, whole LSJ entries, one
re-ask of unanswered items, the gate (20/20: 10 anchors `in_range`, 10 plants `out_of_range`), the in-range share
threshold (>= 0.80), the out-of-range threshold (<= 2 items per unit), and the unit rule: a unit fails when it fails
two of (a)-(c) (n/a counts neither way). Back-translation (a) and term agreement (b) as in `checks.py` THRESHOLDS.

## If the gate fails
Check (c) is reported as `judge_failed_gate` and plays no part in the verdicts. No second draw is made without the
hub's order; if one is ordered it is reported under its own label beside this run, as in Simple Drugs 1-5.

## First run result (seed 20261128, scored 2026-11-28)
**Gate 19/20, failed.** The miss: plant J06805 (Simp.7.12.1, target 79, διαφορᾷ, planted English "scars" taken from
Simp.7.10.1 target 215), group G00284. The judge's first line for the item says `in_range` with the note "Wait: see
below"; at the end of the same answer it writes "Correction for the item I marked incorrectly" and gives `out_of_range`
("διαφορά means difference here; 'scars' matches no listed sense"). The rule used in every run keeps the first line given
for an item (`checks.answers_from_groups`), so the gate counts `in_range`. By the pre-registered rule check (c) is
`judge_failed_gate` and the verdicts rest on (a) and (b): 410 pass, 126 mixed, 9 fail, 3 insufficient. All its files
are in `judge_v03_run1_seed20261128/` (with its `checks.json` and its published key); nothing in it is changed.

## Repair run (hub order 2026-11-28), written before any repair call
- Only the draw changes: `checks.py build-judge --work simpl-med-6-11 --anchors v03 --seed 20261129` (new anchors, new
  plants, new shuffle and grouping). **Seed 20261129**, chosen now and not changed afterwards; not used by any earlier run.
  Key outside the repository until scored.
- All 6,810 items are judged again, so gate and items come from the same run, as in the Simple Drugs 1-5 repair run.
- Unchanged: prompt, model, effort, backend, groups of ten, whole LSJ entries, re-ask, the gate (20/20), the thresholds,
  the unit rule and the parsing rule (the first line given for an item counts).
- Known limit: a second draw after a failed gate raises the chance of passing by chance alone. The first run stays on
  record beside this one, and this run is reported under its own label ("repair run"). If its gate fails as well, (c)
  stays unused and both failures are reported.

## Disclosed: items answered twice in one group (first run)
36 items were answered twice within one judge answer; 5 of them with two different verdicts. The first line counted in
each case, by the rule above; the rule is not changed. Group, item, first verdict -> later verdict:
G00092 J05075 out_of_range -> in_range; G00213 J02668 out_of_range -> in_range; G00284 J06805 in_range -> out_of_range
(the gate miss); G00566 J06068 out_of_range -> in_range; G00591 J02525 out_of_range -> in_range.

## Result of the repair run (seed 20261129, scored 2026-11-28, after all calls)
- Gate: **20/20 passed** (10 anchors in range, 10 plants out of range). Check (c) therefore counts in the verdicts of this
  run. The first run (seed 20261128, gate 19/20 failed) stays on record unchanged in `judge_v03_run1_seed20261128/`.
- Unit verdicts with (a)+(b)+(c): **521 pass, 24 fail, 3 insufficient** (Simp.8.17.6, Simp.8.17.7, Simp.9.2.14: no target
  pair for (b)). First run, (a)+(b) only: 410 pass, 126 mixed, 9 fail, 3 insufficient.
- (c) units: 494 pass / 50 fail, 90.8% [88.09-92.96] (4 n/a). Items in range: A 3217/3395, 94.8% [93.96-95.46] (146 out,
  32 unsure); B 3222/3395, 94.9% [94.11-95.59] (138 out, 35 unsure). First run, exploratory: A and B 3218/3395 each, 94.8%.
- Failing units: Simp.6.1.15-6.1.16, 6.1.54-6.1.55, 6.3.6, 6.4.7-6.4.8, 7.10.32, 7.10.36, 7.11.16, 7.11.18, 8.13.9,
  8.15.3, 8.15.12, 8.16.8, 8.18.1, 8.18.44, 8.21.2-8.21.3, 8.21.9, 8.22.1, 8.22.8, 9.3.15, 9.3.26-9.3.27, 10.2.12,
  10.2.16, 11.1.15, 11.1.18.
- Items answered twice in one group in this run: 11, none with two different verdicts.
- Caveat as stated above: this is a second draw after a failed gate, so the pass is weaker evidence than a first-draw pass.
- Calls: 681 groups + 1 re-ask (8 items), claude-sonnet-5-5, 12:39Z-13:35Z, run without a stop.
