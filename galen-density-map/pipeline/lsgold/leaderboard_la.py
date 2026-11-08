"""LS-Gold, stage 3 — the standing Latin leaderboard: one command regenerates a static page + JSON from the scores.

Reads data/qc/lsgold/ls_gold_scores.json and relocation_stats.json, writes docs/ls-gold/index.html (GitHub Pages
ready, no external assets), docs/ls-gold/leaderboard.json and docs/ls-gold/README.md. Every row carries N and a
Wilson 95% interval; the strict figure stands beside the headline blind figure; the version string is the gold file's
row count + date so a number never silently changes. Baseline rows (the oracles' own first choice) are marked.

Run: python -X utf8 -I pipeline/lsgold/leaderboard_la.py
"""
from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_la import author_names  # noqa: E402

GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsgold"
DOCS = GDM.parent / "docs" / "ls-gold"
LABELS = {"stanza_ittb": "Stanza 1.15 la-ittb", "stanza_perseus": "Stanza 1.15 la-perseus", "stanza_proiel": "Stanza 1.15 la-proiel",
          "stanza_llct": "Stanza 1.15 la-llct", "stanza_udante": "Stanza 1.15 la-udante", "latincy_lg": "LatinCy la_core_web_lg",
          "latincy_md": "LatinCy la_core_web_md", "latincy_sm": "LatinCy la_core_web_sm", "cltk": "CLTK 1.5 Latin backoff lemmatizer",
          "collatinus_first": "Collatinus, first analysis (baseline)", "whitaker_first": "Whitaker's Words, first analysis (baseline)"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    scores = json.load((QC / "ls_gold_scores.json").open(encoding="utf-8"))
    stats = json.load((QC / "relocation_stats.json").open(encoding="utf-8"))
    n_gold = sum(1 for _ in csv.DictReader((QC / "ls_gold_v0.csv").open(encoding="utf-8")))
    names = author_names()
    version = f"v0 ({n_gold} loci, {scores['date']})"
    authors = [a for a in sorted(scores["loci_per_author"], key=lambda a: -scores["loci_per_author"][a]) if scores["loci_per_author"][a] >= 100]
    rows = []
    for name, b in sorted(scores["systems"].items(), key=lambda kv: (kv[1].get("baseline", False), -(kv[1]["match_blind"]["pct"] or 0))):
        rows.append({"system": name, "label": LABELS.get(name, name), "baseline": b.get("baseline", False), "scored": b["scored"], "missing": b["missing"],
                     "blind_pct": b["match_blind"]["pct"], "blind_ci": b["match_blind"]["wilson95"], "strict_pct": b["match_strict"]["pct"],
                     "by_author": {a: b["by_author"].get(a) for a in authors}, "by_validation": b["by_validation"], "by_ls_citations": b.get("by_ls_citations", {})})
    DOCS.mkdir(parents=True, exist_ok=True)
    lb = {"benchmark": "LS-Gold", "version": version, "date": scores["date"], "n_loci": n_gold, "loci_per_author": scores["loci_per_author"],
          "relocation": stats.get("status_counts"), "rule": stats.get("rule"), "rows": rows, "author_names": {a: names.get(a, a) for a in authors},
          "citation": "Pepperman, W. (2026). LS-Gold: lemmatizer accuracy on the dictionary-cited stratum of Latin. Galen Density Project (LSJ-Gold's Latin twin), https://github.com/Montblanctech/Galen",
          "how_to_submit": "open a pull request adding submissions/ls-gold/<system>/<edition_stem>.jsonl token caches ({i, surface, lemma} per token of the project's Latin token stream, data/latin_corpus/tokens/); the maintainers score them with pipeline/lsgold/score_la.py and add the row at the next version"}
    (DOCS / "leaderboard.json").write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")

    def ci(r):
        return f"{r['pct']} <span class=ci>[{r['wilson95'][0]}–{r['wilson95'][1]}]</span>" if r else "—"

    h = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>LS-Gold leaderboard (Latin)</title>",
         "<style>body{font:15px/1.45 Georgia,serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.93em}th,td{border-bottom:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#f3f1ec}.ci{color:#777;font-size:.85em}.b{font-weight:bold}.small{color:#555;font-size:.9em}.base td{color:#666;font-style:italic}code{background:#f3f1ec;padding:0 .25em}</style></head><body>",
         f"<h1>LS-Gold leaderboard</h1><p class=small>Latin lemmatizer accuracy on the <em>dictionary-cited stratum</em>: tokens that Lewis &amp; Short cites for a headword, relocated into Perseus canonical-latinLit editions and validated by two independent morphological analysers. The Latin twin of <a href=../lsj-gold/>LSJ-Gold</a>. Version <b>{html.escape(version)}</b>. Numbers never change inside a version; a new author or system is a new version.</p>",
         "<table><tr><th>system</th><th>loci</th><th>match (blind) %</th><th>strict %</th>" + "".join(f"<th>{html.escape(names.get(a, a))}<br><span class=small>n {scores['loci_per_author'][a]}</span></th>" for a in authors) + "</tr>"]
    for r in rows:
        cls = " class=base" if r["baseline"] else ""
        h.append(f"<tr{cls}><td>{html.escape(r['label'])}</td><td>{r['scored']}</td><td class=b>{r['blind_pct']} <span class=ci>[{r['blind_ci'][0]}–{r['blind_ci'][1]}]</span></td><td>{r['strict_pct']}</td>"
                 + "".join(f"<td>{ci(r['by_author'].get(a))}</td>" for a in authors) + "</tr>")
    h.append("</table>")
    h.append("<h2>By validation route and by how often Lewis &amp; Short cites the headword</h2><p class=small>A locus is validated when Collatinus's analyses of the token contain the headword (route <em>collatinus</em>), else when Whitaker's Words' do (<em>whitaker</em>), else when the token equals the form L&amp;S quotes beside the citation and neither analyser knows the token (<em>quoted</em>). The two baseline rows are those analysers' own first choice, so their figures on their own route are circular and printed for scale only.</p>"
             "<table><tr><th>system</th><th>validated by Collatinus</th><th>validated by Whitaker</th><th>validated by the quoted form</th><th>headword cited once</th><th>cited 2–5 times</th><th>cited 6 or more</th></tr>")
    for r in rows:
        v, c = r["by_validation"], r["by_ls_citations"]
        cls = " class=base" if r["baseline"] else ""
        h.append(f"<tr{cls}><td>{html.escape(r['label'])}</td><td>{ci(v.get('collatinus'))}</td><td>{ci(v.get('whitaker'))}</td><td>{ci(v.get('quoted'))}</td>"
                 f"<td>{ci(c.get('1'))} <span class=small>n {c.get('1', {}).get('n', '')}</span></td><td>{ci(c.get('2-5'))} <span class=small>n {c.get('2-5', {}).get('n', '')}</span></td><td>{ci(c.get('6+'))} <span class=small>n {c.get('6+', {}).get('n', '')}</span></td></tr>")
    h.append("</table>")
    sc = stats.get("status_counts", {})
    h.append(f"<h2>How the loci were made</h2><p class=small>{html.escape(stats.get('rule', ''))}. Of {stats.get('citations_into_held_works', '?')} Lewis &amp; Short citations into works held here: located {sc.get('located')}, ambiguous {sc.get('ambiguous')}, not located {sc.get('not_located')}, locator not in our edition {sc.get('locator_not_in_edition')}. Match = the system's lemma equals the L&amp;S headword after case, diacritic, u/v, i/j and homograph-digit normalisation; strict keeps u/v and i/j as printed. The token stream is the project's own (<code>data/latin_corpus/tokens/</code>); every system was run on it pre-tokenised, so there is no alignment step.</p>")
    h.append("<h2>Honesty</h2><p class=small>Lewis &amp; Short (1879) cites what its lexicographers found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy, and treebank test scores are not comparable with it. The Perseus L&amp;S XML is incomplete and its CTS tags cover 74% of its citations. Only works with a Latin edition in canonical-latinLit are covered; L&amp;S was written against older editions, so locators drift and the relocation rule (unit ±1) absorbs some of that. The validation oracles are themselves lexicon-driven analysers: a token neither analyser knows and that L&amp;S does not quote is not a locus, which biases the set toward forms the lexica cover. No human reader has judged a sheet of these loci yet. Nothing here patches any system's output; every figure traces to a row in <code>data/qc/lsgold/ls_gold_scored.csv</code>.</p>")
    h.append("<h2>Submit a system</h2><p class=small>Write <code>&lt;edition_stem&gt;.jsonl</code> caches for the covered editions with your lemmas (<code>{i, surface, lemma}</code> per token of the project's token stream) and open a pull request adding them under <code>submissions/ls-gold/&lt;system&gt;/</code>. Texts CC BY-SA 4.0 (Perseus Digital Library); gold CC BY-SA 4.0 (derived from the Perseus Lewis &amp; Short); code MIT.</p>")
    h.append("</body></html>")
    (DOCS / "index.html").write_text("\n".join(h), encoding="utf-8")
    md = [f"# LS-Gold leaderboard — {version}", "", "| system | loci | blind % [95% CI] | strict % | " + " | ".join(names.get(a, a) for a in authors) + " |",
          "|---|---|---|---|" + "---|" * len(authors)]
    for r in rows:
        md.append(f"| {r['label']} | {r['scored']} | **{r['blind_pct']}** [{r['blind_ci'][0]}–{r['blind_ci'][1]}] | {r['strict_pct']} | "
                  + " | ".join((f"{r['by_author'][a]['pct']}" if r['by_author'].get(a) else "—") for a in authors) + " |")
    md += ["", "Regenerate: `python pipeline/lsgold/score_la.py` then `python pipeline/lsgold/leaderboard_la.py`. Page: `docs/ls-gold/index.html` (GitHub Pages)."]
    (DOCS / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
