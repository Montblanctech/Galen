"""T1 recommendations — "which lemmatizer for my author?" (2026-11-07). Report only; a RULE, never a judgement.

Reads outputs/t1/author_table_all.csv, outputs/t1/convention_pairs.csv and data/qc/lsjgold/lsj_gold_scores.json;
writes outputs/t1/recommendations.csv and outputs/t1/RECOMMENDATIONS.md. No model-written text, no glosses.

Usage: python pipeline/t1_recommend.py     (also: python pipeline/t1_author_table.py --recommend  delegates here)
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "outputs" / "t1"
GOLD = ROOT / "data" / "qc" / "lsjgold" / "lsj_gold_scores.json"
MIN_N = 100
SYS = (("odycy", "odyCy"), ("dilemma", "Dilemma"))

RULE = """**Rule (applied mechanically, in this order; nothing is a judgement call).**
1. *Basis A, LSJ-Gold:* if both systems have an LSJ-Gold accent-blind score for the author with n >= 100 loci each, compare the two Wilson 95% intervals (recomputed from k, n). Non-overlapping: the higher system is recommended. Overlapping: `either`.
2. *Basis B, M1 floor (fallback when A does not apply):* compare the two systems' article-neutral Morpheus floors (percent of analyzable tokens, as in `author_table_all.csv`), with n = tokens x (100 - not-in-cache% - no-analysis%) / 100 (an approximation; the table gives percentages only). Both n >= 100 and Wilson intervals non-overlapping: the higher floor is recommended; overlapping: `either`. A floor with a cache gap above 15% is marked `cache_gap` in the row (the Morpheus cache was built for Galen; the floor is partial there) but is still used.
3. *Neither basis has n >= 100 for both systems:* `insufficient data`.
`Dilemma` = lexicon-first (Open Greek Dilemma 1.3.15, lsj convention); `odyCy` = neural (odyCy 0.7.0 frozen run). The recommendation names the system with the higher number on the stated basis; it says nothing about error types. Genre tags: the repository carries no per-author genre field, so the column is `n/a` throughout rather than invented."""


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 100.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def decide(a: tuple[float, float, int], b: tuple[float, float, int]) -> str | None:
    """a, b = (pct, n) triples; returns 'odycy'/'dilemma'/'either' or None if n < MIN_N."""
    (pa, na), (pb, nb) = a[:2], b[:2]
    if na < MIN_N or nb < MIN_N:
        return None
    la, ha = wilson(pa / 100 * na, na)
    lb, hb = wilson(pb / 100 * nb, nb)
    if la > hb:
        return "odyCy"
    if lb > ha:
        return "Dilemma"
    return "either"


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(HERE / "lsjgold"))
    try:
        from leaderboard import NAMES  # type: ignore
    except Exception:
        NAMES = {}
    tab = {r["tlg"]: r for r in csv.DictReader((OUT / "author_table_all.csv").open(encoding="utf-8"))}
    gold = json.load(GOLD.open(encoding="utf-8"))
    gsys = {s: gold["systems"].get(s, {}).get("by_author", {}) for s, _ in SYS}
    conv_tok = {"article": 0, "other": 0}
    for r in csv.DictReader((OUT / "convention_pairs.csv").open(encoding="utf-8")):
        conv_tok["article" if r["class"] == "article" else "other"] += int(r["tokens"])
    art_share = round(100 * conv_tok["article"] / (conv_tok["article"] + conv_tok["other"]), 1)
    authors = sorted(set(tab) | set(gold["loci_per_author"]))
    rows = []
    for tlg in authors:
        t = tab.get(tlg, {})
        r = {"tlg": tlg, "name": NAMES.get(tlg) or t.get("author", ""), "genre": "n/a", "tokens": t.get("tokens", "")}
        for s, _ in SYS:
            g = (gsys[s] or {}).get(tlg) or {}
            r[f"gold_{s}_pct"] = g.get("pct", "")
            r[f"gold_{s}_k"] = g.get("k", "")
            r[f"gold_{s}_n"] = g.get("n", "")
            r[f"gold_{s}_wilson95"] = f"{g['wilson95'][0]}-{g['wilson95'][1]}" if g.get("wilson95") else ""
            r[f"floor_{s}_strict_pct"] = t.get(f"m1_{s}_admissible_pct", "")
            r[f"floor_{s}_neutral_pct"] = t.get(f"m1_{s}_article_neutral_pct", "")
            r[f"cache_gap_{s}_pct"] = t.get(f"m1_{s}_not_in_cache_pct", "")
            nic, na = fnum(t.get(f"m1_{s}_not_in_cache_pct")), fnum(t.get(f"m1_{s}_no_analysis_pct"))
            tok = fnum(t.get("tokens"))
            r[f"floor_{s}_n_est"] = round(tok * (100 - nic - na) / 100) if None not in (tok, nic, na) else ""
        r["m2_agree_strict_pct"] = t.get("m2_odycy_dilemma_agree_pct", "")
        r["m2_agree_neutral_pct"] = t.get("m2_odycy_dilemma_agree_article_neutral_pct", "")
        dn, ds = fnum(r["floor_dilemma_neutral_pct"]), fnum(r["floor_dilemma_strict_pct"])
        r["dilemma_convention_gap_pts"] = round(dn - ds, 2) if None not in (dn, ds) else ""
        gl = [fnum(r[f"gold_{s}_n"]) for s, _ in SYS]
        rec, basis = None, ""
        if None not in (fnum(r["gold_odycy_pct"]), fnum(r["gold_dilemma_pct"])):
            rec = decide((float(r["gold_odycy_pct"]), float(r["gold_odycy_n"])), (float(r["gold_dilemma_pct"]), float(r["gold_dilemma_n"])))
            basis = "LSJ-Gold" if rec else ""
        if rec is None:
            fo, fd = fnum(r["floor_odycy_neutral_pct"]), fnum(r["floor_dilemma_neutral_pct"])
            no, nd = fnum(r["floor_odycy_n_est"]), fnum(r["floor_dilemma_n_est"])
            if None not in (fo, fd, no, nd):
                rec = decide((fo, no), (fd, nd))
                basis = "M1 floor (article-neutral)" if rec else ""
        flag = "cache_gap" if basis.startswith("M1") and any((fnum(r[f"cache_gap_{s}_pct"]) or 0) > 15 for s, _ in SYS) else ""
        r["recommendation"] = rec or "insufficient data"
        r["basis"] = basis
        r["flag"] = flag
        rows.append(r)
    cols = list(rows[0].keys())
    with (OUT / "recommendations.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    cnt = Counter(r["recommendation"] for r in rows)
    bas = Counter((r["recommendation"], r["basis"]) for r in rows)
    md = ["# Which lemmatizer for my author? (T1 recommendations)", "", RULE, "",
          "Counts: " + "; ".join(f"{k}: {v}" for k, v in sorted(cnt.items())) + f" (of {len(rows)} authors; by basis: " + "; ".join(f"{k[0]}/{k[1] or '-'}: {v}" for k, v in sorted(bas.items())) + ").", "",
          f"Article-convention share: tokens whose odyCy/Dilemma lemma pair is class `article` are {art_share}% of all disagreeing-pair tokens in `convention_pairs.csv` ({conv_tok['article']:,} of {conv_tok['article']+conv_tok['other']:,}). Per-author effect of the convention: column `conv gap` = Dilemma neutral floor minus strict floor.",
          "", "Sources: `author_table_all.csv`, `convention_pairs.csv`, `data/qc/lsjgold/lsj_gold_scores.json`. Gold = accent-blind LSJ-Gold match % (k/n, Wilson 95%); floor = M1 Morpheus floor, percent of analyzable tokens (strict / article-neutral), n_est as defined in the rule. Full numbers in `recommendations.csv`.", "",
          "| tlg | author | genre | recommendation | basis | odyCy gold % (k/n) [CI] | Dilemma gold % (k/n) [CI] | odyCy floor s/n (n_est) | Dilemma floor s/n (n_est) | cache gap o/d % | M2 agree s/n | conv gap | flag |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def g(r, s):
        return f"{r[f'gold_{s}_pct']} ({r[f'gold_{s}_k']}/{r[f'gold_{s}_n']}) [{r[f'gold_{s}_wilson95']}]" if r[f"gold_{s}_n"] != "" else "—"

    def f(r, s):
        return f"{r[f'floor_{s}_strict_pct']} / {r[f'floor_{s}_neutral_pct']} ({r[f'floor_{s}_n_est']})" if r[f"floor_{s}_n_est"] != "" else "—"
    for r in rows:
        md.append(f"| {r['tlg']} | {r['name']} | {r['genre']} | **{r['recommendation']}** | {r['basis'] or '—'} | {g(r,'odycy')} | {g(r,'dilemma')} | {f(r,'odycy')} | {f(r,'dilemma')} | "
                  f"{r['cache_gap_odycy_pct'] or '—'} / {r['cache_gap_dilemma_pct'] or '—'} | {r['m2_agree_strict_pct'] or '—'} / {r['m2_agree_neutral_pct'] or '—'} | {r['dilemma_convention_gap_pts'] if r['dilemma_convention_gap_pts']!='' else '—'} | {r['flag']} |")
    (OUT / "RECOMMENDATIONS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(dict(cnt), dict((f"{k[0]}|{k[1]}", v) for k, v in bas.items()), "article share", art_share)


if __name__ == "__main__":
    main()
