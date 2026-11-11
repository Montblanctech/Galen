# Phase 1 Deliverable: Galen Corpus Census (OGL / First1KGreek)

## What this is
A structured inventory of every Galen (TLG author `tlg0057`) edition digitized in
machine-readable Greek by the Open Greek and Latin Project's First1KGreek repository
(`github.com/OpenGreekAndLatin/First1KGreek`, `catalog.json`, master branch,
fetched 2026-07-24). It is the Phase 1 census gate — the check that determines
whether a Phase 2 terminology density map is feasible.

**Result: green light.** 97 distinct Galenic works (103 listed editions, some works
have more than one edition/witness), spanning roughly 2.4 million words of Greek
across pharmacology, therapeutics, pathology, anatomy, physiology, pulse theory,
and Hippocratic commentary. Coverage is not limited to *De simplicibus medicamentorum*
(`tlg0057.tlg075`, catalogued as books I–VI though the file holds all eleven), which Perseus/Scaife surfaces most prominently — every one
of these 97 works has its own Scaife reader URL and is independently fetchable.

## Files
- `galen_ogl_census.csv` — flat table, one row per edition. Opens in Excel/Sheets or
  loads into pandas.
- `galen_ogl_census.json` — the same data plus a summary block, structured for
  programmatic use (e.g. iterate `works[]`, pull `urn` to fetch each XML file, use
  `category` to restrict analysis to pharmacological/therapeutic works).

## Columns
| Column | Meaning |
|---|---|
| `tlg_number` | Galen's TLG work number (e.g. `tlg075`) |
| `edition_suffix` | Which edition/witness of that work (`1st1K-grc1`, `opp-grc1`, etc.) |
| `urn` | Full CTS URN, usable to construct the raw XML path or Scaife URL |
| `title` | Latin (or Greek, where no Latin title exists) work title as catalogued |
| `languages` | Which languages exist for that edition entry (grc/lat/eng/deu) |
| `wordcount` | Greek word count as reported by OGL's own catalog |
| `kuhn_volume_approx` | **Best-effort only** — see caveat below |
| `category` | Rough subject bucket (pharmacology, pathology, anatomy, etc.) for filtering |
| `scaife_url` | Direct reader link |

## Caveats — read before using downstream
1. **`kuhn_volume_approx` is not verified.** It was populated from general knowledge
   of the standard Kühn edition's layout for well-known works; several entries are
   marked `TBD` or "not in Kühn" where confidence was low. Before citing Kühn
   volume/page numbers in scholarly work, check this column against a proper
   concordance (e.g. the TLG canon's own Kühn mapping, or Fichtner's *Corpus
   Galenicum* bibliography) — it is not authoritative.
2. **`category` is a rough, author-assigned classification**, not an OGL or TLG
   field — useful for a first-pass filter, not a citable taxonomy.
3. **Pseudo-Galenic works are listed separately** (`pseudo_galen_excluded_from_main_count`
   in the JSON) and excluded from the main word-count total, since they are
   catalogued under a different TLG author number (`tlg0530`) and traditionally
   flagged as spurious. Downstream analysis should decide explicitly whether to
   include or exclude them.
4. **Gaps in the tlg-number sequence** (tlg005, tlg026, tlg080, tlg088, tlg090–091,
   tlg097–098, tlg104–106, tlg108–113, and everything past tlg114) are either not
   digitized here, fragmentary, or catalogued under different work numbers — not
   independently re-verified per title.
5. This inventory covers **Greek only.** It does not cover the Arabic transmission
   (Galen surviving only in Arabic) — a separate, much harder census against a
   different corpus (no equivalent open GitHub repository; it would require Arabic
   manuscript catalogues or the Graeco-Arabic Studies project's own materials).

## Catalog errors found by reading the files (2026-11-11)

The `title` and `wordcount` columns are Open Greek and Latin's catalog values, kept as reported. `phase1/census_file_check.py`
adds three columns from the TEI files themselves: `greek_words_in_file`, `books_in_file` and `catalog_note`. Six editions disagree
with their catalog entry:

- `tlg075` *De simplicium medicamentorum*: catalogued as books I–VI and 66,926 words; the file holds books I–XI and 133,948 Greek words.
- `tlg076` *De compositione medicamentorum secundum locos*: catalogued as books I–VI; the file holds books I–X.
- `tlg017` *De usu partium*: catalogued as books I–XI; the file holds books I–XVII.
- `tlg019` (opp-grc1), `tlg035` (1st1K-grc3) and `tlg073` (1st1K-grc2): catalog word counts 8,800, 849 and 2,723; the files hold 7,259, 480 and 2,251 Greek words.

Totals: 2,407,608 words by the catalog, 2,473,208 Greek words counted in the files.

