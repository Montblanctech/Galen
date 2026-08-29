#!/usr/bin/env python3
"""Stage 07: build human-facing punch_list.csv with example works + context.

Applies auditable author-name and units/numerals stoplists (logged, never silent).
Restricts to punch_list_pos_whitelist (default NOUN/ADJ) — substantive terminology.
Auto-drops hallucinated non-words (no LSJ + no Galen surface within edit distance).
Labels sense_count 0 vs 1 as separate tiers (do not pool).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, project_root, resolve_path
from lib.edit_distance import has_neighbor_within
from lib.greek_normalize import casefold_greek
from lib.io_utils import ensure_dir, read_jsonl, write_json
from lib.stoplists import default_stoplist_dir, is_numeral_lemma, load_stoplist


def collect_surfaces_by_lemma(*dirs: Path) -> dict[str, set[str]]:
    """Map each lemma -> surfaces that were lemmatized *to* it in Galen.

    Hallucination check uses these (not the global surface inventory): γαήτσρ's
    assigned surfaces are γαστρός/γαστρὸς (edit dist 4), while ὀπίον has ὀπίου
    (dist 1). Checking the global inventory would falsely keep γαήτσρ via γαστήρ
    at dist 2.
    """
    by_lemma: dict[str, set[str]] = defaultdict(set)
    for d in dirs:
        if not d.exists():
            continue
        for path in d.glob("*.jsonl"):
            for row in read_jsonl(path):
                lemma = row.get("lemma")
                surface = row.get("surface") or ""
                if not lemma or not surface:
                    continue
                by_lemma[casefold_greek(lemma)].add(casefold_greek(surface))
    return by_lemma


def lsj_tier(sense_count: int) -> str:
    """Separate quality tiers — do not pool sense_count 0 with 1."""
    if sense_count <= 0:
        return "absent"  # sense_count == 0
    if sense_count == 1:
        return "thin"  # single sense
    return "rich"


def collect_lemma_evidence(lemmatized_galen: Path, target_lemmas: set[str]) -> dict[str, dict]:
    work_counts: dict[str, Counter[str]] = defaultdict(Counter)
    contexts: dict[str, str] = {}
    target_cf = {casefold_greek(t) for t in target_lemmas}
    for path in sorted(lemmatized_galen.glob("*.jsonl")):
        work = path.stem
        surfaces: list[str] = []
        rows = list(read_jsonl(path))
        for row in rows:
            surfaces.append(row.get("surface") or "")
        for i, row in enumerate(rows):
            lemma = row.get("lemma")
            if not lemma:
                continue
            lemma_cf = casefold_greek(lemma)
            if lemma_cf not in target_cf:
                continue
            work_counts[lemma_cf][work] += 1
            if lemma_cf not in contexts:
                left = " ".join(s for s in surfaces[max(0, i - 5) : i] if s)
                mid = row.get("surface") or lemma
                right = " ".join(s for s in surfaces[i + 1 : i + 6] if s)
                contexts[lemma_cf] = f"{left} [{mid}] {right}".strip()
    evidence = {}
    for lemma in target_cf:
        top = [w for w, _ in work_counts[lemma].most_common(3)]
        evidence[lemma] = {
            "example_work_urns": ";".join(top),
            "example_context": contexts.get(lemma, ""),
        }
    return evidence


def stem_to_urn(stem: str) -> str:
    if stem.startswith("urn_cts_"):
        after = stem[len("urn_cts_") :]
        if "_" in after:
            lit, rest = after.split("_", 1)
            return f"urn:cts:{lit}:{rest}"
    return stem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)

    outputs = resolve_path(cfg, "outputs")
    src = outputs / "keyness_with_lsj.csv"
    if not src.exists():
        print(f"Missing {src}; run 06_lsj_crossref.py first.")
        return 1

    threshold = int(cfg.get("punch_list_thin_gloss_threshold", 1))
    pos_whitelist = {
        str(p).upper() for p in (cfg.get("punch_list_pos_whitelist") or ["NOUN", "ADJ"])
    }
    stop_dir = default_stoplist_dir(project_root())
    authors = load_stoplist(stop_dir / "authors.txt")
    units = load_stoplist(stop_dir / "units_numerals.txt")
    debris = load_stoplist(stop_dir / "elision_debris.txt")

    rows = []
    excluded_authors: list[dict] = []
    excluded_units: list[dict] = []
    excluded_debris: list[dict] = []
    excluded_pos: list[dict] = []

    with src.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row.get("lsj_sense_count") or 0) > threshold:
                continue
            lemma = casefold_greek(row.get("lemma") or "")
            if not lemma:
                continue
            pos = (row.get("pos") or "").upper()
            if pos_whitelist and pos not in pos_whitelist:
                excluded_pos.append(
                    {
                        "lemma": lemma,
                        "pos": pos,
                        "reason": "pos_not_in_whitelist",
                        "log_likelihood": row.get("log_likelihood"),
                        "galen_raw": row.get("galen_raw"),
                    }
                )
                continue
            if lemma in authors:
                excluded_authors.append(
                    {"lemma": lemma, "reason": "author_stoplist", "log_likelihood": row.get("log_likelihood"), "galen_raw": row.get("galen_raw")}
                )
                continue
            if lemma in units or is_numeral_lemma(lemma):
                excluded_units.append(
                    {
                        "lemma": lemma,
                        "reason": "units_numerals_stoplist" if lemma in units else "numeral_pattern",
                        "log_likelihood": row.get("log_likelihood"),
                        "galen_raw": row.get("galen_raw"),
                    }
                )
                continue
            if lemma in debris:
                excluded_debris.append(
                    {"lemma": lemma, "reason": "elision_debris_stoplist", "log_likelihood": row.get("log_likelihood"), "galen_raw": row.get("galen_raw")}
                )
                continue
            row = dict(row)
            row["lemma"] = lemma
            rows.append(row)

    rows.sort(key=lambda r: float(r["log_likelihood"]), reverse=True)

    lemmatized = resolve_path(cfg, "lemmatized") / "galen"

    # Auditable filter: drop candidates that never lemmatize an inflected form
    # (surface!=lemma). These are lemmatizer passthrough junk, not rare terms.
    has_inflected: set[str] = set()
    if lemmatized.exists():
        for path in lemmatized.glob("*.jsonl"):
            for tok in read_jsonl(path):
                lemma = tok.get("lemma")
                surface = tok.get("surface") or ""
                if not lemma:
                    continue
                lemma = casefold_greek(lemma)
                if casefold_greek(surface) != lemma:
                    has_inflected.add(lemma)

    excluded_never_real: list[dict] = []
    kept = []
    for row in rows:
        lemma = row["lemma"]
        if lemma not in has_inflected:
            excluded_never_real.append(
                {
                    "lemma": lemma,
                    "reason": "never_lemmatizes_inflected_form",
                    "log_likelihood": row.get("log_likelihood"),
                    "galen_raw": row.get("galen_raw"),
                }
            )
            continue
        kept.append(row)
    rows = kept

    # Hallucination auto-drop (P3-2): sense_count==0 AND no assigned surface
    # within edit distance of the lemma form. Judgment-free; keeps ὀπίον
    # (ὀπίου @ dist 1), drops γαήτσρ (assigned surfaces γαστρός @ dist 4).
    # Plausible-but-wrong lemmas (νεύρος) stay — they have close own-surfaces.
    max_ed = int(cfg.get("hallucination_max_edit_distance", 2))
    nonmed = resolve_path(cfg, "lemmatized_galen_nonmedical")
    print(
        f"Scanning lemma->surface map for hallucination filter "
        f"(max_edit_distance={max_ed})..."
    )
    by_lemma = (
        collect_surfaces_by_lemma(lemmatized, nonmed) if lemmatized.exists() else {}
    )
    print(f"  lemmas with surfaces: {len(by_lemma)}")
    excluded_hallucination: list[dict] = []
    kept = []
    for row in rows:
        lemma = row["lemma"]
        sense = int(row.get("lsj_sense_count") or 0)
        own_surfaces = by_lemma.get(lemma) or set()
        if sense == 0 and not has_neighbor_within(lemma, own_surfaces, max_ed):
            excluded_hallucination.append(
                {
                    "lemma": lemma,
                    "reason": "hallucination_no_lsj_no_surface_neighbor",
                    "max_edit_distance": max_ed,
                    "own_surface_examples": sorted(own_surfaces)[:5],
                    "log_likelihood": row.get("log_likelihood"),
                    "galen_raw": row.get("galen_raw"),
                    "pos": row.get("pos", ""),
                }
            )
            continue
        kept.append(row)
    rows = kept
    print(f"Hallucination drops: {len(excluded_hallucination)}")

    # Audit logs — never silent
    ensure_dir(outputs)
    write_json(outputs / "excluded_authors.json", {"count": len(excluded_authors), "terms": excluded_authors})
    write_json(outputs / "excluded_units_numerals.json", {"count": len(excluded_units), "terms": excluded_units})
    write_json(outputs / "excluded_elision_debris.json", {"count": len(excluded_debris), "terms": excluded_debris})
    write_json(
        outputs / "excluded_pos_whitelist.json",
        {
            "count": len(excluded_pos),
            "whitelist": sorted(pos_whitelist),
            "terms": excluded_pos[:1000],
        },
    )
    write_json(
        outputs / "excluded_never_real_lemma.json",
        {"count": len(excluded_never_real), "terms": excluded_never_real[:500]},
    )
    write_json(
        outputs / "excluded_hallucinations.json",
        {
            "count": len(excluded_hallucination),
            "max_edit_distance": max_ed,
            "terms": excluded_hallucination,
        },
    )
    with (outputs / "excluded_stoplist_audit.log").open("w", encoding="utf-8") as log:
        log.write("# lemma\treason\tlog_likelihood\tgalen_raw\tpos\n")
        for item in (
            excluded_pos
            + excluded_authors
            + excluded_units
            + excluded_debris
            + excluded_never_real
            + excluded_hallucination
        ):
            log.write(
                f"{item['lemma']}\t{item['reason']}\t{item.get('log_likelihood')}\t"
                f"{item.get('galen_raw')}\t{item.get('pos', '')}\n"
            )
    print(
        f"Stoplist exclusions: pos_whitelist={len(excluded_pos)} "
        f"(keep {sorted(pos_whitelist)}) "
        f"authors={len(excluded_authors)} "
        f"units/numerals={len(excluded_units)} "
        f"elision_debris={len(excluded_debris)} "
        f"never_real_lemma={len(excluded_never_real)} "
        f"hallucinations={len(excluded_hallucination)} "
        f"(logged to outputs/excluded_stoplist_audit.log)"
    )

    lemmas = {r["lemma"] for r in rows}
    evidence = collect_lemma_evidence(lemmatized, lemmas) if lemmatized.exists() else {}

    for lemma, ev in evidence.items():
        urns = []
        for stem in ev["example_work_urns"].split(";") if ev["example_work_urns"] else []:
            urns.append(stem_to_urn(stem))
        ev["example_work_urns"] = ";".join(urns)

    # Tier separately: thin (sense_count==1) ranked above absent (sense_count==0)
    # within the same log-likelihood sort — both kept, not pooled as one signal.
    def _tier_rank(row: dict) -> tuple:
        sense = int(row.get("lsj_sense_count") or 0)
        # thin (1) before absent (0); then by LL desc
        tier_ord = 0 if sense == 1 else 1 if sense == 0 else 2
        return (tier_ord, -float(row.get("log_likelihood") or 0.0))

    rows.sort(key=_tier_rank)

    out_path = outputs / "punch_list.csv"
    fieldnames = [
        "lemma",
        "pos",
        "galen_raw_count",
        "galen_per10k",
        "log_likelihood",
        "lsj_sense_count",
        "lsj_tier",
        "example_work_urns",
        "example_context",
    ]
    tier_counts = {"absent": 0, "thin": 0, "rich": 0}
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            lemma = row["lemma"]
            sense = int(row.get("lsj_sense_count") or 0)
            tier = lsj_tier(sense)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            ev = evidence.get(lemma, {"example_work_urns": "", "example_context": ""})
            writer.writerow(
                {
                    "lemma": lemma,
                    "pos": row.get("pos", ""),
                    "galen_raw_count": row.get("galen_raw", ""),
                    "galen_per10k": row.get("galen_per10k", ""),
                    "log_likelihood": row.get("log_likelihood", ""),
                    "lsj_sense_count": row.get("lsj_sense_count", ""),
                    "lsj_tier": tier,
                    "example_work_urns": ev["example_work_urns"],
                    "example_context": ev["example_context"],
                }
            )

    print(
        f"Wrote {len(rows)} punch-list terms to {out_path} "
        f"(lsj_tier absent={tier_counts['absent']} thin={tier_counts['thin']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
