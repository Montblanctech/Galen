"""Galen First Drafts v0, stage 5: one static page per work (spec: firstdrafts_v0_spec.md).

Reads outputs/firstdrafts/<slug>/ (units.jsonl, renderings_*.jsonl, alignment.json, term_table.csv,
checks.json, units_meta.json, align_meta.json) and writes docs/first-drafts/<slug>/index.html plus
docs/first-drafts/<slug>/data.json (the same data for reuse) and docs/first-drafts/index.html.
Greek beside both English renderings, page markers kept, target terms highlighted (green = the two
renderings agree, red = they differ), term table per unit, difficulty from the density map, the three
check marks and the unit verdict, the banner, and a link to the issue template. No model involved.

2026-11-12: a work that is not in common.WORKS is read from configs/<slug>.json (common.work_config); its titles,
citation labels, source language and dictionary links come from the config (page_text). A Galen page is unchanged.
  --dest DIR          write the pages under DIR instead of docs/first-drafts (the landing page is then not rebuilt)
  --build-date DATE   the date printed on the page (default today), for reproducing a published page
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from datetime import date

from common import LANG, LEXICA, REPO, WORKS, draft_words, marker_re, out_dir, read_jsonl, work_config

RENDERINGS = {"A": "fable-5-1", "B": "opus-5-5"}
ISSUE_URL = "https://github.com/Montblanctech/Galen/issues/new?template=first-draft-correction.yml"
MARK = re.compile(r"\[(\d+)\]")


def esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def mark_pages(s: str, mark=MARK, label: str = "Kühn page") -> str:
    return mark.sub(r'<span class=pb title="' + label + r'">\1</span>', esc(s))


def highlight(text: str, spans: list[tuple[str, str, str]], mark=MARK, label: str = "Kühn page") -> str:
    """Wrap the first not-yet-used case-insensitive occurrence of each phrase; spans = (phrase, css_class, title).
    Positions are found in the escaped plain text first and assembled afterwards, so a mark can never land
    inside another mark's attributes."""
    base = esc(text)
    taken: list[tuple[int, int, str, str]] = []
    for phrase, cls, title in spans:
        p = esc(phrase.strip())
        if not p or len(p) < 2:
            continue
        for m in re.finditer(re.escape(p), base, flags=re.I):
            if all(m.end() <= a or m.start() >= b for a, b, _, _ in taken):
                taken.append((m.start(), m.end(), cls, title))
                break
    taken.sort()
    out, pos = [], 0
    for a, b, cls, title in taken:
        out.append(base[pos:a])
        out.append(f'<mark class="{cls}" title="{esc(title).replace(chr(34), "&quot;")}">{base[a:b]}</mark>')
        pos = b
    out.append(base[pos:])
    return mark.sub(r'<span class=pb title="' + label + r'">\1</span>', "".join(out))


SPLIT_OVER = 120  # units; above this a work is published one page per book


def clean_headword(h: str) -> str:
    """LSJ headword for display and Logeion links (2026-11-11): drop the quantity marks ^ and _ the Perseus XML writes,
    and rebuild capitals the XML writes as a detached breathing/accent before a lower-case letter (ʼαδρίας -> Ἀδρίας,
    ʼ ́αμμων -> Ἄμμων, ʽροδιακός -> Ῥοδιακός)."""
    import unicodedata
    h = (h or "").replace("^", "").replace("_", "").strip()
    marks = {"ʼ": "̓", "’": "̓", "ʽ": "̔", "᾽": "̓", "῾": "̔"}
    lead, i = "", 0
    while i < len(h) and (h[i] in marks or h[i] in " ́̀͂̓̔"):
        lead += marks.get(h[i], h[i] if h[i] != " " else "")
        i += 1
    if lead and i < len(h):
        return unicodedata.normalize("NFC", h[i].upper() + lead + h[i + 1:])
    return unicodedata.normalize("NFC", h)


CYRILLIC_LOOKALIKES = str.maketrans("аеорсухіјѕАЕОРСУХІЈЅ", "aeopcyxijsAEOPCYXIJS")


def link_headword(h: str) -> str:
    """A Lewis & Short headword for a dictionary link: quantity marks and the prefix hyphen off (com-mŏdŭlātĭo -> commodulatio)."""
    import unicodedata
    h = unicodedata.normalize("NFD", (h or "").replace("^", "").replace("_", "").replace("-", "").strip())
    h = h.translate(CYRILLIC_LOOKALIKES)  # Perseus L&S has Cyrillic letters in a few headwords (hexastўlos); after NFD, so ў = у + breve is caught
    return unicodedata.normalize("NFC", "".join(c for c in h if not unicodedata.combining(c)))


