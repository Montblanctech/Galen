"""Constrained-terminology demonstration, stage 3: build blind judge packets.

For every (passage, translator) with both conditions translated, write one pair: the Greek passage,
translation A and translation B in random order (seed 20261106), condition hidden. Judges answer
preference in {A, B, tie} and may name wrongly rendered terms. The A/B key goes to --key-out
(outside the repo until demo_score.py has scored).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "data" / "qc" / "mt2026" / "constrained"
TRANSLATORS = ["fable-5-1", "opus-5-5"]


def load_jsonl(p: Path) -> dict[str, str]:
    out = {}
    for line in p.open(encoding="utf-8"):
        line = line.strip()
        if line:
            o = json.loads(line)
            out[o["passage_id"]] = o["translation"]
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=20261106)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    passages = {json.loads(l)["passage_id"]: json.loads(l) for l in (OUT / "passages.jsonl").open(encoding="utf-8")}
    pairs, key = [], []
    for tr in TRANSLATORS:
        c0 = load_jsonl(OUT / f"translation_C0_{tr}.jsonl")
        c1 = load_jsonl(OUT / f"translation_C1_{tr}.jsonl")
        for pid in sorted(passages):
            if pid not in c0 or pid not in c1:
                continue
            flip = rng.random() < 0.5
            A, B = (c1[pid], c0[pid]) if flip else (c0[pid], c1[pid])
            pair_id = f"P{len(pairs)+1:03d}"
            pairs.append({"pair_id": pair_id, "passage_id": pid, "greek": passages[pid]["text"], "translation_A": A, "translation_B": B})
            key.append({"pair_id": pair_id, "passage_id": pid, "translator": tr, "A_is": "C1" if flip else "C0", "B_is": "C0" if flip else "C1"})
    rng.shuffle(pairs)
    order = {p["pair_id"]: n for n, p in enumerate(pairs)}
    key.sort(key=lambda k: order[k["pair_id"]])
    with (OUT / "judge_pairs.jsonl").open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    a.key_out.parent.mkdir(parents=True, exist_ok=True)
    with a.key_out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(key[0].keys()))
        w.writeheader()
        w.writerows(key)
    (OUT / "judge_instructions.txt").write_text(
        "JUDGE INSTRUCTIONS (blind paired comparison)\n\n"
        "Each pair has a Greek passage from Galen (tokenised stream, no punctuation) and two English translations A and B "
        "of it. Decide which translation renders Galen's technical content (humoral, anatomical, pharmacological terms, "
        "quantities, procedures) more precisely and faithfully to the Greek. Style and fluency do not count unless they "
        "change the sense. Answer per pair: preference in {A, B, tie}; confidence in {high, medium, low}; a short note "
        "naming any term you think either translation renders wrongly (write the Greek word and the English used). "
        "Use only the pair file and your own knowledge of Greek: no lemmatizer, no web, no other files. Answer every pair.\n"
        f"Output: UTF-8 CSV with header pair_id,preference,confidence,note; {len(pairs)} rows.\n", encoding="utf-8")
    print(json.dumps({"n_pairs": len(pairs), "per_translator": {tr: sum(k["translator"] == tr for k in key) for tr in TRANSLATORS},
                      "key": "PRIVATE until scored"}, indent=2))


if __name__ == "__main__":
    main()
