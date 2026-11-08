"""T0 — reference-corpus sensitivity check against the Open Greek Corpus (2026-11-05).

Question. The density map's keyness was computed as Galen-medical (odyCy lemmas) vs
First1KGreek-minus-Galen (odyCy lemmas, 19.68M tokens). Open Greek (opengreek.org,
release corpus-2026-11-05.1, CC BY-SA) publishes per-work lemma counts for 3,939 works /
65.3M tokens, lemmatized with its own Dilemma lemmatizer, including all 68 Galen medical
editions. Does the map hold when (a) the reference is three times larger and (b) a
different lemmatizer is used on BOTH sides?

Design (model-consistency constraint respected: both sides of every comparison use the
same lemmatizer):
  Map A (frozen, ours):  Galen-medical/odyCy  vs  First1K-minus-Galen/odyCy    -> keyness_scores.csv
  Map B (Open Greek):    Galen-medical/Dilemma vs Open-Greek-minus-Galen/Dilemma (this script)
  Map B' (control):      Galen-medical/Dilemma vs First1K-subset-of-Open-Greek-minus-Galen/Dilemma
                         (isolates reference size from lemmatizer: B' vs A differs only by lemmatizer;
                          B vs B' differs only by reference size)
Compare: Spearman rank correlation of log-likelihood over shared lemmas; overlap of the top-N key
lemma sets (N = 200, 500, 1000, |punch list|); which of our 1,433 punch-list lemmas remain key in
B/B'; which Open-Greek-only lemmas enter the top sets. Report-only; outputs/ is not modified
except for the new outputs/t0/ directory.

Inputs (downloaded 2026-11-05 from github.com/open-greek/open-greek-corpus/main/data):
  work_lemma_counts.tsv.gz  (slug, lemma, count; no header)
  corpus_catalog.tsv        (slug, tlg, source, tokens, ...)
Usage: python t0_opengreek_sensitivity.py --opengreek-dir <dir with the two files>
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "outputs" / "t0"
sys.path.insert(0, str(HERE))
from lib.config import load_config  # noqa: E402
from lib.census import load_census, medical_urn_stems  # noqa: E402

GALEN_TLG = "tlg0057"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def log_likelihood(a: float, b: float, c: float, d: float) -> float:
    """Dunning LL for a (domain) vs b (reference) with corpus sizes c, d; same as stage 05."""
    if a == 0 and b == 0:
        return 0.0
    e1 = c * (a + b) / (c + d)
    e2 = d * (a + b) / (c + d)
    ll = 0.0
    if a > 0:
        ll += a * math.log(a / e1)
    if b > 0:
        ll += b * math.log(b / e2)
    ll *= 2
    return ll if (a / c) > (b / d) else -ll  # signed: positive = key in domain


def spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return float("nan")
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
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
    return round(num / den, 4) if den else float("nan")


def keyness_table(domain: Counter, ref: Counter, min_freq: int, min_ll: float) -> dict[str, dict]:
    c = sum(domain.values()); d = sum(ref.values())
    out = {}
    for lemma, a in domain.items():
        if a < min_freq:
            continue
        b = ref.get(lemma, 0)
        ll = log_likelihood(a, b, c, d)
        if ll >= min_ll:
            out[lemma] = {"domain_raw": a, "ref_raw": b, "domain_per10k": 1e4 * a / c, "ref_per10k": 1e4 * b / d, "ll": ll}
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--opengreek-dir", required=True)
    a = ap.parse_args()
    og = Path(a.opengreek_dir)
    cfg = load_config()
    census = load_census((ROOT.parent / "phase1" / "galen_ogl_census.json").resolve())
    med_stems = medical_urn_stems(cfg, census)  # e.g. urn_cts_greekLit_tlg0057.tlg008.1st1K-grc1
    med_tlg = {s.split("tlg0057.")[1].split(".")[0] for s in med_stems}  # tlg008 ...
    min_freq = int(cfg.get("min_domain_frequency", 5))
    min_ll = float(cfg.get("keyness_min_log_likelihood", 15.13))
    OUT.mkdir(parents=True, exist_ok=True)

    # --- catalog: slug -> (tlg, source)
    cat = {r["slug"]: r for r in csv.DictReader((og / "corpus_catalog.tsv").open(encoding="utf-8"), delimiter="\t")}
    galen_med_slugs = {s for s, r in cat.items() if r["tlg"].startswith(GALEN_TLG + ".") and r["tlg"].split(".")[-1] in med_tlg}
    galen_all_slugs = {s for s, r in cat.items() if r["tlg"].startswith(GALEN_TLG + ".") or r["author"].startswith("galen")}
    first1k_slugs = {s for s, r in cat.items() if r["source"] == "first1k"}

    # --- stream the lemma counts
    dom_B, ref_B, ref_Bp = Counter(), Counter(), Counter()
    n_rows = 0
    with gzip.open(og / "work_lemma_counts.tsv.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            slug, lemma, cnt = line.rstrip("\n").split("\t")
            n_rows += 1
            lemma = nfc(lemma); cnt = int(cnt)
            if slug in galen_med_slugs:
                dom_B[lemma] += cnt
            elif slug in galen_all_slugs:
                continue  # non-medical Galen: out of both sides (disjoint reference, as in Map A)
            else:
                ref_B[lemma] += cnt
                if slug in first1k_slugs:
                    ref_Bp[lemma] += cnt

    # --- Map A (frozen)
    A_rows = list(csv.DictReader((ROOT / "outputs" / "keyness_scores.csv").open(encoding="utf-8")))
    A = {nfc(r["lemma"]): float(r["log_likelihood"]) for r in A_rows if r.get("direction", "overused") == "overused"}
    punch = [nfc(r["lemma"]) for r in csv.DictReader((ROOT / "outputs" / "punch_list.csv").open(encoding="utf-8"))]
    punch_set = set(punch)

    B = keyness_table(dom_B, ref_B, min_freq, min_ll)
    Bp = keyness_table(dom_B, ref_Bp, min_freq, min_ll)

    def top(tbl: dict, n: int) -> list[str]:
        return [k for k, _ in sorted(tbl.items(), key=lambda kv: -(kv[1]["ll"] if isinstance(kv[1], dict) else kv[1]))[:n]]

    summary = {
        "date": "2026-11-05", "design": __doc__.split("Design")[0].strip(),
        "open_greek_release": "corpus-2026-11-05.1",
        "rows_streamed": n_rows,
        "galen_medical_works_in_open_greek": len(galen_med_slugs),
        "galen_medical_tokens_dilemma": sum(dom_B.values()),
        "reference_B_tokens": sum(ref_B.values()), "reference_Bprime_first1k_tokens": sum(ref_Bp.values()),
        "reference_A_tokens_odycy_first1k": 19677479,
        "thresholds": {"min_domain_frequency": min_freq, "keyness_min_log_likelihood": min_ll},
        "key_lemmas": {"A_frozen": len(A), "B_open_greek": len(B), "Bprime_first1k_subset": len(Bp)},
    }
    # rank correlations over shared lemmas
    for name, tbl in (("B", B), ("Bprime", Bp)):
        shared = [l for l in tbl if l in A]
        summary[f"spearman_LL_A_vs_{name}_shared"] = {"n_shared": len(shared), "rho": spearman([A[l] for l in shared], [tbl[l]["ll"] for l in shared])}
    sharedBB = [l for l in B if l in Bp]
    summary["spearman_LL_B_vs_Bprime_shared"] = {"n_shared": len(sharedBB), "rho": spearman([B[l]["ll"] for l in sharedBB], [Bp[l]["ll"] for l in sharedBB])}
    # top-N overlaps
    ov = {}
    for n in (200, 500, 1000, len(punch)):
        tA, tB, tBp = set(top(A, n)), set(top(B, n)), set(top(Bp, n))
        ov[str(n)] = {"A∩B": len(tA & tB), "A∩Bprime": len(tA & tBp), "B∩Bprime": len(tB & tBp), "jaccard_A_B": round(len(tA & tB) / len(tA | tB), 3)}
    summary["topN_overlap"] = ov
    # punch list survival
    surv_B = [l for l in punch if l in B]; surv_Bp = [l for l in punch if l in Bp]
    absent_dom = [l for l in punch if l not in dom_B]
    summary["punch_list"] = {"n": len(punch), "still_key_in_B": len(surv_B), "still_key_in_Bprime": len(surv_Bp),
                             "lemma_absent_from_dilemma_galen_side": len(absent_dom),
                             "note": "a punch lemma absent from the Dilemma side is a lemmatizer-convention or artifact difference (e.g. odyCy fragment vs Dilemma headword), not a keyness change"}
    # new entrants: top-500 of B not in A at all
    newB = [l for l in top(B, 500) if l not in A]
    summary["top500_B_not_key_in_A"] = {"n": len(newB), "examples": newB[:40]}
    lostA = [l for l in top(A, 500) if l in dom_B and l not in B]
    summary["top500_A_present_in_dilemma_galen_but_not_key_in_B"] = {"n": len(lostA), "examples": lostA[:40]}

    (OUT / "t0_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT / "keyness_open_greek_B.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["lemma", "domain_raw", "ref_raw", "domain_per10k", "ref_per10k", "log_likelihood", "in_A", "in_punch"])
        for l, r in sorted(B.items(), key=lambda kv: -kv[1]["ll"]):
            w.writerow([l, r["domain_raw"], r["ref_raw"], round(r["domain_per10k"], 4), round(r["ref_per10k"], 4), round(r["ll"], 4), int(l in A), int(l in punch_set)])
    with (OUT / "punch_list_survival.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["lemma", "in_dilemma_galen", "dilemma_galen_raw", "key_in_B", "ll_B", "key_in_Bprime", "ll_Bprime", "ll_A"])
        for l in punch:
            w.writerow([l, int(l in dom_B), dom_B.get(l, 0), int(l in B), round(B[l]["ll"], 2) if l in B else "", int(l in Bp), round(Bp[l]["ll"], 2) if l in Bp else "", round(A.get(l, 0), 2)])
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
