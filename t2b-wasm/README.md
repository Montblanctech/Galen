# t2b-wasm: the T2b scorer in the browser

A Rust port of the T2b transcription plausibility scorer, the "ancient Greek autocorrect" for papyrus HTR
output (`galen-density-map/pipeline/t2b_scorer.py`, flags from `t2b_flag.py`; results in
`galen-density-map/outputs/t2b/README.md`). It compiles to a 163 KB WebAssembly module with no dependencies
and runs on a 6.6 MB pruned copy of the counts. The page is `docs/tools/autocorrect/`.

What it does is unchanged from the Python scorer:

- It segments a scriptio-continua line into the k best readings over attested forms.
- It reads through a small HTR channel: the letter classes Α/Λ/Δ, Ε/Θ/Ο/Σ, Η/Ν and Ι/Τ, and at most one lost
  letter per word.
- It scores with an interpolated absolute-discounting bigram LM (d = 0.75) and a per-letter penalty for
  unknown segments.
- It flags low-plausibility words the way `t2b_flag.py` does.

The constants, the candidate order, the beam (48, at most 4 per last word, top 8 candidates) and the stable
sorts are the same.

## Build

```sh
export PATH=~/.cargo/bin:$PATH        # stable Rust, edition 2024, target wasm32-unknown-unknown
cd t2b-wasm
cargo test --release                  # unit tests (the real-model tests need docs/tools/autocorrect/model.bin)
cargo build --release                 # native CLI: target/release/t2b-cli
cargo build --release --target wasm32-unknown-unknown --lib
cp target/wasm32-unknown-unknown/release/t2b.wasm ../docs/tools/autocorrect/t2b.wasm
```

The model is rebuilt from the counts cache (`galen-density-map/data/t2b_cache/counts.npz`, gitignored):

```sh
python -I -X utf8 galen-density-map/pipeline/t2b_export_model.py sweep --thresholds 1,2,3,4,5,8   # dev split
python -I -X utf8 galen-density-map/pipeline/t2b_export_model.py export --bigram-min 2
python -I -X utf8 galen-density-map/pipeline/t2b_export_model.py compare --split test
```

Checks, run from the repository root with the Galen venv's Python:

```sh
python -I -X utf8 t2b-wasm/tools/parity.py           # Rust vs Python on the pruned model, dev + test
python -I -X utf8 t2b-wasm/tools/wasm_vs_native.py   # the shipped .wasm (Node + glue.js) vs the native CLI
python -I -X utf8 t2b-wasm/tools/page_check.py       # the page in headless Chromium, from a local http.server
python -I -X utf8 t2b-wasm/tools/gen_continua.py     # regenerates src/continua_table.rs (to_continua table)
```

The page needs no build step. Its four files (`index.html`, `glue.js`, `t2b.wasm`, `model.bin`) and an
offline service worker (`sw.js`, cache-first; bump `VERSION` when a file changes) are served as they are.

## Layout

| file | role |
|---|---|
| `src/model.rs` | model.bin reader: front-coded keys, varints, CRC-32, id order, bigram rows |
| `src/scorer.rs` | Lexicon candidates, LM, beam segmenter, flags |
| `src/letters.rs` | alphabet, confusion classes, constants, `to_continua` |
| `src/continua_table.rs` | generated: the 313 code points `to_continua` keeps, and their letters |
| `src/math.rs` | `ln` / `exp` (fdlibm algorithms) |
| `src/lib.rs` | JSON output and the C ABI for wasm: `t2b_alloc`, `t2b_free`, `t2b_init`, `t2b_segment`, `t2b_out_ptr`, `t2b_out_len` |
| `src/bin/t2b-cli.rs` | native CLI: one input per stdin line, one JSON object per output line |
| `tests/scorer.rs` | native tests |
| `MODEL_FORMAT.md` | the model.bin spec |

The JSON for one line is `{"input", "readings": [...]}`. Each reading has `score`, `text`, `segments` and
`flags`.

- A segment has `start`, `end`, `observed`, `form` (null if unknown), `edit` (the reference's tag: `sub1`,
  `lost:Ν@3+sub1`, `unknown`), `corrected`, `unknown`, `count`, `lm`, `chan`, `score` and `changes` (letter
  by letter: `{"at", "from", "to"}` or `{"at", "lost"}`).
- A flag has `segment`, `observed`, `kind` (`unattested`, `alternative`, `unattested+alt`), `count`,
  `alternative`, `alt_edit`, `alt_count`, `margin` (nats) and `alt_changes`.

Flags are computed on the observed words of each reading's segmentation: `t2b_flag.flag_words` with no
fragments and no elision, margin 4 nats, top 12 candidates.

## The model and the cost of pruning

