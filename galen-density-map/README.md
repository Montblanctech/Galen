# Galen Terminology Density Map

Phase 2 pipeline: fetch digitized Galenic Greek (First1KGreek), lemmatize with
**odyCy** (spaCy transformer), compute log-likelihood keyness against a non-Galen
reference corpus, cross-reference thin LSJ glosses, and emit a prioritized
`punch_list.csv`.

**Non-goals:** translations, lexicon adjudication, UI.

## Setup

```bash
cd galen-density-map
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt

# odyCy Ancient Greek TRANSFORMER model (required — not the small _sm model, not CLTK):
pip install https://huggingface.co/chcaa/grc_odycy_joint_trf/resolve/main/grc_odycy_joint_trf-0.7.0-py3-none-any.whl
```

Pinned stack:

| Component | Version |
|---|---|
| spaCy | 3.7.5 |
| spacy-transformers | 1.3.5 |
| odyCy model | `grc_odycy_joint_trf==0.7.0` |

Phase 1 census input: `../phase1/galen_ogl_census.json`.

## Run (stage by stage)

All tunables are in `config.yaml`. Each stage is independently rerunnable.

```bash
python pipeline/01_fetch.py --skip-reference          # Galen medical scope
python pipeline/01_fetch.py --skip-reference --all-galen   # + non-medical Galen (whole-Galen axis)
python pipeline/02_extract.py                         # NFC + lunate σ + header strip + crasis
python pipeline/03_lemmatize.py --skip-existing       # medical → lemmatized/galen/
python pipeline/03_lemmatize.py --nonmedical-only --skip-existing  # → galen_nonmedical/
# After overnight full reference fetch (separate step — do not start until QC passes):
#   python pipeline/01_fetch.py
python pipeline/02_extract.py --include-reference
python pipeline/03_lemmatize.py --include-reference --skip-galen --skip-existing
python pipeline/04_frequency.py                       # medical + whole-Galen + reference
python pipeline/05_keyness.py
python pipeline/06_lsj_crossref.py                    # Beta Code LSJ; checks top-50 common
python pipeline/07_punchlist.py                       # thin gloss + hallucination drop + lsj_tier
python pipeline/08_qc.py                              # standing QC summary
python pipeline/09_four_way.py                        # plan §9 four-way classification
python pipeline/10_accuracy_sample.py                 # random-60 reviewer sheet
```

## Normalization (stage 02)

- Unicode NFC
- Lunate sigma `ϲ`/`Ϲ` → `σ`/`Σ`; word-final → `ς`
- Strip ALL-CAPS Greek header tokens (e.g. `ΓΑΛΗΝΟΥ`)
- Expand known crasis/elision (`κᾀνταῦθα` → `καὶ ἐνταῦθα`, `οὐδ'` → `οὐδέ`); unknown tight matches dropped + logged
- Lemma counting is case-insensitive (`ἱπποκράτης` == `Ἱπποκράτης`)

## Stoplists (auditable)

Under `data/stoplists/`:

- `authors.txt` — ancient names (odyCy tags them NOUN, not PROPN)
- `units_numerals.txt` — dosage units / bare numerals (`δραχ`, `δραχμή`, …)
- `elision_debris.txt` — elision/crasis leftovers

Every exclusion is written to `outputs/excluded_stoplist_audit.log`.

## Punch-list POS whitelist

Config: `punch_list_pos_whitelist: [NOUN, ADJ]`. Stage 07 keeps only substantive
terminology (substances, plants, minerals, body parts, conditions). **ADJ is kept** —
quality terms like δριμύς ("acrid") are wanted. ADV / PRON / VERB / etc. style noise
is dropped and logged to `outputs/excluded_pos_whitelist.json` + the audit log.

## Lemma orthography (documented only)

Stage 03 may apply **purely orthographic** lemma normalizations (logged in the
lemmatize summary). Current rule: `γιγγν` → `γιγν` (odyCy doubled-gamma on γίγνομαι).
Semantic lemma corrections are **out of scope** (plan §3) — see suspect report below.

## Outputs

