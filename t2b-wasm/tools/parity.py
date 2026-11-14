"""Parity: the Rust port (native t2b-cli) against the Python reference, both on the PRUNED model.bin.

Inputs: every line of the dev and test sets at every noise level (clean, light, heavy), plus each clean line
re-spaced and lower-cased ("spaced_lower", e.g. "ουν ειωθεν η φυσις", final ς included) to exercise the
to_continua path. Python side: t2b_scorer.Segmenter on t2b_export_model.read_model(model.bin), k = 5; flags
from t2b_flag.flag_words itself on the top reading's observed words (fresh Lexicon, so its top-12 candidate
cache is not shared with the segmenter's top-8 one; ids cast to int64, see Int64Grid).

Checks
  top-1      same segments (spans, forms, edit tags) and score within 1e-9; per-segment LM and channel terms
             within 1e-9
  top-k      the same k readings in the same order; where not, the score lists must agree within 1e-9 and every
             differing rank must sit inside a group of tied scores (= "up to float ties")
  flags      same flagged segments, kinds, best alternatives, edit tags and margins (t2b_flag rounds to 2 dp),
             the same notes (alternative is also a spelling; unattested form of an attested stem), and the same
             spellings (unattested words a spelling rule explains, accepted or not)
  texts      whole texts read with the writer's habits (t2b_spelling.segment_text against segment_text_json,
             t2b-cli --text): the same habits and, line by line, the same top reading and score
Both sides use the spelling rules (outputs/t2b/spelling_rules.json; Rust: src/spelling_table.rs, generated
from it).

  python -I -X utf8 t2b-wasm/tools/parity.py [--limit N]
  (build first: cargo build --release in t2b-wasm/)
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PIPE = REPO / "galen-density-map" / "pipeline"
sys.path.insert(0, str(PIPE))
import t2b_scorer as T  # noqa: E402
import t2b_export_model as X  # noqa: E402
import t2b_flag as F  # noqa: E402
import t2b_spelling as S  # noqa: E402

CLI = REPO / "t2b-wasm" / "target" / "release" / ("t2b-cli.exe" if sys.platform == "win32" else "t2b-cli")
OUT = T.PROJECT / "outputs" / "t2b"
TOL = 1e-9
K = 5           # readings compared
KX = K + 1      # readings fetched: the extra one shows whether a reading at rank K ties with one just cut off


def inputs(limit: int = 0) -> list[dict]:
    rows = []
    for split in ("dev", "test"):
        lines = X.load_lines(split)
        if limit:
            lines = lines[:limit]
        for r in lines:
            for lv in ("clean", "light", "heavy"):
                rows.append({"split": split, "id": r["id"], "level": lv, "text": r["noisy"][lv]["s"]})
            rows.append({"split": split, "id": r["id"], "level": "spaced_lower", "text": " ".join(r["gold"]).lower()})
    return rows


def py_reading(seg: T.Segmenter, r: T.Reading) -> dict:
    lex = seg.lex
    segs, prev = [], -1
    for x in r.segments:
        L = x.end - x.start
        if x.form is None:
            lm, chan, wid = 0.0, math.log(T.P_UNK) + L * seg._unk_letter, -1
        else:
            wid = lex.exact[x.form]
            lm = float(seg.lm_grid(np.array([prev], dtype=np.int64), np.array([wid], dtype=np.int64))[0, 0])
            chan = next(c for i, c, _ in lex.candidates(x.observed, seg.cand_top) if i == wid)
        segs.append({"start": x.start, "end": x.end, "observed": x.observed, "form": x.form, "edit": x.edit,
                     "lm": lm, "chan": chan})
        prev = wid
    return {"score": r.score, "segments": segs}


def key_of(rd: dict) -> tuple:
    return tuple((s["start"], s["end"], s["form"], s["edit"]) for s in rd["segments"])


class Int64Grid:
    """t2b_flag.flag_words calls seg.lm_grid(np.array([prev]), ...) without a dtype. With numpy 1.x on Windows
    that array is int32 and `prev << 23` overflows for every id >= 256, so the reference looks up the wrong
    bigram. The harness hands flag_words this wrapper, which casts to int64 as Segmenter.segment does, so the
    comparison is against the intended definition (README "Parity", reference bug)."""

    def __init__(self, seg: T.Segmenter):
        self.seg = seg
        self.lex = seg.lex

    def lm_grid(self, prev, cand):
        return self.seg.lm_grid(np.asarray(prev, dtype=np.int64), np.asarray(cand, dtype=np.int64))


def py_flags(seg_flag: T.Segmenter, rd: dict) -> tuple[list[dict], list[tuple]]:
    words = [{"raw": s["observed"], "form": s["observed"], "key": s["observed"], "n": len(s["observed"]),
              "restored": 0, "fragment": False, "elided": False} for s in rd["segments"]]
    sps: list = []
    rows = F.flag_words(Int64Grid(seg_flag), words, margin=4.0, spellings=sps)
    return ([{"segment": x["i"], "kind": x["kind"], "alternative": x["best_alternative"] or None,
              "alt_edit": x["alt_edit"], "margin": x["margin_nats"], "alt_spelling": x["alt_spelling"] or None,
              "stem_attested": x["stem_attested"]} for x in rows],
            [(x["i"], x["regularized"], x["rule"], x["accepted"]) for x in sps])


def words_of(key: tuple, rd: dict) -> tuple:
    return tuple(f if f is not None else "?" + s["observed"] for (_, _, f, _), s in zip(key, rd["segments"]))


def tied_ok(ps: list[float], rs: list[float], pk: list, rk: list, pw: list, rw: list) -> bool:
    """The first K readings differ only where scores tie: equal score lists, and at each differing rank either
    the same words (another segmentation of the same reading with a tied score, which the dedup by words
    merges) or another rank, among the KX fetched, with the same score (tied readings in another order, or a
    tied reading cut off at rank K)."""
    n = min(K, len(ps))
    if min(K, len(rs)) != n or any(abs(a - b) > TOL for a, b in zip(ps[:n], rs[:n])):
        return False
    for i in range(n):
        if pk[i] != rk[i] and pw[i] != rw[i]:
            near = [j for j in range(len(ps)) if j != i and abs(ps[j] - ps[i]) <= TOL]
            if not near:
                return False
    return True


def text_cases(n_texts: int = 12, per: int = 30) -> list[str]:
    """Whole texts with habits to find: the Philodemus papyri (held out of the counts), lines as the editor
    divided them, Leiden marks removed by to_continua, `per` lines to a text."""
    out = []
    for w in ("tlg1595.tlg221", "tlg1595.tlg370"):
        files = [p for p in T.corpus_files(T.data_root(None)) if T.work_id(p) == w]
        lines = [T.to_continua(x) for x in files[0].read_text(encoding="utf-8", errors="replace").splitlines()]
        lines = [x for x in lines if len(x) >= 12]
        for i in range(0, min(len(lines), per * n_texts // 2), per):
            out.append("\n".join(lines[i:i + per]))
        # texts where the writer's habits must show: the lines that carry the Herculanean ποη- for ποιη- and the
        # assimilated nasals (συνχ-, ἐνκ-, ἐνπ-), eight to a text
        for pat in ("ΠΟΗ", "ΣΥΝΧ", "ΕΝΚ", "ΕΝΠ"):
            hab = [x for x in lines if pat in x]
            for i in range(0, min(len(hab), 24), 8):
                out.append("\n".join(hab[i:i + 8]))
    return out


def text_parity(seg: T.Segmenter, model: str, problems: list) -> dict:
    texts = text_cases()
    same_habits = same_lines = n_lines = with_habits = 0
    for t in texts:
        res = subprocess.run([str(CLI), model, "--text", "-k", "1"], input=t.encode("utf-8"), capture_output=True,
                             check=True)
        ro = json.loads(res.stdout.decode("utf-8"))
        pr, ph = S.segment_text(seg, t, k=1)
        rh = [(h["rule"], h["uses"], h["opportunities"]) for h in ro["habits"]]
        phk = [(h["rule"], h["uses"], h["opportunities"]) for h in ph]
        with_habits += bool(ph)
        ok_h = rh == phk and all(abs(a_["text_rate"] - b_["text_rate"]) <= 1e-12 for a_, b_ in zip(ph, ro["habits"]))
        same_habits += ok_h
        if not ok_h:
            problems.append({"kind": "text_habits", "py": ph, "rust": ro["habits"]})
        for rd, line in zip(pr, ro["lines"]):
            n_lines += 1
            pk = tuple((g.start, g.end, g.form, g.edit) for g in rd[0].segments)
            r0 = line["readings"][0]
            rk = tuple((g["start"], g["end"], g["form"], g["edit"]) for g in r0["segments"])
            ok = pk == rk and abs(rd[0].score - r0["score"]) <= TOL
            same_lines += ok
            if not ok:
                problems.append({"kind": "text_line", "py": [rd[0].score, rd[0].text], "rust": [r0["score"], r0["text"]]})
    return {"texts": len(texts), "texts_with_habits": with_habits, "habits_identical": same_habits,
            "lines": n_lines, "top1_identical": same_lines}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(X.MODEL))
    ap.add_argument("--limit", type=int, default=0, help="lines per split (0 = all)")
    ap.add_argument("--texts-only", action="store_true", help="only the whole-text (habits) check")
    a = ap.parse_args(argv)
    counts = X.read_model(Path(a.model))
    if a.texts_only:
        probs: list = []
        seg_t = T.Segmenter(T.Lexicon(counts, spelling=S.SpellingRules.load()))
        print(json.dumps(text_parity(seg_t, a.model, probs)), len(probs))
        for p_ in probs[:5]:
            print(json.dumps(p_, ensure_ascii=False)[:600])
        return
    rows = inputs(a.limit)
    seg = T.Segmenter(T.Lexicon(counts, spelling=S.SpellingRules.load()))
    seg_flag = T.Segmenter(T.Lexicon(counts, spelling=S.SpellingRules.load()))
    # Rust
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "in.txt"
        inp.write_text("\n".join(r["text"] for r in rows) + "\n", encoding="utf-8")
        t0 = time.time()
        with open(inp, encoding="utf-8") as fh:
            res = subprocess.run([str(CLI), a.model, "-k", str(KX), "--time"], stdin=fh, capture_output=True,
                                 check=True)
        rust_s = time.time() - t0
    rust = [json.loads(x) for x in res.stdout.decode("utf-8").splitlines()]
    timing = res.stderr.decode("utf-8").strip()
    assert len(rust) == len(rows)
    tally: dict = {}
    problems = []
    t0 = time.time()
    for row, ro in zip(rows, rust):
        reads = seg.segment(row["text"], k=KX)
        pr = [py_reading(seg, r) for r in reads]
        rr = [{"score": x["score"], "segments": x["segments"]} for x in ro["readings"]]
        t = tally.setdefault(row["level"], {"inputs": 0, "top1": 0, "top1_tie": 0, "topk": 0, "topk_tie": 0,
                                            "seg_terms": 0, "flags": 0, "input_norm": 0})
        t["inputs"] += 1
        t["input_norm"] += ro["input"] == T.to_continua(row["text"])
        pk, rk = [key_of(x) for x in pr], [key_of(x) for x in rr]
        ps, rs = [x["score"] for x in pr], [x["score"] for x in rr]
        pw, rw = [words_of(k, x) for k, x in zip(pk, pr)], [words_of(k, x) for k, x in zip(rk, rr)]
        top1 = pk[0] == rk[0] and abs(ps[0] - rs[0]) <= TOL
        t["top1"] += top1
        if not top1 and tied_ok(ps, rs, pk, rk, pw, rw) and (pw[0] == rw[0] or (len(ps) > 1 and abs(ps[0] - ps[1]) <= TOL)):
            t["top1_tie"] += 1
        if pk[:K] == rk[:K] and all(abs(x - y) <= TOL for x, y in zip(ps[:K], rs[:K])):
            t["topk"] += 1
        elif tied_ok(ps, rs, pk, rk, pw, rw):
            t["topk_tie"] += 1
        else:
            problems.append({"row": row, "kind": "topk", "py": [(s, " ".join(str(w[2]) for w in k)) for s, k in zip(ps, pk)],
                             "rust": [(s, " ".join(str(w[2]) for w in k)) for s, k in zip(rs, rk)]})
        if top1:
            terms = all(abs(a_["lm"] - b_["lm"]) <= TOL and abs(a_["chan"] - b_["chan"]) <= TOL
                        for a_, b_ in zip(pr[0]["segments"], rr[0]["segments"]))
            t["seg_terms"] += terms
            pf, psp = py_flags(seg_flag, pr[0])
            rf = [{"segment": f["segment"], "kind": f["kind"], "alternative": f["alternative"],
                   "alt_edit": f["alt_edit"], "margin": f["margin"], "alt_spelling": f["alt_spelling"],
                   "stem_attested": f["stem_attested"]} for f in ro["readings"][0]["flags"]]
            rsp = [(x["segment"], x["regularized"], x["rule"], x["accepted"]) for x in ro["readings"][0]["spellings"]]
            same = len(pf) == len(rf) and psp == rsp and all(
                x["segment"] == y["segment"] and x["kind"] == y["kind"] and x["alternative"] == y["alternative"]
                and x["alt_edit"] == y["alt_edit"] and x["alt_spelling"] == y["alt_spelling"]
                and x["stem_attested"] == y["stem_attested"]
                and ((x["margin"] is None and y["margin"] is None)
                     or (x["margin"] is not None and y["margin"] is not None
                         and abs(x["margin"] - y["margin"]) <= 0.0051))
                for x, y in zip(pf, rf))
            t["flags"] += same
            if not same:
                problems.append({"row": row, "kind": "flags", "py": [pf, psp], "rust": [rf, rsp]})
            if not terms:
                problems.append({"row": row, "kind": "terms"})
        else:
            problems.append({"row": row, "kind": "top1", "py": [ps[0], pk[0]], "rust": [rs[0], rk[0]]})
    py_s = time.time() - t0
    texts = text_parity(seg, a.model, problems)
    tot = {k: sum(v[k] for v in tally.values()) for k in next(iter(tally.values()))}
    report = {"model": str(Path(a.model).relative_to(REPO)) if Path(a.model).is_relative_to(REPO) else a.model,
              "k": K, "by_level": tally, "total": tot, "rust_seconds": round(rust_s, 1),
              "python_seconds": round(py_s, 1), "rust_timing": timing, "texts": texts, "problems": problems[:50],
              "n_problems": len(problems)}
    lines = ["| inputs | level | top-1 identical | top-1 tie-only | top-k identical | top-k up to ties | segment terms "
             "(of top-1 identical) | flags identical | normalised input identical |",
             "|---|---|---|---|---|---|---|---|---|"]
    for lv, v in list(tally.items()) + [("all", tot)]:
        lines.append(f"| {v['inputs']} | {lv} | {v['top1']} | {v['top1_tie']} | {v['topk']} | {v['topk'] + v['topk_tie']} "
                     f"| {v['seg_terms']} | {v['flags']} | {v['input_norm']} |")
    md = "\n".join(lines)
    if not a.limit:
        (OUT / "wasm_parity.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / "wasm_parity.md").write_text(md + "\n", encoding="utf-8")
    print(md)
    print(f"top-1 agreement {tot['top1']}/{tot['inputs']} = {tot['top1'] / tot['inputs']:.4%}; "
          f"problems {len(problems)}; rust {rust_s:.1f}s ({timing.splitlines()[-1]}), python {py_s:.1f}s")
    for p in problems[:5]:
        print(json.dumps(p, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
