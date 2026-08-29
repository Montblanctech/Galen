#!/usr/bin/env python3
"""H3-M M1: Morpheus admissibility (report-only). Never patches frozen outputs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import load_config, project_root, resolve_path
from lib.io_utils import ensure_dir, read_json, read_jsonl, write_json
from lib.stoplists import default_stoplist_dir, is_numeral_lemma, load_stoplist

from h3m.lemma_eq import admissibility_verdict, analyses_have_lemma, lemma_nfc, surface_nfc
from h3m.morpheus_client import MorpheusClient
from h3m.paths import G1A_MIN_ADMISSIBLE, G1C_COVERAGE_MAX, h3m_cache_dir, h3m_dir
from h3m.stats_util import pct, wilson_ci


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

SUBCORPORA = (
    ("medical", "galen"),
    ("nonmedical", "galen_nonmedical"),
)


def _load_top50_lemmas(cfg: dict[str, Any]) -> list[str]:
    outputs = resolve_path(cfg, "outputs")
    path = outputs / "lsj_top50_common_check.json"
    if path.exists():
        data = read_json(path)
        lemmas = [d["lemma"] for d in data.get("details") or [] if d.get("lemma")]
        if lemmas:
            return lemmas
    freq_path = outputs / "lemma_frequency_galen.json"
    freq = read_json(freq_path)
    stop_dir = default_stoplist_dir(project_root())
    skip = load_stoplist(stop_dir / "units_numerals.txt") | load_stoplist(stop_dir / "authors.txt")
    ranked = sorted(
        freq.get("lemmas", {}).items(),
        key=lambda kv: kv[1].get("raw_count", 0),
        reverse=True,
    )
    lemmas: list[str] = []
    for lemma, _info in ranked:
        if lemma in skip or is_numeral_lemma(lemma):
            continue
        lemmas.append(lemma)
        if len(lemmas) >= 50:
            break
    return lemmas


def _load_controls(qc_dir: Path) -> list[dict[str, str]]:
    path = qc_dir / "accuracy_controls.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def collect_inventory(cfg: dict[str, Any], g1a_lemmas: set[str] | None = None) -> dict[str, Any]:
    """Scan frozen JSONL; unique (surface, lemma) with token weights. Read-only."""
    lem_root = resolve_path(cfg, "lemmatized")
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    lemma_surface: dict[str, Counter[str]] = defaultdict(Counter)
    subcorpus_tokens = Counter()
    pos_tokens = Counter()
    watch = g1a_lemmas or set()

    for subcorpus, dirname in SUBCORPORA:
        folder = lem_root / dirname
        if not folder.exists():
            print(f"WARN missing {folder}")
            continue
        files = sorted(folder.glob("*.jsonl"))
        print(f"Scanning {subcorpus}: {len(files)} files", flush=True)
        for path in files:
            stem = path.stem
            for row in read_jsonl(path):
                surface = row.get("surface") or ""
                lemma = row.get("lemma") or ""
                if not surface or not lemma:
                    continue
                pos = row.get("pos") or ""
                subcorpus_tokens[subcorpus] += 1
                pos_tokens[pos] += 1
                key = (surface, lemma)
                rec = stats.get(key)
                if rec is None:
                    rec = {
                        "surface": surface,
                        "lemma": lemma,
                        "token_count": 0,
                        "pos_counts": Counter(),
                        "works": set(),
                        "subcorpus_counts": Counter(),
                    }
                    stats[key] = rec
                rec["token_count"] += 1
                rec["pos_counts"][pos] += 1
                rec["works"].add(stem)
                rec["subcorpus_counts"][subcorpus] += 1
                if subcorpus == "medical" and (not watch or lemma in watch):
                    lemma_surface[lemma][surface] += 1

    pairs = []
    for rec in stats.values():
        pos_counts: Counter = rec["pos_counts"]
        pos = pos_counts.most_common(1)[0][0] if pos_counts else ""
        pairs.append(
            {
                "surface": rec["surface"],
                "lemma": rec["lemma"],
                "pos": pos,
                "token_count": rec["token_count"],
                "works": sorted(rec["works"]),
                "subcorpus_counts": dict(rec["subcorpus_counts"]),
            }
        )
    print(
        f"Inventory: {len(pairs)} unique (surface, lemma) pairs, "
        f"{sum(subcorpus_tokens.values())} tokens",
        flush=True,
    )
    return {
        "pairs": pairs,
        "subcorpus_tokens": dict(subcorpus_tokens),
        "pos_tokens": dict(pos_tokens),
        "lemma_surface_medical": {k: dict(v) for k, v in lemma_surface.items()},
        "n_unique_surfaces": len({surface_nfc(p["surface"]) for p in pairs}),
    }


def _majority_surface(lemma: str, lemma_surface: dict[str, dict[str, int]]) -> str:
    counts = lemma_surface.get(lemma) or {}
    if not counts:
        return lemma
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _expected_g1b(control_id: str, strength: str, control_type: str) -> list[str]:
    if control_id == "C01":
        return ["inadmissible", "no_analysis"]
    if control_type == "wrong_plant" and strength == "unambiguous":
        return ["inadmissible"]
    if control_type == "right_anchor":
        return ["admissible"]
    if control_type == "wrong_plant" and strength == "accent":
        return ["admissible"]  # accent-blind primary
    return ["admissible", "inadmissible", "no_analysis"]


def run_g1a(
    client: MorpheusClient,
    top50: list[str],
    lemma_surface: dict[str, dict[str, int]],
) -> dict[str, Any]:
    details = []
    n_adm = 0
    for lemma in top50:
        surface = _majority_surface(lemma, lemma_surface)
        analyses = client.analyze(surface)
        verdict = admissibility_verdict(lemma, analyses)
        strict = analyses_have_lemma(lemma, analyses, accent_blind=False)
        if verdict == "admissible":
            n_adm += 1
        details.append(
            {
                "lemma": lemma,
                "surface": surface,
                "verdict": verdict,
                "accent_strict_admissible": strict,
                "n_analyses": len(analyses),
                "analyses_sample": analyses[:8],
            }
        )
    passed = n_adm >= G1A_MIN_ADMISSIBLE
    print(f"G1a plumbing: {n_adm}/{len(top50)} admissible (need >={G1A_MIN_ADMISSIBLE}) pass={passed}")
    return {
        "n": len(top50),
        "admissible": n_adm,
        "passed": passed,
        "details": details,
    }


def run_g1b(client: MorpheusClient, controls: list[dict[str, str]]) -> dict[str, Any]:
    details = []
    mismatches = []
    for row in controls:
        cid = row["control_id"]
        surface = row["surface_form"]
        lemma = row["lemma_produced"]
        analyses = client.analyze(surface)
        verdict = admissibility_verdict(lemma, analyses)
        strict = analyses_have_lemma(lemma, analyses, accent_blind=False)
        expected = _expected_g1b(cid, row.get("strength", ""), row.get("control_type", ""))
        ok = verdict in expected
        rec = {
            "control_id": cid,
            "control_type": row.get("control_type"),
            "strength": row.get("strength"),
            "surface": surface,
            "lemma_produced": lemma,
            "expected_verdicts": expected,
            "verdict": verdict,
            "accent_strict_admissible": strict,
            "n_analyses": len(analyses),
            "analyses_sample": analyses[:8],
            "matches_expected": ok,
        }
        details.append(rec)
        if not ok:
            mismatches.append(cid)
        print(f"  G1b {cid} {surface!r} → {lemma!r}: {verdict} (expected {expected}) ok={ok}")
    return {
        "n": len(controls),
        "mismatches": mismatches,
        "details": details,
    }


def _tally(
    pairs: list[dict[str, Any]],
    analyses_by_surface: dict[str, list[str]],
) -> dict[str, Any]:
    token_counts = Counter()
    type_counts = Counter()
    by_sub: dict[str, Counter] = defaultdict(Counter)
    by_pos: dict[str, Counter] = defaultdict(Counter)
    token_strict_admissible = 0
    type_strict_admissible = 0
    inadmissible_rows = []
    no_analysis_rows = []

    for p in pairs:
        surface = p["surface"]
        lemma = p["lemma"]
        key = surface_nfc(surface)
        analyses = analyses_by_surface.get(key, [])
        verdict = admissibility_verdict(lemma, analyses)
        n = int(p["token_count"])
        pos = p.get("pos") or ""
        token_counts[verdict] += n
        type_counts[verdict] += 1
        if analyses_have_lemma(lemma, analyses, accent_blind=False):
            token_strict_admissible += n
            type_strict_admissible += 1
        for sub, c in (p.get("subcorpus_counts") or {}).items():
            by_sub[sub][verdict] += int(c)
        by_pos[pos][verdict] += n
        if verdict == "inadmissible":
            inadmissible_rows.append({**p, "n_analyses": len(analyses)})
        elif verdict == "no_analysis":
            no_analysis_rows.append({**p, "n_analyses": 0})

    token_total = sum(token_counts.values())
    analyzable = token_counts["admissible"] + token_counts["inadmissible"]
    type_total = sum(type_counts.values())
    type_analyzable = type_counts["admissible"] + type_counts["inadmissible"]
    no_analysis_frac = (token_counts["no_analysis"] / token_total) if token_total else 0.0
    flag_g1c = no_analysis_frac > G1C_COVERAGE_MAX
    floor_ready = analyzable > 0 and not flag_g1c

    def _rate_block(adm: int, inadm: int, none: int) -> dict[str, Any]:
        ana = adm + inadm
        tot = adm + inadm + none
        lo, hi = wilson_ci(adm, ana) if ana else (float("nan"), float("nan"))
        return {
            "admissible": adm,
            "inadmissible": inadm,
            "no_analysis": none,
            "total": tot,
            "analyzable": ana,
            "admissible_pct_of_analyzable": pct(adm, ana),
            "inadmissible_pct_of_analyzable": pct(inadm, ana),
            "no_analysis_pct_of_all": pct(none, tot),
            "admissible_wilson95_lo_pct": None if ana == 0 else round(100.0 * lo, 2),
            "admissible_wilson95_hi_pct": None if ana == 0 else round(100.0 * hi, 2),
        }

    by_subcorpus = {}
    for sub, ctr in by_sub.items():
        by_subcorpus[sub] = _rate_block(ctr["admissible"], ctr["inadmissible"], ctr["no_analysis"])
    by_pos_out = {}
    for pos, ctr in sorted(by_pos.items(), key=lambda kv: -sum(kv[1].values())):
        by_pos_out[pos] = _rate_block(ctr["admissible"], ctr["inadmissible"], ctr["no_analysis"])

    return {
        "token_weighted": _rate_block(
            token_counts["admissible"], token_counts["inadmissible"], token_counts["no_analysis"]
        ),
        "type_level": _rate_block(
            type_counts["admissible"], type_counts["inadmissible"], type_counts["no_analysis"]
        ),
        "by_subcorpus": by_subcorpus,
        "by_pos": by_pos_out,
        "accent_strict_admissible_tokens": token_strict_admissible,
        "accent_strict_admissible_pct_of_analyzable": pct(token_strict_admissible, analyzable),
        "accent_strict_admissible_types": type_strict_admissible,
        "flag_g1c_coverage": flag_g1c,
        "floor_paper_ready": floor_ready,
        "token_total": token_total,
        "type_total": type_total,
        "inadmissible_rows": inadmissible_rows,
        "no_analysis_rows": no_analysis_rows,
    }


def _write_pair_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["surface", "lemma", "pos", "token_count", "work_count", "works", "medical_n", "nonmedical_n"]
    ranked = sorted(rows, key=lambda r: (-int(r["token_count"]), r["surface"], r["lemma"]))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in ranked:
            works = r.get("works") or []
            sc = r.get("subcorpus_counts") or {}
            w.writerow(
                {
                    "surface": r["surface"],
                    "lemma": r["lemma"],
                    "pos": r.get("pos", ""),
                    "token_count": r["token_count"],
                    "work_count": len(works),
                    "works": ";".join(works),
                    "medical_n": sc.get("medical", 0),
                    "nonmedical_n": sc.get("nonmedical", 0),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--gates-only", action="store_true")
    parser.add_argument("--max-surfaces", type=int, default=0, help="Debug cap on Morpheus queries")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    _configure_stdio()
    cfg = load_config(args.config)

    out_dir = h3m_dir(cfg)
    cache_dir = h3m_cache_dir(cfg)
    qc_dir = resolve_path(cfg, "qc")

    top50 = _load_top50_lemmas(cfg)
    inv_path = cache_dir / "m1_pair_inventory.json"
    if inv_path.exists():
        print(f"Loading inventory {inv_path}")
        inventory = read_json(inv_path)
    else:
        inventory = collect_inventory(cfg, g1a_lemmas=set(top50))
        write_json(
            inv_path,
            {
                "subcorpus_tokens": inventory["subcorpus_tokens"],
                "pos_tokens": inventory["pos_tokens"],
                "n_unique_surfaces": inventory["n_unique_surfaces"],
                "n_pairs": len(inventory["pairs"]),
                "pairs": inventory["pairs"],
                "lemma_surface_medical": inventory["lemma_surface_medical"],
            },
        )

    client = MorpheusClient(cache_dir / "morpheus_by_surface.jsonl", workers=args.workers)
    print(json.dumps({k: v for k, v in client.info().items() if k != "cache_path"}, ensure_ascii=False))

    g1a = run_g1a(client, top50, inventory["lemma_surface_medical"])
    if not g1a["passed"]:
        write_json(out_dir / "m1_admissibility_summary.json", {"g1a": g1a, "halted": "g1a_failed"})
        print("G1a FAILED — normalization/interface bug. Not reporting a floor.")
        return 2

    controls = _load_controls(qc_dir)
    g1b = run_g1b(client, controls)

    if args.gates_only:
        write_json(
            out_dir / "m1_admissibility_summary.json",
            {"g1a": g1a, "g1b": g1b, "gates_only": True, "morpheus": client.info()},
        )
        print("Gates-only run complete.")
        return 0 if g1a["passed"] else 2

    surfaces = [p["surface"] for p in inventory["pairs"]]
    if args.max_surfaces:
        uniq = []
        seen = set()
        for s in surfaces:
            k = surface_nfc(s)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s)
            if len(uniq) >= args.max_surfaces:
                break
        surfaces = uniq
        keep = {surface_nfc(s) for s in surfaces}
        inventory["pairs"] = [p for p in inventory["pairs"] if surface_nfc(p["surface"]) in keep]

    analyses_by_surface = client.analyze_many(surfaces)
    tallied = _tally(inventory["pairs"], analyses_by_surface)

    _write_pair_csv(out_dir / "m1_inadmissible.csv", tallied.pop("inadmissible_rows"))
    _write_pair_csv(out_dir / "m1_no_analysis.csv", tallied.pop("no_analysis_rows"))

    summary = {
        "morpheus": client.info(),
        "accent_policy": {
            "primary": "H4b lemma_to_lookup_key (accent-blind Beta Code)",
            "strict_diagnostic": "NFC + casefold + lunate/final sigma, accents kept",
        },
        "g1a": {k: v for k, v in g1a.items() if k != "details"} | {"details": g1a["details"]},
        "g1b": g1b,
        "g1c": {
            "no_analysis_frac": tallied["token_weighted"]["no_analysis_pct_of_all"],
            "threshold_pct": G1C_COVERAGE_MAX * 100,
            "flag_g1c_coverage": tallied["flag_g1c_coverage"],
            "floor_paper_ready": tallied["floor_paper_ready"],
        },
        "n_unique_surfaces": inventory["n_unique_surfaces"],
        "n_pairs": len(inventory["pairs"]),
        "subcorpus_tokens": inventory["subcorpus_tokens"],
        **{k: v for k, v in tallied.items()},
    }
    write_json(out_dir / "m1_admissibility_summary.json", summary)
    tw = tallied["token_weighted"]
    print(
        f"M1 token-weighted admissible {tw['admissible_pct_of_analyzable']}% "
        f"of analyzable (N={tw['analyzable']}); "
        f"no_analysis {tw['no_analysis_pct_of_all']}% of all; "
        f"G1c_flag={tallied['flag_g1c_coverage']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
