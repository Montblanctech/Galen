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
NAMES = {"tlg0085": "Aeschylus", "tlg0011": "Sophocles", "tlg0627": "Hippocrates", "tlg0086": "Aristotle", "tlg0057": "Galen", "tlg0031": "New Testament",
         "tlg0012": "Homer", "tlg0016": "Herodotus", "tlg0003": "Thucydides", "tlg0059": "Plato", "tlg0006": "Euripides", "tlg0019": "Aristophanes",
         "tlg0032": "Xenophon", "tlg0543": "Polybius", "tlg0099": "Strabo", "tlg0008": "Athenaeus", "tlg0001": "Apollonius Rhodius", "tlg0005": "Theocritus",
         "tlg0033": "Pindar", "tlg0014": "Demosthenes", "tlg0020": "Hesiod", "tlg0023": "Oppian", "tlg2045": "Nonnus", "tlg0526": "Josephus", "tlg0525": "Pausanias",
         "tlg0004": "Diogenes Laertius", "tlg0060": "Diodorus", "tlg0007": "Plutarch", "tlg0062": "Lucian", "tlg0010": "Isocrates", "tlg0028": "Antiphon"}
LABELS = {"odycy": "odyCy 0.7.0 (grc_odycy_joint_trf)", "dilemma": "Dilemma 1.3.15 (Open Greek, lsj convention)",
          "stanza_perseus": "Stanza 1.14 grc-perseus", "stanza_proiel": "Stanza 1.14 grc-proiel", "stoicheia": "Stoicheia tagger-parser (2026)"}


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
          "relocation": stats.get("status_counts"), "rule": stats.get("rule"), "rows": rows,
          "citation": "Pepperman, W. (2026). LSJ-Gold: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek. Galen Density Project. DOI: pending",
          "how_to_submit": "produce <stem>.jsonl token files for the covered First1K editions with your lemmas, run pipeline/lsjgold/score.py --system-cache <dir>, then pipeline/lsjgold/leaderboard.py; open a pull request with the three output files"}
    (DOCS / "leaderboard.json").write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")

    def ci(r):
        return f"{r['pct']} <span class=ci>[{r['wilson95'][0]}–{r['wilson95'][1]}]</span>" if r else "—"

    h = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>LSJ-Gold leaderboard</title>",
         "<style>body{font:15px/1.45 Georgia,serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border-bottom:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#f3f1ec}.ci{color:#777;font-size:.85em}.b{font-weight:bold}.small{color:#555;font-size:.9em}code{background:#f3f1ec;padding:0 .25em}</style></head><body>",
         f"<h1>LSJ-Gold leaderboard</h1><p class=small>Lemmatizer accuracy on the <em>dictionary-cited stratum</em> of Ancient Greek: tokens that Liddell–Scott–Jones cites for a headword, relocated into First1KGreek editions. Version <b>{html.escape(version)}</b>. Numbers never change inside a version; a new author or system is a new version.</p>",
         "<table><tr><th>system</th><th>loci</th><th>match (accent-blind) %</th><th>strict %</th><th>article-neutral %</th>" + "".join(f"<th>{NAMES.get(a,a)}<br><span class=small>n {scores['loci_per_author'][a]}</span></th>" for a in authors) + "</tr>"]
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
    h.append("<h2>Honesty</h2><p class=small>LSJ cites what a 1940 lexicographer found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy. The Perseus LSJ XML is incomplete. Only works held in First1K editions are covered. odyCy's lemmas are a frozen 2026-07 run; Dilemma is context-free on the surface; convention differences count against a system in the strict and blind columns and are partly undone in the article-neutral one. No human has validated the relocation yet; the blind salted sheet is in the repository.</p>")
    h.append("<h2>Submit a system</h2><p class=small><code>pip install greek-lemma-audit</code>; write <code>&lt;stem&gt;.jsonl</code> token files for the covered editions with your lemmas; run <code>pipeline/lsjgold/score.py --system-cache &lt;dir&gt;</code> and <code>pipeline/lsjgold/leaderboard.py</code>; open a pull request. Data CC BY 4.0, code MIT. Cite: Pepperman, W. (2026), LSJ-Gold, Galen Density Project, DOI pending.</p>")
    h.append("</body></html>")
    (DOCS / "index.html").write_text("\n".join(h), encoding="utf-8")
    md = [f"# LSJ-Gold leaderboard — {version}", "", "| system | loci | blind % [95% CI] | strict % | article-neutral % | " + " | ".join(NAMES.get(a, a) for a in authors) + " |",
          "|---|---|---|---|---|" + "---|" * len(authors)]
    for r in rows:
        md.append(f"| {r['label']} | {r['scored']} | **{r['blind_pct']}** [{r['blind_ci'][0]}–{r['blind_ci'][1]}] | {r['strict_pct']} | {r['article_neutral_pct']} | "
                  + " | ".join((f"{r['by_author'][a]['pct']}" if r['by_author'].get(a) else "—") for a in authors) + " |")
    md += ["", "Regenerate: `python pipeline/lsjgold/score.py [--system-cache DIR]` then `python pipeline/lsjgold/leaderboard.py`. Page: `docs/lsj-gold/index.html` (GitHub Pages)."]
    (DOCS / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
