# First Drafts: the recipe (methods note, 2026-11-12)

First Drafts turns an untranslated pre-modern text into a machine first draft with an apparatus: two independent
model renderings per passage, every hard word tied to its dictionary entry, three machine checks per passage, and
the failures marked and kept. It was built on Galen (fourteen works, cycles 1 to 4). This note describes the method
apart from Galen: what goes in, what each stage writes, what the checks can and cannot tell you, and how to add a
language. The specs it summarises are `firstdrafts_v0_spec.md` and `firstdrafts_v02_spec.md` at the repository root.

## What goes in

1. **A TEI text.** Any TEI/EpiDoc edition with an `edition` div (First1KGreek, Perseus canonical-latinLit and
   similar). The text must carry the reference system scholars cite it by: page breaks (`<pb n>`, Kühn pages for
   Galen), milestones (`<milestone unit="section" n>`, Pliny), or numbered divs (`<div subtype="section" n>`,
   Vitruvius).
2. **A work config** (JSON, `configs/<slug>.json`): where the text is, its language, which element marks a unit
   boundary and how its number becomes a citation id, which tagger and lexicon to use, and the target-word rule.
   Galen works need no file: `--work <slug>` builds the config from `common.WORKS` (`generic.galen_config`).
3. **A lexicon** with an adapter: LSJ for Greek, Lewis & Short for Latin. The lexicon supplies the headword and
   entry every target word is checked against, and its sense count marks how thinly it covers a word.
4. **A tagger** (lemma + part of speech) and a **reference frequency list** made by the same tagger over a large
   corpus, used to find the words that are rare. Both are local and deterministic.

## The stages and their files

Everything is written to `outputs/firstdrafts/<slug>/` (`FIRSTDRAFTS_OUT=<dir>` redirects every stage to a copy).
Stages 1, 2, 4 and 6 are deterministic and call no model. Every stage takes `--work <slug>`: a Galen slug resolves
through `common.WORKS`, any other slug through `configs/<slug>.json` (`common.work_config`, the one loader).