`counts.npz` is 95 MB: 313,797 forms and 6,264,923 bigram types. `model.bin` keeps every form the scorer can
propose (count >= 2, length <= 24; 313,788) and the bigrams with count >= 2 (1,779,469). Each form keeps its
full ctx and n1, so a pruned pair backs off exactly like an unseen one. The keys are front-coded and the counts
varints; the format is in [`MODEL_FORMAT.md`](MODEL_FORMAT.md).

**The threshold was chosen on the dev split only.** The rule was fixed before the sweep was run
(`t2b_export_model.pick`): among models of 8 MB or less, the largest threshold whose dev metrics stay within
0.005 boundary F1 and 0.010 line top-1 and top-5 of the full counts on every level. If none qualifies, the
smallest threshold that fits. None qualified, so the threshold is 2 (`outputs/t2b/prune_sweep_dev.md`).

Dev, 150 lines (bigram >= 1 renumbers the ids and drops nothing; it reproduces the full counts exactly):

| model | size | level | boundary F1 | line top-1 | line top-5 |
|---|---|---|---|---|---|
| full counts.npz | 95 MB | clean / light / heavy | .972 / .931 / .868 | .713 / .407 / .207 | .787 / .507 / .247 |
| bigram >= 1 | 17.1 MB | clean / light / heavy | .972 / .931 / .868 | .713 / .407 / .207 | .787 / .507 / .247 |
| **bigram >= 2** | **6.6 MB** | clean / light / heavy | .969 / .929 / .869 | .700 / .393 / .200 | .767 / .480 / .247 |
| bigram >= 3 | 4.5 MB | clean / light / heavy | .968 / .927 / .866 | .693 / .393 / .200 | .767 / .473 / .240 |
| bigram >= 5 | 3.5 MB | clean / light / heavy | .967 / .930 / .864 | .693 / .387 / .187 | .767 / .487 / .240 |
| bigram >= 8 | 3.1 MB | clean / light / heavy | .965 / .930 / .869 | .680 / .367 / .180 | .773 / .500 / .240 |

**Test, 480 lines, measured once with the chosen model** (`outputs/t2b/prune_compare_test.md`; the full row
reproduces `eval_test.md`):

| model | level | boundary F1 | word rec. | line top-1 | line top-5 | rec. top-1 | rec. top-5 |
|---|---|---|---|---|---|---|---|
| full counts.npz | clean | .977 | .958 | .817 | .881 | .817 | .881 |
| full counts.npz | light | .930 | .863 | .458 | .521 | .746 | .844 |
| full counts.npz | heavy | .868 | .731 | .190 | .260 | .603 | .828 |
| model.bin | clean | .977 | .958 | .812 | .877 | .812 | .877 |
| model.bin | light | .929 | .860 | .446 | .521 | .725 | .844 |
| model.bin | heavy | .866 | .727 | .185 | .260 | .589 | .828 |

Pruning costs at most .002 boundary F1 and .012 line top-1 over all lines; on the lines the channel can undo
by design, top-1 drops .021 (light) and .014 (heavy), while top-5 is unchanged. Most of the cost is the 4.4
million pairs seen once, which a count threshold cannot keep under the size target: with them the model is
17 MB.

## Parity

`tools/parity.py` runs the native CLI and the Python reference (`t2b_scorer.Segmenter` on
`t2b_export_model.read_model(model.bin)`), both on the pruned model. It covers every dev and test line at
every noise level, plus each clean line re-spaced and lower-cased (`ουν ειωθεν η φυσις`, final ς included) to
exercise `to_continua`: 2,520 inputs, k = 5. Results are in `outputs/t2b/wasm_parity.{md,json}`.

| inputs | level | top-1 identical | top-1 tie only | top-5 identical | top-5 up to ties | segment terms | flags identical | normalised input |
|---|---|---|---|---|---|---|---|---|
| 630 | clean | 630 | 0 | 628 | 630 | 630 | 630 | 630 |
| 630 | light | 630 | 0 | 628 | 630 | 630 | 630 | 630 |
| 630 | heavy | 629 | 1 | 625 | 630 | 629 | 629 | 630 |
| 630 | spaced, lower case | 630 | 0 | 628 | 630 | 630 | 630 | 630 |
| **2,520** | **all** | **2,519** | **1** | **2,509** | **2,520** | **2,519** | **2,519** | **2,520** |

- **Top-1 reading: 2,520 of 2,520 identical words and scores.** In 2,519 the segments, spans, edit tags
  and score (within 1e-9) are identical. The per-segment LM and channel terms and the flags (kind,
  alternative, edit, margin) are identical in those 2,519 too.
