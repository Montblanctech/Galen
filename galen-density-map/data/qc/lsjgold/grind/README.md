# LSJ-Gold 1.0: the reading record (2026-11-11)

How LSJ-Gold 0.1.2 became the stable 1.0. Script: `pipeline/lsjgold/grind.py` (rules in its docstring, committed before any
answer was read). Release: `release/lsj-gold-1.0/`.

## Files
- `ledger.csv`: every locus read here, its pool (the reason it was doubted), every reader's verdict in every round (JSON; A = Claude
  Opus, B = Claude Sonnet, C = a fresh Claude Opus deciding splits), and the decision.
- `r<round>_sheet_<n>.csv`, `r<round>tb_sheet_<n>.csv`: the blind sheets; `answers_*.csv`: each reader's answers;
  `key_round<n>*_PUBLISHED_AFTER_SCORING.csv`: which rows were controls, published only after scoring.
- `gates_round<n>*.json`: each reader's control score per sheet. `strata*.json`: the sizes of the strata the samples were drawn from.
- `report.json`: counts by pool and the residual error of the sampled strata. `reader_instructions.txt`: what every reader saw.

## How the reading was kept blind
Readers worked in their own sessions on a copy of the sheets in a folder that held nothing else (no ledger, no key, no other
reader's answers); the answers were copied here after each round. One reader wrote its answers through a small script that held
its own verdicts; it looked nothing up.

## Rounds
- **Round 1** (1,518 loci, 11 sheets, 22 readers + 2 tie-break readers): the loci every system misses, the tokens gold under two
  headwords, and everything 0.1.2 had dropped on a split vote or by a failed gate, plus seeded samples. The instructions now state
  LSJ's filing conventions (accent-blind headwords, -περ/-γε forms and adverbs under the simple word), the two that had failed 0.1.2's
  sheet 3. Every reader passed every gate (anchors 10/10 on 21 of 22 sheets, plants 9 or 10 of 10).
- **Round 2** (1,731 loci, 12 sheets, 24 readers + 1 tie-break reader): added after round 1's samples showed where the bulk's errors
  are. All 1,031 loci where Dilemma matches the gold and every context system misses, and samples of the remaining strata. Every
  reader passed every gate.

## The build session's own reading (a language model, not a Greek specialist)
- Round 1, 30 kept loci where every system misses (seed 20261113): **30 right** (νεώς under ναός, ἄχει under ἠχέω, τέτρωρον
  under τετράορος). These are the hard words the benchmark is for.
- Round 1, 30 dropped from the same pool: about **26 wrong golds** (νίκης under νικάω, the article under τις, ἂν under ἀνά); 4 are
  πρῶτος under πρότερος, where LSJ files πρῶτος but the readers did not: lost on purpose, conservatively.
- The 6 dropped sample loci of round 1: 5 wrong golds (χρῆν under χράω, ἁλῶν under ἁλή, φυλακῇ under φυλακεύς); 1 an LSJ filing
  question (εἰρύσατο under ἐρύω).
- Round 2, all 35 dropped: about **31 wrong golds** (ἔστω under ἵστημι, νέας "ships" under νέος, φάναι under φαίνω, πυροῖς
  "wheat" under πυρά, πειρήνας under περαίνω); about 4 LSJ filing calls lost conservatively (Πέργαμον under πέργαμον, three forms
  of μέμονα).

## What is left
`report.json` gives the residual error of the strata that were sampled, not read in full: about 400 of 70,033 loci (95% range
123–1,330). Finding them would mean reading the bulk whole. 1.0 is frozen; a correction becomes a numbered erratum, decided by the
same rules, with its own record here.
