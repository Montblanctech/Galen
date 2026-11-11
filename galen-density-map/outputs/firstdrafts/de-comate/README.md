# Galen, *De comate secundum Hippocratem* (On Coma according to Hippocrates) — machine first draft v0.1, cycle 4 (2026-11-11)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No English translation found. Spanish: J. M. Nieto Ibáñez 2005. Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and literature checks on 2026-11-10 and 2026-11-11). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/de-comate/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged; cycle 4 note `firstdrafts_v02_cycle4_note.md`; check (c) under judge v0.3, `firstdrafts_v03_judge_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg052.1st1K-grc1 (Kühn 1824, vol. 7 pp. 643-665; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn VII 643–665.
- `units.py`: **23 units** (one Kühn page snapped back to the preceding sentence end; 22 units span two pages, 1 one), **3,258 Greek words**, 72–187 words per unit (median 148); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 0.98%). 0 book(s), 4 chapter(s) in the TEI.
- Targets: **175** NOUN/ADJ tokens (every punch-list token first, 52; then four-way `genuinely_hard` tokens rarest-first, 123; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **174 (99.4%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤1.69 low, ≤2.14 mid, above high; 8/8/7 units).

## Renderings (`translate.py api`, batch mode (Message Batches), `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). Sent as one Message Batch per stage (one request per unit), prompt SHA-256 on every row.
- Output: **A 23/23 units rendered** (4,662 English words; refusals 0, errors left 0), **B 23/23** (4,583 words; refusals 0, errors left 0). Page markers reproduced: A 23, B 22 of 23 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 20 of 23 units anchored, B: 19 of 23), then length-based beads inside each segment (A 1:1 90, 2:1 36, 1:2 2, Greek sentences with no English bead 3; B 88 / 30 / 18 / 1). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 175 rows; both renderings reported a rendering for 175 targets. Self-flagged `uncertain`: A 4, B 8. Term memory consistency (information, never enforced): A 76/90 (84.44%), B 74/90 (82.22%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (batch mode; 23 requests for A, 23 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **22 of 23 units pass, 1 fail** (95.7%, Wilson 95% 79.01–99.23); not run or n/a: 0. Mean term-lemma recall A 0.781, B 0.819; mean content-lemma recall A 0.639, B 0.619. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **131 of 175 targets agree (74.86%, Wilson 95% 67.94–80.7)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 41/52 = 78.85%; four-way-only targets 90/123 = 73.17%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **14 of 23 units pass, 9 fail** (60.9%, Wilson 95% 40.79–77.84); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.047 (n = 23).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 368 items (348 real: both renderings of the 174 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261111, judged by `claude-sonnet-5-5` in 37 groups of 10 with the whole LSJ entry (54–28968 characters, median 421); 71 anchor candidates passed the validator, 59 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 19/20.** Misses (control kind, expected → got, the control's English): plant `sleepy` out_of_range → in_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 22 units and failed 1. These figures are not used.
- Item level: A in range 164, out of range 10, unsure 0; B 163 / 9 / 2.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 14 units · mixed: 8 · fail: 1 · insufficient: 0** — failed: K7.652-653. Mixed: K7.643-644, K7.649-650, K7.651-652, K7.654-655, K7.655-656, K7.660-661, K7.662-663, K7.664-665.
- By difficulty tier: low 5 pass / 2 mixed / 1 fail; mid 6 pass / 2 mixed / 0 fail; high 3 pass / 4 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/de-comate/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.

## The judge gate failed by one control, and the control was at fault
Check (c) under judge v0.3 got 19 of 20 controls. The miss is a plant: the rendering *sleepy*, taken from another target, was shown for νωθρά in ἡ πρὸς Ἱπποκράτους λεγομένη νωθρὰ καταφορά, and the judge said in_range. LSJ glosses καταφορὴ νωθρά as 'falling into a heavy sleep', so the judge was right and the plant was not a wrong rendering. By the rule fixed before the run, the gate counts as failed and check (c) is reported unused for this work; the unit verdicts above use (a) and (b) only. Plants that share a stem with the target's LSJ glosses (here *sleepy* and *sleep*) will be excluded in the next version of the judge; that change is not applied here after the fact.
