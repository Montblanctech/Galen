"""Alignment diagnostic for one held work: units, aligned units, first misaligned units.

Aligned tokens are shown in [brackets].

A unit counts as aligned when at least half of its tokens found a JSONL index.
Usage (.venv): python -X utf8 pipeline/lsjgold/align_check.py tlg0059.tlg034 [--show 5] [--min 0.5]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relocate  # noqa: E402


def check(work: str, show: int = 5, min_frac: float = 0.5, quiet: bool = False) -> dict:
    au, wk = work.split(".")
    held = relocate.held_works()
    if (au, wk) not in held:
        raise SystemExit(f"{work}: not held")
    xml, jsonl = held[(au, wk)]
    passages = relocate.passage_index(xml)
    aligned = relocate.align_to_jsonl(passages, jsonl)
    keys = list(dict.fromkeys(k for k, _ in passages))  # a unit resumed after a nested one appears twice
    n_units = len(keys)
    n_ok, n_tok, n_tok_ok, bad = 0, 0, 0, []
    for loc in keys:
        al = aligned.get(loc, [])
        toks = [s for s, _ in al]
        hits = sum(1 for _, i in al if i is not None)
        n_tok += len(toks)
        n_tok_ok += hits
        if toks and hits / len(toks) >= min_frac:
            n_ok += 1
        else:
            bad.append((loc, hits, len(toks), [t if i is None else f"[{t}]" for t, i in al[:8]]))
    res = {"work": work, "xml": xml.name, "jsonl": jsonl.name, "units": n_units, "aligned_units": n_ok,
           "unit_rate": n_ok / n_units if n_units else 0.0, "tokens": n_tok, "aligned_tokens": n_tok_ok}
    if not quiet:
        print(f"{work}  xml={xml.name}  jsonl={jsonl.parent.name}/{jsonl.name}")
        print(f"units {n_units}  aligned {n_ok} ({100 * res['unit_rate']:.1f}%)  tokens {n_tok_ok}/{n_tok}")
        for loc, h, n, t in bad[:show]:
            print(f"  MISALIGNED {loc}  {h}/{n}  {' '.join(t)}")
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("works", nargs="+", help="tlgNNNN.tlgNNN ...")
    ap.add_argument("--show", type=int, default=5)
    ap.add_argument("--min", type=float, default=0.5, help="fraction of a unit's tokens that must align")
    a = ap.parse_args()
    for w in a.works:
        check(w, a.show, a.min)
