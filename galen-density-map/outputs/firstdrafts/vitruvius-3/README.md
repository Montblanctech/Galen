# Vitruvius, De architectura book 3: Latin pilot of the generic First Drafts pipeline (2026-11-12)

This is the first non-Galen and first Latin run of the First Drafts pipeline. It ran end to end from `pipeline/firstdrafts/configs/vitruvius-3.json`. It is a **calibration run**, not a first translation: Vitruvius has a complete English translation (Morgan 1914), so the draft can be scored against a human one.

- **Text:** Krohn's Teubner edition (1912), from Perseus canonical-latinLit.
  - 29 units, 4,059 words, 54 sections.
  - 209 target words, chosen by the lexicon-rarity rule. The dictionary is Lewis & Short; words are lemmatized with LatinCy, falling back to Collatinus.
- **Models and settings:** the same as the Galen runs. A `claude-fable-5-1`, B `claude-opus-5-5`, back-translation and judge `claude-sonnet-5-5`, direct mode.

## Results (`checks.json`)
| check | result |
|---|---|
| (a) back-translation term recall | 27 of 29 units pass (93.1%) |
| (b) two-model term agreement | 77.5% of 209 terms; 19 of 29 units pass the 70% rule |
| (c) salted Lewis & Short judge | gate **passed 20/20**; 21 of 29 units pass; out of range 17 of 206 items per rendering |
| (d) agreement with Morgan 1914 (51 of 54 sections, 200 targets) | A 64.0% [57.1–70.3], B 66.0% [59.2–72.2] |
| term-memory consistency | A 77.5%, B 84.3% |

- **Unit verdicts:** 23 pass, 6 fail. All are kept.
- **Comparison with Galen:** on *Composition of Drugs by Kind*, check (d) gave A 63.5% and B 66.4% against Marai's reference. The Latin figures land in the same place.

## Check (d) against Morgan, not pre-registered
- **Source:** M. H. Morgan, *Vitruvius: The Ten Books on Architecture* (Harvard 1914), public domain, text from Project Gutenberg eBook #20239.
- **Matching:** Morgan numbers his paragraphs per chapter, and his book 3 has the same 54 sections as Krohn (pr 4, ch. 1–5: 9, 8, 13, 5, 15). Each section was matched to its unit and to its first and last four Latin words.
- **Dropped:** 3 sections whose English did not match the Gutenberg text verbatim after normalisation.
- **Rule:** the pre-registered check (d) rule, via `reference_extra.py`.
- **What is in the repo:** loci and counts only (`checks_reference_morgan1914.json`). The Morgan text is not copied here.

## Known faults (reported, not patched)
- LatinCy lemma errors pass into the targets (*normam* → *normo*, *angulares* → *angulo*). 40 of 158 lemma keys have no Lewis & Short headword.
- *in antis* (pilasters, *antae*) resolved to *antes* ("rows of vines"). The judge item for it is therefore wrong, not the translation.
- A single model family translates, back-translates and judges, so the checks share lineage with the translators. Syntax, negation scope and argument structure are not measured.
