# Galen, *Quos quibus catharticis medicamentis et quando purgare oporteat* (Whom to Purge, with Which Cathartic Drugs, and When) — machine first draft v0.1, cycle 3 (2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise that has no modern-language translation (census `phase1/galen_ogl_census.csv`, `translation_status = none`; see `translation_source` there for the Galenus verbatim / Fichtner evidence). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/quos-quibus/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg073.1st1K-grc1 (Kühn 1826, vol. 11 pp. 343-356; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; First1KGreek also has tlg073.1st1K-grc2, the Oribasius excerpt of the same work (Kühn XI 343-356 ap. Oribasium, with Latin and German), not used here; Kühn XI 343–356.
- `units.py`: **14 units** (one Kühn page snapped back to the preceding sentence end; 12 units span two pages, 2 one), **1,999 Greek words**, 61–175 words per unit (median 152); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 1.50%). 0 book(s), 1 chapter(s) in the TEI.
- Targets: **101** NOUN/ADJ tokens (every punch-list token first, 37; then four-way `genuinely_hard` tokens rarest-first, 64; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **100 (99.0%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤0.68 low, ≤3.09 mid, above high; 5/5/4 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 14/14 units rendered** (2,728 English words; refusals 0, errors left 0), **B 14/14** (2,646 words; refusals 0, errors left 0). Page markers reproduced: A 14, B 14 of 14 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 14 of 14 units anchored, B: 14 of 14), then length-based beads inside each segment (A 1:1 81, 2:1 3, 1:2 0, Greek sentences with no English bead 0; B 78 / 1 / 7 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 101 rows; both renderings reported a rendering for 101 targets. Self-flagged `uncertain`: A 2, B 3. Term memory consistency (information, never enforced): A 12/14 (85.71%), B 11/14 (78.57%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 14 calls for A, 14 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **11 of 14 units pass, 3 fail** (78.6%, Wilson 95% 52.41–92.43); not run or n/a: 0. Mean term-lemma recall A 0.681, B 0.702; mean content-lemma recall A 0.647, B 0.627. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **83 of 101 targets agree (82.18%, Wilson 95% 73.58–88.42)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 30/37 = 81.08%; four-way-only targets 53/64 = 82.81%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **11 of 14 units pass, 3 fail** (78.6%, Wilson 95% 52.41–92.43); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.392 (n = 14).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 220 items (200 real: both renderings of the 100 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 22 groups of 10 with the whole LSJ entry (41–5476 characters, median 487); 82 anchor candidates passed the validator, 17 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 16/20.** Misses (control kind, expected → got, the control's English): anchor `snub-nosed` in_range → out_of_range; anchor `soul` in_range → out_of_range; anchor `bringing to` in_range → out_of_range; anchor `apph` in_range → out_of_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 10 units and failed 4. These figures are not used.
- Item level: A in range 90, out of range 8, unsure 2; B 91 / 8 / 1.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 9 units · mixed: 4 · fail: 1 · insufficient: 0** — failed: K11.343. Mixed: K11.348-349, K11.352-353, K11.354-355, K11.355-356.
- By difficulty tier: low 2 pass / 2 mixed / 1 fail; mid 3 pass / 2 mixed / 0 fail; high 4 pass / 0 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/quos-quibus/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
