"""Galen First Drafts v0/v0.2, stage 3: sentence alignment and the term table (spec: firstdrafts_v0_spec.md).

Inputs (outputs/firstdrafts/<slug>/): units.jsonl, targets.csv, renderings_fable-5-1.jsonl,
renderings_opus-5-5.jsonl, lsj_entries.json (lsj_index.py).

Sentence alignment per rendering: the Greek of a unit is split at sentence ends (full stop, question
mark); the English at [.!?;] followed by a space and a capital. Bracketed page markers [NNN] are hard
anchors: when the English carries the same markers as the Greek, each inter-marker segment is aligned on
its own. Inside a segment a Gale–Church-style dynamic programme over 1:1, 1:2, 2:1, 1:0 and 0:1 beads on
character lengths (ratio = segment English chars / Greek chars) gives the beads.

Term table: one row per target with Dilemma lemma, odyCy lemma, POS, punch tier, v3 tier, four-way
quadrant, LSJ entry (id, key, headword, senses), the English each rendering reported for it (and its
y/n uncertainty flag), both renderings normalised with pipeline/mt2026/score_consistency.norm, the
agreement verdict, the Greek sentence carrying the target and the aligned English sentence(s) of A and B.

Writes alignment.json, term_table.csv, align_meta.json. Deterministic; no model involved.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter

from common import PIPE, SENTENCE_END, lemma_key_fn, marker_re, nfc, out_dir, read_jsonl, strip_punct, work_config

sys.path.insert(0, str(PIPE / "mt2026"))
from score_consistency import norm  # noqa: E402

from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

RENDERINGS = {"A": "fable-5-1", "B": "opus-5-5"}
MARK = re.compile(r"\[(\d+)\]")


def galen_end(t: str) -> bool:
    return t.endswith(SENTENCE_END)


def split_greek(display: str, mark=MARK, is_end=galen_end) -> list[dict]:
    """Sentences of the display source text; each keeps its marker-free token span (start, end) for target lookup.
    Galen: split at '.' and ';' (the Greek question mark). A config work: its front end's sentence-end rule (Latin:
    '.', '?', '!' only, never ';', with closing quotes stripped and abbreviations excluded)."""
    toks = display.split()
    sents, cur, start_plain, n_plain = [], [], 0, 0
    for t in toks:
        cur.append(t)
        if not mark.fullmatch(t):
            n_plain += 1
            if is_end(t):
                sents.append({"text": " ".join(cur), "start": start_plain, "end": n_plain})
                cur, start_plain = [], n_plain
    if cur:
        sents.append({"text": " ".join(cur), "start": start_plain, "end": n_plain})
    return sents


def split_english(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[\.\?\!;])\s+(?=[A-Z\[“\"'(])", text)
    return [p.strip() for p in parts if p.strip()]


def segments(items: list[str], key=lambda s: s, mark=MARK) -> list[tuple[list[str], list[str]]]:
    """Split a sentence list into (markers_seen, sentences) segments at page markers (a marker starts a new segment)."""
    segs, cur, marks = [], [], []
    for s in items:
        ms = mark.findall(key(s))
        if ms and cur:
            segs.append((marks, cur))
            cur, marks = [], []
        marks = marks + ms
        cur.append(s)
    segs.append((marks, cur))
    return segs


def gale_church(g: list[str], e: list[str], mark=MARK) -> list[tuple[list[int], list[int]]]:
    """Beads over sentence index lists; cost = squared normalised length difference, plus a penalty per non-1:1 bead."""
    lg = [len(mark.sub("", s)) for s in g]
    le = [len(mark.sub("", s)) for s in e]
    r = (sum(le) / sum(lg)) if sum(lg) else 1.0
    n, m = len(g), len(e)
    INF = float("inf")
    best = [[INF] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0

    def cost(gi: list[int], ei: list[int]) -> float:
        a = sum(lg[i] for i in gi) * r
        b = sum(le[j] for j in ei)
        if a + b == 0:
            return 0.0
        pen = {(1, 1): 0.0, (1, 2): 0.6, (2, 1): 0.6, (1, 0): 2.5, (0, 1): 2.5}[(len(gi), len(ei))]
        return ((a - b) / ((a + b) / 2)) ** 2 + pen

    for i in range(n + 1):
        for j in range(m + 1):
            if best[i][j] == INF:
                continue
            for di, dj in ((1, 1), (1, 2), (2, 1), (1, 0), (0, 1)):
                if i + di <= n and j + dj <= m:
                    c = best[i][j] + cost(list(range(i, i + di)), list(range(j, j + dj)))
                    if c < best[i + di][j + dj]:
                        best[i + di][j + dj] = c
                        back[i + di][j + dj] = (di, dj)
    beads, i, j = [], n, m
    while (i, j) != (0, 0):
        di, dj = back[i][j]
        beads.append((list(range(i - di, i)), list(range(j - dj, j))))
        i, j = i - di, j - dj
    return beads[::-1]


def align_unit(greek_display: str, english: str, mark=MARK, is_end=galen_end) -> tuple[list[dict], dict]:
    gs = split_greek(greek_display, mark, is_end)
    es = split_english(english)
    g_marks = mark.findall(greek_display)
    e_marks = mark.findall(english or "")
    anchored = bool(g_marks) and g_marks == e_marks
    beads_out = []
    if anchored:
        gseg = segments([s["text"] for s in gs], mark=mark)
        eseg = segments(es, mark=mark)
        if len(gseg) != len(eseg):
            anchored = False
    if anchored:
        goff = eoff = 0
        for (_, gl), (_, el) in zip(gseg, eseg):
            for gi, ei in gale_church(gl, el, mark):
                beads_out.append({"g": [goff + x for x in gi], "e": [eoff + y for y in ei]})
            goff += len(gl)
            eoff += len(el)
    else:
        for gi, ei in gale_church([s["text"] for s in gs], es, mark):
            beads_out.append({"g": gi, "e": ei})
    stats = {"n_greek_sentences": len(gs), "n_english_sentences": len(es), "markers_match": g_marks == e_marks, "anchored": anchored,
             "beads": Counter(f"{len(b['g'])}:{len(b['e'])}" for b in beads_out)}
    for b in beads_out:
        b["greek"] = " ".join(gs[i]["text"] for i in b["g"])
        b["english"] = " ".join(es[j] for j in b["e"])
    return beads_out, {"sentences": gs, "english_sentences": es, **stats}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="adversus-lycum")
    a = ap.parse_args()
    out = out_dir(a.work)
    work = work_config(a.work)
    if work["galen"]:
        mark, is_end, lkey = MARK, galen_end, lemma_to_lookup_key
    else:
        from generic import sentence_end_fn  # noqa: E402

        mark, is_end, lkey = re.compile(marker_re(work)), sentence_end_fn(work["unit"]), lemma_key_fn(work["lang"])
    units = read_jsonl(out / "units.jsonl")
    targets = list(csv.DictReader((out / "targets.csv").open(encoding="utf-8")))
    lsj = json.loads((out / "lsj_entries.json").read_text(encoding="utf-8")) if (out / "lsj_entries.json").exists() else {}
    rend = {}
    for tag, short in RENDERINGS.items():
        rend[tag] = {r["unit_id"]: r for r in read_jsonl(out / f"renderings_{short}.jsonl")}

    alignment, meta = {}, {"units": len(units), "per_rendering": {}}
    for tag in RENDERINGS:
        st = Counter()
        alignment_tag = {}
        for u in units:
            r = rend[tag].get(u["unit_id"])
            eng = (r or {}).get("response", {}) or {}
            eng = eng.get("translation", "") if isinstance(eng, dict) else ""
            beads, info = align_unit(u["greek"], eng, mark, is_end)
            alignment_tag[u["unit_id"]] = {"beads": beads, "greek_sentences": [s["text"] for s in info["sentences"]], "english_sentences": info["english_sentences"],
                                           "sentence_spans": [[s["start"], s["end"]] for s in info["sentences"]], "anchored": info["anchored"], "markers_match": info["markers_match"]}
            st["units_with_translation"] += bool(eng)
            st["anchored"] += info["anchored"]
            st["markers_match"] += info["markers_match"]
            for k, v in info["beads"].items():
                st[f"bead_{k}"] += v
        alignment[tag] = alignment_tag
        meta["per_rendering"][tag] = dict(st)
    (out / "alignment.json").write_text(json.dumps(alignment, ensure_ascii=False), encoding="utf-8")

    # --- term table
    rows = []
    prior: dict[str, dict[str, set]] = {tag: {} for tag in RENDERINGS}
    for t in targets:
        uid, tno = t["unit_id"], int(t["target_no"])
        row = {k: t[k] for k in ("unit_id", "target_no", "surface", "dilemma_lemma", "odycy_lemma", "pos", "punch_tier", "tier_v3", "fourway", "class", "page")}
        ent = lsj.get(lkey(t["dilemma_lemma"])) or lsj.get(lkey(t["odycy_lemma"])) or {}
        row.update({"lsj_entry_id": ent.get("lsj_entry_id", ""), "lsj_key": ent.get("lsj_key", ""), "lsj_headword": ent.get("lsj_headword", ""),
                    "lsj_sense_count": ent.get("lsj_sense_count", ""), "lsj_entry_text": ent.get("lsj_entry_text", ""),
                    "lsj_first_sense_gloss": ent.get("lsj_first_sense_gloss", "")})
        # Greek sentence holding the target
        al = alignment["A"][uid]
        gsent, gidx = "", None
        for i, (s, e) in enumerate(al["sentence_spans"]):
            if s <= tno < e:
                gsent, gidx = al["greek_sentences"][i], i
                break
        row["greek_sentence"] = gsent
        for tag in RENDERINGS:
            r = rend[tag].get(uid)
            body = (r or {}).get("response") or {}
            rr = next((x for x in body.get("renderings", []) if isinstance(x, dict) and x.get("target_no") == tno), None) if isinstance(body, dict) else None
            row[f"rendering_{tag}"] = (rr or {}).get("english", "")
            row[f"uncertain_{tag}"] = (rr or {}).get("uncertain", "")
            row[f"norm_{tag}"] = norm(row[f"rendering_{tag}"])
            es = ""
            if gidx is not None:
                for b in alignment[tag][uid]["beads"]:
                    if gidx in b["g"]:
                        es = b["english"]
                        break
            row[f"english_sentence_{tag}"] = es
        both = bool(row["rendering_A"]) and bool(row["rendering_B"])
        row["agree"] = "" if not both else ("y" if row["norm_A"] == row["norm_B"] else "n")
        # v0.2 memory consistency: does this rendering repeat one of the same model's earlier renderings of the lemma
        # (text order; "" when the lemma has no earlier rendering by that model)
        lem = t["dilemma_lemma"] or t["odycy_lemma"]
        for tag in RENDERINGS:
            seen = prior[tag].get(lem)
            if not row[f"norm_{tag}"]:
                row[f"memory_consistent_{tag}"] = ""
            elif seen is None:
                row[f"memory_consistent_{tag}"] = ""
            else:
                row[f"memory_consistent_{tag}"] = "y" if row[f"norm_{tag}"] in seen else "n"
            if row[f"norm_{tag}"]:
                prior[tag].setdefault(lem, set()).add(row[f"norm_{tag}"])
        rows.append(row)
    with (out / "term_table.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    meta["term_table"] = {"rows": len(rows), "with_lsj_entry": sum(1 for r in rows if r["lsj_entry_id"]), "both_rendered": sum(1 for r in rows if r["agree"]),
                          "agree": sum(1 for r in rows if r["agree"] == "y"), "disagree": sum(1 for r in rows if r["agree"] == "n"),
                          "uncertain_A": sum(1 for r in rows if r["uncertain_A"] == "y"), "uncertain_B": sum(1 for r in rows if r["uncertain_B"] == "y")}
    (out / "align_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
