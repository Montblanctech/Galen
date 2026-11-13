"""Galen First Drafts v0.2, stage 4: the pre-registered machine checks (spec: firstdrafts_v02_spec.md; v0 spec
firstdrafts_v0_spec.md for Adversus Lycum).

  (a) back-translation agreement   build-bt -> api-bt (or model session + ingest-bt) -> score
  (b) rendering agreement A vs B   from term_table.csv (align.py) -> score
  (c) LSJ-anchored salted judge    build-judge (key OUTSIDE the repo; v0.2: anchors validated, whole LSJ entries,
                                   items grouped 10 per request) -> api-judge (or session + ingest-judge) -> score
  (d) reference agreement          calibration units only (reference/calibration_map.json): term-level agreement of
                                   each rendering with the CC BY reference translation; v0.2, reported beside a-c
  memory consistency               informational: does a rendering repeat the model's own earlier rendering of the lemma

Thresholds are the spec's and are repeated in THRESHOLDS below; `score` applies them, writes checks.json (per unit:
a, b, c, d, verdict; summary with Wilson intervals) and copies the judge key beside the results as
judge_key_PUBLISHED_AFTER_SCORING.csv. Report only: nothing is patched. Nothing calls a model unless an api-*
subcommand is given explicitly.

  python checks.py build-bt      --work <slug>
  python checks.py api-bt        --work <slug> --rendering A [--budget USD] [--mode direct|batch] [--subset calibration]
  python checks.py ingest-bt     --work <slug> --rendering A --responses <path> ...
  python checks.py build-judge   --work <slug> --key-out <path outside repo> [--seed 20261109] [--subset calibration]
  python checks.py api-judge     --work <slug> [--budget USD] [--mode direct|batch]
  python checks.py ingest-judge  --work <slug> --responses <path> ...
  python checks.py score         --work <slug> [--key <path>] [--subset calibration]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from common import GDM, LANG, LEXICA, PIPE, lemma_key_fn, marker_re, nfc, out_dir, read_jsonl, sha256, strip_punct, work_config, write_jsonl

sys.path.insert(0, str(PIPE / "mt2026"))
from score_consistency import STOP, norm  # noqa: E402

from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

THRESHOLDS = {
    "a_term_recall_min": 0.50, "a_content_recall_min_when_no_targets": 0.40,
    "b_agreement_min": 0.70,
    "c_in_range_share_min": 0.80, "c_out_of_range_max": 2, "c_gate": "20/20 controls (10 validated anchors in_range, 10 plants out_of_range)",
    "d_expected_min": 0.60, "d_calibration_halt_below": 0.40,
    "unit_fail_rule": "fails two of three checks a-c (n/a counts neither way); d and memory consistency are reported, never part of the verdict",
}
RENDERINGS = {"A": "fable-5-1", "B": "opus-5-5"}
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
MARK = re.compile(r"\s*\[\d+\]\s*")
JUDGE_GROUP = 10

def bt_system(author: str, lang_name: str, style: str, term_word: str, key: str, src: str) -> str:
    """Back-translation system prompt; Galen's values give the cycle 1-4 prompt exactly."""
    return (f"Translate the English passage into {lang_name} prose of the kind {author} writes ({style}). "
            f"Keep technical terms technical; render each term with the standard {term_word} word. Do not add notes. "
            'Answer with one JSON object and nothing else: {"' + key + '": "<the ' + src + '>"}.')


def judge_system(src: str, lex_short: str, lex_full: str) -> str:
    """Judge system prompt; Galen's values (Greek, LSJ) give the cycle 1-4 prompt exactly."""
    return (f"You are checking whether an English rendering of one {src} word falls within the range of senses that the {lex_full} entry "
            f"for that word gives. For every item you see the {src} sentence, the target word as it appears, its lemma, the complete {lex_short} entry text (plain text) "
            "and one English rendering taken from a translation of the sentence. Answer in_range if the English is a translation equivalent covered "
            f"by some sense in the entry in this context ({lex_short}'s exact wording is not required; a cognate, a contextual equivalent or an idiomatic phrase counts "
            "when the entry's senses cover it); out_of_range if it corresponds to none of the entry's senses; unsure if you cannot tell from what is shown. "
            "Some items are quality-control items; you are not told which; judge every item on its merits. "
            'Answer for every item with one JSON object per line and nothing else: {"item_id": "<id>", "verdict": "in_range|out_of_range|unsure", "note": "<at most 15 words>"}.')


BT_SYSTEM = bt_system("Galen", "Ancient Greek", "Attic-Koine, 2nd century AD", "ancient Greek", "greek", "Greek")
JUDGE_SYSTEM = judge_system("Greek", "LSJ", "LSJ (Liddell-Scott-Jones)")


def is_galen(work: dict | None) -> bool:
    return work is None or work.get("galen", True)


def bt_system_for(work: dict | None) -> str:
    if is_galen(work):
        return BT_SYSTEM
    L = LANG[work["lang"]]
    return bt_system(work["author"], L["name"], work["bt_style"], L["term_word"], L["bt_key"], L["adj"])


def judge_system_for(work: dict | None) -> str:
    if is_galen(work):
        return JUDGE_SYSTEM
    lx = LEXICA[work["lexicon"]["name"]]
    return judge_system(LANG[work["lang"]]["adj"], lx["short"], lx["full"])


def bt_key(work: dict | None) -> str:
    return "greek" if is_galen(work) else LANG[work["lang"]]["bt_key"]


def mark_re(work: dict | None):
    return MARK if is_galen(work) else re.compile(r"\s*" + marker_re(work) + r"\s*")


