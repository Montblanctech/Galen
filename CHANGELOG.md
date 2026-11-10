# Changelog

All notable changes to this project. Format loosely follows Keep a Changelog; versions are
dated on release and each gets a Zenodo DOI.

## [Unreleased] — 2026-11-09

### Fixed
- **LSJ-Gold 0.1.1** (`release/lsj-gold-0.1.1/`, `pipeline/lsjgold/erratum_0_1_1.py`): 0.1 counted a locus as validated by LSJ's quoted form when its token matched any word of a quoted phrase, so some golds were a neighbouring word (Iliad 9:130 καὶ gold κάμνω). 0.1.1 keeps a quoted locus only when LSJ quotes that single word, and never on a quoted prefix such as "προσ-" (2 loci): 71,974 of 93,926 loci, rows unedited, the 21,952 dropped listed beside them. All five systems rescored on the same outputs (`score.py --from-scored`, which reproduces 0.1 exactly on the 0.1 gold): Stoicheia 92.3, Dilemma 92.3, Stanza-Perseus 84.3, odyCy 82.0, Stanza-PROIEL 79.1. Leaderboard, failure catalogues and medical gap regenerated; audit kit 0.3.1 ships the 0.1.1 gold. 0.1 stays citable at doi:10.5281/zenodo.24046260.

### Changed
- The project site's front page and the README now open with Galen First Drafts, the nine works with a link to each; the front page no longer says it holds no translation. README v3.0 paragraph corrected: LSJ-Gold covers 54 authors, not 17.

