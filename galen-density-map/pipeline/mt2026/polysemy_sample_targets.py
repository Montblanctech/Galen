"""Polysemy probe, stage 1 (spec: mt2026_polysemy_probe_spec.md): draw targets over the 40 existing passages.

Per passage: up to 4 polysemy_risk and up to 4 genuinely_hard NOUN/ADJ tokens (four-way classification),
distinct lemmas within the passage, positions not already 11/05 targets, seed 20261106. Writes
data/qc/mt2026/polysemy/translator_targets.csv (class withheld) and the PRIVATE class key to --key-out.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "mt2026"
OUT = QC / "polysemy"
PER_CLASS_PER_PASSAGE = 4
CLASSES = ("polysemy_risk", "genuinely_hard")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=20261106)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    fw = {r["lemma"]: r["quadrant"] for r in csv.DictReader((GDM / "outputs" / "four_way_classification.csv").open(encoding="utf-8"))}
    old = {(r["passage_id"], int(r["target_no"])) for r in csv.DictReader((QC / "translator_targets.csv").open(encoding="utf-8"))}
    passages = [json.loads(l) for l in (QC / "passages.jsonl").open(encoding="utf-8")]
    targets, key = [], []
    for p in passages:
        toks = [json.loads(l) for l in (GDM / "data" / "lemmatized" / "galen" / f"{p['work_stem']}.jsonl").open(encoding="utf-8")]
        seg = toks[p["start_index"] : p["start_index"] + p["n_tokens"]]
        text_tokens = p["text"].split(" ")
        assert len(text_tokens) == len(seg), p["passage_id"]
        for cls in CLASSES:
            cands = [(j, t) for j, t in enumerate(seg) if t.get("pos") in ("NOUN", "ADJ") and fw.get(t["lemma"]) == cls and (p["passage_id"], j) not in old]
            rng.shuffle(cands)
            seen, picked = set(), []
            for j, t in cands:
                if t["lemma"] in seen:
                    continue
                seen.add(t["lemma"])
                picked.append((j, t))
                if len(picked) == PER_CLASS_PER_PASSAGE:
                    break
            for j, t in picked:
                targets.append({"passage_id": p["passage_id"], "target_no": j, "surface": text_tokens[j]})
                key.append({"passage_id": p["passage_id"], "target_no": j, "surface": text_tokens[j], "lemma": t["lemma"], "pos": t["pos"], "class": cls})
    targets.sort(key=lambda r: (r["passage_id"], r["target_no"]))
    key.sort(key=lambda r: (r["passage_id"], r["target_no"]))
    with (OUT / "translator_targets.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["passage_id", "target_no", "surface"])
        w.writeheader()
        w.writerows(targets)
    a.key_out.parent.mkdir(parents=True, exist_ok=True)
    with a.key_out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(key[0].keys()))
        w.writeheader()
        w.writerows(key)
    meta = {"date": "2026-11-06", "spec": "mt2026_polysemy_probe_spec.md", "seed": a.seed, "n_passages": len(passages), "n_targets": len(targets),
            "per_class": dict(Counter(k["class"] for k in key)), "distinct_lemmas_per_class": {c: len({k["lemma"] for k in key if k["class"] == c}) for c in CLASSES},
            "translators": ["fable-5-1", "opus-5-5", "sonnet-5-5"], "runs_per_translator": 2, "key": "PRIVATE until scored"}
    (OUT / "sample_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
