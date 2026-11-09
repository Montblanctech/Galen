"""LS-Gold, stage 2 — score Latin lemmatizers on the relocated loci (the Latin twin of lsjgold/score.py).

Systems: every <system>/<edition_stem>.jsonl under --system-cache dir(s) (default data/latin_corpus/caches), as
written by latin_caches.py: one line per token of the project's token stream {"i", "surface", "lemma"}. The lemma at
the gold token_index is compared with the Lewis & Short headword: blind = latnorm.key equality (case, diacritics,
u/v, i/j, homograph digits neutral: the headline figure); strict = diacritics and digits off, u/v and i/j as printed.
Enclitics: the token stream keeps -que/-ne/-ue on the host word; a system that lemmatizes the host alone still matches
(L&S cites the host word), one that returns 'que' is counted wrong. Strata: author, validation route (collatinus /
whitaker / quoted), how often L&S cites the entry (1 / 2-5 / 6+). Wilson 95% everywhere. Rows need >= 100 loci per
author to print. The two lexicon-first baselines (collatinus_first, whitaker_first) are the oracles' own first choice
and are therefore partly circular with the oracle validation routes; the by_validation block shows how much.
Outputs data/qc/lsgold/ls_gold_scores.json, ls_gold_table.md, ls_gold_scored.csv.

Run: python -X utf8 -I pipeline/lsgold/score_la.py [--gold data/qc/lsgold/ls_gold_v0.csv] [--system-cache DIR]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from latnorm import key as lkey, strict as lstrict  # noqa: E402

GDM = HERE.parent.parent
OUT = GDM / "data" / "qc" / "lsgold"
CORPUS = GDM / "data" / "latin_corpus"
MIN_AUTHOR_ROW = 100
BASELINES = {"collatinus_first", "whitaker_first"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 2), round(100 * (c + h), 2))


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson95": list(wilson(k, n)) if n else None}


def author_names() -> dict[str, str]:
    man_path = CORPUS / "editions_manifest.json"
    names: dict[str, str] = {}
    if man_path.exists():
        for w, r in json.loads(man_path.read_text(encoding="utf-8")).items():
            au = w.split(".")[0]
            if r.get("author") and au not in names:
                names[au] = r["author"]
    return names


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=OUT / "ls_gold_v0.csv")
    ap.add_argument("--system-cache", action="append", type=Path, default=[])
    a = ap.parse_args()
    caches = a.system_cache or [CORPUS / "caches"]
    gold = list(csv.DictReader(a.gold.open(encoding="utf-8")))
    cites_path = OUT / "ls_citation_counts.json"
    cites = json.load(cites_path.open(encoding="utf-8")) if cites_path.exists() else {}

    def cites_tier(eid: str) -> str:
        n = cites.get(eid, 0)
        return "unknown" if not n else "1" if n == 1 else "2-5" if n <= 5 else "6+"

    need: dict[str, set[int]] = defaultdict(set)
    for g in gold:
        need[g["edition_stem"]].add(int(g["token_index"]))
    systems: dict[str, dict[tuple[str, int], str]] = {}
    surf: dict[tuple[str, str, int], str] = {}
    misaligned: Counter = Counter()
    for d in caches:
        if not Path(d).exists():
            continue
        for sysdir in sorted(Path(d).iterdir()):
            if not sysdir.is_dir():
                continue
            m = systems.setdefault(sysdir.name, {})
            for stem, idxs in need.items():
                p = sysdir / f"{stem}.jsonl"
                if not p.exists():
                    continue
                for i, line in enumerate(p.open(encoding="utf-8")):
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    k = int(r.get("i", i))
                    if k in idxs:
                        surf[(sysdir.name, stem, k)] = (r.get("surface") or "").strip()
                        m[(stem, k)] = (r.get("lemma") or "").strip()

    scored = []
    agg: dict[str, Counter] = defaultdict(Counter)
    for g in gold:
        key = (g["edition_stem"], int(g["token_index"]))
        hk = g["headword_key"]
        hs = lstrict(g["headword"])
        ct = cites_tier(g.get("entry_id", ""))
        row = dict(g, cites_tier=ct)
        for name, m in systems.items():
            lem = m.get(key)
            cs = surf.get((name,) + key)
            if lem is not None and cs and lkey(cs) != lkey(g["surface"]):
                misaligned[name] += 1
                lem = None
            row[f"{name}_lemma"] = lem if lem is not None else ""
            if not lem:
                row[f"{name}_blind"] = ""
                agg[name]["missing"] += 1
                continue
            b = lkey(lem) == hk
            s = lstrict(lem) == hs
            row[f"{name}_blind"] = int(b)
            row[f"{name}_strict"] = int(s)
            c = agg[name]
            c["n"] += 1
            c["blind"] += b
            c["strict"] += s
            c[f"author:{g['author']}:n"] += 1
            c[f"author:{g['author']}:blind"] += b
            c[f"val:{g['validation']}:n"] += 1
            c[f"val:{g['validation']}:blind"] += b
            c[f"cites:{ct}:n"] += 1
            c[f"cites:{ct}:blind"] += b
        scored.append(row)

    authors = sorted({g["author"] for g in gold})
    res = {"date": datetime.date.today().isoformat(), "gold": a.gold.name, "n_loci": len(gold),
           "loci_per_author": dict(Counter(g["author"] for g in gold).most_common()), "systems": {}}
    for name, c in agg.items():
        res["systems"][name] = {
            "baseline": name in BASELINES, "scored": c["n"], "missing": c["missing"], "misaligned_surface": misaligned.get(name, 0),
            "match_blind": rate(c["blind"], c["n"]), "match_strict": rate(c["strict"], c["n"]),
            "by_author": {au: rate(c[f"author:{au}:blind"], c[f"author:{au}:n"]) for au in authors if c[f"author:{au}:n"] >= MIN_AUTHOR_ROW},
            "by_validation": {v: rate(c[f"val:{v}:blind"], c[f"val:{v}:n"]) for v in ("collatinus", "whitaker", "quoted") if c[f"val:{v}:n"]},
            "by_ls_citations": {t: rate(c[f"cites:{t}:blind"], c[f"cites:{t}:n"]) for t in ("1", "2-5", "6+", "unknown") if c[f"cites:{t}:n"]}}
    (OUT / "ls_gold_scores.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = list(dict.fromkeys(k for r in scored for k in r))
    with (OUT / "ls_gold_scored.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(scored)
    names = author_names()
    md = [f"# LS-Gold v0 — Latin lemmatizer accuracy on the dictionary-cited stratum ({res['date']})", "",
          f"{len(gold)} relocated loci over {len(authors)} authors. Match = headword equality after case, diacritic, u/v, i/j and homograph-digit normalisation; strict keeps u/v and i/j as printed. Wilson 95% in brackets.", "",
          "| system | loci | blind % | strict % | " + " | ".join(names.get(au, au)[:18] for au in authors if res['loci_per_author'].get(au, 0) >= MIN_AUTHOR_ROW) + " |",
          "|---|---|---|---|" + "---|" * sum(1 for au in authors if res['loci_per_author'].get(au, 0) >= MIN_AUTHOR_ROW)]
    for name, b in sorted(res["systems"].items(), key=lambda kv: -(kv[1]["match_blind"]["pct"] or 0)):
        cells = []
        for au in authors:
            if res['loci_per_author'].get(au, 0) < MIN_AUTHOR_ROW:
                continue
            r = b["by_author"].get(au)
            cells.append(f"{r['pct']}" if r else "—")
        md.append(f"| {name}{' (baseline)' if b['baseline'] else ''} | {b['scored']} | **{b['match_blind']['pct']}** [{b['match_blind']['wilson95'][0]}–{b['match_blind']['wilson95'][1]}] | {b['match_strict']['pct']} | " + " | ".join(cells) + " |")
    md += ["", "By validation route and citation frequency (blind %):", ""]
    for name, b in res["systems"].items():
        md.append(f"- {name}: " + ", ".join(f"{v} {r['pct']} (n {r['n']})" for v, r in b["by_validation"].items()) + "; cited " + ", ".join(f"{t}: {r['pct']} (n {r['n']})" for t, r in b["by_ls_citations"].items()))
    md += ["", "Honesty: Lewis & Short cites what an 1879 lexicographer found worth citing, so this is the rare, dictionary-worthy stratum, not overall accuracy; loci come only from works held in Perseus canonical-latinLit editions; gold = the L&S headword; the two *_first baselines are the oracles' own first choice and partly circular with the collatinus/whitaker validation routes (see by_validation); every figure traces to a row in ls_gold_scored.csv."]
    (OUT / "ls_gold_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:14]))


if __name__ == "__main__":
    main()
