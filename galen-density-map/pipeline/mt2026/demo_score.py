"""Constrained-terminology demonstration, stage 4: score (spec: mt2026_constrained_terminology_spec.md).

Inputs: data/qc/mt2026/constrained/ renderings_{C0,C1}_{translator}.csv and translation_*.jsonl,
terminology.csv, the 11/05 renderings (../renderings_<translator>.csv) and class table
(../term_disagreements.csv), judge answer CSVs (--judge NAME=path, repeatable) and the private A/B key.

Reports (constrained_summary.json + constrained_result.md, all with Wilson 95%):
 1 compliance: ten-term targets rendered with the preferred rendering in C1, per translator;
 2 spillover: cross-translator disagreement on the OTHER targets, C0 vs C1 (two-proportion z);
 3 run-to-run: each translator's C0 vs its own 11/05 renderings, all targets of the subset;
 4 judges: P(C1 preferred) per judge, ties, per translator; agreement between judges.
Un-blinds the key into judge_verdicts.csv and copies it beside the results. Report only.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_consistency import norm, two_prop_z, wilson  # noqa: E402

QC = HERE.parent.parent / "data" / "qc" / "mt2026"
OUT = QC / "constrained"
TRANSLATORS = ["fable-5-1", "opus-5-5"]


def read(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig") as fh:
        return [{k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh)]


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n) if n else (float("nan"), float("nan"))  # score_consistency.wilson returns percent
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson95": [round(lo, 2), round(hi, 2)] if n else None}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, type=Path, help="private A/B key from demo_judge_pairs.py")
    ap.add_argument("--judge", action="append", default=[], help="NAME=path to a judge answer CSV (repeatable)")
    a = ap.parse_args()

    terms = read(OUT / "terminology.csv")
    pref = {t["lemma"]: norm(t["preferred_rendering_lsj_first_gloss"]) for t in terms}
    term_set = set(pref)
    classes = {(r["passage_id"], r["target_no"]): r for r in read(QC / "term_disagreements.csv")}
    targets = read(OUT / "translator_targets.csv")
    tkeys = [(r["passage_id"], r["target_no"]) for r in targets]
    is_term = {k: classes.get(k, {}).get("lemma", "") in term_set for k in tkeys}

    rend = {}
    for tr in TRANSLATORS:
        for c in ("C0", "C1"):
            p = OUT / f"renderings_{c}_{tr}.csv"
            rend[(c, tr)] = {(r["passage_id"], r["target_no"]): r for r in read(p)} if p.exists() else {}
        rend[("1105", tr)] = {(r["passage_id"], r["target_no"]): r for r in read(QC / f"renderings_{tr}.csv")}

    summary: dict = {"date": "2026-11-06", "spec": "mt2026_constrained_terminology_spec.md", "n_targets": len(tkeys),
                     "n_term_targets": sum(is_term.values()), "n_other_targets": sum(not v for v in is_term.values())}

    # 1 compliance
    comp = {}
    for tr in TRANSLATORS:
        k = n = 0
        detail = []
        for key in tkeys:
            if not is_term[key] or key not in rend[("C1", tr)]:
                continue
            lemma = classes[key]["lemma"]
            r = norm(rend[("C1", tr)][key]["rendering"])
            ok = bool(r) and (r == pref[lemma] or set(r.split()) <= set(pref[lemma].split()) or set(pref[lemma].split()) <= set(r.split()))
            n += 1
            k += ok
            detail.append({"passage_id": key[0], "target_no": key[1], "lemma": lemma, "rendering": rend[("C1", tr)][key]["rendering"],
                           "preferred": pref[lemma], "compliant": ok})
        comp[tr] = {**rate(k, n), "detail": detail}
    summary["compliance_C1"] = comp

    # 2 spillover and term disagreement by condition
    def cross(c: str, which: str) -> dict:
        k = n = 0
        for key in tkeys:
            if (which == "term") != is_term[key]:
                continue
            a1, a2 = rend[(c, TRANSLATORS[0])].get(key), rend[(c, TRANSLATORS[1])].get(key)
            if not a1 or not a2:
                continue
            n += 1
            k += norm(a1["rendering"]) != norm(a2["rendering"])
        return rate(k, n)

    sp = {c: {"term_targets": cross(c, "term"), "other_targets": cross(c, "other")} for c in ("C0", "C1")}
    sp["1105"] = {"term_targets": cross("1105", "term"), "other_targets": cross("1105", "other")}
    o0, o1 = sp["C0"]["other_targets"], sp["C1"]["other_targets"]
    sp["other_targets_C0_vs_C1"] = two_prop_z(o0["k"], o0["n"], o1["k"], o1["n"]) if o0["n"] and o1["n"] else None
    summary["cross_translator_disagreement"] = sp

    # 3 run-to-run
    r2r = {}
    for tr in TRANSLATORS:
        k = n = kt = nt = 0
        for key in tkeys:
            a1, a2 = rend[("C0", tr)].get(key), rend[("1105", tr)].get(key)
            if not a1 or not a2:
                continue
            d = norm(a1["rendering"]) != norm(a2["rendering"])
            if is_term[key]:
                nt += 1
                kt += d
            else:
                n += 1
                k += d
        r2r[tr] = {"other_targets": rate(k, n), "term_targets": rate(kt, nt)}
    summary["run_to_run_C0_vs_1105"] = r2r

    # 4 judges
    key_rows = {r["pair_id"]: r for r in read(a.key)}
    judges = {}
    verdict_rows = []
    jmaps = {}
    for spec in a.judge:
        name, path = spec.split("=", 1)
        ans = {r["pair_id"]: r for r in read(Path(path))}
        jmaps[name] = ans
        k = n = ties = 0
        by_tr = {tr: Counter() for tr in TRANSLATORS}
        for pid, kr in key_rows.items():
            r = ans.get(pid)
            if not r:
                continue
            p = r["preference"].strip().upper()[:1]
            n += 1
            if p == "T":
                ties += 1
                by_tr[kr["translator"]]["tie"] += 1
                continue
            chosen = kr["A_is"] if p == "A" else kr["B_is"]
            k += chosen == "C1"
            by_tr[kr["translator"]][chosen] += 1
        judges[name] = {"answered": n, "ties": ties, "C1_preferred_of_decided": rate(k, n - ties), "C1_preferred_of_all": rate(k, n),
                        "by_translator": {tr: dict(c) for tr, c in by_tr.items()}}
    if len(jmaps) >= 2:
        n1, n2 = list(jmaps)[:2]
        both = [pid for pid in key_rows if pid in jmaps[n1] and pid in jmaps[n2]]
        agree = sum(jmaps[n1][p]["preference"].strip().upper()[:1] == jmaps[n2][p]["preference"].strip().upper()[:1] for p in both)
        judges["between_judges_raw_agreement"] = rate(agree, len(both))
    summary["judges"] = judges
    for pid, kr in key_rows.items():
        row = dict(kr)
        for name, ans in jmaps.items():
            r = ans.get(pid, {})
            p = r.get("preference", "").strip().upper()[:1]
            row[f"{name}_pref"] = p
            row[f"{name}_chosen"] = "tie" if p == "T" else (kr["A_is"] if p == "A" else (kr["B_is"] if p == "B" else ""))
            row[f"{name}_confidence"] = r.get("confidence", "")
            row[f"{name}_note"] = r.get("note", "")
        verdict_rows.append(row)
    if verdict_rows:
        with (OUT / "judge_verdicts.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(verdict_rows[0].keys()))
            w.writeheader()
            w.writerows(verdict_rows)
        shutil.copy(a.key, OUT / "judge_key_PUBLISHED_AFTER_SCORING.csv")
    (OUT / "constrained_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str)[:6000])


if __name__ == "__main__":
    main()
