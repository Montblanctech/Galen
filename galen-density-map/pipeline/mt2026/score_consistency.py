"""MT-2026 consistency probe — stage 3: score two blind translators' term renderings.

Usage: python score_consistency.py --key-dir <dir with mt2026_target_classes.csv>
Reads data/qc/mt2026/renderings_<model>.csv for the two translators, joins the class key,
normalises renderings IDENTICALLY for both classes, and writes:
  mt2026_summary.json, term_disagreements.csv, passage_table.csv, mt2026_result.md
and copies the class key next to the results (published with them).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MT = ROOT / "data" / "qc" / "mt2026"
TRANSLATORS = {"fable-5-1": MT / "renderings_fable-5-1.csv", "opus-5-5": MT / "renderings_opus-5-5.csv"}

STOP = {"the", "a", "an", "of", "and", "or", "to", "its", "their", "his", "her", "this", "that", "these", "those",
        "some", "any", "one", "ones", "which", "what", "is", "are", "be", "being", "by", "in", "on", "with", "for"}
# Small, symmetric synonym fold applied to both classes alike (documented; extend only here).
FOLD = {
    "mixtures": "mixture", "temperaments": "temperament", "temperament": "mixture", "krasis": "mixture", "crasis": "mixture",
    "blend": "mixture", "blending": "mixture", "constitution": "mixture",
    "drugs": "drug", "medicine": "drug", "medicines": "drug", "medicament": "drug", "medicaments": "drug", "remedy": "drug", "remedies": "drug",
    "plasters": "plaster", "emplastrum": "plaster", "emplaster": "plaster", "salve": "plaster",
    "humours": "humour", "humors": "humour", "humor": "humour",
    "faculties": "faculty", "power": "faculty", "powers": "faculty", "capacity": "faculty", "capacities": "faculty", "potency": "faculty",
    "qualities": "quality", "bodies": "body", "parts": "part", "animals": "animal", "living": "animal", "creature": "animal", "creatures": "animal",
    "dry": "dry", "dryness": "dry", "moist": "wet", "moisture": "wet", "wetness": "wet", "humid": "wet", "hot": "hot", "heat": "hot", "warm": "hot", "warmth": "hot",
    "cold": "cold", "coldness": "cold", "cool": "cold", "chill": "cold",
    "substances": "substance", "ingredients": "ingredient", "ingredient": "substance",
    "wounds": "wound", "ulcers": "ulcer", "sores": "ulcer", "sore": "ulcer",
    "drachms": "drachma", "drachmas": "drachma", "drachm": "drachma", "drams": "drachma", "dram": "drachma",
    "minae": "mina", "minas": "mina", "ounces": "ounce", "litrai": "litra", "pounds": "pound",
    "wax": "wax", "cerate": "cerate", "cerates": "cerate",
    "styptic": "astringent", "binding": "astringent", "astringents": "astringent",
}


def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z\s\-]", " ", s)
    toks = [t for t in re.split(r"[\s\-]+", s) if t and t not in STOP]
    out = []
    for t in toks:
        t = FOLD.get(t, t)
        # crude singularisation, applied to both classes alike
        if t.endswith("ies") and len(t) > 4:
            t = t[:-3] + "y"
        elif t.endswith("es") and len(t) > 4 and t[-3] in "sxz":
            t = t[:-2]
        elif t.endswith("s") and not t.endswith("ss") and len(t) > 3:
            t = t[:-1]
        t = FOLD.get(t, t)
        out.append(t)
    return " ".join(sorted(set(out)))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 2), round(100 * (c + h), 2))


def two_prop_z(k1: int, n1: int, k2: int, n2: int) -> dict:
    if min(n1, n2) == 0:
        return {}
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0.0
    z = (p1 - p2) / se if se else 0.0
    # two-sided p via erfc
    pval = math.erfc(abs(z) / math.sqrt(2))
    se_diff = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {"diff_pct_points": round(100 * (p1 - p2), 2), "z": round(z, 3), "p_two_sided": round(pval, 5),
            "ci95_diff_pct_points": [round(100 * ((p1 - p2) - 1.96 * se_diff), 2), round(100 * ((p1 - p2) + 1.96 * se_diff), 2)]}


def spearman(x: list[float], y: list[float]) -> dict:
    n = len(x)
    if n < 3:
        return {"n": n}
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    rho = num / den if den else 0.0
    # Fisher z CI
    if abs(rho) < 1:
        fz = 0.5 * math.log((1 + rho) / (1 - rho))
        se = 1.06 / math.sqrt(n - 3)
        lo, hi = math.tanh(fz - 1.96 * se), math.tanh(fz + 1.96 * se)
    else:
        lo = hi = rho
    return {"n": n, "rho": round(rho, 3), "ci95": [round(lo, 3), round(hi, 3)]}


def load(p: Path) -> dict[tuple[str, int], dict]:
    out = {}
    with p.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            r = {k.strip(): (v or "").strip() for k, v in r.items()}
            out[(r["passage_id"], int(r["target_no"]))] = r
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-dir", required=True)
    a = ap.parse_args()
    key_dir = Path(a.key_dir)
    key = list(csv.DictReader((key_dir / "mt2026_target_classes.csv").open(encoding="utf-8")))
    passages = {json.loads(l)["passage_id"]: json.loads(l) for l in (MT / "passages.jsonl").open(encoding="utf-8")}
    names = [n for n, p in TRANSLATORS.items() if p.exists()]
    if len(names) < 2:
        print("need both translator files; have:", names)
        return
    t1, t2 = load(TRANSLATORS[names[0]]), load(TRANSLATORS[names[1]])

    rows = []
    cls_counts = defaultdict(lambda: {"n": 0, "disagree": 0, "unc1": 0, "unc2": 0, "missing": 0})
    per_passage = defaultdict(lambda: {"punch_n": 0, "punch_dis": 0, "ctrl_n": 0, "ctrl_dis": 0, "all_n": 0, "all_dis": 0})
    lemma_renderings = {n: defaultdict(lambda: defaultdict(set)) for n in names}
    for k in key:
        pid, tn, cls = k["passage_id"], int(k["target_no"]), k["class"]
        r1, r2 = t1.get((pid, tn)), t2.get((pid, tn))
        c = cls_counts[cls]
        c["n"] += 1
        if not r1 or not r2:
            c["missing"] += 1
            rows.append({**k, names[0]: r1.get("rendering", "") if r1 else "", names[1]: r2.get("rendering", "") if r2 else "",
                         "norm1": "", "norm2": "", "verdict": "missing"})
            continue
        n1, n2 = norm(r1["rendering"]), norm(r2["rendering"])
        dis = int(n1 != n2)
        c["disagree"] += dis
        c["unc1"] += int(r1.get("uncertain", "").lower() == "y")
        c["unc2"] += int(r2.get("uncertain", "").lower() == "y")
        pp = per_passage[pid]
        pp["all_n"] += 1; pp["all_dis"] += dis
        if cls == "punch":
            pp["punch_n"] += 1; pp["punch_dis"] += dis
        else:
            pp["ctrl_n"] += 1; pp["ctrl_dis"] += dis
        lemma_renderings[names[0]][cls][k["lemma"]].add(n1)
        lemma_renderings[names[1]][cls][k["lemma"]].add(n2)
        rows.append({**k, names[0]: r1["rendering"], names[1]: r2["rendering"], "norm1": n1, "norm2": n2,
                     "verdict": "disagree" if dis else "agree",
                     f"uncertain_{names[0]}": r1.get("uncertain", ""), f"uncertain_{names[1]}": r2.get("uncertain", "")})

    p, q = cls_counts["punch"], cls_counts["control"]
    summary: dict = {"date": "2026-11-05", "design": "mt2026_consistency_probe_spec.md", "translators": names,
                     "normalisation": "lowercase, strip parentheticals/punctuation, drop function words, symmetric synonym fold (FOLD in score_consistency.py), crude singularisation; identical for both classes",
                     "classes": {}}
    for cls, c in cls_counts.items():
        scored = c["n"] - c["missing"]
        summary["classes"][cls] = {"targets": c["n"], "scored": scored, "disagree": c["disagree"],
                                   "disagreement_rate_pct": round(100 * c["disagree"] / scored, 2) if scored else None,
                                   "wilson95": wilson(c["disagree"], scored),
                                   f"uncertain_rate_{names[0]}_pct": round(100 * c["unc1"] / scored, 2) if scored else None,
                                   f"uncertain_rate_{names[1]}_pct": round(100 * c["unc2"] / scored, 2) if scored else None,
                                   "missing": c["missing"]}
    # punch split by LSJ tier (thin = has an LSJ entry; absent = no LSJ headword, where lemmatizer artifacts concentrate)
    tiers = defaultdict(lambda: {"n": 0, "disagree": 0})
    for r in rows:
        if r["class"] == "punch" and r["verdict"] in ("agree", "disagree"):
            t = tiers[r.get("lsj_tier") or "-"]
            t["n"] += 1; t["disagree"] += int(r["verdict"] == "disagree")
    summary["punch_by_lsj_tier"] = {k: {"scored": v["n"], "disagree": v["disagree"],
                                        "disagreement_rate_pct": round(100 * v["disagree"] / v["n"], 2) if v["n"] else None,
                                        "wilson95": wilson(v["disagree"], v["n"])} for k, v in tiers.items()}
    if "thin" in tiers and cls_counts["control"]["n"]:
        summary["thin_vs_control"] = two_prop_z(tiers["thin"]["disagree"], tiers["thin"]["n"], q["disagree"], q["n"] - q["missing"])
    summary["punch_vs_control"] = two_prop_z(p["disagree"], p["n"] - p["missing"], q["disagree"], q["n"] - q["missing"])

    # paired per-passage comparison (passages with both classes present)
    paired = [(pp["punch_dis"] / pp["punch_n"], pp["ctrl_dis"] / pp["ctrl_n"]) for pp in per_passage.values() if pp["punch_n"] and pp["ctrl_n"]]
    if paired:
        diffs = [a - b for a, b in paired]
        summary["paired_passages"] = {"n": len(paired), "mean_diff_pct_points": round(100 * sum(diffs) / len(diffs), 2),
                                      "passages_punch_worse": sum(1 for d in diffs if d > 0), "passages_control_worse": sum(1 for d in diffs if d < 0),
                                      "ties": sum(1 for d in diffs if d == 0)}
    # passage-level density correlation
    xs, ys, ptab = [], [], []
    for pid, pp in per_passage.items():
        P = passages[pid]
        rate = pp["all_dis"] / pp["all_n"] if pp["all_n"] else None
        ptab.append({"passage_id": pid, "work": P["work"], "density_tier": P["density_tier"], "punch_density_per100": P["punch_density_per100"],
                     "targets_scored": pp["all_n"], "disagreements": pp["all_dis"], "disagreement_rate_pct": round(100 * rate, 2) if rate is not None else "",
                     "punch_rate_pct": round(100 * pp["punch_dis"] / pp["punch_n"], 2) if pp["punch_n"] else "",
                     "control_rate_pct": round(100 * pp["ctrl_dis"] / pp["ctrl_n"], 2) if pp["ctrl_n"] else ""})
        if rate is not None:
            xs.append(P["punch_density_per100"]); ys.append(rate)
    summary["passage_level_spearman_density_vs_disagreement"] = spearman(xs, ys)
    for work in ("temp", "cmpg"):
        xw = [x for x, pid in zip(xs, [t["passage_id"] for t in ptab if t["targets_scored"]]) if passages[pid]["work"] == work]
        yw = [y for y, pid in zip(ys, [t["passage_id"] for t in ptab if t["targets_scored"]]) if passages[pid]["work"] == work]
        summary[f"spearman_{work}"] = spearman(xw, yw)
    # within-translator consistency on repeated lemmas
    wt = {}
    for n in names:
        for cls in ("punch", "control"):
            multi = {l: s for l, s in lemma_renderings[n][cls].items() if len([1 for k in key if k["lemma"] == l and k["class"] == cls]) >= 2}
            inconsistent = sum(1 for s in multi.values() if len(s) > 1)
            wt[f"{n}_{cls}"] = {"lemmas_seen_2plus": len(multi), "rendered_inconsistently": inconsistent,
                                "rate_pct": round(100 * inconsistent / len(multi), 2) if multi else None}
    summary["within_translator_consistency"] = wt

    with (MT / "term_disagreements.csv").open("w", encoding="utf-8", newline="") as fh:
        fields = sorted({k for r in rows for k in r})
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)
    with (MT / "passage_table.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ptab[0].keys())); w.writeheader(); w.writerows(ptab)
    shutil.copy(key_dir / "mt2026_target_classes.csv", MT / "mt2026_target_classes.csv")
    (MT / "mt2026_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    sp, sc = summary["classes"].get("punch", {}), summary["classes"].get("control", {})
    pv = summary["punch_vs_control"]
    rho = summary["passage_level_spearman_density_vs_disagreement"]
    res = (f"Two frontier models ({names[0]}, {names[1]}) translated the same 40 passages blind. On punch-list targets the two renderings "
           f"disagreed in {sp.get('disagreement_rate_pct')}% of cases (n={sp.get('scored')}, Wilson 95% {sp.get('wilson95')}) against "
           f"{sc.get('disagreement_rate_pct')}% on matched control targets (n={sc.get('scored')}, {sc.get('wilson95')}): a difference of "
           f"{pv.get('diff_pct_points')} points (95% CI {pv.get('ci95_diff_pct_points')}, two-proportion z = {pv.get('z')}, p = {pv.get('p_two_sided')}). "
           f"At passage level, punch-list density and disagreement rate correlate at Spearman ρ = {rho.get('rho')} (95% CI {rho.get('ci95')}, n={rho.get('n')}). "
           f"Disagreement is not error, and the two models share a lineage, so agreement is optimistic; the headline is the difference between classes, not either rate.")
    (MT / "mt2026_result.md").write_text("# MT-2026 result (numbers only; architect writes the prose)\n\n" + res + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n" + res)


if __name__ == "__main__":
    main()
