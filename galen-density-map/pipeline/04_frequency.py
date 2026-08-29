#!/usr/bin/env python3
"""Stage 04: aggregate lemma frequencies (raw + per 10k).

Writes medical-subcorpus, reference, and whole-Galen (medical + nonmedical) files.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, resolve_path
from lib.greek_normalize import casefold_greek
from lib.io_utils import ensure_dir, read_jsonl, write_json


def aggregate_dirs(srcs: list[Path]) -> dict:
    counts: Counter[str] = Counter()
    pos_votes: dict[str, Counter[str]] = defaultdict(Counter)
    total = 0
    files = 0
    for src in srcs:
        if not src.exists():
            continue
        for path in sorted(src.glob("*.jsonl")):
            files += 1
            for row in read_jsonl(path):
                lemma = row.get("lemma")
                if not lemma:
                    continue
                lemma = casefold_greek(lemma)
                counts[lemma] += 1
                total += 1
                pos = row.get("pos") or ""
                if pos:
                    pos_votes[lemma][pos] += 1

    lemmas = {}
    for lemma, raw in counts.items():
        pos = pos_votes[lemma].most_common(1)[0][0] if pos_votes[lemma] else ""
        lemmas[lemma] = {
            "raw_count": raw,
            "per_10k": round((raw / total) * 10000, 4) if total else 0.0,
            "pos": pos,
        }
    return {"corpus_total_tokens": total, "files": files, "lemmas": lemmas}


def aggregate_dir(src: Path) -> dict:
    return aggregate_dirs([src])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)

    lemmatized = resolve_path(cfg, "lemmatized")
    outputs = resolve_path(cfg, "outputs")
    ensure_dir(outputs)

    galen_dir = lemmatized / "galen"
    if not galen_dir.exists():
        print(f"Missing lemmatized Galen dir: {galen_dir}")
        return 1
    galen_freq = aggregate_dir(galen_dir)
    write_json(outputs / "lemma_frequency_galen.json", galen_freq)
    print(
        f"Galen (medical): {galen_freq['corpus_total_tokens']} tokens, "
        f"{len(galen_freq['lemmas'])} lemmas"
    )

    nonmed_dir = resolve_path(cfg, "lemmatized_galen_nonmedical")
    if nonmed_dir.exists() and any(nonmed_dir.glob("*.jsonl")):
        nonmed_freq = aggregate_dir(nonmed_dir)
        write_json(outputs / "lemma_frequency_galen_nonmedical.json", nonmed_freq)
        print(
            f"Galen (nonmedical): {nonmed_freq['corpus_total_tokens']} tokens, "
            f"{len(nonmed_freq['lemmas'])} lemmas"
        )
        whole_freq = aggregate_dirs([galen_dir, nonmed_dir])
    else:
        print("WARNING: no nonmedical lemmatized data; whole-Galen = medical only.")
        nonmed_freq = {"corpus_total_tokens": 0, "files": 0, "lemmas": {}}
        write_json(outputs / "lemma_frequency_galen_nonmedical.json", nonmed_freq)
        whole_freq = aggregate_dirs([galen_dir])
    write_json(outputs / "lemma_frequency_galen_whole.json", whole_freq)
    print(
        f"Galen (whole): {whole_freq['corpus_total_tokens']} tokens, "
        f"{len(whole_freq['lemmas'])} lemmas (files={whole_freq['files']})"
    )

    ref_dir = lemmatized / "reference"
    if ref_dir.exists() and any(ref_dir.glob("*.jsonl")):
        ref_freq = aggregate_dir(ref_dir)
        write_json(outputs / "lemma_frequency_reference.json", ref_freq)
        print(
            f"Reference: {ref_freq['corpus_total_tokens']} tokens, "
            f"{len(ref_freq['lemmas'])} lemmas"
        )
    else:
        print("WARNING: no reference lemmatized data; writing empty reference frequency file.")
        write_json(
            outputs / "lemma_frequency_reference.json",
            {"corpus_total_tokens": 0, "lemmas": {}},
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