# anchor validation (v0.2): a gloss must be an English phrase of real words, not a fragment, label or function word
GLOSS_LABELS = {"in", "also", "the", "of", "to", "a", "an", "and", "or", "with", "for", "by", "at", "on", "as", "is", "are", "be", "later", "older", "form", "poet",
                "gen", "dat", "acc", "nom", "voc", "pl", "sg", "fem", "masc", "neut", "adv", "comp", "sup", "subst", "part", "pf", "aor", "fut", "impf", "pres", "mid", "pass",
                "act", "opt", "subj", "inf", "ind", "imper", "dual", "aeol", "dor", "ion", "att", "ep", "lacon", "boeot", "collat", "contr", "freq", "esp", "mostly", "only",
                "prob", "perh", "dub", "metaph", "abs", "trans", "intr", "causal", "cf", "v", "ib", "id", "sc", "al", "etc", "like", "see", "from", "into", "than", "very",
                "same", "used", "word", "forms", "i", "e", "ii", "iii", "iv", "sens", "obsc", "lit", "prop", "generally", "properly", "strictly", "written", "read"}


ARTICLES_PREPS = {"a", "an", "the", "of", "in", "to", "with", "for", "by", "at", "on", "from", "into"}


def valid_anchor_gloss(gloss: str) -> bool:
    """v0.2 anchor rule: lower-case Latin letters, hyphens, apostrophes and spaces only; one to six words; not opened
    by a grammatical label or abbreviation; at least one content word of three or more letters that is neither a
    label nor a stop word. 'also ος', 'in', 'older vέπος SIG 9' (cycle 1's defective anchors) all fail."""
    g = (gloss or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z\-' ]{1,60}", g):
        return False
    toks = [t for t in re.split(r"[\s\-]+", g) if t]
    if not toks or len(toks) > 6:
        return False
    if toks[0] in GLOSS_LABELS and toks[0] not in ARTICLES_PREPS:  # a grammatical label or abbreviation opens it: not a gloss
        return False
    content = [t for t in toks if len(t) >= 3 and t not in GLOSS_LABELS and t not in STOP]
    return len(content) >= 1


def gkey(tok: str) -> str:
    t = strip_punct(nfc(tok)).lower().replace("ς", "σ")
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 2), round(100 * (c + h), 2)]


