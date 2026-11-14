"""T2b browser model: a compact, pruned copy of the counts cache for the in-browser scorer (t2b-wasm/).

  export   counts.npz -> docs/tools/autocorrect/model.bin (format: t2b-wasm/MODEL_FORMAT.md)
  sweep    bigram-pruning thresholds on the DEV split: model size and the README metrics per threshold
  compare  full counts vs the exported model on a split (default test): the cost of pruning

What is pruned
  forms    kept if count >= --form-min (default MIN_COUNT = 2, the scorer's own floor, so no proposable form
           is lost) and length <= 24 (the Lexicon's max_len); the pooled <RARE> id is dropped (never proposed)
  bigrams  kept if both forms are kept and the bigram count >= --bigram-min
  per form the FULL ctx (bigram count with the form on the left) and n1 (distinct right neighbours) are kept,
           so a pruned bigram falls back to the discounted unigram term exactly as an unseen one does
Ids in the model are ranks by (count desc, key asc); the scorer's tie-breaking follows id order, so the
exported model is read back by `read_model` into the same id order for both the Python and Rust scorers.

  python -I -X utf8 pipeline/t2b_export_model.py sweep --thresholds 1,2,3,4,5,8
  python -I -X utf8 pipeline/t2b_export_model.py export --bigram-min 3
  python -I -X utf8 pipeline/t2b_export_model.py compare --split test
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t2b_scorer as T  # noqa: E402
import t2b_eval as E  # noqa: E402

REPO = T.PROJECT.parent
MODEL = REPO / "docs" / "tools" / "autocorrect" / "model.bin"
MAGIC = b"T2BM"
VERSION = 1
CODE = {c: i for i, c in enumerate(T.LETTERS)}          # letter -> byte 0..23
MAX_LEN = 24


# ---------------------------------------------------------------------------------------------
# varints (unsigned LEB128), vectorised
# ---------------------------------------------------------------------------------------------

def varint_bytes(a: np.ndarray) -> bytes:
    a = np.asarray(a, dtype=np.uint64)
    if a.size == 0:
        return b""
    nbytes = np.ones(a.size, dtype=np.int64)
    for s in range(7, 64, 7):
        nbytes += (a >> np.uint64(s)) > 0
    out = np.zeros(int(nbytes.sum()), dtype=np.uint8)
    start = np.concatenate([[0], np.cumsum(nbytes)[:-1]])
    v = a.copy()
    for b in range(int(nbytes.max())):
        live = nbytes > b
        more = nbytes > b + 1
        byte = (v & np.uint64(0x7F)).astype(np.uint8) | np.where(more, 0x80, 0).astype(np.uint8)
        out[start[live] + b] = byte[live]
        v = v >> np.uint64(7)
    return out.tobytes()


def varint_read(buf: bytes, n: int) -> np.ndarray:
    """Decode n varints from buf (which must hold exactly those)."""
    b = np.frombuffer(buf, dtype=np.uint8)
    ends = np.nonzero(b < 0x80)[0]
    if len(ends) != n:
        raise ValueError(f"varint stream: expected {n} values, found {len(ends)}")
    starts = np.concatenate([[0], ends[:-1] + 1])
    out = np.zeros(n, dtype=np.uint64)
    lens = ends - starts + 1
    for k in range(int(lens.max()) if n else 0):
        live = lens > k
        out[live] |= (b[starts[live] + k] & 0x7F).astype(np.uint64) << np.uint64(7 * k)
    return out


def checksum(data: bytes) -> int:
    """CRC-32 (zlib / IEEE 802.3) of the payload: a cheap check against a truncated download."""
    return zlib.crc32(data) & 0xFFFFFFFF


# ---------------------------------------------------------------------------------------------
# pruning
# ---------------------------------------------------------------------------------------------

def prune(c: T.Counts, form_min: int = T.MIN_COUNT, bigram_min: int = 1) -> T.Counts:
    """Pruned Counts in model id order (count desc, key asc). bigram_min = 1 keeps every bigram between kept
    forms (only the ids are renumbered)."""
    n_old = len(c.forms)
    lens = np.array([len(f) for f in c.forms])
    keep_old = np.nonzero((c.uni >= form_min) & (lens <= MAX_LEN))[0]
    keys = [c.forms[i] for i in keep_old.tolist()]
    for k in keys:
        if any(ch not in CODE for ch in k):
            raise ValueError(f"form outside the 24-letter alphabet: {k!r}")
    alpha = np.argsort(np.array(keys, dtype=object), kind="stable")       # positions in key order
    alpha_rank = np.empty(len(keys), dtype=np.int64)
    alpha_rank[alpha] = np.arange(len(keys))
    uni_k = c.uni[keep_old]
    order = np.lexsort((alpha_rank, -uni_k))                              # count desc, key asc
    new_of_old = np.full(n_old, -1, dtype=np.int64)
    new_of_old[keep_old[order]] = np.arange(len(order))
    forms = [keys[i] for i in order.tolist()]
    uni = uni_k[order].astype(np.float64)
    ctx = c.ctx[keep_old[order]].astype(np.int64)
    n1 = c.n1[keep_old[order]].astype(np.int64)
    left = new_of_old[c.bkeys >> T.SHIFT]
    right = new_of_old[c.bkeys & (T.MAXV - 1)]
    m = (left >= 0) & (right >= 0) & (c.bcounts >= bigram_min)
    bk = (left[m] << T.SHIFT) | right[m]
    bc = c.bcounts[m].astype(np.int32)
    o = np.argsort(bk, kind="stable")
    meta = {"n_tokens_ours": int(c.n_tokens), "form_min": form_min, "bigram_min": bigram_min,
            "source_forms": n_old, "source_bigrams": int(len(c.bkeys))}
    return T.Counts(forms, uni, bk[o], bc[o], ctx, n1, meta)


# ---------------------------------------------------------------------------------------------
# writer / reader
# ---------------------------------------------------------------------------------------------

def _section(b: bytes) -> bytes:
    return len(b).to_bytes(4, "little") + b


def encode(p: T.Counts) -> bytes:
    """Serialise a pruned Counts (in model id order) as model.bin bytes."""
    n = len(p.forms)
    form_min = int(p.meta["form_min"])
    bigram_min = int(p.meta["bigram_min"])
    alpha = sorted(range(n), key=lambda i: p.forms[i])
    # keys, front-coded in key order
    kb = bytearray()
    prev = ""
    for i in alpha:
        f = p.forms[i]
        s = 0
        while s < len(prev) and s < len(f) and prev[s] == f[s]:
            s += 1
        kb.append(s)
        kb.append(len(f) - s)
        kb.extend(CODE[ch] for ch in f[s:])
        prev = f
    ai = np.array(alpha, dtype=np.int64)
    uni = p.uni[ai].astype(np.int64)
    ctx = p.ctx[ai]
    if (uni < form_min).any() or (ctx > uni).any() or (p.n1[ai] > ctx).any():
        raise ValueError("count invariant broken (uni >= form_min, ctx <= uni, n1 <= ctx)")
    left = p.bkeys >> T.SHIFT
    right = p.bkeys & (T.MAXV - 1)
    rowlen = np.bincount(left, minlength=n)
    first = np.ones(len(left), dtype=bool)
    first[1:] = left[1:] != left[:-1]
    delta = right.copy()
    delta[~first] = right[~first] - right[np.nonzero(~first)[0] - 1] - 1
    if (delta < 0).any() or (p.bcounts < bigram_min).any():
        raise ValueError("bigram keys must be sorted and unique, counts >= bigram_min")
    header = varint_bytes(np.array([n, len(p.bkeys), int(p.meta["n_tokens_ours"]), form_min, bigram_min,
                                    max(len(f) for f in p.forms)]))
    body = b"".join(_section(x) for x in (
        header, bytes(kb), varint_bytes(uni - form_min), varint_bytes(uni - ctx), varint_bytes(p.n1[ai]),
        varint_bytes(rowlen), varint_bytes(delta), varint_bytes(p.bcounts.astype(np.int64) - bigram_min)))
    return MAGIC + bytes([VERSION, 0, 0, 0]) + body + checksum(body).to_bytes(4, "little")


def decode(data: bytes) -> T.Counts:
    """model.bin bytes -> Counts in model id order (what the Rust scorer sees)."""
    if data[:4] != MAGIC or data[4] != VERSION:
        raise ValueError("not a T2BM v1 model")
    body = data[8:-4]
    if checksum(body) != int.from_bytes(data[-4:], "little"):
        raise ValueError("model checksum mismatch")
    secs, o = [], 0
    while o < len(body):
        ln = int.from_bytes(body[o:o + 4], "little")
        secs.append(body[o + 4:o + 4 + ln])
        o += 4 + ln
    if len(secs) != 8:
        raise ValueError("model: expected 8 sections")
    n, nb, n_tok, form_min, bigram_min, _maxlen = (int(x) for x in varint_read(secs[0], 6))
    kb = secs[1]
    keys, prev, o = [], "", 0
    for _ in range(n):
        s, ln = kb[o], kb[o + 1]
        f = prev[:s] + "".join(T.LETTERS[x] for x in kb[o + 2:o + 2 + ln])
        keys.append(f)
        prev = f
        o += 2 + ln
    uni_a = varint_read(secs[2], n).astype(np.int64) + form_min
    ctx_a = uni_a - varint_read(secs[3], n).astype(np.int64)
    n1_a = varint_read(secs[4], n).astype(np.int64)
    alpha_rank = np.arange(n)
    order = np.lexsort((alpha_rank, -uni_a))          # id -> alpha position
    forms = [keys[i] for i in order.tolist()]
    rowlen = varint_read(secs[5], n).astype(np.int64)
    delta = varint_read(secs[6], nb).astype(np.int64)
    bc = (varint_read(secs[7], nb).astype(np.int64) + bigram_min).astype(np.int32)
    left = np.repeat(np.arange(n, dtype=np.int64), rowlen)
    # right ids: within each row, the running sum of (delta + 1), minus 1
    cs = np.cumsum(delta + 1)
    starts = np.concatenate([[0], np.cumsum(rowlen)[:-1]])
    nz = rowlen > 0
    prior = np.where(starts[nz] > 0, cs[np.maximum(starts[nz] - 1, 0)], 0)
    right = cs - np.repeat(prior, rowlen[nz]) - 1
    bk = (left << T.SHIFT) | right
    meta = {"n_tokens_ours": n_tok, "form_min": form_min, "bigram_min": bigram_min}
    return T.Counts(forms, uni_a[order].astype(np.float64), bk, bc, ctx_a[order], n1_a[order], meta)


def read_model(path: Path = MODEL) -> T.Counts:
    return decode(Path(path).read_bytes())


def write_model(p: T.Counts, path: Path = MODEL) -> int:
    data = encode(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data)


def same_counts(a: T.Counts, b: T.Counts) -> bool:
    return (a.forms == b.forms and np.array_equal(a.uni, b.uni) and np.array_equal(a.bkeys, b.bkeys)
            and np.array_equal(a.bcounts, b.bcounts) and np.array_equal(a.ctx, b.ctx)
            and np.array_equal(a.n1, b.n1) and int(a.n_tokens) == int(b.n_tokens))


# ---------------------------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------------------------

def load_lines(split: str) -> list[dict]:
    path = E.OUT / f"testset_{split}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def run_eval(counts: T.Counts, lines: list[dict], levels=("clean", "light", "heavy")) -> dict:
    seg = T.Segmenter(T.Lexicon(counts, min_count=T.MIN_COUNT))
    out = {}
    for lv in levels:
        r = E.evaluate(lines, lv, seg.segment)
        r.pop("samples", None)
        out[lv] = r
    return out


METRICS = ("boundary_F1", "word_recovery_R", "line_top1", "line_top5", "recoverable_top1", "recoverable_top5")


def fmt_row(name: str, size: int | None, res: dict) -> list[str]:
    rows = []
    for lv, r in res.items():
        rows.append(f"| {name} | {'' if size is None else f'{size / 1e6:.2f} MB'} | {lv} | "
                    + " | ".join(f"{r[m]:.3f}" if r.get(m) is not None else "" for m in METRICS) + " |")
    return rows


MAX_BYTES = 8_000_000
TOL_F1 = 0.005          # largest allowed drop in boundary F1, per level, against the full counts
TOL_LINE = 0.010        # largest allowed drop in line top-1 and top-5, per level


def pick(res_all: dict) -> str:
    """The selection rule, fixed before the sweep was run: among thresholds whose model is <= 8 MB, the
    LARGEST (smallest model) whose dev metrics stay within TOL_F1 / TOL_LINE of the full counts on every
    level; if none does, the smallest threshold that fits."""
    full = res_all["full"]["results"]
    fits = sorted((int(k.rsplit("_", 1)[1]), v) for k, v in res_all.items()
                  if k.startswith("bigram_min_") and v["size"] <= MAX_BYTES)
    ok = [t for t, v in fits if all(
        full[lv]["boundary_F1"] - r["boundary_F1"] <= TOL_F1 + 1e-12
        and full[lv]["line_top1"] - r["line_top1"] <= TOL_LINE + 1e-12
        and full[lv]["line_top5"] - r["line_top5"] <= TOL_LINE + 1e-12 for lv, r in v["results"].items())]
    if ok:
        return f"bigram_min {max(ok)} (within tolerance; size {res_all[f'bigram_min_{max(ok)}']['size']:,} bytes)"
    return f"bigram_min {fits[0][0]} (none within tolerance; smallest threshold that fits)" if fits else "none fits"


HEAD = ("| model | size | level | boundary F1 | word rec. | line top-1 | line top-5 | rec. top-1 | rec. top-5 |\n"
        "|---|---|---|---|---|---|---|---|---|")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--counts", default=str(T.cache_path()))
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--form-min", type=int, default=T.MIN_COUNT)
    ex.add_argument("--bigram-min", type=int, required=True)
    ex.add_argument("--out", default=str(MODEL))
    sw = sub.add_parser("sweep")
    sw.add_argument("--split", default="dev")
    sw.add_argument("--thresholds", default="1,2,3,4,5,8")
    sw.add_argument("--form-min", type=int, default=T.MIN_COUNT)
    sw.add_argument("--no-eval", action="store_true")
    co = sub.add_parser("compare")
    co.add_argument("--split", default="test")
    co.add_argument("--model", default=str(MODEL))
    a = ap.parse_args(argv)
    t0 = time.time()
    full = T.load_counts(Path(a.counts))
    print(f"loaded {a.counts}: {len(full.forms):,} forms, {len(full.bkeys):,} bigrams ({time.time() - t0:.0f}s)",
          file=sys.stderr)
    out_dir = E.OUT
    if a.cmd == "export":
        p = prune(full, a.form_min, a.bigram_min)
        size = write_model(p, Path(a.out))
        back = read_model(Path(a.out))
        assert same_counts(p, back), "round trip failed"
        print(f"wrote {a.out}: {size:,} bytes, {len(p.forms):,} forms, {len(p.bkeys):,} bigrams (round trip ok)")
        return
    if a.cmd == "sweep":
        lines = load_lines(a.split)
        rows, res_all = [HEAD], {}
        if not a.no_eval:
            res = run_eval(full, lines)
            res_all["full"] = {"size": None, "results": res}
            rows += fmt_row("full counts.npz", None, res)
        for t in (int(x) for x in a.thresholds.split(",")):
            p = prune(full, a.form_min, t)
            size = len(encode(p))
            print(f"bigram_min {t}: {len(p.forms):,} forms, {len(p.bkeys):,} bigrams, {size:,} bytes",
                  file=sys.stderr, flush=True)
            res = {} if a.no_eval else run_eval(p, lines)
            res_all[f"bigram_min_{t}"] = {"size": size, "forms": len(p.forms), "bigrams": int(len(p.bkeys)),
                                         "results": res}
            rows += fmt_row(f"bigram >= {t}", size, res) if res else [f"| bigram >= {t} | {size / 1e6:.2f} MB |"]
            print("\n".join(rows[-3:]), flush=True)
        if not a.no_eval:
            res_all["pick"] = pick(res_all)
            rows.append(f"\npick (rule declared before the sweep): {res_all['pick']}")
            (out_dir / f"prune_sweep_{a.split}.json").write_text(json.dumps(res_all, indent=1), encoding="utf-8")
            (out_dir / f"prune_sweep_{a.split}.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        print("\n".join(rows))
        return
    if a.cmd == "compare":
        lines = load_lines(a.split)
        p = read_model(Path(a.model))
        size = Path(a.model).stat().st_size
        rf = run_eval(full, lines)
        rp = run_eval(p, lines)
        rows = [HEAD] + fmt_row("full counts.npz", None, rf) + fmt_row(
            f"model.bin (bigram >= {p.meta['bigram_min']})", size, rp)
        (out_dir / f"prune_compare_{a.split}.json").write_text(json.dumps(
            {"model": str(a.model), "size": size, "meta": p.meta, "full": rf, "pruned": rp}, indent=1),
            encoding="utf-8")
        (out_dir / f"prune_compare_{a.split}.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        print("\n".join(rows))


if __name__ == "__main__":
    main()