| stage | script | writes | model? |
|---|---|---|---|
| 1. units and targets | `generic.py` (any text) or `units.py` (Galen; same output) | `units.jsonl`, `targets.csv`, `units_meta.json`, `front_end.json`; `tagged.jsonl` (when the tagger runs here) | no |
| 2. lexicon entries | `lsj_index.py` (LSJ, or Lewis & Short when the config's lexicon is `ls`) | `lsj_entries.json`, `lsj_entries_missing.json` | no |
| 3. two renderings | `translate.py build`, then `api` | `requests.jsonl`, `renderings_fable-5-1.jsonl`, `renderings_opus-5-5.jsonl`, `usage.jsonl` | yes |
| 4. alignment and term table | `align.py` | `alignment.json`, `term_table.csv`, `align_meta.json` | no |
| 5. machine checks | `checks.py build-bt / api-bt / build-judge / api-judge / score` | `backtranslation_A/B.jsonl`, `judge_sheet.jsonl`, `judge_answers.jsonl`, `checks.json` | yes (bt, judge) |
| 6. page | `page.py` (`--dest <dir>` writes elsewhere and skips the landing rebuild; `--build-date`) | `docs/first-drafts/<slug>/index.html`, `data.json` | no |

**Dry run.** `translate.py api`, `checks.py api-bt` and `checks.py api-judge` take `--dry-run`: the stage builds
every request exactly as it would send it and writes `dryrun_<stage>.jsonl` (id, system, user, prompt SHA-256); no key
is read, no client is made, nothing is sent. The translate dry run gives each unit the term memory built from the
renderings on disk of the units before it in send order (a fresh work has none).

**Stage 1 in detail** (`generic.py`):

- *Tokens.* Whitespace tokens of the edition div; notes, apparatus and readings (`note`, `app`, `rdg`, plus `del`
  for editions that mark deletions) are skipped, their tails kept. Each boundary element becomes an inline marker
  `[ref]` (Kühn `[197]`, Vitruvius `[3.1.2]`), so the reference survives into the prompt and the English. Every token
  remembers its current reference and its structural levels (book, chapter).
- *Units.* At each marker the boundary moves back to the last sentence end since the previous boundary, so no unit
  starts or ends mid-sentence; a unit records every reference it touches. A unit shorter than `min_tokens` merges
  into the next (25 for Kühn pages, 100 for Vitruvius sections, which in book 3 run 16 to 145 words, median 67); a title line alone
  joins the unit it heads; an empty tail joins the previous unit. The unit id is the first and last reference
  (`K18a.196-197`, `Vitr.3.1.7-3.1.8`). A config can keep only some books (`keep`).
- *Tagging.* `odycy_precomputed` aligns a frozen odyCy stream to the TEI words (Galen); `latincy` runs LatinCy
  `la_core_web_lg` on the TEI words themselves (no alignment) through `latin_tagger.py` in `.venv-lat`.
- *Lexicon resolution.* `lsj`: the Dilemma lemma (LSJ convention), else the odyCy lemma, looked up in the stage-06
  LSJ index. `ls`: the LatinCy lemma, else Collatinus's first lemma, else Collatinus's only lemma that has an entry,
  looked up in an index of the Perseus Lewis & Short XML (built once, cached in `data/firstdrafts_cache/`). The
  tier is *absent* (no entry), *thin* (at most one sense, the threshold the Galen punch list used) or *rich*.
- *Targets.* NOUN and ADJ tokens, at most 8 distinct lemmas per unit, never in a title line, never a proper name.
  Two rules:
  - `galen`: the Galen punch list (Galen-key words thin or absent in LSJ) first, then the four-way
    `genuinely_hard` words, rarest in whole Galen first. This needs the Galen density-map outputs, so it applies to
    Galen only.
  - `lexicon_rarity` (any text): a word is a candidate when neither its tagger lemma nor its lexicon lemma is among
    the `freq_top_n` (5,000) most frequent lemmas of the reference corpus. Candidates rank lexicon-thin first, then
    rich, then absent (absent is mostly lemmatizer debris: the Galen absent-tier reader pass found most of that tier
    to be artifacts), and within a rank the rarest in the reference corpus first.
- The column and field names are units.py's, so stages 2 to 6 read the files unchanged. Two names are historical
  and mean the same thing for every language: `greek` / `greek_plain` hold the source text, `odycy_lemma` is the
  tagger's lemma and `dilemma_lemma` the lexicon-convention lemma. `punch_tier` holds the lexicon tier when it is
  thin or absent, and `punch_density_per100` counts those words per 100 tokens (the difficulty tiers come from it).
  Rarity rows add `lex_headword`, `lex_entry_id`, `lex_senses`, `lex_route` and `ref_count`.

## The three machine checks, and what they cannot catch

A unit fails when it fails two of the three (thresholds pre-registered in `checks.THRESHOLDS`).

- **(a) Back-translation.** A third model turns each English rendering back into the source language; the unit
  passes when the back-translation recovers at least half of the unit's target lemmas (40% of its content lemmas
  when it has no targets). *Cannot catch:* an English that names the right word with the wrong sense (the
  back-translation returns the same word), smooth paraphrase that keeps the terms but changes the claim, wrong
  syntax, negation or attribution.
- **(b) Agreement of the two renderings.** The two translators (different model families, same neutral prompt, no
  glossary) agree on at least 70% of the unit's target terms. *Cannot catch:* both models wrong the same way, which
  is likely for a word both learned from the same standard translation or the same dictionary gloss; agreement is
  evidence of consistency, not of correctness.
- **(c) Lexicon-anchored judge.** A model judge decides whether each target rendering lies within the senses of the
  word's whole dictionary entry, salted with 10 validated anchors and 10 planted wrong renderings it must get right
  (20/20 gate, key kept outside the repository until scoring); the unit passes with at least 80% in range and at
  most 2 out. *Cannot catch:* a sense the dictionary lacks (the thin and absent words, the very ones the method
  targets, get the weakest check), a rendering in range but wrong for this passage, anything outside the target
  words. Targets without an entry are not judged at all.

