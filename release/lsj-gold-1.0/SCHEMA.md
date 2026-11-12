# lsj_gold.csv schema

| column | meaning |
|---|---|
| headword | LSJ headword (Unicode, from the entry key) |
| headword_key | accent/case-blind Beta Code key used for matching |
| author, work | TLG ids of the cited work |
| cited_edition | the edition the LSJ URN names (Perseus) |
| locator | CTS passage locator in the citation |
| unit | the unit found in our First1K edition (line number or div path) |
| token_index | 0-based index into the project's token JSONL for that edition (urn_cts_greekLit_<author>.<work>.<edition>.jsonl) |
| surface | the token |
| validation | morpheus (Morpheus analyses contain the headword) or quoted (LSJ quotes this single word beside the citation, compared on letters only, never a prefix ending in "-"; used when Morpheus had no analysis) |
| quoted_form | the form LSJ quotes near the citation, if any |
| lsj_part, entry_key | provenance in the Perseus LSJ XML |
| status | located |

Scoring: a system matches when its lemma at token_index equals headword after accent/case normalisation (blind); strict = exact; article-neutral maps the article's forms to ὁ first.

`lsj_gold_1_0_dropped.csv` and `lsj_gold_0_1_2_duplicates.csv` have the same columns; the dropped file adds `why` (how the locus was decided) and `readers_headword` (the headword a reader gave instead). `ledger.csv`: `locus` (author.work:token_index:headword_key), `pool`, `headword`, `surface`, `author`, `work`, `token_index`, `status` (keep or drop), `verdicts` (JSON: every round's answers, A = Opus, B = Sonnet, C = the third reader), `note`.
