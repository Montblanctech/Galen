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
- **Permissive-analyzer caveat (G1b C04):** Perseids Morpheus sometimes lists a variant or
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
- **G1b** 12/13 controls matched expectation. C04 (ἥπατος as lemma) is `admissible` under
  Morpheus — the analyzer lists ἥπατος among readings of that surface (same unanimous
  Stanza output in G2b). Recorded as a permissive-analyzer caveat, not a plumbing miss.
- **G1c** no_analysis 4.41% of tokens (below 15%); floor is paper-ready.
- **G2a** 0/20 encoding artifacts (pass). Work-level alignment loss mean 8.2% (flagged >5%);
  sample-level drop ~16% on the 5k — reported, not buried.
- **G2b** wrong-plants mostly contested; right-anchors C09/C11/C13 unanimous; several
  controls unaligned (tokenization divergence).
- **G3a** 10/10 relocated matched surfaces appear in the mapped page-window excerpt
  (form-on-page check; quoted LSJ text is not the target).

## CLTK / M4 / M5

Skipped (spec default).
