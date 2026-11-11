# Galen Corpus Infrastructure — Census + Terminology Density Map

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21561962.svg)](https://doi.org/10.5281/zenodo.21561962)

**Galen in English for the first time.** Thirteen works of Galen that had no complete English translation that we know of, published as machine first drafts by William Pepperman: unverified, with the Greek, two renderings, a term table and the failed units marked on every page. [Read them on the project site](https://montblanctech.github.io/Galen/first-drafts/), and see [what the drafts say](https://montblanctech.github.io/Galen/findings/): 678 items (people, lost books, recipes, cases) found in them, each linked to its passage.

- [*Against Lycus*](https://montblanctech.github.io/Galen/first-drafts/adversus-lycum/) (Adversus Lycum)
- [*On the Composition of Drugs by Kind*](https://montblanctech.github.io/Galen/first-drafts/comp-per-genera/) (De compositione medicamentorum per genera)
- [*On Leeches, Revulsion, Cupping, Incision and Scarification*](https://montblanctech.github.io/Galen/first-drafts/hirudinibus/) (De hirudinibus, revulsione, cucurbitula, incisione et scarificatione)
- [*Whom to Purge, with Which Cathartic Drugs, and When*](https://montblanctech.github.io/Galen/first-drafts/quos-quibus/) (Quos quibus catharticis medicamentis et quando purgare oporteat)
- [*On the Power of Purgative Drugs*](https://montblanctech.github.io/Galen/first-drafts/purgantium-facultate/) (De purgantium medicamentorum facultate)
- [*On the Periods of the Whole Disease*](https://montblanctech.github.io/Galen/first-drafts/morbi-temporibus/) (De totius morbi temporibus)
- [*Commentary on Hippocrates' (or Polybus') Regimen in Health for Private Persons*](https://montblanctech.github.io/Galen/first-drafts/in-hipp-salubri/) (In Hippocratis vel Polybi opus De salubri victus ratione privatorum commentarius)
- [*On the Shoulder Dislocated in Ways Hippocrates Did Not See*](https://montblanctech.github.io/Galen/first-drafts/de-humero/) (De humero iis modis prolapso quos Hippocrates non vidit)
- [*On Difficulty of Breathing*](https://montblanctech.github.io/Galen/first-drafts/difficultate-respirationis/) (De difficultate respirationis)

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
lemmatizer accuracy on the words the dictionary itself cites: **70,198 relocated loci over 54
authors** (0.1.2), CC BY 4.0, with a [standing leaderboard](docs/lsj-gold/index.html) and a pip-installable
[audit kit](audit-kit/) (`greek-lemma-audit lsjgold`) so any system can be scored the same way.
Stoicheia, a 2026 diffusion tagger, matches the lexicographer's headword 92.8% of the time and Dilemma (lexicon-first) 92.8%, a tie;
Stanza-Perseus 84.8%, odyCy 82.5% and Stanza-PROIEL 79.6%, the four neural systems on the same 67,639 loci
(Stoicheia is above Dilemma on Homer 95.1, Aeschylus 94.3 and Sophocles 96.8; just below on Plato and Herodotus; well below on
Hippocrates, 79.4 to 95.9). On headwords LSJ cites only once: Dilemma 92.3%, Stoicheia 78.4%, the treebank-trained systems 60%.
0.1.1 corrects 0.1 (93,926 loci), which also counted a token matching any word of a phrase LSJ quotes; 0.1.2 reads its 652 weakest loci blind and drops 313, counts a repeated locus once, and sets aside 49 tokens gold under two headwords. See [`release/lsj-gold-0.1.2/README.md`](release/lsj-gold-0.1.2/README.md). Details: [`CHANGELOG.md`](CHANGELOG.md), [`galen-density-map/data/qc/lsjgold/README.md`](galen-density-map/data/qc/lsjgold/README.md).

**LS-Gold (2026-11-08, on the lab branch, not yet a release) — the Latin twin of LSJ-Gold.** The words Lewis & Short (1879) cites for a headword, relocated into the Perseus canonical-latinLit editions and checked by two independent offline analysers (Collatinus and Whitaker's Words): **161,032 loci over 33 authors, 20,830 headwords**, blind relocation check 60/60 by two readers, CC BY-SA 4.0 (L&S's licence), with a [leaderboard](docs/ls-gold/index.html) built the same way as the Greek one. LatinCy 84.9%, CLTK 84.0%, Stanza la-proiel 75.5%, la-perseus 65.5%, la-ittb 65.3%, la-llct 44.4%, all on the same loci; on headwords L&S cites once the neural systems lose 15–25 points and the lexicon-backed ones do not, the same shape as the Greek table. Details: [`galen-density-map/data/qc/lsgold/README.md`](galen-density-map/data/qc/lsgold/README.md).

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
| [`galen-density-map/data/qc/lsjgold/`](galen-density-map/data/qc/lsjgold/) | **LSJ-Gold**: the benchmark (`lsj_gold_v0_1_2.csv`, 70,198 loci; 0.1.1 `lsj_gold_v0_1_1.csv`; 0.1 `lsj_gold_v0.csv`, 93,926), scores, validation and reading sheets, README |
| [`release/lsj-gold-0.1.2/`](release/lsj-gold-0.1.2/) | The current LSJ-Gold release folder (CSV, schema, scores, leaderboard JSON, set-aside rows, CC BY 4.0, checksums); [`0.1.1`](release/lsj-gold-0.1.1/) and [`0.1`](release/lsj-gold-0.1/) are kept as published |
| [`docs/lsj-gold/`](docs/lsj-gold/) | The leaderboard page and JSON (GitHub Pages) |
| [`galen-density-map/data/qc/lsgold/`](galen-density-map/data/qc/lsgold/) | **LS-Gold**: the Latin twin (`ls_gold_v0.csv`, 161,032 Lewis & Short loci over 33 authors), scores, blind sheet, README |
| [`galen-density-map/pipeline/lsgold/`](galen-density-map/pipeline/lsgold/) | The LS-Gold pipeline: fetch and tokenize the Perseus Latin editions, relocate, two-oracle validation, score, leaderboard |
| [`docs/ls-gold/`](docs/ls-gold/) | The Latin leaderboard page and JSON (GitHub Pages) |
| [`docs/first-drafts/`](docs/first-drafts/) | **Galen First Drafts**: machine first English drafts of thirteen works with no complete English translation known to us, unverified, with the Greek, two renderings, term table and check marks; the [drafts index](docs/first-drafts/index.html) lists every work (author William Pepperman) |
| [`galen-density-map/pipeline/firstdrafts/`](galen-density-map/pipeline/firstdrafts/) | The First Drafts pipeline (units, renderings, alignment, term table, three pre-registered checks, page) and its spec |
| [`phase1/README_translation_status.md`](phase1/README_translation_status.md) | Translation status of every census work (english / other modern / partial / none), with sources |
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
(in 0.1.2) the lexicon-first Dilemma and the 2026 Stoicheia tagger are level at 92.8%, followed by Stanza-Perseus 84.8%, odyCy 82.5% (63.1% on Hippocrates) and Stanza-PROIEL 79.6%. Across 50 First1K
authors, 71% of odyCy–Dilemma disagreement is the article convention (`outputs/t1/`).

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
[doi:10.5281/zenodo.21561962](https://doi.org/10.5281/zenodo.21561962); this version (3.0.0) is [doi:10.5281/zenodo.24046260](https://doi.org/10.5281/zenodo.24046260).
See also [`CITATION.cff`](CITATION.cff) — GitHub shows a "Cite this repository" button.

## License

- Data products: **CC-BY-4.0** (see [`LICENSE-DATA`](LICENSE-DATA))
- Code: **MIT** (see [`LICENSE`](LICENSE))
