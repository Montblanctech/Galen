# MW-Gold leaderboard — v0 (12946 loci, 2026-11-09)

| system | loci | blind % [95% CI] | strict % | Ṛgveda | Manusmṛti | Atharvaveda | Aṣṭādhyāyī (Pāṇini) | Bhāgavatapurāṇa | Kathāsaritsāgara | Kumārasambhava | Aitareyabrāhmaṇa | Kirātārjunīya |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ByT5-Sanskrit multitask (Nehrdich, Hellwig, Keutzer 2024), local CPU — trained on DCS | 12855 | **82.82** [82.16–83.47] | 82.75 | 80.37 | 86.72 | 81.95 | 82.16 | 89.1 | 88.68 | 76.84 | 88.57 | 83.65 |
| Stanza 1.15 sa (UD_Sanskrit-Vedic) — trained on DCS | 12946 | **69.5** [68.7–70.28] | 69.36 | 67.13 | 73.32 | 70.95 | 67.77 | 73.37 | 71.34 | 56.54 | 79.59 | 63.55 |
| vidyut-cheda 0.4.0 (Ambuda segmenter-tagger) — trained on DCS | 11523 | **41.91** [41.01–42.81] | 41.9 | 41.6 | 38.73 | 42.11 | 46.33 | 45.48 | 45.14 | 35.59 | 44.8 | 37.25 |
| vidyut-kosha, first analysis (baseline) | 11961 | **52.29** [51.4–53.19] | 52.25 | 56.26 | 45.44 | 53.26 | 51.71 | 50.7 | 47.6 | 44.02 | 60.0 | 49.51 |

Regenerate: `python pipeline/mwgold/score_mw.py` then `python pipeline/mwgold/leaderboard_mw.py`. Page: `docs/mw-gold/index.html` (GitHub Pages).
