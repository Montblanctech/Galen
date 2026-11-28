# Simple Drugs 1-5: check (c) repair run (judge v0.3, second draw), note written before any repair call

**Date:** 2026-11-27, committed before the first judge call of this run. Hub order, after the first v0.3 run failed its gate.

## The first run (kept, the pre-registered result)
Judge v0.3 (`firstdrafts_v03_judge_note.md`), seed 20261109, 6,054 items (6,034 real, 10 anchors, 10 plants), 606 groups,
`claude-sonnet-5-5` effort high through the Claude Code CLI (cc backend). **Gate 19/20, failed.** The one miss: anchor J06044
("distribution", unit K11.604-605, A = B shared rendering attested in the entry) judged `out_of_range`; the judge's own
note says the sense is covered ("'distribution' alone is covered as sense; here of drug conveyance"). By the pre-registered
rule check (c) is `judge_failed_gate` for every unit and the unit verdicts rest on (a) and (b): 313 pass, 87 mixed, 8 fail,
2 insufficient. All its files are in `judge_v03_run1_seed20261109/` (with its `checks.json`); nothing in it is changed.

## What this run changes
Only the draw: `checks.py build-judge --anchors v03 --seed 20261127` (new anchors, new plants, new shuffle and grouping;
key outside the repository until scored). Prompt, model, effort, group size, whole LSJ entries, re-ask, gate (20/20) and
the unit thresholds are unchanged. All 6,054 items are judged again, so gate and items come from the same run.
Same backend as the first run (cc).

## Known limits, stated before the run
- A second draw after a failed gate raises the chance of passing by chance alone. The first run is the pre-registered
  result and stays on record beside this one; this run is reported under its own label ("repair run"), as Composition of
  Drugs by Kind reports its v0.3 re-run beside v0.2.
- The first-run miss was an anchor the judge rejected while saying its sense is covered. That is a judge error on a
  valid control, not a defective control, so unlike the v0.2 to v0.3 change nothing about the controls is fixed here.
- If this run's gate fails as well, (c) stays unused and both failures are reported.

## Result of the repair run (scored 2026-11-27, after all calls)

- Gate: **20/20 passed** (10 anchors in range, 10 plants out of range; no misses). Check (c) therefore counts in the verdicts
  of this run. The first run (seed 20261109, gate 19/20 failed) stays on record unchanged in `judge_v03_run1_seed20261109/`.
- Unit verdicts with (a)+(b)+(c): **396 pass, 12 fail, 2 insufficient** (K11.588-589, K11.619: no target pair for (b)).
  First run, (a)+(b) only: 313 pass, 87 mixed, 8 fail, 2 insufficient.
- (c) units: 393 pass / 15 fail, 96.3% [94.02-97.76]. Items in range: A 2903/3017, 96.2% [95.48-96.85] (77 out, 37 unsure);
  B 2909/3017, 96.4% [95.70-97.03] (76 out, 32 unsure). First run, exploratory: A 96.6%, B 96.1%.
- Failing units: K11.456-457, 471-472, 494-495, 498-499, 499-500, 514-515, 530-531, 580-581, 690-691, 716-717, 730-731, 740-741.
- Caveat as stated above: this is a second draw after a failed gate, so the pass is weaker evidence than a first-draw pass.
- Calls: about 610 Sonnet calls (606 groups + 1 re-ask; 6 calls that failed for a lapsed sign-in were sent again unchanged).
