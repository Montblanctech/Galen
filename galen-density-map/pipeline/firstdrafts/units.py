"""Galen First Drafts v0, stage 1: split a First1KGreek TEI into translation units (spec: firstdrafts_v0_spec.md).

Unit = one Kühn page snapped back to the nearest preceding sentence end, so no unit starts or ends
mid-sentence; a unit records every Kühn page it touches and keeps the page breaks inline as [NNN].
For every unit: the Greek (display and plain), its locus, chapter(s), token count, the odyCy token
range it aligns to (lemma + POS from data/lemmatized/, greedy surface alignment), the punch-list
density per 100 tokens (the MT-2026 measure), and the target words (NOUN/ADJ tokens whose odyCy
lemma is on the punch list or four-way `genuinely_hard`) with their Dilemma lemma.

Writes outputs/firstdrafts/<slug>/units.jsonl, targets.csv, units_meta.json, cost_estimate.json.
Deterministic; no model involved. Usage:
  .venv/Scripts/python -X utf8 pipeline/firstdrafts/units.py --work adversus-lycum
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter

from lxml import etree

from common import GDM, PRICES_PER_MTOK, SENTENCE_END, WORKS, nfc, out_dir, strip_punct, token_proxy_english, token_proxy_greek, write_jsonl

from h3m.align import align_surfaces  # noqa: E402
from lib.greek_normalize import normalize_lunate_sigma  # noqa: E402

TEI = "{http://www.tei-c.org/ns/1.0}"
TARGET_POS = {"NOUN", "ADJ"}
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
TARGET_CAP = 8  # per unit; all punch-list tokens first (spec)


def chapter_key(c: str) -> list:
    """'2.3a' -> [2, 3, 'a']: numeric parts numerically, a letter suffix (Kühn has chapter 3a) after."""
    out = []
    for part in c.split("."):
        m = re.match(r"(\d+)(.*)", part)
        out += [int(m.group(1)), m.group(2)] if m else [10**6, part]
    return out


def tei_tokens(xml_path) -> list[dict]:
    """Token stream with page / chapter attributes; page breaks become inline markers."""
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    root = etree.parse(str(xml_path), parser).getroot()
    edition = root.find(f".//{TEI}div[@type='edition']")
    state = {"page": None, "chapter": None, "book": None, "head": False}
    toks: list[dict] = []

    def chap() -> str | None:
        """'book.chapter' where the TEI has books (Composition by Kind), else the chapter number."""
        if state["chapter"] is None:
            return None
        return f"{state['book']}.{state['chapter']}" if state["book"] else state["chapter"]

    def emit(text: str) -> None:
        text = normalize_lunate_sigma(nfc(text))
        for m in re.finditer(r"\S+", text):
            toks.append({"surface": m.group(0), "page": state["page"], "chapter": chap(), "book": state["book"], "head": state["head"]})

    def walk(el) -> None:
        tag = etree.QName(el).localname
        if tag in {"note", "app", "rdg", "teiHeader"}:
            return
        if tag == "pb":
            state["page"] = el.get("n")
            toks.append({"surface": f"[{el.get('n')}]", "page": state["page"], "chapter": chap(), "book": state["book"], "head": False, "pb": True})
        elif tag == "div" and el.get("subtype") == "book":
            state["book"] = el.get("n")
            state["chapter"] = None
        elif tag == "div" and el.get("subtype") == "chapter":
            state["chapter"] = el.get("n")
        elif tag == "head":
            state["head"] = True
        if el.text and tag not in {"pb", "milestone"}:
            emit(el.text)
        for ch in el:
            walk(ch)
            if ch.tail:
                emit(ch.tail)
        if tag == "head":
            state["head"] = False

    walk(edition)
    return toks


def write_estimate(out, units: list[dict], targets: list[dict]) -> None:
    # --- cost estimate (pre-registered proxies; API list prices; v0.2: term memory, whole LSJ entries to the judge,
    #     judge items in groups of 10, direct and Message-Batches (half price) totals)
    n_words = sum(u["n_tokens"] for u in units)
    greek_tok = token_proxy_greek(n_words)
    ctx_overhead = greek_tok * 2  # neighbouring units as context, both sides
    prompt_fixed = 800 * len(units)  # system prompt + locus + target list framing
    memory_tok = 30 * len(targets)  # TERM MEMORY block: ~30 tokens per target that has a prior rendering (upper bound: every target)
    eng_tok = token_proxy_english(int(n_words * 1.25))  # English runs ~25% longer in words
    table_tok = 25 * len(targets)
    judge_items = 2 * len(targets) + 20
    judge_groups = -(-judge_items // 10)
    # thinking allowance (v0.2): all three models think by default and thinking is billed as output; the cycle 1 proxy
    # had no term for it. Allowance per call, pre-registered here and measured against usage.jsonl after the run:
    THINK = {"translate": 2500, "backtranslate": 800, "judge_group": 600}
    est = {"spec": "firstdrafts_v02_spec.md", "n_units": len(units), "n_greek_words": n_words, "n_targets": len(targets),
           "proxy": "Greek words x4.5 tokens, English words x1.3, prompt 800 tok/unit, context = both neighbours, term memory 30 tok/target, "
                    "judge 650 input + 20 output tokens per item (whole LSJ entry, groups of 10), back-translation 300 tok prompt/unit, "
                    f"thinking allowance (output tokens) {THINK['translate']}/translation unit, {THINK['backtranslate']}/back-translation unit, {THINK['judge_group']}/judge group",
           "thinking_allowance_output_tokens": THINK,
           "prices_per_mtok": {m: {"input": p[0], "output": p[1]} for m, p in PRICES_PER_MTOK.items()}, "items": {}, "total_usd_direct": 0.0, "total_usd_batch": 0.0}

    def add(name, model, tin, tout):
        pi, po = PRICES_PER_MTOK[model]
        usd = tin / 1e6 * pi + tout / 1e6 * po
        est["items"][name] = {"model": model, "input_tokens": tin, "output_tokens": tout, "usd": round(usd, 2), "usd_batch": round(usd / 2, 2)}
        est["total_usd_direct"] = round(est["total_usd_direct"] + usd, 2)
        est["total_usd_batch"] = round(est["total_usd_batch"] + usd / 2, 2)

    add("rendering_A", "claude-fable-5-1", greek_tok + ctx_overhead + prompt_fixed + memory_tok, eng_tok + table_tok + THINK["translate"] * len(units))
    add("rendering_B", "claude-opus-5-5", greek_tok + ctx_overhead + prompt_fixed + memory_tok, eng_tok + table_tok + THINK["translate"] * len(units))
    add("backtranslation_A+B", "claude-sonnet-5-5", 2 * (eng_tok + 300 * len(units)), 2 * greek_tok + THINK["backtranslate"] * 2 * len(units))
    add("judge_c", "claude-sonnet-5-5", judge_items * 650, judge_items * 20 + THINK["judge_group"] * judge_groups)
    est["total_usd"] = est["total_usd_direct"]
    (out / "cost_estimate.json").write_text(json.dumps(est, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="adversus-lycum")
    ap.add_argument("--estimate-only", action="store_true", help="rewrite cost_estimate.json from the existing units.jsonl / targets.csv")
    a = ap.parse_args()
    w = WORKS[a.work]
    out = out_dir(a.work)
    if a.estimate_only:
        units = [json.loads(l) for l in (out / "units.jsonl").open(encoding="utf-8") if l.strip()]
        targets = list(csv.DictReader((out / "targets.csv").open(encoding="utf-8")))
        write_estimate(out, units, targets)
        print((out / "cost_estimate.json").read_text(encoding="utf-8"))
        return
    xml = GDM / "data" / "raw_xml" / f"{w['stem']}.xml"
    lem_path = GDM / "data" / "lemmatized" / w["lemmatized_dir"] / f"{w['stem']}.jsonl"
    odycy = [json.loads(l) for l in lem_path.open(encoding="utf-8") if l.strip()]

    toks = tei_tokens(xml)
    words = [t for t in toks if not t.get("pb")]
    # --- align TEI words to the odyCy stream (which dropped all-caps tokens and expanded crasis)
    pairs, loss = align_surfaces([strip_punct(t["surface"]) for t in words], [strip_punct(t["surface"]) for t in odycy], window=12)
    tei2ody = {i: j for i, j in pairs}
    for i, t in enumerate(words):
        j = tei2ody.get(i)
        t["ody_i"] = j
        t["lemma"] = nfc(odycy[j]["lemma"]) if j is not None else ""
        t["pos"] = odycy[j]["pos"] if j is not None else ""

    # --- unit boundaries: at each page break, snap back to the last sentence end since the previous boundary
    n = len(toks)
    is_end = [(not t.get("pb")) and t["surface"].endswith(SENTENCE_END) for t in toks]
    boundaries = [0]
    for i, t in enumerate(toks):
        if t.get("pb") and i > 0:
            j = i - 1
            while j > boundaries[-1] and not is_end[j]:
                j -= 1
            cut = j + 1 if j > boundaries[-1] else i
            if cut > boundaries[-1]:
                boundaries.append(cut)
    boundaries.append(n)
    # merge a unit shorter than 25 words into the previous one (a page break right after a sentence end)
    merged = [boundaries[0]]
    for b in boundaries[1:]:
        if b - merged[-1] < 25 and len(merged) > 1 and b != n:
            continue
        merged.append(b)
    boundaries = merged
    # a trailing segment with no words (the text ends at a page break, as De humero does at [423]) joins the previous unit
    if len(boundaries) > 2 and not any(not t.get("pb") for t in toks[boundaries[-2]:boundaries[-1]]):
        del boundaries[-2]

    # --- punch list, tiers, four-way
    punch = {nfc(r["lemma"]): r["lsj_tier"] for r in csv.DictReader((GDM / "outputs" / "punch_list.csv").open(encoding="utf-8"))}
    v3 = {nfc(r["lemma"]): r["tier_v3"] for r in csv.DictReader((GDM / "outputs" / "phase3" / "punch_list_v3.csv").open(encoding="utf-8"))}
    fourway, whole_freq = {}, {}
    for r in csv.DictReader((GDM / "outputs" / "four_way_classification.csv").open(encoding="utf-8")):
        fourway[nfc(r["lemma"])] = r["quadrant"]
        whole_freq[nfc(r["lemma"])] = int(r.get("wholegalen_raw") or 0)

    from dilemma import Dilemma  # type: ignore

    dil = Dilemma(lang="grc", convention="lsj")
    memo: dict[str, str] = {}

    def dlem(surface: str) -> str:
        s = strip_punct(surface)
        if s not in memo:
            try:
                memo[s] = nfc(dil.lemmatize(s, guess=True) or "")
            except Exception:
                memo[s] = ""
        return memo[s]

    units, targets = [], []
    for k in range(len(boundaries) - 1):
        seg = toks[boundaries[k]:boundaries[k + 1]]
        wds = [t for t in seg if not t.get("pb")]
        pages = sorted({t["page"] for t in seg if t["page"]}, key=int)
        chapters = sorted({t["chapter"] for t in seg if t["chapter"]}, key=chapter_key)
        books = sorted({t.get("book") for t in seg if t.get("book")}, key=int)
        uid = f"K{w['kuhn_vol_short']}.{pages[0]}" + (f"-{pages[-1]}" if len(pages) > 1 else "")
        while any(u["unit_id"] == uid for u in units):
            uid += "x"
        display = " ".join(t["surface"] for t in seg)
        plain = " ".join(t["surface"] for t in wds)
        n_tok = len(wds)
        punch_hits = [t for t in wds if t["pos"] in TARGET_POS and t["lemma"] in punch]
        tiers = Counter(punch[t["lemma"]] for t in punch_hits)
        # targets: every punch-list NOUN/ADJ token, then four-way genuinely_hard tokens rarest-first
        # (whole-Galen raw frequency), distinct lemmas within the unit, capped at TARGET_CAP per unit
        cands = []
        for j, t in enumerate(wds):
            if t["pos"] not in TARGET_POS:
                continue
            cls = []
            if t["lemma"] in punch:
                cls.append(f"punch:{punch[t['lemma']]}")
            if fourway.get(t["lemma"]) == "genuinely_hard":
                cls.append("fourway:genuinely_hard")
            if t["head"] or dlem(t["surface"])[:1].isupper():  # title line; proper names (Dilemma capitalises them)
                continue
            if cls:
                cands.append((0 if t["lemma"] in punch else 1, whole_freq.get(t["lemma"], 10**9), j, t, cls))
        cands.sort(key=lambda c: (c[0], c[1], c[2]))
        tgt_rows, seen = [], set()
        for _, _, j, t, cls in cands:
            if t["lemma"] in seen or len(tgt_rows) >= TARGET_CAP:
                continue
            seen.add(t["lemma"])
            tgt_rows.append({"unit_id": uid, "target_no": j, "surface": t["surface"], "surface_clean": strip_punct(t["surface"]),
                             "odycy_lemma": t["lemma"], "dilemma_lemma": dlem(t["surface"]), "pos": t["pos"],
                             "punch_tier": punch.get(t["lemma"], ""), "tier_v3": v3.get(t["lemma"], ""), "fourway": fourway.get(t["lemma"], ""),
                             "class": "+".join(cls), "page": t["page"]})
        tgt_rows.sort(key=lambda r: r["target_no"])
        targets += tgt_rows
        ody_idx = [t["ody_i"] for t in wds if t["ody_i"] is not None]
        units.append({
            "unit_id": uid, "work": a.work, "urn": w["urn"], "kuhn_vol": w["kuhn_vol"], "pages": pages, "books": books,
            "locus": f"K. {w['kuhn_vol']} {pages[0]}" + (f"–{pages[-1]}" if len(pages) > 1 else ""),
            "chapters": chapters, "n_tokens": n_tok, "n_words_for_cost": n_tok,
            "greek": display, "greek_plain": plain,
            "odycy_start": min(ody_idx) if ody_idx else None, "odycy_end": max(ody_idx) if ody_idx else None,
            "odycy_aligned_share": round(len(ody_idx) / n_tok, 3) if n_tok else 0,
            "punch_density_per100": round(100 * len(punch_hits) / n_tok, 2) if n_tok else 0.0,
            "n_punch_thin": tiers.get("thin", 0), "n_punch_absent": tiers.get("absent", 0),
            "n_content_tokens": sum(1 for t in wds if t["pos"] in CONTENT_POS),
            "n_targets": len(tgt_rows), "has_head": any(t["head"] for t in wds),
        })
    if w.get("books"):   # cycle 4: a draft of some books only (In Hipp. De victu acutorum II-IV)
        keep = {u["unit_id"] for u in units if u["books"] and set(u["books"]) <= set(w["books"])}
        units = [u for u in units if u["unit_id"] in keep]
        targets = [r for r in targets if r["unit_id"] in keep]
    # density terciles within the work
    dens = sorted(u["punch_density_per100"] for u in units)
    t1, t2 = dens[len(dens) // 3], dens[2 * len(dens) // 3]
    for u in units:
        u["difficulty_tier"] = "low" if u["punch_density_per100"] <= t1 else ("mid" if u["punch_density_per100"] <= t2 else "high")

    write_jsonl(out / "units.jsonl", units)
    with (out / "targets.csv").open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(targets[0].keys()), lineterminator="\n")
        wr.writeheader()
        wr.writerows(targets)

    write_estimate(out, units, targets)

    meta = {"work": a.work, "urn": w["urn"], "source": w["source_note"], "n_units": len(units), "n_tei_words": len(words), "n_odycy_tokens": len(odycy),
            "alignment_loss": loss, "n_targets": len(targets), "targets_by_class": dict(Counter(t["class"] for t in targets)),
            "density_terciles": [t1, t2], "units_per_tier": dict(Counter(u["difficulty_tier"] for u in units)),
            "n_books": len({b for u in units for b in u["books"]}), "n_chapters": len({c for u in units for c in u["chapters"]}),
            "pages_per_unit": dict(Counter(len(u["pages"]) for u in units)), "dilemma_version": __import__("dilemma").__version__}
    (out / "units_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=1, ensure_ascii=False))
    print((out / "cost_estimate.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
