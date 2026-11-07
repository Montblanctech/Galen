# H3-M methods pins

Report-only QC. Frozen `data/lemmatized/**`, `data/extracted_text/**`, and `outputs/**` are not
modified. Artifacts: `galen-density-map/data/qc/h3m/`. Cache (gitignored): `h3m/cache/`.

## Lemmatizer under test

- odyCy `grc_odycy_joint_trf==0.7.0` (spaCy 3.7.5), as frozen in stage 03.

## Morpheus (M1)

- Engine: Perseids Morpheus, creator `org.perseus:tools:morpheus.v1`, `engine=morpheusgrc`.
- Preferred: Docker `perseidsproject/morpheus-perseids-api:v2.1.5` on `localhost:1500`
  (`pipeline/h3m/docker-compose.yml`).
- This run: Docker was not installed on the Windows host; queries went to
  `https://morph.perseids.org` (same JSON/RDF analysis API). Unique NFC surfaces are cached in
  `h3m/cache/morpheus_by_surface.jsonl` so the public service is hit at most once per surface.
- Accent policy (primary membership): H4b `lemma_to_lookup_key` (NFC, casefold, Beta Code, strip
  diacritics/digits/sigma variants). Accent-strict NFC+sigma rates are a diagnostic only.
- Three-way outcome: `admissible` / `inadmissible` / `no_analysis`. Coverage gaps are excluded
  from the denominator.
- **Permissive-analyzer caveat (G1b control):** Perseids Morpheus sometimes lists a variant or
  inflected stem as a lemma. Surface ἥπατος returns `['ἥπατος', 'ἧπαρ']`, so odyCy's
  passthrough lemma ἥπατος scores `admissible`. Where Morpheus carries variant/late lemmas,
  the admissibility floor is slightly optimistic. No M1 code change; the rate is still the
  paper floor, with this caveat.

## Stanza (M2)

- `stanza==1.14.0`
- Packages: `grc` / `perseus` and `grc` / `proiel` (processors `tokenize,pos,lemma`).
- Samples: frozen random-60 (seed **20260725**); fresh medical 5,000 (seed **20260827**).
- Lemma comparison: NFC + casefold + lunate/final sigma, **accents kept**.
- Honesty: both Stanza models and odyCy train on overlapping UD treebanks (Perseus, PROIEL);
  agreement overstates accuracy and is an upper-ish bound, never labeled “accuracy.”
- **Report both agreement numbers**, not vs-consensus alone: on the 5k sample, odyCy vs
  unanimous Stanza (perseus+proiel) is **94.17%**; pairwise odyCy↔perseus is **82.89%**.
  The vs-consensus figure is conditional on the two Stanza models agreeing, which selects
  easier tokens. **15.82%** of the 5k sample was dropped to alignment loss (flagged).

## LSJ citations (M3)

- Perseus LSJ XML parts `grc.lsj.perseus-eng{1..27}.xml` (same cache as H4).
- Kühn `(vol, page)` mapped from First1K TEI headers (`biblScope unit="vol"|"pp"`) + `<pb n>`
  (and `milestone unit="Kühn_page"` where present). 92 Kühn editions, 13,800 unique pages.
- **Relocation (F1):** a valid location is a token in the ±1 Kühn-page window whose
  **Morpheus reading set contains the LSJ headword** (accent-blind `lemma_to_lookup_key`).
  Quoted Greek in the LSJ entry is optional context confirmation only — never the target
  (LSJ often abbreviates the headword, so the quoted span is a collocate). odyCy lemmas are
  not used to locate (that route was circular). Uniqueness: exactly one Morpheus-validated
  token in the window; otherwise drop as `not_located` or `ambiguous`. A unique Morpheus
  surface that cannot be bound to a single odyCy lemma is `invalid_location_rejected`.
- **Scoring (F2):** accent-blind and accent-strict match rates with Wilson 95% CIs. This is
  **rare-stratum accuracy** (LSJ-cited vocabulary), not overall accuracy. The superseded
  quoted-collocate run (59.79% on 1231 rows) is invalid and must not be published.
- **Mismatch taxonomy (F3):** every accent-blind mismatch is classified as passthrough
  (lemma==surface, inflected), garble (no LSJ headword and no assigned surface within
  edit distance 2 — P3-2 hallucination test), variant-headword (odyCy lemma is itself an
  LSJ headword sharing the stem), or other/true substitution. Rates are reported with and
  without class (c).
- **Cache (F4):** `morpheus_by_surface.jsonl` is written as UTF-8 bytes. This repair found
  62 non-UTF-8/bad-JSON lines; surface keys could not be recovered from those bytes, so they
  were dropped (not silently counted as successful queries). The rewritten cache is strict
  UTF-8 (174,380 lines, 0 remaining non-UTF-8, 0 failed queries). Window surfaces missing
  from cache were re-queried during F1 pre-warm (50,514, failed=0).
