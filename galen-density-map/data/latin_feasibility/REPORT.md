# Latin twin of LSJ-Gold: feasibility (Lewis & Short)

All numbers computed by `pipeline/lsjgold/latin_ls_counts.py`, `latin_ls_editions.py`, `latin_ls_report.py` from the files in this folder (`ls_citation_counts.json`, `editions.json`, `cll_tree.json`, `lexica_tree.json`). Nothing committed or pushed.

## Source

- PerseusDL/lexica, `CTS_XML_TEI/perseus/pdllex/lat/ls/`: `lat.ls.perseus-eng1.xml` (77,249,035 B, deprecated, Greek in beta code, header says do not use) and `lat.ls.perseus-eng2.xml` (77,415,379 B, Greek in Unicode, the one counted). Both downloaded here.
- Licence: CC BY-SA 4.0 (repo `license.md`, `<availability>` in the eng2 header); reuse must credit the Perseus Digital Library with a link, identify each text and its GitHub repo, and corrections go back to Perseus. Share-alike applies to any derived release of the lexicon text; benchmark gold built from it should carry the same licence.
- 51,645 `<entryFree>` entries (4,977 bibls inside L&S entries cite greekLit URNs and are excluded).

## Citation counts (`urn:cts:latinLit:(phi|stoa)NNNN.(phi|stoa)NNN[.edition][:locator]`)

- Entries with at least one Latin CTS citation: **30,018** of 51,645
- Latin CTS citations (work-level at least): **280,550**, across **217** works and **49** authors
- Citations per entry: 1 = 10,488 (34.9%); 2-5 = 9,719 (32.4%); 6+ = 9,811 (32.7%)
- Of those 280,550, 5,758 have a work URN but no locator (unusable as gold; e.g. phi1236.phi001 2,678 and phi1044.phi001 1,426, both absent from the repo tree)
- Bibls that are NOT usable as URN gold: 18,416 plain-text `n` (`Dig. 1.2.3`, `Sil. Ital. 3.4`, `Plin. Ep.`, `Justin`, `Hor. Ars.`, `Aug. Conf.` ...), 72,936 bibls with no `n` at all, 3,777 author-only URNs (largest: phi0684 2,432, phi1245 398, stoa0043 288; see `bibls_author_only_by_author`). Total bibls seen 380,656; URN-resolvable Latin share 73.7%. A mapping table from abbreviation to work (Plin. Ep., Justin, Sil. Ital. ...) could recover part of the plain-text group (top labels listed in the JSON, key `bibls_plain_text_by_label_top60`).
- Locator schemes seen (the `locator_depth_by_work` field): colon-separated, 2 levels (book:line, e.g. Aen., Met., Lucr.; 8,5xx Aeneid), 3 levels (book:chapter:section, e.g. Livy, Pliny NH, Cicero, Quintilian), occasional 4-5 levels (Cic. de Or. with the 4,012 cites of the form `Orat::N:N:N` (empty second level); Plautus act:scene:line; Cic. Fam./Att. book:letter:section). Fragments appear as `fr::N:N:N`. Edition tag in the URN: `perseus-lat1` for most Cicero/Virgil/Ovid/Plautus cites, none at all for Pliny NH, Livy, Quintilian, Lucretius, Caesar BC, Curtius, `perseus-lat2` for Sallust/Propertius/Cic. Div., `perseus-lat3` for Celsus; the repo files are mostly `perseus-lat2` (lat1 returns 404 for almost all), see `work_versions` in the JSON.

## Top 40 works

