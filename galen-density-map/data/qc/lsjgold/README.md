# LSJ-Gold v0 — lemmatizer accuracy on the dictionary-cited stratum (2026-11-06, night build)

> **This is the build log, newest entries last; numbers in it are as of each entry.** The current release is **LSJ-Gold 0.1.2** (70,198 loci over 54 authors; `lsj_gold_v0_1_2.csv`): see [`release/lsj-gold-0.1.2/README.md`](../../../../release/lsj-gold-0.1.2/README.md); the 0.1.2 reading record is [`recheck_0_1_2/README.md`](recheck_0_1_2/README.md) and the leaderboard at https://montblanctech.github.io/Galen/lsj-gold/. The form → lemma list is [`release/lsj-gold-lexicon-0.1.2/`](../../../../release/lsj-gold-lexicon-0.1.2/).


Spec: `../../../../lsj_gold_benchmark_spec.md`. Scripts: `pipeline/lsjgold/relocate.py` (citations → token loci), `pipeline/lsjgold/score.py` (systems → table). Report only.

## What is here
| file | what |
|---|---|
| `lsj_gold_v0.csv` | **6,116 loci**: LSJ headword, accent-blind key, author, work, cited (Perseus) edition, CTS locator, the unit found in our First1K edition, the token index into the project's odyCy JSONL for that edition, the surface, the validation route (`morpheus` 5,505 / `quoted` 611), LSJ's quoted form, the LSJ part and entry key |
| `unlocated.csv` | the 7,983 citations into held works that did not become loci, with status: `not_located` 5,558 (mostly surfaces the Morpheus cache does not cover yet; the online fill is running), `ambiguous` 828 (two or more validated surfaces in the window), `locator_not_in_edition` 1,597 (LSJ cites a numbering our edition does not carry: Aristotle *Ath. Pol.*, the NT, Hippocrates by page) |
| `relocation_stats.json` | counts and the rule |
| `lsj_gold_scores.json`, `lsj_gold_table.md`, `lsj_gold_scored.csv` | the table and every locus with each system's lemma |
| `morpheus_lsjgold.jsonl` | Morpheus analyses fetched for this benchmark (online fill, Perseids), separate from the project's Galen cache |

## The table (v0)
| system | loci | match blind | strict | article-neutral | Hippocrates (2,275) | Aeschylus (3,477) | Sophocles (323) |
|---|---|---|---|---|---|---|---|
| odyCy 0.7.0 (frozen project run) | 6,116 | **69.7** [68.5–70.8] | 63.5 | 69.7 | **61.3** | 73.7 | 86.4 |
| Dilemma 1.3.15 (lsj convention) | 6,088 | **92.1** [91.4–92.7] | 88.9 | 92.1 | **93.4** | 91.5 | 89.2 |

By LSJ sense tier (odyCy): rich 72.6 (n 4,822), thin 58.7 (n 1,273). By validation route (odyCy): morpheus 72.8, quoted 41.7 (the quoted route selects the forms Morpheus could not analyse, which are the hard ones).

Reading: the Galen result (odyCy 61.5 / Dilemma 95.2 on 1,324 Kühn-relocated loci) **replicates on Hippocrates** with loci relocated by a different route (CTS locators, 2,275 loci: 61.3 / 93.4). On tragedy the gap narrows (Aeschylus 73.7 / 91.5, Sophocles 86.4 / 89.2): the neural system's failure is the medical lexicon, not rare words as such; the lexicon-first system is flat at 89–93 across genres.

