"""Cut the small test fixtures from the real published data (run from the repo root).

    python mcp/tests/make_fixtures.py

Writes mcp/tests/fixtures/repo/<same paths as the public repo>, a few units per work, a few dozen
lemmas, a few gold rows. The tests read only these files and never touch the network.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "fixtures" / "repo"


def cut_work(rel: str, keep) -> set[str]:
    d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    ids = [u["unit_id"] for u in d["units"] if keep(u)]
    sel = set(ids)
    d["units"] = [{k: v for k, v in u.items() if k != "greek_plain"} for u in d["units"] if u["unit_id"] in sel]
    d["term_table"] = [{k: v for k, v in t.items() if k != "lsj_entry_text"} for t in d["term_table"]
                       if t["unit_id"] in sel]
    d["renderings"] = {k: [r for r in v if r["unit_id"] in sel] for k, v in d["renderings"].items()}
    d["checks"]["units"] = {k: v for k, v in d["checks"]["units"].items() if k in sel}
    out = OUT / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return {t["lsj_entry_id"] for t in d["term_table"] if t["lsj_entry_id"]}


def main() -> None:
    ids = cut_work("docs/first-drafts/hirudinibus/data.json", lambda u: u["unit_id"] in
                   {"K11.317", "K11.317-318", "K11.318-319"})
    ids |= cut_work("docs/first-drafts/in-hipp-acut/data.json",
                    lambda u: any(p in {"608", "609", "610", "611"} for p in u["pages"]))
    cut_work("docs/method/vitruvius-3/data.json", lambda u: u["unit_id"] in
             {"Vitr.3.pr.1", "Vitr.3.1.1-3.1.2", "Vitr.3.1.5", "Vitr.3.1.6", "Vitr.3.1.9-3.2.2"})

    ti_rel = "galen-density-map/outputs/firstdrafts/_index/term_index.json"
    ti = json.loads((ROOT / ti_rel).read_text(encoding="utf-8"))
    extra = {"γνώρισμα", "νεῦρον", "νευρότρωτος", "δριμύς", "χυμός", "ἀραιός", "ὄνυξ"}
    lem = [r for r in ti["lemmas"] if r["key"] in ids or r["lemma"] in extra]
    keys = {r["key"] for r in lem}
    for r in lem:  # keep every locus only where a test pages through them
        if r["lemma"] != "δριμύς":
            for w in r["works"]:
                w["loci"] = w["loci"][:6]
    ti = {"summary": ti["summary"], "most_inconsistent": [k for k in ti["most_inconsistent"] if k in keys],
          "lemmas": lem}
    (OUT / ti_rel).parent.mkdir(parents=True, exist_ok=True)
    (OUT / ti_rel).write_text(json.dumps(ti, ensure_ascii=False), encoding="utf-8")

    for rel, heads in (("release/lsj-gold-1.0/lsj_gold.csv", {"ἀάω", "ἀγαθός", "ὄνυξ"}),
                       ("release/ls-gold-1.0/ls_gold.csv", {"ab-dico", "abacus"})):
        with open(ROOT / rel, encoding="utf-8", newline="") as fh:
            r = csv.DictReader(fh)
            rows = [x for x in r if x["headword"] in heads][:60]
            fields = r.fieldnames
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        (OUT / rel).write_text(buf.getvalue(), encoding="utf-8")
        board = rel.rsplit("/", 1)[0] + "/leaderboard.json"
        b = json.loads((ROOT / board).read_text(encoding="utf-8"))
        (OUT / board).write_text(json.dumps({"version": b.get("version"), "author_names": b.get("author_names")},
                                            ensure_ascii=False), encoding="utf-8")
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"fixtures: {len(lem)} lemmas, {total} bytes under {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