| # | Author | Work | phi id | Citations | Latin edition in canonical-latinLit (file, bytes) |
|--:|---|---|---|--:|---|
| 1 | Pliny, the Elder | Naturalis Historia | phi0978.phi001 | 23,381 | perseus-lat2 (13,243,638) |
| 2 | Titus Livius (Livy) | Ab urbe condita | phi0914.phi001 | 23,100 | perseus-lat2 (7,295,656); perseus-lat3 (4,684,342); perseus-lat4 (5,951,469); perseus-lat5 (3,012,877) |
| 3 | Quintilian | Institutio Oratoria | phi1002.phi001 | 11,959 | perseus-lat2 (2,683,107) |
| 4 | Ovid | Metamorphoses | phi0959.phi006 | 10,176 | perseus-lat2 (931,299) |
| 5 | P. Vergilius Maro (Virgil) | Aeneid | phi0690.phi003 | 8,526 | perseus-lat2 (694,937) |
| 6 | Lucretius | De Rerum Natura | phi0550.phi001 | 6,781 | perseus-lat1 (459,795) |
| 7 | Cicero, Marcus Tullius | Letters to his Friends | phi0474.phi056 | 5,664 | perseus-lat2 (1,124,134) |
| 8 | Cicero, Marcus Tullius | Letters to Atticus | phi0474.phi057 | 5,366 | perseus-lat2 (1,327,999) |
| 9 | Columella, Lucius Junius Moderatus | (not in repo) | phi0845.phi001 | 5,260 | **not found** |
| 10 | Julius Caesar | Gallic War | phi0448.phi001 | 5,177 | perseus-lat2 (691,991) |
| 11 | Tacitus, Cornelius | Annales | phi1351.phi005 | 5,107 | perseus-lat2 (778,483) |
| 12 | Cicero, Marcus Tullius | In C. Verrem | phi0474.phi005 | 4,655 | perseus-lat2 (1,320,692) |
| 13 | Gellius, Aulus | Noctes Atticae | phi1254.phi001 | 4,389 | perseus-lat2 (1,469,718) |
| 14 | Cicero, Marcus Tullius | On Oratory | phi0474.phi037 | 4,300 | perseus-lat2 (566,539) |
| 15 | Horace | Carmen Saeculare | phi0893.phi002 | 4,039 | perseus-lat2 (7,857) |
| 16 | Juvenal | Saturae | phi1276.phi001 | 3,845 | perseus-lat2 (366,144) |
| 17 | Cicero, Marcus Tullius | Tusculanae Disputationes | phi0474.phi049 | 3,597 | perseus-lat2 (760,670) |
| 18 | Martial | Epigrammata | phi1294.phi002 | 3,524 | perseus-lat2 (960,064) |
| 19 | Horace | Satires | phi0893.phi004 | 3,198 | perseus-lat2 (176,460) |
| 20 | P. Vergilius Maro (Virgil) | Georgics | phi0690.phi002 | 3,036 | perseus-lat2 (176,105) |
| 21 | Cicero, Marcus Tullius | De Officiis | phi0474.phi055 | 3,008 | perseus-lat2 (309,457) |
| 22 | Cicero, Marcus Tullius | De Natura Deorum | phi0474.phi050 | 2,931 | perseus-lat2 (328,419) |
| 23 | Julius Caesar | Civil War | phi0448.phi002 | 2,840 | perseus-lat2 (331,853); perseus-lat3 (260,700) |
| 24 | (not in repo) | (not in repo) | phi1236.phi001 | 2,678 | **not found** |
| 25 | Cicero, Marcus Tullius | Philippicae | phi0474.phi035 | 2,661 | perseus-lat2 (705,704) |
| 26 | Curtius Rufus, Quintus | Historiarum Alexandri Magni | phi0860.phi001 | 2,648 | perseus-lat2 (912,268) |
| 27 | Tacitus, Cornelius | Historiae | phi1351.phi004 | 2,626 | perseus-lat2 (453,247) |
| 28 | Cicero, Marcus Tullius | de Finibus Bonorum et Malorum | phi0474.phi048 | 2,570 | perseus-lat2 (532,712) |
| 29 | Ovid | Fasti | phi0959.phi007 | 2,488 | perseus-lat2 (383,373) |
| 30 | Propertius, Sextus | Elegiae | phi0620.phi001 | 2,438 | perseus-lat3 (230,572) |
| 31 | Cicero, Marcus Tullius | De Republica | phi0474.phi043 | 2,433 | perseus-lat2 (214,263) |
| 32 | Sallust | Bellum Iugurthinum | phi0631.phi002 | 2,308 | perseus-lat3 (186,280); perseus-lat4 (162,606) |
| 33 | Cicero, Marcus Tullius | De Divinatione | phi0474.phi053 | 2,179 | perseus-lat3 (252,509); perseus-lat4 (268,227) |
| 34 | Seneca, Lucius Annaeus | Epistulae | phi1017.phi015 | 2,094 | perseus-lat2 (1,274,876) |
| 35 | Celsus, Aulus Cornelius | De Medicina | phi0836.phi002 | 2,046 | perseus-lat4 (741,623); perseus-lat5 (893,899); perseus-lat6 (833,266) |
| 36 | Vitruvius Pollio | On Architecture | phi1056.phi001 | 1,991 | perseus-lat2 (552,982) |
| 37 | Lucan | Civil War | phi0917.phi001 | 1,985 | perseus-lat2 (648,640) |
| 38 | Cicero, Marcus Tullius | Brutus | phi0474.phi039 | 1,919 | perseus-lat2 (317,575) |
| 39 | (not in repo) | (not in repo) | phi0684.phi001 | 1,832 | **not found** |
| 40 | Statius, P. Papinius (Publius Papinius) | Thebais | phi1020.phi001 | 1,748 | perseus-lat2 (887,747) |

