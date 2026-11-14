# T2b — transcription plausibility scorer: results (v1 2026-11-13; spelling layer 2026-11-14)

The scorer is an "ancient Greek autocorrect" for HTR output of papyri. It takes a scriptio-continua
string, segments it into attested word forms, and gives the k best readings. Each reading is scored by
attestation frequency, bigram collocation and a small HTR confusion channel. Nothing is trained. Code
and commands: [`pipeline/t2b_README.md`](../../pipeline/t2b_README.md). Every number below comes from
a file in this folder.

## What it is

- **Evidence.** The unigram and bigram counts come from our own corpora: the First1K reference corpus
  and the Galen extracted text. The 19 held-out works are removed (`holdout_works.json`). That leaves
  21,560,737 tokens, 313,796 forms attested twice or more, and 6,264,923 bigram types.
  - Forms seen once (277,722 types) share one id. They are never proposed.
  - With `--dilemma`, Dilemma's `form_profile.db` (1,322,738 scriptio-continua keys) is added as
    extra unigram evidence. It is scaled to our corpus size and read in place, so no second store is
    built. Dilemma ships no bigram table, so collocation evidence is ours only.
- **Keys.** Each form is reduced to its scriptio-continua key: NFD, combining marks dropped,
  uppercase, and ς, ϲ and C all become Σ. Accent minimal pairs collapse, as they do on the papyrus.
- **Language model.** Interpolated absolute discounting with d = 0.75 (the textbook default, not
  fitted).
- **Channel.** The model can undo three kinds of error:
  - a within-class confusion: Α/Λ/Δ, Ε/Θ/Ο/Σ (lunate C), Η/Ν or Ι/Τ, at 3% per letter;
  - one lost letter per word, at 1% per letter;
  - an unknown segment, at 1e-4 and then 1/24 per letter;
  - since 2026-11-14, an ancient spelling of a form unattested as written: one of 253 rules learned from
    the editors' regularizations in papyri.info, at its measured rate (section 3 of the real case).
    The test-set table below is without it; its numbers with it are in section 3.
- **Search.** A beam search over positions with bigram state: 48 hypotheses, at most 4 per last word,
  and the top 8 candidate forms per substring.
- **Constants.** All five constants were set by hand. Only one was checked on the dev split, never on
  test: the minimum count for a proposed form, 2 vs 3. Count 2 won on every level (bigram F1
  .972/.931/.868 vs .965/.927/.862; `eval_dev_mc2.md`, `eval_dev_mc3.md`).

## Test set (no training, held out)

- **Works.** 12 held-out works, picked by a seeded shuffle of First1K works of 100 KB to 1.5 MB, plus
  Galen works of the same size. Every edition of a held-out work is excluded from the counts. The
  works:
  - Philo, *De plantatione*
  - Galen, *De placitis* and *De crisibus*
  - Archimedes, *De sphaera et cylindro*
  - Polyaenus, *Excerpta*
  - Hippocrates, *De affectionibus interioribus* and *De natura muliebri*
  - Athenagoras, *Legatio*
  - Cleomedes
  - Origen, *Philocalia*
  - Philoponus, *In De gen. an.*
  - Stephanus, *In De int.*
- **Lines.** 40 "HTR lines" per work, 480 in all. Each line is 20 to 40 letters of whole words,
  stripped to scriptio continua (`testset_test.jsonl`).
- **Noise.** Seeded, per letter: within-class confusion, off-channel substitution (any other letter,
  which the scorer cannot undo), and lost letters. These are assumptions, not measured HTR error
  rates. Measured on the injected lines:

  | level | within-class | off-channel | lost | letter error rate | lines recoverable by design |
  |---|---|---|---|---|---|
  | clean | – | – | – | 0 | 480 of 480 |
  | light | 3% | 0.5% | 1% | 4.75% | 295 of 480 |
  | heavy | 8% | 1% | 3% | 12.4% | 151 of 480 |

  A line is recoverable by design when it has no off-channel error and at most one lost letter per
  word.
- **Metrics.** All are measured in the noisy string's coordinates:
  - boundary P/R/F1 over word boundaries;
  - word recovery: the gold word found with its span and its spelling;
  - line top-1 / top-5: the whole gold word sequence is the first reading, or among the first five.

