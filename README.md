# Galen Corpus Infrastructure — Census + Terminology Density Map

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21561962.svg)](https://doi.org/10.5281/zenodo.21561962)

Reproducible infrastructure for making the untranslated Galenic corpus legible as a problem for
translators and machine-translation research. Two phases, released together as of v2.0:

- **Phase 1 — Digital-coverage census**: a structured, machine-readable census of the Galenic
  Greek corpus as digitized in Open Greek and Latin's **First1KGreek**: **103 editions across 97
  distinct works** (~2.4M words of Greek), with CTS URNs, word counts, working subject
  categories, and reader links.
- **Phase 2 — Terminology density map**: a config-driven pipeline (extraction → odyCy
  lemmatization → log-likelihood keyness against a 19.7M-token non-Galen reference → LSJ
  cross-reference) producing a **four-way classification** of candidate-hard vocabulary along
  two frequency axes (medical Galen × Galen's own disjoint non-medical works) and a prioritized
  **punch list of 1,433 thin-gloss candidate terms**. Motivated by Zainaldin et al.'s finding
  that terminology rarity predicts MT failure on Galen (r = −.97): this maps *which* vocabulary,
  per lemma, corpus-wide.

The preprint describing Phase 2 is in [`paper/`](paper/) (`main.pdf`).

## Contents

| Path | What |
|---|---|
| [`phase1/galen_ogl_census.csv`](phase1/galen_ogl_census.csv) | The census — flat table, one row per edition |
| [`phase1/galen_ogl_census.json`](phase1/galen_ogl_census.json) | Same data plus a summary block, for programmatic use |
| [`phase1/README_phase1_census.md`](phase1/README_phase1_census.md) | Census schema, results, and caveats |
| [`galen-density-map/pipeline/`](galen-density-map/pipeline/) | The Phase 2 pipeline, stages 01–10 plus the `h3m/` accuracy-validation suite |
| [`galen-density-map/outputs/punch_list.csv`](galen-density-map/outputs/punch_list.csv) | The 1,433-term punch list (lemma, frequencies, keyness, LSJ tier, attested contexts) |
| [`galen-density-map/outputs/four_way_classification.csv`](galen-density-map/outputs/four_way_classification.csv) | Four-way classification of 12,538 lemmas |
| [`galen-density-map/outputs/`](galen-density-map/outputs/) | Keyness scores, per-corpus lemma frequencies, audited exclusion logs, QC summary |
| [`galen-density-map/data/qc/`](galen-density-map/data/qc/) | QC artifacts, incl. `h3m/` machine-bounded lemmatizer-accuracy measurements + METHODS |
| [`paper/main.pdf`](paper/main.pdf) | The Phase 2 preprint (ACL-style, XeLaTeX) |
| [`SOURCES.md`](SOURCES.md) | Per-field provenance |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |

## Lemmatizer accuracy (measured, not assumed)

Every frequency inherits odyCy's error rate, so we bound it three ways (details:
[`galen-density-map/data/qc/h3m/METHODS.md`](galen-density-map/data/qc/h3m/METHODS.md), paper §5):
**89.5%** of analyzable medical tokens carry a Morpheus-admissible lemma (rule-based floor);
cross-system agreement with Stanza is 82.9% pairwise / 94.2% vs-consensus (optimistic, shared
treebanks); on **1,850** gold loci mined from LSJ's own Galen citations, odyCy matches the
lexicographer's headword **62.3%** accent-blind — a rare-stratum accuracy that independently
confirms the rarity→failure pattern. Error is **reported, never patched**.

## Reproducibility

Model (`grc_odycy_joint_trf` 0.7.0), spaCy, and all dependencies are pinned
([`galen-density-map/requirements.txt`](galen-density-map/requirements.txt)); every stage is
config-driven ([`config.yaml`](galen-density-map/config.yaml)) and independently re-runnable.
Large regenerable intermediates (raw TEI, lemmatized JSONL, the 60MB reference lemma-frequency
JSON) are not in git; the reference frequencies ship with the Zenodo record, and everything else
regenerates from the pipeline.

## Scope

Phase 1 is a **digital-availability census** — what Greek text is digitized, and where. It does
not carry translation status, authenticity classification, non-Greek (Arabic/Syriac) witnesses,
or critical-edition status. Two fields — `kuhn_volume_approx` and `category` — are
approximate/author-assigned; read the caveats in the [census README](phase1/README_phase1_census.md)
before citing them. Phase 2 is **compile-and-attribute infrastructure**: it makes no translation
and adjudicates no Greek word's meaning; contested judgments are surfaced for specialists, with
fields left blank for a future community-compiled Phase 3.

## Citing

Cite the concept DOI (always resolves to the latest version):
[doi:10.5281/zenodo.21561962](https://doi.org/10.5281/zenodo.21561962).
See also [`CITATION.cff`](CITATION.cff) — GitHub shows a "Cite this repository" button.

## License

- Data products: **CC-BY-4.0** (see [`LICENSE-DATA`](LICENSE-DATA))
- Code: **MIT** (see [`LICENSE`](LICENSE))
