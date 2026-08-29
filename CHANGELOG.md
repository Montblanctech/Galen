# Changelog

All notable changes to this project. Format loosely follows Keep a Changelog; versions are
dated on release and each gets a Zenodo DOI.

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
  ships with the Zenodo record rather than git.
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
