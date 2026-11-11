"""Galen First Drafts: check (d) against a further human translation that may not be redistributed (2026-11-11).

Input: a JSONL of passages {n, kuhn, english, unit_ids, greek_start, greek_end} kept OUTSIDE the repository (for
Composition of Drugs by Kind: Manuela Marai's own translations in her 2023 Warwick PhD thesis "Wound Treatment in
Galen", wrap.warwick.ac.uk/id/eprint/188639, extracted by a model reader and checked here). The thesis text is not
copied into the repository; only loci and agreement counts are written.

Checks before scoring (a passage that fails any is dropped and listed):
  1. its English occurs verbatim in the thesis text (whitespace and soft hyphens normalised);
  2. greek_start occurs in the first unit and greek_end in the last unit of unit_ids, in that order;
  3. one passage per Greek span: where the thesis quotes a locus more than once, the longest English is kept.
Scoring: checks.score_d, the rule of the pre-registered check (d), on a copy of the term table (the work's own files
are not changed). Output: outputs/firstdrafts/<slug>/checks_reference_<tag>.json.

  python -X utf8 pipeline/firstdrafts/reference_extra.py --work comp-per-genera --passages <jsonl> --source-text <txt> --tag thesis_marai2023
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import out_dir, read_jsonl  # noqa: E402
from checks import score_d  # noqa: E402


def flat(s: str) -> str:
    s = s.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    s = re.sub(r"-\s*\n\s*", "", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--passages", type=Path, required=True)
    ap.add_argument("--source-text", type=Path, required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--citation", default="")
    a = ap.parse_args()
    out = out_dir(a.work)
    units = {u["unit_id"]: u for u in read_jsonl(out / "units.jsonl")}
    b = a.source_text.read_bytes()
    try:
        src = flat(b.decode("utf-8"))
    except UnicodeDecodeError:   # pdftotext wrote the thesis text as Latin-1
        src = flat(b.decode("cp1252", errors="replace"))
    src_nospace = src.replace(" ", "")
    raw = read_jsonl(a.passages)
    kept, dropped = {}, []
    for p in raw:
        eng = flat(p["english"])
        if eng.replace(" ", "") not in src_nospace:
            dropped.append((p["n"], "english not verbatim in the source"))
            continue
        uids = p["unit_ids"]
        if not uids or any(u not in units for u in uids):
            dropped.append((p["n"], "unknown unit"))
            continue
        g0 = units[uids[0]]["greek_plain"]
        g1 = units[uids[-1]]["greek_plain"]
        i = g0.find(p["greek_start"])
        j = g1.find(p["greek_end"])
        if i < 0 or j < 0 or (len(uids) == 1 and j + len(p["greek_end"]) <= i):
            dropped.append((p["n"], "greek start/end not found in order"))
            continue
        if len(uids) == 1:
            greek = g0[i: j + len(p["greek_end"])]
        else:
            greek = g0[i:] + " " + " ".join(units[u]["greek_plain"] for u in uids[1:-1]) + " " + g1[: j + len(p["greek_end"])]
        span = (tuple(uids), p["greek_start"], p["greek_end"])
        if span in kept and len(kept[span]["english"]) >= len(eng):
            dropped.append((p["n"], f"repeat of passage {kept[span]['n']} (shorter or equal)"))
            continue
        if span in kept:
            dropped.append((kept[span]["n"], f"repeat of passage {p['n']} (shorter)"))
        kept[span] = {"n": p["n"], "passage": p["n"], "kuhn": p.get("kuhn", ""), "unit_ids": uids, "greek": greek, "english": eng}
    passages = sorted(kept.values(), key=lambda x: x["n"])
    tt = list(csv.DictReader((out / "term_table.csv").open(encoding="utf-8")))
    for r in tt:
        for f in ("ref_agree_A", "ref_agree_B", "ref_passage"):
            r[f] = ""
    with tempfile.TemporaryDirectory() as td:
        ref = Path(td) / "reference"
        ref.mkdir()
        (ref / "calibration_map.json").write_text("{}", encoding="utf-8")
        with (ref / "passages.jsonl").open("w", encoding="utf-8") as fh:
            for p in passages:
                fh.write(json.dumps({k: p[k] for k in ("passage", "greek", "english", "unit_ids")}, ensure_ascii=False) + "\n")
        res = score_d(Path(td), tt)
    res.pop("items", None)
    res = {"tag": a.tag, "source": a.citation, "exploratory": "not pre-registered; the rule is the pre-registered rule of check (d)",
           "n_passages_extracted": len(raw), "n_passages_scored": len(passages), "dropped": [{"n": n, "why": w} for n, w in dropped],
           "passages": [{"n": p["n"], "kuhn": p["kuhn"], "unit_ids": p["unit_ids"]} for p in passages], **res}
    (out / f"checks_reference_{a.tag}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    pr = res["per_rendering"]
    print(json.dumps({"scored": len(passages), "dropped": len(dropped), "A": pr["A"], "B": pr["B"]}, ensure_ascii=False))
    for n, w in dropped:
        print("  dropped", n, w)


if __name__ == "__main__":
    main()
