"""Stage 12 — punch-list headword map under an independent lemmatizer (ROADMAP item 8 prep, 2026-11-06).

T0 (outputs/t0) showed that 899 of the 1,433 punch-list lemmas are not Dilemma headwords, 690 of
them in the ``absent`` tier. This stage asks, lemma by lemma, *what Dilemma makes of the same
tokens*: every Galen-medical surface that odyCy lemmatized to a punch-list lemma is re-lemmatized
with Open Greek's Dilemma (lsj convention; ``guess=False`` = lexicon+rules only, ``guess=True`` =
also the transformer), the resulting headword distribution is recorded, and the top headword is
looked up in the project's LSJ index (same accent-blind Beta Code key as stage 06).

Each punch lemma gets one machine class (REPORT ONLY; the punch list itself is not modified):
  same_headword          Dilemma's majority headword is the odyCy lemma (accent-blind). Two lemmatizers agree.
  relemmatized_lsj       Dilemma maps the tokens to a different headword that HAS an LSJ entry
                         -> the odyCy lemma is an artifact (inflected form / mis-accent / fragment) of a described word.
  relemmatized_no_lsj    Dilemma maps to a different headword that also has no LSJ entry.
  unresolved             Dilemma (guess=False) returns no lemma for the majority of the tokens
                         (the guess=True result is recorded separately, never used for the class).
  split                  no Dilemma headword reaches 50% of the tokens (odyCy pooled several words).

Also recorded: Dilemma's lemma for the odyCy lemma *string* itself (an inflected form lemmatizes
to something else; a headword lemmatizes to itself), the M1 Morpheus admissibility share of the
odyCy lemma over its own surfaces (offline cache, accent-blind key), whether the resolved headword is
already a key lemma in the frozen Map A (outputs/keyness_scores.csv) and whether it sits elsewhere
in the punch list.

Outputs (outputs/phase3/): absent_tier_headword_map.csv (all 1,433 rows, tier column),
absent_tier_headword_summary.json, README_headword_map.md. Run under the audit venv
(``.venv/Scripts/python -X utf8 pipeline/12_absent_tier_headword_map.py``); Dilemma data must be installed.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402
from lib.census import load_census, medical_urn_stems  # noqa: E402
from lib.config import load_config  # noqa: E402

OUT = ROOT / "outputs" / "phase3"
DATE = "2026-11-06"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    """Accent-blind comparison key (same as M1's primary key)."""
    return lemma_to_lookup_key(nfc(s))


def tier_of(sense_count: int) -> str:
    if sense_count <= 0:
        return "absent"
    return "thin" if sense_count == 1 else "rich"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    cfg = load_config()
    census = load_census((ROOT.parent / "phase1" / "galen_ogl_census.json").resolve())
    med_stems = medical_urn_stems(cfg, census)
    OUT.mkdir(parents=True, exist_ok=True)

    punch = list(csv.DictReader((ROOT / "outputs" / "punch_list.csv").open(encoding="utf-8")))
    punch_lemmas = {nfc(r["lemma"]): r for r in punch}
    punch_blind = {blind(l): l for l in punch_lemmas}
    print(f"punch list: {len(punch)} lemmas", flush=True)

    # --- surfaces per punch lemma, Galen medical only
    surf_by_lemma: dict[str, Counter] = defaultdict(Counter)
    n_tok = 0
    lem_dir = ROOT / "data" / "lemmatized" / "galen"
    for p in sorted(lem_dir.glob("*.jsonl")):
        if p.stem not in med_stems:
            continue
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                n_tok += 1
                lem = nfc(row.get("lemma", ""))
                if lem in punch_lemmas:
                    surf_by_lemma[lem][nfc(row.get("surface", ""))] += 1
    print(f"scanned {n_tok} medical tokens; {len(surf_by_lemma)} punch lemmas have surfaces ({time.time()-t0:.0f}s)", flush=True)

    # --- Morpheus admissibility of the odyCy lemma over its surfaces (offline cache)
    morph: dict[str, set[str]] = {}
    morph_ok: dict[str, bool] = {}
    cache = ROOT / "data" / "qc" / "h3m" / "cache" / "morpheus_by_surface.jsonl"
    with cache.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            s = nfc(r.get("surface_nfc", ""))
            morph_ok[s] = bool(r.get("ok"))
            morph[s] = {blind(x) for x in (r.get("lemmas") or [])}
    print(f"morpheus cache: {len(morph)} surfaces", flush=True)

    # --- LSJ index (stage 06 key)
    lsj = json.load((ROOT / "data" / "lsj" / "_lsj_index.json").open(encoding="utf-8"))

    def lsj_hit(lemma: str) -> dict:
        h = lsj.get(lemma_to_lookup_key(nfc(lemma)))
        if not h:
            return {"exists": False, "senses": 0, "headword": ""}
        return {"exists": bool(h.get("lsj_exists", True)), "senses": int(h.get("lsj_sense_count") or 0), "headword": h.get("lsj_headword", "")}

    # --- Map A key lemmas (frozen)
    keyA = {nfc(r["lemma"]): float(r["log_likelihood"]) for r in csv.DictReader((ROOT / "outputs" / "keyness_scores.csv").open(encoding="utf-8"))
            if r.get("direction", "overused") == "overused"}
    keyA_blind = {blind(l): l for l in keyA}

    # --- Dilemma
    from dilemma import Dilemma  # type: ignore

    dil = Dilemma(lang="grc", convention="lsj")
    dil_version = getattr(sys.modules["dilemma"], "__version__", "unknown")
    memo_strict: dict[str, str] = {}
    memo_guess: dict[str, str] = {}

    def lem(surface: str, guess: bool) -> str:
        memo = memo_guess if guess else memo_strict
        if surface not in memo:
            try:
                memo[surface] = nfc(dil.lemmatize(surface, guess=guess) or "")
            except Exception:
                memo[surface] = ""
        return memo[surface]

    rows = []
    cls_count: Counter = Counter()
    cls_by_tier: dict[str, Counter] = defaultdict(Counter)
    for r in punch:
        lemma = nfc(r["lemma"])
        tier = r["lsj_tier"]
        surfs = surf_by_lemma.get(lemma, Counter())
        n = sum(surfs.values())
        dist_strict: Counter = Counter()
        dist_guess: Counter = Counter()
        n_unres = 0
        adm = inadm = noan = nocache = 0
        lb = blind(lemma)
        for s, c in surfs.items():
            hs = lem(s, False)
            hg = lem(s, True)
            if hs:
                dist_strict[hs] += c
            else:
                n_unres += c
            if hg:
                dist_guess[hg] += c
            if s in morph:
                if not morph_ok.get(s) or not morph[s]:
                    noan += c
                elif lb in morph[s]:
                    adm += c
                else:
                    inadm += c
            else:
                nocache += c
        top_hw, top_n = (dist_strict.most_common(1)[0] if dist_strict else ("", 0))
        top_hw_g, top_n_g = (dist_guess.most_common(1)[0] if dist_guess else ("", 0))
        share = top_n / n if n else 0.0
        unres_share = n_unres / n if n else 1.0
        self_lem_strict = lem(lemma, False)
        self_lem_guess = lem(lemma, True)
        hit_top = lsj_hit(top_hw) if top_hw else {"exists": False, "senses": 0, "headword": ""}

        if n == 0:
            cls = "no_surfaces"
        elif unres_share > 0.5:
            cls = "unresolved"
        elif share < 0.5:
            cls = "split"
        elif blind(top_hw) == lb:
            cls = "same_headword"
        elif hit_top["exists"]:
            cls = "relemmatized_lsj"
        else:
            cls = "relemmatized_no_lsj"
        cls_count[cls] += 1
        cls_by_tier[tier][cls] += 1

        analyzable = adm + inadm
        rows.append({
            "lemma": lemma, "lsj_tier": tier, "pos": r["pos"], "galen_raw_count": r["galen_raw_count"],
            "log_likelihood": r["log_likelihood"], "n_surface_tokens": n, "n_surface_types": len(surfs),
            "machine_class": cls,
            "dilemma_top_headword": top_hw, "dilemma_top_share": round(share, 3),
            "dilemma_unresolved_share": round(unres_share, 3),
            "dilemma_headword_distribution": "; ".join(f"{h}:{c}" for h, c in dist_strict.most_common(5)),
            "dilemma_guess_top_headword": top_hw_g, "dilemma_guess_top_share": round(top_n_g / n, 3) if n else 0.0,
            "dilemma_lemma_of_lemma_string": self_lem_strict, "dilemma_guess_lemma_of_lemma_string": self_lem_guess,
            "lemma_string_is_own_headword": int(bool(self_lem_strict) and blind(self_lem_strict) == lb),
            "top_headword_lsj_exists": int(hit_top["exists"]), "top_headword_lsj_senses": hit_top["senses"],
            "top_headword_lsj_tier": tier_of(hit_top["senses"]) if hit_top["exists"] else "absent",
            "top_headword_lsj_form": hit_top["headword"],
            "top_headword_key_in_mapA": int(blind(top_hw) in keyA_blind) if top_hw else 0,
            "top_headword_mapA_ll": round(keyA[keyA_blind[blind(top_hw)]], 2) if top_hw and blind(top_hw) in keyA_blind else "",
            "top_headword_elsewhere_in_punch": int(blind(top_hw) in punch_blind and punch_blind[blind(top_hw)] != lemma) if top_hw else 0,
            "m1_admissible_share": round(adm / analyzable, 3) if analyzable else "",
            "m1_inadmissible_tokens": inadm, "m1_no_analysis_tokens": noan, "m1_not_in_cache_tokens": nocache,
            "example_surfaces": "; ".join(f"{s}:{c}" for s, c in surfs.most_common(4)),
        })

    # --- summary
    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    by_tier = {}
    for tier in ("absent", "thin"):
        tr = [x for x in rows if x["lsj_tier"] == tier]
        re_lsj = [x for x in tr if x["machine_class"] == "relemmatized_lsj"]
        by_tier[tier] = {
            "n": len(tr),
            "classes": dict(cls_by_tier[tier]),
            "classes_pct": {k: pct(v, len(tr)) for k, v in cls_by_tier[tier].items()},
            "relemmatized_lsj_resolved_tier": dict(Counter(x["top_headword_lsj_tier"] for x in re_lsj)),
            "relemmatized_lsj_headword_key_in_mapA": sum(x["top_headword_key_in_mapA"] for x in re_lsj),
            "relemmatized_lsj_headword_elsewhere_in_punch": sum(x["top_headword_elsewhere_in_punch"] for x in re_lsj),
            "lemma_string_is_own_headword": sum(x["lemma_string_is_own_headword"] for x in tr),
            "m1_inadmissible_majority": sum(1 for x in tr if x["m1_admissible_share"] != "" and x["m1_admissible_share"] < 0.5),
            "distinct_resolved_headwords": len({blind(x["dilemma_top_headword"]) for x in re_lsj}),
        }
    summary = {
        "date": DATE, "stage": "12_absent_tier_headword_map", "report_only": True,
        "dilemma_version": dil_version, "dilemma_convention": "lsj",
        "medical_tokens_scanned": n_tok, "punch_lemmas": len(punch),
        "classes_all": dict(cls_count), "by_tier": by_tier,
        "class_definitions": {
            "same_headword": "Dilemma majority headword == odyCy lemma (accent-blind)",
            "relemmatized_lsj": "Dilemma majority headword differs and has an LSJ entry: odyCy lemma is an artifact of a described word",
            "relemmatized_no_lsj": "Dilemma majority headword differs and has no LSJ entry",
            "unresolved": "Dilemma guess=False returns nothing for >50% of the tokens",
            "split": "no Dilemma headword reaches 50% of the tokens",
            "no_surfaces": "no medical token carries this lemma (should be 0)",
        },
        "elapsed_s": round(time.time() - t0, 1),
    }
    cols = list(rows[0].keys())
    with (OUT / "absent_tier_headword_map.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (OUT / "absent_tier_headword_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
