# Which lemmatizer for my author? (T1 recommendations)

**Rule (applied mechanically, in this order; nothing is a judgement call).**
1. *Basis A, LSJ-Gold:* if both systems have an LSJ-Gold accent-blind score for the author with n >= 100 loci each, compare the two Wilson 95% intervals (recomputed from k, n). Non-overlapping: the higher system is recommended. Overlapping: `either`.
2. *Basis B, M1 floor (fallback when A does not apply):* compare the two systems' article-neutral Morpheus floors (percent of analyzable tokens, as in `author_table_all.csv`), with n = tokens x (100 - not-in-cache% - no-analysis%) / 100 (an approximation; the table gives percentages only). Both n >= 100 and Wilson intervals non-overlapping: the higher floor is recommended; overlapping: `either`. A floor with a cache gap above 15% is marked `cache_gap` in the row (the Morpheus cache was built for Galen; the floor is partial there) but is still used.
3. *Neither basis has n >= 100 for both systems:* `insufficient data`.
`Dilemma` = lexicon-first (Open Greek Dilemma 1.3.15, lsj convention); `odyCy` = neural (odyCy 0.7.0 frozen run). The recommendation names the system with the higher number on the stated basis; it says nothing about error types. Genre tags: the repository carries no per-author genre field, so the column is `n/a` throughout rather than invented.

Counts: Dilemma: 40; either: 5; insufficient data: 14; odyCy: 7 (of 66 authors; by basis: Dilemma/LSJ-Gold: 2; Dilemma/M1 floor (article-neutral): 38; either/LSJ-Gold: 1; either/M1 floor (article-neutral): 4; insufficient data/-: 14; odyCy/M1 floor (article-neutral): 7).

Article-convention share: tokens whose odyCy/Dilemma lemma pair is class `article` are 79.2% of all disagreeing-pair tokens in `convention_pairs.csv` (1,555,109 of 1,963,738). Per-author effect of the convention: column `conv gap` = Dilemma neutral floor minus strict floor.

Sources: `author_table_all.csv`, `convention_pairs.csv`, `data/qc/lsjgold/lsj_gold_scores.json`. Gold = accent-blind LSJ-Gold match % (k/n, Wilson 95%); floor = M1 Morpheus floor, percent of analyzable tokens (strict / article-neutral), n_est as defined in the rule. Full numbers in `recommendations.csv`.

