# T2b — transcription plausibility scorer (v1 2026-11-13; spelling layer 2026-11-14)

An "ancient Greek autocorrect" for HTR output of papyri. It splits a scriptio-continua string
(uppercase, no accents, no spaces) into attested word forms and returns the k best readings, scored by
attestation frequency plus bigram collocation, through a small declared HTR confusion channel. No
training. Results and the full write-up: [`outputs/t2b/README.md`](../outputs/t2b/README.md).

| file | what |
|---|---|
| `t2b_scorer.py` | library + CLI: counts, lexicon with the channel, k-best beam segmenter, greedy baseline |
| `t2b_eval.py` | held-out split, noisy test lines, metrics (boundary F1, word recovery, line top-1/top-5) |
| `t2b_flag.py` | real case: flags low-plausibility readings in Philodemus (First1K tlg1595), word-division check |
| `t2b_spelling_data.py` | papyri.info (DDbDP + DCLP, CC BY 3.0): each document rendered as written and as regularized, aligned word by word; seeded train/test split |
| `t2b_spelling.py` | spelling rules learned from those pairs (`outputs/t2b/spelling_rules.json`), the channel side, the writer's habits, whole-text reading; `export-rust` writes `t2b-wasm/src/spelling_table.rs` |
| `t2b_spelling_eval.py` | the rules on the held-out papyri: words, scribal slips, lines |
| `../tests/test_t2b_scorer.py`, `../tests/test_t2b_spelling.py` | tests on toy corpora |

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
python -I -X utf8 pipeline/t2b_flag.py                  # with the spelling layer; --no-spelling for v1
# spelling layer: papyri.info clone (sparse, DDbDP + DCLP, about 1.3 GB) in data/external/ (gitignored)
git clone --depth 1 --filter=blob:none --sparse https://github.com/papyri/idp.data.git data/external/idp.data
git -C data/external/idp.data sparse-checkout set DDbDP DCLP
python -I -X utf8 pipeline/t2b_spelling_data.py          # data/t2b_cache/spelling_*.jsonl, outputs/t2b/spelling_data.json
python -I -X utf8 pipeline/t2b_spelling.py learn         # outputs/t2b/spelling_rules.json
python -I -X utf8 pipeline/t2b_spelling.py export-rust   # t2b-wasm/src/spelling_table.rs
python -I -X utf8 pipeline/t2b_spelling_eval.py          # outputs/t2b/spelling_eval.{json,md}
python -I -X utf8 pipeline/t2b_eval.py run --split test --systems bigram,bigram_spelling --tag spelling
python -I -X utf8 -m pytest -q tests/test_t2b_scorer.py tests/test_t2b_spelling.py
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