## Validation of the relocation (blind, salted; `validation/`)
60 random loci + 10 anchors (surface = LSJ's quoted form) + 10 plants (same locus shown with a wrong headword of the same first letter), seed 20261107, two blind model readers (fable-5-1, opus-5-5), nothing from any system shown. Both readers: 10/10 plants rejected, 10/10 anchors accepted, and **60/60 random loci confirmed as instances of the headword** (relocation precision 100%, Wilson 95% 94.0–100). Zero disagreements between readers. Key and answers published after scoring. A human reader on the same sheet is the next step; the sheet is ready.

## Method in one paragraph
Citations carry `n="urn:cts:greekLit:tlgA.tlgW.<edition>:<locator>"`. For every (author, work) this project holds as a First1K TEI edition plus odyCy JSONL, the TEI is indexed by CTS unit (`<l n>` lines for drama, nested `div[@type=textpart][@n]` paths "1:2:2" for prose; repeated line numbers in lyric restarts get an unreachable suffix), the unit's own words (editorial notes, apparatus and sigla removed; glued punctuation stripped) are aligned to the JSONL token stream (exact, then accent-blind, then a three-token-confirmed resync), and in the cited unit ±1 sibling every surface is validated against the headword: Morpheus analyses contain it (accent-blind), or, when Morpheus has no analysis, the surface equals LSJ's quoted form. Exactly one validated surface → a locus; several → ambiguous; none → not located.

## Known limits of v0 (fix list)
- Aeschylus aligns at 80–97% (the TEI wraps lyric lines in strophe divs whose text must not be read twice; fixed); the *Septem* (tlg004) still loses a fifth of its tokens to apparatus interleaving.
- Aristotle *Ath. Pol.* and the New Testament: LSJ's numbering is not the edition's (`locator_not_in_edition`).
- The Morpheus cache is Galen's; the online fill (0.4 s per surface, Perseids) is the bottleneck for Aeschylus and Sophocles; v0.1 reruns the relocation when it has finished.
- Only works held in First1K editions; Plato, Homer, Herodotus (Perseus editions) would need their texts added.
- No human has validated a locus; the kit's blind salted sheet is the next step.
- odyCy lemmas are the frozen 2026-07 run; Dilemma is context-free on the surface. Convention differences are counted against both in the strict and blind columns.

## Perseus editions (v0.2 preview) — 2026-11-07
Added the 40 most-cited Perseus editions (`pipeline/lsjgold/perseus_tokens.py`; manifest `data/perseus_corpus/manifest.json`, licence CC BY-SA 4.0 from PerseusDL/canonical-greekLit; raw XML and token JSONL are gitignored and regenerable). **39 downloaded, 1 failed** (Diodorus tlg0060.tlg001: 404 at perseus-grc1/2/3). The edition listed in the works file (perseus-grc1) was a 404 for almost every work; perseus-grc2 was used (grc3 for Athenaeus). **2,605,501 tokens** (Iliad 111,881; Odyssey 87,170; Herodotus 184,944; Thucydides 150,123; Polybius 311,262; Strabo 285,252; Xenophon 6 works; Plato Republic-range tlg030/034 88,225/104,853; Aristophanes 5 plays; Pindar, Theocritus, Apollonius Rhodius, Athenaeus, Nonnus, Aristotle tlg010/035, Sophocles, Aeschylus). Tokens come from the unmodified 02_extract/greek_normalize functions plus TOKEN_RE, with edge punctuation stripped (the project's JSONL comes from spaCy, which splits it off) and no lemmas (odyCy was not run; the odyCy row therefore scores only First1K-held works). For works held in both First1K and Perseus (Aeschylus x5, Sophocles tlg003) the First1K edition keeps priority.

Code changes (all small): `relocate.py` held_works() gains the Perseus pair after the First1K/Galen pairs, and `passage_index` parses with `remove_comments=True, remove_pis=True` (a Perseus `<l>` contained an XML comment node and crashed the indexer); `score.py` adds the Perseus raw_xml dir to `held` and writes the CSV header as the union of row keys (Perseus rows have no odyCy strict field and crashed the writer).

**Numbers.** Loci 6,116 -> **31,046** (citations into held works 14,099 -> 168,946). Caution: the v0 run was restricted to four authors; the new run is unrestricted over all 905 held works and the Morpheus cache has grown since, so part of the rise (e.g. Aeschylus 3,477 -> 6,923, Hippocrates 2,275 -> 2,470) is not Perseus. Loci in Perseus-only works: 21,289. Whole run: located 31,046, ambiguous 5,500, not_located 58,020, locator_not_in_edition 74,380 (no online Morpheus lookups; cache only).

| author (Perseus-only works) | located | ambiguous | not_located | locator_not_in_edition |
|---|---|---|---|---|
| Thucydides | 5,146 | 1,285 | 5,036 | 789 |
| Sophocles (7 works added) | 5,818 | 299 | 6,282 | 1,752 |
| Aristophanes | 3,343 | 193 | 4,945 | 210 |
| Xenophon (4 works) | 2,965 | 1,108 | 6,824 | 259 |
| Polybius | 2,203 | 219 | 4,657 | 232 |
| Herodotus | 1,620 | 1,255 | 15,582 | 1,784 |
| Homer | 171 | 16 | 2,116 | 36,983 |
| Athenaeus | 6 | 4 | 631 | 2,630 |
| Plato | 2 | 8 | 18 | 9,435 |
| Strabo | 0 | 95 | 3,679 | 101 |

**What did not work (reported, not patched).** The indexer keys `<l n>` by bare line number and textparts by their own path, so it cannot reach Homer's book:line citations, Plato's Stephanus pages, Pindar/Theocritus/Apollonius/Nonnus (book/ode:line), Aristotle tlg010/035, Athenaeus, tlg0526 or Sophocles tlg008: 15 of the 39 works are marked `supported: false` in the manifest. Homer's 171 loci are bare-line coincidences validated by headword only (the window can be in another book), so treat them as unplaced; Plato and Homer, the main goal, are therefore NOT yet in the benchmark. Fix for v0.3: key lines as `book:line` and Stephanus `<milestone unit="section">`. Euripides was not in the top 40 and is not downloaded. Herodotus and Strabo lose most citations to `not_located` (Morpheus cache has few of their surfaces; an online fill would help).

**Dilemma per author (blind %, n)**: Aeschylus 90.51 (6,904); Sophocles 89.47 (6,117); Thucydides 89.64 (5,145); Aristophanes 88.51 (3,332); Xenophon 90.29 (2,965); Hippocrates 93.98 (2,459); Polybius 90.10 (2,203); Herodotus 86.60 (1,620); Homer 87.13 (171, unreliable placement). Overall Dilemma 89.94 [89.60-90.27] over 30,980 loci (strict 87.09, article-neutral 89.99); odyCy 69.25 over 6,770 First1K-held loci (Perseus works have no odyCy lemmas). Dilemma is flat at 87-94 across Attic prose, comedy, tragedy, history and medicine. Leaderboard/table headers show raw TLG ids for the new authors (tlg0003 Thucydides, tlg0019 Aristophanes, tlg0032 Xenophon, tlg0543 Polybius, tlg0016 Herodotus, tlg0012 Homer). The regenerated v0 files overwrite the 6,116-locus outputs (kept in git history).

## v0.2 preview, second pass (2026-11-07 ~02:00): Homer and Stephanus indexing fixed
Lines inside a textpart path are keyed with the path (Homer "1:5"); Stephanus `<milestone unit="section" n="327a"/>` sections are units; a block that contains units no longer has its text read twice. Result: **96,462 loci over 54 authors** (Homer 20,330, Aeschylus 6,923, Sophocles 6,142, Thucydides 5,155, Aristophanes 3,346, Xenophon 2,968, Hippocrates 2,654, Plato 2,238, Polybius 2,209, Pindar 1,717, Herodotus 1,623, Theocritus 911, Apollonius Rhodius 768, Nonnus 231 …). Dilemma blind match **87.8% [87.6–88.0]** overall; highest on Hippocrates (94.4), 89–90 on Attic prose and drama, lowest on the late/epic poets (Theocritus 76.8, Apollonius 68.9, Nonnus 48.9: dialect and epic vocabulary). odyCy is scored only where the project has its lemmas (62,400 First1K loci: 74.8). Known alignment gaps to fix next: Plato *Laws* (4%) and Herodotus (18%) — their page/section wrappers still interleave text; Homer 95.7%, *Republic* 97.6%, Hippocrates 99.9%, Aeschylus 97%.

## v0.3 (2026-11-07, day): the aligner fixed, 257 editions, 96,462 loci over 54 authors

**What changed.** (1) `relocate.py` rebuilt: a one-pass, document-order passage index (text belongs to the last section marker seen, across speech, paragraph and page wrappers; Stephanus sections; lines keyed book:line) and a confirmed-jump aligner (a forward jump must be confirmed by the next token). Plato *Laws* 4% → 98% of tokens aligned, Herodotus 18% → 99.6%, Strabo 4% → 97%, Euripides 56% → 99%, Xenophon 62% → 98%; no work got worse (`align_check.py`). (2) Round 2 of the Perseus fetch (`perseus_tokens_more.py`): every LSJ-cited work with 50 or more citations and no held edition was tried at perseus-grc1/2/3 and First1K; 217 found, one missing (Xenophon tlg0032.tlg015), 2.45M new tokens; the holdings are now 257 editions. (3) The scorer checks the cached surface against the gold surface at the index and counts a mismatch as missing (`misaligned_surface`): the kit-made Stanza caches for First1K works were off the project's token stream and are replaced by caches built on it (`perseus_caches.py --first1k`).

**Numbers.** 249,090 LSJ citations into held works; located **96,462** (Morpheus 67,898, quoted form 28,564); ambiguous 12,816; not located 113,636; locator not in edition 26,176. Authors with 100 or more loci: 34.

**Dilemma** 87.84 [87.63–88.05] on 96,281 loci (strict 84.88, article-neutral 87.89). **odyCy** 74.82 [74.48–75.16] on 62,400 loci (First1K lemmas from the project's frozen run; Perseus works lemmatised token-by-token by `perseus_caches.py`, caches still being filled). Stanza and Stoicheia rows carry only the works whose aligned caches exist so far and are provisional.

| author | loci | Dilemma | odyCy |
|---|---|---|---|
| Homer | 20,329 | 85.84 | 76.47 |
| Aeschylus | 7,776 | 90.29 | 72.66 |
| Herodotus | 7,627 | 87.59 | 82.25 |
| Plato | 7,590 | 89.97 | 72.32 |
| Euripides | 7,284 | 87.9 | — |
| Sophocles | 6,694 | 89.38 | 82.55 |
| Aristophanes | 5,974 | 88.68 | 66.37 |
| Xenophon | 5,934 | 90.09 | 73.87 |
| Thucydides | 5,155 | 89.64 | 75.29 |
| Demosthenes | 3,530 | 90.28 | — |
| Hippocrates | 2,654 | 94.4 | 61.68 |
| Pindar | 2,440 | 85.01 | 67.91 |
| Polybius | 2,209 | 90.18 | — |
| Hesiod | 1,448 | 84.11 | — |
| New Testament | 1,218 | 90.15 | — |
| Isocrates | 1,216 | 89.23 | — |
| Theocritus | 935 | 76.77 | 53.4 |
| Apollonius Rhodius | 770 | 68.88 | 43.64 |
| Lysias | 737 | 90.37 | — |
| Strabo | 652 | 79.72 | — |
| Antiphon | 631 | 90.02 | — |
| Aeschines | 533 | 89.68 | — |
| Andocides | 451 | 91.57 | — |
| Homeric Hymns | 451 | 79.33 | — |

**Coverage** (`coverage.py`, `docs/lsj-gold/coverage.html`): of 254,849 LSJ citations with a CTS URN, 249,090 now point into a held edition; what remains is mostly works with under 50 citations.

**Still open (reported, not patched).** The not-located count (113,636) is mostly Morpheus coverage (the cache was built for Galen; `--online` fills it at about 0.5 s a surface) and citations by a locator scheme the edition does not carry. Stanza and Stoicheia rows over the whole benchmark waited for (both landed: Stanza 11/07, Stoicheia 11/08 12:09, below) their cache loops. Validation (60/60, 20/20 controls) was done on the v0 loci; a new blind sheet over the enlarged set is the next check.

**Second blind check (v0.3 loci, `validation_v03/`, seed 20261108, 60 random + 10 anchors + 10 plants over the 96,462-locus set; two model readers, opus-5-5 and sonnet-5-5, each in its own session with nothing but the sheet).** Both passed the control gate (anchors 9/10 and 10/10, plants 10/10 and 10/10). Random loci confirmed: 57/60 (95.0% [86.3–98.3]) and 56/60 (93.3% [84.1–97.4]); agreement κ 0.85. The three loci both readers rejected, all in the key published after scoring: two came through the quoted-form route where LSJ's quote was a neighbouring word, not a form of the headword (ἀνούτατος cited under ἄβλητος, Il. 4.540; ὀδύρματα under πανδάκρυτος, Soph. Tr. 51); one is an accent-blind key collision (τί read as τίς where the gold says τις, Soph. Ph. 643). Reported, not removed: this is the benchmark's measured error rate on this version. **Rule change v0.3.1 from this finding:** a quoted-form validation must share the headword's first two letters (accent-blind), the same test the multi-word route already applied; the relocation is rerun under that rule and the counts below this line are the rerun's. The τις/τίς class (distinct LSJ headwords with one accent-blind key) stays as a known limit of accent-blind matching.

**v0.3.1 rerun (2026-11-07 14:48).** Located **93,926** (was 96,462: the rule drops 2,536 quoted-route loci; ambiguous 11,943, not located 117,045, locator not in edition 26,176). Dilemma **90.12** [89.93–90.31] on 93,750 loci (was 87.84): the dropped loci were disproportionately wrong placements, which is what the blind sheet predicted. Dilemma by validation route: Morpheus 92.99, quoted form 82.26, so the quoted route is still the weaker one and is reported as its own column. odyCy 76.60 [76.27–76.92] on 63,679 loci (Morpheus route 84.31, quoted 56.81). Stanza and Stoicheia rows remain partial until their cache loops end. 54 authors, 34 with 100 or more loci.

**Stanza rows (15:45, caches built on the project's token stream by `perseus_caches.py`, Perseus works and 22 First1K works).** Stanza-Perseus 79.56 [79.30–79.83] and Stanza-PROIEL 72.03 [71.74–72.32] on 90,452 loci (3,474 missing: works without a cache). By citation frequency of the headword (`lsj_citation_counts.json`, 48,656 LSJ entries with a CTS citation: 22,682 cited once): once-cited loci Dilemma 83.81, Stanza-Perseus 53.28, odyCy 54.60, Stanza-PROIEL 50.81; cited 6+ times 90.71 / 82.48 / 78.93 / 74.46. Stanza-Perseus lowest on Quintus Smyrnaeus 52.6, Nonnus 60.4, Apollonius 61.2; highest Hesiod 89.3, Sophocles 87.7, Homer 85.5.

**Final rows of the day (17:00, every cache complete).** On the same 90,452 loci (3,474 loci lie in works without a cache): Dilemma 90.12, Stanza-Perseus 79.56, odyCy 75.70 [75.42–75.98], Stanza-PROIEL 72.03. odyCy by author: New Testament 92.2, Hesiod 85.9, Sophocles 84.3, Herodotus 84.3 at the top; Hippocrates 62.2, Theocritus 59.3, Nonnus 53.7, Apollonius 51.4, Quintus Smyrnaeus 38.4 at the bottom. Once-cited headwords: Dilemma 83.8, Stanza-Perseus 53.3, odyCy 52.6, Stanza-PROIEL 50.8.

**Stoicheia row (18:10, caches built on the project's token stream under `.venv-sto`, 22 First1K works).** 87.64 [86.86–88.38] on 7,233 loci (strict 82.03): Aeschylus 93.10 (n 4,215; Dilemma 92.18, Stanza-Perseus 80.62, odyCy 73.71), Sophocles 94.39 (n 321; Dilemma 90.94), Hippocrates 78.30 (n 2,654; Dilemma 94.89, Stanza-Perseus 63.75, odyCy 62.17). Once-cited headwords 78.0, cited 6+ 91.0. A 2026 diffusion model closes the gap to the lexicon on tragedy and halves it on medical prose; Homer, Herodotus and the Republic are being cached now.

**Stoicheia row, extended (19:35; Homer, Herodotus, Republic added).** 87.57 [87.23–87.91] on 36,542 loci: Sophocles 94.39 (Dilemma 90.94), Aeschylus 93.10 (92.18), Plato 89.75 (90.68), Homer 88.39 (88.05), Herodotus 84.67 (89.51), Hippocrates 78.30 (94.89). Once-cited headwords 74.98, cited 6+ 89.22. Level with the lexicon on epic and tragedy, behind it where the vocabulary is technical.

**Stoicheia row, full (2026-11-08 12:09; every held edition cached overnight under `.venv-sto`, 278 cache files, surface check 0 misaligned).** **87.69** [87.48–87.91] on **90,452** loci, the same loci as the three treebank-trained systems (strict 83.46, article-neutral 87.70; 3,474 loci without a lemma). Second on the table: 2.4 points behind Dilemma (90.12), 8.1 ahead of Stanza-Perseus (79.56). By author against Dilemma: above on Hesiod 94.08 (88.08), Sophocles 93.77 (90.94), Aeschylus 93.10 (92.18); level on Homer 88.39 (88.05), Andocides 92.38 (92.38), Isaeus 92.75 (92.75); 1–4 points below on the prose authors and Euripides (Xenophon 90.49 vs 91.36, Thucydides 89.38 vs 90.75, Plato 88.05 vs 90.68, Euripides 87.49 vs 91.51, Herodotus 84.67 vs 89.51, Aristophanes 84.91 vs 90.56); 16 below on Hippocrates 78.30 (94.89); 10–25 below on the late epic (Nonnus 70.47 vs 81.88, Apollonius Rhodius 63.43 vs 79.94, Quintus Smyrnaeus 53.38 vs 78.63). Strata: Morpheus-validated 93.85, quoted-form 70.95; LSJ tier rich 89.15 / thin 75.26 / absent 54.81 (n 104); cited once **67.64** (n 2,027; Dilemma 83.81, Stanza-Perseus 53.28, odyCy 52.64, Stanza-PROIEL 50.81), cited 2–5 74.76, cited 6+ 89.63. The 36,542-loci figures of 11/07 (87.57, once-cited 74.98) were the six early authors and stand above as history; the once-cited figure fell by 7 points when the orators, Euripides, Aristophanes and the late epic came in. Medical subset (`medical_gap/`): Stoicheia misses 21.71% of the 2,695 Hippocrates and Galen loci against 12.31% overall. Failure catalogue now covers all five systems (`failures/`). Paper tables, leaderboard page, release folder and coverage map regenerated by `score_chain.ps1`.
