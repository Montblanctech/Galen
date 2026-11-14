# model.bin, format T2BM version 1

The compact counts the in-browser scorer reads. Writer: `galen-density-map/pipeline/t2b_export_model.py`
(`encode`). Readers: the same file (`decode`, for the Python scorer) and `t2b-wasm/src/model.rs`.

## Layout

All integers are little-endian. A *varint* is unsigned LEB128: 7 bits per byte, low bits first, high bit set
on every byte but the last.

| bytes | content |
|---|---|
| 4 | magic `T2BM` |
| 1 | version, `1` |
| 3 | reserved, zero |
| … | 8 sections, each a `u32` byte length and then its bytes |
| 4 | CRC-32 (zlib / IEEE 802.3) of the 8 sections, length prefixes included |

| # | section | content |
|---|---|---|
| 0 | header | 6 varints: `n_forms`, `n_bigrams`, `n_tokens`, `form_min`, `bigram_min`, `max_len` |
| 1 | keys | `n_forms` front-coded keys in key order: `u8` shared-prefix length with the previous key, `u8` suffix length, then the suffix as letter codes |
| 2 | counts | `n_forms` varints, `count - form_min`, in key order |
| 3 | ctx | `n_forms` varints, `count - ctx`, in key order |
| 4 | n1 | `n_forms` varints, `n1`, in key order |
| 5 | row lengths | `n_forms` varints: the number of stored bigrams with each form on the left, in **id** order |
| 6 | right ids | `n_bigrams` varints: per row, the right ids ascending, as gaps (`right - previous_right - 1`, with `previous_right = -1` at a row start) |
| 7 | bigram counts | `n_bigrams` varints, `count - bigram_min`, in the same order |

- **Letter codes.** 0 to 23 in the order `ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ`, which is also code-point order. Keys are
  scriptio-continua keys (`t2b_scorer.to_continua`).
- **Ids.** A form's id is its rank by (count descending, key ascending). Readers compute it from sections 1
  and 2. The reference scorer breaks ties by id order, so both readers must use exactly this order.
- **ctx and n1** are the FULL counts from `counts.npz`: the total bigram count with the form on the left,
  and its number of distinct right neighbours. Pruned bigrams are only missing rows, so the LM backs off for
  them exactly as for an unseen pair.
- **Invariants** (checked by both readers): `count >= form_min`, `ctx <= count`, `n1 <= ctx`, right ids
  `< n_forms`, all letter codes `< 24`, section lengths consumed exactly.

## What is kept

- Forms with count `>= form_min` (2, the scorer's own `MIN_COUNT`, so no form it could propose is lost) and
  length `<= 24` (the Lexicon's `max_len`). The pooled `<RARE>` id is dropped. That gives 313,788 forms.
- Bigrams between kept forms with count `>= bigram_min`. The published model uses 2: 1,779,469 of
  6,165,907 pairs.
- `n_tokens` is the corpus size the unigram probabilities divide by (21,560,737).

## Size of the published file (bigram_min 2)

| section | bytes |
|---|---|
| header | 13 |
| keys (front-coded) | 1,311,748 |
| counts | 325,182 |
| ctx | 313,788 |
| n1 | 319,984 |
| row lengths | 315,280 |
| right ids | 2,264,135 |
| bigram counts | 1,791,737 |
| total, with magic, length prefixes and CRC | 6,641,911 (3,454,761 gzipped at level 6) |
