# LSJ-Gold lexicon 0.1: Ancient Greek form → lemma list

A plain list of Greek word forms and their dictionary headwords, for lemmatizer dictionaries. Every row is a form
that the Liddell–Scott–Jones lexicon (LSJ) cites under a headword, found again in a real edition by
[LSJ-Gold 0.1](../lsj-gold-0.1/) (93,926 relocated loci over 54 authors). Made for
[stanfordnlp/stanza#1732](https://github.com/stanfordnlp/stanza/issues/1732); usable by any system.

Built by `galen-density-map/pipeline/lsjgold/make_lexicon.py` from `release/lsj-gold-0.1/lsj_gold.csv`, 2026-11-10.
Nothing in it is model-written or inferred: rows are counted from LSJ-Gold, filtered by the fixed rules below, and
split by a fixed hash.

## Files

| file | rows | what |
|---|---|---|
| `lexicon_all.tsv` | 45,886 | every unambiguous form → lemma pair, 14,875 headwords |
| `lexicon_train.tsv` | 41,433 | the pairs of the 13,406 headwords outside the held-out slice |
| `lexicon_heldout.tsv` | 4,453 | the pairs of the 1,469 held-out headwords |
| `heldout_headwords.txt` | 1,469 | the held-out headwords, one per line |
| `ambiguous_forms.tsv` | 922 | forms attested under two or more headwords, with each candidate and its count; not in the lexicon |
| `stats.json` | | every count on this page |

Columns of the lexicon files (tab-separated, UTF-8, NFC):
`form`, `lemma` (LSJ headword), `loci` (LSJ-Gold loci for the pair), `morpheus_loci` (loci where Morpheus analyses the
form to the headword), `quoted_loci` (loci validated by LSJ's own quoted form), `n_authors`, `authors` (TLG ids),
`lsj_entry` (Perseus LSJ entry key).

## Rules

1. Forms and headwords are Unicode NFC. Forms keep their case and accents as printed in the edition, so a word
   before another word carries a grave (`σαγὴν`); normalise on your side if your system expects acute.
2. LSJ's vowel-quantity marks in headwords (`^` short, `_` long, as in `γόνυ^`) are removed: 659 rows. They are
   markup, not spelling.
3. Headwords with characters outside Greek letters and combining marks are left out, not repaired: 351 rows. Most
   are capitals the Perseus LSJ XML writes as a detached breathing (`ʼ ́αρης` for Ἄρης).
4. Forms carrying punctuation are left out: 16 rows.
5. A form attested under two or more headwords is ambiguous. It goes to `ambiguous_forms.tsv`, never into the
   lexicon: 922 forms. Some are true homographs (`ἄξω`: ἄγω or ἄγνυμι); some are LSJ citing a passage under a
   compound's entry. Both kinds are kept out of the lexicon.

26,525 of the 45,886 pairs have at least one locus validated by Morpheus; the rest are validated by the form LSJ
quotes at the citation.

## Held-out slice and fair comparison

A headword is held out when `sha256("lsjgold-lexicon-0.1:" + headword) mod 10 == 0`, about one headword in ten.
No headword has forms on both sides. A lemmatizer trained with `lexicon_train.tsv` has never seen any form of a
held-out headword, so it can still be scored fairly on the 8,892 LSJ-Gold loci of those headwords. A system
trained with `lexicon_all.tsv` has seen every LSJ-Gold form, so its full LSJ-Gold score is no longer a test.
The LSJ-Gold leaderboard will show dictionary-trained models in their own rows and report them on the held-out loci.

## Licence and citation

CC BY 4.0, like LSJ-Gold. Underlying sources: the Perseus LSJ XML (CC BY-SA 3.0), First1KGreek and Perseus
canonical-greekLit editions (CC BY-SA 4.0). Cite LSJ-Gold: Pepperman, W. (2026), *LSJ-Gold*, Galen Density Project,
doi:10.5281/zenodo.24046260, and name this file set as "LSJ-Gold lexicon 0.1".