def page_text(w: dict, galen: bool) -> dict:
    """Every work-specific phrase of the page. The Galen values are the cycle 1-4 page text, unchanged."""
    if galen:
        return {"author": "Galen", "adj": "Greek", "lat_line": f"{w['title_lat']} · Kühn {w['kuhn_vol']} {w['kuhn_pages']}",
                "cite_tail": f"Kühn {w['kuhn_vol']} {w['kuhn_pages']}", "markers": "The small grey numbers are the pages of Kühn's Greek edition.",
                "col": "Greek (Kühn)", "label": "Kühn page", "lex": LEXICA["lsj"], "lemma_th": "Dilemma lemma", "tagger": "odyCy",
                "uncertain_key": "uncertain_greek", "difficulty": "punch-list density per 100 tokens from the terminology density map",
                "credit": "Greek text CC BY-SA 4.0 (First1KGreek / Open Greek and Latin).", "series": "Galen First Drafts", "tier_prefix": "punch",
                "doi": "concept DOI 10.5281/zenodo.21561962"}
    L, lx = LANG[w["lang"]], LEXICA[w["lexicon"]["name"]]
    return {"author": w["author"], "adj": L["adj"], "lat_line": f"{w['title_lat']} · {w['citation']}", "cite_tail": w["citation"],
            "markers": f"The small grey numbers are the {w.get('marker_label', 'section')}s of {w['edition_desc']}.",
            "col": f"{L['adj']} ({w.get('edition_short', w['edition_desc'])})", "label": w.get("marker_label", "section"), "lex": lx,
            "lemma_th": f"{lx['short']} lemma", "tagger": {"latincy": "LatinCy", "odycy_precomputed": "odyCy"}.get(w["tagger"]["name"], w["tagger"]["name"]),
            "uncertain_key": L["uncertain_key"],
            "difficulty": f"density per 100 tokens of words outside the reference frequency list that {lx['short']} covers with at most one sense or not at all",
            "credit": w.get("text_credit", ""), "series": "First Drafts", "tier_prefix": "lex",
            "doi": f"DOI {w['doi']}" if w.get("doi") else "DOI not yet assigned"}


def parts_config(slug: str) -> dict | None:
    """A Galen work published in parts (2026-11-28, Simple Drugs 1-5 and 6-11): configs/<slug>.json with a "parts" list.
    Each part keeps its own output folder, checks and judge run; the page puts them together. None for any other work."""
    p = Path(__file__).resolve().parent / "configs" / f"{slug}.json"
    if slug in WORKS or not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d if d.get("parts") else None


DATA_URL = "https://github.com/Montblanctech/Galen/tree/master/galen-density-map/outputs/firstdrafts/"


def meth_html(w: dict, T: dict, slug: str, built, P: dict | None) -> str:
    """The scholar view's methods line. A work in parts names each part's prompt and links each part's folder."""
    terms = (f"Terms: <mark class=agree>green</mark> = both renderings agree on the term (after normalisation), <mark class=differ>red</mark> = they differ, "
             f"<mark class=one>grey</mark> = one rendering reported. Hover a mark for the {T['adj']} lemma and the other rendering. ")
    if not P:
        return (f"<p class=\"small meth\">{T['adj']}: {esc(w['source_note'])}. Rendering A: <code>claude-fable-5-1</code>; rendering B: <code>claude-opus-5-5</code>; "
                f"same neutral prompt, no glossary, fresh context, built {built.isoformat()}. Method, numbers and what the checks cannot catch: "
                f"<a href=\"{DATA_URL}{slug}\">README and data</a>; pre-registered thresholds: <code>{esc(w.get('spec', 'firstdrafts_v0_spec.md'))}</code>. "
                f"{terms}Unit difficulty = {T['difficulty']} (tercile within this work).</p>")
    runs = " ".join(f"Books {esc(ps['books'])}: {esc(ps['prompt'])}; README and data: <a href=\"{DATA_URL}{esc(ps['slug'])}\">{esc(ps['slug'])}</a>." for ps in P["parts"])
    return (f"<p class=\"small meth\">{T['adj']}: {esc(w['source_note'])}. Rendering A: <code>claude-fable-5-1</code>; rendering B: <code>claude-opus-5-5</code>, "
            f"built {built.isoformat()}. The two halves were drafted and checked as separate runs, each with its own judge draw and its own numbers. {runs} "
            f"Pre-registered thresholds: <code>{esc(w.get('spec', 'firstdrafts_v02_spec.md'))}</code> with the judge of <code>firstdrafts_v03_judge_note.md</code>. "
            f"{terms}Unit difficulty = {T['difficulty']} (tercile within each half).</p>")


FLAG_NOTE = "places for a reader to look, not confirmed errors"
FLAG_CSS = """.flags{font:13px/1.45 system-ui,"Segoe UI",sans-serif;color:#7a4a00;margin:.35rem 0 0} .flags.none{color:#777} details.fl ul{margin:.2rem 0;padding-left:1.2rem;font-size:.86em} details.fl li{margin:.25rem 0}
body.read .flags{max-width:38rem;margin:-.6rem auto 1.1rem;color:#8a6a3a} body.read .flags.none{display:none}
@media(prefers-color-scheme:dark){body.read .flags{color:#d2b07a}}
"""