### Results (test, 480 lines; `eval_test.md`, `eval_test_dilemma.md`)

| system | level | lines | boundary P | boundary R | boundary F1 | word rec. | line top-1 | line top-5 | recoverable lines | rec. top-1 | rec. top-5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy | clean | 480 | 0.664 | 0.673 | **0.669** | 0.506 | 0.150 | 0.150 | 480 | 0.150 | 0.150 |
| greedy | light | 480 | 0.513 | 0.631 | **0.566** | 0.363 | 0.037 | 0.037 | 295 | 0.061 | 0.061 |
| greedy | heavy | 480 | 0.392 | 0.578 | **0.467** | 0.222 | 0.002 | 0.002 | 151 | 0.007 | 0.007 |
| unigram | clean | 480 | 0.965 | 0.974 | **0.969** | 0.937 | 0.773 | 0.850 | 480 | 0.773 | 0.850 |
| unigram | light | 480 | 0.886 | 0.948 | **0.916** | 0.829 | 0.406 | 0.498 | 295 | 0.661 | 0.810 |
| unigram | heavy | 480 | 0.803 | 0.905 | **0.851** | 0.685 | 0.133 | 0.206 | 151 | 0.424 | 0.656 |
| bigram_nochannel | clean | 480 | 0.961 | 0.990 | **0.975** | 0.965 | 0.848 | 0.887 | 480 | 0.848 | 0.887 |
| bigram_nochannel | light | 480 | 0.797 | 0.933 | **0.860** | 0.743 | 0.181 | 0.190 | 295 | 0.295 | 0.308 |
| bigram_nochannel | heavy | 480 | 0.641 | 0.795 | **0.710** | 0.475 | 0.023 | 0.025 | 151 | 0.073 | 0.080 |
| bigram | clean | 480 | 0.965 | 0.989 | **0.977** | 0.958 | 0.817 | 0.881 | 480 | 0.817 | 0.881 |
| bigram | light | 480 | 0.894 | 0.969 | **0.930** | 0.863 | 0.458 | 0.521 | 295 | 0.746 | 0.844 |
| bigram | heavy | 480 | 0.822 | 0.919 | **0.868** | 0.731 | 0.190 | 0.260 | 151 | 0.603 | 0.828 |
| dilemma_bigram | clean | 480 | 0.972 | 0.989 | **0.980** | 0.962 | 0.833 | 0.904 | 480 | 0.833 | 0.904 |
| dilemma_bigram | light | 480 | 0.899 | 0.970 | **0.933** | 0.866 | 0.463 | 0.537 | 295 | 0.752 | 0.871 |
| dilemma_bigram | heavy | 480 | 0.825 | 0.925 | **0.872** | 0.735 | 0.183 | 0.256 | 151 | 0.583 | 0.815 |

Systems:

- **greedy:** the baseline, greedy longest attested match with no channel.
- **unigram:** frequency only, with the channel.
- **bigram_nochannel:** collocation, no channel.
- **bigram:** the v1 scorer.
- **dilemma_bigram:** the v1 scorer plus Dilemma attestation.

### What the numbers say

- **Against the baseline.** Greedy longest-match scores boundary F1 .669 on clean text, and the
  scorer .977. The difference is the segmentation model, before any correction. Greedy almost never
  recovers a whole line (top-1 .150 clean, .002 heavy).
- **Collocation.** Bigrams help on clean text (top-1 .773 → .817) and with noise (F1 .916 → .930
  light).
- **The channel is a trade-off.**
  - Without it, F1 drops to .860 light and .710 heavy. With it, F1 is .930 and .868.
  - On clean text the channel costs a little. It "corrects" correct forms toward more frequent
    neighbours: top-1 .848 without the channel, .817 with it.
  - A deployed version should gate the channel on the HTR's own letter confidences. It does not
    have them yet.
- **Whole-line recovery under noise is modest.** Top-1 over all lines is .458 light and .190 heavy.
  On the lines the channel can undo by design, it is .746 / .603, and top-5 is .844 / .828. The rest
  of the gap on those lines is real ambiguity: Ε/Ο/Σ swaps that make another attested word, and short
  words. The lines with an off-channel error are, by construction, beyond v1.
