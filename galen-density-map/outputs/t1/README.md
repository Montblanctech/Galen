# T1 author table — the 50 largest First1KGreek authors, odyCy vs Dilemma (2026-11-06)

`author_table_top50.csv` / `author_table_all.csv` / `author_table.md`, built by `pipeline/t1_author_table.py` from one `greek-lemma-audit run` per author (systems `reference` = the project's frozen odyCy 0.7.0 lemmas, `dilemma` = Open Greek Dilemma 1.3.15, lsj convention, guess off; M1 from the Galen Morpheus cache; M2 strict and article-convention-neutral). 16.4M tokens in all. Report only.

## What 50 authors say
| figure | median | range |
|---|---|---|
| M1 Morpheus floor, odyCy (strict) | 94.9 | 87.7 – 97.0 |
| M1 floor, Dilemma strict / article-neutral | 80.7 / **96.0** | 73.1–88.2 / 94.2–97.0 |
| odyCy–Dilemma agreement, strict / article-neutral | 70.1 / **84.4** | 60.2–75.5 / 77.3–88.3 |
| Morpheus cache gap (not-in-cache share) | 15.8% | 5.0 – 27.6% |

1. **The two lemmatizers agree on about 84% of tokens once the article convention is mapped, on every author, prose or scholia, 4th c. BCE or 12th c. CE.** The strict figure (≈70%) is the convention gap, not knowledge; the remaining 16% is the review queue for any author.
2. **Dilemma's floor is flat (94–97%) across all fifty; odyCy's drops exactly where the project started.** The three lowest odyCy floors in the table are the medical authors: Dioscorides 87.7, Pseudo-Galen 89.7, Hippocrates 91.8 (Galen itself 89.5, from the project's own run), against 94–97 for the philosophers, commentators and chroniclers. A neural lemmatizer trained on Perseus/PROIEL treebanks fails on the medical lexicon specifically; a lexicon-first one does not. That is the density map's premise, measured from the other side.
3. **The Morpheus cache was built for Galen**, so the odyCy floor is a partial figure outside Galen (gap 5–28%, flagged per author); the online fill (`--online`) would close it at about 0.5 s per surface.
4. Archimedes (60.2% strict agreement, lowest) and Ptolemy (73.1 Dilemma strict, lowest) are the notation-heavy texts: numerals and sigla, the same failure as Diophantus.

## Caveats
The odyCy lemmas are the v2.0 frozen run (model-consistency rule of the paper); Dilemma ran live; both systems' errors are correlated with text genre and neither is gold. One author (tlg4026) was re-run after a MemoryError in the loop; two per-author runs died under memory pressure from a concurrent Stoicheia job and were re-run. Author names from the Open Greek corpus catalog (CC BY-SA).
