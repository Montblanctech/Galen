# greek-lemma-audit — Lemmatizer Audit Kit

One command that audits **any Ancient Greek lemmatizer output over any corpus**,
author-stratified, and emits a **bounded accuracy range**, a **disagreement
worklist** and a **blind reviewer sheet**, as a citable JSON. It is item T1 of
the Galen Density Project roadmap and packages the project's H3-M machine
validation (M1–M3) and M5 blind-sheet protocol so they run over a First1K or
Open Greek author instead of Galen alone.

**Report-only.** The kit never modifies the corpus, never writes into the
project's frozen caches, never installs or downloads models. Everything it
reports carries its N, its 95% Wilson interval and its seed.

## What it measures

| | Measurement | What it yields | Epistemic status |
|---|---|---|---|
| M1 | **Morpheus admissibility** — is the lemma among the rule-based analyzer's readings for the surface? | **error floor**: every `inadmissible` lemma is a near-certain error | independent of neural training data; permissive on variant headwords |
| M2 | **Cross-system agreement** across whatever systems ran (pairwise, all-agree, audit-vs-consensus) + alignment-loss report | **upper-ish bound** + the frequency-ranked **disagreement worklist** | systems share treebanks → correlated errors → overstates accuracy |
| M3 | **LSJ-citation gold** (plugin, Galen only): re-scores every system on the project's 1,850 Morpheus-relocated LSJ loci | **rare-stratum point estimate** | dead-expert gold; LSJ-cited vocabulary is the hard stratum |
| M5 | **Blind reviewer sheet** (frozen random N, salted with controls, shuffled with a seed, private key) + **scorer** (Wilson CI, control gate, Cohen's κ) | the human / LLM adjudication protocol, ready to send | reported separately, never pooled with M1–M3 |

M1 keeps four outcomes apart and never collapses them: `admissible`,
`inadmissible`, `no_analysis` (Morpheus has no reading: coverage gap, excluded
from the denominator) and `not_in_cache` (the surface was never looked up
because the run was offline — also excluded, and flagged when it exceeds 15%).

## Install

```
cd audit-kit
pip install -e .            # stdlib + beta-code + requests
pip install -e .[test]      # + pytest
python -m pytest -q
```

Lemmatizer systems are optional extras; each adapter **skips cleanly and says
why** when its library or model is absent:

| `--systems` name | needs | notes |
|---|---|---|
| `reference` | nothing | the lemmas already in the input JSONL (odyCy 0.7.0 in this project) |
| `odycy` | `spacy==3.7.5`, odyCy wheel `grc_odycy_joint_trf-0.7.0` | loaded as stage 03 does |
| `stanza-perseus`, `stanza-proiel` | `stanza==1.14.0` + the `grc` model **already downloaded** (or `--allow-download`) | reads the project's per-work caches first |
| `dilemma`, `dilemma-guess` | `dilemma-nlp` + its 4.6 GB data download | lexicon-first (Open Greek); `guess=False` / `guess=True` variants; per-surface memo |
| `stoicheia` | a local snapshot of `Ericu950/Stoicheia-tagger-parser` (`--stoicheia-dir` / `STOICHEIA_DIR`), `transformers >= 4.45` (its own venv: conflicts with odyCy's spaCy pin) | 428M-param character model, edit-script lemmas rescored against its lexicon; **85 tokens/s on an 8-thread CPU**; custom code read before first use (no side effects) |
| `greta` | nothing runnable | probes as **unavailable with the reason**: no published lemmatization weights (see `systems/greta.py`); loads a fine-tuned seq2seq from `GRETA_DIR` if someone trains one |

`greek-lemma-audit systems` probes them without downloading anything.

Environment that runs all of them here (2026-11-06), from the repo root:

```
python -m venv --system-site-packages .venv      # inherits torch/spaCy/stanza/odyCy wheels
.venv/Scripts/python -m pip install "numpy<2"    # spaCy 3.7.5 / thinc need numpy 1.x (ABI)
.venv/Scripts/python -m pip install dilemma-nlp lxml pytest -e audit-kit
.venv/Scripts/python -c "import stanza; [stanza.download('grc', package=p, processors='tokenize,pos,lemma') for p in ('perseus','proiel')]"
.venv/Scripts/python -m dilemma download --no-tagger --with-attestation   # 4.6 GB into ~/.cache/dilemma
set STANZA_RESOURCES_DIR=%LOCALAPPDATA%\StanfordNLP\stanza\Cache\1.14.0\resources
esources
```

## Run

```
greek-lemma-audit run --out OUT --corpus-root galen-density-map/data/lemmatized \
    --subcorpus reference --author tlg2039 \
    --systems reference,stanza-perseus,stanza-proiel \
    --controls galen-density-map/data/qc/accuracy_controls.csv \
    --key-out /somewhere/private/key.csv
```

Input: a directory tree of token JSONL files in the project format
(`{"i","surface","lemma","pos","morph"}`) **or** plain-text `.txt` works (the
`reference` system then has nothing to offer; other systems lemmatize the text).
`--author tlgNNNN` filters on the CTS URN author id in the file name;
`--subcorpus` on the first directory level under the root. Works are streamed
one at a time.

Outputs in `OUT/`:

- `audit_summary.json` — the citable record: corpus strata (by author, by
  subcorpus), every system's availability and version, M1/M2/M3/M5 blocks with
  N + CI, seeds, tool versions, runtime, and a `bounded_range` block (floor,
  upper bound, rare-stratum point, sheet status) for the audit system;
- `disagreements.csv` — every token where the systems disagree, frequency-ranked
  by (surface, audit lemma), with each system's lemma, the G2a mechanical class
  (`encoding_artifact` / `accent_only` / `real_disagreement`), whether the audit
  system stands alone against a unanimous rest, and ±6 tokens of context;
- `reviewer_sheet.csv` + `reviewer_instructions.txt` — blind (reviewer columns
  only); the private key goes **only** to `--key-out`;
- `audit_report.md` — one paragraph written from the numbers;
- `m1_inadmissible_<system>.csv`, `m1_no_analysis_<system>.csv`,
  `m1_not_in_cache_<system>.csv`, `m3_rescored_<system>.csv` — worklists.

Useful flags: `--m2-sample N --seed S` (also report M2 on a seeded Algorithm-R
reservoir sample; `--m2-sample 5000 --seed 20260827` reproduces the project's
sample), `--m5-n`, `--m5-seed`, `--m5-sample-csv` (use a pre-drawn sample such
as the project's `accuracy_sample_random60.csv`; with seed 20261105 this
reproduces the project's Sheet A), `--online --rate-limit 0.5 --max-online N`
(query morph.perseids.org for uncached surfaces; new rows go to
`OUT/cache/morpheus_new.jsonl`), `--max-disagreements`, `--no-m3`.

## Reader batches (any model or human, blind, in parallel)

```
greek-lemma-audit batches --sheet OUT/reviewer_sheet.csv --out OUT/batches --rows 100
```

writes `batch_NN.csv` + `prompt_NN.txt` (the sheet's instructions plus a fixed
blind-reader preamble: no lemmatizer, no web, no other files, every row, same
`row_id`s). Run each prompt with the reader of your choice under its own harness,
then score with the batch answers joined by `;`:

```
greek-lemma-audit score --key KEY.csv --answers "r1_b01.csv;r1_b02.csv" --answers "r2_b01.csv;r2_b02.csv" --out OUT/score
```

This is how the project ran its model readers (two models, eight batches each,
`outputs/phase3/reader_pass/`). The kit never calls a model API itself.

## Papyri: the pre-processing report

```
greek-lemma-audit papyri-scan --subcorpus reference --author tlg1595 --out scan.json
```

`papyri.py` implements the Leiden clean-up (brackets, insertions, unread-letter
dots, line/column breaks, quotation marks, final iota adscript) **with flags per
token and no guessed letters**; `papyri-scan` reports how much of a corpus it
would touch (Philodemus in First1K: 14.8%). It is not yet applied in front of the
systems in `run`; that is the next step of T2b.

## Score a returned sheet

```
greek-lemma-audit score --key /somewhere/private/key.csv \
    --answers reader1.csv [--answers reader2.csv] --out OUT/score
```

Answer files carry `row_id`, `answer` (`y`/`n`/`unsure`; the sheet's own
`lemma_correct(y/n/unsure)` column is accepted) and `correct_lemma_if_wrong`.
The rate is computed on the random rows only; the gate per reader is the
protocol's §3 (FAIL on missing the non-word control, missing ≥2 unambiguous
wrong-plants, or marking any right-anchor wrong; accent-only controls are
diagnostic); two readers get Cohen's κ.

## Score your system on LSJ-Gold

```
pip install "git+https://github.com/Montblanctech/Galen#subdirectory=audit-kit"
# write DIR/<system>/<urn_cts_greekLit_tlgAAAA.tlgWWW.edition>.jsonl, one {"i": token_index, "lemma": "..."} per token
greek-lemma-audit lsjgold --system-cache DIR --out scores.json
# prints a Markdown table: blind / strict / article-neutral match, Wilson 95%, by author and validation route
```

The 57,278-locus benchmark (CC BY 4.0) ships inside the package; `--gold CSV` overrides it. Works your system
lacks are reported as `missing`, never as wrong. Optional: `--min-author-rows N`, `--lsj-index JSON` (adds an LSJ
sense-tier stratum). LSJ cites the rare, dictionary-worthy stratum, so this is not overall accuracy.

## Verification against the project's published numbers

Run over the frozen Galen medical JSONL (`--subcorpus galen --author tlg0057`,
systems `reference,stanza-perseus,stanza-proiel` from the H3-M caches, M1 from
cache only) the kit reproduces `data/qc/h3m/` exactly: M1 1,487,476 admissible /
174,279 inadmissible / 84,528 no_analysis (89.51% of analyzable, 4.84% gap),
G1b 12/13 with the same C04 permissive-analyzer caveat, M3 point estimate on the
1,324 loci that fall in the medical subcorpus, and the M5 Sheet A row order.
See the session report for the M2 sample comparison.

## First live results (v0.2, 2026-11-06)

Galen medical, 71 editions, 1,746,283 tokens, audit system = the project's odyCy
output, 11 min on CPU (Dilemma live, Stanza from the H3-M caches):

| | reference (odyCy 0.7.0) | dilemma 1.3.15 (lsj) | stanza-perseus | stanza-proiel |
|---|---|---|---|---|
| M1 floor, admissible % of analyzable (strict) | 89.51 | 82.04 | 91.17 | 87.45 |
| M1 floor, article-convention-neutral | 89.51 | **95.33** | 91.17 | 87.45 |
| M3 LSJ-citation gold, accent-blind match % (n ≈ 1,320) | 61.48 [58.8–64.1] | **95.22 [93.9–96.3]** | 59.65 | 59.73 |
| M3 strict match % | 53.02 | 93.40 | 55.68 | 55.38 |
| M2 pairwise agreement with reference, strict % | — | 68.28 | 83.27 | 84.33 |
| M2 pairwise agreement with reference, article-neutral % | — | 84.42 | 83.27 | 84.33 |

Read with the caveats the kit prints: (a) the M3 gold is LSJ citations and
Dilemma's lexicon is LSJ-headed, so part of its 34-point margin over the neural
systems is headword *convention*, not knowledge; what the table does establish is
that three independently trained neural lemmatizers all sit near 60% on the
LSJ-cited stratum. (b) Dilemma's 82% M1 floor and its 68% agreement with odyCy
are dominated by one convention: it returns the article as its surface form
(τῶν, τοῖς, τό …) where odyCy, Stanza and Morpheus give ὁ — about 40% of the
592k disagreement rows. v0.2 therefore reports an **article-neutral** figure
beside every strict M1/M2 figure (`convention_neutral()` in `normalize.py`, a
documented table, never applied silently). With that one convention mapped,
Dilemma has the **highest Morpheus floor of the four systems (95.3%)** and agrees
with odyCy as often as the Stanza models do (84%); Dilemma–Stanza-proiel is the
best-agreeing pair (86.6%). (c) Dilemma's 63 misses on the gold are
mostly -ῶς adverbs it heads on their own where LSJ heads the adjective.

Diophantus (tlg2039, 5,673 tokens, text-fed systems): odyCy re-run live against
its own stored output agrees on 98.55% of 4,357 aligned tokens; the gap is the
project's stage-03 lemma lowercasing (which the kit does not apply) plus genuine
instability (διάμετρον ↔ διάμετρος in both directions). Alignment loss on
notation-heavy text was 58% before the Greek-letter-only alignment filter and
23% after; the kit flags it either way.

## Accent policy and attribution

`normalize.py`, `align.py`, `stats.py` and the M1/M2/M5 logic are copied with
attribution from `galen-density-map/pipeline/lib/` and `pipeline/h3m/` so the
kit is standalone while its numbers stay byte-comparable with
`data/qc/h3m/METHODS.md`: M1 membership is accent-blind (H4b Beta Code key),
M2 equality is accent-preserving (NFC + casefold + sigma), the accent-strict
admissibility rate is a diagnostic.

## Status (v0.3.1)

0.3.1 (2026-11-10): packaged gold is LSJ-Gold 0.1.1 (71,974 loci; 0.1 less the 21,952 phrase-only quoted loci, see the erratum in `release/lsj-gold-0.1.1/README.md`).
0.3.0 (2026-11-07): `lsjgold` subcommand and packaged LSJ-Gold 0.1 (93,926 loci, CC BY 4.0); 23 tests.
0.2.0 (2026-11-06): below.

Working here: `reference`, `odycy` (live, in the venv above), `stanza-perseus`
and `stanza-proiel` (live or from cache), `dilemma` / `dilemma-guess` (live),
M1 offline, M2 with Greek-only alignment and the article-neutral figure, M3
re-scoring, M5 build + score, CLI, 16 tests (environment-independent).
`stoicheia` (live, in a second venv with transformers 5), `greta` (unavailable by
design, with the reason), `batches` for blind parallel readers. Not exercised:
online Morpheus fill. Not yet: the 50-author table (running), a human reader.

MIT licence.
