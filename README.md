# Galen Corpus Infrastructure — Phase 1: Digital-Coverage Census

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21561964.svg)](https://doi.org/10.5281/zenodo.21561964)

A structured, machine-readable census of the Galenic Greek corpus as digitized in the Open Greek
and Latin Project's **First1KGreek** repository: **103 editions across 97 distinct works** (~2.4M
words of Greek), with CTS URNs, word counts, working subject categories, and reader links.

This is Phase 1 of a multi-phase effort to make the untranslated Galenic corpus legible as a
problem for translators and machine-translation research. It answers a question no single resource
currently does cleanly: *which Galenic works exist in machine-readable Greek, and where.*

## Contents

| Path | What |
|---|---|
| [`phase1/galen_ogl_census.csv`](phase1/galen_ogl_census.csv) | The census — flat table, one row per edition |
| [`phase1/galen_ogl_census.json`](phase1/galen_ogl_census.json) | Same data plus a summary block, for programmatic use |
| [`phase1/README_phase1_census.md`](phase1/README_phase1_census.md) | Schema, results, and caveats |
| [`SOURCES.md`](SOURCES.md) | Per-field provenance |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |

## Scope

This is a **digital-availability census** — what Greek text is digitized, and where. It does not
(yet) carry translation status, authenticity classification, non-Greek (Arabic/Syriac) witnesses,
or critical-edition status. Two fields — `kuhn_volume_approx` and `category` — are
approximate/author-assigned; read the caveats in the [census README](phase1/README_phase1_census.md)
before citing them.

Later phases extend this into a terminology density map and a prioritized translation-priority
punch list (in development).

## Citing

Archived release: [doi:10.5281/zenodo.21561964](https://doi.org/10.5281/zenodo.21561964).
See also [`CITATION.cff`](CITATION.cff) — GitHub shows a "Cite this repository" button.

## License

- Data products: **CC-BY-4.0** (see [`LICENSE-DATA`](LICENSE-DATA))
- Any accompanying code: **MIT** (see [`LICENSE`](LICENSE))
