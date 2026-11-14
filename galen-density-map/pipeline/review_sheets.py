"""Review worksheets for Galen First Drafts: a seeded sample of units per work, printable sheets for a scholar's read,
and a scorer that turns the filled sheets back into per-work numbers. No model calls; reads only files on disk.

    python -X utf8 pipeline/review_sheets.py build            # writes outputs/review_sheets/
    python -X utf8 pipeline/review_sheets.py score [CSV ...]  # default: outputs/review_sheets/filled/*.csv

Sample per work (seed SEED, per-work stream random.Random(f"{SEED}:{slug}")), N_PER_WORK units in three strata:

- D (disagreement): the K_DISAGREE units with the most target terms on which renderings A and B disagree (check (b),
  term level: term_table.csv `agree` == "n"), ties broken by the higher disagreement rate, then by a seeded random
  key. Units with no disagreeing term are never in D. D is taken whole (a census of its stratum).
- F (check failure): units not in D that fail at least one of checks (a), (b), (c) (per-check verdict "fail" in
  checks.json; (c) counts only where the judge passed its gate). N_FAIL drawn at random without replacement.
- R (control): every other unit. The rest of the N_PER_WORK drawn at random without replacement; if R is too small,
  F takes the remainder. A work with N_PER_WORK units or fewer is taken whole.

Each stratum keeps its population size N_s and sample size n_s, so the scorer can weight a stratum by N_s / N and give
a whole-work estimate (stratified random sampling; D and small works are censuses).

Sheet order is round-robin over the strata (stratum order shuffled each round, units shuffled within a stratum), so
any first k sheets mix the strata and a reviewer who stops early still leaves a usable sample. Which rendering is
shown as "1" and which as "2" is a seeded coin per unit (key: key/sample_key.csv); the sheet shows neither model
names nor check results, so the reader is not told which units the machine flagged.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent
FD_ROOT = GDM / "outputs" / "firstdrafts"
OUT_ROOT = GDM / "outputs" / "review_sheets"

SEED = "20261113"
N_PER_WORK = 10
K_DISAGREE = 4
N_FAIL = 3
RENDERINGS = {"A": "fable-5-1", "B": "opus-5-5"}   # page labels and model files, as page.py
STRATA = ("D", "F", "R")
STRATUM_NAME = {"D": "A/B term disagreement (top units)", "F": "fails a machine check", "R": "random control"}

REVIEW_FIELDS = ("reviewer", "better", "term_wrong", "term_note", "sense_wrong", "sense_note", "comment")
SHEET_COLS = ("work", "sheet_no", "unit_id", "locus") + REVIEW_FIELDS + ("greek", "rendering_1", "rendering_2", "terms")
KEY_COLS = ("work", "sheet_no", "unit_id", "stratum", "stratum_N", "stratum_n", "work_N", "shown_1", "shown_2",
            "n_targets", "n_disagree", "disagree_rate", "a", "b", "c", "unit_verdict", "seed")


sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "firstdrafts"))


def galen_works() -> dict:
    from common import WORKS  # noqa: E402

    return WORKS


def clean_headword(h: str) -> str:
    from page import clean_headword as ch  # noqa: E402  (the published pages' display rule)

    return ch(h)


# ---------------------------------------------------------------------------------------------------- reading a work

def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def first_sense_gloss(entry_txt: str) -> str:
    """LSJ first-sense gloss from the entry text alone; the same rule as lsj_index.first_sense_gloss with no <sense>
    list (used only where term_table.csv predates the lsj_first_sense_gloss column: Adversus Lycum, cycle 1)."""
    text = re.sub(r"\s+", " ", entry_txt or "")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"=\s*[^,;]*[,;]", " ", text)
    text = re.sub(r"^\s*[A-Z]?\s*[IVX]*\.?\s*\d*\.?\s*", "", text)
    for m in re.finditer(r"(?<![A-Za-z])([a-z][a-z\-']+(?: [a-zA-Z\-']+)*)", text):
        seg = text[m.start(1):]
        seg = re.split(r"[,;:]| [A-Z][a-z]{1,5}\. ?| v\. | cf\. |\d", seg)[0].strip(" .")
        if seg:
            return seg
    return ""


def clean(s: str) -> str:
    """Drops the empty Kühn marker '[None]' (a page number the TEI lacks; in-hipp-salubri), as page.py does."""
    return (s or "").replace("[None] ", "").replace("[None]", "")


def load_work(slug: str, root: Path = FD_ROOT) -> dict:
    d = root / slug
    units = read_jsonl(d / "units.jsonl")
    checks = json.loads((d / "checks.json").read_text(encoding="utf-8"))
    terms: dict[str, list[dict]] = defaultdict(list)
    with (d / "term_table.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            terms[r["unit_id"]].append(r)
    rend = {}
    for lab, model in RENDERINGS.items():
        rend[lab] = {r["unit_id"]: clean(((r.get("response") or {}).get("translation")) or "")
                     for r in read_jsonl(d / f"renderings_{model}.jsonl")}
    return {"slug": slug, "units": units, "checks": checks.get("units", {}), "terms": terms, "rend": rend}


def unit_stats(work: dict) -> list[dict]:
    out = []
    for u in work["units"]:
        uid = u["unit_id"]
        rows = work["terms"].get(uid, [])
        both = [r for r in rows if r.get("agree") in ("y", "n")]
        nd = sum(1 for r in both if r["agree"] == "n")
        ck = work["checks"].get(uid, {})
        v = {k: (ck.get(k) or {}).get("verdict", "") for k in ("a", "b", "c")}
        out.append({"unit_id": uid, "n_targets": len(rows), "n_both": len(both), "n_disagree": nd,
                    "disagree_rate": round(nd / len(both), 3) if both else 0.0,
                    **v, "any_fail": any(v[k] == "fail" for k in ("a", "b", "c")),
                    "unit_verdict": ck.get("verdict", "")})
    return out


# ---------------------------------------------------------------------------------------------------------- sampling

def strata(stats: list[dict], slug: str, seed: str = SEED, k_d: int = K_DISAGREE) -> tuple[random.Random, dict]:
    """The three stratum populations (unit ids, in work order) and the seeded stream left after the D tie-break."""
    rng = random.Random(f"{seed}:{slug}")
    by_id = {s["unit_id"]: s for s in stats}
    ids = [s["unit_id"] for s in stats]
    tie = {uid: rng.random() for uid in ids}
    ranked = sorted((u for u in ids if by_id[u]["n_disagree"] > 0),
                    key=lambda u: (-by_id[u]["n_disagree"], -by_id[u]["disagree_rate"], tie[u]))
    d = ranked[:k_d]
    f = [u for u in ids if u not in d and by_id[u]["any_fail"]]
    r = [u for u in ids if u not in d and u not in f]
    return rng, {"D": d, "F": f, "R": r}


def sample_work(stats: list[dict], slug: str, seed: str = SEED, n: int = N_PER_WORK, k_d: int = K_DISAGREE,
                n_f: int = N_FAIL) -> list[dict]:
    """The documented rule (module docstring). Returns the sampled units in sheet order, each with its stratum,
    stratum population N_s, sample size n_s and display swap. Deterministic in (stats, slug, seed)."""
    by_id = {s["unit_id"]: s for s in stats}
    ids = [s["unit_id"] for s in stats]
    rng, P = strata(stats, slug, seed, k_d)
    d_pop, f_pop, r_pop = P["D"], P["F"], P["R"]
    if len(ids) <= n:
        take = {"D": list(d_pop), "F": list(f_pop), "R": list(r_pop)}
    else:
        room = n - len(d_pop)
        fn = min(n_f, len(f_pop), room)
        rn = min(room - fn, len(r_pop))
        fn = min(len(f_pop), room - rn)   # R too small: F takes the remainder
        take = {"D": list(d_pop), "F": rng.sample(f_pop, fn), "R": rng.sample(r_pop, rn)}
    pop = {"D": len(d_pop), "F": len(f_pop), "R": len(r_pop)}
    queues = {s: rng.sample(take[s], len(take[s])) for s in STRATA}
    order = []
    while any(queues.values()):
        for s in rng.sample(STRATA, len(STRATA)):
            if queues[s]:
                order.append((s, queues[s].pop(0)))
    out = []
    for i, (s, uid) in enumerate(order, 1):
        swap = rng.random() < 0.5
        out.append({**by_id[uid], "sheet_no": i, "stratum": s, "stratum_N": pop[s], "stratum_n": len(take[s]),
                    "work_N": len(ids), "shown_1": "B" if swap else "A", "shown_2": "A" if swap else "B"})
    return out


# ------------------------------------------------------------------------------------------------------------ sheets

def term_rows(rows: list[dict], shown_1: str, shown_2: str) -> list[dict]:
    out = []
    for r in rows:
        fs = r.get("lsj_first_sense_gloss") or (first_sense_gloss(r.get("lsj_entry_text", "")) if r.get("lsj_entry_id") else "")
        out.append({"surface": r["surface"].strip(".,;:·"), "lemma": r.get("dilemma_lemma") or r.get("odycy_lemma", ""),
                    "headword": clean_headword(r.get("lsj_headword", "")), "senses": r.get("lsj_sense_count", ""),
                    "first_sense": fs if r.get("lsj_entry_id") else "(no LSJ entry)",
                    "r1": r.get(f"rendering_{shown_1}", ""), "r2": r.get(f"rendering_{shown_2}", ""),
                    "differ": r.get("agree") == "n"})
    return out


def terms_text(trs: list[dict]) -> str:
    return " | ".join(f"{t['surface']} ({t['headword'] or t['lemma']}; LSJ: {t['first_sense']}): 1 {t['r1'] or '-'}; 2 {t['r2'] or '-'}"
                      f"{' [differ]' if t['differ'] else ''}" for t in trs)


def sheet_units(work: dict, sample: list[dict]) -> list[dict]:
    units = {u["unit_id"]: u for u in work["units"]}
    out = []
    for s in sample:
        u = units[s["unit_id"]]
        out.append({"sheet_no": s["sheet_no"], "unit_id": s["unit_id"], "locus": u.get("locus", ""),
                    "greek": clean(u.get("greek", "")),
                    "rendering_1": work["rend"][s["shown_1"]].get(s["unit_id"], ""),
                    "rendering_2": work["rend"][s["shown_2"]].get(s["unit_id"], ""),
                    "terms": term_rows(work["terms"].get(s["unit_id"], []), s["shown_1"], s["shown_2"])})
    return out


def e(s) -> str:
    return html.escape(str(s or ""), quote=True)


MARK_RE = re.compile(r"\[(\d+)\]")


def marks(s: str) -> str:
    return MARK_RE.sub(lambda m: f'<span class=pg title="Kühn page">[{m.group(1)}]</span>', e(s))


CSS = """
:root{--ink:#1d1b18;--muted:#5d5850;--rule:#c9c2b6;--tint:#f4f1ea;--diff:#8a3b12;--bg:#fffdf9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ink:#ece7dd;--muted:#b3ab9e;--rule:#575148;--tint:#2a2723;--diff:#f0a070;--bg:#1b1916}}
:root[data-theme="dark"]{--ink:#ece7dd;--muted:#b3ab9e;--rule:#575148;--tint:#2a2723;--diff:#f0a070;--bg:#1b1916}
*{box-sizing:border-box}
body{margin:0 auto;max-width:60rem;padding:1.5rem 16px 4rem;background:var(--bg);color:var(--ink);
 font:15px/1.5 "Gentium Plus","Gentium Book Plus","Palatino Linotype","Book Antiqua",Georgia,"Times New Roman",serif}
h1{font-size:1.45rem;margin:.2rem 0 .3rem}h2{font-size:1.1rem;margin:0 0 .4rem}
.small{font-size:.85rem;color:var(--muted)}
.cover{border-bottom:2px solid var(--ink);padding-bottom:1rem;margin-bottom:1.5rem}
.cover ol{padding-left:1.2rem}.cover li{margin:.2rem 0}
.line{display:inline-block;min-width:14rem;border-bottom:1px solid var(--ink)}
.unit{border-top:2px solid var(--ink);padding-top:.8rem;margin-top:2rem}
.uh{display:flex;flex-wrap:wrap;gap:.3rem 1.2rem;align-items:baseline}
.uh .no{font-weight:700;font-size:1.1rem}
.grc{font-size:1.02rem;margin:.6rem 0;padding:.6rem .8rem;background:var(--tint);border-radius:3px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.cols h3{font-size:.95rem;margin:.2rem 0;letter-spacing:.03em}
.cols p{margin:.2rem 0;text-align:left}
.pg{color:var(--muted);font-size:.8em}
table{border-collapse:collapse;width:100%;margin:.8rem 0;font-size:.9rem}
th,td{border-bottom:1px solid var(--rule);padding:.25rem .4rem;text-align:left;vertical-align:top}
th{font-weight:600}
tr.differ td.r{color:var(--diff);font-weight:600}
.form{border:1px solid var(--ink);padding:.6rem .8rem;margin-top:.6rem;break-inside:avoid}
.form .q{margin:.35rem 0}.box{display:inline-block;margin-right:1.1rem;white-space:nowrap}
.box::before{content:"";display:inline-block;width:.85em;height:.85em;border:1px solid var(--ink);margin-right:.3em;vertical-align:-.1em}
.write{border-bottom:1px solid var(--rule);height:1.6em}
.index li{margin:.3rem 0}
a{color:inherit}
@media (max-width:640px){.cols{grid-template-columns:1fr}}
@media print{body{max-width:none;padding:0;font-size:11pt;background:#fff;color:#000}
 .unit{break-before:page;margin-top:0;border-top:none}.grc{background:none;border:1px solid #999}
 .noprint{display:none}a{text-decoration:none}}
@page{margin:16mm 14mm}
"""


def html_page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">"
            f"<title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>")


COVER_STEPS = """<ol>
<li>Each sheet is one passage: the Greek (Kühn's text, page numbers in brackets), two machine renderings labelled 1 and 2,
and a table of the words the pipeline singled out, with the first sense of their LSJ entry.</li>
<li>Read the sheets in order and stop when your time is up. A partly filled set is still useful; leave a passage blank if you did not read it.</li>
<li>For each passage you read, tick one box on each line and write a few words where something is wrong. <i>Term wrong</i>: a word is rendered
with a meaning it cannot have here. <i>Sense wrong</i>: the passage as a whole says something the Greek does not (construction, negation, who says what, the argument).</li>
<li>Return the paper sheets (a photo is fine) or the CSV file with the same columns. Full instructions: <code>reviewer_instructions.md</code>.</li>
</ol>"""


def work_html(slug: str, meta: dict, sheets: list[dict]) -> str:
    t = f"{meta['title_lat']} — review sheets"
    parts = [f"""<div class=cover><div class=small>Galen First Drafts · review sheets · seed {e(SEED)}</div>
<h1>Galen, <i>{e(meta['title_lat'])}</i></h1><div>{e(meta['title_eng'])} · Kühn {e(meta.get('kuhn_vol', ''))} {e(meta.get('kuhn_pages', ''))}</div>
<p class=small>{len(sheets)} passages chosen from the work by a fixed rule. The renderings are machine output that no scholar has checked.</p>
{COVER_STEPS}
<p>Reviewer <span class=line>&nbsp;</span> &nbsp; Date <span class=line style="min-width:8rem">&nbsp;</span></p>
<p class="noprint small"><a href="index.html">All works</a> · <a href="{e(slug)}.csv">CSV for this work</a></p></div>"""]
    for s in sheets:
        rows = "".join(f"<tr class=\"{'differ' if t['differ'] else ''}\"><td lang=grc>{e(t['surface'])}</td><td lang=grc>{e(t['headword'] or t['lemma'])}"
                       f"{(' <span class=small>(' + e(t['senses']) + (' sense' if t['senses'] == '1' else ' senses') + ')</span>') if t['senses'] else ''}"
                       f"{('<br><span class=small>lemma ' + e(t['lemma']) + '</span>') if t['lemma'] and t['headword'] and t['lemma'] != t['headword'] else ''}</td><td>{e(t['first_sense'])}</td>"
                       f"<td class=r>{e(t['r1']) or '—'}</td><td class=r>{e(t['r2']) or '—'}</td></tr>" for t in s["terms"])
        table = (f"<table><tr><th>Greek</th><th>LSJ headword</th><th>LSJ first sense</th><th>in 1</th><th>in 2</th></tr>{rows}</table>"
                 f"<div class=small>Coloured rows: the pipeline counted the two renderings of the word as different. The first sense is where the LSJ entry begins, not necessarily the sense meant here; the headword is the entry the pipeline matched, which can itself be wrong.</div>"
                 if s["terms"] else "<p class=small>No words singled out in this passage.</p>")
        r1 = marks(s["rendering_1"]) or "<em class=small>no rendering</em>"
        r2 = marks(s["rendering_2"]) or "<em class=small>no rendering</em>"
        parts.append(f"""<section class=unit id="s{s['sheet_no']}">
<div class=uh><span class=no>Sheet {s['sheet_no']}</span><span>{e(s['locus'])}</span><span class=small>unit {e(s['unit_id'])}</span></div>
<div class=grc lang=grc>{marks(s['greek'])}</div>
<div class=cols><div><h3>RENDERING 1</h3><p>{r1}</p></div><div><h3>RENDERING 2</h3><p>{r2}</p></div></div>
{table}
<div class=form>
<div class=q><b>Which rendering is better?</b> &nbsp;<span class=box>1</span><span class=box>2</span><span class=box>neither</span></div>
<div class=q><b>A term wrong?</b> &nbsp;<span class=box>none</span><span class=box>in 1</span><span class=box>in 2</span><span class=box>in both</span> &nbsp;which word(s):</div><div class=write></div>
<div class=q><b>Sense wrong?</b> &nbsp;<span class=box>none</span><span class=box>in 1</span><span class=box>in 2</span><span class=box>in both</span> &nbsp;where:</div><div class=write></div>
<div class=q><b>Comment</b></div><div class=write></div><div class=write></div>
</div></section>""")
    return html_page(t, "".join(parts))


def index_html(works: list[tuple[str, dict, int]]) -> str:
    li = "".join(f"<li><a href=\"{e(s)}.html\"><i>{e(m['title_lat'])}</i></a> — {e(m['title_eng'])} · {n} passages · "
                 f"<a href=\"{e(s)}.csv\">CSV</a></li>" for s, m, n in works)
    return html_page("First Drafts review sheets", f"""<h1>Galen First Drafts: review sheets</h1>
<p>One set of sheets per work, about ten passages each, chosen by a fixed seeded rule. Each sheet shows the Greek, two machine renderings
and the words the pipeline singled out with their LSJ first sense, and asks four short questions. Print a work's page (one passage per sheet)
or fill in its CSV. Instructions: <code>reviewer_instructions.md</code>.</p>
<ul class=index>{li}</ul><p class=small>Built from <code>outputs/firstdrafts/</code> by <code>pipeline/review_sheets.py</code>; seed {e(SEED)}.</p>""")


def write_csv(p: Path, cols, rows) -> None:
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cols), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


INSTRUCTIONS = """# Reviewer instructions: Galen First Drafts review sheets

**What you are looking at.** Thirteen works of Galen were translated by two language models, passage by passage,
with no human correction. For each work, about ten passages were chosen by a fixed rule (some where the two
renderings differ most, some that automated checks flagged, some at random; the sheet does not say which). Each
sheet shows one passage: the Greek of Kühn's edition with his page numbers in brackets, two renderings labelled
**1** and **2**, and a table of the words the pipeline singled out (rare or thinly covered in LSJ), each with the LSJ
headword it was matched to, the first sense of that entry, and how each rendering translated it. The labels 1 and 2
are shuffled from passage to passage; they are not the A and B of the published pages.

**What we ask.** Read the Greek and the two renderings, then answer four questions. Your judgement is the measure;
there is no answer key.

1. **Which rendering is better?** `1`, `2` or `neither` (no real difference, or equally good or bad).
2. **A term wrong?** `none`, `1`, `2` or `both`: a word is rendered with a meaning it cannot have in this passage.
   Write the word(s) in the note (the Greek, the English, or both).
3. **Sense wrong?** `none`, `1`, `2` or `both`: the rendering says something the Greek does not, beyond single words
   (construction, negation, who is speaking or criticised, the step of the argument). Say where in the note.
4. **Comment** (optional): anything else, such as a better rendering, a textual problem in Kühn, or a word the table
   should have included.

**How long.** About three to five minutes a passage (an estimate; nobody has timed it yet). In 30 minutes that is
roughly six to ten passages. Work through the sheets **in order** and stop when your time is up: the order is
arranged so that the first few passages already mix the three kinds. Leave a passage blank if you did not read it;
a blank is not counted. Answer only the questions you are sure of; a partial answer is still used.

**Things to keep in mind.**
- The LSJ first sense is where the entry begins, not the sense Galen needs; a rendering that departs from it may be
  right. The matched headword can itself be wrong (the pipeline's lemmatizer chose it).
- Words in square brackets in a rendering were supplied by the model; words in parentheses repeat the Greek.
- Only Kühn's text was used; if a rendering goes wrong because the text is corrupt, say so in the comment rather
  than marking the rendering wrong.
- Please do not look up the published page for a passage before answering; the sheets are meant to be read cold.

**Returning the sheets.** Either print the work's HTML page (one passage per sheet), tick and write by hand, and
send a scan or photo; or open the work's CSV in a spreadsheet and fill the columns `reviewer`, `better`,
`term_wrong`, `term_note`, `sense_wrong`, `sense_note`, `comment` (values as above; leave the other columns as
they are). Your name or initials in `reviewer` is enough; say if you would rather not be named in anything that
reports the results.

**How the answers are used.** They are counted per work: how often each rendering was preferred, and in how many
passages a term or the sense was marked wrong, separately for flagged and unflagged passages. That tells us whether
the automated flags point where a reader finds problems, and gives a first, rough error rate per work. No answer is
published as a correction without the reviewer's agreement.
"""


def readme_md(summary: dict) -> str:
    rows = "\n".join(f"| {w} | {x['units']} | {x['units_with_a_disagreement']} | {x['units_with_a_failing_check']} | "
                     + " | ".join(f"{x['strata'][st]['n']} / {x['strata'][st]['N']}" for st in STRATA) + f" | {x['sampled']} |"
                     for w, x in summary.items())
    rule = __doc__.split("Sample per work", 1)[1].split("Sheet order", 1)[0].strip()
    return f"""# Review sheets for Galen First Drafts

Built by `pipeline/review_sheets.py build` from `outputs/firstdrafts/<slug>/` (units, renderings, `term_table.csv`,
`checks.json`); no model calls. Tests: `tests/test_review_sheets.py`.

## Files
- `index.html`: the list of works. `<slug>.html`: printable sheets, a cover and one passage per printed page.
- `<slug>.csv`: the same sheets as rows to fill (UTF-8 with BOM, so a spreadsheet shows the Greek); reviewer columns
  `reviewer, better, term_wrong, term_note, sense_wrong, sense_note, comment`; the text columns are for reading only.
- `reviewer_instructions.md`: one page for the reader, neutral wording.
- `key/sample_key.csv`: per sampled unit, its stratum, the stratum's size, which model is shown as 1 and as 2, and
  the machine check results. Not for the reader (the sheets hide strata, check results and model names).
  `key/sampling.json`: parameters and per-work counts.
- `filled/` (put returned CSVs here) and `scores/` (written by the scorer).

## Sampling rule
Seed `{SEED}`; per work {N_PER_WORK} units, {K_DISAGREE} in D and {N_FAIL} in F where possible.

{rule}

| work | units | units with an A/B term disagreement | units failing a check | D n / N | F n / N | R n / N | sampled |
|---|---|---|---|---|---|---|---|
{rows}

## Scoring
Put each filled CSV in `filled/` (or pass the paths) and run

    python -X utf8 pipeline/review_sheets.py score [CSV ...]

It maps 1 and 2 back to the models through the key, skips unread rows, reports unreadable values instead of guessing,
and writes `scores/scores.json` and `scores/summary.md`: per work the preference counts with a sign test, the share
of passages with a wrong term and with a wrong sense in each model's rendering (overall and by stratum, Wilson 95%
intervals), any error in flagged (D+F) vs control (R) passages, a stratum-weighted estimate for the whole work when
every stratum was read, and agreement between reviewers on passages read by more than one.

{SUPPORTS}"""


def build(fd_root: Path = FD_ROOT, out: Path = OUT_ROOT, seed: str = SEED, works: dict | None = None) -> dict:
    works = works if works is not None else galen_works()
    out.mkdir(parents=True, exist_ok=True)
    key_rows, done, summary = [], [], {}
    for slug, meta in works.items():
        d = fd_root / slug
        if not (d / "checks.json").exists() or not all((d / f"renderings_{m}.jsonl").exists() for m in RENDERINGS.values()):
            continue
        work = load_work(slug, fd_root)
        stats = unit_stats(work)
        sample = sample_work(stats, slug, seed)
        sheets = sheet_units(work, sample)
        (out / f"{slug}.html").write_text(work_html(slug, meta, sheets), encoding="utf-8")
        write_csv(out / f"{slug}.csv", SHEET_COLS,
                  [{"work": slug, **{k: s[k] for k in ("sheet_no", "unit_id", "locus", "greek", "rendering_1", "rendering_2")},
                    "terms": terms_text(s["terms"])} for s in sheets])
        for s in sample:
            key_rows.append({"work": slug, "seed": seed, **{k: s[k] for k in KEY_COLS if k in s},
                             "shown_1": RENDERINGS[s["shown_1"]], "shown_2": RENDERINGS[s["shown_2"]]})
        _, P = strata(stats, slug, seed)
        summary[slug] = {"units": len(stats), "sampled": len(sample),
                         "strata": {st: {"N": len(P[st]), "n": sum(1 for s in sample if s["stratum"] == st)} for st in STRATA},
                         "units_with_a_failing_check": sum(1 for x in stats if x["any_fail"]),
                         "units_with_a_disagreement": sum(1 for x in stats if x["n_disagree"] > 0)}
        done.append((slug, meta, len(sheets)))
    (out / "key").mkdir(exist_ok=True)
    write_csv(out / "key" / "sample_key.csv", KEY_COLS, key_rows)
    (out / "key" / "sampling.json").write_text(json.dumps(
        {"seed": seed, "n_per_work": N_PER_WORK, "k_disagree": K_DISAGREE, "n_fail": N_FAIL,
         "renderings": RENDERINGS, "rule": __doc__.split("Sample per work", 1)[1].split("Each stratum", 1)[0].strip(),
         "works": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "index.html").write_text(index_html(done), encoding="utf-8")
    (out / "reviewer_instructions.md").write_text(INSTRUCTIONS, encoding="utf-8")
    (out / "README.md").write_text(readme_md(summary), encoding="utf-8")
    (out / "filled").mkdir(exist_ok=True)
    (out / "filled" / ".gitkeep").touch()
    return summary


# ----------------------------------------------------------------------------------------------------------- scoring

BETTER = {"1": "1", "2": "2", "neither": "neither", "none": "neither", "same": "neither", "equal": "neither", "0": "neither"}
WRONG = {"none": "none", "no": "none", "n": "none", "0": "none", "-": "none", "1": "1", "in 1": "1", "2": "2", "in 2": "2",
         "both": "both", "in both": "both", "1+2": "both", "1,2": "both", "1 and 2": "both", "12": "both", "1/2": "both"}


def norm(v: str, table: dict) -> str | None:
    """'' -> '' (not answered); a known value -> canonical; anything else -> None (invalid, reported)."""
    v = (v or "").strip().lower()
    if not v:
        return ""
    return table.get(v)


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def binom_two_sided(k: int, n: int) -> float | None:
    """Exact two-sided sign test p (p = 0.5) for k of n decisive preferences."""
    if n == 0:
        return None
    pk = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return round(min(1.0, sum(p for p in pk if p <= pk[k] + 1e-12)), 4)


def read_key(p: Path) -> dict:
    with p.open(encoding="utf-8-sig") as fh:
        return {(r["work"], r["unit_id"]): r for r in csv.DictReader(fh)}


def read_filled(paths: list[Path], key: dict) -> tuple[list[dict], list[str]]:
    """Every answered row of the filled sheets, with labels mapped back to models. Returns (readings, problems)."""
    readings, problems = [], []
    for p in paths:
        with p.open(encoding="utf-8-sig") as fh:
            for i, r in enumerate(csv.DictReader(fh), 2):
                k = (r.get("work", "").strip(), r.get("unit_id", "").strip())
                if k not in key:
                    problems.append(f"{p.name}:{i}: {k} not in the sample key")
                    continue
                vals = {"better": norm(r.get("better"), BETTER), "term_wrong": norm(r.get("term_wrong"), WRONG),
                        "sense_wrong": norm(r.get("sense_wrong"), WRONG)}
                bad = [f"{f}={r.get(f)!r}" for f, v in vals.items() if v is None]
                if bad:
                    problems.append(f"{p.name}:{i}: {k[1]}: unreadable {', '.join(bad)} (row skipped)")
                    continue
                if not any(vals.values()):
                    continue   # not read
                kr = key[k]
                lab = {"1": kr["shown_1"], "2": kr["shown_2"]}
                models = lambda v: [] if v in ("", "none") else ([lab["1"], lab["2"]] if v == "both" else [lab[v]])  # noqa: E731
                readings.append({"work": k[0], "unit_id": k[1], "reviewer": (r.get("reviewer") or p.stem).strip(),
                                 "stratum": kr["stratum"], "stratum_N": int(kr["stratum_N"]), "work_N": int(kr["work_N"]),
                                 "better": vals["better"], "better_model": lab.get(vals["better"], vals["better"]),
                                 "term_wrong": vals["term_wrong"], "term_wrong_models": models(vals["term_wrong"]),
                                 "sense_wrong": vals["sense_wrong"], "sense_wrong_models": models(vals["sense_wrong"]),
                                 "term_note": r.get("term_note", ""), "sense_note": r.get("sense_note", ""), "comment": r.get("comment", "")})
    return readings, problems


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "wilson95": wilson(k, n)}


def score_work(rs: list[dict], models=tuple(RENDERINGS.values())) -> dict:
    """Per-work numbers from the readings of one work. Each unit counts once: when several reviewers read a unit,
    its value is the share of them that marked it (for rates) and every reading counts for preferences."""
    units = defaultdict(list)
    for r in rs:
        units[r["unit_id"]].append(r)
    out = {"n_readings": len(rs), "n_units": len(units), "reviewers": sorted({r["reviewer"] for r in rs}),
           "by_stratum_units": dict(Counter(v[0]["stratum"] for v in units.values()))}
    pref = Counter(r["better_model"] for r in rs if r["better"])
    dec = sum(pref[m] for m in models)
    out["preference"] = {**{m: pref[m] for m in models}, "neither": pref["neither"], "decisive": dec,
                         "sign_test_p": binom_two_sided(pref[models[0]], dec) if dec else None}

    def unit_value(v: list[dict], field: str, model: str | None) -> float | None:
        ans = [r for r in v if r[field]]
        if not ans:
            return None
        hit = [(r[field] != "none") if model is None else (model in r[field + "_models"]) for r in ans]
        return sum(hit) / len(hit)

    def summarise(field: str, model: str | None) -> dict:
        vals = {u: unit_value(v, field, model) for u, v in units.items()}
        vals = {u: x for u, x in vals.items() if x is not None}
        k = sum(1 for x in vals.values() if x >= 0.5)
        res = {"units": rate(k, len(vals))}
        strata = defaultdict(list)
        for u, x in vals.items():
            strata[units[u][0]["stratum"]].append(x)
        res["by_stratum"] = {s: rate(sum(1 for x in xs if x >= 0.5), len(xs)) for s, xs in sorted(strata.items())}
        res["work_estimate_pct"] = weighted_estimate(units, vals)
        return res

    out["term_wrong"] = {m: summarise("term_wrong", m) for m in models}
    out["sense_wrong"] = {m: summarise("sense_wrong", m) for m in models}
    out["term_wrong_any"] = summarise("term_wrong", None)
    out["sense_wrong_any"] = summarise("sense_wrong", None)
    # any error in either rendering: a unit counts when both questions were answered
    both = {}
    for u, v in units.items():
        ans = [r for r in v if r["term_wrong"] and r["sense_wrong"]]
        if ans:
            both[u] = sum(1 for r in ans if r["term_wrong"] != "none" or r["sense_wrong"] != "none") / len(ans)
    flagged = [x for u, x in both.items() if units[u][0]["stratum"] in ("D", "F")]
    control = [x for u, x in both.items() if units[u][0]["stratum"] == "R"]
    out["any_error"] = {"units": rate(sum(1 for x in both.values() if x >= 0.5), len(both)),
                        "flagged_D_F": rate(sum(1 for x in flagged if x >= 0.5), len(flagged)),
                        "control_R": rate(sum(1 for x in control if x >= 0.5), len(control)),
                        "work_estimate_pct": weighted_estimate(units, both)}
    out["reviewer_agreement"] = agreement(units)
    return out


def weighted_estimate(units: dict, vals: dict) -> float | None:
    """Stratified estimate of the share of the work's units with the property: sum over strata of N_s/N times the
    stratum's sample share. None unless every stratum with units in the work was read at least once."""
    if not vals:
        return None
    any_u = next(iter(units.values()))[0]
    n_work = any_u["work_N"]
    pops, xs = {}, defaultdict(list)
    for u, v in units.items():
        pops[v[0]["stratum"]] = v[0]["stratum_N"]
    for u, x in vals.items():
        xs[units[u][0]["stratum"]].append(1.0 if x >= 0.5 else 0.0)
    if any(s not in xs for s in pops) or sum(pops.values()) != n_work:
        return None
    return round(100 * sum(pops[s] / n_work * (sum(xs[s]) / len(xs[s])) for s in pops), 1)


def agreement(units: dict) -> dict:
    """Pairwise agreement between reviewers on units read by two or more (raw share, no chance correction)."""
    pairs = Counter()
    for v in units.values():
        for f in ("better", "term_wrong", "sense_wrong"):
            ans = [r[f] if f == "better" else (r[f] != "none") for r in v if r[f]]
            for i in range(len(ans)):
                for j in range(i + 1, len(ans)):
                    pairs[(f, "n")] += 1
                    pairs[(f, "same")] += ans[i] == ans[j]
    return {f: rate(pairs[(f, "same")], pairs[(f, "n")]) for f in ("better", "term_wrong", "sense_wrong") if pairs[(f, "n")]}


SUPPORTS = """## What these numbers would support claiming

The numbers describe what the named reviewers found on the sampled passages of each work, with the sampling rule in
`key/sampling.json`. With about ten passages per work and one reader, every percentage has a confidence interval
tens of points wide (the Wilson intervals are printed); read them as a first measurement, not a quality rating.

- **Preference (1 vs 2, mapped back to the two models).** "On n passages of work W, reviewer R preferred model X's
  rendering k times, model Y's j times, and saw no difference m times." A sign test p is printed for information.
  It does not support "model X translates Galen better" beyond those passages and that reader.
- **Term wrong / sense wrong per rendering.** "Reviewer R marked at least one wrong term in k of n passages read." The
  control stratum (R) is a simple random sample of the work's unflagged units, so its rate (with its interval) is an
  estimate for those units. The work estimate weights the strata by their size (N_s / N); it is printed only when every
  stratum was read, and it inherits the reviewer's judgement as its definition of "wrong".
- **Flagged vs control (any error).** The comparison of D+F (passages the checks or the A/B disagreement singled out)
  with R is the one test of the machine apparatus: if flagged passages carry errors more often than controls, the flags
  point where a reader should look. With ten passages per work this is only suggestive; pooled over works it becomes a
  measurement. If controls show errors as often as flagged passages, a passage without a flag cannot be called checked.
- **What they never support.** That an unflagged passage is correct; that the whole work is usable without reading it;
  any claim about syntax, argument or attribution beyond what the reviewer wrote; and any comparison between works read
  by different reviewers (differences in reviewers and in works cannot be told apart).
"""


def score(paths: list[Path], key_path: Path, out: Path) -> dict:
    key = read_key(key_path)
    readings, problems = read_filled(paths, key)
    by_work = defaultdict(list)
    for r in readings:
        by_work[r["work"]].append(r)
    res = {"inputs": [str(p) for p in paths], "problems": problems, "works": {w: score_work(rs) for w, rs in sorted(by_work.items())}}
    pooled = score_work_pooled(readings)
    res["pooled"] = pooled
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "summary.md").write_text(summary_md(res), encoding="utf-8")
    return res


def score_work_pooled(readings: list[dict]) -> dict:
    """Flagged vs control pooled over works (unweighted; each unit once)."""
    units = defaultdict(list)
    for r in readings:
        units[(r["work"], r["unit_id"])].append(r)
    fl, co = [], []
    for v in units.values():
        ans = [r for r in v if r["term_wrong"] and r["sense_wrong"]]
        if not ans:
            continue
        x = sum(1 for r in ans if r["term_wrong"] != "none" or r["sense_wrong"] != "none") / len(ans) >= 0.5
        (fl if v[0]["stratum"] in ("D", "F") else co).append(x)
    return {"any_error_flagged_D_F": rate(sum(fl), len(fl)), "any_error_control_R": rate(sum(co), len(co)),
            "n_works": len({r["work"] for r in readings}), "n_units": len(units)}


def fmt(r: dict) -> str:
    if not r or not r["n"]:
        return "—"
    ci = f" [{r['wilson95'][0]}–{r['wilson95'][1]}]" if r.get("wilson95") else ""
    return f"{r['k']}/{r['n']} ({r['pct']}%){ci}"


def summary_md(res: dict) -> str:
    m = list(RENDERINGS.values())
    lines = ["# Review sheet scores", "", f"Inputs: {', '.join(Path(p).name for p in res['inputs']) or 'none'}.", ""]
    if res["problems"]:
        lines += ["Rows not used:", *[f"- {p}" for p in res["problems"]], ""]
    lines += [f"| work | units read | reviewers | prefer {m[0]} / {m[1]} / neither | term wrong {m[0]} | term wrong {m[1]} | sense wrong {m[0]} | sense wrong {m[1]} | any error: flagged | any error: control | work estimate any error |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for w, s in res["works"].items():
        p = s["preference"]
        est = s["any_error"]["work_estimate_pct"]
        lines.append(f"| {w} | {s['n_units']} | {', '.join(s['reviewers'])} | {p[m[0]]} / {p[m[1]]} / {p['neither']} | "
                     f"{fmt(s['term_wrong'][m[0]]['units'])} | {fmt(s['term_wrong'][m[1]]['units'])} | {fmt(s['sense_wrong'][m[0]]['units'])} | "
                     f"{fmt(s['sense_wrong'][m[1]]['units'])} | {fmt(s['any_error']['flagged_D_F'])} | {fmt(s['any_error']['control_R'])} | "
                     f"{'—' if est is None else str(est) + '%'} |")
    pl = res["pooled"]
    lines += ["", f"Pooled over {pl['n_works']} work(s), {pl['n_units']} unit(s): any error in flagged passages {fmt(pl['any_error_flagged_D_F'])}, "
              f"in controls {fmt(pl['any_error_control_R'])}.", "", "Rates count units (a unit read by several reviewers counts as marked when half or more marked it); "
              "brackets are Wilson 95% intervals. \"Work estimate\" weights strata by size and is shown only when every stratum was read.", "", SUPPORTS]
    return "\n".join(lines)


# -------------------------------------------------------------------------------------------------------------- main

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--firstdrafts", default=str(FD_ROOT))
    b.add_argument("--out", default=str(OUT_ROOT))
    b.add_argument("--seed", default=SEED)
    s = sub.add_parser("score")
    s.add_argument("csv", nargs="*")
    s.add_argument("--key", default=str(OUT_ROOT / "key" / "sample_key.csv"))
    s.add_argument("--out", default=str(OUT_ROOT / "scores"))
    a = ap.parse_args(argv)
    if a.cmd == "build":
        summ = build(Path(a.firstdrafts), Path(a.out), a.seed)
        for w, x in summ.items():
            print(f"{w}: {x['sampled']}/{x['units']} units  " + "  ".join(f"{st} {x['strata'][st]['n']}/{x['strata'][st]['N']}" for st in STRATA))
    else:
        paths = [Path(p) for p in a.csv] or sorted((OUT_ROOT / "filled").glob("*.csv"))
        res = score(paths, Path(a.key), Path(a.out))
        print(f"{sum(len(v) for v in [res['works']])} work(s) scored, {len(res['problems'])} row problem(s); {Path(a.out) / 'summary.md'}")


if __name__ == "__main__":
    main()
