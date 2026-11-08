"""Galen Term Explorer — a static, searchable page over every key lemma of the density map (2026-11-07).

For translators and students: type a Galenic word (or a stem) and see what the project knows: keyness vs the rest of
Greek, LSJ tier, punch-list status and v3 label, Dilemma's headword (artifact flag), Morpheus floor share, Galen
frequency, two attested contexts, and for punch rows the attributed concordance size and Kühn loci sample. Nothing is
written by a model; every field is a measurement or an attribution already in the repo.

Writes docs/galen-terms/terms.json (one record per key lemma, 10,6xx) and docs/galen-terms/index.html (vanilla JS,
client-side search, no external assets). Run in the audit venv (Dilemma for the non-punch rows' headword flag).
"""
from __future__ import annotations

import csv
import json
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402
from lib.census import load_census, medical_urn_stems  # noqa: E402
from lib.config import load_config  # noqa: E402

DOCS = ROOT.parent / "docs" / "galen-terms"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


HTML = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Galen Term Explorer</title>
<style>body{font:15px/1.45 Georgia,serif;max-width:1100px;margin:1.5rem auto;padding:0 1rem;color:#222}input{font:inherit;width:100%;padding:.5rem;border:1px solid #999}
table{border-collapse:collapse;width:100%;margin-top:1rem}th,td{border-bottom:1px solid #ddd;padding:.3rem .45rem;text-align:left;vertical-align:top;font-size:.93em}th{background:#f3f1ec;position:sticky;top:0}
.g{color:#111;font-size:1.05em}.s{color:#666;font-size:.85em}.t-absent{color:#a33}.t-thin{color:#b60}.t-rich{color:#363}.flag{color:#a33}.ctx{font-size:.85em;color:#333}
.pill{display:inline-block;border:1px solid #bbb;border-radius:.6em;padding:0 .4em;font-size:.8em;margin-right:.2em}</style></head><body>
<h1>Galen Term Explorer</h1>
<p class=s>Every lemma that Galen's medical works over-use against the rest of Greek (<span id=n></span> key lemmas; odyCy 0.7.0 lemmas, First1KGreek text). Type a word, a stem, or a filter: <code>tier:absent</code>, <code>punch</code>, <code>v3:real_no_perseus_lsj</code>, <code>flag:differs</code>, <code>quad:polysemy_risk</code>, <code>pos:NOUN</code>. Nothing here was written by a model: keyness, LSJ tiers, Dilemma headwords, reader verdicts and loci are measurements and attributions from the Galen Density Project (v3.0 lab build). Report, never patch.</p>
<input id=q placeholder="search: θηριακ   or   tier:absent punch   or   flag:differs pos:NOUN" autofocus>
<p class=s id=count></p><table><thead><tr><th>lemma</th><th>Galen</th><th>keyness</th><th>LSJ</th><th>Dilemma headword</th><th>punch / v3</th><th>attested contexts</th></tr></thead><tbody id=rows></tbody></table>
<script>
let D=[];fetch('terms.json').then(r=>r.json()).then(j=>{D=j.records;document.getElementById('n').textContent=j.n.toLocaleString();render(D.slice(0,200),j.n)});
function strip(s){return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase()}
function render(rows,total){const tb=document.getElementById('rows');tb.innerHTML='';for(const r of rows){const tr=document.createElement('tr');
tr.innerHTML=`<td><span class=g>${r.l}</span><br><span class=s>${r.pos} · ${r.surf.join(' ')}</span></td><td>${r.n.toLocaleString()}<br><span class=s>${r.per10k}/10k · ${r.works} works</span></td><td>${r.ll}<br><span class=s>ref ${r.ref10k}/10k · ${r.quad}</span></td><td class="t-${r.tier}">${r.tier}${r.senses?` (${r.senses})`:''}<br><span class=s>${r.lsjhw||''}</span></td><td>${r.hw||'—'} ${r.hwflag==='differs'?'<span class=flag>≠</span>':''}<br><span class=s>${r.consensus?'consensus '+r.consensus:''}${r.name==='y'?' · name':''}</span></td><td>${r.punch?`<span class=pill>punch</span><br>${r.v3}${r.att?`<br><span class=s>${r.att} att. · Kühn ${r.kuhn}</span>`:''}`:''}</td><td class=ctx>${r.ctx.map(c=>c).join('<br>')}</td>`;tb.appendChild(tr)}
document.getElementById('count').textContent=`${rows.length} shown of ${total}`}
document.getElementById('q').addEventListener('input',e=>{const parts=e.target.value.trim().split(/\\s+/).filter(Boolean);let rows=D;const text=[];for(const p of parts){const m=p.match(/^(tier|v3|flag|quad|pos):(.*)$/);if(m){const[,k,v]=m;rows=rows.filter(r=>({tier:r.tier,v3:r.v3,flag:r.hwflag,quad:r.quad,pos:r.pos})[k]===v)}else if(p==='punch'){rows=rows.filter(r=>r.punch)}else text.push(strip(p))}
if(text.length){rows=rows.filter(r=>{const h=strip(r.l)+' '+strip(r.hw||'')+' '+strip(r.consensus||'');return text.every(t=>h.includes(t))})}render(rows.slice(0,300),rows.length)});
</script></body></html>"""


def main() -> None:
    if "--author" in sys.argv:
        return author_main(sys.argv[sys.argv.index("--author") + 1])
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    DOCS.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    census = load_census((ROOT.parent / "phase1" / "galen_ogl_census.json").resolve())
    med = medical_urn_stems(cfg, census)
    key = [r for r in csv.DictReader((ROOT / "outputs" / "keyness_scores.csv").open(encoding="utf-8")) if r.get("direction", "overused") == "overused"]
    lemmas = {nfc(r["lemma"]): r for r in key}
    v3 = {nfc(r["lemma"]): r for r in csv.DictReader((ROOT / "outputs" / "phase3" / "punch_list_v3.csv").open(encoding="utf-8"))}
    attrib = {nfc(r["lemma"]): r for r in csv.DictReader((ROOT / "outputs" / "phase3" / "attributed_punch_list.csv").open(encoding="utf-8"))}
    lsj = json.load((ROOT / "data" / "lsj" / "_lsj_index.json").open(encoding="utf-8"))
    fw = {nfc(r["lemma"]): r["quadrant"] for r in csv.DictReader((ROOT / "outputs" / "four_way_classification.csv").open(encoding="utf-8"))}

    # contexts + surfaces from the medical token streams
    occ: dict[str, list[tuple[str, str]]] = defaultdict(list)
    surfs: dict[str, Counter] = defaultdict(Counter)
    works_of: dict[str, set] = defaultdict(set)
    for p in sorted((ROOT / "data" / "lemmatized" / "galen").glob("*.jsonl")):
        if p.stem not in med:
            continue
        toks = [json.loads(l) for l in p.open(encoding="utf-8")]
        for i, t in enumerate(toks):
            lem = nfc(t.get("lemma", ""))
            if lem in lemmas:
                surfs[lem][nfc(t.get("surface", ""))] += 1
                works_of[lem].add(p.stem)
                if len(occ[lem]) < 12:
                    lo, hi = max(0, i - 7), min(len(toks), i + 8)
                    occ[lem].append((p.stem.split("_")[3], " ".join(f"[{x['surface']}]" if j == i else x["surface"] for j, x in enumerate(toks[lo:hi], lo))))
    print(f"scanned medical tokens ({time.time()-t0:.0f}s)", flush=True)

    dil = None
    try:
        from dilemma import Dilemma  # type: ignore

        dil = Dilemma(lang="grc", convention="lsj")
    except Exception as exc:
        print(f"Dilemma unavailable: {exc}")
    memo: dict[str, str] = {}

    def dil_hw(l: str) -> str:
        if dil is None:
            return ""
        if l not in memo:
            try:
                memo[l] = nfc(dil.lemmatize(l, guess=False) or "")
            except Exception:
                memo[l] = ""
        return memo[l]

    records = []
    for lem, r in lemmas.items():
        hit = lsj.get(lemma_to_lookup_key(lem))
        senses = int(hit.get("lsj_sense_count") or 0) if hit else None
        tier = "absent" if not senses else ("thin" if senses == 1 else "rich")
        p3 = v3.get(lem)
        a = attrib.get(lem, {})
        by_work: dict[str, str] = {}
        for w, c in occ[lem]:
            by_work.setdefault(w, c)
        ctxs = list(by_work.values())[:2]
        dh = p3["dilemma_top_headword"] if p3 and p3.get("dilemma_top_headword") else dil_hw(lem)
        records.append({
            "l": lem, "k": blind(lem), "pos": r.get("pos", ""), "n": int(float(r.get("galen_raw_count") or 0)),
            "per10k": round(float(r.get("galen_per10k") or 0), 2), "ref10k": round(float(r.get("reference_per10k") or 0), 3),
            "ll": round(float(r.get("log_likelihood") or 0), 1), "tier": tier, "senses": senses or 0,
            "quad": fw.get(lem, ""), "punch": bool(p3), "v3": p3["tier_v3"] if p3 else "",
            "hw": dh, "hwflag": ("" if not dh else ("same" if blind(dh) == blind(lem) else "differs")),
            "consensus": (p3.get("headword_consensus") or "") if p3 else "", "name": (p3.get("proper_name") or "") if p3 else "",
            "m1": (p3.get("m1_admissible_share") or "") if p3 else "", "works": len(works_of[lem]),
            "surf": [f"{s}:{c}" for s, c in surfs[lem].most_common(4)], "ctx": ctxs,
            "att": a.get("concordance_n", ""), "kuhn": ";".join([x for x in (a.get("kuhn_loci") or "").split(";") if x.strip()][:3]),
            "lsjhw": hit.get("lsj_headword", "") if hit else "",
        })
    records.sort(key=lambda x: -x["ll"])
    (DOCS / "terms.json").write_text(json.dumps({"generated": time.strftime("%Y-%m-%d"), "n": len(records), "records": records}, ensure_ascii=False), encoding="utf-8")
    html = HTML

    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({"records": len(records), "punch": sum(r["punch"] for r in records), "dilemma_differs": sum(r["hwflag"] == "differs" for r in records),
                      "tiers": dict(Counter(r["tier"] for r in records)), "elapsed_s": round(time.time() - t0, 1)}, ensure_ascii=False))


def author_main(tlg: str) -> None:
    """Per-author page from outputs/t3/<tlg>/term_map.csv + punch_list.csv -> docs/terms/<tlg>/{index.html,terms.json}.

    Same page as the Galen explorer. Fields are copied from the term map; nothing is computed by a model.
    If terms.json would exceed 8 MB the contexts column is dropped and the footer says so.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    src = ROOT / "outputs" / "t3" / tlg
    rows = list(csv.DictReader((src / "term_map.csv").open(encoding="utf-8")))
    punch = {nfc(r["lemma"]) for r in csv.DictReader((src / "punch_list.csv").open(encoding="utf-8"))}
    summ = json.load((src / "summary.json").open(encoding="utf-8"))
    name = tlg
    for e in json.load((ROOT / "data" / "reference_corpus" / "_first1k_catalog.json").open(encoding="utf-8"))["catalog"]:
        if e["urn"].split(":")[3].split(".")[0] == tlg:
            name = e["group_name"]
            break
    flagmap = {"dilemma_differs": "differs", "dilemma_unresolved": "unresolved"}

    def build(with_ctx: bool) -> list[dict]:
        out = []
        for r in rows:
            lem = nfc(r["lemma"])
            hw = nfc(r.get("dilemma_headword_of_lemma", ""))
            fl = r.get("artifact_flag", "")
            out.append({
                "l": lem, "k": blind(lem), "pos": r["pos"], "n": int(float(r["author_raw"] or 0)),
                "per10k": round(float(r["author_per10k"] or 0), 2), "ref10k": round(float(r["ref_per10k"] or 0), 3),
                "ll": round(float(r["log_likelihood"] or 0), 1), "tier": r["lsj_tier"], "senses": int(float(r["lsj_sense_count"] or 0)),
                "quad": "", "punch": lem in punch, "v3": "", "hw": hw, "hwflag": flagmap.get(fl, fl or ("" if not hw else ("same" if blind(hw) == blind(lem) else "differs"))),
                "consensus": "", "name": "", "m1": r.get("m1_admissible_share", ""), "works": int(float(r["n_works"] or 0)),
                "surf": [x.strip() for x in r["surfaces"].split(";")[:4] if x.strip()],
                "ctx": [r[c] for c in ("context_1", "context_2", "context_3") if r.get(c)] if with_ctx else [],
                "att": "", "kuhn": "", "lsjhw": r.get("lsj_headword", ""),
            })
        out.sort(key=lambda x: -x["ll"])
        return out

    dest = ROOT.parent / "docs" / "terms" / tlg
    dest.mkdir(parents=True, exist_ok=True)
    recs, dropped = build(True), False
    payload = json.dumps({"generated": time.strftime("%Y-%m-%d"), "author": name, "tlg": tlg, "n": len(recs), "records": recs}, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 8 * 1024 * 1024:
        recs, dropped = build(False), True
        payload = json.dumps({"generated": time.strftime("%Y-%m-%d"), "author": name, "tlg": tlg, "n": len(recs), "records": recs}, ensure_ascii=False)
    (dest / "terms.json").write_text(payload, encoding="utf-8")
    esc = name.replace("&", "&amp;").replace("<", "&lt;")
    intro = (f"Every lemma that {esc} ({tlg}; {summ['author_tokens']:,} odyCy tokens, {summ['works']} works) over-uses against the rest of Greek "
             f"(<span id=n></span> key lemmas; LL &ge; {summ['min_log_likelihood']}, domain frequency &ge; {summ['min_domain_frequency']}; reference {summ['reference_tokens']:,} tokens; odyCy 0.7.0 lemmas, First1KGreek text). "
             "Type a word, a stem, or a filter: <code>tier:absent</code>, <code>punch</code>, <code>flag:differs</code>, <code>pos:NOUN</code>. "
             "Nothing here was written by a model: keyness, LSJ tiers and Dilemma headwords are measurements from the Galen Density Project T3 term map (v0). Report, never patch.")
    page = HTML.replace("Galen Term Explorer", f"{esc} Term Explorer")
    ia, ib = page.index("<p class=s>Every lemma"), page.index("</p>", page.index("<p class=s>Every lemma")) + 4
    page = page[:ia] + f"<p class=s>{intro}</p>" + page[ib:]
    page = page.replace(" · ${r.quad}", "").replace("placeholder=\"search: θηριακ   or   tier:absent punch   or   flag:differs pos:NOUN\"", "placeholder=\"search a stem, or tier:absent punch\"")
    foot = f"<p class=s>Source: outputs/t3/{tlg}/term_map.csv, {summ['date']}." + (" Attested-contexts column dropped: terms.json would exceed 8 MB." if dropped else "") + " <a href=\"../index.html\">All authors</a></p>"
    page = page.replace("</script></body></html>", "</script>" + foot + "</body></html>")
    (dest / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps({"author": name, "tlg": tlg, "records": len(recs), "punch": sum(r["punch"] for r in recs), "terms_json_bytes": len(payload.encode("utf-8")), "contexts_dropped": dropped}, ensure_ascii=False))


if __name__ == "__main__":
    main()