| tlg | author | genre | recommendation | basis | odyCy gold % (k/n) [CI] | Dilemma gold % (k/n) [CI] | odyCy floor s/n (n_est) | Dilemma floor s/n (n_est) | cache gap o/d % | M2 agree s/n | conv gap | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tlg0001 | Apollonius Rhodius | n/a | **insufficient data** | — | — | 68.88 (529/768) [65.52-72.05] | — | — | — / — | — / — | — |  |
| tlg0003 | Thucydides | n/a | **insufficient data** | — | — | 89.64 (4620/5154) [88.78-90.44] | — | — | — / — | — / — | — |  |
| tlg0005 | Theocritus | n/a | **insufficient data** | — | — | 76.84 (700/911) [73.99-79.46] | — | — | — / — | — / — | — |  |
| tlg0008 | Athenaeus | n/a | **insufficient data** | — | — | — | — | — | — / — | — / — | — |  |
| tlg0011 | Sophocles | n/a | **either** | LSJ-Gold | 86.38 (279/323) [82.21-89.69] | 89.47 (5474/6118) [88.68-90.22] | — | — | — / — | — / — | — |  |
| tlg0012 | Homer | n/a | **insufficient data** | — | — | 85.84 (17420/20293) [85.36-86.32] | — | — | — / — | — / — | — |  |
| tlg0016 | Herodotus | n/a | **insufficient data** | — | — | 86.63 (1406/1623) [84.89-88.2] | — | — | — / — | — / — | — |  |
| tlg0018 | Philo Judaeus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.61 / 94.61 (343310) | 82.28 / 96.13 (344272) | 15.47 / 15.33 | 72.09 / 84.34 | 13.85 | cache_gap |
| tlg0019 | Aristophanes | n/a | **insufficient data** | — | — | 88.55 (2953/3335) [87.42-89.58] | — | — | — / — | — / — | — |  |
| tlg0032 | Xenophon | n/a | **insufficient data** | — | — | 90.3 (2680/2968) [89.18-91.31] | — | — | — / — | — / — | — |  |
| tlg0033 | Pindar | n/a | **insufficient data** | — | — | 85.06 (1457/1713) [83.29-86.67] | — | — | — / — | — / — | — |  |
| tlg0057 | Galen | n/a | **insufficient data** | — | — | — | — | — | — / — | — / — | — |  |
| tlg0059 | Plato | n/a | **insufficient data** | — | — | 90.17 (2018/2238) [88.87-91.34] | — | — | — / — | — / — | — |  |
| tlg0082 | Apollonius Dyscolus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.2 / 94.2 (100956) | 78.73 / 96.3 (101675) | 15.36 / 14.79 | 66.59 / 82.21 | 17.57 | cache_gap |
| tlg0085 | Aeschylus | n/a | **Dilemma** | LSJ-Gold | 72.61 (2858/3936) [71.2-73.98] | 90.51 (6249/6904) [89.8-91.18] | — | — | — / — | — / — | — |  |
| tlg0086 | Aristotle | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.75 / 94.75 (749838) | 80.46 / 95.66 (753229) | 6.6 / 6.22 | 70.52 / 85.73 | 15.2 |  |
| tlg0087 | Aelius Herodianus Et Pseudo-Herodianus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.05 / 95.05 (276906) | 78.78 / 97.03 (284589) | 27.59 / 25.63 | 66.47 / 80.26 | 18.25 | cache_gap |
| tlg0093 | Theophrastus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.41 / 94.41 (185284) | 80.37 / 95.62 (186552) | 9.64 / 9.06 | 70.2 / 85.02 | 15.25 |  |
| tlg0363 | Claudius Ptolemaeus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.32 / 94.32 (161560) | 73.06 / 96.75 (164313) | 17.6 / 16.45 | 63.56 / 82.97 | 23.69 | cache_gap |
| tlg0526 | Josephus | n/a | **insufficient data** | — | — | — | — | — | — / — | — / — | — |  |
| tlg0527 | Septuaginta | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 96.9 / 96.9 (273083) | 79.79 / 94.18 (277167) | 23.54 / 22.4 | 70.05 / 82.58 | 14.39 | cache_gap |
| tlg0530 | Pseudo-Galenus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 89.71 / 89.71 (80848) | 84.3 / 97.05 (81944) | 7.6 / 6.64 | 68.09 / 80.47 | 12.75 |  |
| tlg0543 | Polybius | n/a | **insufficient data** | — | — | 90.18 (1992/2209) [88.86-91.35] | — | — | — / — | — / — | — |  |
| tlg0544 | Sextus Empiricus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.13 / 94.13 (180436) | 82.04 / 95.65 (182272) | 9.48 / 8.64 | 71.28 / 84.36 | 13.61 |  |
| tlg0552 | Archimedes | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 92.71 / 92.71 (81142) | 74.79 / 95.15 (81195) | 18.87 / 18.81 | 60.17 / 77.6 | 20.36 | cache_gap |
| tlg0555 | Clemens Alexandrinus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.59 / 95.59 (83135) | 79.96 / 95.89 (83309) | 17.39 / 17.22 | 70.25 / 84.45 | 15.93 | cache_gap |
| tlg0559 | Heron | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 93.83 / 93.83 (84167) | 75.92 / 96.77 (85482) | 17.95 / 16.94 | 64.22 / 81.92 | 20.85 | cache_gap |
| tlg0627 | Hippocrates | n/a | **Dilemma** | LSJ-Gold | 61.68 (1637/2654) [59.82-63.51] | 94.4 (2495/2643) [93.46-95.21] | 91.81 / 91.81 (323416) | 84.86 / 96.26 (323671) | 9.27 / 9.22 | 69.83 / 81.03 | 11.4 |  |
| tlg0656 | Dioscorides Pedanius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 87.72 / 87.72 (109046) | 88.23 / 96.93 (110014) | 11.73 / 10.96 | 68.92 / 77.26 | 8.7 |  |
| tlg0732 | Alexander | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.68 / 94.68 (969866) | 81.22 / 96.1 (974372) | 5.0 / 4.59 | 70.96 / 86.43 | 14.88 |  |
| tlg1271 | Clemens Romanus Et Clementina | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 95.61 / 95.61 (111863) | 82.4 / 94.7 (112545) | 15.85 / 15.35 | 73.59 / 85.17 | 12.3 | cache_gap |
| tlg1764 | Vettius Valens | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.85 / 94.85 (76576) | 81.87 / 96.33 (78108) | 22.24 / 21.42 | 71.0 / 82.83 | 14.46 | cache_gap |
| tlg2000 | Plotinus | n/a | **either** | M1 floor (article-neutral) | — | — | 95.8 / 95.8 (198714) | 84.1 / 95.67 (198885) | 6.7 / 6.62 | 75.37 / 87.48 | 11.57 |  |
| tlg2001 | Themistius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 93.93 / 93.93 (231511) | 81.25 / 95.49 (233026) | 5.5 / 4.92 | 70.75 / 85.33 | 14.24 |  |
| tlg2018 | Eusebius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.28 / 95.28 (648626) | 80.55 / 95.52 (657968) | 17.76 / 16.67 | 70.22 / 83.37 | 14.97 | cache_gap |
| tlg2021 | Epiphanius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 96.0 / 96.0 (184298) | 80.91 / 96.43 (188646) | 19.31 / 17.43 | 70.75 / 84.77 | 15.52 | cache_gap |
| tlg2023 | Iamblichus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.68 / 94.68 (125512) | 80.75 / 95.9 (126088) | 11.1 / 10.73 | 71.12 / 85.3 | 15.15 |  |
| tlg2034 | porphyrius-tyrius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.12 / 95.12 (129402) | 80.87 / 95.77 (131804) | 16.52 / 15.05 | 69.36 / 82.54 | 14.9 | cache_gap |
| tlg2035 | athanasius-of-alexandria | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 97.04 / 97.04 (89587) | 82.19 / 95.91 (90729) | 16.87 / 15.82 | 75.54 / 88.28 | 13.72 | cache_gap |
| tlg2042 | Origenes | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 95.85 / 95.85 (757110) | 79.34 / 95.39 (766592) | 16.98 / 15.96 | 70.03 / 84.84 | 16.05 | cache_gap |
| tlg2045 | Nonnus | n/a | **insufficient data** | — | — | 48.92 (113/231) [42.54-55.33] | — | — | — / — | — / — | — |  |
| tlg2048 | Salaminius Hermias Sozomenus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.55 / 95.55 (89379) | 80.95 / 96.67 (90012) | 20.37 / 19.81 | 70.09 / 83.73 | 15.72 | cache_gap |
| tlg2057 | Socrates Scholasticus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.83 / 95.83 (79810) | 79.99 / 96.71 (80635) | 21.02 / 20.2 | 70.13 / 84.86 | 16.72 | cache_gap |
| tlg2115 | Hippolytus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.36 / 95.36 (115156) | 81.45 / 96.68 (116173) | 15.72 / 14.99 | 70.95 / 84.62 | 15.23 | cache_gap |
| tlg2200 | Libanius | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 95.15 / 95.15 (334586) | 80.15 / 94.33 (339316) | 14.9 / 13.85 | 69.1 / 81.74 | 14.18 |  |
| tlg2371 | Chronicon Paschale | n/a | **either** | M1 floor (article-neutral) | — | — | 96.01 / 96.01 (82080) | 79.12 / 96.06 (85736) | 26.16 / 23.89 | 68.53 / 82.25 | 16.94 | cache_gap |
| tlg2703 | Anna Comnena | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.8 / 94.8 (224305) | 78.41 / 96.46 (229409) | 21.3 / 19.55 | 66.3 / 81.4 | 18.05 | cache_gap |
| tlg3135 | Joannes Zonaras | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.64 / 95.64 (281741) | 79.67 / 96.68 (285304) | 22.07 / 21.12 | 68.67 / 83.21 | 17.01 | cache_gap |
| tlg4013 | Simplicius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.26 / 94.26 (907656) | 80.77 / 96.06 (913796) | 6.41 / 5.79 | 69.97 / 85.54 | 15.29 |  |
| tlg4015 | Joannes Philoponus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.3 / 94.3 (1061703) | 80.72 / 95.83 (1068870) | 5.98 / 5.37 | 69.88 / 85.42 | 15.11 |  |
| tlg4016 | Ammonius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 93.92 / 93.92 (213270) | 80.21 / 95.9 (214883) | 7.84 / 7.17 | 69.52 / 85.23 | 15.69 |  |
| tlg4018 | Asclepius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.59 / 94.59 (163060) | 81.51 / 95.95 (163902) | 5.57 / 5.09 | 72.12 / 86.68 | 14.44 |  |
| tlg4019 | Olympiodorus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.26 / 94.26 (154261) | 80.68 / 95.66 (155144) | 7.49 / 6.98 | 70.89 / 85.79 | 14.98 |  |
| tlg4020 | Elias | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.75 / 94.75 (82355) | 81.02 / 95.57 (83005) | 7.48 / 6.78 | 71.2 / 85.9 | 14.55 |  |
| tlg4026 | Anonymi In Aristotelis Artem Rhetoricam | n/a | **either** | M1 floor (article-neutral) | — | — | 95.92 / 95.92 (83745) | 81.05 / 95.75 (84471) | 11.78 / 11.05 | 72.22 / 86.23 | 14.7 |  |
| tlg4031 | Eustratius | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.23 / 95.23 (217539) | 81.3 / 96.05 (219172) | 8.41 / 7.79 | 71.92 / 86.39 | 14.75 |  |
| tlg4033 | Anonymi In Aristotelis Ethica Nicomachea | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.5 / 95.5 (88172) | 81.85 / 95.88 (88885) | 8.12 / 7.42 | 73.51 / 87.31 | 14.03 |  |
| tlg4034 | Michael | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.4 / 94.4 (131957) | 80.13 / 96.02 (132573) | 5.84 / 5.43 | 70.31 / 86.57 | 15.89 |  |
| tlg4036 | Proclus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.73 / 94.74 (140626) | 78.24 / 96.13 (143266) | 12.86 / 11.25 | 67.59 / 84.03 | 17.89 |  |
| tlg4089 | Theodoretus | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 94.79 / 94.8 (141891) | 77.94 / 96.19 (143574) | 20.71 / 19.8 | 67.57 / 83.29 | 18.25 | cache_gap |
| tlg4090 | Cyrillus | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 95.9 / 95.9 (230435) | 79.46 / 95.68 (234684) | 22.5 / 21.12 | 69.71 / 83.01 | 16.22 | cache_gap |
| tlg4102 | Catenae (Novum Testamentum) | n/a | **odyCy** | M1 floor (article-neutral) | — | — | 96.34 / 96.34 (935996) | 80.02 / 95.42 (943098) | 16.58 / 15.98 | 72.9 / 86.77 | 15.4 | cache_gap |
| tlg5023 | Scholia In Euripidem | n/a | **either** | M1 floor (article-neutral) | — | — | 96.08 / 96.08 (316328) | 79.13 / 96.05 (319281) | 20.31 / 19.61 | 70.12 / 84.55 | 16.92 | cache_gap |
| tlg5026 | Scholia In Homerum | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.99 / 95.99 (666708) | 80.78 / 96.61 (678014) | 22.62 / 21.34 | 69.76 / 83.01 | 15.83 | cache_gap |
| tlg5034 | Scholia In Pindarum | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 96.31 / 96.31 (77544) | 79.24 / 96.99 (78061) | 21.12 / 20.69 | 68.54 / 83.72 | 17.75 | cache_gap |
| tlg9010 | Suda | n/a | **Dilemma** | M1 floor (article-neutral) | — | — | 95.08 / 95.09 (343764) | 81.09 / 96.44 (349678) | 25.73 / 24.49 | 69.14 / 81.48 | 15.35 | cache_gap |
