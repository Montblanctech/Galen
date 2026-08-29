# Human spot-check protocol (public summary)

The planned human evaluation of lemmatizer accuracy uses a salted-control design. This
note describes the design; the control items themselves are withheld until the
evaluation is complete, because publishing them would let an annotator identify the
planted rows and defeat the check.

- **Sample.** A frozen random 60-token sample from the medical subcorpus (reservoir
  sampling, seed 20260725, documented in the pipeline). The accuracy rate is computed
  on these 60 tokens **only**.
- **Salting.** A small set of known-answer control rows — documented lemmatizer errors
  and verified-correct lemmatizations drawn from real corpus tokens — is shuffled
  invisibly into the reviewer sheet. Reviewers are told controls exist, not which rows
  they are. Controls never enter the accuracy rate; they only gate whether a reviewer's
  answers are usable (catching mark-everything-correct and mark-everything-wrong
  annotation).
- **Two readers.** The selected design is two independent readers on the identical
  sheet, reporting the rate plus inter-annotator agreement (Cohen's κ) — directly
  addressing the single-evaluator limitation noted in the MT study this work builds on.
- **Targeting.** The cross-system disagreement set (`m2_disagreements.csv`) supplements
  the frozen sample as a priority queue, concentrating human attention where the
  machine measurements cannot settle the answer.
- **Machine verdicts as sidecar.** Machine verdicts on the frozen 60
  are recorded separately and never shown to reviewers before annotation.

Full protocol, control set, and answer key will be published with the human-evaluation
results.