None of the checks reads the passage as a scholar would. A passage without the red rule is not checked; it only did
not fail. The reference check (d), on calibration passages with a published human translation, is reported beside
the three and is never part of the verdict.

## Adding a language

1. **Text.** A TEI edition with the citation system in its markup. Write the config: `break` (the element, a
   `match` on its attributes, the attribute holding the number, and a `ref` template such as `{book}.{chapter}.{n}`),
   `levels` (the divs that give book and chapter), `sentence_end` (and `sentence_end_strip` for closing quotes or
   brackets, `not_sentence_end_re` for abbreviations such as Latin praenomina), `min_tokens`, the `id` and `locus`
   prefixes.
2. **Tagger.** Any tagger giving a lemma and a Universal POS tag per word. Add a `tag_<name>` adapter in
   `generic.py` that fills `lemma`, `pos` and `ody_i` (index into the stream that `checks.py` slices for content
   lemmas). If the tagger lives in its own environment, follow `latin_tagger.py` (JSON in, JSON out, one subprocess).
3. **Lexicon.** An adapter class with `resolve(token)` (lexicon lemma, headword, entry id, sense count, tier, route),
   `is_proper(token)` and `key` (the accent- and spelling-blind comparison key, shared with the frequency list). An
   index of the dictionary XML that maps every headword and variant spelling to its entry is enough.
4. **Reference frequency.** The same tagger run over a large corpus of the language; `reference_counts` needs only
   lemma counts keyed by the lexicon key. Exclude the work itself.
5. **Check the units by reading them** before any model call: a seeded random sample, each boundary at a sentence
   end, each id matching the edition's numbering (the Latin smoke test below is the template).
6. **Back end.** Add the language to `common.LANG` (its name, adjective, back-translation JSON key) and, for a new
   dictionary, to `common.LEXICA` (short and full name, link pattern) with a `build_<lexicon>` branch in `lsj_index.py`
   that writes the same `lsj_entries.json` fields, and a `lemma_key_fn` entry. The config adds the prompt facts:
   `author`, `title_lat`, `title_eng`, `edition_desc` (how the translator prompt names the edition), `edition_short`,
   `citation` (the user-prompt work line), `marker_label` (page, section, line), `marker_re` (the marker regex),
   `bt_style` (the back-translation register), `text_credit`, and `doi` once one is assigned.
7. **Calibrate check (a) with an echo** before spending: write the source itself as a fake back-translation of both
   renderings and score it. A perfect back-translation should pass every unit; the shortfall is the measuring
   instrument's own loss (Vitruvius 3: term recall 0.978, content recall 1.0).

## Worked example 1: Galen, *Adversus Lycum* (grc, Kühn pages)

Config: `configs/adversus-lycum.json` (identical to `generic.galen_config("adversus-lycum")`): break `<pb n>` with
ref `{n}`, levels book/chapter divs, sentence end `.` and `;` (the Greek question mark), `min_tokens` 25, id
`K18a.<page>`, tagger `odycy_precomputed` (`data/lemmatized/galen_nonmedical/...tlg093...jsonl`), lexicon `lsj`,
target rule `galen`.

    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/generic.py --work adversus-lycum --out <scratch>

Regression (2026-11-12, run to a scratch directory): for all fourteen works in `common.WORKS`, the generic front end
gives the published `units.jsonl` and `targets.csv` exactly (every unit id, boundary, Greek text, token count and
target row; the only difference is the `books` field, which units.py gained after cycle 1 and which Adversus Lycum's
published file predates), and for Adversus Lycum all four files are byte-identical to the current units.py output.

The `lexicon_rarity` rule on the same text (`--targets-rule lexicon_rarity`) chooses 196 targets against the Galen
rule's 350, 90 of them the same tokens (65 shared lemmas of 154 and 254). The difference is by design: the Galen rule
targets words that are characteristic of Galen and thin in LSJ (punch list) or hard by the four-way classification,
many of them common Greek words (ποιότης, μοῖρα, καπνός, διπλάσιος); the rarity rule targets words rare in Greek at
large (ἀνεμέσητος, ὀξυλάπαθος, ἄνυσις, ἡμιτόνος). For Galen the Galen rule stays.

