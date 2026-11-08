# MT-2026 constrained-terminology demonstration — plan §10, pre-registered 2026-11-06

**Status:** SPEC committed before any translator or judge ran; RUN and SCORED 2026-11-06, result in `galen-density-map/data/qc/mt2026/constrained/constrained_result.md` (the LSJ-first-gloss glossary was obeyed 100% and judged worse in ~3/4 of decided pairs). Builds on `mt2026_consistency_probe_spec.md` (40 passages, 306 targets, two blind translators, result: no punch/control difference).

**Question.** The plan's §10 said: define ten terms properly, feed them to the MT pipeline as constrained terminology, re-run on passages, show the delta. The 11/05 probe measured *stability*, which constrained terminology raises by construction (both translators are told the same rendering), so the stability delta on the ten terms is **compliance**, not a finding. What can be measured honestly:

1. **Compliance**: share of the ten-term targets the translator renders with the supplied rendering (normalised match).
2. **Spillover on other targets**: cross-translator disagreement on the *other* targets in the same passages, with vs without the glossary. Prediction if the glossary helps beyond its own terms: lower; if it only pins its terms: unchanged.
3. **Run-to-run baseline**: each translator's fresh no-glossary renderings vs its own 11/05 renderings on the same targets (how much a model wobbles against itself; the floor below which cross-translator figures are noise).
4. **Blind paired quality judgment**: for every (passage, translator) the glossary and no-glossary translations are shown to a judge in random A/B order, judge blind to condition, with the Greek. Judge picks the translation that renders Galen's technical content more precisely, or tie, and names any term it thinks is wrong. Reported: P(glossary preferred) per judge with Wilson 95%, tie rate, per-translator split. Two judge models.

**Terms (ten, chosen by rule before the run; the rule is the registration).** From the punch-list targets of the 40 passages: `thin` tier (an LSJ entry exists, so every definition is LSJ's, not written by a model), ranked by observed 11/05 disagreement + self-flagged uncertainty, then by number of target occurrences; function words, comparatives and non-medical abstractions excluded (ἔνιοι, βελτίων, ποιότης). Result: δύσκρατος, δυσκρασία, ῥευματικός, ψωρώδης, δακνώδης, ἐγκηρίς, ῥητίνη, μαλακτικός, ψιμύθιον, χαλβάνη. **Definition** = the Perseus LSJ entry text (as in `attributed_punch_list.csv`, ≤600 chars). **Preferred rendering** = LSJ's first English gloss, extracted mechanically (first English clause of the entry), so no model wrote it. Passages = every 11/05 passage with at least one of these as a target.

**Conditions.** Two fresh translator sessions per model (claude-fable-5-1, claude-opus-5-5): C0 = exactly the 11/05 instructions, no glossary; C1 = the same plus `terminology.csv` and the instruction "where one of these terms occurs, use the preferred rendering; everything else as before". Sessions see nothing else from the project. Judges: claude-sonnet-5-5 and claude-opus-5-5, fresh sessions, A/B order randomised with seed 20261106, key outside the repo until scoring.

**Normalisation** = `score_consistency.norm` (same FOLD, same stop list), applied identically to all conditions.

**Honesty clauses.** A model judge of Greek→English is weak evidence and shares lineage with the translators; a preference is not a correctness measure. With ~18 passages × 2 translators the judgment has roughly ±16 points of interval on a preference rate. Compliance is reported as compliance. Nothing here is a scholar's definition: the glossary is LSJ's text. Whatever the numbers say is written up (`data/qc/mt2026/constrained/constrained_result.md`).

**Files.** `pipeline/mt2026/demo_build.py` (terms, glossary, passage subset, both target lists), `demo_judge_pairs.py` (A/B packets + private key), `demo_score.py`. Outputs under `data/qc/mt2026/constrained/`.
