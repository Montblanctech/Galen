# MT-2026 Consistency Probe — does the density map still predict where 2026 translation wobbles? (Architect Spec, executed 2026-11-05)

**Date:** 2026-11-05. **Status:** SPEC + RUN (stage 1 sampled; stages 2–3 run by two model sessions and a scorer).

**Question.** Zainaldin et al. (arXiv:2602.24119) found with 2025-era models that terminology rarity predicts passage-level translation quality (r = −.97) on *De temperamentis* (translated, high quality) and *De compositione medicamentorum per genera* (untranslated, low quality). The density map claims to locate the vocabulary that blocks translation. With a 2026 model, is the punch list still where translation is unstable?

**What we can measure without reading Greek.** Not correctness: *stability*. Two independent translators (two model sessions, different models) translate the same 40 passages blind. For every target word they record the English rendering they used. Then:
1. **Term-level disagreement rate**: fraction of targets where the two renderings differ (after normalising case, articles, plural, and a small synonym fold applied *identically* to both classes). Compare **punch-list targets** vs **matched control targets** (NOUN/ADJ in the same passage, not on the punch list, LSJ sense count ≥ 3). Prediction if the map is right: punch > control, with a 95% CI on the difference (two-proportion z, and a per-passage paired comparison).
2. **Passage-level**: disagreement rate vs punch-list density per 100 tokens (Spearman ρ, with its CI), the analogue of Zainaldin's r.
3. **Self-flagged uncertainty**: each translator may mark a target `uncertain`; report the rate by class as a secondary signal (self-report is weak evidence and is labelled so).
4. **Within-translator inconsistency**: for a lemma that appears as a target in ≥2 passages, does the same translator render it the same way? Rate by class.

**Honesty clauses (go in the write-up verbatim, roughly).** Disagreement is not error: two translators can differ and both be right, or agree and both be wrong. The two models share a developer and training lineage, so agreement is optimistic. Passages are the tokenised surface stream without punctuation, identical for both translators. 153 punch and 153 control targets over 40 passages (20 per work, density-tercile stratified, seed 20261105) give roughly ±8 points on a class rate; the headline is the *difference*, not either rate.

## Stage 1 — sample (done): `pipeline/mt2026/sample_passages.py`
Outputs `data/qc/mt2026/passages.jsonl`, `translator_targets.csv` (passage_id, target_no, surface: the class is withheld), `sample_meta.json`. The class key is outside the repository until scoring.

## Stage 2 — two blind translators
Each translator session receives `passages.jsonl` and `translator_targets.csv` and nothing else from the project. For each passage: an English translation (scholarly register, keep technical terms technical, do not paraphrase around a term), then for each listed target the single English word or phrase used for it in the translation, and `uncertain` = y/n. Outputs:
- `data/qc/mt2026/translation_<model>.jsonl` — `{passage_id, translation}`
- `data/qc/mt2026/renderings_<model>.csv` — `passage_id, target_no, surface, rendering, uncertain(y/n), note`
Translators: `claude-fable-5-1` and `claude-opus-5-5`, separate sessions, no shared context.

## Stage 3 — score: `pipeline/mt2026/score_consistency.py`
Joins the two rendering files with the class key, applies the normalisation (documented in the script, identical across classes), computes 1–4 above, writes `mt2026_summary.json`, `term_disagreements.csv` (every target with both renderings and the verdict), `passage_table.csv`, and a one-paragraph `mt2026_result.md` written from the numbers, whatever they say.

## Outcomes and what each means
- Punch ≫ control and ρ > 0: the map still points at the unstable vocabulary under 2026 models; a short second paper or a §7 addendum.
- Punch ≈ control: the 2026 model has closed the gap on this vocabulary at the term level; report as a negative result (the map's *diagnostic* claim weakens, the *coverage* claim — which words lack lexicon support — does not).
- Either way the result is reported. No pre-registration file existed before today; this spec, committed before stage 2 ran, is the pre-registration.
