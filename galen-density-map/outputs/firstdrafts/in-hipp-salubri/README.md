# Galen, *In Hippocratis vel Polybi opus De salubri victus ratione privatorum commentarius* (Commentary on Hippocrates' (or Polybus') Regimen in Health for Private Persons) — machine first draft v0.1, cycle 3 (2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no translation in any modern language found (census `phase1/galen_ogl_census.csv`, `translation_status`, `translation_source`, `translation_note`; checked against catalogues, publishers and theses in `drafts/prior_translation_check.md`). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/in-hipp-salubri/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg086.1st1K-grc1 (Kühn 1828, vol. 15 pp. 174-223; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn XV 174–223.
- `units.py`: **51 units** (one Kühn page snapped back to the preceding sentence end; 34 units span two pages, 17 one), **6,840 Greek words**, 48–189 words per unit (median 135); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 4.34%). 0 book(s), 34 chapter(s) in the TEI.
- Targets: **311** NOUN/ADJ tokens (every punch-list token first, 76; then four-way `genuinely_hard` tokens rarest-first, 235; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **307 (98.7%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤0.68 low, ≤1.4 mid, above high; 19/16/16 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 51/51 units rendered** (9,091 English words; refusals 0, errors left 0), **B 51/51** (8,935 words; refusals 0, errors left 0). Page markers reproduced: A 51, B 50 of 51 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 50 of 51 units anchored, B: 47 of 51), then length-based beads inside each segment (A 1:1 229, 2:1 49, 1:2 1, Greek sentences with no English bead 0; B 240 / 40 / 8 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 311 rows; both renderings reported a rendering for 311 targets. Self-flagged `uncertain`: A 12, B 17. Term memory consistency (information, never enforced): A 88/105 (83.81%), B 89/105 (84.76%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 51 calls for A, 51 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **45 of 51 units pass, 6 fail** (88.2%, Wilson 95% 76.62–94.5); not run or n/a: 0. Mean term-lemma recall A 0.724, B 0.718; mean content-lemma recall A 0.555, B 0.549. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **241 of 311 targets agree (77.49%, Wilson 95% 72.53–81.78)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 64/76 = 84.21%; four-way-only targets 177/235 = 75.32%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **36 of 51 units pass, 15 fail** (70.6%, Wilson 95% 57.0–81.29); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.043 (n = 51).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 634 items (614 real: both renderings of the 307 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 64 groups of 10 with the whole LSJ entry (14–16910 characters, median 733); 258 anchor candidates passed the validator, 43 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 17/20.** Misses (control kind, expected → got, the control's English): anchor `flowing through` in_range → out_of_range; anchor `cleansing from guilt or defilement` in_range → out_of_range; anchor `delimitation` in_range → out_of_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 45 units and failed 6. These figures are not used.
- Item level: A in range 287, out of range 15, unsure 5; B 285 / 21 / 1.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 32 units · mixed: 17 · fail: 2 · insufficient: 0** — failed: K15.216-217, K15.221. Mixed: K15.174, K15.174-175, K15.178, K15.182-183, K15.188, K15.188-189, K15.191, K15.193, K15.197-198, K15.198-199, K15.201-202, K15.207-208, K15.212, K15.215-216, K15.218, K15.218-219, K15.220.
- By difficulty tier: low 10 pass / 8 mixed / 1 fail; mid 9 pass / 7 mixed / 0 fail; high 13 pass / 2 mixed / 1 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/in-hipp-salubri/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
