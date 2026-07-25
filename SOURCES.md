# Sources — Phase 1 Census

Every field in `phase1/galen_ogl_census.{csv,json}` and its provenance. Fields fall into two
groups: **externally sourced** (traceable to a published/public dataset) and **author-supplied**
(approximate or classificatory, not citable as authoritative). Under-claiming is deliberate —
see the caveats.

## Externally sourced

| Field | Source |
|---|---|
| `tlg_number`, `edition_suffix`, `urn`, `title`, `languages` | **OpenGreekAndLatin / First1KGreek**, `catalog.json`, `master` branch (`github.com/OpenGreekAndLatin/First1KGreek`), fetched **2026-07-24**. |
| `wordcount` | Greek word count **as reported by the OGL/First1KGreek catalog** for that edition. Not independently recomputed for the census; treat as the catalog's figure. |
| `scaife_url` | Direct reader link into the **Perseus/Scaife** reader (`scaife.perseus.org`), constructed from the CTS URN. |

Author-number and citation conventions referenced (vocabulary, not data fields): Galen = TLG
author **`tlg0057`**; pseudo-Galenic works are catalogued under **`tlg0530`** and are listed
separately (`pseudo_galen_excluded_from_main_count` in the JSON), not folded into the main
word-count total.

## Author-supplied — NOT externally sourced, do not cite as authoritative

| Field | Status |
|---|---|
| `kuhn_volume_approx` | **Best-effort mapping only**, populated from general knowledge of the Kühn edition's layout; several entries are `TBD` / "not in Kühn". **Verify against a proper concordance** (TLG canon's Kühn mapping, or Fichtner's *Corpus Galenicum*) before citing any Kühn volume/page. |
| `category` | **Author-assigned** rough subject bucket (pharmacology, pathology, anatomy, …) for first-pass filtering. Not an OGL or TLG field; not a citable taxonomy. |

## Scope limits

- **Greek only.** This census covers machine-readable Greek in First1KGreek. It does not cover
  the Arabic/Syriac transmission (Galen surviving only in Arabic), which requires a different
  corpus and a separate effort.
- **Digital-availability census**, not a full corpus census. It deliberately does **not** carry
  Fichtner numbers, authenticity status, translation status, non-Greek witnesses, or
  critical-edition status. Those are future work.
- Gaps in the tlg-number sequence (e.g. tlg005, tlg026, tlg080, tlg088, tlg090–091, tlg097–098,
  tlg104–106, tlg108–113, and past tlg114) are not-digitized-here, fragmentary, or catalogued
  under different numbers — not independently re-verified per title.

## How to cite the underlying data
Open Greek and Latin Project, *First1KGreek* (`github.com/OpenGreekAndLatin/First1KGreek`),
CC-BY-SA. This census is a derived inventory; the Greek texts themselves remain the OGL
project's, under their license.
