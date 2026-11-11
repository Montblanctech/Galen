# Galen, *De totius morbi temporibus* (On the Periods of the Whole Disease) — machine first draft v0.1, cycle 3 (2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No translation in any modern language found. Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and a literature check on 2026-11-10). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/morbi-temporibus/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg047.1st1K-grc1 (Kühn 1824, vol. 7 pp. 440-462; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn VII 440–462.
- `units.py`: **23 units** (one Kühn page snapped back to the preceding sentence end; 19 units span two pages, 4 one), **3,545 Greek words**, 61–211 words per unit (median 158); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 1.07%). 0 book(s), 8 chapter(s) in the TEI.
- Targets: **166** NOUN/ADJ tokens (every punch-list token first, 81; then four-way `genuinely_hard` tokens rarest-first, 85; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **159 (95.8%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤1.94 low, ≤3.25 mid, above high; 8/8/7 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 23/23 units rendered** (4,815 English words; refusals 0, errors left 0), **B 23/23** (4,774 words; refusals 0, errors left 0). Page markers reproduced: A 23, B 23 of 23 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 20 of 23 units anchored, B: 16 of 23), then length-based beads inside each segment (A 1:1 89, 2:1 3, 1:2 4, Greek sentences with no English bead 0; B 45 / 3 / 48 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 166 rows; both renderings reported a rendering for 166 targets. Self-flagged `uncertain`: A 4, B 4. Term memory consistency (information, never enforced): A 41/49 (83.67%), B 38/50 (76.0%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 23 calls for A, 23 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **22 of 23 units pass, 1 fail** (95.7%, Wilson 95% 79.01–99.23); not run or n/a: 0. Mean term-lemma recall A 0.76, B 0.742; mean content-lemma recall A 0.634, B 0.624. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **131 of 166 targets agree (78.92%, Wilson 95% 72.09–84.43)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 64/81 = 79.01%; four-way-only targets 67/85 = 78.82%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **16 of 23 units pass, 7 fail** (69.6%, Wilson 95% 49.13–84.4); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = 0.011 (n = 23).

### (c) LSJ-anchored term check, salted judge — gate passed
- 338 items (318 real: both renderings of the 159 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 34 groups of 10 with the whole LSJ entry (14–11012 characters, median 656); 123 anchor candidates passed the validator, 35 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 20/20.** All controls were judged as planted.
- Unit level (pass = share `in_range` ≥ 0.80 and at most 2 `out_of_range`): **20 of 23 units pass, 3 fail** (87.0%, Wilson 95% 67.87–95.46); n/a: 0.
- Item level: A in range 145, out of range 9, unsure 5; B 148 / 9 / 2.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks.
- **pass: 23 units · mixed: 0 · fail: 0 · insufficient: 0**.
- By difficulty tier: low 8 pass / 0 mixed / 0 fail; mid 8 pass / 0 mixed / 0 fail; high 7 pass / 0 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/morbi-temporibus/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
