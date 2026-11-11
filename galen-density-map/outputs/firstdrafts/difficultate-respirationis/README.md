# Galen, *De difficultate respirationis* (On Difficulty of Breathing) — machine first draft v0.1, cycle 3 (2026-11-09)

**What this is.** A work of *Galen First Drafts*: a machine translation of a Galenic treatise with no complete English translation that we know of. Earlier translations: No complete translation in any modern language. One paragraph (Kühn VII 781–782) is in English in A. A. Long 2021. Sources: `phase1/galen_ogl_census.csv` (Fichtner 2023, Galenus verbatim, and a literature check on 2026-11-10). Two language models rendered the Greek independently with the same neutral prompt and no glossary (with the v0.2 term memory as information); the renderings were aligned to the Greek, every target term tied to its LSJ entry, and the three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/difficultate-respirationis/`. Spec: `firstdrafts_v02_spec.md` (thresholds unchanged for cycle 3, `firstdrafts_v02_cycle3_note.md`). Author of the drafts: William Pepperman (Galen Density Project, Montblanc Tech LLC).

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek tlg0057.tlg056.1st1K-grc1 (Kühn 1824, vol. 7 pp. 753-960; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; Kühn VII 753–960.
- `units.py`: **207 units** (one Kühn page snapped back to the preceding sentence end; 189 units span two pages, 18 one), **31,901 Greek words**, 48–273 words per unit (median 153); page breaks kept inline. Aligned to the odyCy token stream of the density map (alignment loss 1.68%). 3 book(s), 51 chapter(s) in the TEI.
- Targets: **1,541** NOUN/ADJ tokens (every punch-list token first, 517; then four-way `genuinely_hard` tokens rarest-first, 1024; cap 8 per unit, proper names and title lines excluded). Dilemma 1.3.15 lemma for each; **1,516 (98.4%) resolve to a Perseus-LSJ entry** (`lsj_index.py`, whole entries).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤1.3 low, ≤2.56 mid, above high; 70/70/67 units).

## Renderings (`translate.py api`, direct mode, `api_backend.py`)
- A = `claude-fable-5-1`, B = `claude-opus-5-5`, effort high, no fallback; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context; the target list by position; a TERM MEMORY block with the same model's earlier renderings of the unit's target lemmas (information, not instruction). One streaming call per unit, per-unit timestamps, prompt SHA-256 on every row.
- Output: **A 207/207 units rendered** (43,042 English words; refusals 0, errors left 0), **B 207/207** (42,629 words; refusals 0, errors left 0). Page markers reproduced: A 203, B 206 of 207 units.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 182 of 207 units anchored, B: 172 of 207), then length-based beads inside each segment (A 1:1 822, 2:1 78, 1:2 51, Greek sentences with no English bead 6; B 686 / 71 / 204 / 3). The alignment is approximate and is used only to show the English sentence next to a term.
- `term_table.csv`: 1,541 rows; both renderings reported a rendering for 1,541 targets. Self-flagged `uncertain`: A 24, B 52. Term memory consistency (information, never enforced): A 905/1005 (90.05%), B 898/1004 (89.44%).

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (direct mode, per-unit timestamps; 207 calls for A, 207 for B), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear in both back-translations.
- **187 of 206 units pass, 19 fail** (90.8%, Wilson 95% 86.04–94.02); not run or n/a: 1. Mean term-lemma recall A 0.737, B 0.72; mean content-lemma recall A 0.637, B 0.62. Per rendering per unit in `checks.json`.

### (b) Rendering agreement A vs B at the term level
- Term level: **1,114 of 1,541 targets agree (72.29%, Wilson 95% 70.0–74.47)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 419/517 = 81.04%; four-way-only targets 695/1024 = 67.87%. Disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **119 of 207 units pass, 88 fail** (57.5%, Wilson 95% 50.68–64.03); n/a (no target with both renderings): 0.
- Density vs disagreement across units: Spearman ρ = -0.283 (n = 207).

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 3,052 items (3,032 real: both renderings of the 1,516 targets with an LSJ entry; 10 validated first-sense anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in 306 groups of 10 with the whole LSJ entry (14–14942 characters, median 501); 1286 anchor candidates passed the validator, 209 first-sense glosses were rejected by it. Key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 15/20.** Misses (control kind, expected → got, the control's English): anchor `that which is sought` in_range → out_of_range; anchor `of the head` in_range → out_of_range; anchor `throbbing of inflamed parts` in_range → out_of_range; anchor `coming to pass` in_range → out_of_range; anchor `twofold` in_range → out_of_range.
- By the pre-registered rule (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts, as in cycles 1 and 2.
- For information only, not pre-registered: applying the unit rule exploratorily would have passed 191 units and failed 16. These figures are not used.
- Item level: A in range 1422, out of range 70, unsure 24; B 1412 / 72 / 32.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass: 108 units · mixed: 91 · fail: 8 · insufficient: 0** — failed: K7.776-777, K7.790-791, K7.807-808, K7.850-851, K7.860-861, K7.864-865, K7.902-903, K7.908-909. 91 mixed units are listed in `checks.json`.
- By difficulty tier: low 23 pass / 43 mixed / 4 fail; mid 39 pass / 27 mixed / 4 fail; high 46 pass / 21 mixed / 0 fail.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Term memory can propagate an early wrong rendering consistently (consistency is reported, never enforced). Kühn's text is the only Greek used; no critical edition was consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. There is no human reference translation for this work, so check (d) of the v0.2 spec does not apply and nothing here was measured against a scholar's English. The judge gate failed, so this work has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_requests.jsonl`, `judge_group_answers.jsonl`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,api_backend,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/difficultate-respirationis/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.

