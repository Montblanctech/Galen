#!/usr/bin/env python3
"""Emit a uniform-random reviewer accuracy sample from medical Galen JSONL.

NOT the suspect list — random tokens for measured lemmatizer accuracy (H3).
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, resolve_path
from lib.io_utils import ensure_dir, read_jsonl, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)

    n = int(cfg.get("accuracy_sample_n", 60))
    seed = int(cfg.get("accuracy_sample_seed", 20260725))
    lemmatized = resolve_path(cfg, "lemmatized") / "galen"
    qc_dir = resolve_path(cfg, "qc")
    ensure_dir(qc_dir)

    if not lemmatized.exists():
        print(f"Missing {lemmatized}")
        return 1

    # Reservoir sample over all tokens with lemma+surface (uniform at random).
    rng = random.Random(seed)
    reservoir: list[tuple[Path, int, dict, list[str]]] = []
    seen = 0
    for path in sorted(lemmatized.glob("*.jsonl")):
        rows = list(read_jsonl(path))
        surfaces = [r.get("surface") or "" for r in rows]
        for i, row in enumerate(rows):
            if not row.get("lemma") or not row.get("surface"):
                continue
            seen += 1
            item = (path, i, row, surfaces)
            if len(reservoir) < n:
                reservoir.append(item)
            else:
                j = rng.randint(1, seen)
                if j <= n:
                    reservoir[j - 1] = item

    # Stable order by (work, index) for readability; sampling already done.
    reservoir.sort(key=lambda t: (t[0].name, t[1]))

    out_path = qc_dir / "accuracy_sample_random60.csv"
    fieldnames = [
        "surface_form",
        "lemma_produced",
        "pos",
        "one_line_context",
        "lemma_correct(y/n)",
        "correct_lemma_if_wrong",
        "work_stem",
        "token_index",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for path, i, row, surfaces in reservoir:
            left = " ".join(s for s in surfaces[max(0, i - 5) : i] if s)
            mid = row.get("surface") or ""
            right = " ".join(s for s in surfaces[i + 1 : i + 6] if s)
            ctx = f"{left} [{mid}] {right}".strip()
            writer.writerow(
                {
                    "surface_form": row.get("surface", ""),
                    "lemma_produced": row.get("lemma", ""),
                    "pos": row.get("pos", ""),
                    "one_line_context": ctx,
                    "lemma_correct(y/n)": "",
                    "correct_lemma_if_wrong": "",
                    "work_stem": path.stem,
                    "token_index": i,
                }
            )

    meta = {
        "n_requested": n,
        "n_emitted": len(reservoir),
        "seed": seed,
        "population_tokens_with_lemma": seen,
        "source": str(lemmatized),
        "output": str(out_path),
        "method": "algorithm-R reservoir sample, uniform over tokens with lemma+surface",
    }
    write_json(qc_dir / "accuracy_sample_random60_meta.json", meta)
    print(f"Wrote {len(reservoir)} rows to {out_path} (seed={seed}, population={seen})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
