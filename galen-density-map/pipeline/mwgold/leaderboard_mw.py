"""MW-Gold, stage 5 — the standing Sanskrit leaderboard: one command regenerates a static page + JSON from the scores.

Reads data/qc/mwgold/mw_gold_scores.json and relocation_stats.json, writes docs/mw-gold/index.html (GitHub Pages
ready, no external assets), docs/mw-gold/leaderboard.json and docs/mw-gold/README.md. Every row carries N and a
Wilson 95% interval; the strict figure stands beside the headline blind figure; rows trained on the DCS carry that
note; the baseline row is marked; the version string is the gold file's row count + date.

Run: python -X utf8 -I pipeline/mwgold/leaderboard_mw.py
"""
from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_mw import TEXT_NAMES  # noqa: E402

GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "mwgold"
DOCS = GDM.parent / "docs" / "mw-gold"
LABELS = {"byt5": "ByT5-Sanskrit multitask (Nehrdich, Hellwig, Keutzer 2024), local CPU", "stanza_sa": "Stanza 1.15 sa (UD_Sanskrit-Vedic)",
          "vidyut_cheda": "vidyut-cheda 0.4.0 (Ambuda segmenter-tagger)", "vidyut_first": "vidyut-kosha, first analysis (baseline)"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    scores = json.load((QC / "mw_gold_scores.json").open(encoding="utf-8"))
    stats = json.load((QC / "relocation_stats.json").open(encoding="utf-8"))
    n_gold = sum(1 for _ in csv.DictReader((QC / "mw_gold_v0.csv").open(encoding="utf-8")))
    version = f"v0 ({n_gold} loci, {scores['date']})"
    texts = [t for t in sorted(scores["loci_per_text"], key=lambda t: -scores["loci_per_text"][t]) if scores["loci_per_text"][t] >= 100]
    rows = []
    for name, b in sorted(scores["systems"].items(), key=lambda kv: (kv[1].get("baseline", False), -(kv[1]["match_blind"]["pct"] or 0))):
        rows.append({"system": name, "label": LABELS.get(name, name), "baseline": b.get("baseline", False), "trained_on_dcs": b.get("trained_on_dcs", ""),
                     "scored": b["scored"], "missing": b["missing"], "blind_pct": b["match_blind"]["pct"], "blind_ci": b["match_blind"]["wilson95"],
                     "strict_pct": b["match_strict"]["pct"], "by_text": {t: b["by_text"].get(t) for t in texts}, "by_validation": b["by_validation"],
                     "by_span": b["by_span"], "by_window": b["by_window"], "by_mw_citations": b.get("by_mw_citations", {})})
    DOCS.mkdir(parents=True, exist_ok=True)
    lb = {"benchmark": "MW-Gold", "version": version, "date": scores["date"], "n_loci": n_gold, "loci_per_text": scores["loci_per_text"],
          "relocation": stats.get("status_counts"), "rule": stats.get("rule"), "rows": rows, "text_names": {t: TEXT_NAMES.get(t, t) for t in texts},
          "citation": "Pepperman, W. (2026). MW-Gold: lemmatizer accuracy on the dictionary-cited stratum of Sanskrit. Galen Density Project (LSJ-Gold's Sanskrit twin), https://github.com/Montblanctech/Galen",
          "how_to_submit": "open a pull request adding submissions/mw-gold/<system>/<stem>.jsonl token caches ({i, surface, lemma} per DCS word of the project's token stream, data/sanskrit_corpus/tokens/); the maintainers score them with pipeline/mwgold/score_mw.py and add the row at the next version"}
    (DOCS / "leaderboard.json").write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")

    def ci(r):
        return f"{r['pct']} <span class=ci>[{r['wilson95'][0]}–{r['wilson95'][1]}]</span>" if r else "—"

    h = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>MW-Gold leaderboard (Sanskrit)</title>",
         "<style>body{font:15px/1.45 Georgia,serif;max-width:1150px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.93em}th,td{border-bottom:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#f3f1ec}.ci{color:#777;font-size:.85em}.b{font-weight:bold}.small{color:#555;font-size:.9em}.base td{color:#666;font-style:italic}.dcs{color:#8a3b00;font-size:.85em}code{background:#f3f1ec;padding:0 .25em}</style></head><body>",
         f"<h1>MW-Gold leaderboard</h1><p class=small>Sanskrit lemmatizer accuracy on the <em>dictionary-cited stratum</em>: the words Monier-Williams (1899) cites for a headword, relocated into the Digital Corpus of Sanskrit (DCS) and validated by the DCS annotators' lemma or by an independent Pāṇinian generator (vidyut-kosha). The Sanskrit twin of <a href=../lsj-gold/>LSJ-Gold</a> and <a href=../ls-gold/>LS-Gold</a>. Version <b>{html.escape(version)}</b>. Numbers never change inside a version; a new text or system is a new version.</p>",
         "<p class=small><b>Read this first.</b> The only human-lemmatized Sanskrit corpus (DCS) is also the training data of the strongest systems. Rows marked <span class=dcs>trained on DCS</span> are scored on their own training distribution and, for ByT5-Sanskrit, on sentences it was trained on: those figures are consistency with the DCS annotators, not generalisation. The rows not trained on DCS, and the <em>vidyut</em> validation route, are the independent part of the table.</p>",
         "<table><tr><th>system</th><th>loci</th><th>match (blind) %</th><th>strict %</th>" + "".join(f"<th>{html.escape(TEXT_NAMES.get(t, t))}<br><span class=small>n {scores['loci_per_text'][t]}</span></th>" for t in texts) + "</tr>"]
    for r in rows:
        cls = " class=base" if r["baseline"] else ""
        note = f"<br><span class=dcs>trained on DCS: {html.escape(r['trained_on_dcs'])}</span>" if r["trained_on_dcs"] else ""
        h.append(f"<tr{cls}><td>{html.escape(r['label'])}{note}</td><td>{r['scored']}</td><td class=b>{r['blind_pct']} <span class=ci>[{r['blind_ci'][0]}–{r['blind_ci'][1]}]</span></td><td>{r['strict_pct']}</td>"
                 + "".join(f"<td>{ci(r['by_text'].get(t))}</td>" for t in texts) + "</tr>")
    h.append("</table>")
    h.append("<h2>By validation route, by span, by window and by how often Monier-Williams cites the headword</h2><p class=small>A locus is validated when the DCS lemma of the word equals the headword (<em>dcs</em>), when a span of compound members joins to the headword (<em>dcs_cpd</em>), when a Vedic verb separated from its preverb (tmesis) carries the root of MW's compound verb (<em>dcs_tmesis</em>: DCS lemmatizes the bare root, so DCS-trained systems are expected to miss these), when vidyut-kosha's analyses of the word contain the headword although the DCS lemma differs (<em>vidyut</em>), or when the word itself is the headword, as with MW's adverb entries (<em>surface</em>). Chapter-window loci come from the Vedic prose texts whose DCS chapter is the unit MW cites. The baseline row is the vidyut generator's own first analysis, so its figure on the vidyut route is circular and printed for scale only.</p>"
             "<table><tr><th>system</th><th>dcs</th><th>dcs_cpd</th><th>dcs_tmesis</th><th>vidyut</th><th>surface</th><th>single word</th><th>compound span</th><th>verse window</th><th>chapter window</th><th>headword cited once</th><th>2–5</th><th>6+</th></tr>")
    for r in rows:
        v, s, w, c = r["by_validation"], r["by_span"], r["by_window"], r["by_mw_citations"]
        cls = " class=base" if r["baseline"] else ""
        h.append(f"<tr{cls}><td>{html.escape(r['label'])}</td><td>{ci(v.get('dcs'))}</td><td>{ci(v.get('dcs_cpd'))}</td><td>{ci(v.get('dcs_tmesis'))}</td><td>{ci(v.get('vidyut'))}</td><td>{ci(v.get('surface'))}</td>"
                 f"<td>{ci(s.get('single'))}</td><td>{ci(s.get('compound'))}</td><td>{ci(w.get('verse'))}</td><td>{ci(w.get('chapter'))}</td>"
                 f"<td>{ci(c.get('1'))} <span class=small>n {c.get('1', {}).get('n', '')}</span></td><td>{ci(c.get('2-5'))} <span class=small>n {c.get('2-5', {}).get('n', '')}</span></td><td>{ci(c.get('6+'))} <span class=small>n {c.get('6+', {}).get('n', '')}</span></td></tr>")
    h.append("</table>")
    sc = stats.get("status_counts", {})
    h.append(f"<h2>How the loci were made</h2><p class=small>{html.escape(stats.get('rule', ''))}. Of {stats.get('citations_in_scope', '?')} Monier-Williams citations into the texts in scope: located {sc.get('located')}, ambiguous {sc.get('ambiguous')}, not located {sc.get('not_located')}, cited verse not in our edition {sc.get('locator_not_in_edition')}. The token is the DCS word (sandhi resolved, compounds split by the annotators); the DCS dump carries no verse numbers, so every sentence was aligned to a verse-numbered open edition first (GRETIL, Hellwig's Vedic Prose Corpus, ambuda-org/dcs); every system was run on the DCS words pre-segmented, so there is no segmentation step in the scoring.</p>")
    h.append("<h2>Honesty</h2><p class=small>Monier-Williams cites what its lexicographers found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy, and treebank test scores are not comparable with it. Only texts held by the DCS with a verse-numbered open edition are covered; the Mahābhārata, Rāmāyaṇa and Harivaṃśa are absent because MW cites editions whose numbering the critical editions do not share. The verse alignment is a step the Greek and Latin twins did not need and its error enters the gold; the blind check measures the headword, not the passage. The gold lemma is the DCS annotators' lemma, so agreement is bounded by one annotation tradition. No human reader has judged a sheet of these loci yet. Nothing here patches any system's output; every figure traces to a row in <code>data/qc/mwgold/mw_gold_scored.csv</code>.</p>")
    h.append("<h2>Submit a system</h2><p class=small>Write <code>&lt;stem&gt;.jsonl</code> caches for the covered texts with your lemmas (<code>{i, surface, lemma}</code> per DCS word of the project's token stream) and open a pull request adding them under <code>submissions/mw-gold/&lt;system&gt;/</code>. Texts: DCS CC BY 4.0 (Oliver Hellwig); gold CC BY-SA 4.0 (derived from the Cologne Digital Sanskrit Dictionaries' Monier-Williams); code MIT.</p>")
    h.append("</body></html>")
    (DOCS / "index.html").write_text("\n".join(h), encoding="utf-8")
    md = [f"# MW-Gold leaderboard — {version}", "", "| system | loci | blind % [95% CI] | strict % | " + " | ".join(TEXT_NAMES.get(t, t) for t in texts) + " |",
          "|---|---|---|---|" + "---|" * len(texts)]
    for r in rows:
        md.append(f"| {r['label']}{' — trained on DCS' if r['trained_on_dcs'] else ''} | {r['scored']} | **{r['blind_pct']}** [{r['blind_ci'][0]}–{r['blind_ci'][1]}] | {r['strict_pct']} | "
                  + " | ".join((f"{r['by_text'][t]['pct']}" if r['by_text'].get(t) else "—") for t in texts) + " |")
    md += ["", "Regenerate: `python pipeline/mwgold/score_mw.py` then `python pipeline/mwgold/leaderboard_mw.py`. Page: `docs/mw-gold/index.html` (GitHub Pages)."]
    (DOCS / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
