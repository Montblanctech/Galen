"""LSJ-Gold failure catalogue: where Dilemma and odyCy miss the dictionary headword, grouped by mechanical string rules.

Reads data/qc/lsjgold/lsj_gold_scored.csv; writes data/qc/lsjgold/failures/ (CSVs + README.md) and docs/lsj-gold/failures.html.
Report only: nothing here patches a lemmatizer. Classes are string rules, not linguistic judgements.
"""
from __future__ import annotations

import csv
import html
import io
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lsjgold_names import GDM, author_name  # noqa: E402

SRC = GDM / "data" / "qc" / "lsjgold" / "lsj_gold_scored.csv"
OUT = GDM / "data" / "qc" / "lsjgold" / "failures"
DOC = GDM.parent / "docs" / "lsj-gold" / "failures.html"
SYSTEMS = ["dilemma", "odycy"]

CLASSES = ["article_convention", "accent_only", "same_stem", "surface_returned", "proper_name", "dialect_ending", "other"]
RULES = {
    "article_convention": "Both headword and produced lemma, after accent/breathing stripping, are forms of the article (ο η το του της τω τον την οι αι τα των τοις ταις τους τας τοιν) and they differ: e.g. headword ὁ, lemma ἡ/τό, or the reverse.",
    "accent_only": "Headword and lemma are equal after stripping accents/breathings (NFD, drop combining marks, lowercase, ς->σ) but not equal before stripping. Blind match already ignores accents, so ~0 is expected.",
    "same_stem": "Headword and lemma both have at least 4 letters and their first 4 letters are equal after accent stripping.",
    "surface_returned": "Lemma equals the surface form after accent stripping: the system returned the form unchanged.",
    "proper_name": "Headword begins with a capital letter.",
    "dialect_ending": "Surface (tonal marks stripped, quantity marks and iota subscript kept) ends in one of: -οισι, -ῃσι, -αισι, -εσσι, -οιο, -ᾰο, -ηθεν, -οθεν, -ονδε, -ῑο. Doric -ᾶς genitive is not detected.",
    "other": "None of the above rules fired.",
}
ORDER_TEXT = "Rules are applied in this order, first match wins: " + ", ".join(CLASSES) + "."
ARTICLE = {"ο", "η", "το", "του", "της", "τω", "τον", "την", "οι", "αι", "τα", "των", "τοις", "ταις", "τους", "τας", "τοιν"}
TONAL = {"́", "̀", "͂", "̓", "̔", "̈"}
ENDINGS = [unicodedata.normalize("NFD", e) for e in ["οισι", "ῃσι", "αισι", "εσσι", "οιο", "ᾰο", "ηθεν", "οθεν", "ονδε", "ῑο"]]
EXCLUDE_MAINT = {"article_convention", "accent_only", "proper_name"}


def strip(s: str) -> str:
    d = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in d if not unicodedata.combining(c)).lower().replace("ς", "σ")


def tonal_strip(s: str) -> str:
    d = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in d if c not in TONAL).lower().replace("ς", "σ")


def classify(head: str, lemma: str, surface: str) -> str:
    h, l, s = strip(head), strip(lemma), strip(surface)
    if h in ARTICLE and l in ARTICLE:
        return "article_convention"
    if h == l and head != lemma:
        return "accent_only"
    if len(h) >= 4 and len(l) >= 4 and h[:4] == l[:4]:
        return "same_stem"
    if l == s:
        return "surface_returned"
    if head[:1].isupper():
        return "proper_name"
    ts = tonal_strip(surface)
    if any(ts.endswith(e) for e in ENDINGS):
        return "dialect_ending"
    return "other"