### Added
- **LS-Gold v0 — the Latin twin of LSJ-Gold** (`galen-density-map/pipeline/lsgold/`, `galen-density-map/data/qc/lsgold/`, `docs/ls-gold/`): Lewis & Short's 253,107 CTS-tagged citations into 162 works held by Perseus canonical-latinLit (173 editions fetched and tokenized by `fetch_editions.py` / `tokenize_editions.py`, 5.4M tokens) relocated by `relocate_la.py` into **161,032 gold loci over 33 authors, 20,830 headwords** (63.6% located; ambiguous 15,059; not located 70,169; locator not in edition 6,847), each validated by Collatinus or Whitaker's Words (`oracle.py`) or by L&S's own quoted form. Blind relocation check (`validation/`, 60 random + 10 anchors + 10 plants, two model readers): 60/60 and 60/60, controls 20/20 each; key published after scoring. Eight systems cached over the whole corpus (`latin_caches.py`) and scored (`score_la.py`): LatinCy la_core_web_lg 84.94%, CLTK 1.5 backoff 83.96%, Stanza 1.15 la-proiel 75.47% / la-perseus 65.46% / la-ittb 65.26% / la-llct 44.40%, with Collatinus-first (82.26%) and Whitaker-first (81.38%) as partly circular baselines. On headwords cited once the neural systems fall 15–25 points below their frequent-headword figure and the lexicon-backed ones do not. Leaderboard page and JSON (`leaderboard_la.py`); `v01_quote_anchor_spec.md` pre-registers the next relocation change (quote-anchored window for the 70k not-located citations) with predictions. Homograph digits are dropped by the comparison key (documented in the README's honesty section). No human reader yet.
- `pipeline/lsjgold/validation_score.py`: date stamp taken from the clock instead of a constant.
- **Galen First Drafts v0.1** (`galen-density-map/pipeline/firstdrafts/`, `galen-density-map/outputs/firstdrafts/`, `docs/first-drafts/`): machine first translations of Galenic works that have no translation in any modern language, published as drafts with their apparatus. First work *Against Lycus* (Kühn XVIIIA 196–245, 7,452 Greek words, 50 units): two independent renderings (claude-fable-5-1, claude-opus-5-5; same neutral prompt, no glossary), sentence alignment, a term table of 350 technical terms tied to 345 LSJ entries and the punch list, and three pre-registered checks (`firstdrafts_v0_spec.md`): back-translation term recall 44/50 units pass; A/B term agreement 78.9%, 37/50 units pass; the salted LSJ judge failed its 20/20 gate (all 10 planted errors caught, 4 of 10 anchors rejected because the mechanical first-gloss extractor produced non-glosses) and is reported unused. Unit verdicts 33 pass / 15 mixed / 2 fail, all kept and marked. Every page carries "Machine first draft, unverified". No scholar has checked it.
- **Galen First Drafts v0.2 — cycle 2 prepared, not run** (`firstdrafts_v02_spec.md`, `galen-density-map/pipeline/firstdrafts/api_backend.py`, `reference.py`, `galen-density-map/outputs/firstdrafts/comp-per-genera/`): the one Claude API backend for translators, back-translator and judge (key from the environment or a key file, never logged; resume from existing JSONL; backoff; direct or Message-Batch mode), the v0.2 fixes (anchors validated as English glosses from the first LSJ sense, whole LSJ entries to the judge, term memory across units as context with consistency reported, per-unit timestamps), and *Composition of Drugs by Kind* (Kühn XIII 362–1058, 697 units, 104,760 Greek words, 5,476 targets, 97.7% with an LSJ entry) with Zainaldin et al.'s ten CC BY reference passages fetched with their licence and mapped to 33 calibration units for a new check (d), reference agreement. No model call made.
- **Galen First Drafts v0.2: *Composition of Drugs by Kind*** (Kühn XIII 362–1058, 104,760 Greek words, 697 units, seven book pages under `docs/first-drafts/comp-per-genera/`): the first complete English translation of the work, as a machine draft with apparatus, rendered on the Claude API. Back-translation 95.8% of units pass; two-model term agreement 77.8%; agreement with the only human reference (ten passages, Zainaldin et al. 2026) 63.5% and 66.4%, above the pre-registered 60%; the salted dictionary judge failed its gate (12/20) and is reported unused. 478 pass, 206 mixed, 9 fail, 4 insufficient, all published and marked. Pages now split by book for works over 120 units; every page carries the author line (William Pepperman) and a citation.
- **Galen First Drafts v0.2 — cycle 3: 7 more works** (`firstdrafts_v02_cycle3_note.md`, `galen-density-map/outputs/firstdrafts/<slug>/`, `docs/first-drafts/<slug>/`): 7 of the eight works that the census listed as `translation_status = none` when cycle 3 was prepared now have machine first drafts with their apparatus, and the eighth, *In Hipp. De natura hominis*, stopped with rendering A at 152 of 173 units (the 11/09 prior-translation check later found a complete English translation of *In Hipp. De natura hominis*, Lewis & Beach 1998, and a complete Italian one of *De hirudinibus*, Ecca 2021; the census and READMEs say so), run on the API in direct mode under the unchanged v0.2 spec and thresholds (A `claude-fable-5-1`, B `claude-opus-5-5`, back-translation and salted LSJ judge `claude-sonnet-5-5`; check (d) not run). *De hirudinibus, revulsione, cucurbitula, incisione et scarificatione* (On Leeches, Revulsion, Cupping, Incision and Scarification; Kühn XI 317–322, 6 units, 704 Greek words, 42 targets): (a) 6/6 units pass, (b) term agreement 88.1%, 5/6 units pass, (c) judge gate 16/20 failed, reported unused; verdicts 5 pass / 1 mixed / 0 fail · *Quos quibus catharticis medicamentis et quando purgare oporteat* (Whom to Purge, with Which Cathartic Drugs, and When; Kühn XI 343–356, 14 units, 1,999 Greek words, 101 targets): (a) 11/14 units pass, (b) term agreement 82.18%, 11/14 units pass, (c) judge gate 16/20 failed, reported unused; verdicts 9 pass / 4 mixed / 1 fail · *De purgantium medicamentorum facultate* (On the Power of Purgative Drugs; Kühn XI 323–342, 20 units, 2,980 Greek words, 158 targets): (a) 19/20 units pass, (b) term agreement 70.25%, 9/20 units pass, (c) judge gate 16/20 failed, reported unused; verdicts 9 pass / 10 mixed / 1 fail · *De totius morbi temporibus* (On the Periods of the Whole Disease; Kühn VII 440–462, 23 units, 3,545 Greek words, 166 targets): (a) 22/23 units pass, (b) term agreement 78.92%, 16/23 units pass, (c) judge gate 20/20 passed, 20/23 units pass; verdicts 23 pass / 0 mixed / 0 fail · *In Hippocratis vel Polybi opus De salubri victus ratione privatorum commentarius* (Commentary on Hippocrates' (or Polybus') Regimen in Health for Private Persons; Kühn XV 174–223, 51 units, 6,840 Greek words, 311 targets): (a) 45/51 units pass, (b) term agreement 77.49%, 36/51 units pass, (c) judge gate 17/20 failed, reported unused; verdicts 32 pass / 17 mixed / 2 fail · *De humero iis modis prolapso quos Hippocrates non vidit* (On the Shoulder Dislocated in Ways Hippocrates Did Not See; Kühn XVIIIA 346–423, 77 units, 9,831 Greek words, 473 targets): (a) 69/77 units pass, (b) term agreement 68.5%, 39/77 units pass, (c) judge gate 19/20 failed, reported unused; verdicts 33 pass / 42 mixed / 2 fail · *De difficultate respirationis* (On Difficulty of Breathing; Kühn VII 753–960, 207 units, 31,901 Greek words, 1,541 targets): (a) 187/206 units pass, (b) term agreement 72.29%, 119/207 units pass, (c) judge gate 15/20 failed, reported unused; verdicts 108 pass / 91 mixed / 8 fail. Every page carries the banner, the author line (William Pepperman, Galen Density Project, Montblanc Tech LLC) and a citation line; the series index lists every work. `units.py`: a trailing wordless page segment joins the previous unit. No scholar has checked any of it.
- **Census translation status** (`phase1/galen_ogl_census.csv`, `README_translation_status.md`): `translation_status` / `translation_source` / `translation_note` for all 103 edition rows from the Galenus verbatim catalogue checked against Fichtner's *Corpus Galenicum*: english 66 works, other modern language 15, partial 4, none 10 (193,644 Greek words, led by *Composition of Drugs by Kind*), unknown 2.

