# Galen, *De plenitudine* (On Plethora) — machine first draft v0.1, cycle 4 (2026-11-11)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No English translation found. German: C. Otte 2001 (edition with translation). Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and literature checks on 2026-11-10 and 2026-11-11). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/de-plenitudine/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged; cycle 4 note `firstdrafts_v02_cycle4_note.md`; check (c) under judge v0.3, `firstdrafts_v03_judge_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg050.1st1K-grc1 (Kühn 1824, vol. 7 pp. 513-583; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn VII 513–583.
- `units.py`: **71 units** (one Kühn page snapped back to the preceding sentence end; 66 units span two pages, 5 one), **11,096 Greek words**, 79–289 words per unit (median 159); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 0.87%). 0 book(s), 11 chapter(s) in the TEI.
- Targets: **525** NOUN/ADJ tokens (every punch-list token first, 190; then four-way `genuinely_hard` tokens rarest-first, 335; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **508 (96.8%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤1.16 low, ≤2.5 mid, above high; 24/24/23 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 71/71 units rendered** (15,339 English words; refusals 0, errors left 0), **B 71/71** (15,090 words; refusals 0, errors left 0). Page markers reproduced: A 70, B 70 of 71 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 59 of 71 units anchored, B: 45 of 71), then length-based beads inside each segment (A 1:1 260, 2:1 5, 1:2 24, Greek sentences with no English bead 0; B 172 / 5 / 112 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 525 rows; both renderings reported a rendering for 525 targets. Self-flagged `uncertain`: A 5, B 17. Term memory consistency (information, never enforced): A 189/228 (82.89%), B 183/230 (79.57%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 71 calls for A, 71 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **54 of 70 units pass, 16 fail** (77.1%, Wilson 95% 66.05–85.41); not run or n/a: 1. Mean term-lemma recall A 0.672, B 0.693; mean content-lemma recall A 0.631, B 0.607. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **416 of 525 targets agree (79.24%, Wilson 95% 75.56–82.49)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 155/190 = 81.58%; four-way-only targets 261/335 = 77.91%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **55 of 70 units pass, 15 fail** (78.6%, Wilson 95% 67.61–86.56); n/a (no target with both renderings): 1.
- Density vs disagreement across units: Spearman ρ = 0.028 (n = 70).

### (c) LSJ-anchored term check, salted judge — gate passed
- 1,036 items (1,016 real: both renderings of the 508 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261111, judged by `claude-sonnet-5-5` in 104 groups of 10 with the whole LSJ entry (14–11462 characters, median 659); 255 anchor candidates passed the validator, 150 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 20/20.** All controls were judged as planted.
- Unit level (pass = share `in_range` ≥ 0.80 and at most 2 `out_of_range`): **66 of 70 units pass, 4 fail** (94.3%, Wilson 95% 86.21–97.76); n/a: 1.
- Item level: A in range 486, out of range 16, unsure 6; B 479 / 23 / 6.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks.
- **pass: 66 units · mixed: 0 · fail: 4 · insufficient: 1** — failed: K7.515-516, K7.519-520, K7.536-537, K7.549-550. Insufficient (a rendering or a check missing): K7.513.
- By difficulty tier: low 21 pass / 0 mixed / 2 fail; mid 22 pass / 0 mixed / 2 fail; high 23 pass / 0 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/de-plenitudine/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
