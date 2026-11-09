# Galen, *De purgantium medicamentorum facultate* (On the Power of Purgative Drugs) — machine first draft v0.1, cycle 3 (2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise that has no modern-language translation (census `phase1/galen_ogl_census.csv`, `translation_status = none`; see `translation_source` there for the Galenus verbatim / Fichtner evidence). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/purgantium-facultate/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg072.1st1K-grc1 (Kühn 1826, vol. 11 pp. 323-342; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn XI 323–342.
- `units.py`: **20 units** (one Kühn page snapped back to the preceding sentence end; 15 units span two pages, 5 one), **2,980 Greek words**, 70–178 words per unit (median 154); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 0.81%). 0 book(s), 5 chapter(s) in the TEI.
- Targets: **158** NOUN/ADJ tokens (every punch-list token first, 48; then four-way `genuinely_hard` tokens rarest-first, 110; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **156 (98.7%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤1.36 low, ≤1.85 mid, above high; 7/7/6 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 and usage on every row.
- Output: **A 20/20 units rendered** (4,132 English words; refusals 0, errors left 0), **B 20/20** (4,100 words; refusals 0, errors left 0). Page markers reproduced: A 20, B 20 of 20 units.
- Cost (`usage.jsonl`, list prices): rendering A $3.00 (20 calls), rendering B $1.01 (20 calls), back-translation $0.79 (40 calls), judge $1.01 (34 calls); **total $5.82** against the pre-run proxy estimate of $6.31 (`cost_estimate.json`; $1.95 per 1,000 Greek words).

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 20 of 20 units anchored, B: 20 of 20), then length-based beads inside each segment (A 1:1 104, 2:1 8, 1:2 2, Greek sentences with no English bead 0; B 94 / 5 / 18 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 158 rows; both renderings reported a rendering for 158 targets. Self-flagged `uncertain`: A 0, B 7. Term memory consistency (information, never enforced): A 35/47 (74.47%), B 36/47 (76.6%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 20 calls for A, 20 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **19 of 20 units pass, 1 fail** (95.0%, Wilson 95% 76.39–99.11); not run or n/a: 0. Mean term-lemma recall A 0.702, B 0.711; mean content-lemma recall A 0.615, B 0.603. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **111 of 158 targets agree (70.25%, Wilson 95% 62.71–76.83)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 36/48 = 75.0%; four-way-only targets 75/110 = 68.18%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **9 of 20 units pass, 11 fail** (45.0%, Wilson 95% 25.82–65.79); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.125 (n = 20).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 332 items (312 real: both renderings of the 156 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 34 groups of 10 with the whole LSJ entry (14–10106 characters, median 701); 135 anchor candidates passed the validator, 19 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 16/20.** Misses (control kind, expected → got, the control's English): anchor `noxious` in_range → out_of_range; anchor `mud` in_range → out_of_range; anchor `argument of disproof or refutation` in_range → out_of_range; anchor `pasture` in_range → out_of_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 20 units and failed 0. These figures are not used.
- Item level: A in range 148, out of range 6, unsure 2; B 150 / 4 / 2.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 9 units · mixed: 10 · fail: 1 · insufficient: 0** — failed: K11.334-335. Mixed: K11.323, K11.326-327, K11.329, K11.329-330, K11.330-331, K11.333-334, K11.336, K11.336-337, K11.337-338, K11.339-340.
- By difficulty tier: low 2 pass / 5 mixed / 0 fail; mid 3 pass / 3 mixed / 1 fail; high 4 pass / 2 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `cost_estimate.json`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `usage.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/purgantium-facultate/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
