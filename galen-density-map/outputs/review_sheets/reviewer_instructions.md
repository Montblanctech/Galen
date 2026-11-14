# Reviewer instructions: Galen First Drafts review sheets

**What you are looking at.** Thirteen works of Galen were translated by two language models, passage by passage,
with no human correction. For each work, about ten passages were chosen by a fixed rule (some where the two
renderings differ most, some that automated checks flagged, some at random; the sheet does not say which). Each
sheet shows one passage: the Greek of Kühn's edition with his page numbers in brackets, two renderings labelled
**1** and **2**, and a table of the words the pipeline singled out (rare or thinly covered in LSJ), each with the LSJ
headword it was matched to, the first sense of that entry, and how each rendering translated it. The labels 1 and 2
are shuffled from passage to passage; they are not the A and B of the published pages.

**What we ask.** Read the Greek and the two renderings, then answer four questions. Your judgement is the measure;
there is no answer key.

1. **Which rendering is better?** `1`, `2` or `neither` (no real difference, or equally good or bad).
2. **A term wrong?** `none`, `1`, `2` or `both`: a word is rendered with a meaning it cannot have in this passage.
   Write the word(s) in the note (the Greek, the English, or both).
3. **Sense wrong?** `none`, `1`, `2` or `both`: the rendering says something the Greek does not, beyond single words
   (construction, negation, who is speaking or criticised, the step of the argument). Say where in the note.
4. **Comment** (optional): anything else, such as a better rendering, a textual problem in Kühn, or a word the table
   should have included.

**How long.** About three to five minutes a passage (an estimate; nobody has timed it yet). In 30 minutes that is
roughly six to ten passages. Work through the sheets **in order** and stop when your time is up: the order is
arranged so that the first few passages already mix the three kinds. Leave a passage blank if you did not read it;
a blank is not counted. Answer only the questions you are sure of; a partial answer is still used.

**Things to keep in mind.**
- The LSJ first sense is where the entry begins, not the sense Galen needs; a rendering that departs from it may be
  right. The matched headword can itself be wrong (the pipeline's lemmatizer chose it).
- Words in square brackets in a rendering were supplied by the model; words in parentheses repeat the Greek.
- Only Kühn's text was used; if a rendering goes wrong because the text is corrupt, say so in the comment rather
  than marking the rendering wrong.
- Please do not look up the published page for a passage before answering; the sheets are meant to be read cold.

**Returning the sheets.** Either print the work's HTML page (one passage per sheet), tick and write by hand, and
send a scan or photo; or open the work's CSV in a spreadsheet and fill the columns `reviewer`, `better`,
`term_wrong`, `term_note`, `sense_wrong`, `sense_note`, `comment` (values as above; leave the other columns as
they are). Your name or initials in `reviewer` is enough; say if you would rather not be named in anything that
reports the results.

**How the answers are used.** They are counted per work: how often each rendering was preferred, and in how many
passages a term or the sense was marked wrong, separately for flagged and unflagged passages. That tells us whether
the automated flags point where a reader finds problems, and gives a first, rough error rate per work. No answer is
published as a correction without the reviewer's agreement.
