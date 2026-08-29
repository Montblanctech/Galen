#!/usr/bin/env python3
"""Stage 09: four-way classification (plan §9).

Axes (config ``four_way_rarity_per10k_threshold``):
  A — rare vs common in the MEDICAL subcorpus
  B — rare vs common in the DISJOINT NON-MEDICAL Galen subcorpus
      (NOT whole-Galen: medical is ~71% of whole, so med/whole are collinear)

Quadrants (content POS only — NOUN/ADJ/VERB):
  rare-med + rare-nonmed     → genuinely_hard
  common-med + rare-nonmed   → false_alarm_domain_vocab
  rare-med + common-nonmed   → mostly_irrelevant
  common-med + common-nonmed → polysemy_risk

Also reports threshold sensitivity (± step) and overlap with keyness punch_list.csv.
CSV optionally retains medical-vs-whole rates for completeness; quadrants use
medical-vs-nonmedical.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, resolve_path
from lib.greek_normalize import casefold_greek
from lib.io_utils import ensure_dir, read_json, write_json


QUADRANTS = {
    ("rare", "rare"): "genuinely_hard",
    ("common", "rare"): "false_alarm_domain_vocab",
    ("rare", "common"): "mostly_irrelevant",
    ("common", "common"): "polysemy_risk",
}

DEFAULT_POS = {"NOUN", "ADJ", "VERB"}


def classify(medical_per10k: float, nonmed_per10k: float, threshold: float) -> str:
    med = "rare" if medical_per10k < threshold else "common"
    nonmed = "rare" if nonmed_per10k < threshold else "common"
    return QUADRANTS[(med, nonmed)]


def load_punch_lemmas(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            lemma = casefold_greek(row.get("lemma") or "")
            if lemma:
                out.add(lemma)
    return out


def run_classification(
    medical: dict,
    nonmedical: dict,
    whole: dict | None,
    threshold: float,
    min_domain_frequency: int,
    pos_whitelist: set[str],
) -> list[dict]:
    med_lemmas = medical.get("lemmas") or {}
    nonmed_lemmas = nonmedical.get("lemmas") or {}
    whole_lemmas = (whole or {}).get("lemmas") or {}
    rows: list[dict] = []
    for lemma, info in med_lemmas.items():
        raw = int(info.get("raw_count") or 0)
        if raw < min_domain_frequency:
            continue
        pos = (info.get("pos") or "").upper()
        if pos_whitelist and pos not in pos_whitelist:
            continue
        med_p10k = float(info.get("per_10k") or 0.0)
        ninfo = nonmed_lemmas.get(lemma) or {}
        nonmed_p10k = float(ninfo.get("per_10k") or 0.0)
        nonmed_raw = int(ninfo.get("raw_count") or 0)
        winfo = whole_lemmas.get(lemma) or {}
        whole_p10k = float(winfo.get("per_10k") or 0.0)
        whole_raw = int(winfo.get("raw_count") or 0)
        quadrant = classify(med_p10k, nonmed_p10k, threshold)
        rows.append(
            {
                "lemma": lemma,
                "pos": pos,
                "medical_raw": raw,
                "medical_per10k": round(med_p10k, 4),
                "nonmedical_raw": nonmed_raw,
                "nonmedical_per10k": round(nonmed_p10k, 4),
                "wholegalen_raw": whole_raw,
                "wholegalen_per10k": round(whole_p10k, 4),
                "quadrant": quadrant,
            }
        )
    rows.sort(key=lambda r: (-r["medical_per10k"], r["lemma"]))
    return rows


def count_quadrants(rows: list[dict]) -> dict[str, int]:
    counts = {name: 0 for name in QUADRANTS.values()}
    for r in rows:
        counts[r["quadrant"]] = counts.get(r["quadrant"], 0) + 1
    return counts


def examples_per_quadrant(rows: list[dict], n: int = 10) -> dict[str, list[dict]]:
    """Top-n by medical_per10k within each quadrant (already sorted globally)."""
    out: dict[str, list[dict]] = {name: [] for name in QUADRANTS.values()}
    for r in rows:
        q = r["quadrant"]
        if len(out[q]) < n:
            out[q].append(
                {
                    "lemma": r["lemma"],
                    "pos": r["pos"],
                    "medical_per10k": r["medical_per10k"],
                    "nonmedical_per10k": r["nonmedical_per10k"],
                    "medical_raw": r["medical_raw"],
                    "nonmedical_raw": r["nonmedical_raw"],
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)

    outputs = resolve_path(cfg, "outputs")
    ensure_dir(outputs)

    med_path = outputs / "lemma_frequency_galen.json"
    nonmed_path = outputs / "lemma_frequency_galen_nonmedical.json"
    whole_path = outputs / "lemma_frequency_galen_whole.json"
    if not med_path.exists():
        print(f"Missing {med_path}; run 04_frequency.py first.")
        return 1
    if not nonmed_path.exists():
        print(f"Missing {nonmed_path}; run 04_frequency.py after nonmedical lemmatize.")
        return 1

    medical = read_json(med_path)
    nonmedical = read_json(nonmed_path)
    whole = read_json(whole_path) if whole_path.exists() else None
    threshold = float(cfg.get("four_way_rarity_per10k_threshold", 1.0))
    step = float(cfg.get("four_way_rarity_threshold_step", 0.5))
    min_freq = int(cfg.get("min_domain_frequency", 5))
    pos_whitelist = {
        str(p).upper()
        for p in (cfg.get("four_way_pos_whitelist") or sorted(DEFAULT_POS))
    }

    rows = run_classification(
        medical, nonmedical, whole, threshold, min_freq, pos_whitelist
    )
    counts = count_quadrants(rows)
    examples = examples_per_quadrant(rows, n=10)

    out_csv = outputs / "four_way_classification.csv"
    fieldnames = [
        "lemma",
        "pos",
        "medical_per10k",
        "nonmedical_per10k",
        "quadrant",
        "medical_raw",
        "nonmedical_raw",
        "wholegalen_per10k",
        "wholegalen_raw",
    ]
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Sensitivity at threshold ± step
    sensitivity = {}
    for label, thr in (
        ("threshold_minus_step", max(0.0, threshold - step)),
        ("threshold", threshold),
        ("threshold_plus_step", threshold + step),
    ):
        r = run_classification(
            medical, nonmedical, whole, thr, min_freq, pos_whitelist
        )
        sensitivity[label] = {
            "threshold": thr,
            "n": len(r),
            "counts": count_quadrants(r),
        }

    base_hard = {r["lemma"] for r in rows if r["quadrant"] == "genuinely_hard"}
    minus_rows = run_classification(
        medical,
        nonmedical,
        whole,
        max(0.0, threshold - step),
        min_freq,
        pos_whitelist,
    )
    plus_rows = run_classification(
        medical, nonmedical, whole, threshold + step, min_freq, pos_whitelist
    )
    minus_hard = {r["lemma"] for r in minus_rows if r["quadrant"] == "genuinely_hard"}
    plus_hard = {r["lemma"] for r in plus_rows if r["quadrant"] == "genuinely_hard"}
    sensitivity["genuinely_hard_membership_shift"] = {
        "at_minus_step_only_n": len(minus_hard - base_hard),
        "lost_at_minus_step_n": len(base_hard - minus_hard),
        "at_plus_step_only_n": len(plus_hard - base_hard),
        "lost_at_plus_step_n": len(base_hard - plus_hard),
        "stable_across_pm_step_n": len(base_hard & minus_hard & plus_hard),
    }

    punch = load_punch_lemmas(outputs / "punch_list.csv")
    hard = base_hard
    overlap = hard & punch
    overlap_stats = {
        "genuinely_hard_n": len(hard),
        "punch_list_n": len(punch),
        "overlap_n": len(overlap),
        "overlap_frac_of_hard": round(len(overlap) / len(hard), 4) if hard else 0.0,
        "overlap_frac_of_punch": round(len(overlap) / len(punch), 4) if punch else 0.0,
        "in_hard_not_punch_n": len(hard - punch),
        "in_punch_not_hard_n": len(punch - hard),
        "overlap_examples": sorted(overlap)[:40],
    }

    note = (
        "Classification inherits lemmatizer noise (fragmented/oblique lemmas such as "
        "διαθέσεων for διάθεσις, νεύρος for νεῦρον). Report for the Greek-literate "
        "reviewer; do not auto-patch (plan §3)."
    )

    summary = {
        "axis_b": "nonmedical_galen_disjoint",
        "medical_tokens": medical.get("corpus_total_tokens"),
        "nonmedical_tokens": nonmedical.get("corpus_total_tokens"),
        "wholegalen_tokens": (whole or {}).get("corpus_total_tokens"),
        "pos_whitelist": sorted(pos_whitelist),
        "min_domain_frequency": min_freq,
        "rarity_per10k_threshold": threshold,
        "rarity_threshold_step": step,
        "classified_n": len(rows),
        "quadrant_counts": counts,
        "quadrant_examples": examples,
        "sensitivity": sensitivity,
        "punch_list_overlap": overlap_stats,
        "limitation_note": note,
    }
    write_json(outputs / "four_way_summary.json", summary)

    print("=" * 60)
    print("FOUR-WAY CLASSIFICATION (medical vs NON-MEDICAL Galen)")
    print("=" * 60)
    print(f"Medical tokens:    {summary['medical_tokens']}")
    print(f"Nonmedical tokens: {summary['nonmedical_tokens']}")
    print(f"Whole-Galen tokens (CSV only): {summary['wholegalen_tokens']}")
    print(f"POS whitelist: {sorted(pos_whitelist)}")
    print(f"Threshold: {threshold} per10k (step +/-{step})")
    print(f"Classified (medical raw >= {min_freq}, content POS): {len(rows)}")
    for q, n in counts.items():
        print(f"  {q}: {n}")
    print("Sensitivity (quadrant counts):")
    for label in ("threshold_minus_step", "threshold", "threshold_plus_step"):
        s = sensitivity[label]
        print(f"  thr={s['threshold']}: {s['counts']}")
    print(
        f"Overlap genuinely_hard ∩ punch_list: {overlap_stats['overlap_n']} "
        f"({overlap_stats['overlap_frac_of_hard']:.1%} of hard, "
        f"{overlap_stats['overlap_frac_of_punch']:.1%} of punch)"
    )
    print("Examples per quadrant (top by medical_per10k):")
    for q, exs in examples.items():
        print(f"  [{q}]")
        for e in exs:
            print(
                f"    {e['lemma']:20} {e['pos']:4}  "
                f"med={e['medical_per10k']:>8}  nonmed={e['nonmedical_per10k']:>8}  "
                f"(raw {e['medical_raw']}/{e['nonmedical_raw']})"
            )
    print(f"NOTE: {note}")
    print(f"Wrote {out_csv}")
    print(f"Wrote {outputs / 'four_way_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
