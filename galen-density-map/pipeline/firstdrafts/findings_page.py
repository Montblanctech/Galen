"""Galen First Drafts — the findings catalogue page: docs/findings/index.html (+ findings.json) from outputs/firstdrafts/findings/.

Every item links to its passage in the draft. The page says what the catalogue is: items found by model readers in
unverified machine drafts, each quote and Greek word checked against the files, the summaries not checked by a scholar.

  python -X utf8 pipeline/firstdrafts/findings_page.py
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GDM, WORKS, read_jsonl  # noqa: E402

REPO = GDM.parent
DOCS = REPO / "docs"
FD = DOCS / "first-drafts"
SRC = GDM / "outputs" / "firstdrafts" / "findings" / "findings.jsonl"
RANK = GDM / "outputs" / "firstdrafts" / "findings" / "rank.jsonl"
VERDICTS = [GDM / "outputs" / "firstdrafts" / "findings" / f for f in ("verdict_galen_work.jsonl", "verdict_lost_source.jsonl")]
# 2026-11-11 attestation check of every 'lost author/work' and 'Galen's own work' item against Fichtner 2023 and the fragment
# collections. Known only from the passage itself, per the check's evidence:
ONLY_FROM_HERE = {372}   # 375 removed 2026-11-11: one of its two works is in Galen's own list (Fichtner 243)

# Corrections after a reading of a random sample against the Greek (2026-11-11; record in
# firstdrafts_sample_read_2026-11-11.md). Keyed by the item's index in findings.jsonl; each corrected item says so.
CORRECTIONS = {
    64: {"summary": "Many who operate on hernias apply the phoinikine plaster immediately after the operation, carrying on the "
                    "treatment with affusions and poultices alongside it."},
    121: {"summary": "In Heras's plaster for fractured limbs the draft gives scraped verdigris as 16 (ιστ΄) minae, against 1 mina of "
                     "litharge and pitch, which is impossible as a weight; the Greek probably means a sixteenth of a mina. The boiling "
                     "instruction also has a doubled 'until (ἕως ἕως)'.",
          "note": "The Greek has ἰοῦ ξυστοῦ μνᾶς ιστ΄. Read as a numeral that is 16 minae; read as a fraction it is a sixteenth of a "
                  "mina, and the next ingredient is written out as μνᾶς ἑκκαιδέκατον ('a sixteenth of a mina'). If so, the draft, not "
                  "the Greek, is wrong here."},
    647: {"category": "claim"},
    449: {"summary": "Galen injured his own shoulder in the wrestling school in his thirty-fifth year: the collarbone was pulled away, "
                    "and he bore tight bandaging for forty days until it was drawn back to the head of the arm-bone, so that people "
                    "who see it now doubt it was ever torn. He could not cure any other grown man the same way, because none could "
                    "bear the bandaging."},
    525: {"note": "The quoted address carries on in the extant text (Kühn XI 332-336), so this is probably part of On the Power of "
                  "Purgative Drugs itself, not a separate lost pamphlet.",
          "attestation": "Probably part of the extant work"},
    375: {"note": "Outside knowledge: both works are lost. The work on Hippocratic anatomy is in Galen's own list of his books "
                  "(Fichtner 243); the essay on the plague in Thucydides seems to be known only from this passage."},
}


def attestation(i: int, v: dict) -> tuple[str, str]:
    if not v or v.get("verdict") == "no_work":
        return "", ""
    if i in ONLY_FROM_HERE:
        return "Apparently known only from this passage (our check)", v.get("evidence", "")
    return {"known": "Known elsewhere", "known_extant": "Known elsewhere (the work survives)", "known_lost": "Known elsewhere (the work is lost)",
            "known_but_new_detail": "Known author; this detail may be new", "unsure": "Not found elsewhere by our check",
            "only_here": "Not found elsewhere by our check"}.get(v.get("verdict"), ""), (v.get("evidence", "") + (" " + v["note"] if v.get("note") else "")).strip()   # {i, s, why}: a model reader's 1-5 score for general interest
CATS = [("person", "People"), ("lost_source", "Lost authors and works"), ("galen_work", "Galen's own works and life"), ("recipe", "Recipes and remedies"),
        ("case", "Cases"), ("procedure", "Procedures"), ("place_event", "Places and events"), ("daily_life", "Daily life, trade, measures"),
        ("claim", "Claims and arguments"), ("doubt", "Doubts: where the draft or the text may be wrong")]
ISSUE_URL = "https://github.com/Montblanctech/Galen/issues/new?template=first-draft-correction.yml"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def page_for(slug: str, uid: str, cache: dict) -> str:
    if slug not in cache:
        books = sorted((FD / slug).glob("book-*.html"))
        cache[slug] = [(b.name, b.read_text(encoding="utf-8")) for b in books]
    for name, text in cache[slug]:
        if f'id="{uid}"' in text:
            return name
    return ""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    items = read_jsonl(SRC)
    cache: dict = {}
    order = {c: i for i, (c, _) in enumerate(CATS)}
    rank = {r["i"]: r for r in read_jsonl(RANK)} if RANK.exists() else {}
    ver = {v["i"]: v for f in VERDICTS if f.exists() for v in read_jsonl(f)}
    for i, r in enumerate(items):
        r["_s"] = rank.get(i, {}).get("s", 0)
        r["_why"] = rank.get(i, {}).get("why", "")
        r["_att"], r["_ev"] = attestation(i, ver.get(i))
        cx = CORRECTIONS.get(i, {})
        r["summary"] = cx.get("summary", r["summary"])
        r["note"] = cx.get("note", r.get("note", ""))
        r["category"] = cx.get("category", r["category"])
        if "attestation" in cx:
            r["_att"] = cx["attestation"]
        r["_fix"] = "Corrected 2026-11-11 after a reading against the Greek." if cx else ""
    items.sort(key=lambda r: (-r["_s"], order.get(r["category"], 99), r["work"], r["unit_id"]))
    rows = []
    for r in items:
        slug = r["work"]
        href = f"../first-drafts/{slug}/{page_for(slug, r['unit_id'], cache)}#{r['unit_id']}"
        rows.append({"c": r["category"], "w": slug, "wt": WORKS[slug]["title_eng"], "t": r["title"], "s": r["summary"], "q": r["quote"], "g": r["greek"],
                     "l": r["locus"], "h": href, "k": r["checks"], "f": r["confidence"], "n": r.get("note", ""), "r": r["_s"], "a": r["_att"], "e": r["_ev"], "x": r["_fix"]})
    DOCS.joinpath("findings").mkdir(exist_ok=True)
    (DOCS / "findings" / "findings.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    n_c = Counter(r["c"] for r in rows)
    works = sorted({(r["w"], r["wt"]) for r in rows}, key=lambda x: x[1])
    cat_opts = "".join(f'<option value="{c}">{esc(lbl)} ({n_c.get(c, 0)})</option>' for c, lbl in CATS if n_c.get(c))
    work_opts = "".join(f'<option value="{w}">{esc(t)}</option>' for w, t in works)
    labels = json.dumps(dict(CATS), ensure_ascii=False)
    doc = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>What the drafts say</title><meta name=description content="A catalogue of people, lost works, recipes, cases and claims found in the Galen First Drafts, each item linked to its passage.">
<link rel=stylesheet href="../site.css">
<style>
.fwrap{{max-width:62rem;margin:0 auto;padding:0 1.25rem}}
.controls{{display:flex;flex-wrap:wrap;gap:.6rem;margin:1.2rem 0}}
.controls select,.controls input{{font:15px/1.3 system-ui,-apple-system,"Segoe UI",sans-serif;padding:.5rem .6rem;border:1px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink);min-width:0}}
.controls input{{flex:1 1 14rem}}
.item{{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:1rem 1.1rem;margin:.8rem 0}}
.item h2{{font-size:1.08rem;margin:0 0 .3rem;line-height:1.35}}
.item .meta{{font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);margin-bottom:.5rem}}
.item blockquote{{margin:.5rem 0;padding-left:.8rem;border-left:3px solid var(--accent);font-size:.98rem}}
.item .gk{{font-size:.95rem;color:var(--muted)}}
.item .note{{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);margin-top:.4rem}}
.tag{{display:inline-block;font:600 11px/1 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-right:.5rem}}
.warnflag{{color:var(--none)}}
#count{{font:14px/1.4 system-ui,sans-serif;color:var(--muted)}}
</style></head><body>
<header class=hero><div class=fwrap>
<div class=kicker>Galen First Drafts</div>
<h1>What the drafts say</h1>
<p class=lede>{len(rows):,} items from the {len(works)} works: people, lost authors and books, Galen's own life and writings, recipes, cases, procedures, prices and measures, and the places where the draft or the Greek itself may be wrong. Each item quotes the draft and links to the passage, with the Greek beside it. The page opens on the highlights; the order, from most to least interesting to a general reader, is a model reader's judgement, not a scholar's.</p>
<p class=warn>How this was made: model readers went through every passage of the machine drafts and noted what a researcher would want. A script then checked that every quotation is word for word in the draft and every Greek word is in that passage's Greek. Nothing else was checked. The summaries are the readers' and have not been read by a scholar, and the drafts themselves are unverified. Much of this has been read by specialists in the Greek; what is new is that it can now be read in English. Treat each item as a pointer to the passage, not as a finding to cite. Every item about a lost author or book, or about Galen's own works, was then checked by model researchers (not a specialist) against Fichtner's catalogue of Galen's works (2023), the standard fragment collections and the web: none was shown to be unknown to scholarship, a few could not be placed, and each such item says what was found and where. One, Galen's lost <em>On the Innate Heat</em>, seems to be known only from the passage shown here. A reading of 40 items chosen at random against the Greek (2026-11-11) found one summary that misstated the passage; it and the other problems that reading found are corrected and marked. <a href="{ISSUE_URL}">Report a correction</a>.</p>
</div></header>
<section><div class=fwrap>
<div class=controls><select id=only aria-label="Show"><option value="5">Highlights</option><option value="">Everything, most interesting first</option></select><select id=cat aria-label="Kind of item"><option value="">All kinds ({len(rows):,})</option>{cat_opts}</select><select id=work aria-label="Work"><option value="">All works</option>{work_opts}</select><input id=q type=search aria-label="Search the items" placeholder="Search: a name, a drug, a word"></div>
<div id=count></div><div id=list></div>
<p class=small><a href="../">Galen First Drafts</a> · <a href="../first-drafts/">All drafts</a> · <a href="findings.json">findings.json</a></p>
</div></section>
<script>
const L={labels};
let D=[];
const e=s=>String(s||'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
function show(){{
  const o=document.getElementById('only').value, c=document.getElementById('cat').value, w=document.getElementById('work').value, q=document.getElementById('q').value.trim().toLowerCase();
  const R=D.filter(r=>(!o||r.r>=+o)&&(!c||r.c===c)&&(!w||r.w===w)&&(!q||(r.t+' '+r.s+' '+r.q+' '+r.g+' '+r.n+' '+r.wt).toLowerCase().includes(q)));
  document.getElementById('count').textContent=R.length+' of '+D.length+' items';
  document.getElementById('list').innerHTML=R.slice(0,400).map(r=>`<div class=item><div class=meta><span class=tag>${{e(L[r.c]||r.c)}}</span>${{e(r.wt)}} · <a href="${{e(r.h)}}">${{e(r.l)}}</a>${{r.k&&r.k!=='pass'?` · <span class=warnflag>passage checks: ${{e(r.k)}}</span>`:''}} · reader's confidence ${{e(r.f)}}${{r.x?` · <span class=warnflag>${{e(r.x)}}</span>`:''}}</div><h2>${{e(r.t)}}</h2><div>${{e(r.s)}}</div><blockquote>“${{e(r.q)}}”</blockquote><div class=gk>${{e(r.g)}}</div>${{r.n?`<div class=note>${{e(r.n)}}</div>`:''}}${{r.a?`<div class=note><b>${{e(r.a)}}.</b> ${{e(r.e)}}</div>`:''}}</div>`).join('')+(R.length>400?'<p class=small>Showing the first 400; narrow the filter to see the rest.</p>':'');
}}
fetch('findings.json').then(r=>r.json()).then(d=>{{D=d;show();}});
['only','cat','work','q'].forEach(id=>document.getElementById(id).addEventListener('input',show));
</script></body></html>"""
    (DOCS / "findings" / "index.html").write_text(doc, encoding="utf-8")
    print("findings page:", len(rows), "items;", dict(n_c))


if __name__ == "__main__":
    main()
