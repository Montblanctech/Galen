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
| validation | morpheus (Morpheus analyses contain the headword) or quoted (equals LSJ's quoted form; used when Morpheus had no analysis) |
| quoted_form | the form LSJ quotes near the citation, if any |
| lsj_part, entry_key | provenance in the Perseus LSJ XML |
| status | located |

Scoring: a system matches when its lemma at token_index equals headword after accent/case normalisation (blind); strict = exact; article-neutral maps the article's forms to ὁ first.
