# LS-Gold v0 — Latin lemmatizer accuracy on the dictionary-cited stratum (2026-11-08)

161032 relocated loci over 33 authors. Match = headword equality after case, diacritic, u/v, i/j and homograph-digit normalisation; strict keeps u/v and i/j as printed. Wilson 95% in brackets.

| system | loci | blind % | strict % | Plautus, Titus Mac | Terence | Julius Caesar | Catullus, C. Valer | Cicero, Marcus Tul | Lucretius | Propertius, Sextus | Sallust | P. Vergilius Maro  | Celsus, Aulus Corn | Curtius Rufus, Qui | Horace | Titus Livius (Livy | Lucan | Ovid | Persius | Phaedrus | Pliny, the Elder | Quintilian | Seneca the Younger | Statius, P. Papini | Valerius Flaccus,  | Valerius Maximus | Vitruvius Pollio | Gellius, Aulus | Juvenal | Martial | Tacitus, Cornelius | Seneca the Younger |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| latincy_lg | 161032 | **84.94** [84.77–85.11] | 63.52 | 79.82 | 81.94 | 88.97 | 85.27 | 86.65 | 87.11 | 88.39 | 87.71 | 87.59 | 81.26 | 86.28 | 87.21 | 85.18 | 73.65 | 85.27 | 86.29 | 82.73 | 78.11 | 87.72 | 85.49 | 82.81 | 85.15 | 82.75 | 76.03 | 76.74 | 88.66 | 75.48 | 85.72 | 83.93 |
| cltk | 161032 | **83.96** [83.78–84.14] | 63.51 | 81.28 | 80.39 | 86.31 | 81.95 | 86.49 | 83.27 | 86.86 | 88.94 | 83.41 | 80.87 | 82.51 | 85.68 | 84.97 | 70.07 | 82.38 | 80.67 | 83.53 | 80.43 | 86.04 | 83.69 | 79.86 | 85.58 | 84.5 | 80.85 | 77.44 | 84.81 | 75.78 | 85.48 | 83.42 |
| collatinus_first (baseline) | 159918 | **82.26** [82.07–82.44] | 58.51 | 81.04 | 80.4 | 83.69 | 82.86 | 81.37 | 82.57 | 82.07 | 79.48 | 82.58 | 84.13 | 84.6 | 80.64 | 81.95 | 82.55 | 82.27 | 85.87 | 84.07 | 83.09 | 82.64 | 81.14 | 83.23 | 84.56 | 81.82 | 83.26 | 82.7 | 83.28 | 81.74 | 84.28 | 81.12 |
| whitaker_first (baseline) | 147490 | **81.38** [81.18–81.58] | 54.5 | 80.9 | 79.21 | 82.83 | 80.05 | 81.73 | 80.1 | 81.08 | 78.54 | 81.87 | 84.13 | 79.22 | 79.45 | 80.24 | 84.48 | 81.16 | 82.48 | 85.3 | 81.78 | 82.41 | 83.12 | 83.23 | 83.02 | 79.73 | 85.2 | 79.36 | 84.46 | 82.81 | 80.69 | 82.68 |
| stanza_proiel | 161032 | **75.47** [75.25–75.67] | 56.59 | 72.64 | 81.11 | 86.99 | 69.28 | 82.14 | 73.8 | 71.75 | 81.74 | 71.0 | 75.23 | 77.27 | 74.25 | 77.63 | 61.29 | 69.56 | 63.97 | 76.51 | 66.93 | 82.14 | 75.49 | 66.7 | 67.92 | 71.93 | 72.62 | 67.2 | 74.45 | 66.57 | 75.46 | 79.19 |
| stanza_perseus | 161032 | **65.46** [65.22–65.69] | 50.12 | 65.92 | 73.27 | 74.42 | 59.3 | 71.79 | 63.39 | 65.69 | 78.55 | 62.05 | 60.03 | 66.1 | 64.64 | 67.1 | 56.73 | 59.25 | 49.74 | 76.1 | 55.44 | 72.72 | 64.99 | 56.78 | 58.79 | 62.28 | 60.57 | 56.8 | 63.27 | 54.89 | 66.35 | 67.68 |
| stanza_ittb | 161032 | **65.26** [65.03–65.49] | 49.23 | 61.76 | 69.14 | 71.49 | 55.9 | 70.9 | 64.8 | 60.73 | 69.99 | 61.17 | 67.63 | 64.97 | 62.05 | 65.43 | 55.76 | 59.79 | 51.14 | 65.86 | 58.52 | 76.13 | 68.18 | 58.3 | 60.24 | 66.37 | 66.38 | 58.06 | 63.7 | 57.03 | 67.22 | 73.6 |
| stanza_llct | 161028 | **44.4** [44.16–44.64] | 32.38 | 46.92 | 53.04 | 49.83 | 38.32 | 51.25 | 38.28 | 40.51 | 51.97 | 38.73 | 42.07 | 44.88 | 43.06 | 47.12 | 35.2 | 37.3 | 35.5 | 43.78 | 37.65 | 50.04 | 44.36 | 37.28 | 34.13 | 46.35 | 47.38 | 39.42 | 46.4 | 38.28 | 43.5 | 49.24 |

By validation route and citation frequency (blind %):

- cltk: collatinus 84.33 (n 158106), whitaker 70.2 (n 2446), quoted 31.67 (n 480); cited 1: 79.8 (n 4687), 2-5: 79.77 (n 15073), 6+: 84.54 (n 141272)
- collatinus_first: collatinus 83.2 (n 158106), whitaker 0.0 (n 1812); cited 1: 86.44 (n 4637), 2-5: 85.44 (n 14943), 6+: 81.78 (n 140338)
- latincy_lg: collatinus 85.27 (n 158106), whitaker 71.3 (n 2446), quoted 47.29 (n 480); cited 1: 70.51 (n 4687), 2-5: 76.72 (n 15073), 6+: 86.3 (n 141272)
- stanza_ittb: collatinus 65.68 (n 158106), whitaker 45.05 (n 2446), quoted 29.38 (n 480); cited 1: 46.49 (n 4687), 2-5: 52.88 (n 15073), 6+: 67.2 (n 141272)
- stanza_llct: collatinus 44.78 (n 158102), whitaker 24.41 (n 2446), quoted 21.88 (n 480); cited 1: 33.06 (n 4686), 2-5: 38.1 (n 15072), 6+: 45.45 (n 141270)
- stanza_perseus: collatinus 65.85 (n 158106), whitaker 46.73 (n 2446), quoted 31.46 (n 480); cited 1: 42.1 (n 4687), 2-5: 49.43 (n 15073), 6+: 67.94 (n 141272)
- stanza_proiel: collatinus 75.96 (n 158106), whitaker 50.7 (n 2446), quoted 39.17 (n 480); cited 1: 55.45 (n 4687), 2-5: 61.2 (n 15073), 6+: 77.65 (n 141272)
- whitaker_first: collatinus 81.56 (n 145044), whitaker 70.4 (n 2446); cited 1: 82.07 (n 2242), 2-5: 85.52 (n 10233), 6+: 81.05 (n 135015)

Honesty: Lewis & Short cites what an 1879 lexicographer found worth citing, so this is the rare, dictionary-worthy stratum, not overall accuracy; loci come only from works held in Perseus canonical-latinLit editions; gold = the L&S headword; the two *_first baselines are the oracles' own first choice and partly circular with the collatinus/whitaker validation routes (see by_validation); every figure traces to a row in ls_gold_scored.csv.
