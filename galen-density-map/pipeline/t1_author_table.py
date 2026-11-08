"""T1 — the author table: one audit row per First1K author from a whole-reference-corpus kit run.

Input: an audit_summary.json produced by ``greek-lemma-audit run --subcorpus reference --systems
reference,dilemma`` over the project's odyCy-lemmatized First1K reference corpus (284 authors), plus
the Open Greek corpus catalog for author names (tlg -> author slug; CC BY-SA). Output: the 50 largest
authors by odyCy tokens (and the full 284 in a second file) with, per author: tokens, works, M1
Morpheus floor for odyCy and for Dilemma (strict and article-neutral; the Morpheus cache was built for
Galen, so the not-in-cache share is reported and the floor is flagged when it exceeds 15%), and the
odyCy–Dilemma agreement strict and article-neutral. Report only.

Usage: python t1_author_table.py --summary <audit_summary.json> --catalog <corpus_catalog.tsv> [--top 50]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "outputs" / "t1"


def merge_author_summaries(d: Path) -> dict:
    """Stitch per-author audit summaries into the shape of one whole-corpus summary (by_author blocks)."""
    merged = {"kit": {}, "corpus": {"by_author": {}}, "m1_admissibility": {"systems": {}}, "m2_agreement": {"by_author": {}},
              "source": "merged per-author runs", "runs": []}
    for sub in sorted(d.iterdir()):
        f = sub / "audit_summary.json"
        if not f.exists():
            continue
        s = json.load(f.open(encoding="utf-8"))
        merged["kit"] = s.get("kit", merged["kit"])
        merged["runs"].append(sub.name)
        for tlg, c in s["corpus"]["by_author"].items():
            merged["corpus"]["by_author"][tlg] = c
        for sysname, blk in s["m1_admissibility"]["systems"].items():
            m = merged["m1_admissibility"]["systems"].setdefault(sysname, {"by_author": {}})
            for tlg, ba in (blk.get("by_author") or {}).items():
                m["by_author"][tlg] = ba
            # per-author article-neutral figure: a single-author run's system-level figure is that author's
            an = blk.get("article_neutral_admissible_pct_of_analyzable")
            for tlg in s["corpus"]["by_author"]:
                if tlg in m["by_author"] and an is not None:
                    m["by_author"][tlg].setdefault("article_neutral_admissible_pct_of_analyzable", an)
        for tlg, mb in (s["m2_agreement"].get("by_author") or {}).items():
            merged["m2_agreement"]["by_author"][tlg] = mb
    return merged


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, default=None, help="one whole-corpus audit_summary.json")
    ap.add_argument("--summaries-dir", type=Path, default=None,
                    help="dir of per-author run dirs (<dir>/<tlg>/audit_summary.json), as produced by one run per author")
    ap.add_argument("--catalog", type=Path, default=None)
    ap.add_argument("--recommend", action="store_true", help="write outputs/t1/recommendations.csv + RECOMMENDATIONS.md (pipeline/t1_recommend.py) and exit")
    ap.add_argument("--top", type=int, default=50)
    a = ap.parse_args()
    if a.recommend:
        import t1_recommend
        t1_recommend.main()
        return
    if a.catalog is None:
        ap.error("--catalog required")
    OUT.mkdir(parents=True, exist_ok=True)
    if a.summaries_dir:
        s = merge_author_summaries(a.summaries_dir)
    elif a.summary:
        s = json.load(a.summary.open(encoding="utf-8"))
    else:
        ap.error("--summary or --summaries-dir required")
    names: dict[str, str] = {}
    for r in csv.DictReader(a.catalog.open(encoding="utf-8"), delimiter="\t"):
        tlg = (r.get("tlg") or "").split(".")[0]
        if tlg and tlg not in names and r.get("author"):
            names[tlg] = r["author"]
    corpus_by_author = s["corpus"]["by_author"]
    m1 = s["m1_admissibility"]["systems"]
    m2 = s["m2_agreement"]
    systems = [x for x in ("reference", "dilemma") if x in m1]
    rows = []
    for tlg, c in corpus_by_author.items():
        row = {"tlg": tlg, "author": names.get(tlg, ""), "works": c["works"], "tokens": c["tokens"]}
        for sysname in systems:
            ba = (m1[sysname].get("by_author") or {}).get(tlg, {})
            tag = "odycy" if sysname == "reference" else sysname
            row[f"m1_{tag}_admissible_pct"] = ba.get("admissible_pct_of_analyzable")
            row[f"m1_{tag}_article_neutral_pct"] = ba.get("article_neutral_admissible_pct_of_analyzable")
            row[f"m1_{tag}_not_in_cache_pct"] = ba.get("not_in_cache_pct_of_all")
            row[f"m1_{tag}_no_analysis_pct"] = ba.get("no_analysis_pct_of_all")
            row[f"m1_{tag}_floor_flag"] = "cache_gap>15%" if (ba.get("not_in_cache_pct_of_all") or 0) > 15 else ""
        mb = (m2.get("by_author") or {}).get(tlg, {})
        row["m2_n_aligned"] = mb.get("n_aligned")
        row["m2_odycy_dilemma_agree_pct"] = (mb.get("all_systems_agree") or {}).get("agree_pct")
        row["m2_odycy_dilemma_agree_article_neutral_pct"] = (mb.get("all_systems_agree_article_neutral") or {}).get("agree_pct")
        rows.append(row)
    rows.sort(key=lambda r: -r["tokens"])
    cols = list(rows[0].keys())
    for name, sel in (("author_table_top%d.csv" % a.top, rows[: a.top]), ("author_table_all.csv", rows)):
        with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(sel)
    top = rows[: a.top]
    md = ["# T1 author table — %d largest First1K authors (odyCy reference vs Dilemma), %s" % (a.top, s.get("kit", {}).get("date", "")),
          "", "Source: `%s` (label: %s). Morpheus cache built for Galen: the floor is only comparable where the not-in-cache share is small; flagged otherwise. Agreement strict and article-convention-neutral (ἡ/τό/τῶν… → ὁ)." % ((a.summary.name if a.summary else str(a.summaries_dir)), s.get("kit", {}).get("label", s.get("source", ""))),
          "", "| tlg | author | tokens | works | M1 odyCy % | cache gap % | M1 Dilemma % (strict / neutral) | odyCy–Dilemma agree % (strict / neutral) |", "|---|---|---|---|---|---|---|---|"]
    for r in top:
        md.append("| %s | %s | %s | %s | %s | %s | %s / %s | %s / %s |" % (
            r["tlg"], r["author"], f'{r["tokens"]:,}', r["works"], r.get("m1_odycy_admissible_pct"), r.get("m1_odycy_not_in_cache_pct"),
            r.get("m1_dilemma_admissible_pct"), r.get("m1_dilemma_article_neutral_pct"),
            r.get("m2_odycy_dilemma_agree_pct"), r.get("m2_odycy_dilemma_agree_article_neutral_pct")))
    (OUT / "author_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:12]))
    print(f"... {len(rows)} authors written; top {a.top} in author_table_top{a.top}.csv")


if __name__ == "__main__":
    main()
