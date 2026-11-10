"""MW-Gold, stage 3 — score Sanskrit lemmatizers on the relocated loci (the Sanskrit twin of lsgold/score_la.py).

Systems: every <system>/<stem>.jsonl under data/sanskrit_corpus/caches (skt_caches.py): one line per token of the
project's stream {"i", "surface", "lemma"} (a leading {"#": ...} header line is allowed for restricted runs).
For a single-token locus the system's lemma at token_index is compared with the MW headword; for a compound span the
system's lemmas for the span are joined with vowel sandhi (sktnorm.join_members) and compared with the headword, and
a system whose single lemma for the FIRST token already equals the headword (it kept the compound whole) is also
right. blind = sktnorm.key equality (case, Vedic accent, anusvāra/class-nasal, homonym digits neutral: the headline);
strict = sktnorm.strict (nasals as printed). Strata: text, validation route (dcs / dcs_cpd / dcs_tmesis / vidyut / surface),
span (single / compound), window kind (verse / chapter), how often MW cites the entry with a locus (1 / 2-5 / 6+).
Wilson 95% everywhere. Text rows need >= 100 loci. The vidyut_first row is a context-free lexicon baseline and is
partly circular with the `vidyut` route; the by_validation block shows how much. The byt5 and stanza_sa rows are
trained on DCS data (the oracle); the leaderboard says so beside them.
Outputs data/qc/mwgold/mw_gold_scores.json, mw_gold_table.md, mw_gold_scored.csv.

Run: python -X utf8 -I pipeline/mwgold/score_mw.py [--gold data/qc/mwgold/mw_gold_v0.csv]
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
from sktnorm import key as skey, strict as sstrict, join_members  # noqa: E402

GDM = HERE.parent.parent
OUT = GDM / "data" / "qc" / "mwgold"
CORPUS = GDM / "data" / "sanskrit_corpus"
MIN_TEXT_ROW = 100
BASELINES = {"vidyut_first"}
TRAINED_ON_DCS = {"byt5": "fine-tuned on the DCS (the oracle corpus itself)", "stanza_sa": "trained on UD_Sanskrit-Vedic, a DCS subset (Ṛgveda)",
                  "vidyut_cheda": "statistics partly from DCS"}
TEXT_NAMES = {"rgveda": "Ṛgveda", "manusmrti": "Manusmṛti", "atharvaveda": "Atharvaveda", "bhagavatapurana": "Bhāgavatapurāṇa", "kathasaritsagara": "Kathāsaritsāgara",
              "kumarasambhava": "Kumārasambhava", "kiratarjuniya": "Kirātārjunīya", "meghaduta": "Meghadūta", "satakatraya": "Bhartṛhari", "hitopadesa": "Hitopadeśa",
              "gitagovinda": "Gītagovinda", "buddhacarita": "Buddhacarita", "amarusataka": "Amaruśataka", "rtusamhara": "Ṛtusaṃhāra", "satapathabrahmana": "Śatapathabrāhmaṇa",
              "taittiriyasamhita": "Taittirīyasaṃhitā", "aitareyabrahmana": "Aitareyabrāhmaṇa", "maitrayanisamhita": "Maitrāyaṇīsaṃhitā", "kathakasamhita": "Kāṭhakasaṃhitā",
              "pancavimsabrahmana": "Pañcaviṃśabrāhmaṇa", "gopathabrahmana": "Gopathabrāhmaṇa", "katyayanasrautasutra": "Kātyāyanaśrautasūtra", "apastambasrautasutra": "Āpastambaśrautasūtra",
              "latyayanasrautasutra": "Lāṭyāyanaśrautasūtra", "sankhayanasrautasutra": "Śāṅkhāyanaśrautasūtra", "asvalayanasrautasutra": "Āśvalāyanaśrautasūtra", "kausikasutra": "Kauśikasūtra",
              "asvalayanagrhyasutra": "Āśvalāyanagṛhyasūtra", "gobhilagrhyasutra": "Gobhilagṛhyasūtra", "sankhayanagrhyasutra": "Śāṅkhāyanagṛhyasūtra", "gautamadharmasutra": "Gautamadharmasūtra",
              "apastambadharmasutra": "Āpastambadharmasūtra", "astadhyayi": "Aṣṭādhyāyī (Pāṇini)"}


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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=OUT / "mw_gold_v0.csv")
    ap.add_argument("--system-cache", action="append", type=Path, default=[])
    ap.add_argument("--exclude-pan", action="store_true", help="leave the Aṣṭādhyāyī stratum out of the headline (default: in, reported per text)")
    a = ap.parse_args()
    caches = a.system_cache or [CORPUS / "caches"]
    gold = list(csv.DictReader(a.gold.open(encoding="utf-8")))
    cites_path = OUT / "mw_citation_counts.json"
    cites = json.load(cites_path.open(encoding="utf-8")) if cites_path.exists() else {}

    def cites_tier(L: str) -> str:
        n = cites.get(L.split(".")[0], 0)
        return "unknown" if not n else "1" if n == 1 else "2-5" if n <= 5 else "6+"

    need: dict[str, set[int]] = defaultdict(set)
    for g in gold:
        i0, sp = int(g["token_index"]), int(g["span"])
        for j in range(i0, i0 + sp):
            need[g["text"]].add(j)
    systems: dict[str, dict[tuple[str, int], str]] = {}
    surf: dict[tuple[str, str, int], str] = {}
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
                for line in p.open(encoding="utf-8"):
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if "i" not in r:
                        continue
                    k = int(r["i"])
                    if k in idxs:
                        surf[(sysdir.name, stem, k)] = (r.get("surface") or "").strip()
                        m[(stem, k)] = (r.get("lemma") or "").strip()

    scored = []
    agg: dict[str, Counter] = defaultdict(Counter)
    misaligned: Counter = Counter()
    for g in gold:
        stem, i0, sp = g["text"], int(g["token_index"]), int(g["span"])
        hk, hs = skey(g["headword"]), sstrict(g["headword"])
        ct = cites_tier(g["L"])
        span_kind = "compound" if sp > 1 else "single"
        row = dict(g, cites_tier=ct, span_kind=span_kind)
        for name, m in systems.items():
            lems = [m.get((stem, j)) for j in range(i0, i0 + sp)]
            cs = surf.get((name, stem, i0))
            if lems[0] is not None and cs and skey(cs) != skey(g["surface"]):
                misaligned[name] += 1
                lems = [None]
            if lems[0] is None or not lems[0]:
                row[f"{name}_lemma"] = ""
                row[f"{name}_blind"] = ""
                agg[name]["missing"] += 1
                continue
            if sp == 1:
                lem = lems[0]
                b = skey(lem) == hk
                s = sstrict(lem) == hs
            else:
                parts = [x or "" for x in lems]
                # the key is applied AFTER joining: the nasal fold depends on the next letter (sam + pad -> saṃpad)
                joined = skey(join_members(parts))
                joined_plain = skey("".join(parts))
                b = joined == hk or joined_plain == hk or skey(lems[0]) == hk
                s = sstrict(join_members(parts)) == hs or sstrict("".join(parts)) == hs or sstrict(lems[0]) == hs
                lem = "+".join(parts)
            row[f"{name}_lemma"] = lem
            row[f"{name}_blind"] = int(b)
            row[f"{name}_strict"] = int(s)
            c = agg[name]
            c["n"] += 1
            c["blind"] += b
            c["strict"] += s
            for k2, v in (("text", stem), ("val", g["validation"]), ("span", span_kind), ("window", g["window_kind"]), ("cites", ct)):
                c[f"{k2}:{v}:n"] += 1
                c[f"{k2}:{v}:blind"] += b
        scored.append(row)

    texts = sorted({g["text"] for g in gold})
    res = {"date": datetime.date.today().isoformat(), "gold": a.gold.name, "n_loci": len(gold),
           "loci_per_text": dict(Counter(g["text"] for g in gold).most_common()), "systems": {}}
    for name, c in agg.items():
        if not c["n"]:
            continue   # a cache directory with nothing scored yet (a run in progress)
        res["systems"][name] = {
            "baseline": name in BASELINES, "trained_on_dcs": TRAINED_ON_DCS.get(name, ""), "scored": c["n"], "missing": c["missing"], "misaligned_surface": misaligned.get(name, 0),
            "match_blind": rate(c["blind"], c["n"]), "match_strict": rate(c["strict"], c["n"]),
            "by_text": {t: rate(c[f"text:{t}:blind"], c[f"text:{t}:n"]) for t in texts if c[f"text:{t}:n"] >= MIN_TEXT_ROW},
            "by_validation": {v: rate(c[f"val:{v}:blind"], c[f"val:{v}:n"]) for v in ("dcs", "dcs_cpd", "dcs_tmesis", "vidyut", "surface") if c[f"val:{v}:n"]},
            "by_span": {v: rate(c[f"span:{v}:blind"], c[f"span:{v}:n"]) for v in ("single", "compound") if c[f"span:{v}:n"]},
            "by_window": {v: rate(c[f"window:{v}:blind"], c[f"window:{v}:n"]) for v in ("verse", "chapter") if c[f"window:{v}:n"]},
            "by_mw_citations": {t: rate(c[f"cites:{t}:blind"], c[f"cites:{t}:n"]) for t in ("1", "2-5", "6+", "unknown") if c[f"cites:{t}:n"]}}
    (OUT / "mw_gold_scores.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = list(dict.fromkeys(k for r in scored for k in r))
    with (OUT / "mw_gold_scored.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(scored)
    big = [t for t in texts if res["loci_per_text"].get(t, 0) >= MIN_TEXT_ROW]
    md = [f"# MW-Gold v0 — Sanskrit lemmatizer accuracy on the dictionary-cited stratum ({res['date']})", "",
          f"{len(gold)} relocated loci over {len(texts)} texts. Match = headword equality after case, accent, anusvāra and homonym-digit normalisation (blind); strict keeps nasals as printed. Compound spans are judged on the sandhi-joined member lemmas. Wilson 95% in brackets.", "",
          "| system | loci | blind % | strict % | " + " | ".join(TEXT_NAMES.get(t, t)[:18] for t in big) + " |",
          "|---|---|---|---|" + "---|" * len(big)]
    for name, b in sorted(res["systems"].items(), key=lambda kv: (kv[1]["baseline"], -(kv[1]["match_blind"]["pct"] or 0))):
        cells = [f"{b['by_text'][t]['pct']}" if t in b["by_text"] else "—" for t in big]
        tag = " (baseline)" if b["baseline"] else (" (trained on DCS)" if b["trained_on_dcs"] else "")
        md.append(f"| {name}{tag} | {b['scored']} | **{b['match_blind']['pct']}** [{b['match_blind']['wilson95'][0]}–{b['match_blind']['wilson95'][1]}] | {b['match_strict']['pct']} | " + " | ".join(cells) + " |")
    md += ["", "By validation route, span, window and MW citation frequency (blind %):", ""]
    for name, b in res["systems"].items():
        md.append(f"- {name}: " + ", ".join(f"{v} {r['pct']} (n {r['n']})" for v, r in b["by_validation"].items())
                  + "; " + ", ".join(f"{v} {r['pct']} (n {r['n']})" for v, r in b["by_span"].items())
                  + "; " + ", ".join(f"{v}-window {r['pct']} (n {r['n']})" for v, r in b["by_window"].items())
                  + "; cited " + ", ".join(f"{t}: {r['pct']} (n {r['n']})" for t, r in b["by_mw_citations"].items()))
    md += ["", "Honesty: Monier-Williams cites what its lexicographers found worth citing: the rare, dictionary-worthy stratum, not overall accuracy. The gold lemma is the DCS annotators' lemma (routes dcs, dcs_cpd) where it equals MW's headword, so systems trained on the DCS (byt5, stanza_sa) are scored on their own training distribution and partly on their training sentences; vidyut_first is the first analysis of the oracle behind the vidyut route. Every figure traces to a row in mw_gold_scored.csv."]
    (OUT / "mw_gold_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:14]))


if __name__ == "__main__":
    main()
