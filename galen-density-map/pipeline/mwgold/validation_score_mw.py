"""MW-Gold, stage 4b — score the blind readers of a validation sheet (gate, relocation precision, κ) and publish the key.

Same arithmetic as lsjgold/validation_score.py (Wilson 95%, Cohen's κ on the 60 random rows between the first two
readers named), with the MW-Gold key columns (text, abbrev, locus, span, validation route).

Run: python -X utf8 -I pipeline/mwgold/validation_score_mw.py --out data/qc/mwgold/validation_final --key <private key>
       --reader opus --answers .../answers_reader_opus.csv --reader sonnet --answers .../answers_reader_sonnet.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lsjgold"))
from validation_score import wilson, rate, norm, kappa  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--reader", action="append", required=True)
    ap.add_argument("--answers", action="append", required=True)
    a = ap.parse_args()
    key = {r["row_id"]: r for r in csv.DictReader(a.key.open(encoding="utf-8"))}
    meta = json.load((a.out / "sheet_meta.json").open(encoding="utf-8"))
    readers = {}
    for name, path in zip(a.reader, a.answers):
        readers[name] = {r["row_id"]: {"ans": norm(r.get("is_instance(yes/no/unsure)") or r.get("is_instance") or ""),
                                       "hw": (r.get("right_headword_if_no") or "").strip(), "note": (r.get("note") or "").strip()}
                         for r in csv.DictReader(Path(path).open(encoding="utf-8-sig"))}
    rand = sorted(rid for rid, k in key.items() if k["kind"] == "random")
    res = {"date": datetime.date.today().isoformat(), "seed": meta["seed"], "n_random": len(rand), "readers": {}}
    for name, ans in readers.items():
        g = lambda rid: ans.get(rid, {"ans": "unsure"})  # noqa: E731
        ay = sum(g(r)["ans"] == "yes" for r, k in key.items() if k["kind"] == "anchor")
        pn = sum(g(r)["ans"] == "no" for r, k in key.items() if k["kind"] == "plant")
        c = Counter(g(r)["ans"] for r in rand)
        by_route: dict[str, Counter] = {}
        for r in rand:
            by_route.setdefault(key[r]["validation"], Counter())[g(r)["ans"]] += 1
        res["readers"][name] = {"answered": len(ans),
                                "gate": {"anchors_yes": f"{ay}/{meta['n_anchors']}", "plants_no": f"{pn}/{meta['n_plants']}",
                                         "passed": ay >= meta["gate"]["anchors_min_yes"] and pn >= meta["gate"]["plants_min_no"]},
                                "random": {v: rate(c[v], len(rand)) for v in ("yes", "no", "unsure")},
                                "relocation_precision_excl_unsure": rate(c["yes"], c["yes"] + c["no"]),
                                "random_by_route": {k: dict(v) for k, v in by_route.items()}}
    names = list(readers)
    if len(names) >= 2:
        v1 = [readers[names[0]].get(r, {}).get("ans", "unsure") for r in rand]
        v2 = [readers[names[1]].get(r, {}).get("ans", "unsure") for r in rand]
        both_yes = sum(x == y == "yes" for x, y in zip(v1, v2))
        res["between_readers"] = {"pair": names[:2], "kappa": kappa(v1, v2), "both_yes": both_yes, "both_no": sum(x == y == "no" for x, y in zip(v1, v2)),
                                  "disagree": sum(x != y for x, y in zip(v1, v2)), "both_yes_rate": rate(both_yes, len(rand)),
                                  "rows_both_no": [r for r, x, y in zip(rand, v1, v2) if x == y == "no"],
                                  "rows_disagree": [r for r, x, y in zip(rand, v1, v2) if x != y]}
    rows = []
    for rid, k in sorted(key.items()):
        row = {"row_id": rid, "kind": k["kind"], "expected": k["expected"], "headword_gold": k["headword"], "headword_shown": k.get("shown_headword", ""),
               "surface": k["surface"], "text": k["text"], "abbrev": k["abbrev"], "locus": k["locus"], "token_index": k["token_index"], "span": k["span"],
               "validation": k["validation"], "dcs_lemma": k.get("dcs_lemma", "")}
        for name, ans in readers.items():
            g = ans.get(rid, {})
            row[f"{name}_answer"] = g.get("ans", "")
            row[f"{name}_headword_if_no"] = g.get("hw", "")
            row[f"{name}_note"] = g.get("note", "")
        rows.append(row)
    with (a.out / "validation_verdicts.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    shutil.copy(a.key, a.out / "validation_key_PUBLISHED_AFTER_SCORING.csv")
    (a.out / "validation_summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
