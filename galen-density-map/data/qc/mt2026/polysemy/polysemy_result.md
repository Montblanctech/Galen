# Polysemy probe — result (2026-11-06, pre-registered in `mt2026_polysemy_probe_spec.md`)

**Setup.** The 40 passages of the 11/05 probe; 310 new NOUN/ADJ targets drawn by rule (seed 20261106): 159 `polysemy_risk` (85 lemmas) and 151 `genuinely_hard` (141 lemmas) from the project's four-way classification; class withheld from translators. Three model families (claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5), two fresh sessions each, identical instructions, no glossary. Normalisation identical to the 11/05 probe.

## Numbers (`polysemy_summary.json`)
| disagreement rate | polysemy_risk (n 159) | genuinely_hard (n 151) | difference, 95% CI, p |
|---|---|---|---|
| within fable (run A vs B) | 11.9% [7.8–17.9] | 14.6% [9.8–21.1] | −2.6 [−10.2, +4.9], .50 |
| within opus | 8.8% [5.3–14.2] | 7.9% [4.6–13.4] | +0.9 [−5.3, +7.0], .79 |
| within sonnet | 11.9% [7.8–17.9] | 14.6% [9.8–21.1] | −2.6 [−10.2, +4.9], .50 |
| fable vs opus (run A) | 11.9% | 13.9% | −2.0 [−9.4, +5.5], .61 |
| fable vs sonnet | 12.6% | 18.5% | −6.0 [−14.0, +2.1], .15 |
| opus vs sonnet | 11.3% | 15.2% | −3.9 [−11.5, +3.7], .31 |
| any of the three differs | 17.0% | 21.2% | −4.2 [−13.0, +4.5], .35 |

Secondary: self-flagged uncertainty is **higher on the genuinely-hard class in all six runs** (2.7–11.3% vs 0–6.3%). Per-lemma within-run inconsistency (same lemma, ≥2 passages, different renderings in one run): polysemy_risk 12–18 of 36 lemmas (33–50%), genuinely_hard 0–2 of 10.

## Reading
1. **The prediction failed.** The polysemy quadrant is not where 2026 renderings wobble more than the medical-only quadrant. Every difference points the other way (medical-only vocabulary slightly less stable), none is significant, and the three model families agree on this. The 11/05 write-up's suggestion that polysemy is "the better candidate for that role" is withdrawn; the pattern it rested on (πλῆθος, καιρός, τροφή) does not generalise to a sampled class.
2. **What polysemy does produce is context-dependent rendering, not instability.** A polysemous lemma that occurs in several passages is rendered differently across those passages in a third to a half of cases within one run (λόγος, πᾶς, πολύς, ἕτερος); a medical-only lemma almost never. That is the translators choosing the sense that fits, which is what polysemy means, and it is the right behaviour, not noise. The term-level stability measure cannot separate "chose a different sense correctly" from "wobbled" without a sense annotation; this probe does not have one.
3. **Translators feel unsure on the rare medical words and render them just as consistently.** The uncertainty flag tracks the class the density map describes (the medical-only lexicon); stability does not. Taken with the constrained-terminology run (the ten punch-list terms were the least stable words in their passages within one model, 15–27%), the picture is: ordinary polysemy → consistent, context-driven variation; the rare technical lexicon → low self-confidence, occasional wobble, and real errors a glossary of the right kind would fix (galbanum, orpiment, terebinth resin).
4. **Consequence for the paper**: §7's last sentence (the polysemy quadrant as the better candidate) is replaced by this result; the map remains a map of lexicon under-description and of translator uncertainty, not of rendering instability.

## Honesty clauses
All three translators share a developer and lineage; disagreement is not error; ≈155 targets per class give about ±7 points on a rate and ±8–9 on a difference; `genuinely_hard` and `polysemy_risk` are frequency-contrast labels from the project's own classification, not human judgments of difficulty; identical rates for fable and sonnet in the within-model row are a coincidence (the two models differ on 48 of 310 targets).

## Files
`translator_targets.csv`, `sample_meta.json`, `translation_<model>_<run>.jsonl` and `renderings_<model>_<run>.csv` (six each), `polysemy_targets_scored.csv` (un-blinded), `polysemy_class_key_PUBLISHED_AFTER_SCORING.csv`, `polysemy_summary.json`. Scripts: `pipeline/mt2026/polysemy_sample_targets.py`, `polysemy_score.py`.
