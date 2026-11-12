# LS-Gold v0 — Latin lemmatizer accuracy on the dictionary-cited stratum (2026-11-11)

157855 relocated loci over 33 authors. Match = headword equality after case, diacritic, u/v, i/j and homograph-digit normalisation; strict keeps u/v and i/j as printed. Wilson 95% in brackets.

| system | loci | blind % | strict % | Plautus, Titus Mac | Terence | Julius Caesar | Catullus, C. Valer | Cicero, Marcus Tul | Lucretius | Propertius, Sextus | Sallust | P. Vergilius Maro  | Celsus, Aulus Corn | Curtius Rufus, Qui | Horace | Titus Livius (Livy | Lucan | Ovid | Persius | Phaedrus | Pliny, the Elder | Quintilian | Seneca the Younger | Statius, P. Papini | Valerius Flaccus,  | Valerius Maximus | Vitruvius Pollio | Gellius, Aulus | Juvenal | Martial | Tacitus, Cornelius | Seneca the Younger |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| latincy_lg | 157855 | **85.34** [85.17–85.52] | 63.8 | 80.79 | 83.58 | 89.14 | 85.76 | 87.25 | 87.4 | 89.13 | 88.02 | 87.85 | 81.22 | 86.59 | 87.49 | 85.41 | 74.3 | 85.82 | 87.05 | 82.79 | 78.43 | 87.81 | 85.86 | 83.42 | 85.37 | 82.93 | 76.16 | 77.2 | 88.99 | 75.94 | 86.07 | 84.01 |
| cltk | 157855 | **84.36** [84.18–84.54] | 63.79 | 82.27 | 81.98 | 86.48 | 82.57 | 87.04 | 83.57 | 87.71 | 89.14 | 83.7 | 81.08 | 82.71 | 85.97 | 85.26 | 70.77 | 82.93 | 80.76 | 83.81 | 80.85 | 86.09 | 84.07 | 80.43 | 85.97 | 84.73 | 81.25 | 77.96 | 85.18 | 76.18 | 85.76 | 83.33 |
| collatinus_first (baseline) | 156841 | **82.48** [82.29–82.67] | 58.64 | 81.75 | 81.28 | 83.75 | 82.85 | 81.76 | 82.82 | 82.65 | 79.75 | 82.77 | 84.2 | 84.69 | 80.74 | 82.12 | 82.62 | 82.43 | 86.44 | 84.77 | 83.3 | 82.62 | 81.23 | 83.47 | 84.6 | 81.98 | 83.6 | 82.9 | 83.37 | 81.85 | 84.4 | 81.2 |
| whitaker_first (baseline) | 144719 | **81.68** [81.48–81.88] | 54.64 | 81.49 | 79.84 | 83.03 | 80.42 | 82.22 | 80.51 | 81.35 | 78.94 | 82.12 | 84.34 | 79.26 | 79.78 | 80.4 | 84.44 | 81.44 | 83.01 | 85.62 | 82.07 | 82.5 | 83.43 | 83.3 | 83.08 | 80.1 | 85.5 | 79.79 | 84.74 | 83.0 | 80.88 | 82.8 |
| stanza_proiel | 157855 | **75.87** [75.65–76.08] | 56.86 | 73.76 | 82.2 | 87.23 | 70.05 | 82.67 | 74.36 | 72.49 | 82.07 | 71.33 | 75.54 | 77.5 | 74.63 | 77.94 | 61.98 | 70.06 | 64.03 | 76.64 | 67.29 | 82.22 | 75.8 | 67.2 | 68.07 | 72.01 | 72.82 | 67.52 | 74.67 | 66.93 | 75.87 | 79.08 |
| stanza_perseus | 157855 | **65.79** [65.55–66.02] | 50.36 | 66.94 | 74.2 | 74.67 | 59.82 | 72.2 | 63.71 | 66.27 | 78.8 | 62.37 | 59.73 | 66.52 | 64.99 | 67.38 | 57.32 | 59.66 | 50.18 | 76.02 | 55.73 | 72.79 | 65.19 | 57.16 | 58.95 | 62.13 | 60.61 | 57.05 | 63.58 | 55.22 | 66.69 | 67.69 |
| stanza_ittb | 157855 | **65.61** [65.37–65.84] | 49.47 | 62.71 | 70.15 | 71.63 | 56.79 | 71.32 | 65.25 | 61.17 | 70.28 | 61.41 | 67.43 | 65.23 | 62.53 | 65.67 | 56.13 | 60.22 | 51.08 | 65.98 | 58.88 | 76.24 | 68.49 | 58.66 | 60.5 | 66.47 | 66.57 | 58.36 | 63.95 | 57.33 | 67.61 | 73.64 |
| stanza_llct | 157851 | **44.62** [44.38–44.87] | 32.51 | 47.8 | 53.94 | 49.95 | 38.95 | 51.46 | 38.59 | 41.0 | 52.01 | 38.94 | 42.43 | 45.16 | 43.27 | 47.29 | 35.55 | 37.57 | 35.79 | 43.65 | 37.9 | 50.14 | 44.44 | 37.54 | 34.17 | 46.56 | 47.53 | 39.64 | 46.6 | 38.39 | 43.72 | 49.32 |

By validation route and citation frequency (blind %):

- cltk: collatinus 84.67 (n 155167), whitaker 73.14 (n 2249), quoted 33.94 (n 439); cited 1: 80.23 (n 4653), 2-5: 80.11 (n 14889), 6+: 84.96 (n 138313)
- collatinus_first: collatinus 83.37 (n 155167), whitaker 0.0 (n 1674); cited 1: 86.84 (n 4604), 2-5: 85.7 (n 14767), 6+: 81.99 (n 137470)
- latincy_lg: collatinus 85.6 (n 155167), whitaker 74.88 (n 2249), quoted 49.66 (n 439); cited 1: 70.88 (n 4653), 2-5: 77.03 (n 14889), 6+: 86.73 (n 138313)
- stanza_ittb: collatinus 65.96 (n 155167), whitaker 47.71 (n 2249), quoted 32.12 (n 439); cited 1: 46.79 (n 4653), 2-5: 53.15 (n 14889), 6+: 67.58 (n 138313)
- stanza_llct: collatinus 44.95 (n 155163), whitaker 25.83 (n 2249), quoted 23.92 (n 439); cited 1: 33.25 (n 4652), 2-5: 38.31 (n 14888), 6+: 45.68 (n 138311)
- stanza_perseus: collatinus 66.11 (n 155167), whitaker 49.53 (n 2249), quoted 34.17 (n 439); cited 1: 42.27 (n 4653), 2-5: 49.63 (n 14889), 6+: 68.32 (n 138313)
- stanza_proiel: collatinus 76.28 (n 155167), whitaker 53.53 (n 2249), quoted 42.82 (n 439); cited 1: 55.73 (n 4653), 2-5: 61.43 (n 14889), 6+: 78.1 (n 138313)
- whitaker_first: collatinus 81.85 (n 142470), whitaker 70.7 (n 2249); cited 1: 82.67 (n 2216), 2-5: 85.78 (n 10130), 6+: 81.35 (n 132373)

Honesty: Lewis & Short cites what an 1879 lexicographer found worth citing, so this is the rare, dictionary-worthy stratum, not overall accuracy; loci come only from works held in Perseus canonical-latinLit editions; gold = the L&S headword; the two *_first baselines are the oracles' own first choice and partly circular with the collatinus/whitaker validation routes (see by_validation); every figure traces to a row in ls_gold_scored.csv.
