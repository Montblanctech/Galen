# MW-Gold v0 — Sanskrit lemmatizer accuracy on the dictionary-cited stratum (2026-11-09)

12946 relocated loci over 32 texts. Match = headword equality after case, accent, anusvāra and homonym-digit normalisation (blind); strict keeps nasals as printed. Compound spans are judged on the sandhi-joined member lemmas. Wilson 95% in brackets.

| system | loci | blind % | strict % | Aitareyabrāhmaṇa | Aṣṭādhyāyī (Pāṇini | Atharvaveda | Bhāgavatapurāṇa | Kathāsaritsāgara | Kirātārjunīya | Kumārasambhava | Manusmṛti | Ṛgveda |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| byt5 (trained on DCS) | 12855 | **82.82** [82.16–83.47] | 82.75 | 88.57 | 82.16 | 81.95 | 89.1 | 88.68 | 83.65 | 76.84 | 86.72 | 80.37 |
| stanza_sa (trained on DCS) | 12946 | **69.5** [68.7–70.28] | 69.36 | 79.59 | 67.77 | 70.95 | 73.37 | 71.34 | 63.55 | 56.54 | 73.32 | 67.13 |
| vidyut_cheda (trained on DCS) | 11523 | **41.91** [41.01–42.81] | 41.9 | 44.8 | 46.33 | 42.11 | 45.48 | 45.14 | 37.25 | 35.59 | 38.73 | 41.6 |
| vidyut_first (baseline) | 11961 | **52.29** [51.4–53.19] | 52.25 | 60.0 | 51.71 | 53.26 | 50.7 | 47.6 | 49.51 | 44.02 | 45.44 | 56.26 |

By validation route, span, window and MW citation frequency (blind %):

- byt5: dcs 96.4 (n 8747), dcs_cpd 77.65 (n 2769), dcs_tmesis 0.0 (n 584), vidyut 10.15 (n 522), surface 5.15 (n 233); single 84.25 (n 10086), compound 77.65 (n 2769); verse-window 82.67 (n 12460), chapter-window 87.59 (n 395); cited 1: 82.49 (n 6920), 2-5: 82.67 (n 4697), 6+: 85.3 (n 1238)
- stanza_sa: dcs 79.07 (n 8826), dcs_cpd 67.87 (n 2776), dcs_tmesis 0.0 (n 584), vidyut 19.35 (n 527), surface 13.73 (n 233); single 69.94 (n 10170), compound 67.87 (n 2776); verse-window 69.3 (n 12542), chapter-window 75.5 (n 404); cited 1: 68.81 (n 6970), 2-5: 70.05 (n 4725), 6+: 71.22 (n 1251)
- vidyut_cheda: dcs 53.16 (n 7853), dcs_cpd 16.58 (n 2515), dcs_tmesis 0.0 (n 444), vidyut 41.95 (n 503), surface 12.5 (n 208); single 48.98 (n 9008), compound 16.58 (n 2515); verse-window 41.76 (n 11158), chapter-window 46.3 (n 365); cited 1: 36.54 (n 6298), 2-5: 44.58 (n 4190), 6+: 63.77 (n 1035)
- vidyut_first: dcs 68.04 (n 8063), dcs_cpd 15.32 (n 2761), dcs_tmesis 0.0 (n 398), vidyut 54.27 (n 527), surface 28.3 (n 212); single 63.39 (n 9200), compound 15.32 (n 2761); verse-window 52.06 (n 11578), chapter-window 59.27 (n 383); cited 1: 50.75 (n 6607), 2-5: 53.67 (n 4345), 6+: 56.49 (n 1009)

Honesty: Monier-Williams cites what its lexicographers found worth citing: the rare, dictionary-worthy stratum, not overall accuracy. The gold lemma is the DCS annotators' lemma (routes dcs, dcs_cpd) where it equals MW's headword, so systems trained on the DCS (byt5, stanza_sa) are scored on their own training distribution and partly on their training sentences; vidyut_first is the first analysis of the oracle behind the vidyut route. Every figure traces to a row in mw_gold_scored.csv.