## Check (c) re-run under judge v0.3 (2026-11-11)
The v0.2 judge gate failed (15/20), and the v0.2 results above report check (c) as unused. Its anchors (LSJ's first-sense gloss) were often wrong in Galen's sentence, so the gate was testing the controls, not the judge. Under judge v0.3 (`firstdrafts_v03_judge_note.md`, committed before any v0.3 call: anchors are targets whose two renderings agree and are attested in the entry; unanswered items are asked once more; prompt, model, plants, gate and thresholds unchanged; seed 20261111) **the gate passed, 20/20**. Items judged in range: rendering A 1418 of 1516, rendering B 1411 of 1516. Check (c) per unit: 189 pass, 18 fail. **Unit verdicts now** (fail = fails two of the three checks): 191 pass, 1 mixed, 15 fail; under v0.2, with (c) unused: 108 pass, 91 mixed, 8 fail. These supersede the v0.2 unit verdicts above; the page's red rules follow the new verdicts. The v0.2 judge files are kept in `judge_v02/`. Limit, stated before the run: v0.3 anchors come from items where the two translators agree, so they cannot show a judge that trusts agreement; the plants, all answered correctly, are what show the judge does not say in_range to everything.

## Agreement with further human translations (check d, exploratory, 2026-11-11)
A. A. Long translated one paragraph of this work, Kühn VII 781–782 (text T23 of 'Pneumatic Episodes from Homer to Galen', in *The Life of Breath in Literature, Culture and Medicine*, Palgrave 2021, open access, CC BY 4.0; copy and licence in `reference/`). The rule of check (d) was applied after the fact to the Greek his paragraph translates (ὅταν οὖν ἤτοι φυμάτων … ὕστερον ἀπαντήσασαι), so the result is exploratory. **Rendering A agrees with his English on 2 of 14 targets (14.29%, Wilson 95% 4.01–39.94); rendering B on 3 of 14 (21.43%, 7.57–47.59).** That is far below the 60% expected for the calibration of *Composition of Drugs by Kind*, on a sample too small to say much. Read item by item (`term_table.csv`, columns `ref_agree_*`), most disagreements are choices of register: the drafts have *tumours* and *phyma*, *orthopnoeas*, *the dropsical*, where Long has *lumps* and *growth*, *vertical breathers*, *dropsy*. One is an error of sense: both drafts render τραχεῖαι ἀρτηρίαι, the windpipe and bronchial tubes, as "rough arteries" (Long: *windpipe*, *pulmonary passages*).
