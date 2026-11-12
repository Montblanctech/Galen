# LS-Gold 1.0: the reading record (2026-11-11)

How LS-Gold v0 became the stable 1.0. Script: `pipeline/lsgold/grind_la.py` (rules in its docstring, committed before any
answer was read; the Latin twin of `pipeline/lsjgold/grind.py`). Release: `release/ls-gold-1.0/`.

## Files
- `ledger.csv`: every locus read, its pool, every reader's verdict in every round (JSON; A = Claude Opus, B = Claude Sonnet, C = a
  fresh Claude Opus deciding splits), and the decision.
- `r<round>_sheet_<n>.csv`, `r<round>tb_sheet_<n>.csv`: the blind sheets; `answers_*.csv`; `key_round<n>*_PUBLISHED_AFTER_SCORING.csv`.
- `gates_round<n>*.json`: each reader's control score per sheet. `strata.json`: stratum sizes. `report.json`: counts and residual error.

## Rounds
- **Round 1** (2,745 loci, 19 sheets, 38 readers + 2 tie-break readers): the loci every system misses (the lexicon baselines
  included), the quoted-route loci, the tokens gold under two headwords, and seeded samples. Every reader passed every gate, all 10/10.
  The reading paused after 18 sheets; sheet 19 was read later, and its key was kept out of the folder until then.
- **Round 2** (2,353 loci, 16 sheets, 32 readers + 2 tie-break readers): the pre-registered trigger fired (the lexicon-only sample
  dropped 8.3%, above 1%), so every locus where a lexicon baseline matches and every neural system misses was read. Every reader passed
  every gate, all 10/10.

## The build session's own reading (a language model, not a Latinist; seed 20261114)
- 30 kept loci from the two big pools: about **30 right** (*tenvius* under *tenuis*, *conbibat* under *combibo*, distributive *seni*,
  *apta* under *apo* as Lewis & Short files it).
- 30 dropped: about **24 wrong golds** (*ita* under *eo*, *sine* under *sino*, *virum* under *vis*, *atque* under *at*, *scientia*
  under *scio*); about 6 conservative losses on Lewis & Short's filing (*Trivia* under *trivius* twice, *aptus*/*apte* under *apo*
  twice, *stabulare* under *stabulor*, *declinatum* under *declinatus*). The readers were not fully consistent on *apo*: one *apta* was
  kept and two *aptus* dropped.

## What is left
`report.json`: about 420 of 157,855 loci (95% range 79–2,273) may still carry a wrong gold, almost all in the bulk. 1.0 is frozen;
a correction becomes a numbered erratum, decided by the same rules.