NAME_KIND = {"intruder": "named in the English only", "missing": "named in the Greek only"}


def flag_kind(i: dict) -> str:
    k = i["kind"]
    return NAME_KIND.get(k, k) if i["check"] in ("drug names", "body parts") else k


def flag_value(v) -> str:
    s = str(v)
    return f"the name of the drug of entry {s[3:]}" if s.startswith("sd:") else s


def flags_html(fl: list[tuple[str, dict]], src_lang: str) -> str:
    """The flags line of one passage: the fidelity checks (numbers, negation, more/less) and the names checks (drug names,
    body parts) on each rendering, sentence pair by sentence pair. They point at places to read against the Greek."""
    if not fl:
        return f'<div class="flags none">Flags ({FLAG_NOTE}): none raised.</div>'
    per = {t: Counter(f"{i['check']} {flag_kind(i)}" for tt_, i in fl if tt_ == t) for t in ("A", "B")}
    line = "; ".join(f"{t}: " + ", ".join(f"{k} {n}" if n > 1 else k for k, n in sorted(c.items())) for t, c in per.items() if c)
    items = []
    for t, i in fl:
        vals = ", ".join(flag_value(v) for v in (i.get("values") or []))
        pair = ""
        if i.get("greek") or i.get("english"):
            pair = f'<br><span lang={src_lang}>{esc(i.get("greek", ""))}</span><br>{esc(i.get("english", ""))}'
        items.append(f"<li><b>{t}</b> · {esc(i['check'])}: {esc(flag_kind(i))}{' (' + esc(vals) + ')' if vals else ''}{pair}</li>")
    return (f'<div class=flags>Flags ({FLAG_NOTE}): {esc(line)}</div>'
            f"<details class=fl><summary>Flagged sentences ({len(fl)})</summary><ul>{''.join(items)}</ul></details>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="adversus-lycum")
    ap.add_argument("--dest", default=None, help="root for the pages (default docs/first-drafts); the landing page is rebuilt only for the default")
    ap.add_argument("--build-date", default=None, help="YYYY-MM-DD printed on the page (default today)")
    a = ap.parse_args()
    slug = a.work
    P = parts_config(slug)
    W = {**P, "galen": True, "lang": "grc"} if P else work_config(slug)
    galen = W["galen"]
    w = P if P else (WORKS[slug] if galen else W)
    T = page_text(w, galen)
    if P:
        T.update(P.get("page_text", {}))
    mk = MARK if galen else re.compile(marker_re(W))
    built = date.fromisoformat(a.build_date) if a.build_date else date.today()
    root = Path(a.dest).resolve() if a.dest else REPO / "docs" / "first-drafts"
    part_of: dict[str, dict] = {}   # unit id -> its part (a work in parts only)
    flags: dict[str, list[tuple[str, dict]]] = {}
    if P:
        units, rend, tt, cku, psum, n_targets = [], {t: {} for t in RENDERINGS}, [], {}, [], 0
        for ps in P["parts"]:
            po = out_dir(ps["slug"])
            pw = work_config(ps["slug"])
            ps = {**ps, "mk": re.compile(marker_re(pw))}
            us = read_jsonl(po / "units.jsonl")
            units += us
            for u in us:
                part_of[u["unit_id"]] = ps
            for t, s_ in RENDERINGS.items():
                rend[t].update({r["unit_id"]: r for r in read_jsonl(po / f"renderings_{s_}.jsonl")})
            tt += list(csv.DictReader((po / "term_table.csv").open(encoding="utf-8")))
            pck = json.loads((po / "checks.json").read_text(encoding="utf-8"))
            cku.update(pck["units"])
            pm = json.loads((po / "units_meta.json").read_text(encoding="utf-8"))
            n_targets += pm.get("n_targets", 0)
            psum.append((ps, pck.get("summary", {}), pm, us))
            for t in ("A", "B"):
                for f in ("fidelity", "names"):
                    fp = po / f"{f}_{t}.json"
                    for i in (json.loads(fp.read_text(encoding="utf-8"))["items"] if fp.exists() else []):
                        flags.setdefault(i["unit_id"], []).append((t, i))
        checks = {"units": cku, "summary": {}, "parts": {ps["slug"]: sm for ps, sm, _, _ in psum}}
        meta = {"n_targets": n_targets}
    else:
        out = out_dir(slug)
        units = read_jsonl(out / "units.jsonl")
        rend = {t: {r["unit_id"]: r for r in read_jsonl(out / f"renderings_{s}.jsonl")} for t, s in RENDERINGS.items()}
    # A Kühn page marker whose number the TEI lacks comes out as "[None]" (in-hipp-salubri K15.178); it marks nothing,
    # so it is dropped from the Greek and the renderings on the page (2026-11-11). The unit files are unchanged.
    for u in units:
        u["greek"] = u["greek"].replace("[None] ", "").replace("[None]", "")
    for t in rend:
        for r in rend[t].values():
            resp = r.get("response") or {}
            if isinstance(resp.get("translation"), str):
                resp["translation"] = resp["translation"].replace("[None] ", "").replace("[None]", "")
    if not P:
        tt = list(csv.DictReader((out / "term_table.csv").open(encoding="utf-8")))
        checks = json.loads((out / "checks.json").read_text(encoding="utf-8")) if (out / "checks.json").exists() else {"units": {}, "summary": {}}
        meta = json.loads((out / "units_meta.json").read_text(encoding="utf-8"))
    by_unit: dict[str, list[dict]] = {}
    for r in tt:
        by_unit.setdefault(r["unit_id"], []).append(r)
    s = checks.get("summary", {})

    def mark(v: str) -> str:
        cls = {"pass": "ok", "fail": "bad", "n/a": "na", "not_run": "na", "missing": "na", "judge_failed_gate": "na", "mixed": "mixed", "insufficient": "na"}.get(v, "na")
        return f'<span class="chk {cls}" title="{esc(v)}">{esc(v)}</span>'

    # the original-language column is marked as such, so a screen reader reads it with the right voice (2026-11-13 audit)
    src_lang = {"grc": "grc", "lat": "la"}.get(W.get("lang", "grc"), "grc")
    parts = []
    # every page carries its own description (2026-11-13 site audit: the Galen pages had none, so search results and
    # link previews fell back to a generic line); a work config may give its own
    desc = w.get("description") or (f"{T['author']}, {w['title_eng']} ({w['title_lat']}): a machine first draft in English with the {T['adj']} beside it, "
                                     f"two independent renderings and the machine checks. Unverified; for reading and correcting.")
    title_html = f"<title>{esc(T['author'])}, {esc(w['title_eng'])} — machine first draft v0.1</title>"
    desc_html = '<meta name=description content="' + esc(desc) + '">'
    parts.append(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
{title_html}{desc_html}
<style>
body{{font:15px/1.5 Georgia,serif;max-width:1400px;margin:0 auto;padding:0 1rem 3rem;color:#222;background:#fff}}
.banner{{background:#7a1f1f;color:#fff;padding:.6rem 1rem;font-size:.95em;position:sticky;top:0;z-index:5}}
.banner a{{color:#ffd}}
h1{{font-size:1.5rem;margin:.8rem 0 .2rem}} h2{{font-size:1.1rem;margin:1.6rem 0 .3rem;border-top:1px solid #ddd;padding-top:.8rem}}
.small{{color:#555;font-size:.88em}} code{{background:#f3f1ec;padding:0 .25em}}
table.sum{{border-collapse:collapse;margin:.5rem 0}} table.sum td,table.sum th{{border-bottom:1px solid #ddd;padding:.2rem .6rem;text-align:left;font-size:.9em}}
.unit{{margin:1.2rem 0;padding:.4rem 0}} .unit.fail{{border-left:6px solid #a33;padding-left:.6rem}}
.uh{{display:flex;flex-wrap:wrap;gap:.8rem;align-items:baseline}} .uh .id{{font-weight:bold}}
.cols{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem}} @media(max-width:900px){{.cols{{grid-template-columns:1fr}}}}
.grc{{font-size:1.02em}} .eng{{}} .col .ch{{margin:.3rem 0;font-size:.85em;color:#555;font-weight:normal}}
.pb{{display:inline-block;background:#eee;border:1px solid #bbb;border-radius:.3em;padding:0 .3em;font-size:.75em;color:#333;vertical-align:super;margin:0 .15em}}
mark.agree{{background:#dff3df}} mark.differ{{background:#f9d6d6}} mark.one{{background:#eee}}
.chk{{display:inline-block;border-radius:.4em;padding:0 .45em;font-size:.8em;border:1px solid #999}} .chk.ok{{background:#dff3df;border-color:#7a7}} .chk.bad{{background:#f9d6d6;border-color:#a33}} .chk.na{{background:#eee}} .chk.mixed{{background:#fbefc9;border-color:#c90}}
.tier-low{{color:#363}} .tier-mid{{color:#975200}} .tier-high{{color:#a33}}
details{{margin:.4rem 0}} summary{{cursor:pointer;color:#444;font-size:.9em}}
table.tt{{border-collapse:collapse;width:100%;font-size:.86em}} table.tt th,table.tt td{{border-bottom:1px solid #e5e5e5;padding:.15rem .4rem;text-align:left;vertical-align:top}}
.unc{{color:#a33;font-size:.8em}} .lsj{{color:#555;font-size:.85em}}
.verdict{{font-weight:bold}}
{FLAG_CSS if P else ''}/* reading view (2026-11-10): the English of rendering A as a book page; the scholar view is the full apparatus */
.modebar{{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.8rem 0 .2rem;font:14px/1.4 system-ui,"Segoe UI",sans-serif;color:#555}}
.modebar button{{font:inherit;border:1px solid #bbb;background:#fff;border-radius:999px;padding:.3rem .9rem;cursor:pointer;color:#333}}
.modebar button[aria-pressed=true]{{background:#7a1f1f;border-color:#7a1f1f;color:#fff}}
.rhead{{display:none}} .unit{{scroll-margin-top:5.5rem}}
body.read{{background:#faf7f0;color:#1f1b16}}
body.read .rhead{{display:block;max-width:38rem;margin:2.2rem auto 1.4rem;text-align:center}}
.rhead .kicker{{font:600 13px/1 system-ui,"Segoe UI",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#7a1f1f}}
.rhead .rt{{font-size:2.1rem;line-height:1.2;margin:.5rem 0}}
.rhead .lat{{font-style:italic;color:#6b6257}}
.rhead .note{{font:14px/1.5 system-ui,"Segoe UI",sans-serif;color:#6b6257;margin-top:.9rem}}
body.read h1.st,body.read .meth,body.read table.sum,body.read details{{display:none}}
body.read .modebar{{max-width:38rem;margin:.8rem auto 0}}
body.read .unit{{max-width:38rem;margin:0 auto;padding:0}}
body.read .unit.fail{{border-left:3px solid #c98a8a;padding-left:.9rem;margin-left:auto}}
body.read .cols{{display:block}}
body.read .col.grc,body.read .col.b,body.read .col .ch{{display:none}}
body.read .col.a{{font-size:19px;line-height:1.75;margin:0 0 1.1rem}}
body.read mark{{background:none;color:inherit}}
body.read .uh{{font:12px/1.4 system-ui,"Segoe UI",sans-serif;color:#766d62;gap:.5rem}}
body.read .uh .id a{{color:#766d62;font-weight:normal;text-decoration:none}}
body.read .uh>span:nth-child(n+3){{display:none}}
body.read .unit.fail .uh::after{{content:"the machine checks flag this passage";color:#a33}}
body.read .pb{{background:none;border:none;color:#766d62;font-family:system-ui,sans-serif}}
body.read h2,body.read .nav,body.read .lic,body.read ul{{max-width:38rem;margin-left:auto;margin-right:auto}}
@media(prefers-color-scheme:dark){{body.read{{background:#16130f;color:#e9e2d6}} body.read .rhead .lat,body.read .rhead .note{{color:#a39a8e}} body.read a{{color:#e2b0a0}} body.read .rhead .kicker{{color:#e2b0a0}} body.read .uh,body.read .uh .id a,body.read .pb,body.read .modebar,body.read .small{{color:#a39a8e}} body.read .unit.fail .uh::after{{color:#e2867a}}}}
</style></head><body class=read>
<script>try{{if(localStorage.getItem('gfd-view')==='scholar')document.body.className='scholar'}}catch(e){{}}</script>
<div class=banner><strong>Machine first draft, unverified, v0.1.</strong> Two language models translated this text independently; no scholar has checked it. Red marks show where the machine checks fail. The apparatus says where to look, not that the text is right. <a href="{ISSUE_URL}">Report a correction</a> · <a href="../../">project pages</a></div>
<div class=modebar><button type=button data-v=read>Read</button><button type=button data-v=scholar>Scholar view</button><span>Read shows one English rendering. Scholar view adds the {T['adj']}, the second rendering, the term marks and the checks.</span></div>
<script>(function(){{var bs=document.querySelectorAll('.modebar button');function set(v){{document.body.className=v;bs.forEach(function(b){{b.setAttribute('aria-pressed',b.dataset.v===v)}});try{{localStorage.setItem('gfd-view',v)}}catch(e){{}}}}bs.forEach(function(b){{b.onclick=function(){{set(b.dataset.v)}}}});set(document.body.className==='scholar'?'scholar':'read')}})()</script>
<header class=rhead><div class=kicker>{esc(T['author'])} · machine first draft</div><h1 class=rt>{esc(w['title_eng'])}</h1><div class=lat>{esc(T['lat_line'])}</div>
<p class=note>{''.join(esc(x) + ' ' for x in (w.get('claim'), w.get('prior_translations')) if x)}This is rendering A, made by a language model and not yet checked by a scholar. {esc(T['markers'])} Passages with a red rule failed the machine checks; those checks are automated agreement tests, not a reading of the {T['adj']}, so a passage without the rule is not checked either. Words in square brackets were supplied by the model for the sense; {T['adj']} in parentheses gives the original word; any remark about a doubtful or corrupt reading is the model's, not a scholar's.</p></header>
<h1 class=st>{esc(T['author'])}, <em>{esc(w['title_lat'])}</em> ({esc(w['title_eng'])}), {esc(T['cite_tail'])}</h1>
{meth_html(w, T, slug, built, P)}
""")
    # summary table
    parts.append(f"<table class=sum><tr>{'<th>books</th>' if P else ''}<th>units</th><th>{T['adj']} words</th><th>targets</th><th>(a) back-translation pass</th><th>(b) A/B agreement pass</th><th>(c) {T['lex']['short']} judge pass</th><th>units failing ≥2 checks</th>{'<th>flags A / B</th>' if P else ''}</tr>")
    def rs(k, s=s):
        v = s.get(k) or {}
        return f"{v.get('pass', '–')}/{(v.get('pass') or 0) + (v.get('fail') or 0)}" if v else "not run"
    def sum_row(s, us, n_t, lead="", gate=None, tail=""):
        g = gate if gate else (' · judge gate ' + str((s.get('c_gate') or {}).get('correct')) + '/' + str((s.get('c_gate') or {}).get('controls')) if s.get('c_gate') else '')
        return (f"<tr>{lead}<td>{len(us)}</td><td>{sum(int(u.get('n_tokens', 0)) for u in us)}</td><td>{n_t}</td><td>{rs('a', s)}</td><td>{rs('b', s)} (term level {(s.get('b_term_level') or {}).get('pct', '–')}%)</td>"
                f"<td>{rs('c', s)}{g}</td><td>{(s.get('unit_verdicts') or {}).get('fail', 0)}</td>{tail}</tr>")
    if P:
        for ps, ss, pm, us in psum:
            ids = {u["unit_id"] for u in us}
            nf = {t: sum(1 for k, v in flags.items() if k in ids for tt_, _ in v if tt_ == t) for t in ("A", "B")}
            parts.append(sum_row(ss, us, pm.get("n_targets", ""), f"<td>{esc(ps['books'])}</td>", f" · {esc(ps['gate'])}", f"<td>{nf['A']} / {nf['B']}</td>"))
        parts.append("</table>")
    else:
        parts.append(sum_row(s, units, meta.get('n_targets', '')) + "</table>")
    parts.append(f"<p class=\"small meth\">Check (a): the English back-translated into {T['adj']} by a third model shares at least half of the unit's term lemmas with the source. Check (b): the two renderings agree on at least 70% of the unit's target terms. Check (c): a model judge, salted with 10 planted errors and 10 anchors it had to get right, finds at least 80% of the term renderings within the {T['lex']['short']} entry's senses, with at most 2 outside. A unit fails when it fails two of three.</p>")
    if P:
        parts.append(f"<p class=\"small meth\">Flags, under each passage: {FLAG_NOTE}. Sentence by sentence, each rendering is compared with the Greek for numbers, negations and words of more or less, "
                     "and for the names of drugs and parts of the body (a name in the English with none in the Greek, or a name in the Greek with none in the English). "
                     "These are word-matching tests: a flag often comes from a sentence pair that is aligned a little off, a paraphrase or a name the model kept in Greek, "
                     "and a passage with no flag is not checked by them either. The flags play no part in the unit verdicts.</p>")

    head_len = len(parts)
    unit_starts = []  # (parts index, book) per unit, for the split by book (v0.2.1)
    for u in units:
        unit_starts.append((len(parts), (u.get('books') or ['1'])[0]))
        uid = u["unit_id"]
        ck = checks["units"].get(uid, {})
        verdict = ck.get("verdict", "insufficient")
        rows = by_unit.get(uid, [])
        a_eng = ((rend["A"].get(uid) or {}).get("response") or {}).get("translation", "")
        b_eng = ((rend["B"].get(uid) or {}).get("response") or {}).get("translation", "")
        spans_g, spans_a, spans_b = [], [], []
        for r in rows:
            agree = r.get("agree")
            cls = "agree" if agree == "y" else ("differ" if agree == "n" else "one")
            lemma = r["dilemma_lemma"] or r["odycy_lemma"]
            spans_g.append((r["surface"].strip(".,;:·"), cls, f"{lemma} · A: {r['rendering_A']} · B: {r['rendering_B']}"))
            if r["rendering_A"]:
                spans_a.append((r["rendering_A"], cls, f"{r['surface']} ({lemma}) · B: {r['rendering_B'] or '—'}"))
            if r["rendering_B"]:
                spans_b.append((r["rendering_B"], cls, f"{r['surface']} ({lemma}) · A: {r['rendering_A'] or '—'}"))
        a_ck, b_ck, c_ck = ck.get("a", {}), ck.get("b", {}), ck.get("c", {})
        uk = T["uncertain_key"]
        if P:   # each half keeps its own markers: Kühn pages in books 1-5, entries in books 6-11
            mk, T["label"] = part_of[uid]["mk"], part_of[uid]["label"]
        parts.append(f"""<div class="unit {'fail' if verdict == 'fail' else ''}" id="{esc(uid)}">
<div class=uh><span class=id><a href="#{esc(uid)}">{esc(uid)}</a></span><span>{esc(u['locus'])}, ch. {esc(', '.join(u['chapters']))}</span>
<span class="tier-{u['difficulty_tier']}">difficulty {esc(u['difficulty_tier'])} ({u['punch_density_per100']}/100; thin {u['n_punch_thin']}, absent {u['n_punch_absent']})</span>
<span>(a) {mark(a_ck.get('verdict', 'not_run'))} (b) {mark(b_ck.get('verdict', 'n/a'))}{' ' + str(b_ck.get('agree')) + '/' + str(b_ck.get('n')) if b_ck.get('n') else ''} (c) {mark(c_ck.get('verdict', 'not_run'))}{' ' + str(c_ck.get('in_range')) + '/' + str(c_ck.get('n')) if c_ck.get('n') and c_ck.get('in_range') is not None else ''}
<span class=verdict>unit: {mark(verdict)}</span></span></div>
<div class=cols>
<div class="col grc" lang={src_lang}><div class=ch>{esc(T['col'])}</div>{highlight(u['greek'], spans_g, mk, T['label'])}</div>
<div class="col eng a"><div class=ch>Rendering A (fable-5-1){' · unsure: ' + esc(', '.join(((rend['A'].get(uid) or {}).get('response') or {}).get(uk, []) or [])) if ((rend['A'].get(uid) or {}).get('response') or {}).get(uk) else ''}</div>{highlight(a_eng, spans_a, mk, T['label']) if a_eng else '<em class=small>no rendering</em>'}</div>
<div class="col eng b"><div class=ch>Rendering B (opus-5-5){' · unsure: ' + esc(', '.join(((rend['B'].get(uid) or {}).get('response') or {}).get(uk, []) or [])) if ((rend['B'].get(uid) or {}).get('response') or {}).get(uk) else ''}</div>{highlight(b_eng, spans_b, mk, T['label']) if b_eng else '<em class=small>no rendering</em>'}</div>
</div>""")
        if P:
            parts.append(flags_html(flags.get(uid, []), src_lang))
        if rows:
            parts.append(f"<details><summary>Term table ({len(rows)} targets)</summary><table class=tt><tr><th>{T['adj']}</th><th>{T['lemma_th']}</th><th>{T['lex']['short']}</th><th>tier</th><th>A</th><th>B</th><th>agree</th><th>judge A / B</th></tr>")
            for r in rows:
                hw = clean_headword(r["lsj_headword"]) if galen else r["lsj_headword"]
                lk = hw if galen else link_headword(hw)
                lsj = f'<a class=lsj href="{T["lex"]["link"].format(hw=esc(lk))}">{esc(hw)}</a> <span class=lsj>{esc(r["lsj_entry_id"])}, {esc(r["lsj_sense_count"])} sense(s)</span>' if r["lsj_entry_id"] else f'<span class=lsj>{T["lex"]["missing"]}</span>'
                tier = " ".join(x for x in (r["punch_tier"] and f"{T['tier_prefix']}:{r['punch_tier']}", r["tier_v3"] and f"v3:{r['tier_v3']}", r["fourway"] and f"4w:{r['fourway']}") if x)
                parts.append(f"<tr><td>{esc(r['surface'])}</td><td>{esc(r['dilemma_lemma'])}<br><span class=lsj>{T['tagger']} {esc(r['odycy_lemma'])}</span></td><td>{lsj}</td><td class=small>{esc(tier)}</td>"
                             f"<td>{esc(r['rendering_A'])}{' <span class=unc>unsure</span>' if r['uncertain_A'] == 'y' else ''}</td><td>{esc(r['rendering_B'])}{' <span class=unc>unsure</span>' if r['uncertain_B'] == 'y' else ''}</td>"
                             f"<td>{esc(r['agree'])}</td><td class=small>{esc(r.get('judge_A', ''))} / {esc(r.get('judge_B', ''))}</td></tr>")
            parts.append("</table></details>")
        parts.append("</div>")
    parts.append(f"<h2>Licence and citation</h2><p class=\"small lic\">{esc(T['credit'])} The renderings and apparatus are machine output published as a draft under CC BY-SA 4.0 (a translation of a CC BY-SA text) by William Pepperman (Galen Density Project, Montblanc Tech LLC); cite as: Pepperman, W. ({built.year}). <i>{T['series']}</i>: {esc(T['author'])}, <i>{esc(w['title_lat'])}</i> ({esc(w['title_eng'])}), machine first draft v0.1, github.com/Montblanctech/Galen, {T['doi']}; and say that it is an unverified machine draft. Corrections: <a href=\"{ISSUE_URL}\">issue template</a>.</p></body></html>")
    dest = root / slug
    dest.mkdir(parents=True, exist_ok=True)
    # Long works are split into one page per book so a phone can open them (v0.2.1, 2026-11-09: the 697-unit
    # Composition of Drugs by Kind made a 7 MB page). The work's index then carries the header, the summary and a book list.
    foot_start = len(parts) - 1
    books = []
    for i, (start, bk) in enumerate(unit_starts):
        end = unit_starts[i + 1][0] if i + 1 < len(unit_starts) else foot_start
        if not books or books[-1][0] != bk:
            books.append([bk, start, end, 0])
        books[-1][2] = end
        books[-1][3] += 1
    for f in dest.glob("book-*.html"):
        f.unlink()
    if len(units) > SPLIT_OVER and len(books) > 1:
        nav = "<p class=\"small nav\">" + " · ".join(f'<a href="book-{bk}.html">Book {bk}</a>' for bk, *_ in books) + ' · <a href="./">contents</a></p>'
        for bk, a, b, n in books:
            # each book page gets its own title and description (they all carried the work's, 2026-11-13 audit)
            head0 = parts[0].replace(title_html, title_html.replace("<title>", f"<title>Book {bk} · ", 1), 1)
            head0 = head0.replace(desc_html, '<meta name=description content="' + esc(f"Book {bk} of {desc}") + '">', 1)
            (dest / f"book-{bk}.html").write_text("\n".join([head0] + parts[1:head_len] +[f"<h2>Book {bk} ({n} units)</h2>", nav] + parts[a:b] + [nav, parts[foot_start]]), encoding="utf-8")
        toc = ["<h2>Books</h2><ul>"] + [f'<li><a href="book-{bk}.html">Book {bk}</a>: {n} units</li>' for bk, a, b, n in books] + ["</ul>"]
        (dest / "index.html").write_text("\n".join(parts[:head_len] + toc + [parts[foot_start]]), encoding="utf-8")
    else:
        (dest / "index.html").write_text("\n".join(parts), encoding="utf-8")
    (dest / "data.json").write_text(json.dumps({"work": w, "units": units, "term_table": tt, "checks": checks, "renderings": {t: [{"unit_id": k, "model": v["model"], "backend": v["backend"], "translation": ((v.get("response") or {}).get("translation", ""))} for k, v in rend[t].items()] for t in RENDERINGS}}, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {dest / 'index.html'} ({(dest / 'index.html').stat().st_size:,} bytes), {len(units)} units, verdicts {dict(Counter(checks['units'].get(u['unit_id'], {}).get('verdict', 'none') for u in units))}")
    if not galen:   # the drafts index lists the Galen series only
        return
    # index of drafts: every work in WORKS whose page exists, in WORKS order (cycle 3 added eight works)
    items = []
    for sl, ww in WORKS.items():
        pdir = root / sl
        odir = out_dir(sl)
        if not (pdir / "index.html").exists() or not (odir / "units_meta.json").exists():
            continue
        mm = json.loads((odir / "units_meta.json").read_text(encoding="utf-8"))
        ss = (json.loads((odir / "checks.json").read_text(encoding="utf-8")).get("summary", {}) if (odir / "checks.json").exists() else {})
        items.append(f'<li><a href="{sl}/">{esc(ww["title_lat"])} ({esc(ww["title_eng"])})</a>, Kühn {esc(ww["kuhn_vol"])} {esc(ww["kuhn_pages"])}: '
                     f'{mm.get("n_units")} units, {draft_words(sl):,} Greek words, {(ss.get("unit_verdicts") or {}).get("fail", 0) if ss else "–"} units failing two or more checks.</li>')
    idx = root / "index.html"
    idx.write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Galen First Drafts</title>
<style>body{{font:16px/1.5 Georgia,serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222}}.small{{color:#555;font-size:.9em}}</style></head><body>
<h1>Galen First Drafts — machine first drafts in English, unverified (v0.1)</h1>
<p class=small>Author of the drafts series: William Pepperman (Galen Density Project). Each work carries its own citation line and version.</p>
<p class=small>Works of Galen with no complete published English translation by a scholar that we know of; each work's page names the earlier partial and other-language translations, and the unreviewed machine translations into English that Source Library (sourcelibrary.org) posted during 2026 (status and sources per work: <code>phase1/README_translation_status.md</code>), rendered twice by two language-model families with the same neutral prompt, aligned to the Greek, every technical term tied to its LSJ entry, three machine checks per unit, failures marked and kept. These are drafts for scholars to correct, not translations to quote. Spec: <code>firstdrafts_v0_spec.md</code> (cycle 1), <code>firstdrafts_v02_spec.md</code> (cycles 2 and 3).</p>
<ul>{"".join(items)}</ul>
<p class=small><a href="../">All project pages</a> · <a href="{ISSUE_URL}">Report a correction</a></p></body></html>""", encoding="utf-8")


if __name__ == "__main__":
    main()
    if "--dest" not in sys.argv:   # a page written elsewhere (scratch) never rebuilds the public landing page
        import landing  # the front page and the drafts index are rebuilt from every work's data (2026-11-10)
        landing.main()
