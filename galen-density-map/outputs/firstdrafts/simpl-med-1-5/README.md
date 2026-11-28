# Galen, *De simplicium medicamentorum temperamentis ac facultatibus* (On the Mixtures and Powers of Simple Drugs), books 1–5 — machine first draft v0.1

**What this is.** The first half of the Simple Drugs drafts in *Galen First Drafts*: a machine translation of books 1–5, the theory of drug powers, with the Greek beside it. Books 6–11 are in `../simpl-med-6-11/`; both halves are on one work page, `docs/first-drafts/simpl-med/`, one page per book. Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these drafts. They are for reading and for correction, not for quotation. The banner says so on every page; the apparatus says where to look, not that the text is right.

**Earlier translations we know of.** An English translation of books 1–5 by J. Wilkins is announced in the Cambridge Galen Translations. All eleven books: a free French version by H. Fayard (1548). An unreviewed machine translation into English of Kühn XI, the volume containing these books, was posted at Source Library (sourcelibrary.org) during 2026. The drafts were translated from the Greek alone.

## Source and units
- Greek: C. G. Kühn, *Claudii Galeni Opera Omnia* vol. XI pp. 379–789 (Leipzig 1826), First1KGreek `urn:cts:greekLit:tlg0057.tlg075.1st1K-grc1`, CC BY-SA 4.0. Config: `pipeline/firstdrafts/configs/simpl-med-1-5.json`.
- **410 passages** cut at Kühn pages (ids `K11.<page>`), **62,869 Greek words**, **3,075 target words** chosen by the fixed rule from LSJ coverage and word frequency.

## Renderings
Each passage translated twice, independently, from the same neutral prompt as the other works, with no glossary and a fresh context: rendering A by `claude-fable-5-1`, rendering B by `claude-opus-5-5`, through the batch API. Files: `requests.jsonl` (with `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`. The two renderings are aligned sentence by sentence with the Greek (`alignment.json`). The back-translations and the judge runs below were made through the Claude Code command-line tool, which adds a fixed preamble of its own to every prompt.

## Checks (thresholds fixed before the run, `firstdrafts_v02_spec.md`; judge `firstdrafts_v03_judge_note.md`)
- (a) Back-translation into Greek by `claude-sonnet-5-5`: 390 of 410 passages pass for A (95.1%), 394 for B (96.1%); **385 pass for both (93.9%, 95% interval 91.2–95.8)**. Files: `bt_requests_*.jsonl`, `backtranslation_*.jsonl`.
- (b) Agreement of A and B on the target words: **2,503 of 3,075 (81.4%)**; 330 of 408 passages meet the 70% rule.
- (c) Judge shown the whole LSJ entry of each target word, salted with 10 planted errors and 10 controls. The pre-registered run (seed 20261109) **failed its control gate, 19 of 20**, when the judge rejected one valid control, so by the rule fixed in advance its verdicts were not used; it is kept unchanged in `judge_v03_run1_seed20261109/`. A second draw of the controls (seed 20261127, nothing else changed; `JUDGE_REPAIR_NOTE.md`, written before any call of that run) **passed 20 of 20**; on it 393 of 408 passages pass (96.3%), and 96.2% of A's and 96.4% of B's judged words fall within the LSJ entry. A pass on a second draw is weaker evidence than a pass on the original draw. Files: `judge_sheet*.jsonl`, `judge_requests.jsonl`, `judge_group_answers*.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- **Verdicts on (a)–(c): 396 passages pass, 12 fail, 2 cannot be scored**; all are kept (`checks.json`, `term_table.csv`).
- Flags, places for a reader to look, not confirmed errors: the fidelity check (numbers, negations, more/less) flags 68 of 2,273 sentence pairs in A and 132 of 2,356 in B (`fidelity_A.json`, `fidelity_B.json`); the names check (drug names and body parts added or missing) flags 111 pairs in A (48.8 per 1,000) and 92 in B (39.0) (`names_A.json`, `names_B.json`). They play no part in the verdicts.

One model family translates, back-translates and judges, so the checks share lineage with the translators.