Top-60 notes: 53 of the top 60 have a Latin edition in the repo. Missing from the top 60: phi0845.phi001 (5,260), phi1236.phi001 (2,678), phi0684.phi001 (1,832), phi1348.phi012 (1,679), phi1044.phi001 (1,426), phi0060.phi001 (1,357), phi0474.phi044 (1,287). phi0845.phi001 (Columella: author folder exists, no work folder), phi1236.phi001, phi0684.phi001, phi1044.phi001, phi0060.phi001, phi1348.phi012 (Suetonius, work not in tree) are not in the repo tree; Cic. Leg. (phi0474.phi044) is in the tree without a Latin XML. For the 60 works the raw-URL probe results (HTTP 200/404 for perseus-lat1 and perseus-lat2) are in `editions.json` under `raw_probe`; the git tree listing is authoritative and agrees with them.

## Held-able share

- Works with a Latin TEI file in canonical-latinLit: 161 of 217 cited works; **253,341 of 280,550 citations = 90.3%**
- Top 60 works carry 78.6% of all Latin citations; 73.1% (of all) sits in the top-60 works that have an edition
- Strict edition-tag match (URN tag present among the repo files): 87,042 = 31.0%. The rest need a tag-to-file map (lat1 -> lat2/lat3 etc.), same book/chapter scheme in most cases.
- Works without any Latin file: 56 works, 27,209 citations

## What changes in relocate.py

1. Tokenization/normalisation: Greek used beta-code/diacritic folding; Latin needs only lowercase, u/v and i/j folding (L&S headwords use both), macron stripping (L&S headwords carry macrons in `<orth>`), enclitic -que/-ne/-ve handling.
2. Edition loader: Greek held editions use the manifest layout in coverage.py; Latin needs a manifest of canonical-latinLit data/phiNNNN/phiNNN/*-lat*.xml, with the edition-tag mapping above (several works have lat2-lat6 as split parts: Livy lat2-lat5 are decades, Sallust lat3/lat4, Celsus lat4-6; these would be merged or selected by locator range).
3. Locator resolver: CTS refs in these TEI files use nested `<div type="textpart" subtype="book|chapter|section|line">`, so a generic ref -> node lookup (n attributes) replaces the Greek-specific one; handle prose (book:chapter:section) vs verse (book:line), the empty `Orat::` segments, the `fr::` fragment forms and drama (act:scene:line).
4. Match window: L&S cites a passage to the line/section; relocation then searches that window for a lemma-consistent token. The prose chapter-section windows are long (Pliny NH, Livy) so scoring must use a window of surrounding sections as the Greek one does.
5. Validator: the Greek benchmark checks relocated tokens with Morpheus-style analysis. Latin needs a lemma-consistent test of 'token t is a form of headword h'. Candidates:
   - Whitaker's Words (Ada binary or the Python ports; `whitakers-words`/`words` executables) fully offline, fast, gives all analyses per form, classical-biased dictionary; good as an 'accepts' oracle (set membership of analyses).
   - CLTK Latin lemmatizer (backoff lemmatizer, offline after one model download from GitHub; lower accuracy, single lemma per form, needs lemma normalisation to L&S headword).
   - LatinCy (spaCy models, pip wheels from Hugging Face; offline after download; context-based lemmas, good accuracy on classical prose; needs spaCy and ~hundreds of MB).
   - Collatinus (C++ with data files; offline, all possible lemmas per form, uses a Gaffiot/L&S-derived lexicon; good for an accepts oracle, needs build or the packaged binaries).
   None downloaded or run here. All four run offline once installed. For a Morpheus-equivalent 'any analysis matches' semantics, Whitaker's Words or Collatinus are closest; LatinCy/CLTK give one lemma per token and would score as a stricter, lower-recall check.
6. Headword keys: L&S `key` is like `A1`, `a2` (homograph digits), `ab`; the Greek keys are pure Greek. Homograph digits must be stripped or mapped before validation; entries are keyed by `id` (`n0`, `n1`) in counts, as done here.

## Honest estimate

- Engineering: XML loader and ref resolver for 160 editions about 2 days; relocate adaptation (normalisation, windows, tag map) about 2 days; validator integration and calibration (pick one oracle, build the lemma/headword normaliser, spot-check 200 hits) 3-5 days. Total about 1-1.5 working weeks for a first scored release limited to works with editions.
- Data ceiling: 90% of URN citations are into held-able works, and 74% of all bibls carry a usable Latin URN; with an abbreviation map for the plain-text bibls the ceiling would move up but each new abbreviation (Dig., Sil. Ital., Plin. Ep., Justin) needs manual mapping and, for Digest, an edition that is not in canonical-latinLit.
- Risk: edition mismatch. L&S was written against older editions than Perseus's, so (as with LSJ) line-level locators can be expected to drift for verse and for the older prose texts; Greek had the same problem. Expect a lower raw match rate on lemma-validated relocation than the Greek benchmark until windows are tuned.