- **The one difference is a tied segmentation of the same reading** (test, `tlg2042.tlg019:12`, heavy).
  Both give ΦΡΟΝΗΣΙΝ ΕΙΤ ΕΠΙΓΙΝΕΣΘΑΙ ΚΑΤΗΓΟΡΗΜΑ ΑΠΟ ΦΡΟΝΗΣΕΩΣ with score -95.21946470279875. Python
  restores the lost Α at the start of ΑΠΟ; Rust restores it at the end of ΚΑΤΗΓΟΡΗΜΑ. The two paths add the
  same terms in a different order, so their scores differ only in the last bits.
- **Why ties cannot follow Python exactly.** Python picks among tied hypotheses with `np.argpartition`,
  whose order for equal values is unspecified and, in numpy 2, CPU-dependent. Rust breaks ties by a stable
  order. Its `ln`/`exp` (fdlibm) can also differ from numpy's by one ulp.
- **Top-5: identical in 2,509; the other 11 differ only where scores tie.** These are another segmentation
  of the same words, two readings with the same score in swapped order, or a tied reading cut off at rank 5;
  the harness fetches a 6th reading to check that.
- **wasm = native, byte for byte.** `tools/wasm_vs_native.py` runs the shipped `t2b.wasm` under Node through
  the page's own `glue.js`. On the same 2,520 inputs its JSON is identical to the native CLI's
  (`outputs/t2b/wasm_vs_native.json`), because the crate computes `ln` and `exp` itself rather than calling
  the platform library.
- **The page.** `tools/page_check.py` serves `docs/` with `http.server` and opens the page in headless
  Chromium with two lines in `?text=`. It waits over the DevTools protocol until the page reports it has run,
  and asserts that the page's JSON equals the native CLI's: it does.

The flag comparison uses `t2b_flag.flag_words` itself, with ids cast to int64; see the reference notes
below.

## Sizes and speed

| item | bytes | gzipped (level 6) |
|---|---|---|
| `t2b.wasm` | 163,053 | 58,029 |
| `model.bin` | 6,641,911 | 3,454,761 |
| `glue.js` | 3,253 | 1,300 |
| `index.html` | ~19,300 | ~7,100 |

Speed per line (lines of 20 to 40 letters, k = 5, flags included):

| where | load (decode model) | mean | median | p95 |
|---|---|---|---|---|
| native CLI, desktop (x86-64) | 112 ms | 10.7 ms | 10.6 ms | 16.2 ms |
| `t2b.wasm` in Node 22 (V8), same desktop | 160 ms | 24.1 ms | 24.0 ms | 37.0 ms |
| the page in headless Chromium, same desktop | 170-210 ms | 40 ms for a 37-letter line, 7 ms for a 13-letter one | | |
| the page in the desktop app's browser pane | | 41-43 ms for the 37-letter line, 28 ms for a 33-letter one | | |

**Not measured on a phone.** A phone CPU is typically 2 to 4 times slower than this desktop, which suggests
about 0.1 s per line plus a model decode of under a second. That is an estimate, not a measurement. The
first visit downloads about 3.5 MB (gzipped); after that, the service worker serves everything from the cache
and the page works offline.

## Notes for the reference

- **int32 overflow in `t2b_flag.flag_words` (and `Segmenter.score_words`) on Windows.** Both call
  `seg.lm_grid(np.array([prev]), np.array([wid]))` without a dtype. With numpy 1.26 on Windows that array is
  int32, so `prev << 23` overflows for every id >= 256 and the bigram lookup reads the wrong key.
  `Segmenter.segment` is not affected: it passes int64 arrays. **The published Philodemus flags
  (`outputs/t2b/philodemus_flags.*`) were computed this way.** Recomputing the margins of the first 60 rows
  of `philodemus_flags.csv` from their context: all 60 match the int32 lookup to the second decimal, and 2
  match the int64 one. With int64, many margins shrink or change sign. ΠΑΡΡΗΣΙΑ goes from 11.77 to -6.63,
  ΓΝΙΩΝ from 14.34 to 0.87, ΠΑΡΑΛΕΞΑΜΕΝΟΙ from 10.60 to 1.06, so the "alternative" flags and the hand-read
  top 30 in `outputs/t2b/README.md` need a rerun. This sprint does not rerun them or change the reference.
  The fix is `dtype=np.int64` in both calls. The port and the parity harness use the intended int64 behaviour.
- **Cache key in `Lexicon.candidates`.** The cache is keyed by the observed string only, so a `top=12` call
  from `flag_words` can get a list cached by the segmenter with `top=8`. The port always uses 12 for flags;
  the harness gives `flag_words` a fresh Lexicon.
- **U+03A2.** `to_continua` keeps this unassigned code point, which lies inside its Α-Ω range. The port keeps
  it too, as letter code 24, which no form contains.