- **Dilemma attestation adds little.** F1 rises .977 → .980 clean and .930 → .933 light, and top-5
  rises .881 → .904 clean. **This row is contaminated.** Dilemma's sources include First1K, so the
  held-out works are inside its counts. Treat it as an upper bound. How much of the gain is leakage
  is unverified.
- **Leakage not ruled out in the main rows.** Quotations of held-out works inside counted works
  (commentaries quoting Hippocrates, for instance) are not removed. The size of that effect is
  unverified.

## Real case: Philodemus, Herculaneum papyri (First1K tlg1595.tlg221 and tlg370; `philodemus_flags.*`)

Philodemus is held out of the counts, so his words cannot attest themselves.

### 1. Word division

Some papyrus lines were read in full by the editor: no brackets, dots or insertions. There are 453
such lines in tlg221 and 1,092 in tlg370. Reduced to scriptio continua and segmented, they agree with
the editor's word division as follows:

| work | lines | boundary P | boundary R | F1 | lines divided exactly as the editor did |
|---|---|---|---|---|---|
| tlg221 | 453 | .914 | .965 | **.939** | .667 |
| tlg370 | 1,092 | .949 | .982 | **.965** | .719 |

With the spelling layer (section 3). Without it: .935 and .958 F1, .658 and .657 lines exact.

Precision is lower because a line starts and ends with partial words (hyphenated across lines). The
scorer splits these into pieces.

### 2. Flags on the edited reading

Some words are skipped:
- words touching an unread gap (Leiden dots; one full stop right after a letter at the end of a word is
  punctuation, not an unread letter);
- elided words;
- letter strings the editor left unarticulated (no accent, no breathing, not an enclitic);
- a lone letter that is not a word (anything but ὁ, ἡ/ἤ, ὦ), debris of a broken line.

A word split in the digital text is joined first: two neighbours whose joined form is attested, when one
half is unattested, or when the first half ends its line (or a stray bracket or line number follows it) and
the whole is more likely than the two halves by 4 nats (ῥυ | θμῶν, παι] | γνίων). 38 words were joined.

Every other word gets a check. It is flagged if it is unattested as written (count < 2 in 21.6M tokens) and
no ancient spelling explains it (section 3), or if a form reachable through the HTR channel scores more than
4 nats better in context. The context score is P(w | prev) + P(next | w) + channel cost. A flag also says
when its proposed correction is itself a known spelling of the same word (τυ[πά]νων, πάλι), and when an
unattested word is a common ending on an attested stem (all but its last three letters begin at least three
attested forms): perhaps a rare form rather than an error.

- **Scored and flagged.** 18,592 words were scored and 624 flagged (3.4%). Before the spelling layer and
  the fixes above: 18,194 scored, 697 flagged (3.8%).
- **By kind.** 608 unattested, 8 better in-channel alternative, 8 both. 257 of the unattested are a common
  ending on an attested stem. 114 unattested words were read as ancient spellings instead of flagged.
- **Flag rate by letter status** (tlg221, the only work with brackets):

  | letter status | flag rate |
  |---|---|
  | read | 2.8% (144 / 5,192) |
  | partly restored | 6.7% (137 / 2,043) |
  | fully restored | 2.7% (54 / 2,017) |

Words where the editor's supplement meets read letters are still flagged at about two and a half times the
rate of read words. This is where restorations and the digital text are most fragile.

**Correction (2026-11-14).** The first run of the flagger looked up word pairs with 32-bit ids on Windows, so
ids above 255 overflowed and many context scores used the wrong word pairs. Everything here is from corrected
runs.

**My hand-read of the top 30 flags by margin (with the spelling layer, 2026-11-14).** I am not a
papyrologist, and none of these are checked against the editions or images, so all are unverified.

