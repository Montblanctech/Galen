# Galen First Drafts — judge v0.3 (check c), pre-registered note

**Date:** 2026-11-10, written and committed before any v0.3 judge call. Applies to a re-judging of all nine published works; nothing else in the pipeline changes (renderings, alignment, back-translation, term agreement and the calibration result stay as published).

## Why
Check (c) asks a judge model whether an English rendering of a Greek word falls within the senses of its LSJ entry *in this sentence*. Its gate is 20 salted controls: 10 anchors expected `in_range`, 10 plants expected `out_of_range`, and it must get all 20. Under v0.2 the gate failed on 8 of the 9 works (12–19 of 20). Reading the misses:

- **Almost all misses were anchors.** The v0.2 anchor was the LSJ entry's first-sense gloss. That gloss is often not the sense in Galen's sentence ("snub-nosed", "of the head", "coming alongside of"), so a judge that reads the context correctly says `out_of_range`. These controls tested the wrong thing.
- **One anchor was garbage** ("apph") that the validator let through.
- **Five controls in *Composition of Drugs by Kind* got no answer at all.** The judge returned fewer lines than items for some groups.
- **Plants were answered correctly** whenever they were answered.

## What changes
1. **Anchors (v0.3).** Each anchor is a target whose two independent renderings (A and B) agree after normalisation (`score_consistency.norm`). The shared rendering must also pass `valid_anchor_gloss`, and at least one of its content words must occur in that target's own LSJ entry. The anchor item shows that shared rendering. Such a rendering is right in context by the agreement of two translators and attested by the lexicon. One anchor per lemma; 10 per work; seed **20261111**.
2. **Re-ask.** Items the judge leaves unanswered are sent once more, in groups of their own, with the same system prompt. Anything still unanswered counts as a miss.
3. **Unchanged.** Plants, the judge prompt, the model (`claude-sonnet-5-5`, effort high), groups of ten, whole LSJ entries, the gate (**20/20**), the in-range share threshold (≥ 0.80) and the out-of-range threshold (≤ 2 items per unit). Unit verdicts use the same rule: a unit fails when it fails two of (a)–(c).

## Known limit, stated before the run
v0.3 anchors come from items where A and B agree. Agreement is evidence, not proof, that a rendering is right. A judge that simply trusts agreement could pass the anchors without reading the entry. The plants are what catch a judge that says `in_range` to everything. Both kinds must pass.

## How it runs
- For each work, the v0.2 judge files move to `judge_v02/` in that work's folder; they are kept, not deleted.
- Then `checks.py build-judge --anchors v03 --seed 20261111` (key outside the repository), `checks.py api-judge --mode batch`, `checks.py score`, and the page is rebuilt.
- Batch mode, Message Batches API.
- Results: each work's `checks.json`, and a line in each README.
- If a work's v0.3 gate still fails, it is reported as failed, as before.
