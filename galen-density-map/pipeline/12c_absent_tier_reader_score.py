"""Stage 12c — score the blind absent-tier reader pass (ROADMAP item 8, 2026-11-06).

Inputs: the PRIVATE key written by 12b, one or more reader answer files (row_id, verdict,
headword, proper_name, note; several batch files per reader are concatenated), stage 12's
headword map. Reader labels come from --reader (same order as --answers groups).

Reports, per reader: control gate (plants caught, anchors kept; the contestable plant declared in
sheet_meta.json is excluded), verdict distribution on the 734 targets with Wilson 95% intervals,
proper-name share, agreement with Dilemma's machine class (artifact <-> relemmatized_* / split,
real_headword <-> same_headword), headword agreement with Dilemma's top headword (accent-blind),
and the per-machine-class breakdown. Across readers: Cohen's kappa on the three-way verdict and
the set of targets both call artifact / both call real.

Then un-blinds: writes outputs/phase3/reader_pass/absent_tier_verdicts.csv (one row per sheet row
with key, Dilemma class and every reader's answer) and absent_tier_reader_summary.json, and copies
the key next to them (the key is public once scored; M5 convention). Report only: the punch
list is not modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

OUT = ROOT / "outputs" / "phase3" / "reader_pass"
VERDICTS = ("real_headword", "artifact", "unsure")
ARTIFACT_CLASSES = {"relemmatized_lsj", "relemmatized_no_lsj", "split"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 2), round(100 * (c + h), 2))


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson95": [lo, hi]}


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[v] * cb[v] for v in set(a) | set(b)) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else float("nan")


def norm_verdict(v: str) -> str:
    v = (v or "").strip().lower().replace(" ", "_")
    if v.startswith("real"):
        return "real_headword"
    if v.startswith("art"):
        return "artifact"
    return "unsure"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, type=Path)
    ap.add_argument("--reader", action="append", required=True, help="reader label (repeat per reader)")
    ap.add_argument("--answers", action="append", required=True,
                    help="for each reader, a ';'-separated list of answer CSVs (batches), same order as --reader")
    a = ap.parse_args()
    if len(a.reader) != len(a.answers):
        ap.error("--reader and --answers must pair up")
    OUT.mkdir(parents=True, exist_ok=True)
    meta = json.load((OUT / "sheet_meta.json").open(encoding="utf-8"))
    contestable = set(meta.get("contestable_plants", {}))

    key = {r["row_id"]: r for r in csv.DictReader(a.key.open(encoding="utf-8"))}
    sheet = {r["row_id"]: r for r in csv.DictReader((OUT / "absent_tier_reader_sheet.csv").open(encoding="utf-8"))}
    readers: dict[str, dict[str, dict]] = {}
    for label, files in zip(a.reader, a.answers):
        ans: dict[str, dict] = {}
        for f in files.split(";"):
            for r in csv.DictReader(Path(f).open(encoding="utf-8-sig")):
                rid = (r.get("row_id") or "").strip()
                if rid in key:
                    ans[rid] = {"verdict": norm_verdict(r.get("verdict", "")), "headword": nfc(r.get("headword", "")),
                                "proper_name": (r.get("proper_name") or "").strip().lower()[:1], "note": (r.get("note") or "").strip()}
        readers[label] = ans
        missing = [rid for rid in key if rid not in ans]
        print(f"{label}: {len(ans)} answers, {len(missing)} missing", flush=True)

    targets = [rid for rid, k in key.items() if k["kind"] == "target"]
    anchors = [rid for rid, k in key.items() if k["kind"] == "anchor"]
    plants = [rid for rid, k in key.items() if k["kind"] == "plant" and k["lemma"] not in contestable]
    summary: dict = {"date": "2026-11-06", "stage": "12c_absent_tier_reader_score", "report_only": True,
                     "n_targets": len(targets), "n_anchors": len(anchors), "n_plants_scored": len(plants),
                     "contestable_plants_excluded": sorted(contestable), "gate": meta["gate"], "readers": {}}

    for label, ans in readers.items():
        g = lambda rid: ans.get(rid, {"verdict": "unsure", "headword": "", "proper_name": "", "note": ""})  # noqa: E731
        plants_caught = sum(g(r)["verdict"] == "artifact" for r in plants)
        plants_hw = sum(g(r)["verdict"] == "artifact" and blind(g(r)["headword"]) == blind(key[r]["expected_headword"]) for r in plants)
        anchors_ok = sum(g(r)["verdict"] == "real_headword" for r in anchors)
        gate_ok = plants_caught >= meta["gate"]["plants_min_caught"] and anchors_ok >= meta["gate"]["anchors_min_correct"]
        tv = Counter(g(r)["verdict"] for r in targets)
        n_t = len(targets)
        by_class: dict[str, Counter] = defaultdict(Counter)
        hw_agree = hw_n = 0
        class_agree = class_n = 0
        proper = Counter()
        for r in targets:
            k = key[r]
            v = g(r)["verdict"]
            by_class[k["machine_class"]][v] += 1
            if v != "unsure":
                class_n += 1
                machine_artifact = k["machine_class"] in ARTIFACT_CLASSES
                if (v == "artifact") == machine_artifact and k["machine_class"] != "unresolved":
                    class_agree += 1
            if v == "artifact" and k["dilemma_top_headword"] and g(r)["headword"]:
                hw_n += 1
                hw_agree += int(blind(g(r)["headword"]) == blind(k["dilemma_top_headword"]))
            if v == "real_headword":
                proper[g(r)["proper_name"] or "?"] += 1
        summary["readers"][label] = {
            "answered": len(ans), "gate": {"plants_caught": f"{plants_caught}/{len(plants)}", "plants_with_right_headword": f"{plants_hw}/{len(plants)}",
                                            "anchors_real_headword": f"{anchors_ok}/{len(anchors)}", "passed": gate_ok},
            "targets": {v: rate(tv[v], n_t) for v in VERDICTS},
            "artifact_rate_excluding_unsure": rate(tv["artifact"], tv["artifact"] + tv["real_headword"]),
            "agreement_with_dilemma_class_excluding_unsure": rate(class_agree, class_n),
            "headword_matches_dilemma_when_artifact": rate(hw_agree, hw_n),
            "proper_name_among_real_headword": dict(proper),
            "by_machine_class": {c: dict(v) for c, v in by_class.items()},
        }

    labels = list(readers)
    if len(labels) >= 2:
        r1, r2 = labels[0], labels[1]
        v1 = [readers[r1].get(r, {}).get("verdict", "unsure") for r in targets]
        v2 = [readers[r2].get(r, {}).get("verdict", "unsure") for r in targets]
        both_art = [r for r, x, y in zip(targets, v1, v2) if x == y == "artifact"]
        both_real = [r for r, x, y in zip(targets, v1, v2) if x == y == "real_headword"]
        hw_both = sum(blind(readers[r1][r]["headword"]) == blind(readers[r2][r]["headword"]) for r in both_art if readers[r1][r]["headword"] and readers[r2][r]["headword"])
        summary["between_readers"] = {
            "readers": [r1, r2], "cohen_kappa_three_way": kappa(v1, v2),
            "raw_agreement": rate(sum(x == y for x, y in zip(v1, v2)), len(targets)),
            "both_artifact": rate(len(both_art), len(targets)), "both_real_headword": rate(len(both_real), len(targets)),
            "both_artifact_same_headword": rate(hw_both, len(both_art)),
            "both_real_headword_proper_names": sum(1 for r in both_real if readers[r1][r]["proper_name"] == "y" and readers[r2][r]["proper_name"] == "y"),
            "disagree_rows": sum(x != y for x, y in zip(v1, v2)),
        }
        # consensus against Dilemma
        cons_art_dil = Counter(key[r]["machine_class"] for r in both_art)
        cons_real_dil = Counter(key[r]["machine_class"] for r in both_real)
        summary["consensus_vs_dilemma"] = {"both_artifact_by_machine_class": dict(cons_art_dil), "both_real_by_machine_class": dict(cons_real_dil)}

    # un-blinded verdict table
    cols = ["row_id", "kind", "lemma", "pos", "galen_count", "surfaces", "expected_verdict", "expected_headword", "machine_class",
            "dilemma_top_headword", "dilemma_top_share", "top_headword_lsj_tier", "m1_admissible_share"]
    for label in labels:
        cols += [f"{label}_verdict", f"{label}_headword", f"{label}_proper_name", f"{label}_note"]
    with (OUT / "absent_tier_verdicts.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for rid in sorted(key):
            k, s = key[rid], sheet[rid]
            row = {"row_id": rid, "kind": k["kind"], "lemma": k["lemma"], "pos": s["pos"], "galen_count": s["galen_count"], "surfaces": s["surfaces"],
                   "expected_verdict": k["expected_verdict"], "expected_headword": k["expected_headword"], "machine_class": k["machine_class"],
                   "dilemma_top_headword": k["dilemma_top_headword"], "dilemma_top_share": k["dilemma_top_share"],
                   "top_headword_lsj_tier": k["top_headword_lsj_tier"], "m1_admissible_share": k["m1_admissible_share"]}
            for label in labels:
                g = readers[label].get(rid, {})
                row[f"{label}_verdict"] = g.get("verdict", "")
                row[f"{label}_headword"] = g.get("headword", "")
                row[f"{label}_proper_name"] = g.get("proper_name", "")
                row[f"{label}_note"] = g.get("note", "")
            w.writerow(row)
    shutil.copy(a.key, OUT / "absent_tier_reader_key_PUBLISHED_AFTER_SCORING.csv")
    (OUT / "absent_tier_reader_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
