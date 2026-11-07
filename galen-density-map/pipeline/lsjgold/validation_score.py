"""LSJ-Gold, stage 5 — score the validation readers (gate, precision of the relocation, kappa) and publish the key."""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
OUT = GDM / "data" / "qc" / "lsjgold" / "validation"


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 2), round(100 * (c + h), 2)]


def rate(k, n):
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson95": wilson(k, n) if n else None}


def norm(v: str) -> str:
    v = (v or "").strip().lower()
    return "yes" if v.startswith("y") else ("no" if v.startswith("n") else "unsure")


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[v] * cb[v] for v in set(a) | set(b)) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else float("nan")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, type=Path)
    ap.add_argument("--reader", action="append", required=True)
    ap.add_argument("--answers", action="append", required=True)
    a = ap.parse_args()
    key = {r["row_id"]: r for r in csv.DictReader(a.key.open(encoding="utf-8"))}
    meta = json.load((OUT / "sheet_meta.json").open(encoding="utf-8"))
    readers = {}
    for name, path in zip(a.reader, a.answers):
        readers[name] = {r["row_id"]: {"ans": norm(r.get("is_instance(yes/no/unsure)") or r.get("is_instance") or r.get("answer", "")),
                                       "hw": (r.get("right_headword_if_no") or "").strip(), "note": r.get("note", "")}
                         for r in csv.DictReader(Path(path).open(encoding="utf-8-sig"))}
    res = {"date": "2026-11-07", "n_random": meta["n_random"], "readers": {}}
    rand = [rid for rid, k in key.items() if k["kind"] == "random"]
    for name, ans in readers.items():
        g = lambda rid: ans.get(rid, {"ans": "unsure", "hw": "", "note": ""})  # noqa: E731
        anchors_yes = sum(g(r)["ans"] == "yes" for r, k in key.items() if k["kind"] == "anchor")
        plants_no = sum(g(r)["ans"] == "no" for r, k in key.items() if k["kind"] == "plant")
        c = Counter(g(r)["ans"] for r in rand)
        res["readers"][name] = {"gate": {"anchors_yes": f"{anchors_yes}/{meta['n_anchors']}", "plants_no": f"{plants_no}/{meta['n_plants']}",
                                         "passed": anchors_yes >= meta["gate"]["anchors_min_yes"] and plants_no >= meta["gate"]["plants_min_no"]},
                                "random": {v: rate(c[v], len(rand)) for v in ("yes", "no", "unsure")},
                                "relocation_precision_excl_unsure": rate(c["yes"], c["yes"] + c["no"])}
    if len(readers) >= 2:
        n1, n2 = list(readers)[:2]
        v1 = [readers[n1].get(r, {}).get("ans", "unsure") for r in rand]
        v2 = [readers[n2].get(r, {}).get("ans", "unsure") for r in rand]
        res["between_readers"] = {"kappa": kappa(v1, v2), "both_yes": sum(x == y == "yes" for x, y in zip(v1, v2)),
                                  "both_no": sum(x == y == "no" for x, y in zip(v1, v2)), "disagree": sum(x != y for x, y in zip(v1, v2))}
    rows = []
    for rid, k in sorted(key.items()):
        row = {"row_id": rid, "kind": k["kind"], "expected": k["expected"], "headword_gold": k["headword"], "headword_shown": k.get("shown_headword", k["headword"]),
               "surface": k["surface"], "author": k["author"], "work": k["work"], "token_index": k["token_index"], "validation": k["validation"]}
        for name, ans in readers.items():
            g = ans.get(rid, {})
            row[f"{name}_answer"] = g.get("ans", "")
            row[f"{name}_headword_if_no"] = g.get("hw", "")
            row[f"{name}_note"] = g.get("note", "")
        rows.append(row)
    with (OUT / "validation_verdicts.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    shutil.copy(a.key, OUT / "validation_key_PUBLISHED_AFTER_SCORING.csv")
    (OUT / "validation_summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