def load_term_table(out: Path) -> list[dict]:
    with (out / "term_table.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def calibration_units(out: Path) -> list[str]:
    p = out / "reference" / "calibration_map.json"
    if not p.exists():
        return []
    return list(json.loads(p.read_text(encoding="utf-8")).get("calibration_unit_ids", []))


def restrict(units: list[dict], out: Path, subset: str | None) -> list[dict]:
    if subset != "calibration":
        return units
    cal = set(calibration_units(out))
    if not cal:
        sys.exit("--subset calibration: no reference/calibration_map.json")
    return [u for u in units if u["unit_id"] in cal]


# ---------------------------------------------------------------- (a)
def bt_requests(out: Path, units: list[dict], tag: str, work: dict | None = None) -> list[dict]:
    rend = {r["unit_id"]: r for r in read_jsonl(out / f"renderings_{RENDERINGS[tag]}.jsonl")}
    system, mk = bt_system_for(work), mark_re(work)
    reqs = []
    for u in units:
        body = (rend.get(u["unit_id"]) or {}).get("response") or {}
        eng = mk.sub(" ", body.get("translation", "")).strip() if isinstance(body, dict) else ""
        if not eng:
            continue
        user = f"Unit {u['unit_id']} ({u['locus']}). ENGLISH:\n{eng}"
        reqs.append({"unit_id": u["unit_id"], "rendering": tag, "system": system, "user": user, "prompt_sha256": sha256(system + "\n\n" + user)})
    return reqs


def cmd_build_bt(slug: str, subset: str | None) -> None:
    out = out_dir(slug)
    units = restrict(read_jsonl(out / "units.jsonl"), out, subset)
    work = work_config(slug)
    for tag in RENDERINGS:
        reqs = bt_requests(out, units, tag, work)
        write_jsonl(out / f"bt_requests_{tag}.jsonl", reqs)
        print(tag, len(reqs), "back-translation requests")


def cmd_api_bt(slug: str, tag: str, a) -> None:
    from api_backend import run_stage

    out = out_dir(slug)
    units = restrict(read_jsonl(out / "units.jsonl"), out, a.subset)
    reqs = {r["unit_id"]: r for r in bt_requests(out, units, tag, work_config(slug))}
    if a.dry_run:
        from api_backend import dry_run_stage

        dry_run_stage(stage=f"backtranslate_{tag}", ids=list(reqs), make_request=lambda i: (reqs[i]["system"], reqs[i]["user"], {"rendering": tag}), out_dir=out, limit=a.limit)
        return
    write_jsonl(out / f"bt_requests_{tag}.jsonl", list(reqs.values()))
    est = None
    cp = out / "cost_estimate.json"
    if cp.exists():
        ce = json.loads(cp.read_text(encoding="utf-8"))
        item = ce.get("items", {}).get("backtranslation_A+B")
        if item:
            est = item["usd"] / max(1, 2 * ce["n_units"]) * (0.5 if a.mode == "batch" else 1.0)
    run_stage(stage=f"backtranslate_{tag}", work=slug, model="claude-sonnet-5-5", ids=list(reqs), make_request=lambda i: (reqs[i]["system"], reqs[i]["user"], {"rendering": tag}),
              out_path=out / f"backtranslation_{tag}.jsonl", usage_path=out / "usage.jsonl", id_field="unit_id", budget=a.budget, mode=a.mode,
              packet_size=a.packet_size or (16 if a.mode == "direct" else 100), workers=a.workers, max_tokens=a.max_tokens, effort=a.effort, est_usd_per_call=est, parse="json", limit=a.limit)


def cmd_ingest_bt(slug: str, tag: str, paths: list[str]) -> None:
    out = out_dir(slug)
    reqs = {r["unit_id"]: r for r in read_jsonl(out / f"bt_requests_{tag}.jsonl")}
    k = bt_key(work_config(slug))
    rows = []
    for p in paths:
        for r in read_jsonl(Path(p)):
            q = reqs.get(r["unit_id"])
            if not q:
                continue
            body = r.get("response")
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except Exception:
                    body = {k: body}
            rows.append({"unit_id": r["unit_id"], "rendering": tag, "model": r.get("model", ""), "backend": "claude_code_session", "prompt_sha256": q["prompt_sha256"],
                         "started_utc": r.get("started_utc", ""), "finished_utc": r.get("finished_utc", ""), "timestamps_scope": "packet",
                         "response": body if isinstance(body, dict) else None, "ok": isinstance(body, dict) and bool(body.get(k))})
    rows.sort(key=lambda r: list(reqs).index(r["unit_id"]))
    write_jsonl(out / f"backtranslation_{tag}.jsonl", rows)
    print(tag, len(rows), "of", len(reqs), "back-translations ingested; missing", sorted(set(reqs) - {r["unit_id"] for r in rows}))


def bt_greek(row: dict, key: str = "greek") -> str:
    """The back-translated source text of a row (key 'greek' for Greek works, 'latin' for Latin)."""
    if row.get(key):
        return row[key]
    body = row.get("response")
    return body.get(key, "") if isinstance(body, dict) else ""


def score_a(out: Path, units: list[dict], targets_by_unit: dict, work: dict | None = None) -> dict:
    if not is_galen(work):
        return score_a_generic(out, units, targets_by_unit, work)
    from dilemma import Dilemma  # type: ignore

    dil = Dilemma(lang="grc", convention="lsj")
    memo: dict[str, str] = {}

    def key_of(word: str) -> str:
        w = strip_punct(word)
        if not w:
            return ""
        if w not in memo:
            try:
                memo[w] = lemma_to_lookup_key(nfc(dil.lemmatize(w, guess=True) or w))
            except Exception:
                memo[w] = lemma_to_lookup_key(w)
        return memo[w]

    work = work_config(units[0]["work"])
    ody = [json.loads(l) for l in (GDM / "data" / "lemmatized" / work["lemmatized_dir"] / f"{work['stem']}.jsonl").open(encoding="utf-8") if l.strip()]
    res = {}
    for tag in RENDERINGS:
        bt = {r["unit_id"]: bt_greek(r) for r in read_jsonl(out / f"backtranslation_{tag}.jsonl")}
        for u in units:
            g = bt.get(u["unit_id"], "")
            bt_keys = {key_of(w) for w in g.split()} | {lemma_to_lookup_key(strip_punct(w)) for w in g.split()}
            bt_keys.discard("")
            term_keys = {lemma_to_lookup_key(t["dilemma_lemma"] or t["odycy_lemma"]) for t in targets_by_unit.get(u["unit_id"], [])}
            term_keys.discard("")
            if u["odycy_start"] is not None:
                content = {lemma_to_lookup_key(nfc(t["lemma"])) for t in ody[u["odycy_start"]:u["odycy_end"] + 1] if t.get("pos") in CONTENT_POS}
            else:
                content = set()
            content.discard("")
            tr = len(term_keys & bt_keys) / len(term_keys) if term_keys else None
            cr = len(content & bt_keys) / len(content) if content else None
            if not g:
                verdict = "missing"
            elif term_keys:
                verdict = "pass" if tr >= THRESHOLDS["a_term_recall_min"] else "fail"
            else:
                verdict = "pass" if (cr or 0) >= THRESHOLDS["a_content_recall_min_when_no_targets"] else "fail"
            res[(u["unit_id"], tag)] = {"term_recall": None if tr is None else round(tr, 3), "n_terms": len(term_keys), "content_recall": None if cr is None else round(cr, 3),
                                         "n_content": len(content), "bt_tokens": len(g.split()), "verdict": verdict}
    return res


def tagger_stream(work: dict, out: Path) -> list[dict]:
    """The lemma + POS stream units.jsonl's odycy_start/odycy_end index: the frozen odyCy file of the config, or the
    tagged.jsonl the generic front end wrote beside the units."""
    t = work.get("tagger", {})
    p = GDM / t["path"] if t.get("name") == "odycy_precomputed" else out / "tagged.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def score_a_generic(out: Path, units: list[dict], targets_by_unit: dict, work: dict) -> dict:
    """Check (a) for a config work: the back-translation's words are lemmatized with the config's tagger family
    (Dilemma for grc, LatinCy via latin_tagger.py for lat), keyed with the language's comparison key; the unit's term
    keys are its targets' lexicon lemmas; content keys come from the tagger stream (tagged.jsonl). Same thresholds."""
    key = lemma_key_fn(work["lang"])
    bk = bt_key(work)
    bts = {tag: {r["unit_id"]: bt_greek(r, bk) for r in read_jsonl(out / f"backtranslation_{tag}.jsonl")} for tag in RENDERINGS}
    order = [(tag, u["unit_id"]) for tag in RENDERINGS for u in units]
    if work["lang"] == "lat":
        # LatinCy over each back-translation in context (as the source stream was tagged), plus the surface and
        # Collatinus' first lemma per word: the Latin twin of Galen's Dilemma lemma + surface. On an echo (the source
        # itself as the back-translation) this recovers 0.978 of the target terms (RECIPE.md, Vitruvius 3).
        from generic import latin_lemmas_in_context  # noqa: E402

        lem = latin_lemmas_in_context([bts[t].get(uid, "") for t, uid in order], work["tagger"])
        keysets = {o: {key(l) for _, l, _ in ws} | {key(w) for w, _, _ in ws} | {c.get("first", "") for _, _, c in ws} for o, ws in zip(order, lem)}
    else:
        from dilemma import Dilemma  # type: ignore

        dil = Dilemma(lang="grc", convention="lsj")
        memo: dict[str, str] = {}

        def dl(w: str) -> str:
            if w not in memo:
                try:
                    memo[w] = nfc(dil.lemmatize(w, guess=True) or w)
                except Exception:
                    memo[w] = w
            return memo[w]

        keysets = {}
        for o in order:
            ws = [strip_punct(w) for w in bts[o[0]].get(o[1], "").split() if strip_punct(w)]
            keysets[o] = {key(dl(w)) for w in ws} | {key(w) for w in ws}
    stream = tagger_stream(work, out)
    res = {}
    for tag in RENDERINGS:
        for u in units:
            g = bts[tag].get(u["unit_id"], "")
            bt_keys = keysets[(tag, u["unit_id"])]
            bt_keys.discard("")
            term_keys = {key(t["dilemma_lemma"] or t["odycy_lemma"]) for t in targets_by_unit.get(u["unit_id"], [])}
            term_keys.discard("")
            content = ({key(nfc(t["lemma"])) for t in stream[u["odycy_start"]:u["odycy_end"] + 1] if t.get("pos") in CONTENT_POS}
                       if u["odycy_start"] is not None else set())
            content.discard("")
            tr = len(term_keys & bt_keys) / len(term_keys) if term_keys else None
            cr = len(content & bt_keys) / len(content) if content else None
            if not g:
                verdict = "missing"
            elif term_keys:
                verdict = "pass" if tr >= THRESHOLDS["a_term_recall_min"] else "fail"
            else:
                verdict = "pass" if (cr or 0) >= THRESHOLDS["a_content_recall_min_when_no_targets"] else "fail"
            res[(u["unit_id"], tag)] = {"term_recall": None if tr is None else round(tr, 3), "n_terms": len(term_keys), "content_recall": None if cr is None else round(cr, 3),
                                         "n_content": len(content), "bt_tokens": len(g.split()), "verdict": verdict}
    return res


# ---------------------------------------------------------------- (c)
def judge_user(items: list[dict], work: dict | None = None) -> str:
    if is_galen(work):
        src, lex = "GREEK", "LSJ"
    else:
        src, lex = LANG[work["lang"]]["adj"].upper(), LEXICA[work["lexicon"]["name"]]["short"]
    parts = []
    for it in items:
        parts.append(f"ITEM {it['item_id']}\n{src} SENTENCE: {it['greek_sentence']}\nTARGET: {it['surface']} (lemma {it['lemma']}; {lex} headword {it['lsj_headword']})\n"
                     f"{lex.upper()} ENTRY: {it['lsj_entry']}\nENGLISH RENDERING: {it['english']}")
    return f"{len(items)} items. Answer with exactly {len(items)} JSON lines, one per item, in this order.\n\n" + "\n\n".join(parts)


def cmd_build_judge(slug: str, key_out: Path, seed: int, subset: str | None, anchors_rule: str = "v03") -> None:
    out = out_dir(slug)
    work = work_config(slug)
    jsys = judge_system_for(work)
    rows = load_term_table(out)
    if subset == "calibration":
        cal = set(calibration_units(out))
        rows = [r for r in rows if r["unit_id"] in cal]
    rng = random.Random(seed)
    items, key = [], []
    real = [r for r in rows if r["lsj_entry_id"] and r["greek_sentence"]]
    for r in real:
        for tag in RENDERINGS:
            if r[f"rendering_{tag}"]:
                iid = f"J{len(items) + 1:05d}"
                items.append({"item_id": iid, "greek_sentence": r["greek_sentence"], "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"],
                              "lsj_headword": r["lsj_headword"], "lsj_entry": r["lsj_entry_text"], "english": r[f"rendering_{tag}"]})
                key.append({"item_id": iid, "kind": "real", "unit_id": r["unit_id"], "target_no": r["target_no"], "rendering": tag, "expected": ""})
    # anchors. v0.2: LSJ first-sense gloss (fails in context: the judge is asked about THIS sentence, and the first
    # sense is often not Galen's; 7 of 9 cycle 1-3 gates failed on anchors). v0.3 (2026-11-10): a target whose two
    # independent renderings agree after normalisation, whose shared rendering is a valid English gloss, and at least
    # one of whose content words occurs in the target's own LSJ entry: right in context by two translators, attested
    # by the lexicon. The anchor item shows that shared rendering.
    if anchors_rule == "v02":
        cands = [r for r in real if valid_anchor_gloss(r.get("lsj_first_sense_gloss", ""))]
        n_invalid = sum(1 for r in real if r.get("lsj_first_sense_gloss") and not valid_anchor_gloss(r["lsj_first_sense_gloss"]))
    else:
        def v03_ok(r):
            a_, b_ = r.get("rendering_A") or "", r.get("rendering_B") or ""
            if not a_ or not b_ or norm(a_) != norm(b_) or not valid_anchor_gloss(a_.lower()):
                return False
            entry = set(norm(r.get("lsj_entry_text") or "").split())
            content = [w for w in norm(a_).split() if len(w) >= 3 and w not in STOP and w not in GLOSS_LABELS]
            return bool(content) and any(w in entry for w in content)
        cands = [r for r in real if v03_ok(r)]
        n_invalid = sum(1 for r in real if r.get("rendering_A") and r.get("rendering_B") and norm(r["rendering_A"]) == norm(r["rendering_B"]) and not v03_ok(r))
    rng.shuffle(cands)
    seen, anchors = set(), []
    for r in cands:
        if r["dilemma_lemma"] in seen:
            continue
        seen.add(r["dilemma_lemma"])
        anchors.append(r)
        if len(anchors) == 10:
            break
    for r in anchors:
        iid = f"J{len(items) + 1:05d}"
        items.append({"item_id": iid, "greek_sentence": r["greek_sentence"], "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"],
                      "lsj_headword": r["lsj_headword"], "lsj_entry": r["lsj_entry_text"],
                      "english": (r["lsj_first_sense_gloss"] if anchors_rule == "v02" else r["rendering_A"]).strip()})
        key.append({"item_id": iid, "kind": "anchor", "unit_id": r["unit_id"], "target_no": r["target_no"],
                    "rendering": "lsj_first_sense_gloss" if anchors_rule == "v02" else "A=B shared rendering, attested in the entry", "expected": "in_range"})
    # plants: a real target with the rendering of a different target (different LSJ entry, no shared normalised token with either rendering or the entry)
    plants, tries = [], 0
    pool = [r for r in real if r["rendering_A"]]
    while len(plants) < 10 and tries < 20000:
        tries += 1
        r, s = rng.sample(pool, 2)
        if r["lsj_entry_id"] == s["lsj_entry_id"] or r["dilemma_lemma"] in {p[0]["dilemma_lemma"] for p in plants}:
            continue
        wrong = s["rendering_A"]
        if not wrong or set(norm(wrong).split()) & (set(norm(r["rendering_A"]).split()) | set(norm(r["rendering_B"]).split()) | set(norm(r["lsj_entry_text"]).split())):
            continue
        plants.append((r, s, wrong))
    for r, s, wrong in plants:
        iid = f"J{len(items) + 1:05d}"
        items.append({"item_id": iid, "greek_sentence": r["greek_sentence"], "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"],
                      "lsj_headword": r["lsj_headword"], "lsj_entry": r["lsj_entry_text"], "english": wrong})
        key.append({"item_id": iid, "kind": "plant", "unit_id": r["unit_id"], "target_no": r["target_no"], "rendering": f"from {s['unit_id']}:{s['target_no']}", "expected": "out_of_range"})
    order = list(range(len(items)))
    rng.shuffle(order)
    items = [items[i] for i in order]
    pos = {it["item_id"]: n for n, it in enumerate(items)}
    key.sort(key=lambda k: pos[k["item_id"]])
    write_jsonl(out / "judge_sheet.jsonl", items)
    groups = []
    for g0 in range(0, len(items), JUDGE_GROUP):
        grp = items[g0:g0 + JUDGE_GROUP]
        user = judge_user(grp, work)
        groups.append({"group_id": f"G{g0 // JUDGE_GROUP + 1:05d}", "item_ids": [it["item_id"] for it in grp], "system": jsys, "user": user, "prompt_sha256": sha256(jsys + "\n\n" + user)})
    write_jsonl(out / "judge_requests.jsonl", groups)
    key_out.parent.mkdir(parents=True, exist_ok=True)
    with key_out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(key[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(key)
    meta = {"spec": "firstdrafts_v02_spec.md" if anchors_rule == "v02" else "firstdrafts_v03_judge_note.md", "anchor_rule": anchors_rule, "seed": seed, "subset": subset, "n_items": len(items), "n_real": sum(k["kind"] == "real" for k in key), "n_anchor": len(anchors), "n_plant": len(plants),
            "n_groups": len(groups), "group_size": JUDGE_GROUP, "anchor_candidates_valid": len(cands), "first_sense_glosses_rejected_by_validator": n_invalid,
            "lsj_entry_chars": {"min": min(len(it["lsj_entry"]) for it in items), "median": sorted(len(it["lsj_entry"]) for it in items)[len(items) // 2], "max": max(len(it["lsj_entry"]) for it in items)},
            "key": "outside the repository until scored"}
    (out / "judge_sheet_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    if len(anchors) < 10 or len(plants) < 10:
        sys.exit(f"could not build 10 anchors / 10 plants ({len(anchors)}/{len(plants)}): the gate needs 20 controls")


def answers_from_groups(out: Path, rows: list[dict], backend: str) -> list[dict]:
    sheet = {it["item_id"] for it in read_jsonl(out / "judge_sheet.jsonl")}
    ans, seen = [], set()
    for r in rows:
        objs = r.get("response") or []
        if isinstance(objs, dict):
            objs = [objs]
        for o in objs:
            iid = str(o.get("item_id", "")).strip()
            if iid in sheet and iid not in seen:
                v = (o.get("verdict") or "").strip().lower()
                ans.append({"item_id": iid, "verdict": v if v in {"in_range", "out_of_range", "unsure"} else "unsure", "note": o.get("note", ""), "model": r.get("model", ""),
                            "backend": backend, "group_id": r.get("group_id", ""), "finished_utc": r.get("finished_utc", "")})
                seen.add(iid)
    ans.sort(key=lambda r: r["item_id"])
    return ans


def cmd_api_judge(slug: str, a) -> None:
    from api_backend import run_stage

    out = out_dir(slug)
    work = work_config(slug)
    groups = {g["group_id"]: g for g in read_jsonl(out / "judge_requests.jsonl")}
    if a.dry_run:
        from api_backend import dry_run_stage

        dry_run_stage(stage="judge", ids=list(groups), make_request=lambda i: (groups[i]["system"], groups[i]["user"], {"item_ids": groups[i]["item_ids"]}), out_dir=out, limit=a.limit)
        return
    est = None
    cp = out / "cost_estimate.json"
    if cp.exists():
        ce = json.loads(cp.read_text(encoding="utf-8"))
        item = ce.get("items", {}).get("judge_c")
        if item:
            est = item["usd"] / max(1, len(groups)) * (0.5 if a.mode == "batch" else 1.0)
    run_stage(stage="judge", work=slug, model="claude-sonnet-5-5", ids=list(groups), make_request=lambda i: (groups[i]["system"], groups[i]["user"], {"item_ids": groups[i]["item_ids"]}),
              out_path=out / "judge_group_answers.jsonl", usage_path=out / "usage.jsonl", id_field="group_id", budget=a.budget, mode=a.mode,
              packet_size=a.packet_size or (16 if a.mode == "direct" else 100), workers=a.workers, max_tokens=a.max_tokens, effort=a.effort, est_usd_per_call=est, parse="jsonl", limit=a.limit)
    ans = answers_from_groups(out, read_jsonl(out / "judge_group_answers.jsonl"), "api" if a.mode == "direct" else "api_batch")
    items = {it["item_id"]: it for it in read_jsonl(out / "judge_sheet.jsonl")}
    missing = [i for i in items if i not in {r["item_id"] for r in ans}]
    if missing:   # v0.3: re-ask the unanswered items once, in groups of their own (cycle 2 lost 5 controls this way)
        re_groups = {}
        for g0 in range(0, len(missing), JUDGE_GROUP):
            grp = [items[i] for i in missing[g0:g0 + JUDGE_GROUP]]
            user = judge_user(grp, work)
            re_groups[f"R{g0 // JUDGE_GROUP + 1:05d}"] = {"system": judge_system_for(work), "user": user, "item_ids": [it["item_id"] for it in grp]}
        print(len(missing), "items unanswered; re-asking them in", len(re_groups), "groups")
        run_stage(stage="judge_reask", work=slug, model="claude-sonnet-5-5", ids=list(re_groups),
                  make_request=lambda i: (re_groups[i]["system"], re_groups[i]["user"], {"item_ids": re_groups[i]["item_ids"]}),
                  out_path=out / "judge_group_answers_reask.jsonl", usage_path=out / "usage.jsonl", id_field="group_id", budget=a.budget, mode=a.mode,
                  packet_size=a.packet_size or (16 if a.mode == "direct" else 100), workers=a.workers, max_tokens=a.max_tokens, effort=a.effort, est_usd_per_call=est, parse="jsonl", limit=a.limit)
        have = {r["item_id"] for r in ans}
        ans += [r for r in answers_from_groups(out, read_jsonl(out / "judge_group_answers_reask.jsonl"), "api" if a.mode == "direct" else "api_batch") if r["item_id"] not in have]
    write_jsonl(out / "judge_answers.jsonl", ans)
    print(len(ans), "of", len(items), "items judged; missing", len(set(items) - {r['item_id'] for r in ans}))


def cmd_ingest_judge(slug: str, paths: list[str]) -> None:
    out = out_dir(slug)
    sheet = {it["item_id"] for it in read_jsonl(out / "judge_sheet.jsonl")}
    rows, seen = [], set()
    for p in paths:
        for r in read_jsonl(Path(p)):
            if r.get("item_id") in sheet and r["item_id"] not in seen:
                v = (r.get("verdict") or "").strip().lower()
                rows.append({"item_id": r["item_id"], "verdict": v if v in {"in_range", "out_of_range", "unsure"} else "unsure", "note": r.get("note", ""), "model": r.get("model", ""), "backend": "claude_code_session"})
                seen.add(r["item_id"])
    rows.sort(key=lambda r: r["item_id"])
    write_jsonl(out / "judge_answers.jsonl", rows)
    print(len(rows), "of", len(sheet), "judged; missing", len(sheet - seen))


# ---------------------------------------------------------------- (d) reference agreement
def score_d(out: Path, tt: list[dict]) -> dict | None:
    cm_path = out / "reference" / "calibration_map.json"
    pj = out / "reference" / "passages.jsonl"
    if not cm_path.exists() or not pj.exists():
        return None
    passages = read_jsonl(pj)
    by_unit: dict[str, list[dict]] = defaultdict(list)
    for p in passages:
        ptoks = {gkey(t) for t in p["greek"].split() if gkey(t)}
        etoks = set(norm(p["english"]).split())
        for uid in p["unit_ids"]:
            by_unit[uid].append({"passage": p["passage"], "greek_tokens": ptoks, "english_tokens": etoks})
    res = {"n_passages": len(passages), "per_rendering": {}, "per_passage": {}, "items": []}
    for tag in RENDERINGS:
        n = k = 0
        for r in tt:
            ps = by_unit.get(r["unit_id"])
            if not ps or not r[f"rendering_{tag}"]:
                continue
            sk = gkey(r["surface"])
            hit = next((p for p in ps if sk in p["greek_tokens"]), None)
            if hit is None:
                continue  # target lies in the unit but outside the reference passage's lines
            rtoks = set(norm(r[f"rendering_{tag}"]).split())
            agree = bool(rtoks & hit["english_tokens"])
            n += 1
            k += agree
            r[f"ref_agree_{tag}"] = "y" if agree else "n"
            r["ref_passage"] = str(hit["passage"])
            pp = res["per_passage"].setdefault(str(hit["passage"]), {t: {"n": 0, "agree": 0} for t in RENDERINGS})
            pp[tag]["n"] += 1
            pp[tag]["agree"] += agree
            res["items"].append({"unit_id": r["unit_id"], "target_no": r["target_no"], "surface": r["surface"], "rendering": tag, "english": r[f"rendering_{tag}"], "agree": agree, "passage": hit["passage"]})
        res["per_rendering"][tag] = {"n": n, "agree": k, "pct": round(100 * k / n, 2) if n else None, "wilson95": wilson(k, n),
                                     "meets_expected_min": (k / n >= THRESHOLDS["d_expected_min"]) if n else None,
                                     "below_halt_line": (k / n < THRESHOLDS["d_calibration_halt_below"]) if n else None}
    res["rule"] = ("a rendering's target agrees with the reference when at least one normalised content token of the rendering occurs in the normalised "
                   "reference passage (score_consistency.norm on both: lower-case, stop words, singularisation, synonym fold); only targets whose Greek token "
                   "falls inside the passage's lines count; lenient by construction (passage-level), so the number is a floor on disagreement, not a ceiling")
    return res


def memory_consistency(tt: list[dict]) -> dict:
    out = {}
    for tag in RENDERINGS:
        n = k = 0
        for r in tt:
            v = r.get(f"memory_consistent_{tag}", "")
            if v in ("y", "n"):
                n += 1
                k += v == "y"
        out[tag] = {"n_with_prior": n, "consistent": k, "pct": round(100 * k / n, 2) if n else None}
    return out


# ---------------------------------------------------------------- score
def cmd_score(slug: str, key_path: Path | None, subset: str | None) -> None:
    out = out_dir(slug)
    units = restrict(read_jsonl(out / "units.jsonl"), out, subset)
    unit_ids = {u["unit_id"] for u in units}
    tt_all = load_term_table(out)
    tt = [r for r in tt_all if r["unit_id"] in unit_ids]
    targets_by_unit = defaultdict(list)
    for r in tt:
        targets_by_unit[r["unit_id"]].append(r)
    result = {"spec": "firstdrafts_v02_spec.md", "thresholds": THRESHOLDS, "work": slug, "subset": subset, "units": {}, "summary": {}}

    # (b)
    b = {}
    for u in units:
        rows = [r for r in targets_by_unit.get(u["unit_id"], []) if r["agree"]]
        if not rows:
            b[u["unit_id"]] = {"n": 0, "agree": 0, "rate": None, "verdict": "n/a"}
        else:
            k = sum(r["agree"] == "y" for r in rows)
            b[u["unit_id"]] = {"n": len(rows), "agree": k, "rate": round(k / len(rows), 3), "verdict": "pass" if k / len(rows) >= THRESHOLDS["b_agreement_min"] else "fail"}

    # (a)
    have_bt = all((out / f"backtranslation_{t}.jsonl").exists() for t in RENDERINGS)
    a_res = score_a(out, units, targets_by_unit, work_config(slug)) if have_bt else {}

    # (c)
    c = {u["unit_id"]: {"verdict": "not_run"} for u in units}
    gate = None
    if key_path and (out / "judge_answers.jsonl").exists():
        key = {k["item_id"]: k for k in csv.DictReader(key_path.open(encoding="utf-8"))}
        ans = {r["item_id"]: r for r in read_jsonl(out / "judge_answers.jsonl")}
        sheet = {it["item_id"]: it for it in read_jsonl(out / "judge_sheet.jsonl")}
        controls = [k for k in key.values() if k["kind"] != "real"]
        hits = sum(1 for k in controls if ans.get(k["item_id"], {}).get("verdict") == k["expected"])
        gate = {"controls": len(controls), "correct": hits, "passed": hits == len(controls) and len(controls) == 20,
                "misses": [{"item_id": k["item_id"], "kind": k["kind"], "expected": k["expected"], "got": ans.get(k["item_id"], {}).get("verdict", "missing"),
                            "english": sheet.get(k["item_id"], {}).get("english", "")} for k in controls if ans.get(k["item_id"], {}).get("verdict") != k["expected"]]}
        gate["defective_anchor_misses"] = sum(1 for m in gate["misses"] if m["kind"] == "anchor" and not valid_anchor_gloss(m["english"]))
        gate["note"] = "" if gate["passed"] else ("gate failed; " + ("all misses are anchors the validator should have rejected" if gate["defective_anchor_misses"] == len(gate["misses"]) else f"{len(gate['misses'])} control misses, {gate['defective_anchor_misses']} of them defective anchors"))
        per_unit = defaultdict(list)
        for k in key.values():
            if k["kind"] == "real" and k["unit_id"] in unit_ids:
                per_unit[k["unit_id"]].append(ans.get(k["item_id"], {}).get("verdict", "missing"))
                for r in targets_by_unit.get(k["unit_id"], []):
                    if r["target_no"] == k["target_no"]:
                        r[f"judge_{k['rendering']}"] = ans.get(k["item_id"], {}).get("verdict", "missing")
        for u in units:
            vs = per_unit.get(u["unit_id"], [])
            cnt = Counter(vs)
            share = (cnt["in_range"] / len(vs)) if vs else None
            explor = None if not vs else {"n": len(vs), "in_range": cnt["in_range"], "out_of_range": cnt["out_of_range"], "unsure": cnt["unsure"], "missing": cnt["missing"],
                                          "share_in_range": round(share, 3),
                                          "verdict": "pass" if share >= THRESHOLDS["c_in_range_share_min"] and cnt["out_of_range"] <= THRESHOLDS["c_out_of_range_max"] else "fail"}
            if not gate["passed"]:
                c[u["unit_id"]] = {"verdict": "judge_failed_gate", "n": len(vs), "exploratory_not_preregistered": explor}
            elif not vs:
                c[u["unit_id"]] = {"verdict": "n/a", "n": 0}
            else:
                c[u["unit_id"]] = explor
        shutil.copy(key_path, out / "judge_key_PUBLISHED_AFTER_SCORING.csv")

    # (d) and memory consistency (write back into the full term table)
    d = score_d(out, tt)
    mem = memory_consistency(tt)
    with (out / "term_table.csv").open("w", encoding="utf-8", newline="") as fh:
        extra = [f for f in ("judge_A", "judge_B", "ref_agree_A", "ref_agree_B", "ref_passage") if f not in tt_all[0]]
        fields = list(tt_all[0].keys()) + extra
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(tt_all)

    # combine
    fails = Counter()
    for u in units:
        uid = u["unit_id"]
        a_unit = {t: a_res.get((uid, t), {"verdict": "not_run"}) for t in RENDERINGS}
        a_vs = [a_unit[t]["verdict"] for t in RENDERINGS]
        a_verdict = "not_run" if "not_run" in a_vs else ("missing" if "missing" in a_vs else ("pass" if all(v == "pass" for v in a_vs) else "fail"))
        verdicts = [a_verdict, b[uid]["verdict"], c[uid]["verdict"]]
        n_fail = sum(v == "fail" for v in verdicts)
        unit_verdict = "fail" if n_fail >= 2 else ("pass" if sum(v == "pass" for v in verdicts) >= 2 else ("mixed" if n_fail == 1 else "insufficient"))
        fails[unit_verdict] += 1
        d_unit = None
        if d:
            rows = [r for r in targets_by_unit.get(uid, []) if r.get("ref_passage")]
            if rows:
                d_unit = {t: {"n": sum(1 for r in rows if r.get(f"ref_agree_{t}") in ("y", "n")), "agree": sum(1 for r in rows if r.get(f"ref_agree_{t}") == "y")} for t in RENDERINGS}
        result["units"][uid] = {"locus": u["locus"], "difficulty_tier": u["difficulty_tier"], "punch_density_per100": u["punch_density_per100"],
                                "a": {"verdict": a_verdict, **{t: a_unit[t] for t in RENDERINGS}}, "b": b[uid], "c": c[uid], "d": d_unit, "verdict": unit_verdict}

    def rate(name, key_fn):
        vs = [key_fn(x) for x in result["units"].values()]
        n = sum(v in ("pass", "fail") for v in vs)
        k = sum(v == "pass" for v in vs)
        return {"pass": k, "fail": n - k, "n_a_or_not_run": len(vs) - n, "pass_pct": round(100 * k / n, 1) if n else None, "wilson95": wilson(k, n)}

    result["summary"] = {
        "n_units": len(units), "unit_verdicts": dict(fails),
        "a": rate("a", lambda x: x["a"]["verdict"]), "b": rate("b", lambda x: x["b"]["verdict"]), "c": rate("c", lambda x: x["c"]["verdict"]),
        "b_term_level": {"n": sum(1 for r in tt if r["agree"]), "agree": sum(1 for r in tt if r["agree"] == "y"),
                         "pct": round(100 * sum(1 for r in tt if r["agree"] == "y") / max(1, sum(1 for r in tt if r["agree"])), 2),
                         "wilson95": wilson(sum(1 for r in tt if r["agree"] == "y"), sum(1 for r in tt if r["agree"]))},
        "b_by_class": {},
        "a_mean_term_recall": {t: round(sum(v["term_recall"] for (u, tag), v in a_res.items() if tag == t and v["term_recall"] is not None) / max(1, sum(1 for (u, tag), v in a_res.items() if tag == t and v["term_recall"] is not None)), 3) for t in RENDERINGS} if a_res else None,
        "a_mean_content_recall": {t: round(sum(v["content_recall"] for (u, tag), v in a_res.items() if tag == t and v["content_recall"] is not None) / max(1, sum(1 for (u, tag), v in a_res.items() if tag == t and v["content_recall"] is not None)), 3) for t in RENDERINGS} if a_res else None,
        "c_gate": gate,
        "c_exploratory_not_preregistered": (dict(Counter(v["exploratory_not_preregistered"]["verdict"] for v in c.values() if v.get("exploratory_not_preregistered")))
                                            if gate and not gate["passed"] else None),
        "c_item_level": {t: dict(Counter(r.get(f"judge_{t}", "") for r in tt if r.get(f"judge_{t}"))) for t in RENDERINGS} if gate else None,
        "d_reference_agreement": {k: v for k, v in d.items() if k != "items"} if d else None,
        "memory_consistency": mem,
        "uncertain_flags": {t: sum(1 for r in tt if r[f"uncertain_{t}"] == "y") for t in RENDERINGS},
    }
    for cls_name, pred in (("punch", lambda r: r["punch_tier"] != ""), ("fourway_only", lambda r: r["punch_tier"] == "")):
        rows = [r for r in tt if r["agree"] and pred(r)]
        k = sum(r["agree"] == "y" for r in rows)
        result["summary"]["b_by_class"][cls_name] = {"n": len(rows), "agree": k, "pct": round(100 * k / len(rows), 2) if rows else None, "wilson95": wilson(k, len(rows))}
    xs = [u["punch_density_per100"] for u in units if b[u["unit_id"]]["rate"] is not None]
    ys = [1 - b[u["unit_id"]]["rate"] for u in units if b[u["unit_id"]]["rate"] is not None]
    if len(xs) >= 5:
        def ranks(v):
            s = sorted(range(len(v)), key=lambda i: v[i])
            r = [0.0] * len(v)
            i = 0
            while i < len(s):
                j = i
                while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                    j += 1
                for k in range(i, j + 1):
                    r[s[k]] = (i + j) / 2 + 1
                i = j + 1
            return r
        rx, ry = ranks(xs), ranks(ys)
        mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
        num = sum((p - mx) * (q - my) for p, q in zip(rx, ry))
        den = math.sqrt(sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry))
        result["summary"]["density_vs_disagreement_spearman"] = {"rho": round(num / den, 3) if den else None, "n": len(xs)}
    if d:
        (out / "reference" / "reference_agreement_items.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in d["items"]), encoding="utf-8")
    name = "checks_calibration.json" if subset == "calibration" else "checks.json"
    (out / name).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    if d and subset == "calibration":
        halt = [t for t, v in d["per_rendering"].items() if v["below_halt_line"]]
        if halt:
            print(f"CALIBRATION HALT: rendering(s) {halt} below {THRESHOLDS['d_calibration_halt_below']} reference agreement; do not send the rest of the work before review")
            sys.exit(3)


def main() -> None:
    from api_backend import add_api_args

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build-bt", "api-bt", "ingest-bt", "build-judge", "api-judge", "ingest-judge", "score"])
    ap.add_argument("--work", default="adversus-lycum")
    ap.add_argument("--rendering", choices=list(RENDERINGS))
    ap.add_argument("--responses", action="append", default=[])
    ap.add_argument("--key-out", type=Path)
    ap.add_argument("--key", type=Path)
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--subset", choices=["calibration"], default=None)
    ap.add_argument("--anchors", choices=["v02", "v03"], default="v03", help="build-judge: anchor rule (v0.3 default, 2026-11-10)")
    add_api_args(ap)
    a = ap.parse_args()
    if a.dry_run and a.cmd not in ("api-bt", "api-judge"):
        sys.exit("--dry-run goes with api-bt or api-judge")
    if a.cmd == "build-bt":
        cmd_build_bt(a.work, a.subset)
    elif a.cmd == "api-bt":
        cmd_api_bt(a.work, a.rendering, a)
    elif a.cmd == "ingest-bt":
        cmd_ingest_bt(a.work, a.rendering, a.responses)
    elif a.cmd == "build-judge":
        cmd_build_judge(a.work, a.key_out, a.seed, a.subset, a.anchors)
    elif a.cmd == "api-judge":
        cmd_api_judge(a.work, a)
    elif a.cmd == "ingest-judge":
        cmd_ingest_judge(a.work, a.responses)
    else:
        cmd_score(a.work, a.key, a.subset)


if __name__ == "__main__":
    main()
