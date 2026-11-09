# Galen, *Adversus Lycum* (Against Lycus) — machine first draft v0.1, cycle 1 (2026-11-09)

**What this is.** The first work of *Galen First Drafts*: a machine translation of a Galenic treatise that has no modern-language translation (census `phase1/README_translation_status.md`: `translation_status = none`; Galenus verbatim lists nothing, Fichtner entry 103 has no T line; Wenkebach's 1951 CMG edition is text only). Two language models rendered the Greek independently with the same neutral prompt and no glossary; the renderings were aligned to the Greek, every target term tied to its LSJ entry, and three pre-registered machine checks run per unit. Nothing was corrected by hand. Page: `docs/first-drafts/adversus-lycum/`. Spec, written before the run: `firstdrafts_v0_spec.md`.

**Unverified.** No scholar has read these pages. The banner says so on every page; the apparatus says where to look, not that the text is right.

## Source and units
- Greek: First1KGreek `tlg0057.tlg093.1st1K-grc1` (Kühn XVIIIA 196–245, keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; all 50 Kühn page breaks present in the TEI.
- `units.py`: 50 units (one Kühn page snapped back to the preceding sentence end; 45 units span two pages, 5 one), 7,452 Greek words, 59–210 words per unit; page breaks kept inline as `[197]`. Greek aligned to the odyCy token stream of the density map (alignment loss 1.65%).
- Targets: 350 NOUN/ADJ tokens (every punch-list token, 88; then four-way `genuinely_hard` tokens rarest-first, 262; cap 8 per unit, proper names and the title excluded). Dilemma 1.3.15 lemma for each; 345 of 350 resolve to a Perseus-LSJ entry (`lsj_index.py`).
- Difficulty: punch-list NOUN/ADJ tokens per 100 tokens (terciles within the work: ≤0.56 low, ≤1.75 mid, above high; 17/17/16 units).

## Renderings
- A = `claude-fable-5-1`, B = `claude-opus-5-5`; prompt in `translate.py` (`SYSTEM`), identical for both; the unit's Greek with its two neighbours as context marked "do not translate"; the target list by position (no class shown). Each unit answered with the translation, the rendering of every target with a y/n uncertainty flag, and the Greek words the model was unsure of.
- Backend: by Will's rule (2026-11-09) no script calls the paid Claude API; `translate.py` had an API backend for the case where a key existed, it was never used (no key is configured on this machine) and was removed. Both translators, the back-translator and the judge ran as Claude Code model sessions (Agent tool, `model=fable` / `opus` / `sonnet`, fresh context, fed the same request files, five packets of ten units per translator). Every row of `renderings_*.jsonl` carries model, prompt SHA-256, the session's timestamps and `backend: claude_code_session`. The API-equivalent cost estimated before the run was $4.90 (`cost_estimate.json`); the actual charge is subscription usage. Sessions used: 10 translator, 4 back-translator, 8 judge (22 in all; about 2.7M subagent tokens as reported by the Agent tool).
- Output: 10,200 English words (A), 9,734 (B); every unit rendered by both; page markers reproduced in all 50 units by both.

## Alignment and term table (`align.py`)
- Sentence alignment anchored on the page markers (A: 48 of 50 units anchored, B: 49), then length-based beads inside each segment: A 189 one-to-one, 39 two-to-one, 7 one-to-two, 19 Greek sentences with no English bead; B 215 / 33 / 11 / 1. The unmatched Greek sentences in A reflect longer English sentences, not omissions, but the alignment is approximate and is labelled so on the page (it is used only to show the English sentence next to a term).
- `term_table.csv`: 350 rows; both renderings reported a rendering for every target. Self-flagged `uncertain`: A 10, B 10.

## The three checks (`checks.py`, thresholds from the spec; results in `checks.json`)

### (b) Rendering agreement A vs B at the term level
- Term level: **276 of 350 targets agree (78.9%, Wilson 95% 74.3–82.8)** after the MT-2026 normalisation (lower-case, stop words, singularisation, published synonym fold). Punch-list targets 74/88 = 84.1% (75.1–90.3); four-way-only targets 202/262 = 77.1% (71.6–81.8). The 74 disagreements are listed in the term table and marked red on the page.
- Unit level (pass = agreement ≥ 0.70): **37 of 50 units pass, 13 fail** (74.0%, 60.5–84.1).
- Density vs disagreement across units: Spearman ρ = −0.05 (n = 50): no relation between punch-list density and A/B disagreement in this work, as in MT-2026.

### (c) LSJ-anchored term check, salted judge — **judge failed the gate; not used**
- 710 items (690 real: both renderings of the 345 targets with an LSJ entry; 10 anchors; 10 plants), shuffled with seed 20261109, judged by `claude-sonnet-5-5` in eight packets; key kept outside the repository until scored, now `judge_key_PUBLISHED_AFTER_SCORING.csv`.
- Gate 20/20 required; **result 16/20.** All 10 planted wrong renderings were caught (`out_of_range`); 6 of 10 anchors were accepted; **4 anchors were rejected, and on inspection the anchors were defective, not the judge**: the mechanical LSJ-first-gloss extractor (`pipeline/mt2026/demo_build.first_gloss`, prescribed by the spec) returned `also ος` for γενναῖος, `older vέπος SIG 9` for ἔπος, `in` for εὐγενής, and the sub-sense `in a form of sun-dial` for στοιχεῖον. The judge called each of them out of range, correctly. By the pre-registered rule the gate nevertheless failed, so (c) is reported as `judge_failed_gate` for every unit and plays no part in the unit verdicts.
- For information only, not pre-registered: the judge found 649 of 690 real renderings `in_range` (A 323 in / 10 out / 12 unsure; B 326 / 10 / 9); applying the unit rule exploratorily would have passed 47 units and failed 3. These figures are not used.
- One judge session reported that for part of its packet the file viewer showed only the first ~330 characters of each LSJ entry (600 were supplied), so some verdicts in packet 4 rest on a truncated entry. Recorded here; next cycle feeds the judge from a tool that returns whole lines.
- Lesson for v0.2 (goes in the next spec, not applied here): validate anchors before salting (an anchor gloss must be an English phrase of real words, not a fragment or a function word), and prefer the entry's first sense over the extractor's first lowercase run.

### (a) Back-translation agreement
- Each English rendering back-translated into Greek by `claude-sonnet-5-5` (two packets of 25 units per rendering; 7,426 Greek words for A), lemmatized with Dilemma, compared with the source lemmas on accent-blind keys. Pass = at least half of the unit's target lemmas reappear.
- **44 of 50 units pass, 6 fail** (88.0%, Wilson 95% 76.2–94.4). Mean term-lemma recall A 0.704, B 0.715 (median 0.75 for both; range 0.0–1.0); mean content-lemma recall (all NOUN/VERB/ADJ/ADV of the unit) A 0.649, B 0.636. Per rendering per unit in `checks.json`.
- The back-translation sessions reported that their timestamps are one clock reading for the whole packet (PowerShell 5.1 has no `-AsUTC`), so `started_utc`/`finished_utc` in `backtranslation_*.jsonl` bracket the packet, not the unit.

## Unit verdicts
Rule: a unit fails when it fails two of the three checks; with (c) out of use, a unit fails only when both (a) and (b) fail.
- **pass (both (a) and (b)): 33 units · mixed (one of the two fails): 15 · fail (both fail): 2** — K18a.228-229, K18a.232-233. Mixed units: K18a.196, K18a.204-205, K18a.217, K18a.219-220, K18a.225-226, K18a.226-227, K18a.227-228, K18a.229-230, K18a.230-231, K18a.231-232, K18a.233-234, K18a.237-238, K18a.238-239, K18a.241-242, K18a.242-243.
- By difficulty tier: low 11 pass / 5 mixed / 1 fail; mid 10 / 6 / 1; high 12 / 4 / 0. The density map's difficulty does not predict the checks' outcome in this work (ρ = −0.05 for (b)); *Against Lycus* is a polemical treatise on innate heat with little pharmacological vocabulary, which is where the map's thin and absent tiers live.
- Failed and mixed units are printed on the page with their marks and kept; nothing was dropped or patched.

## What the checks cannot catch
A rendering that both models get wrong in the same way passes (b): the two models share a developer and training lineage, so agreement is optimistic. A confident mistranslation that round-trips faithfully passes (a). A sense that LSJ lists but Galen does not intend passes (c). Syntax, the scope of a negation, the referent of a pronoun and the structure of an argument are examined by no check. The back-translator and the judge are models of the same developer as the translators. Kühn's text is the only Greek used; Wenkebach's critical edition was not consulted, so a Kühn corruption is translated as it stands (the translators' `uncertain_greek` lists mark some of these). The sentence alignment is length-based and approximate. The judge gate failed on defective anchors, so this cycle has **two** usable checks, not three, and the unit verdicts rest on (a) and (b) alone. These pages are a draft for scholars to correct, with an issue template for every correction; they are not a translation to quote.

## Files
`units.jsonl`, `units_meta.json`, `targets.csv`, `cost_estimate.json`, `requests.jsonl` (+ `requests_README.md`), `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `ingest_report_*.json`, `lsj_entries.json` (+ `_missing`), `alignment.json`, `align_meta.json`, `term_table.csv` (with `judge_A`/`judge_B`), `bt_requests_{A,B}.jsonl`, `backtranslation_{A,B}.jsonl`, `judge_sheet.jsonl`, `judge_sheet_meta.json`, `judge_answers.jsonl`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `checks.json`. Scripts: `pipeline/firstdrafts/{common,units,translate,lsj_index,align,checks,page}.py`. Page: `docs/first-drafts/adversus-lycum/index.html` (+ `data.json`). Issue template: `.github/ISSUE_TEMPLATE/first-draft-correction.yml`.
