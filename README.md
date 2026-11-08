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

**v3.0 (2026-11-07) — Phase 3 v0 and the LSJ-Gold benchmark.** The punch list is re-tiered from
a headword map and a blind reader pass (`outputs/phase3/punch_list_v3.csv`: thin 615,
thin_contested 84, artifact_suspect 602, real_no_perseus_lsj 108, real_contested 24); two
pre-registered probes report negative results (an LSJ-first-gloss glossary makes translations
worse; polysemy does not predict instability); and the project ships **LSJ-Gold**, a benchmark of
lemmatizer accuracy on the words the dictionary itself cites: **93,926 relocated loci over 17
authors**, CC BY 4.0, with a [standing leaderboard](docs/lsj-gold/index.html) and a pip-installable
[audit kit](audit-kit/) (`greek-lemma-audit lsjgold`) so any system can be scored the same way.
Dilemma (lexicon-first) matches the lexicographer's headword 90.1% of the time; Stanza-Perseus 79.6% and
odyCy 75.7% and Stanza-PROIEL 72.0%, all on the same 90,452 loci; Stoicheia, a 2026 diffusion tagger, 87.6% on 36,542 loci
(Aeschylus 93.1 and Sophocles 94.4, above Dilemma there; Homer 88.4 and Plato 89.8, level with it; Herodotus 84.7 and
Hippocrates 78.3, below it). On headwords LSJ cites only once: Dilemma 83.8%, Stoicheia 75.0%, the treebank-trained systems 51–53%. Details: [`CHANGELOG.md`](CHANGELOG.md), [`galen-density-map/data/qc/lsjgold/README.md`](galen-density-map/data/qc/lsjgold/README.md).

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
| [`galen-density-map/outputs/phase3/`](galen-density-map/outputs/phase3/) | Phase 3 v0: attributed punch list, headword map, blind reader pass, `punch_list_v3.csv` |
| [`galen-density-map/data/qc/lsjgold/`](galen-density-map/data/qc/lsjgold/) | **LSJ-Gold**: the benchmark (`lsj_gold_v0.csv`, 93,926 loci), scores, validation sheets, README |
| [`release/lsj-gold-0.1/`](release/lsj-gold-0.1/) | The LSJ-Gold release folder (CSV, schema, scores, leaderboard JSON, CC BY 4.0, checksums) |
| [`docs/lsj-gold/`](docs/lsj-gold/) | The leaderboard page and JSON (GitHub Pages) |
| [`audit-kit/`](audit-kit/) | `greek-lemma-audit`: Morpheus floor, cross-system agreement, LSJ gold, blind sheets, `lsjgold` scoring (MIT, on PyPI) |
| [`galen-density-map/outputs/t1/`](galen-density-map/outputs/t1/) | Fifty-author convention table and per-author lemmatizer recommendations |
| [`docs/terms/`](docs/terms/) | Term Explorer pages (Galen and three further authors) |
| [`galen-density-map/data/qc/mt2026/`](galen-density-map/data/qc/mt2026/) | MT-2026 probes: consistency, constrained terminology, polysemy (all pre-registered, all reported) |
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
confirms the rarity→failure pattern. Error is **reported, never patched**. v3.0 adds a fourth bound, **M5**, two blind model readers on the salted
human protocol (83.3% / 81.7%, κ 0.94), and widens the gold to **LSJ-Gold** across 54 authors, where
the lexicon-first Dilemma reaches 90.1%, Stanza-Perseus 79.6%, odyCy 75.7% (62.2% on Hippocrates), Stanza-PROIEL 72.0%; 71% of their disagreement
with each other is the article convention (`outputs/t1/`).

## Reproducibility

Model (`grc_odycy_joint_trf` 0.7.0), spaCy, and all dependencies are pinned
([`galen-density-map/requirements.txt`](galen-density-map/requirements.txt)); every stage is
config-driven ([`config.yaml`](galen-density-map/config.yaml)) and independently re-runnable.
Large regenerable intermediates (raw TEI, lemmatized JSONL, the 60MB reference lemma-frequency
JSON) are not in git; the reference frequencies are attached to the [v2.0 GitHub release](https://github.com/Montblanctech/Galen/releases/tag/v2.0)
(`lemma_frequency_reference.json.gz`), and everything else regenerates from the pipeline.

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
