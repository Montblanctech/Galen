"""Cross-work term index of the Galen First Drafts (2026-11-13). No model involved.

Reads every Galen work's outputs/firstdrafts/<slug>/term_table.csv (the target words, their LSJ entry and the two
renderings A and B) and the published pages docs/first-drafts/<slug>/*.html (to find which page file holds each unit's
anchor), and writes outputs/firstdrafts/_index/:

  term_index.json        one record per lemma: LSJ entry and first sense, group, per-work loci and renderings, flags
  term_index.csv         one row per lemma x work (the same per-work summary, flat)
  term_occurrences.csv   one row per target occurrence (lemma key, work, unit, Kühn citation, page anchor, A, B)
  anchors_check.json     every unit cited, the page file holding its anchor, and the units whose anchor is missing

and, with --page DIR, a static searchable HTML page DIR/index.html in the drafts pages' style.

Lemma key: the LSJ entry id when the target has one (so spelling variants of one headword fall together), else the
Dilemma lemma. Renderings are compared by the term table's norm_A / norm_B (score_consistency.norm: lower case, stop
words and parentheses off, crude singular), the same key check (b) uses.

Consistency across works (only for lemmas in two or more works): in each work take the modal normalised rendering
of A and B pooled (ties: the alphabetically first). The lemma is flagged `diverges` when the works' modal renderings
are not all the same; `flag_A` / `flag_B` say the same for one model alone (each model translated each work with a
term memory of that work only, so a model can be consistent inside a work and still change between works).
`cross_work_agreement` is the share of the lemma's works whose modal rendering equals the commonest modal rendering.

Group (drugs, anatomy, diseases, qualities, other) is a keyword heuristic over the modal English renderings, the LSJ
first-sense gloss and the start of the LSJ entry; it is a finding aid, not a classification a scholar made.

Usage:  python pipeline/firstdrafts/term_index.py [--page DIR] [--base URL]
  --page DIR   also write the HTML page to DIR (use a scratch folder; not docs/)
  --base URL   prefix of the draft-page links (default "../", i.e. the page sits in a sibling folder of the drafts)
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import GDM, REPO, WORKS, out_dir  # noqa: E402

GROUPS = ("drugs", "anatomy", "diseases", "qualities", "other")
GROUP_LABEL = {"drugs": "drugs and materia medica", "anatomy": "anatomy", "diseases": "diseases and symptoms",
               "qualities": "qualities and temperaments", "other": "other"}

# Cue words per group, matched as whole words (a trailing s allowed) against the English evidence of a lemma.
CUES = {
    "drugs": """drug drugs medicine medicament remedy remedies antidote plaster poultice salve ointment unguent liniment
        cerate pastille troche lozenge collyrium eyesalve pessary suppository enema clyster purgative cathartic emetic
        plant herb shrub tree root seed fruit berry leaf leaves flower bark gum resin balsam juice sap oil myrrh
        frankincense incense pepper saffron aloe opium poppy hellebore scammony colocynth spurge euphorbium cumin anise
        fennel dill rue mint parsley celery lettuce cabbage mustard nettle vetch lentil barley wheat bean pea grape
        vinegar honey wax pitch tar turpentine alum salt soda nitre natron sulphur bitumen litharge verdigris rust
        copper bronze lead iron zinc cadmia calamine antimony stibnite chalcitis misy orpiment realgar cinnabar ochre
        earth clay ash lime gall oakgall galbanum opopanax ammoniacum sagapenum bdellium storax spikenard nard cassia
        cinnamon costus iris saffron castoreum dose decoction infusion potion draught electuary gargle mouthwash
        dressing compress fomentation embrocation emollient styptic caustic""",
    "anatomy": """bone bones muscle tendon sinew nerve vein artery vessel membrane ligament joint socket skull cranium rib
        vertebra spine backbone shoulder humerus arm forearm elbow wrist hand finger thumb leg thigh femur knee shin
        foot heel toe hip pelvis groin head face eye eyelid eyebrow ear nose nostril mouth lip tongue tooth teeth gum
        palate jaw cheek chin neck throat windpipe trachea larynx pharynx gullet oesophagus chest thorax breast nipple
        diaphragm lung heart pericardium liver spleen kidney bladder womb uterus vagina penis testicle scrotum stomach
        belly abdomen intestine bowel gut colon rectum anus navel skin flesh fat cartilage marrow brain meninx
        tissue gland tonsil uvula epiglottis acromion clavicle collarbone scapula shoulderblade armpit axilla
        hypochondrium peritoneum omentum mesentery body limb organ cavity ventricle""",
    "diseases": """fever disease illness sickness malady inflammation ulcer ulceration wound tumour tumor swelling
        abscess pain ache cough coma lethargy lethargus delirium frenzy phrenitis pleurisy pneumonia peripneumonia dropsy
        jaundice paroxysm crisis dislocation luxation fracture spasm convulsion cramp discharge diarrhoea diarrhea
        dysentery fistula gangrene erysipelas plethora apoplexy paralysis palsy ophthalmia rash itch scab sore lesion
        symptom pustule boil carbuncle cancer polyp wart callus haemorrhage hemorrhage bleeding catarrh flux colic
        vomiting nausea dyspnoea dyspnea asthma orthopnoea quinsy angina strangury ileus tenesmus epilepsy melancholy
        mania insanity madness vertigo fainting syncope shivering rigor chill sweating sweat insomnia somnolence
        stupor numbness tremor putrefaction putrescence corruption suppuration pus gout arthritis sciatica phthisis
        consumption wasting atrophy hiccup hiccough sneezing tertian quartan quotidian ague relapse""",
    "qualities": """hot cold warm cool dry moist wet humid bitter sweet sour acid acrid sharp pungent astringent harsh
        soft hard thick thin dense rarefied porous viscous sticky glutinous smooth rough heavy fatty oily greasy salty
        saline warming cooling drying moistening heating chilling mild bland insipid tart austere caustic biting
        heat warmth coldness cold dryness moisture humidity wetness bitterness sweetness sourness acidity acrimony
        pungency astringency harshness softness hardness thickness thinness density rarity porosity viscosity
        smoothness roughness heaviness lightness fattiness saltiness mixture temperament blend krasis dyscrasia
        distemper quality power faculty potency""",
}
CUE_SETS = {g: set(v.split()) for g, v in CUES.items()}
# a few cues are ambiguous between groups; they count only where listed first
PRIORITY = ("drugs", "anatomy", "diseases", "qualities")
WORD = re.compile(r"[a-z]+")


def strip_greek(s: str) -> str:
    """Accent- and breathing-blind lower case, for search keys."""
    s = unicodedata.normalize("NFD", s or "").lower()
    return unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c))).replace("ς", "σ")


def _words(s: str) -> list[str]:
    out = []
    for w in WORD.findall((s or "").lower()):
        out.append(w)
        if w.endswith("s") and len(w) > 3:
            out.append(w[:-1])
    return out


def classify(pos: str, renderings: list[str], gloss: str, entry_text: str) -> tuple[str, dict]:
    """Group of one lemma from its English evidence: each modal rendering (weight 2), the LSJ first-sense gloss (1),
    the first 300 characters of the LSJ entry (1). The best group needs a score of at least 2 and at least one hit in
    the renderings (the LSJ entry alone mentions too many body parts and plants in passing), else 'other'. An
    adjective never goes to 'anatomy' (an adjective of a body part is not the body part)."""
    score, from_rend = Counter(), set()
    for weight, texts, is_rend in ((2, renderings, True), (1, [gloss], False), (1, [(entry_text or "")[:300]], False)):
        for t in texts:
            ws = set(_words(t))
            for g in PRIORITY:
                if ws & CUE_SETS[g]:
                    score[g] += weight
                    if is_rend:
                        from_rend.add(g)
    if pos == "ADJ":
        score.pop("anatomy", None)
    score = Counter({g: v for g, v in score.items() if g in from_rend})
    if not score:
        return "other", {}
    best = max(PRIORITY, key=lambda g: (score[g], -PRIORITY.index(g)))
    return (best if score[best] >= 2 else "other"), dict(score)


# Comparison key one step coarser than norm: degree and filler words off, a crude stem, so that rare / rarer /
# more rarely or complete / most complete count as one rendering. It is used only to decide divergence.
CORE_STOP = set("more most less least very as who which what that such kind sort part form one thing being so too quite rather".split())


def stem(t: str) -> str:
    for suf in ("ically", "ally", "ly"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break
    for suf in ("est", "er"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break
    if len(t) > 3 and t[-1] == t[-2] and t[-1] not in "aeiouls":
        t = t[:-1]
    if t.endswith("e") and len(t) > 3:
        t = t[:-1]
    if t.endswith("i") and len(t) >= 3:   # drier -> dri -> dry
        t = t[:-1] + "y"
    return t


def core(n: str) -> str:
    """core("more rarely") == core("rare") == core("rarer") == "rar"; core("") == ""."""
    toks = [stem(t) for t in (n or "").split() if t not in CORE_STOP]
    return " ".join(sorted(set(toks))) if toks else (n or "")


JUNK_GLOSS = re.compile(r"^(cf\b|etc\b|v\.|=|sc\.)", re.I)


def clean_gloss(g: str) -> str:
    """The LSJ first-sense gloss, or "" when the index picked up a cross-reference or a fragment (cf, etc, an
    unbalanced parenthesis) instead of a sense."""
    g = (g or "").strip()
    if not g or JUNK_GLOSS.match(g) or g.count(")") > g.count("(") or len(g) < 3:
        return ""
    return g


def divergence(per_work: list[dict]) -> dict:
    """Cross-work consistency of one lemma from its per-work summaries (see the module docstring). Works whose
    renderings are all empty do not count. The core key decides; `diverges_surface` uses the plain norm key."""
    modes = [p["modal_core"] for p in per_work if p["modal_core"]]
    if len(modes) < 2:
        return {"cross_work_agreement": None, "distinct_modal": len(set(modes)), "diverges": None, "diverges_surface": None,
                "flag_A": None, "flag_B": None, "global_core": modes[0] if modes else ""}
    mc = Counter(modes)
    top = modal(mc)
    out = {"cross_work_agreement": round(mc[top] / len(modes), 3), "distinct_modal": len(mc), "diverges": len(mc) > 1,
           "diverges_surface": len({p["modal"] for p in per_work if p["modal"]}) > 1, "global_core": top}
    for t in ("A", "B"):
        mt = [p[f"core_{t}"] for p in per_work if p[f"core_{t}"]]
        out[f"flag_{t}"] = len(set(mt)) > 1 if len(mt) >= 2 else None
    return out


def lemma_key(r: dict) -> str:
    """LSJ entry id, else the accent-blind lemma (two spellings of a word LSJ lacks, καταγματικός / καταγματῖκός, fall together)."""
    return r["lsj_entry_id"] or "lemma:" + strip_greek(r["dilemma_lemma"] or r["odycy_lemma"])


def modal(c: Counter) -> str:
    """Commonest value of a counter; ties go to the alphabetically first, so the result is deterministic."""
    if not c:
        return ""
    top = max(c.values())
    return min(k for k, v in c.items() if v == top)


def galen_slugs() -> list[str]:
    """Every Galen work (common.WORKS order) that has a term table on disk."""
    return [s for s in WORKS if (out_dir(s) / "term_table.csv").exists()]


UNIT_ID = re.compile(r'<div class="unit[^"]*" id="([^"]+)"')


def page_anchors(slug: str, docs_root: Path) -> dict[str, str]:
    """unit id -> page file (index.html or book-N.html) holding its anchor in the published drafts pages."""
    found: dict[str, str] = {}
    d = docs_root / slug
    if not d.exists():
        return found
    for f in sorted(d.glob("*.html")):
        for m in UNIT_ID.finditer(f.read_text(encoding="utf-8")):
            found.setdefault(html.unescape(m.group(1)), f.name)
    return found


def read_rows(slugs: list[str]) -> list[dict]:
    rows = []
    for s in slugs:
        with (out_dir(s) / "term_table.csv").open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["work"] = s
                rows.append(r)
    return rows


def kuhn(slug: str, page: str) -> str:
    return f"K. {WORKS[slug]['kuhn_vol']} {page}" if slug in WORKS else page


def build(rows: list[dict], anchors: dict[str, dict[str, str]]) -> dict:
    """The index from term-table rows (each with a 'work' field) and the anchor map {slug: {unit_id: file}}."""
    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_key[lemma_key(r)].append(r)
    works_order = list(dict.fromkeys(r["work"] for r in rows))
    # the cycle-1 table (adversus-lycum) has no lsj_first_sense_gloss column; the same LSJ entry in a later work carries it
    gloss: dict[str, str] = {}
    for r in rows:
        if r.get("lsj_first_sense_gloss") and r["lsj_entry_id"]:
            gloss.setdefault(r["lsj_entry_id"], r["lsj_first_sense_gloss"])
    lemmas, missing = [], set()
    for key, rs in by_key.items():
        lem_c = Counter(r["dilemma_lemma"] or r["odycy_lemma"] for r in rs)
        pos = modal(Counter(r["pos"] for r in rs))
        first = rs[0]
        per_work = []
        for w in works_order:
            wr = [r for r in rs if r["work"] == w]
            if not wr:
                continue
            ca, cb, raw = Counter(), Counter(), defaultdict(Counter)
            loci = []
            for r in wr:
                for t, c in (("A", ca), ("B", cb)):
                    n = r[f"norm_{t}"]
                    if n:
                        c[n] += 1
                        raw[n][r[f"rendering_{t}"].strip()] += 1
                f = anchors.get(w, {}).get(r["unit_id"], "")
                if not f:
                    missing.add((w, r["unit_id"]))
                loci.append({"unit": r["unit_id"], "kuhn": kuhn(w, r["page"]), "file": f, "A": r["rendering_A"], "B": r["rendering_B"],
                             "agree": r["agree"]})
            pooled = ca + cb
            cc = Counter()
            for k, v in pooled.items():
                cc[core(k)] += v
            per_work.append({
                "work": w, "n": len(wr),
                "A": [[modal(raw[k]), k, v] for k, v in sorted(ca.items(), key=lambda kv: (-kv[1], kv[0]))],
                "B": [[modal(raw[k]), k, v] for k, v in sorted(cb.items(), key=lambda kv: (-kv[1], kv[0]))],
                "modal": modal(pooled), "modal_core": modal(cc), "modal_A": modal(ca), "modal_B": modal(cb),
                "core_A": core(modal(ca)), "core_B": core(modal(cb)),
                "agree_ab": sum(r["agree"] == "y" for r in wr), "both_ab": sum(r["agree"] in ("y", "n") for r in wr),
                "loci": loci,
            })
        raw_gloss = first.get("lsj_first_sense_gloss") or gloss.get(first["lsj_entry_id"], "")
        rec = {
            "key": key, "lemma": modal(lem_c), "variants": sorted(lem_c), "pos": pos,
            "lsj_entry_id": first["lsj_entry_id"], "lsj_headword": first["lsj_headword"], "lsj_key": first["lsj_key"],
            "lsj_first_sense": clean_gloss(raw_gloss), "lsj_first_sense_raw": raw_gloss, "lsj_senses": first["lsj_sense_count"],
            "n": len(rs), "n_works": len(per_work), "works": per_work,
        }
        rec.update(divergence(per_work))
        all_modes = [x[1] for p in per_work for x in p["A"][:1] + p["B"][:1]]
        rec["group"], rec["group_score"] = classify(pos, all_modes, rec["lsj_first_sense"], first["lsj_entry_text"])
        lemmas.append(rec)
    lemmas.sort(key=lambda r: (strip_greek(r["lemma"]), r["key"]))
    return {"lemmas": lemmas, "missing_anchors": sorted(missing), "works": works_order}


def inconsistency_rank(lemmas: list[dict], min_works: int = 3, min_per_work: int = 2, terms_only: bool = True) -> list[dict]:
    """Lemmas whose usual rendering differs between works, most divergent first. Only works where the lemma occurs at
    least min_per_work times count (a single occurrence has no usual rendering), and at least min_works such works are
    needed. Order: lowest agreement over those works, then most distinct usual renderings, most works, most occurrences.
    terms_only drops adjectives of the group 'other' (quantity and degree words such as πάμπολυς, μικρός, ἑκάτερος,
    whose renderings vary with the syntax, not the sense). Each returned record carries `rank_works` (the counted
    works), `rank_agreement` and `rank_distinct`."""
    out = []
    for r in lemmas:
        if terms_only and r["pos"] == "ADJ" and r["group"] == "other":
            continue
        ws = [p for p in r["works"] if p["n"] >= min_per_work and p["modal_core"]]
        if len(ws) < min_works:
            continue
        mc = Counter(p["modal_core"] for p in ws)
        if len(mc) < 2:
            continue
        out.append(dict(r, rank_works=len(ws), rank_agreement=round(mc[modal(mc)] / len(ws), 3), rank_distinct=len(mc)))
    return sorted(out, key=lambda r: (r["rank_agreement"], -r["rank_distinct"], -r["rank_works"], -r["n"], r["lemma"]))


def summary(ix: dict) -> dict:
    L = ix["lemmas"]
    multi = [r for r in L if r["n_works"] >= 2]
    return {
        "built": date.today().isoformat(),
        "works": ix["works"], "n_works": len(ix["works"]),
        "occurrences": sum(r["n"] for r in L), "lemmas": len(L),
        "lemmas_without_lsj_entry": sum(not r["lsj_entry_id"] for r in L),
        "lemmas_with_entry_but_no_first_sense": sum(bool(r["lsj_entry_id"]) and not r["lsj_first_sense"] for r in L),
        "by_group": dict(Counter(r["group"] for r in L)),
        "by_pos": dict(Counter(r["pos"] for r in L)),
        "by_n_works": {str(k): v for k, v in sorted(Counter(r["n_works"] for r in L).items())},
        "in_two_or_more_works": len(multi),
        "diverging": sum(bool(r["diverges"]) for r in multi),
        "diverging_surface": sum(bool(r["diverges_surface"]) for r in multi),
        "ranked_divergent": len(inconsistency_rank(L)),
        "diverging_A": sum(bool(r["flag_A"]) for r in multi), "diverging_B": sum(bool(r["flag_B"]) for r in multi),
        "in_three_or_more_works": sum(r["n_works"] >= 3 for r in L),
        "diverging_three_or_more": sum(bool(r["diverges"]) for r in L if r["n_works"] >= 3),
        "missing_anchors": len(ix["missing_anchors"]),
        "units_cited": len({(p["work"], l["unit"]) for r in L for p in r["works"] for l in p["loci"]}),
    }


def write_outputs(ix: dict, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    sm = summary(ix)
    top = inconsistency_rank(ix["lemmas"])
    (dest / "term_index.json").write_text(json.dumps({"summary": sm, "most_inconsistent": [r["key"] for r in top[:50]], "lemmas": ix["lemmas"]},
                                                     ensure_ascii=False, indent=0), encoding="utf-8")
    with (dest / "term_index.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "lemma", "pos", "group", "lsj_entry_id", "lsj_headword", "lsj_first_sense", "lemma_n", "lemma_n_works", "diverges",
                    "cross_work_agreement", "flag_A", "flag_B", "work", "n", "modal", "renderings_A", "renderings_B", "kuhn_loci"])
        for r in ix["lemmas"]:
            for p in r["works"]:
                w.writerow([r["key"], r["lemma"], r["pos"], r["group"], r["lsj_entry_id"], r["lsj_headword"], r["lsj_first_sense"], r["n"], r["n_works"],
                            "" if r["diverges"] is None else int(r["diverges"]), "" if r["cross_work_agreement"] is None else r["cross_work_agreement"],
                            "" if r["flag_A"] is None else int(r["flag_A"]), "" if r["flag_B"] is None else int(r["flag_B"]),
                            p["work"], p["n"], p["modal"], "; ".join(f"{d} ({n})" for d, _, n in p["A"]), "; ".join(f"{d} ({n})" for d, _, n in p["B"]),
                            "; ".join(dict.fromkeys(l["kuhn"] for l in p["loci"]))])
    with (dest / "term_occurrences.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "lemma", "work", "unit_id", "kuhn", "page_file", "anchor", "rendering_A", "rendering_B", "agree"])
        for r in ix["lemmas"]:
            for p in r["works"]:
                for l in p["loci"]:
                    w.writerow([r["key"], r["lemma"], p["work"], l["unit"], l["kuhn"], l["file"], f"{p['work']}/{l['file']}#{l['unit']}" if l["file"] else "",
                                l["A"], l["B"], l["agree"]])
    (dest / "anchors_check.json").write_text(json.dumps({"units_cited": sm["units_cited"], "missing": [list(x) for x in ix["missing_anchors"]]}, indent=1), encoding="utf-8")
    return sm


# ---------------------------------------------------------------- page

def usual(p: dict) -> str:
    """Display form of a work's usual rendering: the commonest raw rendering of its modal normalised key."""
    for lst in (p["A"], p["B"]):
        for disp, k, _ in lst:
            if k == p["modal"]:
                return disp
    return p["modal"]