def write_csv(path: Path, header: list, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def fmt_pairs(c: Counter, k: int) -> str:
    return "; ".join(f"{h} -> {l} ({n})" for (h, l), n in c.most_common(k))


def md_table(header: list, rows: list) -> str:
    esc = lambda x: str(x).replace("|", "\\|")
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(esc(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def csv_line(vals: list) -> str:
    b = io.StringIO()
    csv.writer(b, lineterminator="").writerow(vals)
    return b.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    with open(SRC, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"read {len(rows)} rows from {SRC}")
    res = {}
    for sysn in SYSTEMS:
        scored = misses = 0
        by_auth_scored = Counter()
        by_auth_pairs = defaultdict(Counter)
        by_auth_miss = Counter()
        cls_rows = defaultdict(list)
        for r in rows:
            lem = r[f"{sysn}_lemma"]
            b = r[f"{sysn}_blind"]
            if not lem or b == "":
                continue
            scored += 1
            by_auth_scored[r["author"]] += 1
            if float(b) != 0:
                continue
            misses += 1
            by_auth_miss[r["author"]] += 1
            by_auth_pairs[r["author"]][(r["headword"], lem)] += 1
            cls_rows[classify(r["headword"], lem, r["surface"])].append(r)
        n_miss = sum(len(v) for v in cls_rows.values())
        assert n_miss == misses
        # by author
        auth_rows = []
        for a, n in by_auth_scored.items():
            m = by_auth_miss[a]
            auth_rows.append([a, author_name(a), n, m, f"{100 * m / n:.2f}", fmt_pairs(by_auth_pairs[a], 5)])
        auth_rows.sort(key=lambda x: (-x[3], x[0]))
        write_csv(OUT / f"{sysn}_by_author.csv", ["author", "author_name", "n_scored", "n_miss", "miss_pct", "top5_headword_to_lemma"], auth_rows)
        # patterns
        pat_rows, pat_tab = [], []
        for c in CLASSES:
            lst = cls_rows.get(c, [])
            ex, seen = [], set()
            for r in lst:
                if r["headword"] in seen:
                    continue
                seen.add(r["headword"])
                ex.append(r)
                if len(ex) == 3:
                    break
            exs = [[r["headword"], r["surface"], r[f"{sysn}_lemma"], author_name(r["author"]), r["locator"]] for r in ex]
            share = f"{100 * len(lst) / n_miss:.2f}"
            pat_tab.append((c, len(lst), share, exs))
            if not exs:
                pat_rows.append([c, RULES[c], len(lst), share, "", "", "", "", ""])
            for i, e in enumerate(exs):
                pat_rows.append([c, RULES[c], len(lst), share, i + 1, *e])
        write_csv(OUT / f"{sysn}_patterns.csv", ["class", "rule", "count", "share_pct", "example_n", "headword", "surface", "lemma", "author", "locator"], pat_rows)
        # top headwords
        hc, hl, ha = Counter(), defaultdict(Counter), defaultdict(Counter)
        first = {}
        for c, lst in cls_rows.items():
            for r in lst:
                h = r["headword"]
                hc[h] += 1
                hl[h][r[f"{sysn}_lemma"]] += 1
                ha[h][author_name(r["author"])] += 1
        top = sorted(hc.items(), key=lambda kv: (-kv[1], kv[0]))
        top_rows = [[h, n, "; ".join(f"{l} ({k})" for l, k in hl[h].most_common(3)), "; ".join(f"{a} ({k})" for a, k in ha[h].most_common(5))] for h, n in top[:200]]
        write_csv(OUT / f"{sysn}_top_headwords.csv", ["headword", "n_miss", "top3_produced_lemmas", "authors_top5"], top_rows)
        # maintainers: exclude article/accent/proper_name
        mc, ml, mloc = Counter(), defaultdict(Counter), {}
        for c, lst in cls_rows.items():
            if c in EXCLUDE_MAINT:
                continue
            for r in lst:
                h = r["headword"]
                mc[h] += 1
                ml[h][r[f"{sysn}_lemma"]] += 1
                mloc.setdefault(h, r)
        maint = []
        for h, n in sorted(mc.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
            r = mloc[h]
            maint.append([h, n, ml[h].most_common(1)[0][0], f"{author_name(r['author'])} {r['locator']}", r["surface"]])
        res[sysn] = dict(scored=scored, n_miss=n_miss, auth=auth_rows, pat=pat_tab, top=top_rows, maint=maint)
        assert sum(p[1] for p in pat_tab) == n_miss
        print(sysn, "scored", scored, "miss", n_miss, "sum classes", sum(p[1] for p in pat_tab))

    # README
    md = ["# LSJ-Gold failure catalogue", "",
          f"Source: `data/qc/lsjgold/lsj_gold_scored.csv` ({len(rows)} rows). Generated by `pipeline/lsjgold/failure_catalogue.py`. Report only; nothing here patches a lemmatizer.", "",
          "## Method", "",
          "A row is *scored* for a system when that system produced a lemma and its `<sys>_blind` value is not empty. A *miss* is a scored row with `<sys>_blind == 0` (the produced lemma differs from the LSJ headword after accent-blind comparison). Systems: dilemma, odycy.", "",
          ORDER_TEXT, ""]
    md += [f"- **{c}**: {RULES[c]}" for c in CLASSES]
    md += ["", "Accent stripping: Unicode NFD, drop combining marks, lowercase, final sigma folded to sigma.", "",
           "**Honest note:** these classes are string rules, not judgements. A row labelled `same_stem` may be a wrong lemma or a legitimate variant headword; `proper_name` only means the headword is capitalised; `other` is not a claim that the error is unexplained, only that no rule fired. Class shares depend on rule order.", ""]
    for sysn in SYSTEMS:
        R = res[sysn]
        md += [f"## {sysn}", "", f"Scored rows: {R['scored']}. Misses: {R['n_miss']} ({100 * R['n_miss'] / R['scored']:.2f}%).", "",
               "### Pattern classes", "",
               md_table(["class", "count", "share %", "examples (headword, surface, lemma, author, locator)"],
                        [[c, n, s, " / ".join(f"{e[0]}, {e[1]}, {e[2]}, {e[3]}, {e[4]}" for e in exs)] for c, n, s, exs in R["pat"]]), "",
               "### By author (top 15 by misses)", "",
               md_table(["author", "name", "n_scored", "n_miss", "miss %", "top 5 headword -> lemma"], R["auth"][:15]), ""]
    md += ["## For maintainers", "",
           "Top 25 missed headwords per system, excluding rows classed article_convention, accent_only or proper_name. Lines: headword,count,most frequent lemma produced,one locus,surface at that locus.", ""]
    for sysn in SYSTEMS:
        md += [f"### {sysn}", "", "```"] + [csv_line(m) for m in res[sysn]["maint"]] + ["```", ""]
    (OUT / "README.md").write_text("\n".join(md), encoding="utf-8")

    # HTML
    e = html.escape
    def htable(header, rws):
        return "<table><tr>" + "".join(f"<th>{e(str(h))}</th>" for h in header) + "</tr>" + "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rws) + "</table>"
    h = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>LSJ-Gold failure catalogue</title>",
         "<style>body{font:15px/1.45 Georgia,serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border-bottom:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#f3f1ec}.small{color:#555;font-size:.9em}code{background:#f3f1ec;padding:0 .25em}</style></head><body>",
         "<h1>LSJ-Gold failure catalogue</h1>",
         f"<p class=small>Where Dilemma and odyCy miss the LSJ headword (scored rows with blind match = 0). Source: <code>lsj_gold_scored.csv</code>, {len(rows)} rows. Classes are mechanical string rules, not judgements; {e(ORDER_TEXT)}</p>"]
    for sysn in SYSTEMS:
        R = res[sysn]
        h.append(f"<h2>{sysn}</h2><p>Scored rows: {R['scored']}. Misses: {R['n_miss']} ({100 * R['n_miss'] / R['scored']:.2f}%).</p><h3>Pattern classes</h3>")
        h.append(htable(["class", "rule", "count", "share %", "examples (headword, surface, lemma, author, locator)"],
                        [[c, RULES[c], n, s, " / ".join(f"{x[0]}, {x[1]}, {x[2]}, {x[3]}, {x[4]}" for x in exs)] for c, n, s, exs in R["pat"]]))
        h.append("<h3>Top 50 missed headwords</h3>")
        h.append(htable(["headword", "misses", "top produced lemmas", "authors"], R["top"][:50]))
    h.append("</body></html>")
    DOC.write_text("\n".join(h), encoding="utf-8")

    for sysn in SYSTEMS:
        R = res[sysn]
        print(sysn, {c: (n, s) for c, n, s, _ in R["pat"]})
        print(sysn, "top5", [(r[0], r[1]) for r in R["top"][:5]])
    for p in sorted(OUT.iterdir()) + [DOC]:
        print(p, p.stat().st_size)


if __name__ == "__main__":
    main()
