#!/usr/bin/env python3
"""Stage 05: log-likelihood (G²) keyness vs reference corpus (Dunning 1993)."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, resolve_path
from lib.io_utils import ensure_dir, read_json


def log_likelihood(a: float, b: float, c: float, d: float) -> float:
    """
    a = freq in Galen subset
    b = freq in reference
    c = total Galen tokens
    d = total reference tokens
    """
    if a < 0 or b < 0 or c <= 0 or d <= 0:
        return 0.0
    # Avoid log(0): use continuity-friendly floor only in expected terms path
    n = c + d
    e1 = c * (a + b) / n
    e2 = d * (a + b) / n
    g2 = 0.0
    if a > 0 and e1 > 0:
        g2 += 2 * a * math.log(a / e1)
    if b > 0 and e2 > 0:
        g2 += 2 * b * math.log(b / e2)
    # when b==0, second term is 0 by convention in many implementations
    return g2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)

    outputs = resolve_path(cfg, "outputs")
    galen = read_json(outputs / "lemma_frequency_galen.json")
    ref = read_json(outputs / "lemma_frequency_reference.json")

    c = float(galen["corpus_total_tokens"])
    d = float(ref["corpus_total_tokens"])
    if c <= 0:
        print("Galen corpus has 0 tokens.")
        return 1
    if d <= 0:
        print("WARNING: reference corpus has 0 tokens — keyness will be uninformative.")

    min_freq = int(cfg.get("min_domain_frequency", 5))
    rows = []
    for lemma, ginfo in galen["lemmas"].items():
        a = float(ginfo["raw_count"])
        if a < min_freq:
            continue
        rinfo = ref["lemmas"].get(lemma, {"raw_count": 0, "per_10k": 0.0})
        b = float(rinfo["raw_count"])
        g2 = log_likelihood(a, b, c, max(d, 1.0))
        # direction: overused if relative freq higher in Galen
        galen_rel = a / c
        ref_rel = (b / d) if d > 0 else 0.0
        direction = "overused" if galen_rel > ref_rel else "underused"
        rows.append(
            {
                "lemma": lemma,
                "pos": ginfo.get("pos", ""),
                "galen_raw": int(a),
                "galen_per10k": ginfo.get("per_10k", 0.0),
                "reference_raw": int(b),
                "reference_per10k": rinfo.get("per_10k", 0.0),
                "log_likelihood": round(g2, 4),
                "direction": direction,
            }
        )

    rows.sort(key=lambda r: r["log_likelihood"], reverse=True)
    ensure_dir(outputs)
    out_path = outputs / "keyness_scores.csv"
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "lemma",
                "pos",
                "galen_raw",
                "galen_per10k",
                "reference_raw",
                "reference_per10k",
                "log_likelihood",
                "direction",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    over = [r for r in rows if r["direction"] == "overused"][:20]
    print(f"Wrote {len(rows)} rows to {out_path}")
    print("Top 20 overused by G² (eyeball check):")
    for r in over:
        print(f"  {r['log_likelihood']:10.2f}  {r['lemma']}  ({r['pos']}) galen={r['galen_raw']} ref={r['reference_raw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
