"""LSJ-Gold, stage 3 — the standing leaderboard: one command regenerates a static page + JSON from the scores.

Reads data/qc/lsjgold/lsj_gold_scores.json and relocation_stats.json, writes docs/lsj-gold/index.html (GitHub Pages
ready, no external assets), docs/lsj-gold/leaderboard.json and docs/lsj-gold/README.md. Every row carries N and a
Wilson 95% interval; strict and article-neutral figures stand beside the headline blind figure; the version string is
the gold file's row count + date so a number never silently changes. Adding a system = drop its <stem>.jsonl caches
under a --system-cache dir, run score.py, run this.
"""
from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsjgold"
DOCS = GDM.parent / "docs" / "lsj-gold"
from lsjgold_names import NAMES, author_name  # noqa: E402
LABELS = {"odycy": "odyCy 0.7.0 (grc_odycy_joint_trf)", "dilemma": "Dilemma 1.3.15 (Open Greek, lsj convention)",
          "stanza_perseus": "Stanza 1.14 grc-perseus", "stanza_proiel": "Stanza 1.14 grc-proiel", "stoicheia": "Stoicheia tagger-parser (2026)"}


def validation_sentence() -> str:
    """One sentence per blind validation sheet, from its summary file: readers, gate, random-locus precision, agreement."""
    out = []
    for folder, label in (("validation", "the v0 loci (6,116)"), ("validation_v03", "the v0.3 loci (96,462)")):
        p = QC / folder / "validation_summary.json"
        if not p.exists():
            continue
        v = json.load(p.open(encoding="utf-8"))
        parts = []
        for name, r in v["readers"].items():
            pr = r["relocation_precision_excl_unsure"]
            parts.append(f"{name.split('_', 1)[-1]} {pr['k']}/{pr['n']} ({pr['pct']}%, controls {r['gate']['anchors_yes']} anchors, {r['gate']['plants_no']} plants)")
        kappa = v.get("between_readers", {}).get("kappa")
        ktxt = f"; agreement κ {kappa}" if isinstance(kappa, (int, float)) and kappa == kappa else "; agreement κ undefined (no variation: both readers said yes to every random locus)"
        out.append(f"Relocation checked blind on {label} by two model readers on a salted sheet: " + "; ".join(parts) + ktxt + ".")
    return " ".join(out)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    scores = json.load((QC / "lsj_gold_scores.json").open(encoding="utf-8"))
    stats = json.load((QC / "relocation_stats.json").open(encoding="utf-8"))
    n_gold = sum(1 for _ in csv.DictReader((QC / "lsj_gold_v0.csv").open(encoding="utf-8")))
    version = f"v0 ({n_gold} loci, {scores['date']})"
    authors = sorted(scores["loci_per_author"], key=lambda a: -scores["loci_per_author"][a])
    rows = []
    for name, b in sorted(scores["systems"].items(), key=lambda kv: -(kv[1]["match_blind"]["pct"] or 0)):
        rows.append({"system": name, "label": LABELS.get(name, name), "scored": b["scored"], "missing": b["missing"],
                     "blind_pct": b["match_blind"]["pct"], "blind_ci": b["match_blind"]["wilson95"],
                     "strict_pct": b["match_strict"]["pct"], "article_neutral_pct": b["match_article_neutral"]["pct"],
                     "by_author": {a: b["by_author"].get(a) for a in authors}, "by_lsj_tier": b["by_lsj_tier"], "by_validation": b["by_validation"]})
    DOCS.mkdir(parents=True, exist_ok=True)
    lb = {"benchmark": "LSJ-Gold", "version": version, "date": scores["date"], "n_loci": n_gold, "loci_per_author": scores["loci_per_author"],
          "relocation": stats.get("status_counts"), "rule": stats.get("rule"), "rows": rows, "author_names": {a: author_name(a) for a in authors},
          "citation": "Pepperman, W. (2026). LSJ-Gold: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek. Galen Density Project. DOI: pending",
          "how_to_submit": "open a pull request adding submissions/<system>/<stem>.jsonl token caches ({i, surface, lemma} per token of the covered editions); CI scores them with `greek-lemma-audit lsjgold` and the maintainers add the row at the next version (see submissions/README.md)"}
    (DOCS / "leaderboard.json").write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")

    def ci(r):
        return f"{r['pct']} <span class=ci>[{r['wilson95'][0]}–{r['wilson95'][1]}]</span>" if r else "—"

    h = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>LSJ-Gold leaderboard</title>",
         "<style>body{font:15px/1.45 Georgia,serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border-bottom:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#f3f1ec}.ci{color:#777;font-size:.85em}.b{font-weight:bold}.small{color:#555;font-size:.9em}code{background:#f3f1ec;padding:0 .25em}</style></head><body>",
         f"<h1>LSJ-Gold leaderboard</h1><p class=small>Lemmatizer accuracy on the <em>dictionary-cited stratum</em> of Ancient Greek: tokens that Liddell–Scott–Jones cites for a headword, relocated into First1KGreek editions. Version <b>{html.escape(version)}</b>. Numbers never change inside a version; a new author or system is a new version.</p>",
         "<table><tr><th>system</th><th>loci</th><th>match (accent-blind) %</th><th>strict %</th><th>article-neutral %</th>" + "".join(f"<th>{author_name(a)}<br><span class=small>n {scores['loci_per_author'][a]}</span></th>" for a in authors) + "</tr>"]
    for r in rows:
        h.append(f"<tr><td>{html.escape(r['label'])}</td><td>{r['scored']}</td><td class=b>{r['blind_pct']} <span class=ci>[{r['blind_ci'][0]}–{r['blind_ci'][1]}]</span></td><td>{r['strict_pct']}</td><td>{r['article_neutral_pct']}</td>"
                 + "".join(f"<td>{ci(r['by_author'].get(a))}</td>" for a in authors) + "</tr>")
    h.append("</table>")
    h.append("<h2>By LSJ sense tier and validation route</h2><table><tr><th>system</th><th>rich-entry headwords</th><th>single-sense headwords</th><th>loci validated by Morpheus</th><th>loci validated by LSJ's quoted form</th></tr>")
    for r in rows:
        t, v = r["by_lsj_tier"], r["by_validation"]
        h.append(f"<tr><td>{html.escape(r['label'])}</td><td>{ci(t.get('rich'))}</td><td>{ci(t.get('thin'))}</td><td>{ci(v.get('morpheus'))}</td><td>{ci(v.get('quoted'))}</td></tr>")
    h.append("</table>")
    sc = stats.get("status_counts", {})
    h.append(f"<h2>How the loci were made</h2><p class=small>{html.escape(stats.get('rule',''))}. Of {stats.get('citations_into_held_works','?')} LSJ citations into works held here: located {sc.get('located')}, ambiguous {sc.get('ambiguous')}, not located {sc.get('not_located')} (mostly Morpheus coverage, being filled), locator not in our edition {sc.get('locator_not_in_edition')}. Match = the system's lemma equals the LSJ headword after accent/case normalisation; strict = exact; article-neutral maps the article's forms to ὁ before comparing.</p>")
    h.append("<h2>Coverage</h2><p class=small>Which works LSJ cites, which are held here, and what a missing edition would add: <a href=coverage.html>the coverage map</a> (<a href=coverage.json>JSON</a>).</p>")
    h.append("<h2>Where the systems fail</h2><p class=small>Every miss grouped by mechanical pattern (same stem, surface returned, dialect ending …) and the most-missed headwords per system, as a list a maintainer can act on: <a href=failures.html>the failure catalogue</a> (<code>data/qc/lsjgold/failures/</code>).</p>")
    h.append("<h2>Honesty</h2><p class=small>LSJ cites what a 1940 lexicographer found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy. The Perseus LSJ XML is incomplete. Only works held in First1KGreek or Perseus editions are covered. odyCy's lemmas are a frozen 2026-07 run on First1K and a token-by-token run on the Perseus works; Dilemma is context-free on the surface; convention differences count against a system in the strict and blind columns and are partly undone in the article-neutral one. " + validation_sentence() + " No human reader has judged a sheet yet; the sheets and keys are in the repository.</p>")
    h.append("<h2>Submit a system</h2><p class=small>Write <code>&lt;stem&gt;.jsonl</code> token caches for the covered editions with your lemmas (<code>{i, surface, lemma}</code> per token) and open a pull request adding them under <code>submissions/&lt;system&gt;/</code>; CI scores them with <code>greek-lemma-audit lsjgold</code> (<code>pip install greek-lemma-audit</code>) and the row is added at the next version. Details: <code>submissions/README.md</code>. Data CC BY 4.0, code MIT. Cite: Pepperman, W. (2026), LSJ-Gold, Galen Density Project, DOI pending.</p>")
    h.append("</body></html>")
    (DOCS / "index.html").write_text("\n".join(h), encoding="utf-8")
    md = [f"# LSJ-Gold leaderboard — {version}", "", "| system | loci | blind % [95% CI] | strict % | article-neutral % | " + " | ".join(author_name(a) for a in authors) + " |",
          "|---|---|---|---|---|" + "---|" * len(authors)]
    for r in rows:
        md.append(f"| {r['label']} | {r['scored']} | **{r['blind_pct']}** [{r['blind_ci'][0]}–{r['blind_ci'][1]}] | {r['strict_pct']} | {r['article_neutral_pct']} | "
                  + " | ".join((f"{r['by_author'][a]['pct']}" if r['by_author'].get(a) else "—") for a in authors) + " |")
    md += ["", "Regenerate: `python pipeline/lsjgold/score.py [--system-cache DIR]` then `python pipeline/lsjgold/leaderboard.py`. Page: `docs/lsj-gold/index.html` (GitHub Pages)."]
    (DOCS / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
