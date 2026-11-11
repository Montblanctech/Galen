# Galen First Drafts: a sample read against the Greek (2026-11-11)

Until this date the drafts and the findings catalogue had been checked only by machine: back-translation, agreement between the two renderings, a dictionary judge, and a script that confirms every quotation and Greek word. This file records the first reading of random samples against the Greek, and what was changed because of it. **The readers were language models working from the Greek, not scholars.** A specialist's reading is still to come.

## 1. The drafts (rendering A, the one shown on the pages)

39 passages, 3 from each of the 13 works, drawn at random (seed 20261111). Each was read sentence by sentence against Kühn's Greek and judged OK, MINOR (a local slip that would not mislead much) or SERIOUS (meaning wrong, omission, addition, wrong number, garbled English).

- **OK 35, MINOR 4, SERIOUS 0.**
- The four slips, all in the two Hippocratic commentaries:
  - *Acute Diseases* K. XV 838–839: μέχρις ἂν ἐπανιῶσιν … is rendered "until they come back up", which after "gruels" reads as vomiting; it means "until they recover / remit" (B has "until they remit").
  - *Acute Diseases* K. XV 552–553: ἀριστᾷν "take the morning meal"; in Hippocratic usage the ἄριστον is the midday meal.
  - *Regimen in Health* K. XV 218–219: τῇ δὲ ἄλλῃ ταλαιπωρίῃ ἀναγκάζειν χρὴ αὐτῶν τὰ σώματα "with the rest of the exertion one must force their bodies"; it means "in other respects one must force their bodies with exertion".
  - *Regimen in Health* K. XV 176–177: περιστατικῷ βίῳ "the 'circumstantial' life"; it means a busy life, a life of affairs (B has this).
- No refusals, placeholders or repeated text. The models sometimes give a Greek word in parentheses or remark on a doubtful reading, although their instructions said not to add notes: across all 1,682 passages, rendering A gives Greek in parentheses in 337 and such a remark in 68. The pages now say that these remarks are the model's.
- One broken page marker: the Greek of *Regimen in Health* K. XV 178 has "[None]" where the TEI gives no page number; the pages no longer show it.
- **The check marks did not predict the slips.** The three sampled passages marked as failing read well, and all four slips had passed. The marks come from automated agreement tests, not a reading of the Greek; the pages now say so, and that an unmarked passage has not been checked by a person either.

## 2. The findings catalogue

40 items drawn at random (seed 1111), each read against its passage in Greek and English.

- Every quotation is word for word in the draft and every Greek word is in its passage (40 of 40).
- Title and summary against the Greek: **38 right, 1 wrong, 1 uncertain.**
  - Wrong: "Hernia surgeons apply the plaster right after operating" said the surgeons apply it "without even moistening the wound first, to prevent inflammation"; the Greek says they carry on the treatment with affusions and poultices alongside it (both drafts translate this correctly; the summary added it). **Corrected.**
  - Uncertain: "'Scraped verdigris 16 minae' implausible": μνᾶς ιστ΄ can be read as "a sixteenth of a mina", as the next ingredient is written out, in which case the draft, not the Greek, is wrong. **Summary and note corrected to say so.**
- Category: Plato's *Philebus* (extant) was filed under lost works. **Moved to claims.**
- Attestation notes that contradicted their own evidence:
  - "Galen's overnight refutation book" called the book an otherwise unattested pamphlet; its evidence says the address continues in the extant text, so it is probably part of *On the Power of Purgative Drugs*. **Corrected.**
  - "Lost works on Hippocratic anatomy and on Thucydides' plague" was labelled as known only from this passage, but the work on anatomy is in Galen's own list of his books (Fichtner 243). **Label removed; note corrected.** The one remaining item so labelled, *On the Innate Heat*, now reads "apparently known only from this passage (our check)".
- Outside the sample: the front-page item on Galen's shoulder said he "tore away his own acromion (acromioclavicular separation)". The passage speaks of the collarbone and gives no modern diagnosis. **Corrected** to what the Greek says.
- Items whose passage failed the checks showed "confidence high"; the confidence is the model reader's, and the page now says so.

Every corrected item is marked on the page. The corrections are in `galen-density-map/pipeline/firstdrafts/findings_page.py` (`CORRECTIONS`); the underlying `findings.jsonl` is unchanged.

## 3. The front page

- "From the project's list of 1,433 words … checked by hand" was false: the list was sorted by machine (the lemmatizer Dilemma and two model readers). **Corrected.** "Real words with no entry at all" now reads "words with no entry in the digital LSJ" (the printed LSJ or its Supplement may have them).
- "Thirteen books, in Galen's own voice": *On Leeches* is treated as pseudo-Galenic by its Italian translator (Ecca 2021). The heading now reads "works from the Galenic corpus", and the work's card and page say so.
- "Two different language models … no help": now says both models are Anthropic's and what they were given (the neighbouring passages for context, no dictionary or glossary).
- The thirteen quotations on the cards are word for word from passages that passed the checks (13 of 13, checked by script).

## 4. Other records corrected the same day

- The four cycle-4 work READMEs said the renderings ran in direct mode; every row records the batch backend. Corrected.
- LS-Gold (the Latin benchmark) has the weakness that LSJ-Gold 0.1 had, on a small scale: 480 of its 161,032 loci are validated only by a word of the quotation Lewis & Short gives (438 of them by one word of a phrase), and in 30 of those read one was wrong (*digna* under *divus*). That is of the order of 15 loci (0.01%). Stated in `galen-density-map/data/qc/lsgold/README.md`; the next version will check them one by one.
