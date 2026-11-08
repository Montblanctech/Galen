"""M5 — score the blind reader files against the private keys.

Usage: python m5_score.py --key-dir <dir with m5_private_key_sheet_a.csv / _b.csv>
Writes to data/qc/h3m/m5/: m5_summary.json, m5_control_audit.csv, m5_sheet_a_verdicts.csv,
m5_disagreement_resolution.csv (if a sheet-B reader file exists), section5_m5_sentence.md,
and copies the private keys next to the results (they are published with the results).
"""
from __future__ import annotations

import argparse
import sys
import csv
import json
import math
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
M5 = ROOT / "data" / "qc" / "h3m" / "m5"

READERS_A = {
    "reader1_fable-5-1": M5 / "m5_sheet_a_reader1_fable-5-1.csv",
    "reader2_opus-5-5": M5 / "m5_sheet_a_reader2_opus-5-5.csv",
}
READERS_B = {"reader1_fable-5-1": M5 / "m5_sheet_b_reader1_fable-5-1.csv"}

UNAMBIGUOUS_WRONG = {"C01", "C02", "C03", "C04", "C05", "C06"}
ACCENT_WRONG = {"C07", "C08"}
ANCHORS = {"C09", "C10", "C11", "C12", "C13"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", (s or "").strip())


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 2), round(100 * (c + h), 2))


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    cats = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def load_reader(p: Path) -> dict[str, dict]:
    rows = {}
    with p.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            r = {k.strip(): (v or "") for k, v in r.items()}
            r["answer"] = r["answer"].strip().lower()
            rows[r["row_id"].strip()] = r
    return rows


