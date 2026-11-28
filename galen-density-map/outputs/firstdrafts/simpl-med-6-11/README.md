# Galen, *De simplicium medicamentorum temperamentis ac facultatibus* (On the Mixtures and Powers of Simple Drugs), books 6–11 — machine first draft v0.1

**What this is.** The second half of the Simple Drugs drafts in *Galen First Drafts*: a machine translation of books 6–11, the catalogue of simple drugs, with the Greek beside it. Books 1–5 are in `../simpl-med-1-5/`; both halves are on one work page, `docs/first-drafts/simpl-med/`, one page per book. Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these drafts. They are for reading and for correction, not for quotation. The banner says so on every page; the apparatus says where to look, not that the text is right.

**Earlier translations we know of.** Books 6–8: a French translation with the Greek by C. Manco (doctoral thesis, Montpellier and Bologna, 2020). The prefaces of books 6–11 and the first two entries of book 6: English by M. Coughlin (ancientmedicine.org, 2023). All eleven books: a free French version by H. Fayard (1548). An unreviewed machine translation into English of Kühn XI and XII, the volumes containing these books, was posted at Source Library (sourcelibrary.org) during 2026. The drafts were translated from the Greek alone.

## Source and units
- Greek: C. G. Kühn, *Claudii Galeni Opera Omnia* vol. XI p. 789 to vol. XII p. 377 (Leipzig 1826), First1KGreek `urn:cts:greekLit:tlg0057.tlg075.1st1K-grc1`, CC BY-SA 4.0. Config: `pipeline/firstdrafts/configs/simpl-med-6-11.json`.
- **548 passages** cut at the catalogue's entries (one drug each; entries under 25 words joined to the next), cited by book, chapter and entry (ids `Simp.<book>.<chapter>.<entry>`). **69,787 Greek words**, **3,488 target words** chosen by the same fixed rule as books 1–5.

## Renderings
Each passage translated twice, independently: rendering A by `claude-fable-5-1`, rendering B by `claude-opus-5-5`, fresh context. The prompt is the neutral prompt of the other works with one block added for this work: a fixed glossary of technical terms, the English for each taken from the place in books 1–5 where Galen himself defines or uses the term, listed when the term occurs in the passage (`glossary.tsv`). The renderings and all the checks were made through the Claude Code command-line tool, which adds a fixed preamble of its own to every prompt, so the context the models saw is not identical to an API run. Files: `requests.jsonl` (with `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, aligned sentence by sentence with the Greek in `alignment.json`.

## Checks (thresholds fixed before the run, as books 1–5)
- (a) Back-translation into Greek by `claude-sonnet-5-5`: 532 of 548 passages pass for A (97.1%), 530 for B (96.7%); **524 pass for both (95.6%, 95% interval 93.6–97.0)**.
- (b) Agreement of A and B on the target words: **2,831 of 3,488 (81.2%, 79.8–82.4)**; 425 of 545 passages meet the 70% rule (78.0%).
- (c) Judge with the whole LSJ entry, salted with 10 planted errors and 10 controls (`JUDGE_SEED_NOTE.md`, written before any call). The pre-registered run (seed 20261128) **failed its control gate, 19 of 20**: for one planted error (the English "scars" set against διαφορά, which means difference there) the judge's first answer was "in range", and later in the same answer it corrected itself to "out of range". The rule fixed before the run counts the first answer given for each item, so the gate failed and that run's verdicts were not used; it is kept unchanged in `judge_v03_run1_seed20261128/`. A second draw of the controls (seed 20261129, fixed before any call; nothing else changed, all 6,810 items judged again) **passed 20 of 20**; on it 494 of 544 passages pass (90.8%, 88.1–93.0), and 94.8% of A's and 94.9% of B's judged words fall within the LSJ entry. A pass on a second draw is weaker evidence than a pass on the original draw. Items answered twice within one answer: 36 in the first draw (5 with two different verdicts, the gate miss among them), 11 in the second (all with the same verdict); the first answer counted each time.
- **Verdicts on (a)–(c): 521 passages pass, 24 fail, 3 cannot be scored**; all are kept (`checks.json`, `term_table.csv`).
- Flags, places for a reader to look, not confirmed errors: the fidelity check flags 71 of 3,828 sentence pairs in A (18.5 per 1,000) and 133 of 3,925 in B (33.9) (`fidelity_*.json`); the names check flags 188 pairs in A (49.1 per 1,000) and 212 in B (54.0) (`names_*.json`). They play no part in the verdicts.

## Changes in the checks from books 1–5
1. The fidelity and names checks strip the catalogue's entry markers (such as `[6.1.1]`) as well as Kühn page markers; before this fix every passage was flagged for an added number. Books 1–5 have no entry markers, so their results are unchanged.
2. The back-translations of rendering A for the two longest book prefaces (6.1.1 and 11.1.1) ran past the 16,000-token output limit and came back cut off; those two were sent again with a 32,000-token limit, same prompt, model and settings.
3. The second judge draw judged all 6,810 items again, as in books 1–5, so the gate and the item verdicts come from the same run.

One model family translates, back-translates and judges, so the checks share lineage with the translators.
