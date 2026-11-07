"""T3 v0 — Attributed Term Map for any First1K author (2026-11-06; ROADMAP tool T3).

Phase 2/3 generalised: for author X (tlgNNNN) in the project's odyCy-lemmatized First1K reference
corpus, compute the lemmas X over-uses against the rest of First1K (+ Galen), tier them by Perseus-LSJ
sense count, flag lemma-inventory artifacts with Dilemma, give three attested contexts each, and carry
the T1 error bar when a per-author audit summary exists. Report only; nothing is patched.

  domain     = X's works in data/lemmatized/reference (odyCy lemmas, as frozen in v2.0)
  reference  = outputs/lemma_frequency_reference.json + lemma_frequency_galen.json minus X's own counts
  keyness    = Dunning log-likelihood (stage 05 formula), min domain freq (default 5; 3 for authors < 100k tokens)
  tiers      = LSJ sense count via data/lsj/_lsj_index.json (absent / thin / rich) as in stage 07
  artifact flag = Dilemma (lsj convention, guess off) lemmatizes the lemma string: same headword or not
  M1 share   = Morpheus admissibility of the lemma over its surfaces where the Galen cache covers them

Usage (audit venv, Dilemma installed):
  .venv/Scripts/python -X utf8 pipeline/t3_author_term_map.py --author tlg2039 [--audit-summary <dir>/audit_summary.json]
Outputs: outputs/t3/<tlg>/term_map.csv, punch_list.csv (thin+absent key lemmas), summary.json, README.md
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402
from lib.config import load_config  # noqa: E402
from lib.stoplists import default_stoplist_dir, load_stoplist  # noqa: E402

LEM = ROOT / "data" / "lemmatized" / "reference"
OUT = ROOT / "outputs" / "t3"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


def log_likelihood(a, b, c, d) -> float:
    if a == 0 and b == 0:
        return 0.0
    e1 = c * (a + b) / (c + d)
    e2 = d * (a + b) / (c + d)
    ll = 0.0
    if a > 0:
        ll += a * math.log(a / e1)
    if b > 0:
        ll += b * math.log(b / e2)
    ll *= 2
    return ll if (a / c) > (b / d) else -ll


def tier_of(n: int | None) -> str:
    if n is None or n <= 0:
        return "absent"
    return "thin" if n == 1 else "rich"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", required=True, help="tlgNNNN")
    ap.add_argument("--audit-summary", type=Path, default=None, help="per-author audit_summary.json from the kit (T1 error bar)")
    ap.add_argument("--min-ll", type=float, default=15.13)
    ap.add_argument("--contexts", type=int, default=3)
    ap.add_argument("--no-dilemma", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    cfg = load_config()
    out = OUT / a.author
    out.mkdir(parents=True, exist_ok=True)

    # stoplists (same files as stage 05)
    stop: set[str] = set()
    sd = default_stoplist_dir(ROOT)
    if sd.exists():
        for p in sd.glob("*.txt"):
            stop |= load_stoplist(p)

    # domain
    works = sorted(p for p in LEM.glob("*.jsonl") if p.stem.split("_")[3].split(".")[0] == a.author)
    if not works:
        raise SystemExit(f"no works for {a.author} under {LEM}")
    dom = Counter()
    pos_of: dict[str, Counter] = defaultdict(Counter)
    surf_of: dict[str, Counter] = defaultdict(Counter)
    occ: dict[str, list[tuple[str, str]]] = defaultdict(list)
    n_dom = 0
    for p in works:
        toks = [json.loads(l) for l in p.open(encoding="utf-8")]
        for i, t in enumerate(toks):
            lem = nfc(t.get("lemma", ""))
            if not lem:
                continue
            n_dom += 1
            dom[lem] += 1
            pos_of[lem][t.get("pos", "")] += 1
            surf_of[lem][nfc(t.get("surface", ""))] += 1
            if len(occ[lem]) < 40:
                lo, hi = max(0, i - 6), min(len(toks), i + 7)
                occ[lem].append((p.stem, " ".join(f"[{x['surface']}]" if j == i else x["surface"] for j, x in enumerate(toks[lo:hi], lo))))
    min_freq = int(cfg.get("min_domain_frequency", 5)) if n_dom >= 100_000 else 3

    # reference = First1K reference (minus author) + Galen
    ref_json = json.load((ROOT / "outputs" / "lemma_frequency_reference.json").open(encoding="utf-8"))
    gal_json = json.load((ROOT / "outputs" / "lemma_frequency_galen.json").open(encoding="utf-8"))
    ref = Counter({nfc(k): v["raw_count"] for k, v in ref_json["lemmas"].items()})
    for k, v in gal_json["lemmas"].items():
        ref[nfc(k)] += v["raw_count"]
    n_ref_total = int(ref_json["corpus_total_tokens"]) + int(gal_json["corpus_total_tokens"])
    for lem, c in dom.items():  # the author's own tokens are inside the reference file: take them out
        ref[lem] -= c
        if ref[lem] <= 0:
            del ref[lem]
    n_ref = n_ref_total - n_dom

    # LSJ, Morpheus
    lsj = json.load((ROOT / "data" / "lsj" / "_lsj_index.json").open(encoding="utf-8"))
    morph: dict[str, set[str]] = {}
    with (ROOT / "data" / "qc" / "h3m" / "cache" / "morpheus_by_surface.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok") and r.get("lemmas"):
                morph[nfc(r["surface_nfc"])] = {blind(x) for x in r["lemmas"]}

    dil = None
    if not a.no_dilemma:
        try:
            from dilemma import Dilemma  # type: ignore

            dil = Dilemma(lang="grc", convention="lsj")
        except Exception as exc:  # report, don't fail
            print(f"Dilemma unavailable ({exc}); artifact flag left blank", flush=True)

    rows = []
    for lem, c in dom.items():
        if c < min_freq or lem in stop:
            continue
        b = ref.get(lem, 0)
        ll = log_likelihood(c, b, n_dom, n_ref)
        if ll < a.min_ll:
            continue
        hit = lsj.get(lemma_to_lookup_key(lem))
        senses = int(hit.get("lsj_sense_count") or 0) if hit else None
        pos = pos_of[lem].most_common(1)[0][0]
        adm = inadm = 0
        for s, n in surf_of[lem].items():
            if s in morph:
                if blind(lem) in morph[s]:
                    adm += n
                else:
                    inadm += n
        dil_hw = ""
        if dil is not None:
            try:
                dil_hw = nfc(dil.lemmatize(lem, guess=False) or "")
            except Exception:
                dil_hw = ""
        by_work: dict[str, list[str]] = defaultdict(list)
        for w, ctx in occ[lem]:
            by_work[w].append(ctx)
        ctxs = [by_work[w][0] for w in sorted(by_work, key=lambda k: -len(by_work[k]))][: a.contexts]
        rows.append({
            "lemma": lem, "pos": pos, "author_raw": c, "author_per10k": round(1e4 * c / n_dom, 4), "ref_raw": b,
            "ref_per10k": round(1e4 * b / n_ref, 4), "log_likelihood": round(ll, 2), "lsj_exists": int(hit is not None),
            "lsj_sense_count": senses if senses is not None else "", "lsj_tier": tier_of(senses),
            "lsj_headword": hit.get("lsj_headword", "") if hit else "",
            "dilemma_headword_of_lemma": dil_hw, "dilemma_agrees": "" if dil is None else int(bool(dil_hw) and blind(dil_hw) == blind(lem)),
            "artifact_flag": "" if dil is None else ("dilemma_differs" if dil_hw and blind(dil_hw) != blind(lem) else ("dilemma_unresolved" if not dil_hw else "")),
            "m1_admissible_share": round(adm / (adm + inadm), 3) if adm + inadm else "", "m1_covered_tokens": adm + inadm,
            "n_works": len(by_work), "surfaces": "; ".join(f"{s}:{n}" for s, n in surf_of[lem].most_common(4)),
            "context_1": ctxs[0] if ctxs else "", "context_2": ctxs[1] if len(ctxs) > 1 else "", "context_3": ctxs[2] if len(ctxs) > 2 else "",
        })
    rows.sort(key=lambda r: -r["log_likelihood"])
    cols = list(rows[0].keys()) if rows else []
    with (out / "term_map.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    punch = [r for r in rows if r["lsj_tier"] in ("thin", "absent") and r["pos"] in ("NOUN", "ADJ", "VERB")]
    with (out / "punch_list.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(punch)

    t1 = {}
    if a.audit_summary and a.audit_summary.exists():
        s = json.load(a.audit_summary.open(encoding="utf-8"))
        m1 = s["m1_admissibility"]["systems"]
        m2 = s["m2_agreement"]["population"]
        t1 = {"source": str(a.audit_summary),
              "m1_odycy_admissible_pct": m1.get("reference", {}).get("token_weighted", {}).get("admissible_pct_of_analyzable"),
              "m1_odycy_not_in_cache_pct": m1.get("reference", {}).get("token_weighted", {}).get("not_in_cache_pct_of_all"),
              "m1_dilemma_admissible_pct_strict": m1.get("dilemma", {}).get("token_weighted", {}).get("admissible_pct_of_analyzable"),
              "m1_dilemma_admissible_pct_article_neutral": m1.get("dilemma", {}).get("article_neutral_admissible_pct_of_analyzable"),
              "m2_odycy_dilemma_agree_pct_strict": (m2.get("pairwise") or {}).get("reference__dilemma", {}).get("agree_pct"),
              "m2_odycy_dilemma_agree_pct_article_neutral": (m2.get("pairwise_article_neutral") or {}).get("reference__dilemma", {}).get("agree_pct")}
    summary = {
        "date": "2026-11-06", "tool": "T3 attributed term map v0", "author": a.author, "works": len(works), "author_tokens": n_dom,
        "reference_tokens": n_ref, "min_domain_frequency": min_freq, "min_log_likelihood": a.min_ll,
        "key_lemmas": len(rows), "tiers": dict(Counter(r["lsj_tier"] for r in rows)),
        "punch_list_thin_absent_noun_adj_verb": len(punch),
        "artifact_flags": dict(Counter(r["artifact_flag"] for r in rows if r["artifact_flag"])) if dil else "dilemma not run",
        "absent_tier_dilemma_differs": sum(1 for r in rows if r["lsj_tier"] == "absent" and r["artifact_flag"] == "dilemma_differs"),
        "absent_tier_n": sum(1 for r in rows if r["lsj_tier"] == "absent"),
        "t1_error_bar": t1 or "no per-author audit summary given",
        "elapsed_s": round(time.time() - t0, 1),
        "caveats": ["odyCy lemmas as frozen in v2.0; the absent tier is artifact-laden (Galen: 82-85%), use the Dilemma flag",
                    "reference = First1K + Galen minus the author; Open Greek not used here (T0 showed reference size barely matters)",
                    "LSJ = Perseus digitisation; 'absent' means absent from it",
                    "Morpheus coverage is the Galen cache: M1 share only where covered"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    top = rows[:15]
    md = [f"# T3 term map — {a.author} ({n_dom:,} odyCy tokens, {len(works)} works) — {summary['date']}", "",
          f"{len(rows)} key lemmas (LL ≥ {a.min_ll}, domain freq ≥ {min_freq}) against {n_ref:,} reference tokens; tiers {summary['tiers']}; "
          f"punch list (thin + absent, NOUN/ADJ/VERB) {len(punch)}; absent-tier lemmas Dilemma re-lemmatizes elsewhere: {summary['absent_tier_dilemma_differs']}/{summary['absent_tier_n']}.", "",
          "| lemma | pos | per10k author / ref | LL | LSJ tier | Dilemma headword | flag |", "|---|---|---|---|---|---|---|"]
    for r in top:
        md.append(f"| {r['lemma']} | {r['pos']} | {r['author_per10k']} / {r['ref_per10k']} | {r['log_likelihood']} | {r['lsj_tier']} | {r['dilemma_headword_of_lemma']} | {r['artifact_flag']} |")
    md += ["", f"T1 error bar: {json.dumps(t1, ensure_ascii=False) if t1 else 'none given'}", "", "Report only. " + " ".join(summary["caveats"])]
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("author", "author_tokens", "key_lemmas", "tiers", "punch_list_thin_absent_noun_adj_verb", "absent_tier_dilemma_differs", "absent_tier_n", "elapsed_s")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
