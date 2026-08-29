#!/usr/bin/env python3
"""Consolidate M1–M3 summaries into h3m_summary.json + §5 draft paragraph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import load_config
from lib.io_utils import read_json, write_json

from h3m.paths import h3m_dir


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    _configure_stdio()
    cfg = load_config(args.config)
    out = h3m_dir(cfg)

    m1 = read_json(out / "m1_admissibility_summary.json") if (out / "m1_admissibility_summary.json").exists() else {}
    m2 = read_json(out / "m2_agreement_summary.json") if (out / "m2_agreement_summary.json").exists() else {}
    m3 = read_json(out / "m3_summary.json") if (out / "m3_summary.json").exists() else {}

    tw = m1.get("token_weighted") or {}
    a = tw.get("admissible_pct_of_analyzable")
    gap = tw.get("no_analysis_pct_of_all")
    med = (m1.get("by_subcorpus") or {}).get("medical") or {}
    a_med = med.get("admissible_pct_of_analyzable")

    s5k = m2.get("random5000") or {}
    vs = (s5k.get("odycy_vs_stanza_consensus") or {})
    b = vs.get("pct")
    if b is None:
        b = ((s5k.get("pairwise") or {}).get("odycy_perseus") or {}).get("pct")

    c_blind = m3.get("rate_blind_pct")
    if c_blind is None:
        c_blind = m3.get("rate_pct")
    c_strict = m3.get("rate_strict_pct")
    n3 = m3.get("n_scored")
    lo = m3.get("wilson95_lo_pct")
    hi = m3.get("wilson95_hi_pct")
    lo_s = m3.get("wilson95_strict_lo_pct")
    hi_s = m3.get("wilson95_strict_hi_pct")
    parked = bool(m3.get("parked"))
    pairwise = ((s5k.get("pairwise") or {}).get("odycy_perseus") or {}).get("pct")
    align_loss = s5k.get("alignment_loss_pct")
    tax = m3.get("mismatch_class_counts") or {}
    var_ok = m3.get("rate_blind_treating_variant_as_ok_pct")
    var_ex = m3.get("rate_blind_excluding_variant_pct")

    summary = {
        "m1_admissible_pct_of_analyzable": a,
        "m1_admissible_pct_medical": a_med,
        "m1_no_analysis_pct_of_all": gap,
        "m1_floor_paper_ready": m1.get("floor_paper_ready") or (m1.get("g1c") or {}).get("floor_paper_ready"),
        "m1_g1a_passed": (m1.get("g1a") or {}).get("passed"),
        "m1_g1c_flag": (m1.get("g1c") or {}).get("flag_g1c_coverage"),
        "m2_odycy_vs_stanza_consensus_pct_5k": b,
        "m2_odycy_perseus_pct_5k": pairwise if pairwise is not None else ((s5k.get("pairwise") or {}).get("odycy_perseus") or {}).get("pct"),
        "m2_alignment_loss_pct_5k": align_loss if align_loss is not None else s5k.get("alignment_loss_pct"),
        "m2_honesty": m2.get("honesty_clause") or (s5k.get("honesty_clause")),
        "m2_flag_alignment_loss": s5k.get("flag_alignment_loss") or m2.get("flag_work_alignment_loss"),
        "m2_g2a_passed": (m2.get("g2a") or {}).get("passed"),
        "m3_n_scored": n3,
        "m3_rate_pct": c_blind,
        "m3_rate_blind_pct": c_blind,
        "m3_rate_strict_pct": c_strict,
        "m3_wilson95_lo_pct": lo,
        "m3_wilson95_hi_pct": hi,
        "m3_wilson95_strict_lo_pct": lo_s,
        "m3_wilson95_strict_hi_pct": hi_s,
        "m3_rate_blind_treating_variant_as_ok_pct": var_ok,
        "m3_rate_blind_excluding_variant_pct": var_ex,
        "m3_mismatch_class_counts": tax,
        "m3_parked": parked,
        "m3_stratum": m3.get("stratum"),
        "morpheus": m1.get("morpheus"),
        "stanza_version": m2.get("stanza_version"),
        "accent_policy": m1.get("accent_policy"),
        "seeds": m2.get("seeds"),
    }
    write_json(out / "h3m_summary.json", summary)

    def _num(x, fallback="[n/a]"):
        return fallback if x is None else x

    tax_bits = []
    if tax:
        tax_bits.append(
            "mismatch taxonomy: "
            f"passthrough {tax.get('passthrough', 0)}, "
            f"garble {tax.get('garble', 0)}, "
            f"variant-headword {tax.get('variant_headword', 0)}, "
            f"other {tax.get('other_substitution', 0)}"
        )
        if var_ok is not None:
            tax_bits.append(f"blind rate treating variant-headword as non-error {_num(var_ok)}%")
        if var_ex is not None:
            tax_bits.append(f"blind rate excluding variant-headword {_num(var_ex)}%")
    tax_clause = ("; " + "; ".join(tax_bits)) if tax_bits else ""
    m3_clause = (
        "LSJ citation mining did not yield ≥50 unambiguous loci and is parked; "
        "M1+M2 still bound the range."
        if parked or not n3
        else (
            f"on the rare/LSJ-cited stratum, against **{n3}** Morpheus-relocated citation "
            f"loci, odyCy matches the lexicographers' headword in **{_num(c_blind)}%** "
            f"accent-blind (95% CI {lo}–{hi}) and **{_num(c_strict)}%** accent-strict "
            f"(95% CI {lo_s}–{hi_s}){tax_clause} — stratum accuracy, not overall accuracy"
        )
    )
    para = (
        "Lemma admissibility against the rule-based Morpheus analyzer is "
        f"**{_num(a_med if a_med is not None else a)}%** of analyzable tokens "
        "(floor on correctness"
        + (f"; medical subcorpus; {_num(gap)}% of tokens had no Morpheus analysis and are excluded" if gap is not None else "")
        + "); "
        "cross-system agreement is "
        f"**{_num(b)}%** vs-consensus (odyCy vs unanimous Stanza perseus+proiel) and "
        f"**{_num(pairwise)}%** pairwise odyCy↔perseus"
        + (f"; **{_num(align_loss)}%** of the 5k sample dropped to alignment loss" if align_loss is not None else "")
        + " (optimistic bound: training treebanks overlap); "
        f"{m3_clause}. "
        "A two-reader human spot-check per the salted-control protocol remains planned; "
        "machine disagreements (M2) will concentrate it on the most informative tokens."
    )
    (out / "section5_bounded_range.md").write_text(
        "# §5 bounded-range draft (machine measurements)\n\n"
        "Architect pastes into `paper_draft.md`; this file does not edit the paper.\n\n"
        + para
        + "\n",
        encoding="utf-8",
    )
    print(para)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
