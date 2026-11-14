# T2b v1 — transcription plausibility scorer: results (2026-11-13)

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
  - an unknown segment, at 1e-4 and then 1/24 per letter.
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
| tlg221 | 453 | .908 | .964 | **.935** | .658 |
| tlg370 | 1,092 | .934 | .982 | **.958** | .657 |

Precision is lower because a line starts and ends with partial words (hyphenated across lines). The
scorer splits these into pieces.

### 2. Flags on the edited reading

Some words are skipped:
- words touching an unread gap;
- elided words;
- letter strings the editor left unarticulated (no accent, no breathing, not an enclitic).

Every other word gets a check. It is flagged if its key is unattested (count < 2 in 21.6M tokens), or
if a form reachable through the channel scores more than 4 nats better in context. The context score
is P(w | prev) + P(next | w) + channel cost.

- **Scored and flagged.** 18,194 words were scored and 697 flagged (3.8%).
- **By kind.** 670 unattested, 9 better in-channel alternative, 18 both.
- **Flag rate by letter status** (tlg221, the only work with brackets):

  | letter status | flag rate |
  |---|---|
  | read | 3.2% (163 / 5,082) |
  | partly restored | 7.6% (147 / 1,940) |
  | fully restored | 3.1% (61 / 1,968) |

Words where the editor's supplement meets read letters are flagged at about twice the rate of read
words. This is where restorations and the digital text are most fragile.

**Correction (2026-11-14).** The first run of the flagger looked up word pairs with 32-bit ids on Windows, so ids above 255 overflowed and many context scores used the wrong word pairs. The counts above are from the corrected rerun. The hand-read below was made on the first run; it is kept for the record and needs redoing on the corrected flags.

**My hand-read of the top 30 flags by margin (first run).** I am not a papyrologist, and none of these are
checked against the editions or images, so all are unverified:

| category | n | examples |
|---|---|---|
| probable slip in the digital text or the restoration | 4 | δύν[αιν] → ΔΥΝΑΜΙΝ; ῥῆορικὴν → ΡΗΤΟΡΙΚΗΝ; παραλεξάμενοι → ΠΑΡΑΔΕΞΑΜΕΝΟΙ (Λ/Δ); οὐτῇ (αὐτῇ?, the scorer's own suggestion is wrong) |
| genuine Herculanean / variant spelling (rare, so flagged, but not an error) | 8 | ποη- for ποιη- ×6 (ποητικήν, ἐποήθη, ποημάτων); τυπάνων (τύπανον); ὅτις (epic) |
| word split across a line end without a hyphen | 5 | παι γνίων, ὑποκεί μένον, στεφανοπο ϊκήν, ἀηδ ῆ, συμβαίν |
| adscript policy: papyri.py keeps final -αι | 3 | συνηθείαι ×2, γυμνασίαι (= -ᾳ) |
| false alarm (a frequent neighbour wins: movable ν, case form, rare verb) | 10 | παρρησία → -ν, ἀποδέδειχε → -ν, αὐλήσει, ἄδοντα, διήκει, παρεθῇ |

The unarticulated-string rule has a cost. Before it, διαθ[σ]εις → ΔΙΑΘΕΣΕΙΣ was flag no. 11, a
probable slip. The digital text gives that word no accent, so the rule now drops it. Joining split
words across line ends is the next fix: it would remove a sixth of the top 30.

**Fixes found on the way.** `papyri.normalize_token` misses final adscript after a breathing (ὧι, ἧι).
`t2b_flag.adscript_left` handles that case. It is worth adding to `papyri.ADSCRIPT` (not edited here).
`stoa0033a`-style group ids also needed a laxer work-id pattern.

## What is left (roadmap notes for the build session)

- **Gate the channel on HTR letter confidences.** Accept the HTR's per-letter alternatives (top-n
  letters with probabilities) instead of the fixed classes. This is the real input format of the
  Ancient Lives / Kentucky / Anagnostes HTR, and it should also remove most clean-text
  over-correction.
- **Flagger: line ends.** Join a word across a line end when the next line starts mid-word without a
  hyphen (5 of the top 30). Also make the unarticulated-string rule spare words that a supplement
  touches.
- **A documentary test.** Philodemus is literary. The next real case is a documentary papyrus from
  DDbDP / papyri.info (CC BY). It is not downloaded here.
- **A truly held-out Dilemma row.** This needs per-work counts from Dilemma, which its
  `form_profile.db` does not expose. Ask upstream, or rebuild the profile without First1K.
- **An expert read of `philodemus_flags.csv`.** A papyrologist should read the flags, with the
  edition and the images.
