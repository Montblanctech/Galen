# Galen, *Adversus eos qui de typis scripserunt vel de circuitibus* (Against Those Who Wrote on Types or on Periods (of Fever)) — machine first draft v0.1, cycle 4 (2026-11-11)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No English translation found. Spanish: E. García Sola 2010. Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and literature checks on 2026-11-10 and 2026-11-11). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/adversus-typos/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged; cycle 4 note `firstdrafts_v02_cycle4_note.md`; check (c) under judge v0.3, `firstdrafts_v03_judge_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg049.1st1K-grc1 (Kühn 1824, vol. 7 pp. 475-512; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn VII 475–512.
- `units.py`: **38 units** (one Kühn page snapped back to the preceding sentence end; 35 units span two pages, 3 one), **5,611 Greek words**, 52–218 words per unit (median 158); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 0.71%). 0 book(s), 7 chapter(s) in the TEI.
- Targets: **273** NOUN/ADJ tokens (every punch-list token first, 64; then four-way `genuinely_hard` tokens rarest-first, 209; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **263 (96.3%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤0.63 low, ≤1.67 mid, above high; 13/13/12 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 38/38 units rendered** (7,565 English words; refusals 0, errors left 0), **B 38/38** (7,530 words; refusals 0, errors left 0). Page markers reproduced: A 38, B 38 of 38 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 33 of 38 units anchored, B: 35 of 38), then length-based beads inside each segment (A 1:1 167, 2:1 12, 1:2 11, Greek sentences with no English bead 0; B 156 / 7 / 32 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 273 rows; both renderings reported a rendering for 273 targets. Self-flagged `uncertain`: A 6, B 12. Term memory consistency (information, never enforced): A 131/153 (85.62%), B 136/153 (88.89%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 38 calls for A, 38 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **35 of 36 units pass, 1 fail** (97.2%, Wilson 95% 85.83–99.51); not run or n/a: 2. Mean term-lemma recall A 0.769, B 0.739; mean content-lemma recall A 0.623, B 0.605. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **217 of 273 targets agree (79.49%, Wilson 95% 74.3–83.85)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 52/64 = 81.25%; four-way-only targets 165/209 = 78.95%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **30 of 38 units pass, 8 fail** (78.9%, Wilson 95% 63.65–88.93); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.18 (n = 38).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 546 items (526 real: both renderings of the 263 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261111, judged by `claude-sonnet-5-5` in 55 groups of 10 with the whole LSJ entry (14–11867 characters, median 683); 125 anchor candidates passed the validator, 84 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 19/20.** Misses (control kind, expected → got, the control's English): plant `twenty-four (four and twenty)` out_of_range → in_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 34 units and failed 4. These figures are not used.
- Item level: A in range 247, out of range 14, unsure 2; B 245 / 15 / 3.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 28 units · mixed: 7 · fail: 1 · insufficient: 2** — failed: K7.501-502. Mixed: K7.483-484, K7.486-487, K7.489-490, K7.494-495, K7.498-499, K7.500-501, K7.507-508. Insufficient (a rendering or a check missing): K7.506-507, K7.509-510.
- By difficulty tier: low 9 pass / 3 mixed / 0 fail; mid 11 pass / 1 mixed / 0 fail; high 8 pass / 3 mixed / 1 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/adversus-typos/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.

## The judge gate failed by one control, and the judge was at fault
Check (c) under judge v0.3 got 19 of 20 controls. The miss is a plant: the rendering *twenty-four (four and twenty)*, taken from another target, was shown for κέρδος ('gain, profit'), and the judge answered in_range although its own note says the rendering is mismatched. That is a judge error, and the gate exists to catch it. By the pre-registered rule, check (c) is reported unused for this work; the unit verdicts above use (a) and (b) only.