## [3.0.0] — 2026-11-07

### Added
- **M5 — machine-adjudicated lemmatizer accuracy** (`galen-density-map/data/qc/h3m/m5/`,
  `pipeline/h3m/m5_build_sheets.py`, `m5_score.py`, spec `m5_llm_adjudication_spec.md`): the
  salted human protocol run blind by two frontier models in separate sessions; both passed the
  13-control gate 13/13; frozen random-60 marked correct at 83.33% / 81.67% (Wilson 95%
  71.97–90.69 / 70.08–89.44), κ 0.942. The 942 cross-system disagreement tokens adjudicated
  system-blind (`m5_disagreement_resolution.csv`). Reported in the paper §5 under its own label;
  never pooled with M1–M3; the human two-reader check stays planned.
- **Phase 3 v0 — attributed punch list** (`galen-density-map/outputs/phase3/`,
  `pipeline/11_phase3_attribution.py`, spec `phase3_v0_spec.md`): for each of the 1,433 punch-list
  lemmas, the full attested concordance, Kühn loci, the Perseus LSJ entry text, the
  medical-tradition footprint by TLG author (Hippocrates, Dioscorides, Oribasius, Aetius, Paulus,
  Aretaeus) from the same-model reference corpus, and the machine QC flags. Attribution only: no
  glosses, no adjudication.
- **MT-2026 consistency probe** (`galen-density-map/data/qc/mt2026/`, `pipeline/mt2026/`, spec
  `mt2026_consistency_probe_spec.md`, pre-registered before stage 2 ran): two blind translators
  (two 2026 models) on 40 density-stratified passages from *De temperamentis* and *De
  compositione medicamentorum per genera*; term-rendering disagreement on 153 punch-list targets
  vs 153 matched controls, passage-level correlation with punch-list density. **Negative result, reported:** punch-list
  targets 10.46% disagreement vs controls 9.80% (difference 0.65 points, 95% CI −6.1 to +7.4);
  Spearman ρ 0.12 at passage level. Renderings wobble on sense-loaded ordinary words and on
  unit/preparation conventions, not on the rare technical lexicon. `mt2026_summary.json`,
  `mt2026_result.md`, `term_disagreements.csv`.
- **T0 — Open Greek sensitivity check** (`galen-density-map/outputs/t0/`, `pipeline/t0_opengreek_sensitivity.py`): keyness recomputed with the Dilemma lemmatizer on both sides against the 61M-token Open Greek reference and its 19M First1K subset. Reference size barely moves the map (ρ 0.946); the lemmatizer does: 899 of 1,433 punch-list lemmas are not Dilemma headwords, 690 of the 734 `absent`-tier rows. The `absent` tier is re-labelled artifact-suspect in this version.
- `ROADMAP.md`: the standing list the project now works from.

### Changed
- `paper/main.tex`: §5 gains the machine-adjudicated paragraph; Limitations gains its caveat.
- `h3_qc_protocol.md`, `galen-density-map/data/qc/h3m/METHODS.md`: M5 status and pins.

