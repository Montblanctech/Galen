#!/usr/bin/env python3
"""Standing QC checks — print every full pipeline run."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.census import filter_galen_works, load_census
from lib.config import load_config, project_root, resolve_path
from lib.greek_normalize import casefold_greek
from lib.io_utils import read_json, read_jsonl, write_json
from lib.suspect_lemmas import run_suspect_report
from lib.urns import urn_to_safe_filename


CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
CONTENT_NVA = {"NOUN", "VERB", "ADJ"}
# Closed-class items tagged ADV by odyCy — lemma==surface is correct, not failure.
# Excluded from the lemmatizer-health passthrough metric only.
ADV_PARTICLES = {
    "τε", "οὖν", "οὐ", "γε", "ὡς", "δέ", "γάρ", "μέν", "ἄν", "δή", "περ",
    "γοῦν", "τοίνυν", "οὔτε", "μήτε", "ἤτοι", "ἦ", "ἤ", "καί", "ἀτάρ",
    "νῦν", "ἔτι", "ἤδη", "πάλιν", "ἅμα", "αὖ", "αὖθις", "δηλαδή",
}


def content_passthrough(lemmatized_galen: Path) -> dict:
    nvaa = nvaa_pt = 0
    nva = nva_pt = 0
    open_adv = open_adv_pt = 0
    for path in lemmatized_galen.glob("*.jsonl"):
        for row in read_jsonl(path):
            pos = row.get("pos")
            lemma = row.get("lemma")
            if not lemma or pos not in CONTENT_POS:
                continue
            lemma_cf = casefold_greek(lemma)
            same = casefold_greek(row["surface"]) == lemma_cf
            nvaa += 1
            nvaa_pt += same
            if pos in CONTENT_NVA:
                nva += 1
                nva_pt += same
            elif lemma_cf not in ADV_PARTICLES:
                open_adv += 1
                open_adv_pt += same
    # Health metric: NVA + open-class ADV (excludes particles where pass-through is correct)
    health_c = nva + open_adv
    health_pt = nva_pt + open_adv_pt
    return {
        "nvaa_tokens": nvaa,
        "nvaa_passthrough_tokens": nvaa_pt,
        "nvaa_passthrough_pct": round(100.0 * nvaa_pt / nvaa, 2) if nvaa else 0.0,
        "nva_tokens": nva,
        "nva_passthrough_tokens": nva_pt,
        "nva_passthrough_pct": round(100.0 * nva_pt / nva, 2) if nva else 0.0,
        "health_tokens": health_c,
        "health_passthrough_tokens": health_pt,
        "health_passthrough_pct": round(100.0 * health_pt / health_c, 2) if health_c else 0.0,
        # Back-compat keys used in acceptance printout
        "content_tokens": health_c,
        "passthrough_tokens": health_pt,
        "passthrough_pct": round(100.0 * health_pt / health_c, 2) if health_c else 0.0,
    }


def never_real_lemma_share(lemmatized_galen: Path, punch_path: Path) -> dict:
    """% of punch-list lemmas that never lemmatize an inflected (surface!=lemma) form."""
    if not punch_path.exists():
        return {"punch_n": 0, "never_real_n": 0, "never_real_pct": 0.0, "examples": []}
    punch_lemmas = []
    with punch_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            punch_lemmas.append(casefold_greek(row["lemma"]))

    has_inflected: set[str] = set()
    seen: set[str] = set()
    for path in lemmatized_galen.glob("*.jsonl"):
        for row in read_jsonl(path):
            lemma = row.get("lemma")
            if not lemma:
                continue
            lemma = casefold_greek(lemma)
            if lemma not in punch_lemmas and lemma not in set(punch_lemmas):
                # still track only punch lemmas for speed
                pass
            seen.add(lemma)
            if casefold_greek(row.get("surface") or "") != lemma:
                has_inflected.add(lemma)

    punch_set = set(punch_lemmas)
    never = sorted(punch_set - has_inflected)
    n = len(punch_set)
    pct = round(100.0 * len(never) / n, 2) if n else 0.0
    return {
        "punch_n": n,
        "never_real_n": len(never),
        "never_real_pct": pct,
        "examples": never[:40],
    }


def per_work_coverage(
    cfg: dict, extracted: Path, *, all_categories: bool = False
) -> dict:
    census_path = (project_root() / cfg["census_file"]).resolve()
    census = load_census(census_path)
    works = filter_galen_works(cfg, census, all_categories=all_categories)
    rows = []
    flagged = []
    for w in works:
        urn = w["urn"]
        stem = urn_to_safe_filename(urn)
        txt = extracted / f"{stem}.txt"
        census_wc = int(w.get("wordcount") or 0)
        extracted_wc = len(txt.read_text(encoding="utf-8").split()) if txt.exists() else 0
        ratio = (extracted_wc / census_wc) if census_wc else None
        row = {
            "urn": urn,
            "title": w.get("title"),
            "category": w.get("category"),
            "census_wordcount": census_wc,
            "extracted_tokens": extracted_wc,
            "ratio": round(ratio, 3) if ratio is not None else None,
        }
        rows.append(row)
        if ratio is not None and ratio < 0.70:
            flagged.append(row)
    return {
        "works_checked": len(rows),
        "flagged_below_70pct": flagged,
        "flagged_n": len(flagged),
        "scope": "whole_galen" if all_categories else "medical",
        "rows": rows,
    }


def lsj_rates(outputs: Path) -> dict:
    top50_path = outputs / "lsj_top50_common_check.json"
    top50 = read_json(top50_path) if top50_path.exists() else {}
    kw_path = outputs / "keyness_with_lsj.csv"
    overall_matched = overall_n = 0
    if kw_path.exists():
        with kw_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                overall_n += 1
                if str(row.get("lsj_exists")).lower() in {"true", "1"}:
                    overall_matched += 1
    overall_pct = round(100.0 * overall_matched / overall_n, 2) if overall_n else 0.0
    return {
        "overall_matched": overall_matched,
        "overall_n": overall_n,
        "overall_pct": overall_pct,
        "top50_common_matched": top50.get("matched"),
        "top50_common_n": top50.get("n"),
        "top50_common_pct": top50.get("rate_pct"),
        "top50_misses": top50.get("misses", []),
    }


def punch_top(punch_path: Path, n: int = 40) -> list[dict]:
    rows = []
    if not punch_path.exists():
        return rows
    with punch_path.open(encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            if i >= n:
                break
            rows.append(
                {
                    "rank": i + 1,
                    "lemma": row["lemma"],
                    "pos": row.get("pos"),
                    "galen_raw_count": row.get("galen_raw_count"),
                    "log_likelihood": row.get("log_likelihood"),
                    "lsj_sense_count": row.get("lsj_sense_count"),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)

    outputs = resolve_path(cfg, "outputs")
    lemmatized = resolve_path(cfg, "lemmatized") / "galen"
    extracted = resolve_path(cfg, "extracted_text")
    punch = outputs / "punch_list.csv"

    print("=" * 60)
    print("QC SUMMARY")
    print("=" * 60)

    lemma_summary = {}
    ls_path = resolve_path(cfg, "lemmatized") / "_lemmatize_summary_galen.json"
    if ls_path.exists():
        lemma_summary = read_json(ls_path)
        model = lemma_summary.get("model") or {}
        print(
            f"Model: {lemma_summary.get('backend')} "
            f"name={model.get('model_name')} v{model.get('model_version')} "
            f"spaCy={model.get('spacy_version')} "
            f"lemmatizer_enabled={model.get('lemmatizer_enabled')}"
        )

    pt = content_passthrough(lemmatized)
    print(
        f"1) Lemmatizer-health passthrough (NOUN/VERB/ADJ + open ADV, "
        f"excl. particles): {pt['health_passthrough_pct']}% "
        f"({pt['health_passthrough_tokens']}/{pt['health_tokens']}) "
        f"[was 28.7% raw NVAA; want materially lower]"
    )
    print(
        f"   raw NVAA (incl. particles): {pt['nvaa_passthrough_pct']}% | "
        f"NVA only: {pt['nva_passthrough_pct']}%"
    )

    never = never_real_lemma_share(lemmatized, punch)
    print(
        f"2) Punch-list never-a-real-lemma: {never['never_real_pct']}% "
        f"({never['never_real_n']}/{never['punch_n']}) "
        f"[was 36%; want low single digits]"
    )
    if never["examples"]:
        print(f"   examples: {', '.join(never['examples'][:15])}")

    cov = per_work_coverage(cfg, extracted, all_categories=False)
    cov_whole = per_work_coverage(cfg, extracted, all_categories=True)
    print(
        f"3) Per-work extract vs census (medical): {cov['works_checked']} works, "
        f"{cov['flagged_n']} below 70%"
    )
    for f in cov["flagged_below_70pct"][:15]:
        print(
            f"   FLAG {f['urn']}: extracted={f['extracted_tokens']} "
            f"census={f['census_wordcount']} ratio={f['ratio']}"
        )
    print(
        f"3b) Per-work extract vs census (whole Galen): {cov_whole['works_checked']} works, "
        f"{cov_whole['flagged_n']} below 70%"
    )
    for f in cov_whole["flagged_below_70pct"][:15]:
        print(
            f"   FLAG {f['urn']} [{f.get('category')}]: extracted={f['extracted_tokens']} "
            f"census={f['census_wordcount']} ratio={f['ratio']}"
        )

    lsj = lsj_rates(outputs)
    print(
        f"4) LSJ match overall: {lsj['overall_pct']}% "
        f"({lsj['overall_matched']}/{lsj['overall_n']})"
    )
    print(
        f"   LSJ top-50 common: {lsj['top50_common_pct']}% "
        f"({lsj['top50_common_matched']}/{lsj['top50_common_n']})"
    )
    if lsj["top50_misses"]:
        print(f"   top-50 misses: {', '.join(lsj['top50_misses'][:20])}")

    top40 = punch_top(punch, 40)
    print(f"5) Punch list top-40 ({len(top40)} shown):")
    for r in top40:
        print(
            f"   {r['rank']:2d}. {float(r['log_likelihood']):8.1f}  "
            f"sense={r['lsj_sense_count']}  n={r['galen_raw_count']:>5}  "
            f"{r['lemma']}  ({r['pos']})"
        )

    # 6) SEPARATE gate from never-a-real-lemma: consistently-wrong lemmas still pass #2.
    qc_dir = project_root() / "data" / "qc"
    suspect_path = qc_dir / "suspect_high_freq_lemmas.csv"
    suspect = run_suspect_report(lemmatized, suspect_path, cfg)
    print(
        f"6) Suspect high-freq lemmas (SEPARATE gate): {suspect['n_suspects']} candidates → "
        f"{suspect_path}"
    )
    print(
        f"   morph coverage: {suspect['morph_coverage_pct']}% "
        f"({suspect['tokens_with_morph']}/{suspect['tokens_scanned']}) | "
        f"flags={suspect['flag_counts']}"
    )
    for h in suspect["head"][:10]:
        print(f"   · n={h['galen_raw_count']:>5}  {h['lemma']}  [{h['flags']}]")
    print(
        "   NOTE: do NOT auto-correct these — priority worklist for Greek-literate spot-check (H3)."
    )

    report = {
        "model": lemma_summary.get("model"),
        "backend": lemma_summary.get("backend"),
        "content_passthrough": pt,
        "never_real_lemma": never,
        "extract_coverage": {
            "works_checked": cov["works_checked"],
            "flagged_n": cov["flagged_n"],
            "flagged_below_70pct": cov["flagged_below_70pct"],
        },
        "extract_coverage_whole_galen": {
            "works_checked": cov_whole["works_checked"],
            "flagged_n": cov_whole["flagged_n"],
            "flagged_below_70pct": cov_whole["flagged_below_70pct"],
        },
        "lsj": lsj,
        "punch_top40": top40,
        "suspect_high_freq_lemmas": suspect,
        "acceptance": {
            "passthrough_below_28": pt["health_passthrough_pct"] < 28.0,
            "never_real_single_digits": never["never_real_pct"] < 10.0,
            "top50_lsj_near_100": (lsj.get("top50_common_pct") or 0) >= 95.0,
            "no_extract_flags": cov["flagged_n"] == 0,
            # Separate from never-a-real-lemma: report emitted + morph available for heuristics
            "suspect_lemma_report_emitted": bool(suspect.get("gate_report_emitted")),
            "suspect_lemma_morph_present": bool(suspect.get("gate_morph_present")),
        },
    }
    write_json(outputs / "qc_summary.json", report)
    print("=" * 60)
    print(f"Wrote {outputs / 'qc_summary.json'}")
    acc = report["acceptance"]
    print("Acceptance:", acc)
    ok = all(acc.values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
