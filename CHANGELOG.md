# Changelog

All notable changes to this project. Format loosely follows Keep a Changelog; versions are
dated on release and each gets a Zenodo DOI.

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