- **Absent-tier headword map and blind reader pass** (stages 12/12b/12c, `outputs/phase3/README_headword_map.md`): Dilemma re-lemmatizes 85.1% of the 734 `absent` punch lemmas to LSJ headwords; two blind model readers call 83.4% / 83.8% artifacts (κ 0.881, all controls caught); 108 consensus real headwords without a Perseus-LSJ entry. Report only; v3.0 carries classes, headwords and verdicts as attributed columns.
- **Audit kit v0.2** (`audit-kit/`): live odyCy, Stanza ×2 and Dilemma; Greek-only alignment; article-convention-neutral figures beside strict; first cross-system LSJ-gold table (Dilemma 95.2% vs neural ~60%).
- **punch_list_v3.csv** (stage 13): the 1,433 rows re-tiered from the headword map and the reader pass (thin 615, thin_contested 84, artifact_suspect 602, real_no_perseus_lsj 108, real_contested 24) with attributed headwords; `real_headwords_no_perseus_lsj.csv`.
- **Audit kit v0.2.x**: Stoicheia adapter (live), GreTa adapter (unavailable with reason), `batches` command, Dilemma memoisation.
- **Constrained-terminology demonstration** (plan §10, pre-registered; `data/qc/mt2026/constrained/`): LSJ-first-gloss glossary obeyed 100% by both translators, term disagreement 23% → 3.8%, other targets unchanged, two blind judges preferred the no-glossary translation in 73–78% of decided pairs. Negative result, reported: a glossary needs a scholar's equivalents, not dictionary definitions.
- **Polysemy probe** (ROADMAP 9, pre-registered; `data/qc/mt2026/polysemy/`): three model families × two runs over 310 targets; polysemy_risk is *not* less stable than genuinely_hard (all differences point the other way, none significant); uncertainty flags track the medical-only class. Negative result, reported; the paper's polysemy sentence is withdrawn.
- **LSJ-Gold v0.3.1** (`galen-density-map/data/qc/lsjgold/`, `pipeline/lsjgold/`, spec `lsj_gold_benchmark_spec.md`, release folder `release/lsj-gold-0.1/`, CC BY 4.0): a benchmark of lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek. Every Perseus-LSJ citation of a held work (First1KGreek editions plus 257 Perseus editions, 5.1M tokens) is relocated into the text and validated by Morpheus or by LSJ's quoted form: **93,926 loci over 54 authors** (Homer 20,329, Aeschylus 7,776, Herodotus 7,627, Plato 7,590, Euripides 7,284, Sophocles 6,694, Aristophanes 5,974, Xenophon 5,934, Thucydides 5,155, Demosthenes 3,530, Hippocrates 2,654 …), each row carrying its provenance. Dilemma matches the headword 90.1% [87.6–88.0] accent-blind (Hippocrates 94.9; the Hellenistic and late epic poets lowest: Oppian 77.4, Apollonius Rhodius 79.9, Nonnus 81.9); odyCy 76.6 on the 63,679 loci its caches cover (Homer 76.5, Herodotus 82.3, Sophocles 82.6, Hippocrates 61.7). Relocation checked blind twice: 60/60 random and 20/20 controls on the v0 loci (`validation/`); on the enlarged set 57/60 and 56/60 with both control gates passed (`validation_v03/`), the three rejected loci exposing a quoted-form weakness that became rule v0.3.1 (a quoted form must share the headword's first letters; 2,536 loci dropped, Dilemma 87.8 → 90.1); the loci are the same 93,926 for every system, so the rows are directly comparable; the aligner was rebuilt the same day (Laws 4% → 98%, Herodotus 18% → 99.6%, Strabo 4% → 97%, Euripides 56% → 99%; `align_check.py`). Stanza 1.14 scored on 90,452 loci with caches built on the project's token stream: Perseus model 79.6% [79.3–79.8], PROIEL 72.0% [71.7–72.3]; by how often LSJ cites the headword, once-cited loci fall to 83.8% (Dilemma), 53.3% (Stanza-Perseus), 52.6% (odyCy), 50.8% (Stanza-PROIEL) against 90.7 / 82.5 / 78.0 / 74.5 on headwords cited six or more times. Stoicheia (2026 diffusion tagger-parser) scored on 36,542 loci with caches built the same way: 87.6% [87.2–87.9] (Aeschylus 93.1, Sophocles 94.4, Plato 89.8, Homer 88.4, Herodotus 84.7, Hippocrates 78.3; once-cited headwords 75.0): the first neural system level with the lexicon-first one on tragedy and epic, 5 points behind on Herodotus and 16 on medical prose. Open, reported: Stoicheia on the remaining 57,000 loci (about 14 hours of CPU).
- **LSJ-Gold leaderboard** (`docs/lsj-gold/`, `pipeline/lsjgold/leaderboard.py`): a standing page and JSON regenerated by one command; every row carries N and a Wilson 95% interval; a version is the gold file's row count and date and never changes inside itself.
- **Audit kit 0.3.0** (`audit-kit/`, MIT): `greek-lemma-audit lsjgold --system-cache DIR` scores any system's token caches on LSJ-Gold with the gold CSV shipped inside the wheel; Stoicheia adapter, `batches`, `papyri-scan` and `--papyri-normalise` (Leiden-bracket clean-up: on Philodemus 13–15% of tokens carry brackets, alignment loss 15% → 4%, one odyCy lemma in five changes).
- **Fifty-author convention table** (`outputs/t1/`): across 50 First1K authors 71% of odyCy–Dilemma disagreement is the article convention; the 11.6% "other" is the real queue. `RECOMMENDATIONS.md`: which lemmatizer for which author, by a stated rule applied mechanically (Dilemma 40, odyCy 7, either 5, insufficient data 14).
- **Term Explorer** (`docs/galen-terms/`, `docs/terms/<tlg>/`): a static page per author (Galen; Diophantus, Philoponus, Philodemus from the T3 term maps): keyness, LSJ tier, Dilemma headword, punch/v3 label, contexts, loci. Built from existing outputs only; no glosses.
- **T3 per-author term maps** (`outputs/t3/`) and **T4 papyrological audit** (`outputs/t4/`, Philodemus).

