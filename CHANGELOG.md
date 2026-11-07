# Changelog

All notable changes to this project. Format loosely follows Keep a Changelog; versions are
dated on release and each gets a Zenodo DOI.

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
- **LSJ-Gold v0.3.1** (`galen-density-map/data/qc/lsjgold/`, `pipeline/lsjgold/`, spec `lsj_gold_benchmark_spec.md`, release folder `release/lsj-gold-0.1/`, CC BY 4.0): a benchmark of lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek. Every Perseus-LSJ citation of a held work (First1KGreek editions plus 257 Perseus editions, 5.1M tokens) is relocated into the text and validated by Morpheus or by LSJ's quoted form: **93,926 loci over 54 authors** (Homer 20,329, Aeschylus 7,776, Herodotus 7,627, Plato 7,590, Euripides 7,284, Sophocles 6,694, Aristophanes 5,974, Xenophon 5,934, Thucydides 5,155, Demosthenes 3,530, Hippocrates 2,654 …), each row carrying its provenance. Dilemma matches the headword 90.1% [87.6–88.0] accent-blind (Hippocrates 94.9; the Hellenistic and late epic poets lowest: Oppian 77.4, Apollonius Rhodius 79.9, Nonnus 81.9); odyCy 76.6 on the 63,679 loci its caches cover (Homer 76.5, Herodotus 82.3, Sophocles 82.6, Hippocrates 61.7). Relocation checked blind twice: 60/60 random and 20/20 controls on the v0 loci (`validation/`); on the enlarged set 57/60 and 56/60 with both control gates passed (`validation_v03/`), the three rejected loci exposing a quoted-form weakness that became rule v0.3.1 (a quoted form must share the headword's first letters; 2,536 loci dropped, Dilemma 87.8 → 90.1); the loci are the same 93,926 for every system, so the rows are directly comparable; the aligner was rebuilt the same day (Laws 4% → 98%, Herodotus 18% → 99.6%, Strabo 4% → 97%, Euripides 56% → 99%; `align_check.py`). Stanza 1.14 scored on 90,452 loci with caches built on the project's token stream: Perseus model 79.6% [79.3–79.8], PROIEL 72.0% [71.7–72.3]; by how often LSJ cites the headword, once-cited loci fall to 83.8% (Dilemma), 53.3% (Stanza-Perseus), 52.6% (odyCy), 50.8% (Stanza-PROIEL) against 90.7 / 82.5 / 78.0 / 74.5 on headwords cited six or more times. Open, reported: the Stoicheia row beyond Galen (41 loci so far).
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