- **Yield (repaired locator):** 7,706 Gal. citations → 4,746 mappable → 1,181 not located →
  892 ambiguous → 823 invalid_location_rejected → **1,850 scored**. Accent-blind match
  **62.32%** (1153/1850; Wilson 95% CI 60.09–64.50); accent-strict **53.95%** (998/1850;
  51.67–56.21). Mismatch taxonomy: passthrough 411, garble 135, variant-headword 15,
  other 136. Blind rate treating variant as non-error 63.14%; excluding variant 62.83%.
  G3a: 10/10 matched surfaces appear in the mapped page-window excerpt. G3b funnel fully
  reported (stages sum to 4,746). Do not publish the superseded 59.79% (N=1231) figure.
- Bias: LSJ-cited tokens skew toward lexicographically interesting (often rarer) vocabulary.

## Gates (this run)

- **G1a** 50/50 top-50 lemmas admissible.
- **G1b** 12/13 controls matched expectation. control (ἥπατος as lemma) is `admissible` under
  Morpheus — the analyzer lists ἥπατος among readings of that surface (same unanimous
  Stanza output in G2b). Recorded as a permissive-analyzer caveat, not a plumbing miss.
- **G1c** no_analysis 4.41% of tokens (below 15%); floor is paper-ready.
- **G2a** 0/20 encoding artifacts (pass). Work-level alignment loss mean 8.2% (flagged >5%);
  sample-level drop ~16% on the 5k — reported, not buried.
- **G2b** wrong-plants mostly contested; right-anchors control/control/control unanimous; several
  controls unaligned (tokenization divergence).
- **G3a** 10/10 relocated matched surfaces appear in the mapped page-window excerpt
  (form-on-page check; quoted LSJ text is not the target).

## CLTK / M4 / M5

Skipped (spec default).

## M5 — machine-adjudicated estimate (2026-11-05)

- Spec: `m5_llm_adjudication_spec.md` (repo root). Builder `pipeline/h3m/m5_build_sheets.py`
  (seed 20261105), scorer `pipeline/h3m/m5_score.py`. Artifacts under `h3m/m5/`.
- Sheet A: the frozen random-60 (seed 20260725) salted with the 13 controls per
  `h3_qc_protocol.md` §2 (73 rows, reviewer columns only). Private key written outside the
  repository during the run; published next to the results after scoring.
- Readers: two separate model sessions, `claude-fable-5-1` (reader 1) and `claude-opus-5-5`
  (reader 2), identical instructions (in the spec), no access to any other project file.
- Gate (protocol §3): both PASS, 13/13 controls each (control non-word caught; 6/6 unambiguous
  wrong-plants; 5/5 anchors; both accent-only controls marked strictly).
- Rate on the 60 random rows only: reader 1 **83.33%** (50/60; Wilson 95% 71.97–90.69),
  reader 2 **81.67%** (49/60; 70.08–89.44); no `unsure`. Raw agreement 98.33%, Cohen's κ 0.942.
  Ten tokens marked wrong by both; nine of those carry an M2 disagreement or misalignment flag;
  nine of ten proposed corrections coincide.
- Sheet B: the 942 M2 disagreement tokens, ±6-token context, candidate lemmas as A/B/C in a
  shuffled system-blind order; one reader (`claude-fable-5-1`). Scored by un-blinding the
  letters (`m5_disagreement_resolution.csv`). See `m5_summary.json` for the tally.
- Epistemic status: a machine-adjudicated estimate under a published prompt. Never pooled with
  M1–M3; does not replace the human two-reader check, which stays planned.
- Sheet B result: 942/942 rows answered (A 389, B 356, C 52, none 145, unsure 0). Un-blinded: the
  reader sided with odyCy on **42.68%** of rows (402/942; Wilson 95% 39.55–45.86). Split by the G2a
  label: on the 463 elision/tokenisation-artifact rows (δ’, τ’ …) odyCy was right 72.35% (335/463);
  on the 479 real-disagreement rows odyCy was right only **13.99%** (67/479; Wilson 11.17–17.38).
  Where the reader chose `none` it gave its own headword (145 rows, `reader_lemma_if_none`).
  Reading: the M2 real-disagreement set is a strong error detector for odyCy and the right first
  stop for a human reader. By POS, odyCy fared worst on VERB (68 right / 171 wrong) and NOUN
  (116 / 195), best on closed classes (ADP 28/2, CCONJ 30/3, PRON 39/9).
