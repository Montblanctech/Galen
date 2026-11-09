"""Galen First Drafts v0, stage 5: one static page per work (spec: firstdrafts_v0_spec.md).

Reads outputs/firstdrafts/<slug>/ (units.jsonl, renderings_*.jsonl, alignment.json, term_table.csv,
checks.json, units_meta.json, align_meta.json) and writes docs/first-drafts/<slug>/index.html plus
docs/first-drafts/<slug>/data.json (the same data for reuse) and docs/first-drafts/index.html.
Greek beside both English renderings, page markers kept, target terms highlighted (green = the two
renderings agree, red = they differ), term table per unit, difficulty from the density map, the three
check marks and the unit verdict, the banner, and a link to the issue template. No model involved.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from datetime import date

from common import REPO, WORKS, out_dir, read_jsonl

RENDERINGS = {"A": "fable-5-1", "B": "opus-5-5"}
ISSUE_URL = "https://github.com/Montblanctech/Galen/issues/new?template=first-draft-correction.yml"
MARK = re.compile(r"\[(\d+)\]")


def esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def mark_pages(s: str) -> str:
    return MARK.sub(r'<span class=pb title="Kühn page">\1</span>', esc(s))


def highlight(text: str, spans: list[tuple[str, str, str]]) -> str:
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
    return MARK.sub(r'<span class=pb title="Kühn page"></span>', "".join(out))


SPLIT_OVER = 120  # units; above this a work is published one page per book


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="adversus-lycum")
    a = ap.parse_args()
    slug = a.work
    w = WORKS[slug]
    out = out_dir(slug)
    units = read_jsonl(out / "units.jsonl")
    rend = {t: {r["unit_id"]: r for r in read_jsonl(out / f"renderings_{s}.jsonl")} for t, s in RENDERINGS.items()}
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

    parts = []
    parts.append(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Galen, {esc(w['title_eng'])} — machine first draft v0.1</title>
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
.grc{{font-size:1.02em}} .eng{{}} .col h4{{margin:.3rem 0;font-size:.85em;color:#555;font-weight:normal}}
.pb{{display:inline-block;background:#eee;border:1px solid #bbb;border-radius:.3em;padding:0 .3em;font-size:.75em;color:#333;vertical-align:super;margin:0 .15em}}
mark.agree{{background:#dff3df}} mark.differ{{background:#f9d6d6}} mark.one{{background:#eee}}
.chk{{display:inline-block;border-radius:.4em;padding:0 .45em;font-size:.8em;border:1px solid #999}} .chk.ok{{background:#dff3df;border-color:#7a7}} .chk.bad{{background:#f9d6d6;border-color:#a33}} .chk.na{{background:#eee}} .chk.mixed{{background:#fbefc9;border-color:#c90}}
.tier-low{{color:#363}} .tier-mid{{color:#b60}} .tier-high{{color:#a33}}
details{{margin:.4rem 0}} summary{{cursor:pointer;color:#444;font-size:.9em}}
table.tt{{border-collapse:collapse;width:100%;font-size:.86em}} table.tt th,table.tt td{{border-bottom:1px solid #e5e5e5;padding:.15rem .4rem;text-align:left;vertical-align:top}}
.unc{{color:#a33;font-size:.8em}} .lsj{{color:#555;font-size:.85em}}
.verdict{{font-weight:bold}}
</style></head><body>
<div class=banner><strong>Machine first draft, unverified, v0.1.</strong> Two language models translated this text independently; no scholar has checked it. Red marks show where the machine checks fail. The apparatus says where to look, not that the text is right. <a href="{ISSUE_URL}">Report a correction</a> · <a href="../../">project pages</a></div>
<h1>Galen, <em>{esc(w['title_lat'])}</em> ({esc(w['title_eng'])}), Kühn {esc(w['kuhn_vol'])} {esc(w['kuhn_pages'])}</h1>
<p class=small>Greek: {esc(w['source_note'])}. Rendering A: <code>claude-fable-5-1</code>; rendering B: <code>claude-opus-5-5</code>; same neutral prompt, no glossary, fresh context, built {date.today().isoformat()}. Method, numbers and what the checks cannot catch: <a href="https://github.com/Montblanctech/Galen/tree/main/galen-density-map/outputs/firstdrafts/{slug}">README and data</a>; pre-registered thresholds: <code>{esc(w.get('spec', 'firstdrafts_v0_spec.md'))}</code>. Terms: <mark class=agree>green</mark> = both renderings agree on the term (after normalisation), <mark class=differ>red</mark> = they differ, <mark class=one>grey</mark> = one rendering reported. Hover a mark for the Greek lemma and the other rendering. Unit difficulty = punch-list density per 100 tokens from the terminology density map (tercile within this work).</p>
""")
    # summary table
    parts.append("<table class=sum><tr><th>units</th><th>Greek words</th><th>targets</th><th>(a) back-translation pass</th><th>(b) A/B agreement pass</th><th>(c) LSJ judge pass</th><th>units failing ≥2 checks</th></tr>")
    def rs(k):
        v = s.get(k) or {}
        return f"{v.get('pass', '–')}/{(v.get('pass') or 0) + (v.get('fail') or 0)}" if v else "not run"
    parts.append(f"<tr><td>{len(units)}</td><td>{meta.get('n_tei_words', '')}</td><td>{meta.get('n_targets', '')}</td><td>{rs('a')}</td><td>{rs('b')} (term level {(s.get('b_term_level') or {}).get('pct', '–')}%)</td><td>{rs('c')}{' · judge gate ' + str((s.get('c_gate') or {}).get('correct')) + '/' + str((s.get('c_gate') or {}).get('controls')) if s.get('c_gate') else ''}</td><td>{(s.get('unit_verdicts') or {}).get('fail', 0)}</td></tr></table>")
    parts.append("<p class=small>Check (a): the English back-translated into Greek by a third model shares at least half of the unit's term lemmas with the source. Check (b): the two renderings agree on at least 70% of the unit's target terms. Check (c): a model judge, salted with 10 planted errors and 10 anchors it had to get right, finds at least 80% of the term renderings within the LSJ entry's senses, with at most 2 outside. A unit fails when it fails two of three.</p>")

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
        parts.append(f"""<div class="unit {'fail' if verdict == 'fail' else ''}" id="{esc(uid)}">
<div class=uh><span class=id><a href="#{esc(uid)}">{esc(uid)}</a></span><span>{esc(u['locus'])}, ch. {esc(', '.join(u['chapters']))}</span>
<span class="tier-{u['difficulty_tier']}">difficulty {esc(u['difficulty_tier'])} ({u['punch_density_per100']}/100; thin {u['n_punch_thin']}, absent {u['n_punch_absent']})</span>
<span>(a) {mark(a_ck.get('verdict', 'not_run'))} (b) {mark(b_ck.get('verdict', 'n/a'))}{' ' + str(b_ck.get('agree')) + '/' + str(b_ck.get('n')) if b_ck.get('n') else ''} (c) {mark(c_ck.get('verdict', 'not_run'))}{' ' + str(c_ck.get('in_range')) + '/' + str(c_ck.get('n')) if c_ck.get('n') and c_ck.get('in_range') is not None else ''}
<span class=verdict>unit: {mark(verdict)}</span></span></div>
<div class=cols>
<div class="col grc"><h4>Greek (Kühn)</h4>{highlight(u['greek'], spans_g)}</div>
<div class="col eng"><h4>Rendering A (fable-5-1){' · unsure: ' + esc(', '.join(((rend['A'].get(uid) or {}).get('response') or {}).get('uncertain_greek', []) or [])) if ((rend['A'].get(uid) or {}).get('response') or {}).get('uncertain_greek') else ''}</h4>{highlight(a_eng, spans_a) if a_eng else '<em class=small>no rendering</em>'}</div>
<div class="col eng"><h4>Rendering B (opus-5-5){' · unsure: ' + esc(', '.join(((rend['B'].get(uid) or {}).get('response') or {}).get('uncertain_greek', []) or [])) if ((rend['B'].get(uid) or {}).get('response') or {}).get('uncertain_greek') else ''}</h4>{highlight(b_eng, spans_b) if b_eng else '<em class=small>no rendering</em>'}</div>
</div>""")
        if rows:
            parts.append(f"<details><summary>Term table ({len(rows)} targets)</summary><table class=tt><tr><th>Greek</th><th>Dilemma lemma</th><th>LSJ</th><th>tier</th><th>A</th><th>B</th><th>agree</th><th>judge A / B</th></tr>")
            for r in rows:
                lsj = f'<a class=lsj href="https://logeion.uchicago.edu/{esc(r["lsj_headword"])}">{esc(r["lsj_headword"])}</a> <span class=lsj>{esc(r["lsj_entry_id"])}, {esc(r["lsj_sense_count"])} sense(s)</span>' if r["lsj_entry_id"] else '<span class=lsj>no Perseus-LSJ entry</span>'
                tier = " ".join(x for x in (r["punch_tier"] and f"punch:{r['punch_tier']}", r["tier_v3"] and f"v3:{r['tier_v3']}", r["fourway"] and f"4w:{r['fourway']}") if x)
                parts.append(f"<tr><td>{esc(r['surface'])}</td><td>{esc(r['dilemma_lemma'])}<br><span class=lsj>odyCy {esc(r['odycy_lemma'])}</span></td><td>{lsj}</td><td class=small>{esc(tier)}</td>"
                             f"<td>{esc(r['rendering_A'])}{' <span class=unc>unsure</span>' if r['uncertain_A'] == 'y' else ''}</td><td>{esc(r['rendering_B'])}{' <span class=unc>unsure</span>' if r['uncertain_B'] == 'y' else ''}</td>"
                             f"<td>{esc(r['agree'])}</td><td class=small>{esc(r.get('judge_A', ''))} / {esc(r.get('judge_B', ''))}</td></tr>")
            parts.append("</table></details>")
        parts.append("</div>")
    parts.append(f"<h2>Licence and citation</h2><p class=small>Greek text CC BY-SA 4.0 (First1KGreek / Open Greek and Latin). The renderings and apparatus are machine output published as a draft under CC BY 4.0 by William Pepperman (Galen Density Project, Montblanc Tech LLC); cite as: Pepperman, W. ({date.today().year}). <i>Galen First Drafts</i>: Galen, <i>{esc(w['title_lat'])}</i> ({esc(w['title_eng'])}), machine first draft v0.1, github.com/Montblanctech/Galen, concept DOI 10.5281/zenodo.21561962; and say that it is an unverified machine draft. Corrections: <a href=\"{ISSUE_URL}\">issue template</a>.</p></body></html>")
    dest = REPO / "docs" / "first-drafts" / slug
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
        nav = "<p class=small>" + " · ".join(f'<a href="book-{bk}.html">Book {bk}</a>' for bk, *_ in books) + ' · <a href="./">contents</a></p>'
        for bk, a, b, n in books:
            (dest / f"book-{bk}.html").write_text("\n".join(parts[:head_len] + [f"<h2>Book {bk} ({n} units)</h2>", nav] + parts[a:b] + [nav, parts[foot_start]]), encoding="utf-8")
        toc = ["<h2>Books</h2><ul>"] + [f'<li><a href="book-{bk}.html">Book {bk}</a>: {n} units</li>' for bk, a, b, n in books] + ["</ul>"]
        (dest / "index.html").write_text("\n".join(parts[:head_len] + toc + [parts[foot_start]]), encoding="utf-8")
    else:
        (dest / "index.html").write_text("\n".join(parts), encoding="utf-8")
    (dest / "data.json").write_text(json.dumps({"work": w, "units": units, "term_table": tt, "checks": checks, "renderings": {t: [{"unit_id": k, "model": v["model"], "backend": v["backend"], "translation": ((v.get("response") or {}).get("translation", ""))} for k, v in rend[t].items()] for t in RENDERINGS}}, ensure_ascii=False), encoding="utf-8")
    # index of drafts: every work in WORKS whose page exists, in WORKS order (cycle 3 added eight works)
    items = []
    for sl, ww in WORKS.items():
        pdir = REPO / "docs" / "first-drafts" / sl
        odir = out_dir(sl)
        if not (pdir / "index.html").exists() or not (odir / "units_meta.json").exists():
            continue
        mm = json.loads((odir / "units_meta.json").read_text(encoding="utf-8"))
        ss = (json.loads((odir / "checks.json").read_text(encoding="utf-8")).get("summary", {}) if (odir / "checks.json").exists() else {})
        items.append(f'<li><a href="{sl}/">{esc(ww["title_lat"])} ({esc(ww["title_eng"])})</a>, Kühn {esc(ww["kuhn_vol"])} {esc(ww["kuhn_pages"])}: '
                     f'{mm.get("n_units")} units, {mm.get("n_tei_words")} Greek words, {(ss.get("unit_verdicts") or {}).get("fail", 0) if ss else "–"} units failing two or more checks.</li>')
    idx = REPO / "docs" / "first-drafts" / "index.html"
    idx.write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Galen First Drafts</title>
