#!/usr/bin/env python3
"""Re-lemmatize works that previously produced empty/near-empty JSONL."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from importlib import import_module

lem = import_module("03_lemmatize")
from lib.config import load_config, resolve_path
from lib.io_utils import write_jsonl


def main() -> int:
    cfg = load_config()
    nlp = lem.get_nlp()
    extracted = resolve_path(cfg, "extracted_text")
    galen_out = resolve_path(cfg, "lemmatized") / "galen"
    fail_log_path = resolve_path(cfg, "lemmatized") / "_lemmatize_failures_retry.log"

    targets = []
    for jsonl in sorted(galen_out.glob("*.jsonl")):
        if jsonl.stat().st_size < 100:
            targets.append(jsonl.stem)
        else:
            # also retry known OOM giants if token count looks truncated vs extract
            txt = extracted / f"{jsonl.stem}.txt"
            if not txt.exists():
                continue
            words = len(txt.read_text(encoding="utf-8").split())
            # crude: if lemmatized tokens < 20% of whitespace words, retry
            n_lines = sum(1 for _ in jsonl.open(encoding="utf-8"))
            if words > 5000 and n_lines < 0.2 * words:
                targets.append(jsonl.stem)

    targets = sorted(set(targets))
    print(f"Retrying {len(targets)} works with 12k-char chunks")
    with fail_log_path.open("w", encoding="utf-8") as fail_log:
        for stem in targets:
            txt_path = extracted / f"{stem}.txt"
            text = txt_path.read_text(encoding="utf-8")
            rows = lem.lemmatize_text(nlp, text, fail_log, stem, max_chars=12_000)
            out = galen_out / f"{stem}.jsonl"
            write_jsonl(out, rows)
            print(f"  {stem}: {len(rows)} tokens (was retry)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
