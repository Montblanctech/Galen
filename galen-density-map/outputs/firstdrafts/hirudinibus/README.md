# Galen, *De hirudinibus, revulsione, cucurbitula, incisione et scarificatione* (On Leeches, Revulsion, Cupping, Incision and Scarification) — machine first draft v0.1, cycle 3 (2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No earlier English translation found. Italian: G. Ecca 2021 (complete). French: Bussemaker and Daremberg 1854, for the passages of Oribasius it is compiled from. Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and a literature check on 2026-11-10). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/hirudinibus/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg071.1st1K-grc1 (Kühn 1826, vol. 11 pp. 317-322; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn XI 317–322.
- `units.py`: **6 units** (one Kühn page snapped back to the preceding sentence end; 5 units span two pages, 1 one), **704 Greek words**, 62–161 words per unit (median 143); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 1.85%). 0 book(s), 4 chapter(s) in the TEI.
- Targets: **42** NOUN/ADJ tokens (every punch-list token first, 18; then four-way `genuinely_hard` tokens rarest-first, 24; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **41 (97.6%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤0.7 low, ≤4.42 mid, above high; 3/2/1 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 6/6 units rendered** (1,075 English words; refusals 0, errors left 0), **B 6/6** (1,045 words; refusals 0, errors left 0). Page markers reproduced: A 6, B 6 of 6 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 6 of 6 units anchored, B: 6 of 6), then length-based beads inside each segment (A 1:1 31, 2:1 6, 1:2 0, Greek sentences with no English bead 0; B 33 / 5 / 0 / 0). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 42 rows; both renderings reported a rendering for 42 targets. Self-flagged `uncertain`: A 3, B 2. Term memory consistency (information, never enforced): A 4/4 (100.0%), B 4/4 (100.0%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 6 calls for A, 6 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **6 of 6 units pass, 0 fail** (100.0%, Wilson 95% 60.97–100.0); not run or n/a: 0. Mean term-lemma recall A 0.702, B 0.744; mean content-lemma recall A 0.576, B 0.583. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **37 of 42 targets agree (88.1%, Wilson 95% 75.0–94.81)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 18/18 = 100.0%; four-way-only targets 19/24 = 79.17%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **5 of 6 units pass, 1 fail** (83.3%, Wilson 95% 43.65–96.99); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.501 (n = 6).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 102 items (82 real: both renderings of the 41 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 11 groups of 10 with the whole LSJ entry (89–4184 characters, median 522); 34 anchor candidates passed the validator, 7 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 16/20.** Misses (control kind, expected → got, the control's English): anchor `that which flows` in_range → out_of_range; anchor `of good name` in_range → out_of_range; anchor `liable to discharge blood` in_range → out_of_range; anchor `holding together` in_range → out_of_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 6 units and failed 0. These figures are not used.
- Item level: A in range 40, out of range 1, unsure 0; B 40 / 1 / 0.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 5 units · mixed: 1 · fail: 0 · insufficient: 0**. Mixed: K11.321-322.
- By difficulty tier: low 2 pass / 1 mixed / 0 fail; mid 2 pass / 0 mixed / 0 fail; high 1 pass / 0 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/hirudinibus/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
