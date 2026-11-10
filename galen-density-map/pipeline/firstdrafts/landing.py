"""Build the site front page (docs/index.html) and the drafts index (docs/first-drafts/index.html).

2026-11-10: a front page for readers, not only for researchers. Every quotation is copied verbatim from
rendering A of a unit that passed the machine checks (the script refuses a quote it cannot find in a
passing unit); every number is read from the outputs. Nothing here is model-written.

Usage: python -X utf8 landing.py
"""
from __future__ import annotations

import html
import json
import re

from common import REPO, WORKS, out_dir

DOCS = REPO / "docs"
FD = DOCS / "first-drafts"

# (slug, unit_id, verbatim excerpt of rendering A). Order = reading order on the page.
QUOTES = [
    ("de-humero", "K18a.346-347", "I was indeed somewhat amazed that he had not seen it at all, while of those after him who say they have seen it, one did so once, another twice, but none so many times as we have up to now."),
    ("adversus-lycum", "K18a.198", "having read the first expositions of his commentaries on the Aphorisms, I could no longer bear to read the rest of the book"),
    ("hirudinibus", "K11.317", "Those newly caught must be kept for one day, with a little blood thrown in to them for nourishment"),
    ("comp-per-genera", "K13.369-370", "For this discourse of mine is addressed above all to my companions, who have asked me now to write these things a second time, after the loss of the earlier ones."),
    ("in-hipp-salubri", "K15.176-177", "they are compelled to use whatever each of them happens to have at hand."),
    ("purgantium-facultate", "K11.323-324", "as wickedness increased over time, there was no longer anything either undared or unsaid among human beings"),
    ("quos-quibus", "K11.343-344", "one must anticipate by evacuating them at the onset of spring"),
    ("morbi-temporibus", "K7.440", "Of the whole disease, then, we conceive periods analogous to the ages of living beings"),
    ("difficultate-respirationis", "K7.753-754", "what is according to nature is one thing, and is as it were a rule and a measure"),
]
PB = re.compile(r"\s*\[\d+\]\s*")


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def unit_text(slug: str, uid: str) -> tuple[str, str]:
    d = json.loads((FD / slug / "data.json").read_text(encoding="utf-8"))
    a = {r["unit_id"]: r["translation"] for r in d["renderings"]["A"]}
    verdict = d["checks"]["units"].get(uid, {}).get("verdict")
    return PB.sub(" ", a[uid]).replace("  ", " "), verdict


def counts(slug: str) -> tuple[int, int, int]:
    m = json.loads((out_dir(slug) / "units_meta.json").read_text(encoding="utf-8"))
    c = json.loads((out_dir(slug) / "checks.json").read_text(encoding="utf-8")).get("summary", {})
    return m["n_units"], m["n_tei_words"], (c.get("unit_verdicts") or {}).get("fail", 0)


def v3_tiers() -> dict[str, int]:
    import csv
    rows = list(csv.DictReader((REPO / "galen-density-map" / "outputs" / "phase3" / "punch_list_v3.csv").open(encoding="utf-8")))
    key = next(k for k in rows[0] if k in ("tier_v3", "v3_tier", "tier"))
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    out["_total"] = len(rows)
    return out