<style>body{{font:16px/1.5 Georgia,serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222}}.small{{color:#555;font-size:.9em}}</style></head><body>
<h1>Galen First Drafts — machine first translations, unverified (v0.1)</h1>
<p class=small>Author of the drafts series: William Pepperman (Galen Density Project). Each work carries its own citation line and version.</p>
<p class=small>Works of Galen with no English translation, most of them with no translation in any modern language (status and sources per work: <code>phase1/README_translation_status.md</code>), rendered twice by two language-model families with the same neutral prompt, aligned to the Greek, every technical term tied to its LSJ entry, three machine checks per unit, failures marked and kept. These are drafts for scholars to correct, not translations to quote. Spec: <code>firstdrafts_v0_spec.md</code> (cycle 1), <code>firstdrafts_v02_spec.md</code> (cycles 2 and 3).</p>
<ul>{"".join(items)}</ul>
<p class=small><a href="../">All project pages</a> · <a href="{ISSUE_URL}">Report a correction</a></p></body></html>""", encoding="utf-8")
    print(f"wrote {dest / 'index.html'} ({(dest / 'index.html').stat().st_size:,} bytes), {len(units)} units, verdicts {dict(Counter(checks['units'].get(u['unit_id'], {}).get('verdict', 'none') for u in units))}")


if __name__ == "__main__":
    main()