def score_sheet_a(key_dir: Path) -> dict:
    key = {r["row_id"]: r for r in csv.DictReader((key_dir / "m5_private_key_sheet_a.csv").open(encoding="utf-8"))}
    readers = {name: load_reader(p) for name, p in READERS_A.items() if p.exists()}
    out: dict = {"readers": {}, "n_random": sum(1 for r in key.values() if r["kind"] == "random")}
    audit_rows, verdict_rows = [], []

    for name, ans in readers.items():
        missing = [rid for rid in key if rid not in ans]
        # control gate
        caught, missed, anchor_wrong, accent_strict = [], [], [], []
        for rid, k in key.items():
            if k["kind"] != "control":
                continue
            a = ans.get(rid, {}).get("answer", "")
            cid = k["control_id"]
            exp = k["expected"]
            hit = (a == exp)
            audit_rows.append({"reader": name, "row_id": rid, "control_id": cid, "expected": exp, "answer": a,
                               "expected_lemma": k["expected_lemma"], "reader_lemma": ans.get(rid, {}).get("correct_lemma_if_wrong", ""),
                               "hit": hit})
            if cid in UNAMBIGUOUS_WRONG:
                (caught if hit else missed).append(cid)
            elif cid in ANCHORS and not hit:
                anchor_wrong.append(cid)
            elif cid in ACCENT_WRONG:
                accent_strict.append((cid, hit))
        fail_reasons = []
        if "C01" in missed:
            fail_reasons.append("missed C01 (non-word)")
        if len(missed) >= 2:
            fail_reasons.append(f"missed {len(missed)}/6 unambiguous wrong-plants: {missed}")
        if anchor_wrong:
            fail_reasons.append(f"marked right-anchors wrong: {anchor_wrong}")
        gate = "PASS" if not fail_reasons else "FAIL"

        # rate on the 60 random rows only
        rand = [(rid, ans.get(rid, {}).get("answer", "")) for rid, k in key.items() if k["kind"] == "random"]
        n = len(rand)
        y = sum(1 for _, a in rand if a == "y")
        nn = sum(1 for _, a in rand if a == "n")
        u = sum(1 for _, a in rand if a == "unsure")
        n_dec = y + nn
        out["readers"][name] = {
            "gate": gate, "gate_fail_reasons": fail_reasons,
            "controls_caught_unambiguous": f"{len(caught)}/6", "anchors_marked_wrong": len(anchor_wrong),
            "accent_controls_strict": {cid: hit for cid, hit in accent_strict},
            "missing_rows": missing,
            "random60": {"y": y, "n": nn, "unsure": u,
                          "rate_lower_pct_unsure_as_wrong": round(100 * y / n, 2) if n else None,
                          "wilson95_lower_bound_variant": wilson(y, n),
                          "rate_point_pct_unsure_excluded": round(100 * y / n_dec, 2) if n_dec else None,
                          "wilson95_point_variant": wilson(y, n_dec)},
        }

    # agreement between the two readers on the 60
    names = list(readers)
    if len(names) == 2:
        a1, a2 = readers[names[0]], readers[names[1]]
        rand_ids = [rid for rid, k in key.items() if k["kind"] == "random"]
        v1 = [a1.get(r, {}).get("answer", "") for r in rand_ids]
        v2 = [a2.get(r, {}).get("answer", "") for r in rand_ids]
        agree = sum(1 for x, y in zip(v1, v2) if x == y)
        both_n_same_lemma = sum(1 for r in rand_ids if a1.get(r, {}).get("answer") == "n" and a2.get(r, {}).get("answer") == "n"
                                and nfc(a1[r].get("correct_lemma_if_wrong")) == nfc(a2[r].get("correct_lemma_if_wrong")))
        both_n = sum(1 for r in rand_ids if a1.get(r, {}).get("answer") == "n" and a2.get(r, {}).get("answer") == "n")
        out["agreement_random60"] = {
            "readers": names, "raw_agreement_pct": round(100 * agree / len(rand_ids), 2),
            "cohen_kappa_3cat": cohen_kappa(v1, v2),
            "cohen_kappa_yn_unsure_as_n": cohen_kappa(["y" if x == "y" else "n" for x in v1], ["y" if x == "y" else "n" for x in v2]),
            "both_marked_wrong": both_n, "both_wrong_same_correct_lemma": both_n_same_lemma,
            "either_marked_wrong": sum(1 for x, y in zip(v1, v2) if x == "n" or y == "n"),
            "both_marked_right": sum(1 for x, y in zip(v1, v2) if x == "y" and y == "y"),
        }
        for r in rand_ids:
            verdict_rows.append({"row_id": r, "surface_form": key[r]["surface_form"], "lemma_produced": key[r]["lemma_produced"],
                                 names[0]: a1.get(r, {}).get("answer", ""), f"{names[0]}_lemma": a1.get(r, {}).get("correct_lemma_if_wrong", ""),
                                 names[1]: a2.get(r, {}).get("answer", ""), f"{names[1]}_lemma": a2.get(r, {}).get("correct_lemma_if_wrong", "")})
        with (M5 / "m5_sheet_a_verdicts.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(verdict_rows[0].keys()))
            w.writeheader(); w.writerows(verdict_rows)

    with (M5 / "m5_control_audit.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys()))
        w.writeheader(); w.writerows(audit_rows)
    return out


def score_sheet_b(key_dir: Path) -> dict | None:
    kp = key_dir / "m5_private_key_sheet_b.csv"
    readers = {name: p for name, p in READERS_B.items() if p.exists()}
    if not kp.exists() or not readers:
        return None
    key = {r["row_id"]: r for r in csv.DictReader(kp.open(encoding="utf-8"))}
    sheet = {r["row_id"]: r for r in csv.DictReader((M5 / "m5_disagreement_sheet.csv").open(encoding="utf-8"))}
    name, p = next(iter(readers.items()))
    ans = load_reader(p)
    res_rows = []
    tally = Counter()
    by_pos = defaultdict(Counter)
    by_artifact = defaultdict(Counter)
    for rid, k in key.items():
        a = ans.get(rid, {}).get("answer", "").strip()
        a_up = a.upper() if a.upper() in ("A", "B", "C") else a.lower()
        sided = []
        for sysname in ("odycy", "perseus", "proiel"):
            if k[f"letter_{sysname}"] and k[f"letter_{sysname}"] == a_up:
                sided.append(sysname)
        if a_up in ("A", "B", "C"):
            verdict = "odycy_right" if "odycy" in sided else "odycy_wrong"
        elif a_up == "none":
            verdict = "odycy_wrong"
        elif a_up == "unsure":
            verdict = "unsure"
        else:
            verdict = "missing"
        tally[verdict] += 1
        tally["sides_with_" + "+".join(sided) if sided else "sides_with_none"] += 1
        pos = sheet.get(rid, {}).get("pos", "")
        by_pos[pos][verdict] += 1
        art = "encoding_artifact" if "encoding_artifact" in (k.get("g2a_odycy_perseus", ""), k.get("g2a_odycy_proiel", "")) else "real_or_unlabelled"
        by_artifact[art][verdict] += 1
        res_rows.append({"row_id": rid, "surface_form": sheet.get(rid, {}).get("surface_form", ""), "pos": pos,
                         "lemma_odycy": k["lemma_odycy"], "lemma_perseus": k["lemma_perseus"], "lemma_proiel": k["lemma_proiel"],
                         "reader_answer": a, "reader_sided_with": "+".join(sided), "reader_lemma_if_none": ans.get(rid, {}).get("correct_lemma_if_none", ""),
                         "verdict_for_odycy": verdict, "g2a_flag": art})
    with (M5 / "m5_disagreement_resolution.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(res_rows[0].keys()))
        w.writeheader(); w.writerows(res_rows)
    n = len(key)
    decided = tally["odycy_right"] + tally["odycy_wrong"]
    return {"reader": name, "n_rows": n, "tally": dict(tally),
            "odycy_right_pct_of_decided": round(100 * tally["odycy_right"] / decided, 2) if decided else None,
            "wilson95_odycy_right": wilson(tally["odycy_right"], decided),
            "by_pos": {k: dict(v) for k, v in sorted(by_pos.items(), key=lambda kv: -sum(kv[1].values()))},
            "by_g2a_flag": {k: dict(v) for k, v in by_artifact.items()}}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-dir", required=True)
    a = ap.parse_args()
    key_dir = Path(a.key_dir)
    summary = {"date": "2026-11-05", "design": "m5_llm_adjudication_spec.md", "sheet_a": score_sheet_a(key_dir)}
    b = score_sheet_b(key_dir)
    if b:
        summary["sheet_b"] = b
    for kf in ("m5_private_key_sheet_a.csv", "m5_private_key_sheet_b.csv"):
        if (key_dir / kf).exists():
            shutil.copy(key_dir / kf, M5 / kf)
    (M5 / "m5_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # §5 sentence
    ra = summary["sheet_a"]["readers"]
    parts = []
    for name, r in ra.items():
        parts.append(f"{name}: {r['random60']['rate_lower_pct_unsure_as_wrong']}% (Wilson 95% {r['random60']['wilson95_lower_bound_variant'][0]}–{r['random60']['wilson95_lower_bound_variant'][1]}), control gate {r['gate']} ({r['controls_caught_unambiguous']} wrong-plants caught, {r['anchors_marked_wrong']} anchors marked wrong)")
    agr = summary["sheet_a"].get("agreement_random60", {})
    sent = ("Two frontier language models reading the identical salted sheet blind marked the frozen random-60 correct at "
            + "; ".join(parts) + (f"; raw agreement {agr.get('raw_agreement_pct')}%, Cohen's κ = {agr.get('cohen_kappa_yn_unsure_as_n')} (y/n)" if agr else "")
            + ". This is a machine-adjudicated estimate, reported separately from the analyzer floor (M1) and the lexicographer gold (M3), and it does not replace the planned human two-reader check.")
    if b:
        sent += (f" On the {b['n_rows']} cross-system disagreement tokens (system-blind), the reader sided with odyCy in "
                 f"{b['odycy_right_pct_of_decided']}% of decided rows (Wilson 95% {b['wilson95_odycy_right'][0]}–{b['wilson95_odycy_right'][1]}).")
    (M5 / "section5_m5_sentence.md").write_text("# §5 M5 sentence (architect pastes; this file does not edit the paper)\n\n" + sent + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n" + sent)


if __name__ == "__main__":
    main()
