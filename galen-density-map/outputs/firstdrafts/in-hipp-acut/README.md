# Galen, *In Hippocratis De victu acutorum commentaria, libri II–IV* (Commentary on Hippocrates' Regimen in Acute Diseases, Books II–IV) — machine first draft v0.1, cycle 4 (2026-11-11)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No English translation of books II–IV found. Book I: French, J. Pietrobelli 2019 (Les Belles Lettres). Book II chapters 20–23: German excerpt, W. Müri 1979. Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and literature checks on 2026-11-10 and 2026-11-11). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/in-hipp-acut/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged; cycle 4 note `firstdrafts_v02_cycle4_note.md`; check (c) under judge v0.3, `firstdrafts_v03_judge_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg087.1st1K-grc1 (Kühn 1828, vol. 15 pp. 418-919, four books; this draft: books II-IV, pp. 515-919; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn XV 515–919.
- `units.py`: **405 units** (one Kühn page snapped back to the preceding sentence end; 334 units span two pages, 71 one), **54,030 Greek words** in the drafted books (67,039 in the whole TEI file, book I included), 27–252 words per unit (median 134); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 0.65%). 3 book(s), 218 chapter(s) in the TEI.
- Targets: **2,820** NOUN/ADJ tokens (every punch-list token first, 953; then four-way `genuinely_hard` tokens rarest-first, 1867; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **2,762 (97.9%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤1.11 low, ≤2.59 mid, above high; 136/135/134 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 405/405 units rendered** (75,388 English words; refusals 0, errors left 0), **B 405/405** (74,068 words; refusals 0, errors left 0). Page markers reproduced: A 398, B 402 of 405 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 353 of 405 units anchored, B: 305 of 405), then length-based beads inside each segment (A 1:1 1364, 2:1 70, 1:2 118, Greek sentences with no English bead 0; B 979 / 71 / 500 / 1). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 2,820 rows; both renderings reported a rendering for 2,820 targets. Self-flagged `uncertain`: A 54, B 123. Term memory consistency (information, never enforced): A 1550/1789 (86.64%), B 1540/1785 (86.27%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 405 calls for A, 405 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **332 of 398 units pass, 66 fail** (83.4%, Wilson 95% 79.45–86.75); not run or n/a: 7. Mean term-lemma recall A 0.708, B 0.689; mean content-lemma recall A 0.612, B 0.597. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **2,203 of 2,820 targets agree (78.12%, Wilson 95% 76.56–79.61)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 772/953 = 81.01%; four-way-only targets 1431/1867 = 76.65%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **293 of 404 units pass, 111 fail** (72.5%, Wilson 95% 67.98–76.65); n/a (no target with both renderings): 1.
- Density vs disagreement across units: Spearman ρ = -0.031 (n = 404).

### (c) LSJ-anchored term check, salted judge — gate passed
- 5,544 items (5,524 real: both renderings of the 2,762 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261111, judged by `claude-sonnet-5-5` in 555 groups of 10 with the whole LSJ entry (14–14942 characters, median 580); 1470 anchor candidates passed the validator, 692 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 20/20.** All controls were judged as planted.
- Unit level (pass = share `in_range` ≥ 0.80 and at most 2 `out_of_range`): **378 of 404 units pass, 26 fail** (93.6%, Wilson 95% 90.74–95.57); n/a: 1.
- Item level: A in range 2612, out of range 119, unsure 31; B 2616 / 117 / 29.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks.
- **pass: 366 units · mixed: 1 · fail: 37 · insufficient: 1** — failed: K15.516-517, K15.536-537, K15.537-538, K15.544, K15.549, K15.573-574, K15.578-579, K15.587-588, K15.614-615, K15.616-617, K15.620-621, K15.624, K15.644-645, K15.648-649, K15.672-673, K15.687-688, K15.695-696, K15.698-699, K15.701-702, K15.706-707, K15.739-740, K15.753, K15.759-760, K15.770-771, K15.778, K15.778-779, K15.780-781, K15.801-802, K15.823-824, K15.831-832, K15.851-852, K15.859, K15.861-862, K15.865-866, K15.897-898, K15.908, K15.918-919. Mixed: K15.561-562. Insufficient (a rendering or a check missing): K15.570.
- By difficulty tier: low 121 pass / 0 mixed / 14 fail; mid 119 pass / 1 mixed / 15 fail; high 126 pass / 0 mixed / 8 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/in-hipp-acut/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
