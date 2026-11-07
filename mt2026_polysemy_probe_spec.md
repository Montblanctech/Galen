# MT-2026 polysemy probe — ROADMAP item 9, pre-registered 2026-11-06

**Status:** SPEC committed before any translator ran; RUN and SCORED 2026-11-06 (`galen-density-map/data/qc/mt2026/polysemy/polysemy_result.md`): the prediction failed; polysemy_risk is not less stable than genuinely_hard in any of the six comparisons; uncertainty flags track the medical-only class instead. Builds on `mt2026_consistency_probe_spec.md` (40 passages, result: punch ≈ control) and the constrained-terminology run (within-model run-to-run instability 6–11% on ordinary targets, 15–27% on ten technical terms).

**Question.** The 11/05 probe's write-up pointed at the **polysemy quadrant** of the four-way classification (`outputs/four_way_classification.csv`: lemmas over-used in Galen's medical works *and* common outside them, so the sense that is meant is in play) as the better candidate for where 2026 rendering is unstable, against the **genuinely hard** quadrant (medical-only vocabulary). Test it directly, at the term level, with three model families and two independent runs each, so that cross-model and within-model instability are separated.

**Design.**
- Passages: the same 40 (`data/qc/mt2026/passages.jsonl`), unchanged.
- Targets: per passage, up to 4 `polysemy_risk` and up to 4 `genuinely_hard` NOUN/ADJ tokens (distinct lemmas within a passage, excluding the 11/05 targets' positions), drawn with seed 20261106 from the odyCy token stream; class withheld from translators; key outside the repo until scoring. Expected ≈ 150 per class.
- Translators: claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5; **two fresh sessions each** (run A, run B), identical 11/05 instructions, no glossary. Six sessions, no shared context.
- Normalisation: `score_consistency.norm` (same FOLD and stop list), identical across classes.

**Measures (all with Wilson 95%, class difference with two-proportion z and CI).**
1. **Within-model run-to-run disagreement** per class, per model (A vs B).
2. **Cross-model disagreement** per class, per model pair (run A of each), and the three-way "all three agree" rate.
3. **Self-flagged uncertainty** per class (secondary, labelled weak).
4. **Per-lemma**: lemmas appearing as targets in ≥2 passages: within-run consistency per class.
Prediction being tested: polysemy_risk > genuinely_hard on measures 1–2. The 11/05 pattern (instability on sense-loaded ordinary words) predicts yes; the constrained run's ten-term result (technical terms unstable within a model) predicts the opposite or a tie. Either way is reported.

**Honesty clauses.** All three translators share a developer and training lineage; disagreement is not error; ~150 targets per class give roughly ±7 points on a class rate, the headline is the difference; the quadrant labels come from the project's own frequency contrast, and `genuinely_hard` is a frequency label, not a judgment that the word is hard for a human.

**Files.** `pipeline/mt2026/polysemy_sample_targets.py` (targets + private key), `polysemy_score.py`; outputs under `data/qc/mt2026/polysemy/`; result paragraph `polysemy_result.md` written from the numbers whatever they say.