## [2.0.0] — 2026-08-29

### Added — Phase 2: terminology density map, four-way classification, punch list, preprint
- `galen-density-map/`: the full config-driven pipeline (stages 01–10: fetch, extract,
  lemmatize, frequency, keyness, LSJ cross-reference, punch list, QC, four-way
  classification, accuracy sampling), with library versions and the odyCy model
  (`grc_odycy_joint_trf` 0.7.0) pinned.
- Deliverables under `galen-density-map/outputs/`: `punch_list.csv` (1,433 thin-gloss
  candidate terms with attested contexts), `four_way_classification.csv` (12,538 lemmas along
  medical × disjoint-non-medical axes), keyness scores, per-corpus lemma frequencies, audited
  exclusion logs, and `qc_summary.json`. The 60MB regenerable reference lemma-frequency JSON
  is attached to the v2.0 GitHub release (gzipped) rather than tracked in git.
- **Machine-bounded lemmatizer accuracy** (`galen-density-map/data/qc/h3m/` + pipeline
  `h3m/`): Morpheus admissibility floor (89.51% of analyzable medical tokens), Stanza
  cross-system agreement (82.89% pairwise / 94.17% vs-consensus), and a 1,850-item gold
  standard mined from LSJ's own Galen citations (62.32% accent-blind / 53.95% strict on the
  rare stratum, with a full mismatch taxonomy). Methods and per-measurement caveats in
  `h3m/METHODS.md`; the human spot-check design is summarized in `h3m/PROTOCOL_NOTE.md`.
- `paper/`: the Phase 2 preprint (ACL-style XeLaTeX, `main.pdf`, 6 pp) and `references.bib`.

### Known limitations (stated, not hidden)
- Lemmatizer error is **reported, not patched**: fragmentation, consistently-wrong irregular
  lemmas, and rare-stratum degradation (62.32% on LSJ-cited loci) are documented and carried
  into the paper's limitations; no Greek lexical judgment is applied by machine.
- The four-way `polysemy_risk` quadrant is a candidate difficulty class, not a confirmed one;
  whether it degrades MT is explicitly open (paper §6).
- Phase 1 census caveats below still apply.

## [1.0.0] — 2026-07-25

### Added — Phase 1: First1KGreek digital-coverage census of Galen
- `phase1/galen_ogl_census.csv` and `.json`: a structured inventory of every Galen
  (TLG `tlg0057`) edition digitized in machine-readable Greek by OpenGreekAndLatin /
  First1KGreek — **103 editions across 97 distinct works**, ~2.4M words of Greek.
- Nine fields per edition: `tlg_number`, `edition_suffix`, `urn`, `title`, `languages`,
  `wordcount`, `kuhn_volume_approx`, `category`, `scaife_url`.
- `phase1/README_phase1_census.md` — schema, result (green-light gate for Phase 2), and caveats.
- `SOURCES.md` — per-field provenance.
- Packaging: `LICENSE` (MIT, code), CC-BY-4.0 for data products, `CITATION.cff`.

### Known limitations (stated, not hidden)
- `kuhn_volume_approx` is an unverified best-effort mapping — not for scholarly citation until
  checked against a proper concordance.
- `category` is an author-assigned filtering bucket, not a citable taxonomy.
- Greek only; no Arabic/Syriac witnesses, no translation/authenticity/critical-edition status.
- Scope is *digital availability*, not the full plan-§8 corpus census.

### Notes
- Phase 2 (terminology density map) is in development on a separate branch and is **not** part
  of this release; its punch list is a draft with a measured-error caveat pending a
  Greek-literate lemmatizer spot-check.