## Worked example 2: Vitruvius, *De architectura* book 3 (lat, sections), the Latin smoke test

Config: `configs/vitruvius-3.json`: Perseus `phi1056.phi001.perseus-lat2` (Krohn, Teubner 1912), break
`<div subtype="section" n>` with ref `{book}.{chapter}.{n}`, refs reset on entering a book or chapter div, sentence
end `.` `?` `!` (closing quotes and brackets stripped; praenomen abbreviations excluded), `min_tokens` 100, id
`Vitr.<first>-<last>`, `keep` book 3, tagger `latincy` (LatinCy `la_core_web_lg` 3.9.8, the best system on LS-Gold:
85.3% blind), Collatinus (pycollatinus 0.1.6) as the fallback route to an L&S headword, lexicon `ls`, rule
`lexicon_rarity` with the reference list from the LS-Gold LatinCy caches over 172 Perseus editions (5.4M tokens,
Vitruvius excluded).

    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/generic.py --config pipeline/firstdrafts/configs/vitruvius-3.json \
        --out outputs/firstdrafts/_smoke_lat

Result (`outputs/firstdrafts/_smoke_lat/vitruvius-3/`): 29 units, 4,059 words (99 to 208 per unit, median 136),
209 targets (130 lexicon-thin, 76 rich, 3 absent); 158 targets resolved through the LatinCy lemma, 48 through
Collatinus, 3 not at all.

Reading check (seed 20261112, 10 of 29 units read, plus a script over all 29 against the edition's own section
divs): every unit begins at the start of its first section and ends at a sentence end; the 54 sections of book 3
each appear exactly once, whole, in document order, inside the unit whose id names them; the first unit carries the
title line *LIBER TERTIUS*. Targets are the book's technical vocabulary (*symmetria*, *commodulatio*, *scamillus*,
*eustylos*, *pseudodipteros*, *proiectura*, *voluta*). Known faults, reported and not patched: LatinCy lemma errors
pass into the targets (*normam* as *normo*, *angulares* as *angulo*, *decusis* as *decusum*), Collatinus ambiguity
leaves *octavae* unresolved (both *octava* and *octavus* have entries), and a Greek word in a `<foreign>` element
followed by its full stop gives a separate `.` token (`διπλάσιονα .`).

## The back end on a config work (2026-11-12)

Stages 2 to 6 read the work config (`common.work_config`). For a Galen work every stage takes its old path, and the
Galen prompts are the template functions filled with Galen's facts, pinned by SHA-256 in
`tests/test_firstdrafts_backend.py`. For a config work:

- `translate.py`: the system prompt is the same neutral wording with the author, language, marker kind, a real marker
  of the work and the edition filled in (`system_prompt`); the term-memory rules are unchanged; the work line comes
  from the config (`citation`); the marker-count problem check counts only reference markers (English supplied words
  are bracketed too).
- `lsj_index.py`: `lexicon.name = "ls"` builds `lsj_entries.json` from Lewis & Short (whole entry text, every sense,
  first-sense gloss = the first italic English of the first sense; keys `lsgold.latnorm.key`). The field names stay
  `lsj_*`, as stage 1's column names do.
- `align.py`: the source is split with the front end's sentence-end rule (Latin `.`, `?`, `!`, never `;`); markers by
  the config's `marker_re`; entries looked up with the language's key.
- `checks.py`: back-translation into the work's language (`bt_style`, JSON key `latin`); the judge prompt and items
  name the config's lexicon; check (a) lemmatizes each back-translation in context with LatinCy (through
  `latin_tagger.py`), adds the surface and Collatinus' first lemma per word, and reads content lemmas from
  `tagged.jsonl`.
- `page.py`: titles, the work line, the citation-marker label (`section`), the source column, the lexicon column and
  its links come from the config. Lewis & Short headwords link to Logeion with quantity marks and the prefix hyphen
  removed (`com-mŏdŭlātĭo` -> `logeion.uchicago.edu/commodulatio`). The lsgold code links no dictionary site, so
  Logeion, which the Greek pages already use and which carries Lewis & Short, was chosen. A config work's page does not
  rewrite the Galen drafts index; its citation line carries the config's `doi` or says that none is assigned yet.

