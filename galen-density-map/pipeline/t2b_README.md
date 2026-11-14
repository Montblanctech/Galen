# T2b — transcription plausibility scorer (v1, 2026-11-13)

An "ancient Greek autocorrect" for HTR output of papyri. It splits a scriptio-continua string
(uppercase, no accents, no spaces) into attested word forms and returns the k best readings, scored by
attestation frequency plus bigram collocation, through a small declared HTR confusion channel. No
training. Results and the full write-up: [`outputs/t2b/README.md`](../outputs/t2b/README.md).

| file | what |
|---|---|
| `t2b_scorer.py` | library + CLI: counts, lexicon with the channel, k-best beam segmenter, greedy baseline |
| `t2b_eval.py` | held-out split, noisy test lines, metrics (boundary F1, word recovery, line top-1/top-5) |
| `t2b_flag.py` | real case: flags low-plausibility readings in Philodemus (First1K tlg1595), word-division check |
| `../tests/test_t2b_scorer.py` | 12 tests on a toy corpus |

## Run (Greek venv, from `galen-density-map/`)

The corpus is read from `data/` (or `--data-root`, or `GALEN_DATA`); the counts cache is written to this
checkout's `data/t2b_cache/` (gitignored, ~95 MB, rebuilt in about a minute).

```bash
python -I -X utf8 pipeline/t2b_eval.py holdout          # outputs/t2b/holdout_works.json (seeded)
python -I -X utf8 pipeline/t2b_scorer.py build --holdout outputs/t2b/holdout_works.json
python -I -X utf8 pipeline/t2b_scorer.py segment ΚΑΙΤΟΝΑΟΓΟΝΕΙΝΑΙΑΛΗΘΗ -k 3
python -I -X utf8 pipeline/t2b_eval.py lines --split test --per-work 40
python -I -X utf8 pipeline/t2b_eval.py run --split test
python -I -X utf8 pipeline/t2b_eval.py run --split test --systems dilemma_bigram --tag dilemma
python -I -X utf8 pipeline/t2b_flag.py
python -I -X utf8 -m pytest -q tests/test_t2b_scorer.py
```

`segment` example output (the HTR read Λ as Α):

```
ΚΑΙΤΟΝΑΟΓΟΝΕΙΝΑΙΑΛΗΘΗ
  1.   -26.58  ΚΑΙ ΤΟΝ ΛΟΓΟΝ ΕΙΝΑΙ ΑΛΗΘΗ   (ΑΟΓΟΝ->ΛΟΓΟΝ [sub1])
  2.   -33.11  ΚΑΙ ΤΟΝ ΛΟ ΓΟΝ ΕΙΝΑΙ ΑΛΗΘΗ   (ΑΟ->ΛΟ [sub1])
  3.   -33.47  ΚΑΙ ΤΟΝ ΑΟΓΟΝ ΕΙΝΑΙ ΑΛΗΘΗ
```

`--json` gives each reading with its edits (span, observed letters, proposed form, edit tag).

## Memory

The counts are built in two passes with disk-partitioned bigram merging, because the lab machine had under
1 GB of free commit while other sessions ran. Peak use is a few hundred MB.