def page_data(ix: dict) -> dict:
    """Compact data for the page: per lemma a short array, per work the renderings and the loci grouped by unit."""
    works = ix["works"]
    widx = {w: i for i, w in enumerate(works)}
    files = sorted({l["file"] for r in ix["lemmas"] for p in r["works"] for l in p["loci"] if l["file"]})
    fidx = {f: i for i, f in enumerate(files)}
    out = []
    for r in ix["lemmas"]:
        pw = []
        for p in r["works"]:
            units = list(dict.fromkeys((l["unit"], l["kuhn"], l["file"]) for l in p["loci"]))
            pw.append([widx[p["work"]], p["n"], [[d, n] for d, _, n in p["A"]], [[d, n] for d, _, n in p["B"]],
                       [[u, k.split(" ")[-1], fidx.get(f, -1)] for u, k, f in units], usual(p), p["modal_core"]])
        out.append([r["lemma"], r["lsj_headword"], r["lsj_first_sense"], GROUPS.index(r["group"]), r["pos"][0], r["n"],
                    -1 if r["cross_work_agreement"] is None else r["cross_work_agreement"], r["distinct_modal"],
                    int(bool(r["flag_A"])), int(bool(r["flag_B"])), strip_greek(" ".join([r["lemma"]] + r["variants"] + [r["lsj_headword"]])) + " " + r["lsj_key"].lower(), pw, r.get("global_core") or ""])
    return {"works": [[w, WORKS[w]["title_lat"], WORKS[w]["title_eng"], WORKS[w]["kuhn_vol"]] for w in works], "files": files,
            "groups": [GROUP_LABEL[g] for g in GROUPS], "lemmas": out}


