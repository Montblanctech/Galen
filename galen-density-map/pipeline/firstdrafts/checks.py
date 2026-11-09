"""Galen First Drafts v0, stage 4: the three pre-registered machine checks (spec: firstdrafts_v0_spec.md).

  (a) back-translation agreement   build-bt -> model session(s) -> ingest-bt -> score
  (b) rendering agreement A vs B   from term_table.csv (align.py) -> score
  (c) LSJ-anchored salted judge    build-judge (key OUTSIDE the repo) -> model session(s) -> ingest-judge -> score

Thresholds are the spec's and are repeated in THRESHOLDS below; `score` applies them, writes
checks.json (per unit: a, b, c, verdict; summary with Wilson intervals) and copies the judge key beside
the results as judge_key_PUBLISHED_AFTER_SCORING.csv. Report only: nothing is patched.

  python checks.py build-bt      --work adversus-lycum
  python checks.py ingest-bt     --work adversus-lycum --rendering A --responses <path> [--responses <path> ...]
  python checks.py build-judge   --work adversus-lycum --key-out <path outside repo> [--seed 20261109]
  python checks.py ingest-judge  --work adversus-lycum --responses <path> [--responses <path> ...]
  python checks.py score         --work adversus-lycum --key <path>
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
from collections import Counter, defaultdict
from pathlib import Path

from common import GDM, PIPE, WORKS, nfc, out_dir, read_jsonl, sha256, strip_punct, write_jsonl

sys.path.insert(0, str(PIPE / "mt2026"))
from demo_build import first_gloss  # noqa: E402
from score_consistency import norm  # noqa: E402

from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

THRESHOLDS = {
    "a_term_recall_min": 0.50, "a_content_recall_min_when_no_targets": 0.40,
    "b_agreement_min": 0.70,
    "c_in_range_share_min": 0.80, "c_out_of_range_max": 2, "c_gate": "20/20 controls",
    "unit_fail_rule": "fails two of three checks (n/a counts neither way)",
}
RENDERINGS = {"A": "fable-5-1", "B": "opus-5-5"}
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
MARK = re.compile(r"\s*\[\d+\]\s*")

BT_SYSTEM = ("Translate the English passage into Ancient Greek prose of the kind Galen writes (Attic-Koine, 2nd century AD). "
             "Keep technical terms technical; render each term with the standard ancient Greek word. Do not add notes. "
             'Answer with one JSON object and nothing else: {"greek": "<the Greek>"}.')

JUDGE_SYSTEM = ("You are checking whether an English rendering of one Greek word falls within the range of senses that the LSJ (Liddell-Scott-Jones) entry "
                "for that word gives. For every item you see the Greek sentence, the target word as it appears, its lemma, the LSJ entry text (plain text, may be "
                "truncated) and one English rendering taken from a translation of the sentence. Answer in_range if the English is a translation equivalent covered "
                "by some sense in the entry in this context (LSJ's exact wording is not required; a cognate, a contextual equivalent or an idiomatic phrase counts "
                "when the entry's senses cover it); out_of_range if it corresponds to none of the entry's senses; unsure if you cannot tell from what is shown. "
                "Some items are quality-control items; you are not told which; judge every item on its merits. "
                'Answer for every item with one JSON object per line: {"item_id": "<id>", "verdict": "in_range|out_of_range|unsure", "note": "<at most 15 words>"}.')


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


# ---------------------------------------------------------------- (a)
def cmd_build_bt(slug: str) -> None:
    out = out_dir(slug)
    units = read_jsonl(out / "units.jsonl")
    for tag, short in RENDERINGS.items():
        rend = {r["unit_id"]: r for r in read_jsonl(out / f"renderings_{short}.jsonl")}
        reqs = []
        for u in units:
            body = (rend.get(u["unit_id"]) or {}).get("response") or {}
            eng = MARK.sub(" ", body.get("translation", "")).strip() if isinstance(body, dict) else ""
            if not eng:
                continue
            user = f"Unit {u['unit_id']} ({u['locus']}). ENGLISH:\n{eng}"
            reqs.append({"unit_id": u["unit_id"], "rendering": tag, "system": BT_SYSTEM, "user": user, "prompt_sha256": sha256(BT_SYSTEM + "\n\n" + user)})
        write_jsonl(out / f"bt_requests_{tag}.jsonl", reqs)
        print(tag, len(reqs), "back-translation requests")


def cmd_ingest_bt(slug: str, tag: str, paths: list[str]) -> None:
    out = out_dir(slug)
    reqs = {r["unit_id"]: r for r in read_jsonl(out / f"bt_requests_{tag}.jsonl")}
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
                    body = {"greek": body}
            rows.append({"unit_id": r["unit_id"], "rendering": tag, "model": r.get("model", ""), "backend": "claude_code_session", "prompt_sha256": q["prompt_sha256"],
                         "started_utc": r.get("started_utc", ""), "finished_utc": r.get("finished_utc", ""), "greek": (body or {}).get("greek", "") if isinstance(body, dict) else ""})
    rows.sort(key=lambda r: list(reqs).index(r["unit_id"]))
    write_jsonl(out / f"backtranslation_{tag}.jsonl", rows)
    print(tag, len(rows), "of", len(reqs), "back-translations ingested; missing", sorted(set(reqs) - {r["unit_id"] for r in rows}))


def score_a(out: Path, units: list[dict], targets_by_unit: dict) -> dict:
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

    work = WORKS[units[0]["work"]]
    ody = [json.loads(l) for l in (GDM / "data" / "lemmatized" / work["lemmatized_dir"] / f"{work['stem']}.jsonl").open(encoding="utf-8") if l.strip()]
    res = {}
    for tag in RENDERINGS:
        bt = {r["unit_id"]: r["greek"] for r in read_jsonl(out / f"backtranslation_{tag}.jsonl")}
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


# ---------------------------------------------------------------- (c)
def cmd_build_judge(slug: str, key_out: Path, seed: int) -> None:
    out = out_dir(slug)
    rows = load_term_table(out)
    rng = random.Random(seed)
    items, key = [], []
    real = [r for r in rows if r["lsj_entry_id"] and r["greek_sentence"]]
    for r in real:
        for tag in RENDERINGS:
            if r[f"rendering_{tag}"]:
                iid = f"J{len(items) + 1:04d}"
                items.append({"item_id": iid, "greek_sentence": r["greek_sentence"], "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"],
                              "lsj_headword": r["lsj_headword"], "lsj_entry": r["lsj_entry_text"][:600], "english": r[f"rendering_{tag}"]})
                key.append({"item_id": iid, "kind": "real", "unit_id": r["unit_id"], "target_no": r["target_no"], "rendering": tag, "expected": ""})
    # anchors: LSJ first gloss, mechanical
    cands = [r for r in real if first_gloss(r["lsj_entry_text"])]
    rng.shuffle(cands)
    seen = set()
    anchors = []
    for r in cands:
        if r["dilemma_lemma"] in seen:
            continue
        seen.add(r["dilemma_lemma"])
        anchors.append(r)
        if len(anchors) == 10:
            break
    for r in anchors:
        iid = f"J{len(items) + 1:04d}"
        items.append({"item_id": iid, "greek_sentence": r["greek_sentence"], "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"],
                      "lsj_headword": r["lsj_headword"], "lsj_entry": r["lsj_entry_text"][:600], "english": first_gloss(r["lsj_entry_text"])})
        key.append({"item_id": iid, "kind": "anchor", "unit_id": r["unit_id"], "target_no": r["target_no"], "rendering": "lsj_first_gloss", "expected": "in_range"})
    # plants: a real target with the rendering of a different target (different LSJ entry, no shared normalised token)
    plants, tries = [], 0
    pool = [r for r in real if r["rendering_A"]]
    while len(plants) < 10 and tries < 5000:
        tries += 1
        r, s = rng.sample(pool, 2)
        if r["lsj_entry_id"] == s["lsj_entry_id"] or r["dilemma_lemma"] in {p[0]["dilemma_lemma"] for p in plants}:
            continue
        wrong = s["rendering_A"]
        if not wrong or set(norm(wrong).split()) & (set(norm(r["rendering_A"]).split()) | set(norm(r["rendering_B"]).split()) | set(norm(r["lsj_entry_text"][:300]).split())):
            continue
        plants.append((r, s, wrong))
    for r, s, wrong in plants:
        iid = f"J{len(items) + 1:04d}"
        items.append({"item_id": iid, "greek_sentence": r["greek_sentence"], "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"],
                      "lsj_headword": r["lsj_headword"], "lsj_entry": r["lsj_entry_text"][:600], "english": wrong})
        key.append({"item_id": iid, "kind": "plant", "unit_id": r["unit_id"], "target_no": r["target_no"], "rendering": f"from {s['unit_id']}:{s['target_no']}", "expected": "out_of_range"})
    order = list(range(len(items)))
    rng.shuffle(order)
    items = [items[i] for i in order]
    pos = {it["item_id"]: n for n, it in enumerate(items)}
    key.sort(key=lambda k: pos[k["item_id"]])
    for it in items:
        it["system"] = JUDGE_SYSTEM
    write_jsonl(out / "judge_sheet.jsonl", items)
    key_out.parent.mkdir(parents=True, exist_ok=True)
    with key_out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(key[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(key)
    meta = {"seed": seed, "n_items": len(items), "n_real": sum(k["kind"] == "real" for k in key), "n_anchor": len(anchors), "n_plant": len(plants), "key": "outside the repository until scored"}
    (out / "judge_sheet_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


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


# ---------------------------------------------------------------- score
def cmd_score(slug: str, key_path: Path | None) -> None:
    out = out_dir(slug)
    units = read_jsonl(out / "units.jsonl")
    tt = load_term_table(out)
    targets_by_unit = defaultdict(list)
    for r in tt:
        targets_by_unit[r["unit_id"]].append(r)
    result = {"spec": "firstdrafts_v0_spec.md", "thresholds": THRESHOLDS, "work": slug, "units": {}, "summary": {}}

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
    a_res = score_a(out, units, targets_by_unit) if have_bt else {}

    # (c)
    c = {u["unit_id"]: {"verdict": "not_run"} for u in units}
    gate = None
    if key_path and (out / "judge_answers.jsonl").exists():
        key = {k["item_id"]: k for k in csv.DictReader(key_path.open(encoding="utf-8"))}
        ans = {r["item_id"]: r for r in read_jsonl(out / "judge_answers.jsonl")}
        controls = [k for k in key.values() if k["kind"] != "real"]
        hits = sum(1 for k in controls if ans.get(k["item_id"], {}).get("verdict") == k["expected"])
        gate = {"controls": len(controls), "correct": hits, "passed": hits == len(controls) and len(controls) == 20,
                "misses": [{"item_id": k["item_id"], "kind": k["kind"], "expected": k["expected"], "got": ans.get(k["item_id"], {}).get("verdict", "missing")} for k in controls if ans.get(k["item_id"], {}).get("verdict") != k["expected"]]}
        per_unit = defaultdict(list)
        for k in key.values():
            if k["kind"] == "real":
                per_unit[k["unit_id"]].append(ans.get(k["item_id"], {}).get("verdict", "missing"))
                for r in targets_by_unit.get(k["unit_id"], []):
                    if r["target_no"] == k["target_no"]:
                        r[f"judge_{k['rendering']}"] = ans.get(k["item_id"], {}).get("verdict", "missing")
        # anchors whose mechanical first gloss is not an English gloss at all (fewer than 3 letters, or a bare
        # function word) are recorded as defective: the gate stays failed (pre-registered), the count is reported
        defective = [m for m in gate["misses"] if m["kind"] == "anchor" and not re.fullmatch(r"[a-z][a-z\- ]{2,}", (next(it for it in read_jsonl(out / "judge_sheet.jsonl") if it["item_id"] == m["item_id"])["english"] or "").strip().lower()) or (next(it for it in read_jsonl(out / "judge_sheet.jsonl") if it["item_id"] == m["item_id"])["english"] or "").strip().lower() in {"in", "also", "the", "of", "to"}]
        gate["defective_anchor_misses"] = len(defective)
        gate["note"] = ("gate failed; every miss is an anchor whose mechanically extracted LSJ first gloss was not an English gloss (see judge_sheet), all plants were caught"
                        if not gate["passed"] and gate["defective_anchor_misses"] == len(gate["misses"]) else "")
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
        # write judge verdicts into the term table
        with (out / "term_table.csv").open("w", encoding="utf-8", newline="") as fh:
            fields = list(tt[0].keys()) + [f for f in ("judge_A", "judge_B") if f not in tt[0]]
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(tt)

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
        result["units"][uid] = {"locus": u["locus"], "difficulty_tier": u["difficulty_tier"], "punch_density_per100": u["punch_density_per100"],
                                "a": {"verdict": a_verdict, **{t: a_unit[t] for t in RENDERINGS}}, "b": b[uid], "c": c[uid], "verdict": unit_verdict}

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
        "uncertain_flags": {t: sum(1 for r in tt if r[f"uncertain_{t}"] == "y") for t in RENDERINGS},
    }
    for cls_name, pred in (("punch", lambda r: r["punch_tier"] != ""), ("fourway_only", lambda r: r["punch_tier"] == "")):
        rows = [r for r in tt if r["agree"] and pred(r)]
        k = sum(r["agree"] == "y" for r in rows)
        result["summary"]["b_by_class"][cls_name] = {"n": len(rows), "agree": k, "pct": round(100 * k / len(rows), 2) if rows else None, "wilson95": wilson(k, len(rows))}
    # density vs disagreement (Spearman, as MT-2026)
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
        num = sum((a - mx) * (b_ - my) for a, b_ in zip(rx, ry))
        den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b_ - my) ** 2 for b_ in ry))
        result["summary"]["density_vs_disagreement_spearman"] = {"rho": round(num / den, 3) if den else None, "n": len(xs)}
    (out / "checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build-bt", "ingest-bt", "build-judge", "ingest-judge", "score"])
    ap.add_argument("--work", default="adversus-lycum")
    ap.add_argument("--rendering", choices=list(RENDERINGS))
    ap.add_argument("--responses", action="append", default=[])
    ap.add_argument("--key-out", type=Path)
    ap.add_argument("--key", type=Path)
    ap.add_argument("--seed", type=int, default=20261109)
    a = ap.parse_args()
    if a.cmd == "build-bt":
        cmd_build_bt(a.work)
    elif a.cmd == "ingest-bt":
        cmd_ingest_bt(a.work, a.rendering, a.responses)
    elif a.cmd == "build-judge":
        cmd_build_judge(a.work, a.key_out, a.seed)
    elif a.cmd == "ingest-judge":
        cmd_ingest_judge(a.work, a.responses)
    else:
        cmd_score(a.work, a.key)


if __name__ == "__main__":
    main()
