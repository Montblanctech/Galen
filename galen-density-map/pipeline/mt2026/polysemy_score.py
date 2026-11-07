"""Polysemy probe, stage 3: score (spec: mt2026_polysemy_probe_spec.md).

Inputs: data/qc/mt2026/polysemy/renderings_<translator>_<run>.csv for translators fable-5-1, opus-5-5,
sonnet-5-5 and runs A, B; the private class key (--key). Writes polysemy_summary.json,
polysemy_targets_scored.csv (un-blinded, every rendering) and copies the key beside them.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_consistency import norm, two_prop_z, wilson  # noqa: E402

OUT = HERE.parent.parent / "data" / "qc" / "mt2026" / "polysemy"
TR = ["fable-5-1", "opus-5-5", "sonnet-5-5"]
RUNS = ["A", "B"]
CLASSES = ("polysemy_risk", "genuinely_hard")


def read(p: Path) -> dict[tuple[str, str], dict]:
    out = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            r = {k.strip(): (v or "").strip() for k, v in r.items()}
            out[(r["passage_id"], r["target_no"])] = r
    return out


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n) if n else (0.0, 0.0)
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson95": [lo, hi] if n else None}


def diff(r1: dict, r2: dict) -> dict | None:
    return two_prop_z(r1["k"], r1["n"], r2["k"], r2["n"]) if r1["n"] and r2["n"] else None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, type=Path)
    a = ap.parse_args()
    key = read(a.key)
    rend = {(t, r): read(OUT / f"renderings_{t}_{r}.csv") for t in TR for r in RUNS}
    present = [(t, r) for (t, r), v in rend.items() if v]
    summary: dict = {"date": "2026-11-06", "spec": "mt2026_polysemy_probe_spec.md", "runs_present": [f"{t}_{r}" for t, r in present],
                     "n_targets": len(key), "per_class": dict(Counter(k["class"] for k in key.values()))}

    def cls_rate(fn, cls):
        k = n = 0
        for tk, kr in key.items():
            if kr["class"] != cls:
                continue
            v = fn(tk)
            if v is None:
                continue
            n += 1
            k += v
        return rate(k, n)

    # 1 within-model
    within = {}
    for t in TR:
        A, B = rend[(t, "A")], rend[(t, "B")]
        if not A or not B:
            continue
        f = lambda tk: (norm(A[tk]["rendering"]) != norm(B[tk]["rendering"])) if tk in A and tk in B else None  # noqa: E731
        within[t] = {c: cls_rate(f, c) for c in CLASSES}
        within[t]["difference_polysemy_minus_hard"] = diff(within[t]["polysemy_risk"], within[t]["genuinely_hard"])
    summary["within_model_run_to_run"] = within
    # pooled within-model
    def pooled_within(tk):
        vals = []
        for t in TR:
            A, B = rend[(t, "A")], rend[(t, "B")]
            if tk in A and tk in B:
                vals.append(norm(A[tk]["rendering"]) != norm(B[tk]["rendering"]))
        return (sum(vals) / len(vals) >= 0.5) if vals else None  # majority of models unstable on this token
    # 2 cross-model (run A)
    cross = {}
    for t1, t2 in combinations(TR, 2):
        A1, A2 = rend[(t1, "A")], rend[(t2, "A")]
        if not A1 or not A2:
            continue
        f = lambda tk, A1=A1, A2=A2: (norm(A1[tk]["rendering"]) != norm(A2[tk]["rendering"])) if tk in A1 and tk in A2 else None  # noqa: E731
        cross[f"{t1}__{t2}"] = {c: cls_rate(f, c) for c in CLASSES}
        cross[f"{t1}__{t2}"]["difference_polysemy_minus_hard"] = diff(cross[f"{t1}__{t2}"]["polysemy_risk"], cross[f"{t1}__{t2}"]["genuinely_hard"])
    runsA = [rend[(t, "A")] for t in TR if rend[(t, "A")]]
    if len(runsA) == 3:
        f = lambda tk: (len({norm(R[tk]["rendering"]) for R in runsA}) > 1) if all(tk in R for R in runsA) else None  # noqa: E731
        cross["any_of_three_differs"] = {c: cls_rate(f, c) for c in CLASSES}
        cross["any_of_three_differs"]["difference_polysemy_minus_hard"] = diff(cross["any_of_three_differs"]["polysemy_risk"], cross["any_of_three_differs"]["genuinely_hard"])
    summary["cross_model_runA"] = cross
    # 3 uncertainty
    unc = {}
    for (t, r), R in rend.items():
        if not R:
            continue
        f = lambda tk, R=R: (R[tk].get("uncertain", "").lower().startswith("y")) if tk in R else None  # noqa: E731
        unc[f"{t}_{r}"] = {c: cls_rate(f, c) for c in CLASSES}
    summary["self_flagged_uncertain"] = unc
    # 4 per-lemma within-run consistency (lemma in >=2 passages)
    per_lemma = {}
    for (t, r), R in rend.items():
        if not R:
            continue
        by = defaultdict(list)
        for tk, kr in key.items():
            if tk in R:
                by[(kr["class"], kr["lemma"])].append(norm(R[tk]["rendering"]))
        res = {}
        for c in CLASSES:
            multi = [v for (cc, l), v in by.items() if cc == c and len(v) >= 2]
            inconsistent = sum(len(set(v)) > 1 for v in multi)
            res[c] = rate(inconsistent, len(multi))
        per_lemma[f"{t}_{r}"] = res
    summary["per_lemma_inconsistency_within_run"] = per_lemma

    cols = ["passage_id", "target_no", "surface", "lemma", "pos", "class"] + [f"{t}_{r}" for t in TR for r in RUNS]
    with (OUT / "polysemy_targets_scored.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for tk, kr in sorted(key.items()):
            row = dict(kr)
            for t in TR:
                for r in RUNS:
                    row[f"{t}_{r}"] = rend[(t, r)].get(tk, {}).get("rendering", "")
            w.writerow(row)
    shutil.copy(a.key, OUT / "polysemy_class_key_PUBLISHED_AFTER_SCORING.csv")
    (OUT / "polysemy_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("runs_present", "per_class", "within_model_run_to_run", "cross_model_runA")}, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
