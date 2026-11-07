# LSJ-Gold submissions

Score your Ancient Greek lemmatizer on the dictionary-cited stratum and get a row on the [leaderboard](../docs/lsj-gold/).

## What to submit

One folder per system, one JSONL file per covered edition, named by the edition's stem:

```
submissions/<your-system>/urn_cts_greekLit_tlg0012.tlg001.perseus-grc2.jsonl
submissions/<your-system>/urn_cts_greekLit_tlg0627.tlg001.1st1K-grc1.jsonl
...
```

Each line is one token of that edition in order: `{"i": <token index>, "surface": "<form>", "lemma": "<your lemma>"}`. The token
index `i` is the line number of the token in the project's token stream for that edition (`galen-density-map/data/perseus_corpus/lemmatized/<stem>.jsonl`,
regenerable with `pipeline/lsjgold/perseus_tokens.py`; First1K editions: `data/lemmatized/reference/<stem>.jsonl` from stage 03).
The scorer checks the surface at every gold index and counts a row whose surface does not match as missing, never as right or wrong.

The gold file (`release/lsj-gold-0.1/lsj_gold.csv`, also inside the pip package) lists every covered edition in its `author`, `work` and
`cited_edition` columns. You need not cover every edition: uncovered loci are reported as missing, and the per-author columns show where you stand.

## How it is scored

Open a pull request adding the folder. The workflow `.github/workflows/lsjgold-submission.yml` runs

```
pip install ./audit-kit
greek-lemma-audit lsjgold --system-cache submissions --out scores.json
```

and writes the table (accent-blind match, strict match, article-neutral match, per author, with N and Wilson 95% intervals) to the job
summary. The same command runs locally. The maintainers then add the row to `docs/lsj-gold/` under the next version string; a number
never changes inside a version.

Please name the model, version and date in your folder's `README.md`, and say whether lemmas were produced with or without context.
Data CC BY 4.0, code MIT. Cite: Pepperman, W. (2026), LSJ-Gold, Galen Density Project, doi:10.5281/zenodo.21561962.
