# Galen, *De compositione medicamentorum per genera* (On the Composition of Drugs by Kind) — machine first draft v0.2, cycle 2 (run 2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No complete translation in any modern language. Parts exist in English: G. Baker 1574 (book 3, from a French epitome), M. Marai 2023 (substantial excerpts, Warwick PhD thesis) and ten reference passages (galen_project, 2026). Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and a literature check on 2026-11-10). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/comp-per-genera/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Calibration against a human translation (check d, pre-registered)
Before the full run, both renderings of the 33 units that hold the ten passages Manuela Marai translated for the galen_project (CC BY 4.0; `reference/`) were compared with her English, target by target: a target agrees when a content word of the rendering occurs in her passage. Rendering A agrees on 87 of 137 targets (63.5%, Wilson 95% 55.18–71.09); rendering B on 91 of 137 (66.42%, 58.16–73.79). The spec's expectation was at least 60% and its halt line 40%: both met the expectation, and the run went on. The comparison is lenient by construction (whole passage, any content word), so the disagreement it finds is a floor. Per passage: `checks_calibration.json`.

## Source and units
- Greek: First1KGreek tlg0057.tlg077.1st1K-grc1 (Kühn 1827, vol. 13 pp. 362-1058, seven books; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn XIII 362–1058.
- `units.py`: **697 units** (one Kühn page snapped back to the preceding sentence end; 607 units span two pages, 90 one), **104,760 Greek words**, 38–241 words per unit (median 154); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 1.26%). 7 book(s), 113 chapter(s) in the TEI.
- Targets: **5,476** NOUN/ADJ tokens (every punch-list token first, 3737; then four-way `genuinely_hard` tokens rarest-first, 1739; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **5,350 (97.7%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤3.66 low, ≤6.29 mid, above high; 234/232/231 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 697/697 units rendered** (141,459 English words; refusals 0, errors left 0), **B 697/697** (138,562 words; refusals 0, errors left 0). Page markers reproduced: A 694, B 692 of 697 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 663 of 697 units anchored, B: 619 of 697), then length-based beads inside each segment (A 1:1 2058, 2:1 2497, 1:2 27, Greek sentences with no English bead 4216; B 2237 / 2453 / 243 / 3909). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 5,476 rows; both renderings reported a rendering for 5,476 targets. Self-flagged `uncertain`: A 57, B 131. Term memory consistency (information, never enforced): A 4041/4285 (94.31%), B 4031/4290 (93.96%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 697 calls for A, 698 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **663 of 692 units pass, 29 fail** (95.8%, Wilson 95% 94.05–97.07); not run or n/a: 5. Mean term-lemma recall A 0.8, B 0.795; mean content-lemma recall A 0.621, B 0.612. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **4,259 of 5,476 targets agree (77.78%, Wilson 95% 76.66–78.86)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 2933/3737 = 78.49%; four-way-only targets 1326/1739 = 76.25%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **502 of 697 units pass, 195 fail** (72.0%, Wilson 95% 68.58–75.23); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = 0.022 (n = 697).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 10,720 items (10,700 real: both renderings of the 5,350 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 1072 groups of 10 with the whole LSJ entry (12–16384 characters, median 301); 4576 anchor candidates passed the validator, 697 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 12/20.** Misses (control kind, expected → got, the control's English): plant `herbs` out_of_range → missing; anchor `shedding` in_range → out_of_range; anchor `of the date-palm` in_range → unsure; anchor `somewhat wet` in_range → out_of_range; plant `henna oil` out_of_range → missing; plant `resin` out_of_range → missing; anchor `previous to` in_range → missing; plant `declines` out_of_range → missing.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 297 units and failed 400. These figures are not used.
- Item level: A in range 4052, out of range 177, unsure 67; B 4039 / 193 / 43.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 478 units · mixed: 206 · fail: 9 · insufficient: 4** — failed: K13.394-395, K13.399-400, K13.478-479, K13.509, K13.710-711, K13.763-764, K13.777, K13.890-891, K13.947-948. 206 mixed units are listed in `checks.json`. Insufficient (a rendering or a check missing): K13.717, K13.756-757, K13.759-760, K13.871-872.
- By difficulty tier: low 157 pass / 71 mixed / 5 fail; mid 162 pass / 64 mixed / 3 fail; high 159 pass / 71 mixed / 1 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/comp-per-genera/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.

## Check (c) re-run under judge v0.3 (2026-11-11)
The v0.2 judge gate failed (12/20), and the v0.2 results above report check (c) as unused. Its anchors (LSJ's first-sense gloss) were often wrong in Galen's sentence, so the gate was testing the controls, not the judge. Under judge v0.3 (`firstdrafts_v03_judge_note.md`, committed before any v0.3 call: anchors are targets whose two renderings agree and are attested in the entry; unanswered items are asked once more; prompt, model, plants, gate and thresholds unchanged; seed 20261111) **the gate passed, 20/20**. Items judged in range: rendering A 5048 of 5350, rendering B 5050 of 5350. Check (c) per unit: 646 pass, 51 fail. **Unit verdicts now** (fail = fails two of the three checks): 661 pass, 1 mixed, 35 fail; under v0.2, with (c) unused: 478 pass, 206 mixed, 9 fail, 4 insufficient. These supersede the v0.2 unit verdicts above; the page's red rules follow the new verdicts. The v0.2 judge files are kept in `judge_v02/`. Limit, stated before the run: v0.3 anchors come from items where the two translators agree, so they cannot show a judge that trusts agreement; the plants, all answered correctly, are what show the judge does not say in_range to everything.