CSS = """
:root{--bg:#faf7f0;--ink:#1f1b16;--muted:#6b6257;--rule:#e4ddd0;--card:#fffdf8;--accent:#7a1f1f;--accent-ink:#fff;--thin:#c98a2b;--none:#a33}
@media(prefers-color-scheme:dark){:root{--bg:#16130f;--ink:#e9e2d6;--muted:#a39a8e;--rule:#3a332b;--card:#1e1a15;--accent:#c4574a;--accent-ink:#fff}}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.65 Georgia,"Iowan Old Style","Palatino Linotype",serif}
a{color:var(--accent)}
.wrap{max-width:62rem;margin:0 auto;padding:0 1.25rem}
.sans{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.kicker{font:600 13px/1 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
header.hero{padding:4.5rem 0 3rem;border-bottom:1px solid var(--rule)}
.hero h1{font-size:clamp(2.2rem,5.5vw,3.6rem);line-height:1.08;margin:.8rem 0 1.2rem;font-weight:600;letter-spacing:-.01em;max-width:16ch}
.hero p.lede{font-size:1.2rem;max-width:40rem;margin:0 0 1.6rem;color:var(--ink)}
.hero .facts{display:flex;flex-wrap:wrap;gap:2.2rem;margin:2rem 0 0;padding:0;list-style:none}
.hero .facts li b{display:block;font:600 1.9rem/1.1 Georgia,serif}
.hero .facts li span{font:14px/1.3 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted)}
.btns{display:flex;flex-wrap:wrap;gap:.7rem}
.btn{display:inline-block;font:600 15px/1 system-ui,-apple-system,"Segoe UI",sans-serif;padding:.85rem 1.25rem;border-radius:999px;text-decoration:none;border:1px solid var(--accent)}
.btn.primary{background:var(--accent);color:var(--accent-ink)}
.btn.ghost{color:var(--accent)}
section{padding:3.2rem 0;border-bottom:1px solid var(--rule)}
section h2{font-size:1.7rem;line-height:1.2;margin:.5rem 0 .6rem;font-weight:600}
section .intro{max-width:40rem;color:var(--muted);margin:0 0 2rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(17.5rem,1fr));gap:1.1rem}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--rule);border-radius:14px;padding:1.3rem 1.3rem 1.1rem;text-decoration:none;color:var(--ink);transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--accent);transform:translateY(-2px)}
.card h3{font-size:1.18rem;line-height:1.3;margin:0 0 .25rem;font-weight:600}
.card .lat{font-style:italic;color:var(--muted);font-size:.9rem;line-height:1.4;margin-bottom:1rem}
.card blockquote{margin:0 0 1rem;padding:0 0 0 .9rem;border-left:3px solid var(--accent);font-size:1rem;line-height:1.55;flex:1}
.card .meta{font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);display:flex;justify-content:space-between;gap:.5rem}
.card .meta .go{color:var(--accent);font-weight:600}
.warn{font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);max-width:44rem;margin:1.6rem 0 0}
.gap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:2.5rem;align-items:center}
@media(max-width:760px){.gap{grid-template-columns:1fr}}
.bar{display:flex;height:2.6rem;border-radius:8px;overflow:hidden;border:1px solid var(--rule)}
.bar div{height:100%}
.legend{list-style:none;padding:0;margin:1rem 0 0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.legend li{display:flex;gap:.6rem;align-items:baseline;margin:.35rem 0}
.legend i{width:.8rem;height:.8rem;border-radius:3px;flex:none;display:inline-block;transform:translateY(1px)}
.legend b{font-variant-numeric:tabular-nums;min-width:3.2rem;display:inline-block}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:1.4rem;counter-reset:s;margin:0;padding:0;list-style:none}
.steps li{counter-increment:s;font-size:1rem}
.steps li::before{content:counter(s);display:inline-grid;place-items:center;width:2rem;height:2rem;border-radius:50%;border:1px solid var(--accent);color:var(--accent);font:600 14px/1 system-ui,sans-serif;margin-bottom:.6rem}
.steps b{display:block;font-size:1.05rem;margin-bottom:.2rem}
.tools{list-style:none;padding:0;margin:0;display:grid;gap:.9rem}
.tools li{font-size:1rem}
.tools a.t{font-weight:600}
footer{padding:2.2rem 0 3rem;font:14px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted)}
code{font-size:.9em;background:var(--rule);padding:0 .3em;border-radius:4px}
"""


def head(title: str, prefix: str) -> str:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><meta name=description content=\"Nine works of Galen that had never been published in English, as machine first drafts with the Greek beside them.\">"
            f"<link rel=stylesheet href=\"{prefix}site.css\"></head><body>")


def cards(prefix: str) -> str:
    out = []
    for slug, uid, q in QUOTES:
        w = WORKS[slug]
        text, verdict = unit_text(slug, uid)
        assert q in text, (slug, uid, q[:40])
        assert verdict == "pass", (slug, uid, verdict)
        n_units, n_words, n_fail = counts(slug)
        page = next((f.name for f in sorted((FD / slug).glob("book-*.html")) if f'id="{uid}"' in f.read_text(encoding="utf-8")), "")
        out.append(f'<a class=card href="{prefix}{slug}/{page}#{esc(uid)}"><h3>{esc(w["title_eng"])}</h3><div class=lat>{esc(w["title_lat"])}</div>'
                   f'<blockquote>“{esc(q[0].upper() + q[1:])}”</blockquote>'
                   f'<div class=meta><span>{n_words:,} Greek words · Kühn {esc(w["kuhn_vol"])}</span><span class=go>Read →</span></div></a>')
    return "<div class=grid>" + "".join(out) + "</div>"


