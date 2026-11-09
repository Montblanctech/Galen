"""Galen First Drafts v0, stage 2: two independent renderings per unit (spec: firstdrafts_v0_spec.md).

The same neutral prompt for both translators, no glossary, fresh context per model. Three subcommands:

  build    write outputs/firstdrafts/<slug>/requests.jsonl: one request per unit (system prompt, user
           prompt with the unit's Greek, its locus, the neighbouring units as context marked "do not
           translate", and the target words by position), plus prompt_sha256 and a session brief
           (requests_README.md) for a model session that fills responses by hand.
  ingest   take the responses file(s) written by Claude Code model sessions (Agent tool, model=fable /
           model=opus; backend "claude_code_session") and write renderings_<model>.jsonl: every row
           carries model, prompt hash, the session's timestamps, backend. The raw session files are
           copied beside it under sessions/.

This script never calls the Claude API (Will, 2026-11-09: no paid API from translate.py or checks.py);
an ANTHROPIC_API_KEY in the environment is ignored.

Model names: A = claude-fable-5-1, B = claude-opus-5-5 (short names fable-5-1 / opus-5-5 in file names,
as in data/qc/mt2026/).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common import REPO, WORKS, out_dir, read_jsonl, sha256, write_jsonl

MODELS = {"fable-5-1": "claude-fable-5-1", "opus-5-5": "claude-opus-5-5"}

SYSTEM = (
    "You are translating Galen from Ancient Greek into English for a scholarly first draft. "
    "Translate the passage marked TRANSLATE completely and faithfully, in a scholarly register, keeping technical "
    "terms technical (do not paraphrase around a term, do not modernise a medical concept into a modern diagnosis), "
    "and keeping the order of the argument. Do not add notes, headings or commentary. Keep every bracketed page "
    "marker such as [197] in the English at the place corresponding to the Greek. The text is Kühn's 1829 edition "
    "and may be corrupt in places: translate what is there as best you can and name the Greek words you are "
    "unsure of. The passages marked CONTEXT are for understanding only; do not translate them. "
    "Answer with one JSON object and nothing else: "
    '{"translation": "<the English of the TRANSLATE passage>", '
    '"renderings": [{"target_no": <int>, "surface": "<Greek word as given>", "english": "<the English word or short phrase you used for it in your translation>", "uncertain": "y|n"}], '
    '"uncertain_greek": ["<Greek words of the passage you are unsure how to translate>"]}. '
    "The renderings list must contain exactly one entry for every target listed, in the order given; if a target "
    "is not rendered by any single word (for example it was absorbed into a construction), give the phrase that "
    "carries it."
)


def build_user(unit: dict, prev: dict | None, nxt: dict | None, targets: list[dict], work: dict) -> str:
    parts = [f"Work: Galen, {work['title_lat']} ({work['title_eng']}), Kühn vol. {work['kuhn_vol']}. Unit {unit['unit_id']}, locus {unit['locus']}, chapter(s) {', '.join(unit['chapters'])}."]
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


def cmd_build(slug: str) -> None:
    out = out_dir(slug)
    work = WORKS[slug]
    units = read_jsonl(out / "units.jsonl")
    tg = defaultdict(list)
    for r in csv.DictReader((out / "targets.csv").open(encoding="utf-8")):
        tg[r["unit_id"]].append({"target_no": int(r["target_no"]), "surface": r["surface"]})
    reqs = []
    for i, u in enumerate(units):
        user = build_user(u, units[i - 1] if i else None, units[i + 1] if i + 1 < len(units) else None, tg.get(u["unit_id"], []), work)
        reqs.append({"unit_id": u["unit_id"], "system": SYSTEM, "user": user, "prompt_sha256": sha256(SYSTEM + "\n\n" + user),
                     "n_targets": len(tg.get(u["unit_id"], [])), "targets": tg.get(u["unit_id"], [])})
    write_jsonl(out / "requests.jsonl", reqs)
    (out / "requests_README.md").write_text(
        "# Translator session brief (one model per session, fresh context, nothing else from the project)\n\n"
        f"Read `requests.jsonl` ({len(reqs)} rows). For every row, act exactly as the `system` text says on the `user` text: translate the TRANSLATE passage, "
        "report the renderings of the listed targets, list the Greek words you are unsure of. Write one JSON object per line to "
        "`responses_<model>.jsonl` with the fields: unit_id, model (your exact model id), started_utc, finished_utc (ISO 8601), "
        "response (the JSON object the system prompt asks for, as an object, not a string). Do not read any other file in this "
        "repository. Do not consult a glossary or any other translation. Do not skip, merge or shorten units.\n", encoding="utf-8")
    print(f"{len(reqs)} requests -> {out / 'requests.jsonl'}; prompt bytes {sum(len(r['system']) + len(r['user']) for r in reqs):,}")


def cmd_ingest(slug: str, short: str, paths: list[str]) -> None:
    out = out_dir(slug)
    reqs = {r["unit_id"]: r for r in read_jsonl(out / "requests.jsonl")}
    sess = out / "sessions"
    sess.mkdir(exist_ok=True)
    resp = []
    for path in paths:
        src = Path(path) if os.path.isabs(path) else REPO / path
        shutil.copy(src, sess / src.name)  # raw session output kept beside the ingested file
        resp += read_jsonl(src)
    rows, problems = [], []
    for r in resp:
        q = reqs.get(r["unit_id"])
        if q is None:
            problems.append(f"{r['unit_id']}: unknown unit")
            continue
        body = r.get("response")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                body = None
        if not isinstance(body, dict) or "translation" not in body:
            problems.append(f"{r['unit_id']}: no translation object")
        else:
            got = [x.get("target_no") for x in body.get("renderings", [])]
            want = [t["target_no"] for t in q["targets"]]
            if got != want:
                problems.append(f"{r['unit_id']}: renderings {got} != targets {want}")
            if body["translation"].count("[") != q["user"].split("TRANSLATE (unit")[1].split("CONTEXT")[0].count("["):
                problems.append(f"{r['unit_id']}: page-marker count differs")
        rows.append({"unit_id": r["unit_id"], "model": r.get("model", MODELS[short]), "backend": "claude_code_session", "prompt_sha256": q["prompt_sha256"],
                     "started_utc": r.get("started_utc", ""), "finished_utc": r.get("finished_utc", ""), "stop_reason": "", "usage": r.get("usage", {}),
                     "raw_text": json.dumps(body, ensure_ascii=False) if body is not None else json.dumps(r.get("response"), ensure_ascii=False), "response": body})
    missing = sorted(set(reqs) - {r["unit_id"] for r in rows})
    rows.sort(key=lambda r: list(reqs).index(r["unit_id"]))
    write_jsonl(out / f"renderings_{short}.jsonl", rows)
    report = {"model": short, "n_units": len(reqs), "n_responses": len(rows), "missing_units": missing, "problems": problems}
    (out / f"ingest_report_{short}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "ingest"])
    ap.add_argument("--work", default="adversus-lycum")
    ap.add_argument("--model", choices=list(MODELS), help="fable-5-1 or opus-5-5")
    ap.add_argument("--responses", action="append", default=[], help="ingest: path(s) to the sessions' responses JSONL (repeatable)")
    a = ap.parse_args()
    if a.cmd == "build":
        cmd_build(a.work)
    else:
        cmd_ingest(a.work, a.model, a.responses)


if __name__ == "__main__":
    main()
