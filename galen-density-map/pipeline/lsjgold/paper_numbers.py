"""LSJ-Gold note: write paper-lsjgold/numbers.tex, table_main.tex and table_authors.tex from the scored files, so every
number in the note traces to data/qc/lsjgold/*.json, outputs/t1/convention_summary.json and data/perseus_corpus/*.json.
Run after score.py: python -X utf8 pipeline/lsjgold/paper_numbers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsjgold"
OUT = GDM.parent / "paper-lsjgold"
sys.path.insert(0, str(HERE))
from leaderboard import LABELS  # noqa: E402
from lsjgold_names import author_name  # noqa: E402


def tex_escape(s: str) -> str:
    return s.replace("&", "\\&").replace("%", "\\%").replace("_", "\\_")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    scores = json.load((QC / "lsj_gold_scores.json").open(encoding="utf-8"))
    stats = json.load((QC / "relocation_stats.json").open(encoding="utf-8"))
    vdir = QC / ("validation_v03" if (QC / "validation_v03" / "validation_summary.json").exists() else "validation")
    val = json.load((vdir / "validation_summary.json").open(encoding="utf-8"))
    meta = json.load((vdir / "sheet_meta.json").open(encoding="utf-8"))
    conv = json.load((GDM / "outputs" / "t1" / "convention_summary.json").open(encoding="utf-8"))
    manifest = json.load((GDM / "data" / "perseus_corpus" / "manifest.json").open(encoding="utf-8"))
    counts = json.load((GDM / "data" / "perseus_corpus" / "token_counts.json").open(encoding="utf-8"))
    sysd = scores["systems"]
    sc = stats["status_counts"]
    n_loci = scores["n_loci"]
    authors = sorted(scores["loci_per_author"], key=lambda a: -scores["loci_per_author"][a])

    def pct(sysname, key="match_blind"):
        return sysd[sysname][key]["pct"] if sysname in sysd else None

    def ci(sysname):
        w = sysd[sysname]["match_blind"]["wilson95"]
        return f"{w[0]}--{w[1]}"

    def by_author(sysname, a):
        r = sysd.get(sysname, {}).get("by_author", {}).get(a)
        return r["pct"] if r else None

    neural = [s for s in ("odycy", "stanza_perseus", "stanza_proiel", "stoicheia") if s in sysd and sysd[s]["scored"] >= 1000]
    neural_pcts = sorted(pct(s) for s in neural)
    if len(neural_pcts) >= 2:
        neural_range = f"{round(neural_pcts[0])}--{round(neural_pcts[-1])}"
    elif neural_pcts:
        neural_range = f"{round(neural_pcts[0])}"
    else:
        neural_range = "?"
    downloaded = [w for w in manifest.get("works", manifest if isinstance(manifest, list) else []) if (w.get("downloaded") if isinstance(w, dict) else True)] if isinstance(manifest, (dict, list)) else []
    n_perseus = len(downloaded) or sum(1 for _ in counts) if isinstance(counts, dict) else len(downloaded)
    n_tokens_m = round(sum(v if isinstance(v, int) else v.get("tokens", 0) for v in counts.values()) / 1e6, 1) if isinstance(counts, dict) else 0
    readers = list(val["readers"].values())
    val_random_pct = round(min(r["relocation_precision_excl_unsure"]["pct"] for r in readers), 1)   # the stricter reader
    plants_caught = min(int(r["gate"]["plants_no"].split("/")[0]) for r in readers)
    anchors_caught = min(int(r["gate"]["anchors_yes"].split("/")[0]) for r in readers)
    morph = sysd["dilemma"]["by_validation"]["morpheus"]["n"] if "dilemma" in sysd else 0
    quoted = sysd["dilemma"]["by_validation"].get("quoted", {"n": 0})["n"] if "dilemma" in sysd else 0
    stanza_sentence = ""
    if "stanza_perseus" in sysd and sysd["stanza_perseus"]["scored"] >= 1000:
        stanza_sentence = f"; Stanza (Perseus / PROIEL models) {pct('stanza_perseus')}\\% / {pct('stanza_proiel')}\\%"

    def m(name, value):
        return f"\\newcommand{{\\{name}}}{{{value}}}\n"

    tex = "% written by pipeline/lsjgold/paper_numbers.py — do not edit\n"
    tex += m("nLoci", f"{n_loci:,}") + m("nAuthors", len(authors)) + m("nPerseusEditions", n_perseus) + m("nTokensM", n_tokens_m)
    tex += m("nCitationsHeld", f"{stats['citations_into_held_works']:,}")
    tex += m("nAmbiguous", f"{sc.get('ambiguous', 0):,}") + m("nNotLocated", f"{sc.get('not_located', 0):,}") + m("nLocatorMissing", f"{sc.get('locator_not_in_edition', 0):,}")
    tex += m("ruleText", tex_escape(stats["rule"]) + ".")
    tex += m("dilemmaBlind", pct("dilemma")) + m("dilemmaBlindRound", round(pct("dilemma") or 0)) + m("dilemmaCI", ci("dilemma"))
    tex += m("odycyBlind", pct("odycy")) + m("odycyCI", ci("odycy")) + m("odycyN", f"{sysd['odycy']['scored']:,}")
    tex += m("neuralRangeText", neural_range) + m("stanzaSentence", stanza_sentence)
    tex += m("dilemmaHippo", by_author("dilemma", "tlg0627") or "--") + m("odycyHippo", by_author("odycy", "tlg0627") or "--")
    tex += m("dilemmaNonnus", by_author("dilemma", "tlg2045") or "--") + m("dilemmaOppian", by_author("dilemma", "tlg0023") or "--") + m("dilemmaApollonius", by_author("dilemma", "tlg0001") or "--")
    tex += m("conventionShare", conv["share_by_class_pct"]["article"])
    def cites(sysname, tier):
        r = sysd.get(sysname, {}).get("by_lsj_citations", {}).get(tier)
        return r["pct"] if r else "--"
    tex += m("dilemmaHapax", cites("dilemma", "1")) + m("odycyHapax", cites("odycy", "1")) + m("stanzaHapax", cites("stanza_perseus", "1"))
    tex += m("dilemmaFreq", cites("dilemma", "6+")) + m("odycyFreq", cites("odycy", "6+")) + m("stanzaFreq", cites("stanza_perseus", "6+"))
    tex += m("nHapaxLoci", f"{sysd['dilemma']['by_lsj_citations'].get('1', {}).get('n', 0):,}" if "dilemma" in sysd else "--")
    tex += m("valRandom", val["n_random"]) + m("valControls", meta["n_anchors"] + meta["n_plants"]) + m("valRandomPct", val_random_pct) + m("valControlsCaught", plants_caught + anchors_caught) + m("valKappa", val.get("between_readers", {}).get("kappa", "--"))
    tex += m("valMorpheusPct", round(100 * morph / max(1, morph + quoted), 1)) + m("valQuotedPct", round(100 * quoted / max(1, morph + quoted), 1))
    OUT.mkdir(exist_ok=True)
    (OUT / "numbers.tex").write_text(tex, encoding="utf-8")

    # main table
    rows = sorted(sysd.items(), key=lambda kv: -(kv[1]["match_blind"]["pct"] or 0))
    t = ["\\begin{table}[t]\\centering\\small", "\\begin{tabular}{lrrrr}", "\\toprule",
         "system & loci & match \\% [95\\% CI] & strict \\% & article-neutral \\% \\\\", "\\midrule"]
    for name, b in rows:
        w = b["match_blind"]["wilson95"]
        t.append(f"{tex_escape(LABELS.get(name, name))} & {b['scored']:,} & \\textbf{{{b['match_blind']['pct']}}} [{w[0]}--{w[1]}] & {b['match_strict']['pct']} & {b['match_article_neutral']['pct']} \\\\")
    t += ["\\bottomrule", "\\end{tabular}", f"\\caption{{LSJ-Gold {scores['date']}: accent-blind headword match on the {n_loci:,} relocated loci; a system is scored only on loci its caches cover.}}", "\\end{table}"]
    (OUT / "table_main.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    # per-author table (systems with any author row)
    systems = [n for n, b in rows if b["by_author"]]
    t = ["\\begin{table}[t]\\centering\\small", "\\begin{tabular}{lr" + "r" * len(systems) + "}", "\\toprule",
         "author & loci & " + " & ".join(tex_escape(s) for s in systems) + " \\\\", "\\midrule"]
    for a in authors:
        cells = []
        for s in systems:
            r = sysd[s]["by_author"].get(a)
            cells.append(f"{r['pct']}" if r else "--")
        t.append(f"{author_name(a)} & {scores['loci_per_author'][a]:,} & " + " & ".join(cells) + " \\\\")
    t += ["\\bottomrule", "\\end{tabular}", "\\caption{Accent-blind match by author (loci with at least 100 scored rows per system; -- otherwise).}", "\\end{table}"]
    (OUT / "table_authors.tex").write_text("\n".join(t) + "\n", encoding="utf-8")

    # by how often LSJ cites the headword
    t = ["\\begin{table}[t]\\centering\\small", "\\begin{tabular}{lrrr}", "\\toprule", "system & cited once & cited 2--5 times & cited 6 or more \\\\", "\\midrule"]
    for name, b in rows:
        c = b.get("by_lsj_citations", {})
        cells = [f"{c[k]['pct']} ({c[k]['n']:,})" if k in c else "--" for k in ("1", "2-5", "6+")]
        t.append(f"{tex_escape(LABELS.get(name, name))} & " + " & ".join(cells) + " \\\\")
    t += ["\\bottomrule", "\\end{tabular}", "\\caption{Accent-blind match by how often LSJ cites the headword anywhere (its hapax stratum first); N in parentheses.}", "\\end{table}"]
    (OUT / "table_cites.tex").write_text("\n".join(t) + "\n", encoding="utf-8")
    print(tex)


if __name__ == "__main__":
    main()