def main() -> None:
    (DOCS / "site.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    slugs = [s for s, _, _ in QUOTES]
    total_words = sum(counts(s)[1] for s in slugs)
    t = v3_tiers()
    none_ = t.get("real_no_perseus_lsj", 0) + t.get("real_contested", 0)
    thin = t.get("thin", 0) + t.get("thin_contested", 0)
    art = t.get("artifact_suspect", 0)
    total = t["_total"]
    seg = lambda n, c: f'<div style="width:{100 * n / total:.2f}%;background:{c}" title="{n}"></div>'

    page = head("Galen in English for the first time", "") + f"""
<header class=hero><div class=wrap>
<div class=kicker>Galen Density Project</div>
<h1>Galen in English for the first time</h1>
<p class=lede>Galen of Pergamon was a doctor in second-century Rome, and more of his writing survives than of any other ancient Greek author. Much of it has never been translated into English. Here are nine of those works, put into English by machine: rough, unchecked by any scholar, and readable today.</p>
<div class=btns><a class="btn primary" href="first-drafts/">Start reading</a><a class="btn ghost" href="#how">How they were made</a></div>
<ul class=facts><li><b>9</b><span>works never before in English</span></li><li><b>{total_words:,}</b><span>words of Greek</span></li><li><b>2</b><span>independent machine translations of each passage</span></li></ul>
</div></header>

<section><div class=wrap>
<div class=kicker>The works</div>
<h2>Nine books, in Galen's own voice</h2>
<p class=intro>Each quotation below is copied from the draft as it stands, from a passage that passed all the machine checks. Click a card to start reading there.</p>
{cards("first-drafts/")}
<p class=warn>These are machine first drafts. No scholar has checked them yet; they are for reading and for correcting, not for quoting as Galen's words. Every page keeps the Greek, a second translation and the checks one click away, under <em>Scholar view</em>.</p>
</div></section>

<section><div class=wrap><div class=gap>
<div><div class=kicker>Why nobody had done it</div>
<h2>Galen's words fall through the dictionary</h2>
<p>Galen wrote in a specialist Greek full of drug names, anatomy and rare technical words. The standard Greek–English dictionary (LSJ) covers many of those words thinly or not at all. That gap makes him hard to translate, for people and for machines: earlier research found that the rarer a passage's terminology, the worse machine translation of Galen does.</p>
<p class=sans style="font-size:15px;color:var(--muted)">From the project's list of {total:,} words that are distinctive to Galen and thinly glossed, checked by hand. <a href="galen-terms/">Look any word up in the Term Explorer</a>.</p></div>
<div><div class=bar>{seg(thin, "var(--thin)")}{seg(none_, "var(--none)")}{seg(art, "var(--rule)")}</div>
<ul class=legend><li><i style="background:var(--thin)"></i><b>{thin:,}</b> real words with only a thin, one-sense entry</li><li><i style="background:var(--none)"></i><b>{none_:,}</b> real words with no entry at all</li><li><i style="background:var(--rule)"></i><b>{art:,}</b> false alarms from the software, set aside</li></ul></div>
</div></div></section>

<section id=how><div class=wrap>
<div class=kicker>Method</div>
<h2>How they were made</h2>
<ol class=steps>
<li><b>The Greek</b>The text comes from Kühn's 1820s edition, as digitised by the First1KGreek project, and is shown beside every passage.</li>
<li><b>Two translations</b>Two different language models translated each passage separately, with the same plain instructions and no help.</li>
<li><b>Three checks</b>Each passage is translated back into Greek, the two versions are compared term by term, and a model judge tests the technical terms against the dictionary.</li>
<li><b>Failures kept</b>Nothing is hidden or smoothed over. Passages that fail the checks stay on the page, marked, so a reader knows where to be careful.</li>
</ol>
<p class=warn>Found a mistake? <a href="https://github.com/Montblanctech/Galen/issues/new?template=first-draft-correction.yml">Report a correction</a>; that is what these drafts are for.</p>
</div></section>

<section><div class=wrap>
<div class=kicker>For researchers</div>
<h2>Data, benchmarks and tools</h2>
<ul class=tools>
<li><a class=t href="lsj-gold/">LSJ-Gold leaderboard</a> — lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek (93,926 relocated loci over 54 authors, CC BY 4.0). <a href="lsj-gold/leaderboard.json">JSON</a>.</li>
<li><a class=t href="ls-gold/">LS-Gold leaderboard</a> — the Latin twin: lemmatizer accuracy on the words Lewis &amp; Short cites (161,032 relocated loci over 33 authors, validated by Collatinus and Whitaker's Words, CC BY-SA 4.0). <a href="ls-gold/leaderboard.json">JSON</a>.</li>
<li><a class=t href="galen-terms/">Galen Term Explorer</a> — any Galenic word: keyness, LSJ tier, Dilemma headword, punch-list label, contexts, Kühn loci.</li>
<li><a class=t href="terms/">Term Explorer for further authors</a> — Diophantus, John Philoponus, Philodemus.</li>
<li><a class=t href="first-drafts/">The drafts index</a> — all nine works with unit counts and check failures.</li>
</ul>
</div></section>

<footer><div class=wrap>Galen First Drafts by William Pepperman, Galen Density Project. Every number on these pages traces to a file in <code>galen-density-map/</code>. Repository: <a href="https://github.com/Montblanctech/Galen">github.com/Montblanctech/Galen</a>. Audit kit: <code>pip install greek-lemma-audit</code>. Cite the concept DOI <a href="https://doi.org/10.5281/zenodo.21561962">10.5281/zenodo.21561962</a> (v3.0: <a href="https://doi.org/10.5281/zenodo.24046260">10.5281/zenodo.24046260</a>).</div></footer>
</body></html>
"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")

    rows = []
    for slug in slugs:
        w = WORKS[slug]
        n_units, n_words, n_fail = counts(slug)
        rows.append(f'<li><a class=t href="{slug}/">{esc(w["title_eng"])}</a> <span class=sans style="color:var(--muted);font-size:15px">· <em>{esc(w["title_lat"])}</em> · Kühn {esc(w["kuhn_vol"])} {esc(w["kuhn_pages"])} · '
                    f'{n_units} passages, {n_words:,} Greek words, {n_fail} failing two or more checks</span></li>')
    idx = head("Galen First Drafts", "../") + f"""
<header class=hero style="padding:3.2rem 0 2.2rem"><div class=wrap>
<div class=kicker><a href="../" style="text-decoration:none">Galen Density Project</a></div>
<h1 style="font-size:clamp(2rem,4.5vw,3rem)">Galen First Drafts</h1>
<p class=lede>Nine works of Galen with no English translation, most of them with none in any modern language, put into English by two language models and checked by machine. Drafts for reading and for scholars to correct, not translations to quote.</p>
</div></header>
<section><div class=wrap>
{cards("")}
</div></section>
<section><div class=wrap>
<div class=kicker>Details</div>
<h2>All nine, with their numbers</h2>
<ul class=tools>{"".join(rows)}</ul>
<p class=warn>Author of the drafts series: William Pepperman (Galen Density Project). Each work carries its own citation line and version. Translation status and sources per work: <code>phase1/README_translation_status.md</code>. Spec: <code>firstdrafts_v0_spec.md</code> (cycle 1), <code>firstdrafts_v02_spec.md</code> (cycles 2 and 3). <a href="https://github.com/Montblanctech/Galen/issues/new?template=first-draft-correction.yml">Report a correction</a>.</p>
</div></section>
<footer><div class=wrap><a href="../">All project pages</a></div></footer>
</body></html>
"""
    (FD / "index.html").write_text(idx, encoding="utf-8")
    print("front page and drafts index written;", total_words, "Greek words;", {"thin": thin, "none": none_, "artifact": art, "total": total})
    sitemap()


SITE = "https://montblanctech.github.io/Galen/"
NOT_PUBLIC = {"mw-gold"}  # lab-only pages, never in the public sitemap


def sitemap() -> None:
    """docs/sitemap.xml: every public HTML page, front page and drafts first (2026-11-10, for Search Console)."""
    from datetime import date
    urls = []
    for p in sorted(DOCS.rglob("*.html")):
        rel = p.relative_to(DOCS).as_posix()
        if rel.split("/")[0] in NOT_PUBLIC:
            continue
        urls.append(SITE + (rel[: -len("index.html")] if rel.endswith("index.html") else rel))
    rank = lambda u: (u != SITE, "/first-drafts/" not in u, u)
    urls = sorted(set(urls), key=rank)
    today = date.today().isoformat()
    body = "".join(f"<url><loc>{esc(u)}</loc><lastmod>{today}</lastmod></url>\n" for u in urls)
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + body + "</urlset>\n", encoding="utf-8")
    print("sitemap:", len(urls), "pages")


if __name__ == "__main__":
    main()