def write_page(ix: dict, sm: dict, dest: Path, base: str = "../") -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    data = json.dumps(page_data(ix), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    top = inconsistency_rank(ix["lemmas"])[:12]
    esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    top_html = "".join(f'<li><a href="#q={esc(r["lemma"])}" data-q="{esc(r["lemma"])}">{esc(r["lemma"])}</a> '
                       f'<span class=small>({esc(r["lsj_first_sense"]) or "no LSJ gloss"}): {r["rank_works"]} works, {r["rank_distinct"]} different usual renderings: {esc(" / ".join(dict.fromkeys(usual(p) for p in r["works"] if p["n"] >= 2)))}</span></li>'
                       for r in top)
    doc = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Galen First Drafts: term index</title>
<meta name=description content="Every target term of the Galen First Drafts across {sm['n_works']} works: LSJ first sense, Kühn loci, how the two machine renderings translated it in each work, and where they diverge.">
<style>
:root{{color-scheme:light dark;--bg:#fff;--fg:#222;--mut:#555;--line:#ddd;--soft:#f3f1ec;--acc:#7a1f1f;--ok:#dff3df;--bad:#f9d6d6;--warn:#fbefc9}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16130f;--fg:#e9e2d6;--mut:#a39a8e;--line:#3a342c;--soft:#25201a;--acc:#c46a5a;--ok:#1f3a24;--bad:#4a2323;--warn:#4a3d1a}}}}
body{{font:15px/1.5 Georgia,serif;max-width:1100px;margin:0 auto;padding:0 1rem 3rem;color:var(--fg);background:var(--bg)}}
a{{color:var(--acc)}}
.banner{{background:#7a1f1f;color:#fff;padding:.6rem 1rem;font-size:.95em;margin:0 -1rem}} .banner a{{color:#ffd}}
h1{{font-size:1.5rem;margin:.8rem 0 .2rem}} h2{{font-size:1.1rem;margin:1.4rem 0 .3rem;border-top:1px solid var(--line);padding-top:.8rem}}
.small{{color:var(--mut);font-size:.88em}}
.bar{{position:sticky;top:0;z-index:5;background:var(--bg);padding:.6rem 0;border-bottom:1px solid var(--line);font:14px/1.4 system-ui,"Segoe UI",sans-serif}}
.bar input[type=search]{{width:100%;box-sizing:border-box;font:16px system-ui,sans-serif;padding:.5rem .7rem;border:1px solid #bbb;border-radius:.5rem;background:var(--bg);color:var(--fg)}}
.chips{{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.45rem;align-items:center}}
.chips button,.chips select{{font:inherit;border:1px solid #bbb;background:var(--bg);color:var(--fg);border-radius:999px;padding:.2rem .7rem;cursor:pointer}}
.chips button[aria-pressed=true]{{background:#7a1f1f;border-color:#7a1f1f;color:#fff}}
#count{{color:var(--mut);margin-left:auto}}
@media(max-width:640px){{.chips{{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}} .chips>*{{flex:0 0 auto}} .chips::-webkit-scrollbar{{display:none}}}}
.lem{{border-bottom:1px solid var(--line);padding:.45rem 0}}
.lem>summary{{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;gap:.2rem .7rem;align-items:baseline}}
.lem>summary::-webkit-details-marker{{display:none}}
.g{{font-size:1.12em;font-weight:bold}} .gl{{color:var(--mut);font-style:italic}}
.tag{{font:12px/1.5 system-ui,sans-serif;border:1px solid #999;border-radius:.4em;padding:0 .4em;color:var(--mut)}}
.tag.div{{background:var(--bad);border-color:#a33;color:var(--fg)}} .tag.con{{background:var(--ok);border-color:#7a7;color:var(--fg)}}
.ren{{font:13px/1.4 system-ui,sans-serif;color:var(--mut)}}
table.w{{border-collapse:collapse;width:100%;font-size:.9em;margin:.4rem 0}}
table.w td,table.w th{{border-bottom:1px solid var(--line);padding:.2rem .4rem;text-align:left;vertical-align:top}}
table.w th{{font-weight:normal;color:var(--mut);font-size:.85em}}
.odd td.m{{background:var(--warn)}}
.loc a{{display:inline-block;margin:0 .35em .1em 0;font:13px system-ui,sans-serif;white-space:nowrap}}
@media(max-width:640px){{table.w thead{{display:none}} table.w tr{{display:block;border-bottom:1px solid var(--line);padding:.3rem 0}} table.w td{{display:block;border:0;padding:.05rem 0}}
 table.w td[data-h]::before{{content:attr(data-h) ": ";color:var(--mut);font:12px system-ui,sans-serif}}}}
#more{{margin:1rem 0;font:14px system-ui,sans-serif;padding:.4rem 1rem;border:1px solid #bbb;border-radius:999px;background:var(--bg);color:var(--fg)}}
</style></head><body>
<div class=banner><strong>Machine first drafts, unverified.</strong> The renderings below are language-model output that no scholar has checked; the groups are a keyword heuristic. Use this index to find where to look. <a href="{esc(base)}">All drafts</a></div>
<h1>Galen First Drafts: term index</h1>
<p class=small>{sm['lemmas']:,} Greek target lemmas ({sm['occurrences']:,} occurrences) across the {sm['n_works']} Galen works published as machine first drafts. For each lemma: the first sense of its LSJ entry, the works and Kühn pages where it is a target term, and how rendering A (<code>claude-fable-5-1</code>) and rendering B (<code>claude-opus-5-5</code>) translated it in each work. Renderings are compared after the normalisation the drafts' agreement check uses (lower case, stop words off, singular), with degree words and endings also set aside (rare, rarer and more rarely count as one). <span class="tag div">diverges</span> means the usual rendering of the lemma is not the same in every work it occurs in ({sm['diverging']:,} of the {sm['in_two_or_more_works']:,} lemmas found in two or more works); each work was translated with a term memory of that work only. Tap a lemma to see its works; each page number links to the passage in the draft.</p>
<details><summary class=small>Most divergent terms across works (three or more works)</summary><ol class=small>{top_html}</ol></details>
<div class=bar><input type=search id=q placeholder="Search Greek (accents optional), LSJ key, or English: e.g. κῶμα, krasis, plaster" autocomplete=off aria-label="Search terms">
<div class=chips id=chips></div></div>
<div id=list></div><button id=more type=button hidden>Show more</button>
<h2>About the data</h2><p class=small>Built {sm['built']} by <code>galen-density-map/pipeline/firstdrafts/term_index.py</code> from each work's <code>term_table.csv</code>; data: <code>outputs/firstdrafts/_index/</code> (JSON and CSV). Lemma = LSJ entry where there is one ({sm['lemmas'] - sm['lemmas_without_lsj_entry']:,} lemmas), else the Dilemma lemma. Only words the pipeline chose as target terms (rare or hard nouns and adjectives, at most eight per passage) are indexed, so a lemma's absence from a work means it was not a target there, not that Galen does not use it. The usual rendering of a lemma in a work is its commonest normalised rendering over A and B together.</p>
<script id=d type="application/json">{data}</script>
<script>
(function(){{
var D=JSON.parse(document.getElementById('d').textContent),BASE={json.dumps(base)},L=D.lemmas,W=D.works,F=D.files,G=D.groups;
function e(s){{return String(s).replace(/[&<>"]/g,function(c){{return{{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
function fold(s){{return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/ς/g,'σ')}}
// search text per lemma: Greek keys + LSJ gloss + every English rendering
var S=L.map(function(r){{var t=[r[10],fold(r[2])];r[11].forEach(function(p){{p[2].concat(p[3]).forEach(function(x){{t.push(x[0].toLowerCase())}})}});return t.join(' | ')}});
var st={{q:'',g:-1,only:0,sort:'az'}},shown=0,res=[],PAGE=60;
var chips=document.getElementById('chips'),list=document.getElementById('list'),more=document.getElementById('more'),q=document.getElementById('q');
var h='<button type=button data-g=-1 aria-pressed=true>all</button>';G.forEach(function(g,i){{h+='<button type=button data-g='+i+'>'+e(g)+'</button>'}});
h+='<button type=button data-only=1>diverging only</button><select id=sort aria-label="Sort"><option value=az>A–Ω</option><option value=n>most frequent</option><option value=div>most divergent</option><option value=w>most works</option></select><span id=count></span>';
chips.innerHTML=h;
chips.onclick=function(ev){{var b=ev.target.closest('button');if(!b)return;if(b.dataset.only){{st.only=1-st.only;b.setAttribute('aria-pressed',!!st.only)}}else{{st.g=+b.dataset.g;chips.querySelectorAll('[data-g]').forEach(function(x){{x.setAttribute('aria-pressed',x===b)}})}}run()}};
document.getElementById('sort').onchange=function(){{st.sort=this.value;run()}};
var tm;q.oninput=function(){{clearTimeout(tm);tm=setTimeout(function(){{st.q=q.value;run()}},120)}};
function ren(a){{return a.map(function(x){{return e(x[0])+(x[1]>1?' <span class=small>×'+x[1]+'</span>':'')}}).join(', ')||'<span class=small>—</span>'}}
function body(r){{var o='<table class=w><thead><tr><th>work</th><th>n</th><th>A (fable-5-1)</th><th>B (opus-5-5)</th><th>Kühn pages</th></tr></thead><tbody>';
var top=r[12];
r[11].forEach(function(p){{var w=W[p[0]];o+='<tr class="'+(r[6]>=0&&r[7]>1&&p[6]&&p[6]!==top?'odd':'')+'"><td data-h=work><a href="'+e(BASE+w[0]+'/')+'">'+e(w[1])+'</a> <span class=small>K. '+e(w[3])+'</span></td><td data-h=n>'+p[1]+'</td><td class=m data-h=A>'+ren(p[2])+'</td><td class=m data-h=B>'+ren(p[3])+'</td><td class=loc data-h=Kühn>'+
p[4].map(function(u){{return u[2]<0?e(u[1]):'<a href="'+e(BASE+w[0]+'/'+(F[u[2]]==='index.html'?'':F[u[2]])+'#'+u[0])+'" title="'+e(u[0])+'">'+e(u[1])+'</a>'}}).join('')+'</td></tr>'}});
return o+'</tbody></table>'}}
function card(i){{var r=L[i],flag=r[6]<0?'':(r[7]>1?'<span class="tag div" title="usual rendering differs between works; agreement '+Math.round(r[6]*100)+'%">diverges · '+r[7]+' renderings</span>':'<span class="tag con">same in all works</span>');
var ws=r[11].map(function(p){{return p[5]}});var uniq=ws.filter(function(x,j){{return x&&ws.indexOf(x)===j}});
return '<details class=lem data-i='+i+'><summary><span class=g lang=grc>'+e(r[0])+'</span>'+(r[1]&&r[1]!==r[0]?'<span class=small lang=grc>LSJ '+e(r[1])+'</span>':'')+'<span class=gl>'+(r[2]?e(r[2]):'no LSJ entry')+'</span><span class=tag>'+e(G[r[3]].split(' ')[0])+'</span><span class=tag>'+r[11].length+' work'+(r[11].length>1?'s':'')+' · '+r[5]+'×</span>'+flag+
'<span class=ren>'+e(uniq.slice(0,6).join(' · '))+'</span></summary></details>'}}
list.addEventListener('toggle',function(ev){{var d=ev.target;if(d.open&&!d.dataset.f){{d.dataset.f=1;d.insertAdjacentHTML('beforeend',body(L[+d.dataset.i]))}}}},true);
function run(){{var t=fold(st.q.trim()),tt=t?t.split(/\\s+/):[];res=[];
for(var i=0;i<L.length;i++){{var r=L[i];if(st.g>=0&&r[3]!==st.g)continue;if(st.only&&!(r[7]>1))continue;var ok=true;for(var k=0;k<tt.length;k++)if(S[i].indexOf(tt[k])<0){{ok=false;break}}if(ok)res.push(i)}}
var by={{n:function(a,b){{return L[b][5]-L[a][5]}},w:function(a,b){{return L[b][11].length-L[a][11].length||L[b][5]-L[a][5]}},div:function(a,b){{var x=L[a],y=L[b];var ax=x[6]<0?2:x[6],bx=y[6]<0?2:y[6];return ax-bx||y[7]-x[7]||y[11].length-x[11].length||y[5]-x[5]}}}}[st.sort];if(by)res.sort(by);
shown=0;list.innerHTML='';page();document.getElementById('count').textContent=res.length+' of '+L.length;
try{{history.replaceState(null,'',st.q?'#q='+encodeURIComponent(st.q):location.pathname+location.search)}}catch(e){{}}}}
function page(){{var h='';var end=Math.min(res.length,shown+PAGE);for(var i=shown;i<end;i++)h+=card(res[i]);list.insertAdjacentHTML('beforeend',h);shown=end;more.hidden=shown>=res.length;
if(res.length===1){{var d=list.querySelector('details');if(d)d.open=true}}}}
more.onclick=page;
document.querySelectorAll('[data-q]').forEach(function(a){{a.onclick=function(ev){{ev.preventDefault();q.value=a.dataset.q;st.q=a.dataset.q;run();q.scrollIntoView()}}}});
var m=location.hash.match(/^#q=(.*)/);if(m){{try{{q.value=decodeURIComponent(m[1])}}catch(e){{}}st.q=q.value}}
run();
}})();
</script></body></html>"""
    p = dest / "index.html"
    p.write_text(doc, encoding="utf-8")
    return p


def main(argv=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=None, help="write the HTML page to this folder (scratch; not docs/)")
    ap.add_argument("--base", default="../", help="link prefix of the drafts pages")
    ap.add_argument("--docs", default=str(REPO / "docs" / "first-drafts"), help="published drafts pages, read for the anchors")
    ap.add_argument("--out", default=str(GDM / "outputs" / "firstdrafts" / "_index"))
    a = ap.parse_args(argv)
    slugs = galen_slugs()
    docs = Path(a.docs)
    anchors = {s: page_anchors(s, docs) for s in slugs}
    ix = build(read_rows(slugs), anchors)
    sm = write_outputs(ix, Path(a.out))
    print(json.dumps(sm, ensure_ascii=False))
    for r in inconsistency_rank(ix["lemmas"])[:15]:
        print(f"  {r['lemma']} ({r['lsj_first_sense']}): {r['n_works']} works, agreement {r['cross_work_agreement']}, modes "
              + "; ".join(f"{p['work']}={p['modal']}" for p in r["works"]))
    if a.page:
        p = write_page(ix, sm, Path(a.page), a.base)
        print(f"wrote {p} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
