"""Response size of typical calls, in tokens (chars / 4).

    python mcp/scripts/measure.py            # live public data (uses/creates the user cache)
    python mcp/scripts/measure.py --local .  # a local checkout of the repo
"""
from __future__ import annotations

import argparse
import sys

from galen_mcp.core import Galen, ToolError
from galen_mcp.store import Store

CALLS = [
    ("list_works", (), {}),
    ("list_works", ("full",), {}),
    ("search_terms", ("nerve",), {}),
    ("search_terms", ("humour",), {}),
    ("search_terms", ("νευρον",), {}),
    ("get_term", ("γνώρισμα",), {}),
    ("get_term", ("δριμύς",), {}),
    ("get_term", ("δριμύς",), {"detail": "full"}),
    ("get_term", ("νεῦρον",), {"work": "de-humero", "detail": "full"}),
    ("get_passage", ("K15.609",), {}),
    ("get_passage", ("K13.458",), {}),
    ("get_passage", ("K7.760",), {}),
    ("get_passage", ("K15.609",), {"detail": "full"}),
    ("get_passage", ("K15.6091",), {}),
    ("lsj_gold_lemma", ("ἀγαθὸν",), {}),
    ("lsj_gold_lemma", ("abdicavit",), {}),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="repo checkout to read instead of the network")
    ap.add_argument("--cache-dir")
    a = ap.parse_args()
    g = Galen(Store(a.cache_dir, source_dir=a.local))
    print("| call | chars | tokens |\n|---|---:|---:|")
    for name, args, kw in CALLS:
        try:
            out = getattr(g, name)(*args, **kw)
        except ToolError as e:
            out = str(e)
        call = f"{name}({', '.join([repr(x) for x in args] + [f'{k}={v!r}' for k, v in kw.items()])})"
        print(f"| `{call}` | {len(out)} | {len(out) // 4} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
