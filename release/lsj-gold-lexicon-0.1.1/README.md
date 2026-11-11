# LSJ-Gold lexicon 0.1.1: Ancient Greek form → lemma list

> **Superseded by [LSJ-Gold lexicon 0.1.2](../lsj-gold-lexicon-0.1.2/) (2026-11-11)**, which sets aside 617 of the pairs below for review (616 that rest only on a word LSJ quotes and that Dilemma lemmatizes differently, about one in seven of those read being wrong, and one pair found wrong by reading). This folder is unchanged.

A plain list of Greek word forms and their dictionary headwords, for lemmatizer dictionaries. Every row is a form
that the Liddell–Scott–Jones lexicon (LSJ) cites under a headword, found again in a real edition by
[LSJ-Gold 0.1.1](../lsj-gold-0.1.1/) (71,974 relocated loci over 54 authors). Made for
[stanfordnlp/stanza#1732](https://github.com/stanfordnlp/stanza/issues/1732); usable by any system.

Built by `galen-density-map/pipeline/lsjgold/make_lexicon.py` from `release/lsj-gold-0.1.1/lsj_gold.csv`, 2026-11-11,
with the same rules as 0.1. Nothing in the lexicon is model-written or inferred: rows are counted from LSJ-Gold,
filtered by the fixed rules below, and split by a fixed hash.

## What changed from 0.1

LSJ-Gold 0.1.1 drops the loci that 0.1 validated only because the token matched one word of a phrase LSJ quotes
(see the erratum in [`../lsj-gold-0.1.1/README.md`](../lsj-gold-0.1.1/README.md)). The lexicon follows:

- **16,397 of 0.1's 45,886 pairs are out of the lexicon.** None of them had a locus that Morpheus confirms; each rested
  only on a phrase match. Most are probably right, some are not (`Ἕκτορα` under ἐκφέρω, `μηδείς` under μή). They are
  kept, flagged, in `phrase_only_pairs.tsv` (below), never in the lexicon files.
- **369 pairs are new.** Their forms were ambiguous in 0.1 only because a phrase match had added a wrong second
  headword; with it gone they resolve (`περὶ` → περί, `πόλεις` → πόλις, `ἄλλος` → ἄλλος, `χάριτος` → χάρις).
- Every other pair is unchanged. 0.1 stays available and citable as it was.

If you used 0.1, swap in `lexicon_all.tsv` (or `lexicon_train.tsv`) from here.

## Files

| file | rows | what |
|---|---|---|
| `lexicon_all.tsv` | 29,858 | every unambiguous form → lemma pair, 10,325 headwords |
| `lexicon_train.tsv` | 26,955 | the pairs of the 9,326 headwords outside the held-out slice |
| `lexicon_heldout.tsv` | 2,903 | the pairs of the 999 held-out headwords |
| `heldout_headwords.txt` | 999 | the held-out headwords, one per line |
| `ambiguous_forms.tsv` | 452 | forms attested under two or more headwords, with each candidate and its count; not in the lexicon |
| `phrase_only_pairs.tsv` | 16,397 | the 0.1 pairs that rest only on a phrase match, with a second opinion; not in the lexicon |
| `stats.json` | | every count on this page |

Columns of the lexicon files (tab-separated, UTF-8, NFC):
`form`, `lemma` (LSJ headword), `loci` (LSJ-Gold loci for the pair), `morpheus_loci` (loci where Morpheus analyses the
form to the headword), `quoted_loci` (loci validated by LSJ's own quoted single word), `n_authors`, `authors` (TLG ids),
`lsj_entry` (Perseus LSJ entry key).

26,863 of the 29,858 pairs have at least one locus validated by Morpheus; the other 2,995 are validated by the single
word LSJ quotes at the citation.

## `phrase_only_pairs.tsv`

The 16,397 pairs that left the lexicon, for anyone who wants more coverage and accepts the risk. Columns: `form`,
`lemma`, `loci`, `n_authors`, `authors`, `lsj_entry` (as in 0.1), then `dilemma_lemma` and `dilemma_agrees`: what
Dilemma 1.3.15 (Open Greek, LSJ convention, lexicon only, no context) returns for the bare form, and whether it matches
the LSJ headword accent-blind (`yes`, `no`, `unresolved`).

Dilemma agrees on 14,428, disagrees on 1,844, and leaves 125 unresolved. For scale, it agrees on 27,784 of the
29,831 lexicon pairs it resolves (93.1%, against 88.7% here). A disagreement is not proof of an error: many are
convention differences (`ἀγκοίνῃσιν`: ἄγκοινα in LSJ, ἀγκοίνη in Dilemma) and some are Dilemma's own mistakes. Two
cautions: filtering by `dilemma_agrees` brings Dilemma's conventions into your dictionary, and a system trained on
these pairs should not be compared with Dilemma on LSJ-Gold as if independent.

## Rules

1. Forms and headwords are Unicode NFC. Forms keep their case and accents as printed in the edition, so a word
   before another word carries a grave (`αἰανὴς`); normalise on your side if your system expects acute.
2. LSJ's vowel-quantity marks in headwords (`^` short, `_` long, as in `γόνυ^`) are removed: 543 rows. They are
   markup, not spelling.
3. Headwords with characters outside Greek letters and combining marks are left out, not repaired: 238 rows. Most
   are capitals the Perseus LSJ XML writes as a detached breathing (`ʼ ́αρης` for Ἄρης).
4. Forms carrying punctuation are left out: 4 rows.
5. A form attested under two or more headwords is ambiguous. It goes to `ambiguous_forms.tsv`, never into the
   lexicon: 452 forms. Some are true homographs (`ἄξω`: ἄγω or ἄγνυμι); some are LSJ citing a passage under a
   compound's entry. Both kinds are kept out of the lexicon.

## Held-out slice and fair comparison

A headword is held out when `sha256("lsjgold-lexicon-0.1:" + headword) mod 10 == 0`, about one headword in ten. The
salt is the same as in 0.1, so a headword held out in one version is held out in the other. No headword has forms on
both sides. A lemmatizer trained with `lexicon_train.tsv` has never seen any form of a held-out headword, so it can
still be scored fairly on the 6,806 LSJ-Gold 0.1.1 loci of those headwords. A system trained with `lexicon_all.tsv`
has seen every LSJ-Gold form, so its full LSJ-Gold score is no longer a test. The LSJ-Gold leaderboard will show
dictionary-trained models in their own rows and report them on the held-out loci.

## Licence and citation

CC BY 4.0, like LSJ-Gold. Underlying sources: the Perseus LSJ XML (CC BY-SA 3.0), First1KGreek and Perseus
canonical-greekLit editions (CC BY-SA 4.0). Cite LSJ-Gold: Pepperman, W. (2026), *LSJ-Gold*, Galen Density Project,
doi:10.5281/zenodo.24046260, and name this file set as "LSJ-Gold lexicon 0.1.1".
