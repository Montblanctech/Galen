"""Galen First Drafts v0.2, stage 2: two independent renderings per unit (spec: firstdrafts_v02_spec.md;
v0 spec firstdrafts_v0_spec.md for Adversus Lycum).

The same neutral prompt for both translators, no glossary, fresh context per model. Subcommands:

  build    write outputs/firstdrafts/<slug>/requests.jsonl: one base request per unit (system prompt, user
           prompt with the unit's Greek, its locus, the neighbouring units as context marked "do not
           translate", and the target words by position), plus prompt_sha256 of the base prompt and a
           session brief (requests_README.md). The term-memory block is NOT in the base request: it is
           built at send time from the renderings already written by the same model (v0.2 §3).
  api      call the Claude API for one model over every unit without a usable row (api_backend.run_stage:
           key from the environment or the key file, resume, usage.jsonl, --budget stop, backoff). Each
           row carries model, backend, the SHA-256 of the prompt actually sent, the term-memory block it
           was sent, per-item timestamps (direct mode), stop reason, usage, USD. Order: calibration units
           first (reference/calibration_map.json, if present), then the rest; --subset calibration sends
           only those.
  ingest   take responses written by Claude Code model sessions (cycle 1 path; backend
           "claude_code_session") and write the same renderings_<model>.jsonl.

Nothing calls a model unless `api` is given explicitly. Model names: A = claude-fable-5-1,
B = claude-opus-5-5 (short names fable-5-1 / opus-5-5 in file names, as in data/qc/mt2026/).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import REPO, WORKS, out_dir, read_jsonl, sha256, write_jsonl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mt2026"))
from score_consistency import norm  # noqa: E402

MODELS = {"fable-5-1": "claude-fable-5-1", "opus-5-5": "claude-opus-5-5"}
MEMORY_MAX_RENDERINGS = 3  # distinct prior renderings shown per lemma

SYSTEM = (
    "You are translating Galen from Ancient Greek into English for a scholarly first draft. "
    "Translate the passage marked TRANSLATE completely and faithfully, in a scholarly register, keeping technical "
    "terms technical (do not paraphrase around a term, do not modernise a medical concept into a modern diagnosis), "
    "and keeping the order of the argument. Do not add notes, headings or commentary. Keep every bracketed page "
    "marker such as [197] in the English at the place corresponding to the Greek. The text is Kühn's 1829 edition "
    "and may be corrupt in places: translate what is there as best you can and name the Greek words you are "
    "unsure of. The passages marked CONTEXT are for understanding only; do not translate them. "
    "A TERM MEMORY block, when present, lists how earlier passages of this same work rendered some of the target "
    "words; it is information about consistency, not an instruction: use the same rendering where the sense is the "
    "same, and a different one where this context requires it. "
    "Answer with one JSON object and nothing else: "
    '{"translation": "<the English of the TRANSLATE passage>", '
    '"renderings": [{"target_no": <int>, "surface": "<Greek word as given>", "english": "<the English word or short phrase you used for it in your translation>", "uncertain": "y|n"}], '
    '"uncertain_greek": ["<Greek words of the passage you are unsure how to translate>"]}. '
    "The renderings list must contain exactly one entry for every target listed, in the order given; if a target "
    "is not rendered by any single word (for example it was absorbed into a construction), give the phrase that "
    "carries it."
)


def build_user(unit: dict, prev: dict | None, nxt: dict | None, targets: list[dict], work: dict) -> str:
    chap = ", ".join(unit.get("chapters") or []) or "?"
    parts = [f"Work: Galen, {work['title_lat']} ({work['title_eng']}), Kühn vol. {work['kuhn_vol']}. Unit {unit['unit_id']}, locus {unit['locus']}, chapter(s) {chap}."]
    if prev:
        parts.append(f"CONTEXT (preceding, do not translate):\n{prev['greek']}")
    parts.append(f"TRANSLATE (unit {unit['unit_id']}):\n{unit['greek']}")
    if nxt:
        parts.append(f"CONTEXT (following, do not translate):\n{nxt['greek']}")
    if targets:
        parts.append("TARGETS (report the English you used for each; target_no is the word's position in the TRANSLATE passage, counting words from 0 and skipping the bracketed page markers):\n" + "\n".join(f"{t['target_no']}\t{t['surface']}" for t in targets))
    else:
        parts.append("TARGETS: none for this unit (return an empty renderings list).")
    return "\n\n".join(parts)


def memory_block(memory: list[dict]) -> str:
    if not memory:
        return ""
    lines = [f"{m['target_no']}\t{m['surface']}\t(lemma {m['lemma']}): earlier rendered as " + "; ".join(f"\"{r}\" (x{n})" for r, n in m["renderings"]) for m in memory]
    return "TERM MEMORY (information, not an instruction: how earlier units of this work rendered these target words):\n" + "\n".join(lines)


def with_memory(base_user: str, memory: list[dict]) -> str:
    """The memory block goes before TARGETS so the target list stays last (as in v0)."""
    blk = memory_block(memory)
    if not blk:
        return base_user
    i = base_user.rfind("\n\nTARGETS")
    return base_user[:i] + "\n\n" + blk + base_user[i:] if i >= 0 else base_user + "\n\n" + blk


def load_targets(out: Path) -> dict[str, list[dict]]:
    tg = defaultdict(list)
    for r in csv.DictReader((out / "targets.csv").open(encoding="utf-8")):
        tg[r["unit_id"]].append({"target_no": int(r["target_no"]), "surface": r["surface"], "lemma": r["dilemma_lemma"] or r["odycy_lemma"]})
    return tg


def cmd_build(slug: str) -> None:
    out = out_dir(slug)
    work = WORKS[slug]
    units = read_jsonl(out / "units.jsonl")
    tg = load_targets(out)
    reqs = []
    for i, u in enumerate(units):
        t = [{"target_no": x["target_no"], "surface": x["surface"]} for x in tg.get(u["unit_id"], [])]
        user = build_user(u, units[i - 1] if i else None, units[i + 1] if i + 1 < len(units) else None, t, work)
        reqs.append({"unit_id": u["unit_id"], "system": SYSTEM, "user": user, "prompt_sha256": sha256(SYSTEM + "\n\n" + user), "n_targets": len(t), "targets": t})
    write_jsonl(out / "requests.jsonl", reqs)
    (out / "requests_README.md").write_text(
        "# Translator requests (base prompts; the api subcommand adds the TERM MEMORY block at send time)\n\n"
        f"`requests.jsonl` has {len(reqs)} rows: system, user (base prompt without term memory), prompt_sha256 of that base prompt, targets. "
        "The row written to `renderings_<model>.jsonl` carries `prompt_sha256` of the prompt actually sent (base + memory) and `term_memory`, "
        "so the sent prompt is reconstructable from these two files.\n\n"
        "Session path (cycle 1, no API): for every row act exactly as `system` says on `user`; write one JSON object per line to `responses_<model>.jsonl` "
        "with unit_id, model, started_utc, finished_utc, response (the object the system prompt asks for). Do not read any other file; no glossary; no skipping.\n", encoding="utf-8")
    print(f"{len(reqs)} requests -> {out / 'requests.jsonl'}; prompt bytes {sum(len(r['system']) + len(r['user']) for r in reqs):,}")


def unit_order(out: Path, units: list[dict], subset: str | None) -> list[str]:
    """Calibration units first (reference/calibration_map.json), then the rest in text order."""
    ids = [u["unit_id"] for u in units]
    cal_path = out / "reference" / "calibration_map.json"
    cal: list[str] = []
    if cal_path.exists():
        cm = json.loads(cal_path.read_text(encoding="utf-8"))
        for p in cm.get("passages", []):
            for uid in p.get("unit_ids", []):
                if uid in ids and uid not in cal:
                    cal.append(uid)
    if subset == "calibration":
        if not cal:
            sys.exit("--subset calibration: no reference/calibration_map.json with unit_ids")
        return cal
    return cal + [i for i in ids if i not in cal]


def build_memory(unit_id: str, tg: dict[str, list[dict]], done_rows: list[dict]) -> list[dict]:
    """For every target of the unit, the distinct prior renderings (normalised equal → one entry, counted)
    of the same lemma in units already rendered by this model, most frequent first, capped."""
    prior: dict[str, Counter] = defaultdict(Counter)
    surface_of: dict[tuple[str, str], str] = {}
    lemma_by_unit_target = {(t_uid, t["target_no"]): t["lemma"] for t_uid, ts in tg.items() for t in ts}
    for r in done_rows:
        body = r.get("response") or {}
        if not isinstance(body, dict):
            continue
        for x in body.get("renderings", []) or []:
            if not isinstance(x, dict) or not x.get("english"):
                continue
            lem = lemma_by_unit_target.get((r["unit_id"], x.get("target_no")))
            if lem:
                key = norm(x["english"])
                if key:
                    prior[lem][key] += 1
                    surface_of[(lem, key)] = x["english"].strip()
    mem = []
    for t in tg.get(unit_id, []):
        c = prior.get(t["lemma"])
        if not c:
            continue
        rend = [(surface_of[(t["lemma"], k)], n) for k, n in c.most_common(MEMORY_MAX_RENDERINGS)]
        mem.append({"target_no": t["target_no"], "surface": t["surface"], "lemma": t["lemma"], "renderings": rend})
    return mem


def cmd_api(slug: str, short: str, a) -> None:
    from api_backend import add_api_args, run_stage  # noqa: F401  (import here: nothing API-related loads for build/ingest)

    out = out_dir(slug)
    model = MODELS[short]
    units = read_jsonl(out / "units.jsonl")
    reqs = {r["unit_id"]: r for r in read_jsonl(out / "requests.jsonl")}
    if set(reqs) != {u["unit_id"] for u in units}:
        sys.exit("requests.jsonl does not match units.jsonl: run build first")
    tg = load_targets(out)
    out_path = out / f"renderings_{short}.jsonl"
    est = None
    cp = out / "cost_estimate.json"
    if cp.exists():
        ce = json.loads(cp.read_text(encoding="utf-8"))
        item = ce.get("items", {}).get(f"rendering_{'A' if short == 'fable-5-1' else 'B'}")
        if item:
            est = item["usd"] / max(1, ce["n_units"]) * (0.5 if a.mode == "batch" else 1.0)

    def make_request(uid: str):
        done = [r for r in read_jsonl(out_path) if r.get("ok")]
        mem = build_memory(uid, tg, done)
        user = with_memory(reqs[uid]["user"], mem)
        return SYSTEM, user, {"base_prompt_sha256": reqs[uid]["prompt_sha256"], "term_memory": mem, "n_memory_terms": len(mem)}

    run_stage(stage=f"translate_{short}", work=slug, model=model, ids=unit_order(out, units, a.subset), make_request=make_request, out_path=out_path,
              usage_path=out / "usage.jsonl", id_field="unit_id", budget=a.budget, mode=a.mode, packet_size=a.packet_size or (8 if a.mode == "direct" else 50),
              workers=a.workers, max_tokens=a.max_tokens, effort=a.effort, est_usd_per_call=est, parse="json", limit=a.limit)
    report_renderings(out, short, reqs)


def report_renderings(out: Path, short: str, reqs: dict) -> dict:
    rows = read_jsonl(out / f"renderings_{short}.jsonl")
    problems = []
    for r in rows:
        q = reqs.get(r["unit_id"])
        body = r.get("response")
        if not isinstance(body, dict) or "translation" not in body:
            problems.append(f"{r['unit_id']}: no translation object ({r.get('stop_reason')})")
            continue
        got = [x.get("target_no") for x in body.get("renderings", []) if isinstance(x, dict)]
        want = [t["target_no"] for t in q["targets"]]
        if got != want:
            problems.append(f"{r['unit_id']}: renderings {got} != targets {want}")
        if body["translation"].count("[") != q["user"].split("TRANSLATE (unit")[1].split("CONTEXT")[0].count("["):
            problems.append(f"{r['unit_id']}: page-marker count differs")
    report = {"model": short, "n_units": len(reqs), "n_responses": len(rows), "n_ok": sum(1 for r in rows if r.get("ok")),
              "missing_units": sorted(set(reqs) - {r["unit_id"] for r in rows}), "refusals": [r["unit_id"] for r in rows if r.get("stop_reason") == "refusal"],
              "backends": dict(Counter(r.get("backend", "") for r in rows)), "problems": problems}
    (out / f"ingest_report_{short}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "problems"}, ensure_ascii=False), f"problems: {len(problems)}")
    return report


def cmd_ingest(slug: str, short: str, paths: list[str]) -> None:
    out = out_dir(slug)
    reqs = {r["unit_id"]: r for r in read_jsonl(out / "requests.jsonl")}
    sess = out / "sessions"
    sess.mkdir(exist_ok=True)
    resp = []
    for path in paths:
        src = Path(path) if os.path.isabs(path) else REPO / path
        shutil.copy(src, sess / src.name)
        resp += read_jsonl(src)
    rows = []
    for r in resp:
        q = reqs.get(r["unit_id"])
        if q is None:
            continue
        body = r.get("response")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                body = None
        rows.append({"unit_id": r["unit_id"], "model": r.get("model", MODELS[short]), "backend": "claude_code_session", "prompt_sha256": q["prompt_sha256"],
                     "started_utc": r.get("started_utc", ""), "finished_utc": r.get("finished_utc", ""), "timestamps_scope": "packet", "stop_reason": "", "usage": r.get("usage", {}),
                     "raw_text": json.dumps(body, ensure_ascii=False) if body is not None else json.dumps(r.get("response"), ensure_ascii=False), "response": body,
                     "ok": isinstance(body, dict) and "translation" in body})
    rows.sort(key=lambda r: list(reqs).index(r["unit_id"]))
    write_jsonl(out / f"renderings_{short}.jsonl", rows)
    report_renderings(out, short, reqs)


def main() -> None:
    from api_backend import add_api_args

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "api", "ingest"])
    ap.add_argument("--work", default="adversus-lycum")
    ap.add_argument("--model", choices=list(MODELS), help="fable-5-1 or opus-5-5")
    ap.add_argument("--responses", action="append", default=[], help="ingest: path(s) to the sessions' responses JSONL (repeatable)")
    ap.add_argument("--subset", choices=["calibration"], default=None, help="api: send only the calibration units")
    add_api_args(ap)
    a = ap.parse_args()
    if a.cmd == "build":
        cmd_build(a.work)
    elif a.cmd == "api":
        if not a.model:
            sys.exit("--model required")
        cmd_api(a.work, a.model, a)
    else:
        cmd_ingest(a.work, a.model, a.responses)


if __name__ == "__main__":
    main()