| category | n | examples |
|---|---|---|
| probable slip in the digital text or the restoration | 10 | γίνεεθαι → γίνεσθαι (lunate C read as Ε); μουσκὴν → μουσικήν; ῥῆορικὴν → ῥητορικήν; δύν[αιν] → δύναμιν; παραλεξάμενοι → παραδεξάμενοι (Λ/Δ); παρακείμενο → -ον; μόνο → μόνον; ὅοι → ὅσοι (the scorer's σοι is wrong); (ουσικὴ (a bracket for μ); τ᾿εἰς (a missing space in a corrupt stretch) |
| sound word, rare form or rare spelling (false alarm) | 13 | θεατοῦ (θεατής, next to θεάτρου); παγίων ×2 (πάγιος); προέχειν; ὑπάκουσιν; ὠνίας; ἐπιτηδεύοι; πανόλως; προσαρμοσάσας; ἐξαμάρτοιέν; ὑποθεῖσαι; ξυνθεῖεν (old Attic ξυν-); συγκυκῶντες |
| sound spelling, which the flag now names as a possible spelling | 2 | τυ[πά]νων (τύπανον; ΥΜ written Υ before a consonant); πάλι (final ν) |
| broken stretch | 3 | συμβαίν (before a line number), ἐναντίο νον, ἀρρ |
| word split by a bracket, joined form unattested | 1 | στεφανοπο[ [ϊ]κ[ὴν |
| adscript policy (papyri.py keeps final -αι) | 1 | γυμνασίαι (= -ᾳ) |

Against the hand-read of the same day without the spelling layer, probable slips in the top 30 rose from 5
to 10, and the 13 ποη- spellings, κεινεῖν, two of the line-end splits (ῥυ θμῶν, ἀ ρετήν) and the stray λ left it. The scorer's own
suggestion is right for 8 of the 10 slips. Two slips (γίνεεθαι, παρακείμενο) were hidden before by the
full-stop bug. Of the 13 false alarms, 7 carry the attested-stem note; so do 2 of the 10 slips, so the note
is a hint, not a filter.

**Fixes found on the way.** `papyri.normalize_token` misses final adscript after a breathing (ὧι, ἧι).
`t2b_flag.adscript_left` handles that case. It is worth adding to `papyri.ADSCRIPT` (not edited here).
`stoa0033a`-style group ids also needed a laxer work-id pattern.

### 3. Ancient spellings (`spelling_rules.json`, `spelling_eval.*`, `philodemus_spellings.csv`)

Scribes spelled by ear: ει for ι, ο for ω, ν for γ before κ. A word spelled that way is unattested in a
literary corpus but is not an error. The spelling layer reads it as the word it is, keeps it as written, and
says which spelling it is.

- **Data.** The editors of the Duke Databank of Documentary Papyri and the Digital Corpus of Literary Papyri
  (papyri.info, CC BY 3.0) mark every spelling they regularized (`<choice><reg>ποιητικόν</reg><orig>ποητικόν</orig>`).
  82,831 documents; each is rendered as written and as regularized, and aligned word by word where the two
  have the same number of words (`t2b_spelling_data.py`; `spelling_data.json`). Documents are split train /
  test by a seeded hash, 1 in 10 to test. Train: 87,605 word pairs away from gaps, 3.46M regularized words.
- **Rules.** Each pair is aligned letter by letter; each difference is a rule "reg written orig before a
  vowel / a consonant / at the word end", a dropped or added letter attached to the neighbour it forms a
  diphthong or a double letter with (ΟΙ written Ο before a vowel, not "Ι dropped"). Rate = uses / chances in
  the train documents. Kept: at least 20 uses, rate at least 1 in 10,000, and a sound change of Koine Greek
  (vowels and diphthongs; voicing, aspiration, nasals, liquids and Σ/Ζ within one place of articulation;
  double consonants; final ν; nasal before a consonant; Ξ/ΚΣ). 107 of the 407 candidates were left out as
  grammar (case endings) or abbreviations, 47 as too rare. **253 rules**: 176 vowel, 38 consonant, 16 double
  consonant, 13 final ν, 9 nasal before a consonant, 1 double letter.
- **Channel.** Only a form that is unattested as written is read through a rule (an attested form is read as
  written), one rule per word, at a cost of log(rate). A rule that would change the last three letters is not
  used when the word ends in a common ending (one that attested words with at least 1 in 10,000 of the tokens
  end in): there it would turn an unattested inflection into another case of the word (ἐξηγητικῶς into
  -ικός), not another spelling of it.
- **Accepted as a spelling.** A word the rule explains is not flagged when the rule's rate is at least 1 in
  1,000 and no misreading explains the word better by 4 nats.
- **The writer's habits.** A rule that a text uses at least 3 times, so often that the papyri's own rate
  would give that many by chance with probability under 1 in 1,000 (Poisson), is read as this writer's
  habit: its cost becomes the text's own rate (shrunk toward the papyri's rate by 20 chances), and the text is
  read again. This is the note of a writer's known spellings, made from the text itself. Philodemus:

  | work | habit | uses / chances | here | in the papyri |
  |---|---|---|---|---|
  | tlg221 | ΟΙ written Ο before a vowel (ποητής) | 23 / 192 | 11.0% | 1.24% |
  | tlg370 | Γ written Ν before a consonant (συνχωρεῖν) | 13 / 180 | 6.6% | 1.19% |
  | tlg370 | Μ written Ν before a consonant (ἐνποιεῖν) | 6 / 119 | 4.4% | 0.61% |
  | tlg370 | Κ written Γ before a consonant (ἐγδέχεσθαι) | 4 / 122 | 2.9% | 0.25% |

  Ι written ΕΙ (κεινεῖν, τειμῆς) is the commonest spelling in both works (18 and 29 words) but is no more
  frequent than in the papyri at large (rate 0.75%), so it is not a habit; it is accepted at the papyri's
  rate. With a fixed count of 3 instead of the Poisson test, a rare rule (Ε written Α) became a "habit"
  from 4 doubtful uses and turned Θαλήτου (Thales) into θελητοῦ; the test stops that.

**Held-out papyri** (`spelling_eval.md`; the test documents, not used for the rules):

| test | without the spelling layer | with it |
|---|---|---|
| a misspelled word on its own (written form unattested, editor's form attested; 4,183 pairs): best reading = editor's form | 0.230 | **0.558** |
| same, single-change spellings only (vowel / consonant / double consonant / nasal) | | 0.72 / 0.76 / 0.67 / 0.76 |
| five words as written, run together (600 windows): word breaks (F1) | 0.805 | **0.833** |
| same: misspelled words read as the editor's form (703 words) | 0.102 | **0.243** |

Of 545 scribal slips the editors corrected (`<sic>`/`<corr>`), 89 are unattested as written; the spelling
layer would excuse 11 of them (12%), and several of those are themselves sound spellings the editor chose to
correct (μελλώντων, κιντύνῳ, ἐπειδείξει). Words with two or more spellings (552 of the 4,183) are almost
never recovered (0.7%): one rule per word.

**On the literary test set** (480 held-out lines, the published model): clean top-1 .810 (.812 without),
light .448 (.446), heavy .192 (.185); word breaks .977 / .930 / .868 (.977 / .929 / .866)
(`prune_compare_test_spelling.md`). Before the attested-form gate, clean top-1 on the full counts fell from .817 to .806:
the layer "regularized" attested forms (μόνων into μόνον).

## What is left (roadmap notes for the build session)

- **Gate the channel on HTR letter confidences.** Accept the HTR's per-letter alternatives (top-n
  letters with probabilities) instead of the fixed classes. This is the real input format of the
  Ancient Lives / Kentucky / Anagnostes HTR, and it should also remove most clean-text
  over-correction.
- **Two spellings in one word.** 13% of the held-out misspelled words have two; the layer allows one.
- **Documentary vocabulary.** 2,196 of the 9,775 held-out pairs have a regularized form our literary counts
  do not know (names, measures, formulae). Counts from DDbDP's regularized text would cover them; they are
  CC BY 3.0 and could be added beside First1K.
- **Unattested sound forms.** Most remaining flags (608 of 624) are unattested words; 13 of the hand-read 30
  are sound. A morphological generator (or Dilemma's attestation, once a held-out row exists) would separate
  rare forms from errors better than the attested-stem hint.
- **A truly held-out Dilemma row.** This needs per-work counts from Dilemma, which its
  `form_profile.db` does not expose. Ask upstream, or rebuild the profile without First1K.
- **An expert read of `philodemus_flags.csv`.** A papyrologist should read the flags, with the
  edition and the images.
