# Translation status of the Galen census (phase1), built 2026-11-09

Three columns added to `galen_ogl_census.csv` and to every entry of `galen_ogl_census.json`: `translation_status`, `translation_source`, `translation_note`. Every existing column is untouched. Built by `build_translation_status.py`; report only, nothing guessed: where no source supports a claim the value is `unknown`.

## Counts (97 distinct tlg0057 works, 103 edition rows; words = OGL Greek word count of the first listed edition)

| status | works | editions | Greek words |
|---|---|---|---|
| `english` | 67 | 71 | 1,387,004 |
| `other_modern` | 19 | 20 | 449,717 |
| `partial` | 6 | 6 | 508,883 |
| `latin_only` | 0 | 0 | 0 |
| `none` | 3 | 3 | 13,348 |
| `unknown` | 2 | 3 | 1,766 |
| total | 97 | 103 | 2,360,718 |

### Works with no modern-language translation in either catalogue (`none`)

- tlg047 *De totius morbi temporibus* (Kühn VII, 3,538 words)
- tlg072 *De purgantium medicamentorum facultate* (Kühn XI, 2,973 words)
- tlg086 *In Hippocratis vel Polybi Opus de Salubri Victus Ratione Privatorum Commentarius* (Kühn XV, 6,837 words)

### `partial` (a source states that only part of the work is translated)

- tlg056 *De difficultate respirationis*: No complete translation in any modern language; one English paragraph exists.
- tlg075 *De simplicium medicamentorum temperamentis ac facultatibus I-VI*: No complete modern translation of books I-XI; Manco thesis (bks VI-VIII, French) unpublished. First1KGreek carries books I-VI only.
- tlg076 *De compositione medicamentorum secundum locos I-VI*: Spanish of book II only; books I and III-X untranslated in any modern language.
- tlg077 *De compositione medicamentorum per genera*: No complete translation in any modern language; English of parts exists.
- tlg087 *In Hippocratis De victu acutorum*: French of book I only; books II-IV untranslated in any modern language.
- tlg092 *In Hippocratis Aphorismos*: Every book has some modern translation; GOHA (BBAW/HU Berlin) is editing bks I-IV with translation; P. N. Singer's English of bk I announced. Not a First Drafts candidate.

### `unknown` (the sources disagree or are silent; not a claim either way)

- tlg084 *De substantia facultatum naturalium fragmentum*: GV lists no translation but Fichtner lists T line(s); their language and coverage are not coded, so the status is unknown rather than none

## Method

1. **Galenus verbatim catalogue** (Rousseau, Glorieux, Taaffe; https://galenus-verbatim.github.io/mera-galeni-folia/), fetched 2026-11-09 and parsed into `translation_sources/galenus_verbatim_catalogue_2026-11-09.json`: per work the Fichtner entry number, the Kühn locus, the critical editions and the *translationes recentiores*, each with ISO-639 language codes (e.g. `Singer, 1997 (grc;eng)`). The codes decide the status: any `eng` → `english`; any other modern language → `other_modern`; only `lat` → `latin_only`.
2. **Fichtner, *Corpus Galenicum*** (BBAW, edition 2023/12, https://cmg.bbaw.de/fileadmin/Webdateien/Dateien/Galen-Bibliographie.pdf), text extracted from the PDF and parsed per entry into `translation_sources/fichtner_translations_2026-11-09.json`: the lines tagged `T` (translation; also `E,T`, `T,K`) joined to the work by its `TLG-ID` line, or by Fichtner's entry number via Galenus verbatim where the TLG id did not parse. Fichtner does not code the language, so a Fichtner T line alone never yields `english`/`other_modern`: a work with no GV translation and at least one Fichtner T line is `unknown`, and the lines are quoted in `translation_source` for a reader to judge. A work with no GV translation and no Fichtner T line is `none`.
3. **Overrides** (`translation_sources/overrides.csv`), each with its citation: Johnston & Papavramidou 2024 (*Galen on the Pulses*, De Gruyter, doi:10.1515/9783110612677) for the four long pulse treatises (GV lists it under tlg059 only); the partial translations named in the research pass `drafts/untranslated_galen_research.md` (Simples bk I ch. 1–3 French; Composition by Place bk II Spanish; Victu acutorum bk I French; Aphorisms commentary bk VI Italian); Composition by Kind confirmed `none` by Fichtner entry 82 and Zainaldin et al. 2026 (arXiv:2602.24119).
4. Kühn's own facing Latin (present for every Kühn work) and the medieval Arabic, Syriac, Hebrew and Latin versions Fichtner lists under *Übers.* are not counted as translations. `partial` is assigned only where a source states partial coverage; the catalogues do not code completeness, so an `english`/`other_modern` listing may in fact be a selection (the note says so on every such row).
5. Works in the census but in neither catalogue, and pseudo-Galenic works (tlg0530, JSON only) with no catalogue data, are `unknown`.

## Known limits

- The catalogues are incomplete (the 2024 pulse volume was missing from GV for three of four works; found by the research pass). A `none` is a statement about two catalogues on 2026-11-09, not a proof.
- German medical dissertations in Fichtner's T lines are often translations of a few chapters; they are quoted, not classified.
- The Cambridge Galen Translations series, Johnston's Loebs and Singer's volumes enter only through the catalogues' listings (GV lists Johnston 2016/2018/2020, Singer 1997/2013, van der Eijk 2018 under the works they cover); no independent table of contents was consulted.