**Regression (2026-11-12, scratch only, no model call).** The pre-change modules were frozen and both versions run on
copies of the published outputs of *Adversus Lycum* (50 units) and the whole of *Composition of Drugs by Kind*
(697 units, seven books): `lsj_entries.json`, `alignment.json`, `term_table.csv`, `requests.jsonl`, the term-memory
prompts of both translators in send order, both back-translation request files, the judge sheet, its group prompts
(71 and 1,072), the judge key and `checks.json`: 15 of 15 files byte-identical per work, and every `--dry-run` prompt
equals the old request byte for byte (translate 697 + 697, back-translation 697 + 697, judge 1,072 for Composition).
Pages: all 13 published works rebuilt into scratch with their published build date are identical to
`docs/first-drafts/` (39 of 39 files) once the two blocks `landing.py` adds to every public page (analytics beacon,
share tags) are set aside, and the old and new `page.py` give identical files when run side by side. The drafts index
under `docs/` is rewritten by `landing.py`, not page.py's output, so it is not compared.

**Fix found by the Latin dry run.** In the ecc0e24 front end the Latin stream index (`odycy_start`/`odycy_end`) was the
TEI word number, while `tagged.jsonl` holds only the words with Latin letters, so every numeral or Greek word shifted
the slice that check (a) reads (book 3: ids ran to 4,058 over 4,024 stream rows; an echo back-translation scored
content recall 0.885). It is now the stream position: all 29 slices equal their units' Latin words and the echo
scores 1.0. Unit text, boundaries and targets are unchanged.

**Vitruvius 3 dry run.** On a scratch copy: `lsj_index.py` resolves 118 of 158 keys (each of the 206 targets with an
entry resolves, to the entry id stage 1 found; the 40 misses are LatinCy-side lemmas with no headword);
`translate.py build` writes 29 requests (151,661 prompt characters); `api --dry-run` builds 29 prompts per
translator. On a second scratch copy with FAKE renderings (the Latin echoed as the English, Lewis & Short glosses as
the term renderings, backend `FAKE_echo`): `align.py` anchors 29 of 29 units on the section markers, `api-bt
--dry-run` builds 29 + 29 back-translation prompts, `build-judge` 432 items (412 real, 10 anchors, 10 plants) in 44
groups, `api-judge --dry-run` 44 prompts, `score` runs, and `page.py --dest <scratch>` renders the page with 162
section markers, 206 Logeion links to Lewis & Short headwords and no Kühn or LSJ label. The fake page stays in
scratch. One judge item shows a lexicon misresolution a real run would carry: *in antis* (pilasters, *antae*)
resolved to L&S *antes* (rows of vines).

**The real run** (done 2026-11-12; results in `outputs/firstdrafts/vitruvius-3/README.md`):

    cd galen-density-map
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/generic.py --config pipeline/firstdrafts/configs/vitruvius-3.json
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/lsj_index.py --work vitruvius-3
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/translate.py build --work vitruvius-3
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/translate.py api --work vitruvius-3 --model fable-5-1
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/translate.py api --work vitruvius-3 --model opus-5-5
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/align.py --work vitruvius-3
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/checks.py api-bt --work vitruvius-3 --rendering A
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/checks.py api-bt --work vitruvius-3 --rendering B
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/checks.py build-judge --work vitruvius-3 --key-out <outside the repo>/vitruvius-3_key.csv
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/checks.py api-judge --work vitruvius-3
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/checks.py score --work vitruvius-3 --key <outside the repo>/vitruvius-3_key.csv
    ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/page.py --work vitruvius-3 --dest <scratch>

Run each `api` command
first with `--dry-run` and read the prompts. Direct mode (the default, packets of 8) lets term memory build across
units; `--mode batch` sends packets of 50 cover all 29 units at once, so the translators would
see no term memory.
