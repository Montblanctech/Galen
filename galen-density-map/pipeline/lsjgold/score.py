"""LSJ-Gold, stage 2 — score lemmatizers on the relocated loci (spec: lsj_gold_benchmark_spec.md).

Systems scored: ``odycy`` = the lemma at the gold token index in the project's frozen JSONL; ``dilemma`` =
Open Greek Dilemma on the gold surface (lsj convention, guess off; context-free, memoised); any further
system whose per-work token cache exists under --system-cache <dir>/<system>/<stem>.jsonl (as written by
`greek-lemma-audit run` / `--precompute-only`: Stanza, Stoicheia...). Match = accent-blind headword equality
(strict also reported); the article/adverb convention layer is reported beside strict, never instead.
Strata: author, LSJ sense tier of the headword, validation route. Wilson 95% everywhere.
Outputs data/qc/lsjgold/lsj_gold_scores.json, lsj_gold_table.md, lsj_gold_scored.csv.
"""
from __future__ import annotations

import argparse
import datetime
import csv
import json
import math
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
GDM = PIPE.parent
sys.path.insert(0, str(PIPE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

OUT = GDM / "data" / "qc" / "lsjgold"
MIN_AUTHOR_ROW = 100


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


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


def stem_for(row: dict, held: dict) -> str:
    return held[(row["author"], row["work"])]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=OUT / "lsj_gold_v0.csv")
    ap.add_argument("--system-cache", action="append", type=Path, default=[], help="dir(s) with <system>/<stem>.jsonl caches")
    ap.add_argument("--no-dilemma", action="store_true")
    ap.add_argument("--from-scored", type=Path, help="take every system's lemma per locus from an earlier lsj_gold_scored.csv "
                    "instead of the caches and Dilemma (rescoring a corrected gold, e.g. 0.1.1, on the same system outputs)")
    a = ap.parse_args()
    gold = list(csv.DictReader(a.gold.open(encoding="utf-8")))
    # held stems
    held = {}
    for xml_dir in (GDM / "data" / "reference_corpus" / "raw_xml", GDM / "data" / "raw_xml", GDM / "data" / "perseus_corpus" / "raw_xml"):
        for x in xml_dir.glob("urn_cts_greekLit_tlg*.xml"):
            parts = x.stem.split("_")[3].split(".")
            held.setdefault((parts[0], parts[1]), x.stem)
    lsj = json.load((GDM / "data" / "lsj" / "_lsj_index.json").open(encoding="utf-8"))
    cites_path = OUT / "lsj_citation_counts.json"   # entry key -> LSJ citations with a CTS URN (lsj_citation_counts.py)
    cites = json.load(cites_path.open(encoding="utf-8")) if cites_path.exists() else {}

    def cites_tier(entry_key: str) -> str:
        n = cites.get(entry_key, 0)
        return "unknown" if not n else "1" if n == 1 else "2-5" if n <= 5 else "6+"

    # odyCy lemmas at indices
    need = defaultdict(set)
    for g in gold:
        need[stem_for(g, held)].add(int(g["token_index"]))
    if a.from_scored:
        # the earlier run already dropped misaligned rows to "" (missing), so they stay missing here
        need.clear()
        a.system_cache, a.no_dilemma = [], True
    ody: dict[tuple[str, int], str] = {}
    for stem, idxs in need.items():
        for lem_dir in (GDM / "data" / "lemmatized" / "reference", GDM / "data" / "lemmatized" / "galen"):
            p = lem_dir / f"{stem}.jsonl"
            if p.exists():
                for i, line in enumerate(p.open(encoding="utf-8")):
                    if i in idxs:
                        ody[(stem, i)] = nfc(json.loads(line).get("lemma", ""))
                break
    systems: dict[str, dict[tuple[str, int], str]] = {"odycy": ody}
    surf: dict[tuple[str, str, int], str] = {}   # (system, stem, index) -> cached surface, for the alignment check
    misaligned: Counter = Counter()
    # cached systems
    for d in a.system_cache:
        for sysdir in Path(d).iterdir():
            if not sysdir.is_dir():
                continue
            m = systems.setdefault(sysdir.name, {})
            for stem, idxs in need.items():
                p = sysdir / f"{stem}.jsonl"
                if p.exists():
                    for i, line in enumerate(p.open(encoding="utf-8")):
                        r = json.loads(line)
                        k = int(r.get("i", i))
                        if k in idxs:
                            # a cache made from another tokenisation (the kit's own) drifts off the project's token stream:
                            # the surface at the index must match the gold surface, else the row is missing, never scored
                            surf[(sysdir.name, stem, k)] = nfc(r.get("surface", ""))
                            m[(stem, k)] = nfc(r.get("lemma", ""))
    # dilemma on surfaces
    if not a.no_dilemma:
        try:
            from dilemma import Dilemma  # type: ignore

            dil = Dilemma(lang="grc", convention="lsj")
            memo = {}
            dl = {}
            for g in gold:
                s = g["surface"]
                if s not in memo:
                    try:
                        memo[s] = nfc(dil.lemmatize(s, guess=False) or "")
                    except Exception:
                        memo[s] = ""
                dl[(stem_for(g, held), int(g["token_index"]))] = memo[s]
            systems["dilemma"] = dl
        except Exception as exc:
            print(f"dilemma unavailable: {exc}", flush=True)

    if a.from_scored:
        systems, surf = {}, {}
        for r in csv.DictReader(a.from_scored.open(encoding="utf-8")):
            key = (stem_for(r, held), int(r["token_index"]))
            for col, v in r.items():
                if col.endswith("_lemma"):
                    m = systems.setdefault(col[: -len("_lemma")], {})
                    if v:
                        m[key] = v

    ARTICLE = {"ἡ", "τό", "τῶν", "τοῦ", "τῆς", "τῷ", "τῇ", "τόν", "τήν", "οἱ", "αἱ", "τά", "τοῖς", "ταῖς", "τούς", "τάς"}

    def conv(l: str) -> str:
        return "ὁ" if nfc(l) in ARTICLE else nfc(l)

    scored = []
    agg: dict[str, Counter] = defaultdict(Counter)
    for g in gold:
        key = (stem_for(g, held), int(g["token_index"]))
        hk = g["headword_key"]
        hit = lsj.get(lemma_to_lookup_key(g["headword"]))
        senses = int(hit.get("lsj_sense_count") or 0) if hit else 0
        tier = "absent" if senses == 0 else ("thin" if senses == 1 else "rich")
        ct = cites_tier(g.get("entry_key", ""))
        row = dict(g, lsj_tier=tier, cites_tier=ct)
        for name, m in systems.items():
            lem = m.get(key)
            cs = surf.get((name,) + key)
            if lem is not None and cs is not None and cs and blind(cs) != blind(g["surface"]):
                misaligned[name] += 1
                lem = None
            row[f"{name}_lemma"] = lem if lem is not None else ""
            if lem is None or lem == "":
                row[f"{name}_blind"] = ""
                agg[name]["missing"] += 1
                continue
            b = blind(lem) == hk
            s = nfc(lem) == nfc(g["headword"])
            c = blind(conv(lem)) == hk
            row[f"{name}_blind"] = int(b)
            row[f"{name}_strict"] = int(s)
            agg[name]["n"] += 1
            agg[name]["blind"] += b
            agg[name]["strict"] += s
            agg[name]["conv"] += c
            agg[name][f"author:{g['author']}:n"] += 1
            agg[name][f"author:{g['author']}:blind"] += b
            agg[name][f"tier:{tier}:n"] += 1
            agg[name][f"tier:{tier}:blind"] += b
            agg[name][f"val:{g['validation']}:n"] += 1
            agg[name][f"val:{g['validation']}:blind"] += b
            agg[name][f"cites:{ct}:n"] += 1
            agg[name][f"cites:{ct}:blind"] += b
        scored.append(row)

    authors = sorted({g["author"] for g in gold})
    res = {"date": datetime.date.today().isoformat(), "gold": str(a.gold.name), "n_loci": len(gold), "loci_per_author": dict(Counter(g["author"] for g in gold)),
           "systems": {}}
    for name, c in agg.items():
        block = {"scored": c["n"], "missing": c["missing"], "misaligned_surface": misaligned.get(name, 0), "match_blind": rate(c["blind"], c["n"]), "match_strict": rate(c["strict"], c["n"]),
                 "match_article_neutral": rate(c["conv"], c["n"]),
                 "by_author": {au: rate(c[f"author:{au}:blind"], c[f"author:{au}:n"]) for au in authors if c[f"author:{au}:n"] >= MIN_AUTHOR_ROW},
                 "by_lsj_tier": {t: rate(c[f"tier:{t}:blind"], c[f"tier:{t}:n"]) for t in ("rich", "thin", "absent") if c[f"tier:{t}:n"]},
                 "by_validation": {v: rate(c[f"val:{v}:blind"], c[f"val:{v}:n"]) for v in ("morpheus", "quoted") if c[f"val:{v}:n"]},
                 "by_lsj_citations": {t: rate(c[f"cites:{t}:blind"], c[f"cites:{t}:n"]) for t in ("1", "2-5", "6+", "unknown") if c[f"cites:{t}:n"]}}
        res["systems"][name] = block
    (OUT / "lsj_gold_scores.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = list(dict.fromkeys(k for r in scored for k in r))  # union: Perseus rows have no odyCy strict field
    with (OUT / "lsj_gold_scored.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(scored)
    from lsjgold_names import author_name
    names = {au: author_name(au) for au in set(authors) | set(res["loci_per_author"])}
    md = [f"# LSJ-Gold v0 — lemmatizer accuracy on the dictionary-cited stratum ({res['date']})", "",
          f"{len(gold)} relocated loci ({', '.join(f'{names.get(k,k)} {v}' for k, v in res['loci_per_author'].items())}). Match = accent-blind headword equality; article-neutral maps ἡ/τό/τῶν… → ὁ. Wilson 95% in brackets.", "",
          "| system | loci | blind % | strict % | article-neutral % | " + " | ".join(names.get(au, au) for au in authors) + " |",
          "|---|---|---|---|---|" + "---|" * len(authors)]
    for name, b in res["systems"].items():
        cells = []
        for au in authors:
            r = b["by_author"].get(au)
            cells.append(f"{r['pct']} ({r['n']})" if r else "—")
        md.append(f"| {name} | {b['scored']} | **{b['match_blind']['pct']}** [{b['match_blind']['wilson95'][0]}–{b['match_blind']['wilson95'][1]}] | {b['match_strict']['pct']} | {b['match_article_neutral']['pct']} | " + " | ".join(cells) + " |")
    md += ["", "By LSJ sense tier of the cited headword (blind %):", ""]
    for name, b in res["systems"].items():
        md.append(f"- {name}: " + ", ".join(f"{t} {r['pct']} (n {r['n']})" for t, r in b["by_lsj_tier"].items()) + "; by validation route: " + ", ".join(f"{v} {r['pct']} (n {r['n']})" for v, r in b["by_validation"].items()))
    md += ["", "Honesty: LSJ cites what a 1940 lexicographer found worth citing, so this is the rare, dictionary-worthy stratum, not overall accuracy; the Perseus LSJ is incomplete; loci come only from works this project holds in First1K editions; odyCy lemmas are the project's frozen v2.0 run; Dilemma is context-free on the surface; gold = LSJ headword, convention differences counted against the system in the strict and blind columns and partly undone in the article-neutral one."]
    (OUT / "lsj_gold_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