| File | Meaning |
|---|---|
| `lemma_frequency_galen.json` | Lemma counts in medical Galen subset |
| `lemma_frequency_galen_nonmedical.json` | Lemma counts in disjoint non-medical Galen (four-way Axis B) |
| `lemma_frequency_galen_whole.json` | Lemma counts over all census Galen (completeness / CSV only) |
| `lemma_frequency_reference.json` | Lemma counts in reference corpus |
| `keyness_scores.csv` | G² keyness |
| `keyness_with_lsj.csv` | Overused + LL threshold + LSJ sense counts |
| `punch_list.csv` | Human-facing deliverable (NOUN/ADJ thin-gloss; `lsj_tier` absent/thin) |
| `four_way_classification.csv` | Plan §9 quadrants on medical vs **non-medical** Galen (NOUN/ADJ/VERB) |
| `four_way_summary.json` | Quadrant counts, sensitivity, punch overlap, per-quadrant examples |
| `lsj_top50_common_check.json` | Must be ~100% match for common words |
| `qc_summary.json` | Standing QC (passthrough, never-real-lemma, coverage, LSJ, suspects) |
| `excluded_stoplist_audit.log` | Every stoplist / POS-whitelist / hallucination drop |
| `excluded_hallucinations.json` | sense_count=0 + no surface neighbor (auto-dropped) |
| `../data/qc/suspect_high_freq_lemmas.csv` | Priority worklist for H3 spot-check |
| `../data/qc/accuracy_sample_random60.csv` | Uniform random 60-token reviewer sheet |

## Standing QC (printed by `08_qc.py`)

1. Lemmatizer-health passthrough % — NOUN/VERB/ADJ + open-class ADV, **excluding**
   closed-class particles tagged ADV (`τε`, `οὖν`, `μέν`, …) where lemma==surface is
   correct. Also prints raw NVAA and NVA-only. Target: materially under 28.7%.
2. % of punch-list lemmas that never lemmatize an inflected form — low single digits
   (candidates that never do are logged + dropped in stage 07).
3. Per-work extracted tokens vs census `wordcount` — flag &lt;70%.
4. LSJ match overall + top-50 common lemmas (~100%; units/authors excluded from the 50).
5. Punch-list top-40 (eyeball check).
6. **Suspect high-freq lemmas** (SEPARATE gate from #2): judgment-free heuristics for
   residual mis-lemmatization / fragmentation — (a) Gen/Dat/plural form used as lemma
   when surface==lemma; (b) near-duplicate lemmas sharing neighbor contexts
   (fragmentation); (c) doubled-consonant orthography; (d) high-freq lemma almost
   never attested as its own surface (phantom citation form). Emits
   `data/qc/suspect_high_freq_lemmas.csv`. Do **not** auto-correct; this is the
   priority set for the Greek-literate spot-check. Gate #2 does not catch
   consistently-wrong lemmas (νεῦρον→νεύρος passes never-a-real-lemma).

Model pin: **odyCy `grc_odycy_joint_trf==0.7.0`** via spaCy 3.7.5 — **not CLTK**, not `_sm`.

## Limitations

- Census `category` tags are author-assigned.
- Kühn volume column in Phase 1 is unverified.
- Lemmatizer accuracy is machine-bounded, not human-verified: 89.5% Morpheus-admissibility
  floor on medical tokens, 62.3% on the rare LSJ-cited stratum (see `data/qc/h3m/METHODS.md`).
  A Greek-literate spot-check remains planned (`data/qc/h3m/PROTOCOL_NOTE.md`); the priority
  queues are `data/qc/h3m/m1_inadmissible.csv` and `m2_disagreements.csv`.
- Thin LSJ sense count ≠ “undefined medically”.
- Transformer chunks at ~4k chars to avoid OOM.
- Keyness is computed against the full First1KGreek-minus-Galen reference (grc
  editions). Re-run `01_fetch.py` → extract/lemmatize reference → 04–08 after any
  lemmatizer change before citing ranks.

## License

Code: MIT. Data products: CC-BY on public release.
