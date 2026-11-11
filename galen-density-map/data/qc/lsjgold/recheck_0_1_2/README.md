# LSJ-Gold 0.1.2 re-check: the 652 weak loci of 0.1.1, read blind (2026-11-11)

**What was checked.** The 651 LSJ-Gold 0.1.1 loci that rest only on the single word LSJ quotes, where that
(form, headword) pair is one the lexicon 0.1.2 set aside because Dilemma gives the form another lemma, plus the one
locus of πόλεων under πολύς found wrong earlier. A sample read had found about one such pair in seven wrong: LSJ
quotes a related or cross-referenced word in an entry, and that word passed as the headword's own form.

**Protocol** (`protocol.json`, `reader_instructions.txt`, `pipeline/lsjgold/recheck_0_1_2.py`; committed before
any answer was read). Four sheets of 163 weak loci each, with 10 anchors and 10 near-miss plants per sheet at unmarked
positions. Two readers per sheet, each in its own session with only the sheet and the instructions: reader A Claude
Opus, reader B Claude Sonnet. Gate per sheet and reader: 9 of 10 anchors yes and 8 of 10 plants no. A failing reader
is replaced once by a fresh reader of the same model; a sheet that still fails has all its loci dropped. A locus is
kept only if both readers answer yes.

**Results** (`summary.json`, `decisions.csv`, answers in `answers_<sheet>_<reader>.csv`, key published after
scoring in `key_PUBLISHED_AFTER_SCORING.csv`).
- Plants: every reader rejected all 10 on every sheet (80 of 80, and 20 of 20 for the replacement readers).
- Anchors: sheets 1, 2 and 4 passed (9, 9, 10, 10, 10, 10 of 10). On sheet 3 both readers accepted 8 of 10; the
  replacement Sonnet reader accepted 9, the replacement Opus reader again 8. So sheet 3 failed and, as the protocol
  says, all 163 of its loci are dropped, including the 117 that both its first readers accepted. The two anchors
  every sheet-3 reader rejected are τῷ in Sophocles, *Antigone* 401 (*τῷ τρόπῳ*, "in what way": the interrogative
  τίς, which the accent-blind key merges with the indefinite τις) and ὅπουπερ under ὅπου (LSJ files -περ forms under
  the simple word; the instructions did not say so). Both are LSJ's own filing, so the controls, not the readers, are
  the weak point; a later version can re-read sheet 3 with those two conventions stated.
- Decisions: **339 loci kept, 313 dropped** (150 on the three passing sheets, 163 on sheet 3). Answer pairs on the
  final readers: yes/yes 456, no/no 126, a split or an unsure 70.

**Sample read by the build session** (seed 20261112; a language model, not a Greek specialist).
- 50 kept loci: **50 right.** Iteratives (ζώεσκον, κοχύδεσκεν), dialect forms (χᾶνας, ἴσαις, ἐρᾶσαι), adverbs filed
  under their adjectives as LSJ does (ὑπερφιάλως, χλιηρῶς). One is right by LSJ's filing more than by grammar
  (Δωδώναθεν under Δωδώνη).
- 50 dropped loci from the passing sheets: **about 29 wrong golds** (the right drops: Πατρέες under πάτραι,
  θυμιήματα under θυμιάω, σπονδήν under σπένδω, τραπείομεν, from τέρπω, under τρέπω, Τέρτυλλος under τέρτα),
  **about 13 right golds lost** to a split or unsure answer (ἔγρετο under ἔγρω, μεμαὼς under μέμονα, ἔρυτο under
  ἐρύω), and 8 unclear.
- So dropped loci are mostly real errors and the kept ones are clean in this sample. Dropping costs some right loci;
  it is the conservative choice for a gold standard. Every dropped locus is in `lsj_gold_0_1_2_dropped.csv` with both
  readers' answers, so a later version can bring right ones back.
