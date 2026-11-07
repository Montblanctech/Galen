"""Constrained-terminology demonstration, stage 1 (spec: mt2026_constrained_terminology_spec.md).

Builds data/qc/mt2026/constrained/: terminology.csv (ten terms, LSJ definition, LSJ-derived preferred
rendering), passages.jsonl (the 11/05 passages that contain one of the terms as a target),
translator_targets.csv (all 11/05 targets of those passages, class withheld), build_meta.json.
Deterministic; no model involved.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "mt2026"
OUT = QC / "constrained"
TERMS = ["δύσκρατος", "δυσκρασία", "ῥευματικός", "ψωρώδης", "δακνῶδής", "ἐγκηρίς", "ῥητίνη", "μαλακτικός", "ψιμύθιον", "χαλβάνη"]
EXCLUDED = {"ἔνιοι": "function word", "βελτίων": "comparative", "ποιότης": "non-medical abstraction"}


def first_gloss(entry: str) -> str:
    """First English clause of a Perseus LSJ entry, mechanically: drop parentheticals and '= <Greek>' cross
    references, then take the first run that starts with a lower-case English word (2+ letters, not an
    abbreviation) and stop at ',', ';', ':' or an author citation such as 'Hp.' / 'Gal.'."""
    text = re.sub(r"\s+", " ", entry or "")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"=\s*[^,;]*[,;]", " ", text)
    abbrev = {"v", "cf", "infr", "supr", "sc", "al", "ib", "id", "pl", "sg", "dub", "etc", "esp", "gen", "dat", "acc", "nom", "adv", "comp", "sup"}
    for m in re.finditer(r"(?<![A-Za-z])([a-z][a-z\-']+(?: [a-zA-Z\-']+)*)", text):
        first = m.group(1).split()[0].strip("-'")
        if first in abbrev or len(first) < 2:
            continue
        seg = text[m.start(1):]
        seg = re.split(r"[,;:]| [A-Z][a-z]{1,5}\. ?| v\. | cf\. ", seg)[0]
        return seg.strip(" .")
    return ""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    td = list(csv.DictReader((QC / "term_disagreements.csv").open(encoding="utf-8")))
    att = {r["lemma"]: r for r in csv.DictReader((GDM / "outputs" / "phase3" / "attributed_punch_list.csv").open(encoding="utf-8"))}
    passages = [json.loads(l) for l in (QC / "passages.jsonl").open(encoding="utf-8")]
    targets = list(csv.DictReader((QC / "translator_targets.csv").open(encoding="utf-8")))

    term_rows = []
    by_term_passages: dict[str, set] = defaultdict(set)
    for r in td:
        if r["lemma"] in TERMS:
            by_term_passages[r["lemma"]].add(r["passage_id"])
    for t in TERMS:
        a = att.get(t)
        if not a:
            raise SystemExit(f"{t} not in attributed_punch_list")
        entry = (a.get("lsj_entry_text") or "")[:600]
        occ = [r for r in td if r["lemma"] == t]
        term_rows.append({
            "lemma": t, "lsj_headword": a.get("lsj_headword", ""), "pos": a.get("pos", ""),
            "preferred_rendering_lsj_first_gloss": first_gloss(entry), "lsj_definition": entry,
            "surfaces_in_targets": "; ".join(sorted({r["surface"] for r in occ})),
            "n_targets": len(occ), "n_passages": len(by_term_passages[t]),
            "disagreed_1105": sum(r["verdict"] != "agree" for r in occ),
            "uncertain_flags_1105": sum((r["uncertain_fable-5-1"] == "y") + (r["uncertain_opus-5-5"] == "y") for r in occ),
        })
    keep = set().union(*by_term_passages.values())
    sub_passages = [p for p in passages if p["passage_id"] in keep]
    sub_targets = [r for r in targets if r["passage_id"] in keep]
    with (OUT / "terminology.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(term_rows[0].keys()))
        w.writeheader()
        w.writerows(term_rows)
    with (OUT / "passages.jsonl").open("w", encoding="utf-8") as fh:
        for p in sub_passages:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with (OUT / "translator_targets.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["passage_id", "target_no", "surface"])
        w.writeheader()
        w.writerows(sub_targets)
    term_target_keys = {(r["passage_id"], r["target_no"]) for r in td if r["lemma"] in TERMS}
    meta = {"date": "2026-11-06", "spec": "mt2026_constrained_terminology_spec.md", "terms": TERMS, "excluded_by_rule": EXCLUDED,
            "n_passages": len(sub_passages), "n_targets": len(sub_targets), "n_term_targets": len(term_target_keys),
            "n_other_targets": len(sub_targets) - len(term_target_keys), "judge_seed": 20261106,
            "conditions": {"C0": "11/05 instructions, no glossary, fresh session", "C1": "same + terminology.csv, use preferred rendering where the term occurs"},
            "translators": ["fable-5-1", "opus-5-5"], "judges": ["sonnet-5-5", "opus-5-5"]}
    (OUT / "build_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    for r in term_rows:
        print(f"{r['lemma']:14s} -> {r['preferred_rendering_lsj_first_gloss']!r:40s} targets {r['n_targets']} passages {r['n_passages']}")


if __name__ == "__main__":
    main()
