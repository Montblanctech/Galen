# LSJ-Gold lexicon 0.1.2: Ancient Greek form → lemma list

A plain list of Greek word forms and their dictionary headwords, for lemmatizer dictionaries. Every row is a form
that the Liddell–Scott–Jones lexicon (LSJ) cites under a headword, found again in a real edition by
[LSJ-Gold 0.1.1](../lsj-gold-0.1.1/) (71,974 relocated loci over 54 authors). Made for
[stanfordnlp/stanza#1732](https://github.com/stanfordnlp/stanza/issues/1732); usable by any system.

**Use this version.** It is [0.1.1](../lsj-gold-lexicon-0.1.1/) with its weakest 617 pairs set aside for review
(below). 0.1 and 0.1.1 stay as they were.

Built by `galen-density-map/pipeline/lsjgold/make_lexicon.py` (0.1.1) and then
`galen-density-map/pipeline/lsjgold/lexicon_review.py` (this step), 2026-11-11. Nothing in the lexicon is
model-written or inferred: every pair is counted from LSJ-Gold. Dilemma is used only to set pairs aside, never to add
or change one.

## Files

| file | rows | what |
|---|---|---|
| `lexicon_all.tsv` | 29,241 | the form → lemma pairs, 10,076 headwords |
| `lexicon_train.tsv` | 26,398 | the pairs of the 9,098 headwords outside the held-out slice |
| `lexicon_heldout.tsv` | 2,843 | the pairs of the 978 held-out headwords |
| `heldout_headwords.txt` | 978 | the held-out headwords that have pairs here, one per line |
| `review_pairs.tsv` | 617 | pairs set aside for review (below), each with its reason; not in the lexicon |
| `ambiguous_forms.tsv` | 452 | forms attested under two or more headwords, with each candidate and its count; not in the lexicon |
| `phrase_only_pairs.tsv` | 16,397 | the 0.1 pairs that rest only on a phrase match, with Dilemma's lemma; not in the lexicon |
| `dilemma_lemmas.tsv` | 46,255 | Dilemma's lemma for every form above, as used here |
| `stats.json` | | the counts of this step |

Columns of the lexicon files (tab-separated, UTF-8, NFC): `form`, `lemma` (LSJ headword), `loci` (LSJ-Gold loci for
the pair), `morpheus_loci` (loci where Morpheus analyses the form to the headword), `quoted_loci` (loci validated by
the single word LSJ quotes), `n_authors`, `authors` (TLG ids), `lsj_entry` (Perseus LSJ entry key).
26,862 pairs have at least one Morpheus-validated locus; the other 2,379 rest on LSJ's quoted word.

## What changed from 0.1.1: `review_pairs.tsv`

A pair rests either on Morpheus (the form analyses to the headword) or only on LSJ quoting that single word at the
citation. We read random samples of the pairs on which Dilemma 1.3.15 (Open Greek, LSJ convention, lexicon only,
bare form) gives a different lemma; the reading is ours, not a specialist's.

- **Quoted-only pairs where Dilemma differs: 10 of 68 read were wrong** (`δήμαρχος` under δημαρχέω, `εὐκαρπείᾳ` under
  εὐθαλής, `ἀντιγράφων` under ἀντιβολή). LSJ's entries often quote a related or cross-referenced word, and that
  word passed as the headword's own form. All 616 such pairs leave the lexicon for `review_pairs.tsv`, with
  Dilemma's lemma beside each. Most are probably right; they come back once checked one by one.
- **Morpheus-validated pairs where Dilemma differs: 1 of 132 read was wrong** (`πόλεων` under πολύς: the accent-blind
  match let the genitive of πόλις pass as Epic πολέων; that pair moves to `review_pairs.tsv`). The rest stay; most differences are conventions (`σαφῶς` under
  σαφής, adverbs being under their adjectives in LSJ) or Dilemma's own error (`ἄπειρον` as ἤπειρος).
- Where Dilemma agrees (27,784 pairs) we found nothing wrong in the samples read, including 80 of the 2,368
  quoted-only ones.

From these samples we expect wrong pairs to be rare, of the order of a few dozen among the 29,241 (about 0.1%). The
samples are small, so that is an estimate, not a bound. Corrections are welcome.

**The benchmark has the same weakness.** The 651 LSJ-Gold 0.1.1 loci behind the 616 quoted-only pairs set aside here
are of the same kind, so roughly 100 of its 71,974 loci (about 0.1%) may carry a wrong gold: smaller than the width
of every system's interval on the leaderboard. LSJ-Gold 0.1.1's data are unchanged; its next version will check
those loci one by one.

## One limit of any list like this

"Unambiguous" means unambiguous **within LSJ-Gold**: the form is attested under one headword at the loci LSJ cites.
Greek homographs can still belong elsewhere in other texts. `ἄξειν` is here under ἄγνυμι, the only headword LSJ
cites it for, but it is far more often the future of ἄγω; `ἀπεῖναι` is here under ἀφίημι (Ionic) and is usually from
ἄπειμι. A lemmatizer that trusts the list over context will make those mistakes. `ambiguous_forms.tsv` lists the
forms LSJ-Gold itself attests under two headwords.

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

A headword is held out when `sha256("lsjgold-lexicon-0.1:" + headword) mod 10 == 0`, about one headword in ten, the
same hash as in 0.1 and 0.1.1. No headword has forms on both sides. A lemmatizer trained with `lexicon_train.tsv` has
never seen any form of a held-out headword, so it can still be scored fairly on the 6,806 LSJ-Gold 0.1.1 loci of
held-out headwords. A system trained with `lexicon_all.tsv` has seen every LSJ-Gold form, so its full LSJ-Gold score
is no longer a test.

## Licence and citation

CC BY 4.0, like LSJ-Gold. Underlying sources: the Perseus LSJ XML (CC BY-SA 3.0), First1KGreek and Perseus
canonical-greekLit editions (CC BY-SA 4.0). Cite LSJ-Gold: Pepperman, W. (2026), *LSJ-Gold*, Galen Density Project,
doi:10.5281/zenodo.24046260, and name this file set as "LSJ-Gold lexicon 0.1.2".
