# Constrained-terminology demonstration — result (2026-11-06, pre-registered in `mt2026_constrained_terminology_spec.md`)

**Setup.** Ten `thin`-tier punch-list terms, each defined by its Perseus-LSJ entry and given a *preferred rendering = LSJ's first English gloss, extracted mechanically* (no scholar, no model wrote it). The 16 passages of the 11/05 probe that contain them (176 targets: 26 term targets, 150 others). Two translators (fable-5-1, opus-5-5), fresh sessions, two conditions: C0 = 11/05 instructions, C1 = same + glossary. Two blind judges (sonnet-5-5, opus-5-5) on 32 A/B pairs, order randomised (seed 20261106), condition hidden; key published after scoring.

## Numbers (`constrained_summary.json`)
| measure | fable-5-1 | opus-5-5 |
|---|---|---|
| compliance with the glossary in C1 (26 term targets) | **26/26** | **26/26** |
| run-to-run disagreement with own 11/05 renderings, other targets (n 150) | 6.0% [3.2–11.0] | 10.7% [6.7–16.6] |
| run-to-run on the ten terms (n 26) | 26.9% | 15.4% |

| cross-translator disagreement | term targets (26) | other targets (150) |
|---|---|---|
| 11/05 run | 23.1% | 10.0% |
| C0 (fresh, no glossary) | 23.1% | 12.7% [8.3–18.9] |
| C1 (glossary) | **3.8%** | 10.7% [6.7–16.6]; C0−C1 = 2.0 points, 95% CI −5.3 to +9.3, p = 0.59 |

| judge | ties | glossary (C1) preferred, of decided pairs | of all 32 |
|---|---|---|---|
| sonnet-5-5 | 21 | 3/11 = **27%** [10–57] | 9% |
| opus-5-5 | 9 | 5/23 = **22%** [10–42] | 16% |
| raw agreement between judges 56% (18/32) | | | |

## Reading
1. **The glossary was obeyed perfectly and made the translations worse.** Both judges, blind, preferred the no-glossary translation in roughly three of four decided pairs, from both translators. Their notes say why, and they agree with each other: χαλβάνη rendered as "the resinous juice of all-heal" where the term is *galbanum*; ῥητίνη as "resin of the pine" where Galen means resin generically or names the tree himself, producing "terebinth resin of the pine" and "larch resin of the pine" (wrong source tree); ῥευματικός as "subject to a discharge or flux" was the one glossary entry a judge preferred over the free rendering "rheumatic" (anachronistic). **LSJ's first gloss is a definition, not a translation equivalent.** Fed as a constraint it is copied verbatim into the prose, at 100% compliance, errors included.
2. **Stability on the constrained terms rose by construction** (23% → 3.8%) and is reported as compliance, not as a finding. Everything else in the same passages was untouched (10.0 / 12.7 / 10.7%, all within noise). A glossary pins its own words and nothing else.
3. **The ten punch-list terms are the least stable words in these passages even within one model**: the same model re-translating the same passages changed its rendering of them 15–27% of the time against 6–11% for the other targets. That is the first within-model number behind the probe's "where 2026 renderings wobble" and it points at the technical lexicon after all, at the term level, once the artifact-laden absent tier is out of the way.
4. **What plan §10 actually needs** is now specific: not "defined terms" but *translation equivalents chosen by someone who knows the pharmacopoeia* (galbanum, orpiment, terebinth resin, white lead), with a rule for generic words (ῥητίνη: translate as the context names the tree). With such a list the compliance result says the models will apply it uniformly. The scholar's ten terms remain Will's hand (ROADMAP item 6/10); the machinery to measure the delta is built and run once, end to end, in an afternoon.

## Honesty clauses
Model judges of Greek→English are weak evidence and share lineage with the translators; a preference is not a correctness measure; 32 pairs give ±16 points on a preference rate; two judges agreed on only 56% of pairs (most of the disagreement is tie vs decided, not A vs B). The glossary was deliberately mechanical so that no model-written gloss entered the project (plan §3); the negative result is about *that* glossary, not about constrained terminology as such. Nothing here is a scholar's definition.

## Files
`terminology.csv`, `passages.jsonl`, `translator_targets.csv`, `translation_{C0,C1}_{fable-5-1,opus-5-5}.jsonl`, `renderings_{C0,C1}_*.csv`, `judge_pairs.jsonl`, `judge_instructions.txt`, `judge_answers_{sonnet-5-5,opus-5-5}.csv`, `judge_verdicts.csv`, `judge_key_PUBLISHED_AFTER_SCORING.csv`, `constrained_summary.json`. Scripts: `pipeline/mt2026/demo_build.py`, `demo_judge_pairs.py`, `demo_score.py`.
