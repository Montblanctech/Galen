#!/usr/bin/env python3
"""H3-M M2: Stanza grc_perseus × grc_proiel agreement (report-only)."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import load_config, resolve_path
from lib.io_utils import ensure_dir, read_jsonl, write_json

from h3m.align import align_surfaces
from h3m.lemma_eq import classify_lemma_disagreement, lemma_nfc, lemmas_equal_strict
from h3m.paths import (
    G2A_ARTIFACT_MAX,
    G2A_HANDPRINT_N,
    RANDOM60_SEED,
    SAMPLE_5K_SEED,
    h3m_cache_dir,
    h3m_dir,
)
from h3m.stats_util import pct, wilson_ci

PACKAGES = ("perseus", "proiel")
PROCESSORS = "tokenize,pos,lemma"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _load_jsonl_work(path: Path) -> list[dict[str, Any]]:
    return list(read_jsonl(path))


def _find_jsonl(lem_root: Path, stem: str) -> Path | None:
    for sub in ("galen", "galen_nonmedical"):
        p = lem_root / sub / f"{stem}.jsonl"
        if p.exists():
            return p
    return None


def reservoir_sample_medical(lem_dir: Path, n: int, seed: int) -> tuple[list[dict], int]:
    rng = random.Random(seed)
    reservoir: list[dict] = []
    seen = 0
    for path in sorted(lem_dir.glob("*.jsonl")):
        rows = _load_jsonl_work(path)
        for i, row in enumerate(rows):
            if not row.get("lemma") or not row.get("surface"):
                continue
            seen += 1
            item = {
                "work_stem": path.stem,
                "token_index": int(row.get("i", i)),
                "surface_form": row["surface"],
                "lemma_produced": row["lemma"],
                "pos": row.get("pos") or "",
            }
            if len(reservoir) < n:
                reservoir.append(item)
            else:
                j = rng.randint(1, seen)
                if j <= n:
                    reservoir[j - 1] = item
    reservoir.sort(key=lambda r: (r["work_stem"], r["token_index"]))
    return reservoir, seen


def load_random60(qc_dir: Path) -> list[dict[str, str]]:
    path = qc_dir / "accuracy_sample_random60.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_controls(qc_dir: Path) -> list[dict[str, str]]:
    path = qc_dir / "accuracy_controls.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _stanza_pipeline(package: str):
    import stanza

    stanza.download("grc", package=package, verbose=False)
    return stanza.Pipeline(
        lang="grc",
        package=package,
        processors=PROCESSORS,
        verbose=False,
        tokenize_no_ssplit=False,
    )


def lemmatize_text(nlp, text: str) -> list[dict[str, str]]:
    doc = nlp(text)
    out: list[dict[str, str]] = []
    i = 0
    for sent in doc.sentences:
        for tok in sent.words:
            surf = tok.text or ""
            lemma = tok.lemma or ""
            if not surf:
                continue
            out.append({"i": str(i), "surface": surf, "lemma": lemma})
            i += 1
    return out


def stanza_for_work(
    nlp,
    package: str,
    stem: str,
    text: str,
    cache_dir: Path,
) -> list[dict[str, str]]:
    path = cache_dir / f"stanza_{package}" / f"{stem}.jsonl"
    if path.exists():
        return list(read_jsonl(path))
    if nlp is None:
        raise RuntimeError(f"Missing Stanza cache {path} and no pipeline loaded")
    rows = lemmatize_text(nlp, text)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def _ody_index_map(ody_rows: list[dict]) -> dict[int, int]:
    out: dict[int, int] = {}
    for pos, row in enumerate(ody_rows):
        out[int(row.get("i", pos))] = pos
    return out


def _lookup_aligned(
    ody_rows: list[dict],
    stanza_rows: list[dict],
    token_index: int,
    by_a: dict[int, int],
    idx_map: dict[int, int],
    stats: dict,
) -> tuple[str | None, dict]:
    """Return (stanza_lemma, align_info) for an odyCy token index."""
    idx = idx_map.get(token_index)
    if idx is None:
        return None, {**stats, "reason": "token_index_missing"}
    ib = by_a.get(idx)
    if ib is None:
        return None, {**stats, "reason": "unaligned"}
    return stanza_rows[ib].get("lemma") or None, {**stats, "reason": "ok"}


def _consensus(perseus: str | None, proiel: str | None) -> str | None:
    if perseus and proiel and lemmas_equal_strict(perseus, proiel):
        return lemma_nfc(perseus)
    return None


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--workers-stanza", type=int, default=1)
    args = parser.parse_args()
    _configure_stdio()
    cfg = load_config(args.config)

    out_dir = h3m_dir(cfg)
    cache_dir = h3m_cache_dir(cfg)
    qc_dir = resolve_path(cfg, "qc")
    lem_root = resolve_path(cfg, "lemmatized")
    extracted = resolve_path(cfg, "extracted_text")

    random60 = load_random60(qc_dir)
    controls = load_controls(qc_dir)
    sample5k, pop = reservoir_sample_medical(
        lem_root / "galen", n=5000, seed=SAMPLE_5K_SEED
    )
    write_json(
        out_dir / "m2_sample_random5000_meta.json",
        {
            "n_requested": 5000,
            "n_emitted": len(sample5k),
            "seed": SAMPLE_5K_SEED,
            "population_tokens_with_lemma": pop,
            "source": str(lem_root / "galen"),
            "method": "algorithm-R reservoir sample, uniform over tokens with lemma+surface",
        },
    )
    _write_csv(
        out_dir / "m2_sample_random5000.csv",
        sample5k,
        ["work_stem", "token_index", "surface_form", "lemma_produced", "pos"],
    )

    stems: set[str] = set()
    for row in random60:
        stems.add(row["work_stem"])
    for row in controls:
        stems.add(row["work_stem"])
    for row in sample5k:
        stems.add(row["work_stem"])

    print(f"M2: {len(stems)} works; loading Stanza packages {PACKAGES}", flush=True)
    need_nlp = False
    for stem in stems:
        for pkg in PACKAGES:
            if not (cache_dir / f"stanza_{pkg}" / f"{stem}.jsonl").exists():
                need_nlp = True
                break
    pipelines = {pkg: _stanza_pipeline(pkg) for pkg in PACKAGES} if need_nlp else {}
    if not need_nlp:
        print("  all Stanza work caches present; skipping model load", flush=True)

    import stanza as _stanza

    stanza_version = getattr(_stanza, "__version__", "unknown")

    stanza_by_pkg_stem: dict[str, dict[str, list[dict]]] = {pkg: {} for pkg in PACKAGES}
    ody_by_stem: dict[str, list[dict]] = {}
    ody_idx_by_stem: dict[str, dict[int, int]] = {}
    align_maps: dict[tuple[str, str], dict[int, int]] = {}
    align_stats_by: dict[tuple[str, str], dict] = {}
    align_stats_acc = []

    for i, stem in enumerate(sorted(stems), 1):
        txt_path = extracted / f"{stem}.txt"
        jsonl_path = _find_jsonl(lem_root, stem)
        if not txt_path.exists() or jsonl_path is None:
            print(f"  SKIP missing text/jsonl for {stem}")
            continue
        text = txt_path.read_text(encoding="utf-8") if need_nlp else ""
        ody_by_stem[stem] = _load_jsonl_work(jsonl_path)
        ody_idx_by_stem[stem] = _ody_index_map(ody_by_stem[stem])
        for pkg in PACKAGES:
            stanza_by_pkg_stem[pkg][stem] = stanza_for_work(
                pipelines.get(pkg), pkg, stem, text, cache_dir
            )
        a = [r.get("surface") or "" for r in ody_by_stem[stem]]
        for pkg in PACKAGES:
            b = [r.get("surface") or "" for r in stanza_by_pkg_stem[pkg][stem]]
            pairs, stats = align_surfaces(a, b)
            align_maps[(stem, pkg)] = {ia: ib for ia, ib in pairs}
            align_stats_by[(stem, pkg)] = stats
            stats = dict(stats)
            stats["stem"] = stem
            stats["package"] = pkg
            align_stats_acc.append(stats)
        print(f"  [{i}/{len(stems)}] {stem} ody={len(ody_by_stem[stem])}", flush=True)

    def score_rows(rows: list[dict], sample_name: str) -> tuple[list[dict], dict]:
        scored = []
        align_drop = 0
        pair_agree = Counter()
        pair_n = Counter()
        three_way = 0
        vs_consensus = 0
        consensus_n = 0
        disagreements = []
        for row in rows:
            stem = row["work_stem"]
            idx = int(row["token_index"])
            ody_lemma = row.get("lemma_produced") or row.get("lemma") or ""
            surface = row.get("surface_form") or row.get("surface") or ""
            ody_rows = ody_by_stem.get(stem)
            if not ody_rows:
                align_drop += 1
                continue
            lemmas = {"odycy": ody_lemma}
            unaligned = False
            for pkg in PACKAGES:
                srows = stanza_by_pkg_stem[pkg].get(stem)
                if not srows:
                    unaligned = True
                    lemmas[pkg] = None
                    continue
                lem, info = _lookup_aligned(
                    ody_rows,
                    srows,
                    idx,
                    align_maps.get((stem, pkg), {}),
                    ody_idx_by_stem.get(stem, {}),
                    align_stats_by.get((stem, pkg), {}),
                )
                lemmas[pkg] = lem
                if info.get("reason") != "ok":
                    unaligned = True
            if unaligned or lemmas["perseus"] is None or lemmas["proiel"] is None:
                align_drop += 1
                rec = {
                    **{k: row.get(k) for k in ("work_stem", "token_index", "pos")},
                    "surface": surface,
                    "lemma_odycy": ody_lemma,
                    "lemma_perseus": lemmas.get("perseus"),
                    "lemma_proiel": lemmas.get("proiel"),
                    "aligned": False,
                    "sample": sample_name,
                }
                scored.append(rec)
                continue
            pe, pr = lemmas["perseus"], lemmas["proiel"]
            pair_n["odycy_perseus"] += 1
            pair_n["odycy_proiel"] += 1
            pair_n["perseus_proiel"] += 1
            if lemmas_equal_strict(ody_lemma, pe):
                pair_agree["odycy_perseus"] += 1
            if lemmas_equal_strict(ody_lemma, pr):
                pair_agree["odycy_proiel"] += 1
            if lemmas_equal_strict(pe, pr):
                pair_agree["perseus_proiel"] += 1
            if lemmas_equal_strict(ody_lemma, pe) and lemmas_equal_strict(ody_lemma, pr):
                three_way += 1
            cons = _consensus(pe, pr)
            if cons is not None:
                consensus_n += 1
                if lemma_nfc(ody_lemma) == cons:
                    vs_consensus += 1
            rec = {
                "work_stem": stem,
                "token_index": idx,
                "pos": row.get("pos") or "",
                "surface": surface,
                "lemma_odycy": ody_lemma,
                "lemma_perseus": pe,
                "lemma_proiel": pr,
                "aligned": True,
                "sample": sample_name,
                "odycy_eq_perseus": lemmas_equal_strict(ody_lemma, pe),
                "odycy_eq_proiel": lemmas_equal_strict(ody_lemma, pr),
                "perseus_eq_proiel": lemmas_equal_strict(pe, pr),
                "three_way": lemmas_equal_strict(ody_lemma, pe) and lemmas_equal_strict(ody_lemma, pr),
            }
            scored.append(rec)
            if not rec["three_way"]:
                disagreements.append(rec)
        n_aligned = sum(1 for r in scored if r.get("aligned"))
        summary = {
            "sample": sample_name,
            "n_rows": len(rows),
            "n_aligned": n_aligned,
            "alignment_drop": align_drop,
            "alignment_loss_pct": pct(align_drop, len(rows)),
            "flag_alignment_loss": (align_drop / len(rows) > 0.05) if rows else False,
            "pairwise": {
                name: {
                    "agree": pair_agree[name],
                    "n": pair_n[name],
                    "pct": pct(pair_agree[name], pair_n[name]),
                    "wilson95_lo_pct": None
                    if not pair_n[name]
                    else round(100.0 * wilson_ci(pair_agree[name], pair_n[name])[0], 2),
                    "wilson95_hi_pct": None
                    if not pair_n[name]
                    else round(100.0 * wilson_ci(pair_agree[name], pair_n[name])[1], 2),
                }
                for name in ("odycy_perseus", "odycy_proiel", "perseus_proiel")
            },
            "three_way_consensus_pct": pct(three_way, n_aligned),
            "odycy_vs_stanza_consensus": {
                "agree": vs_consensus,
                "n_unanimous_stanza": consensus_n,
                "pct": pct(vs_consensus, consensus_n),
            },
            "honesty_clause": (
                "Stanza grc_perseus and grc_proiel train on the same UD treebanks "
                "(Perseus, PROIEL) that odyCy trains on, so errors are correlated "
                "and agreement overstates accuracy. Report as an upper-ish bound, "
                "never as accuracy."
            ),
        }
        return scored, summary, disagreements

    s60, sum60, dis60 = score_rows(random60, "random60")
    s5k, sum5k, dis5k = score_rows(sample5k, "random5000")
    sctl, sumctl, _disctl = score_rows(controls, "controls")

    # G2b: contested vs unanimous on controls
    g2b = []
    for rec, src in zip(sctl, controls):
        pe, pr, od = rec.get("lemma_perseus"), rec.get("lemma_proiel"), rec.get("lemma_odycy")
        if rec.get("three_way"):
            status = "unanimous"
        elif rec.get("aligned"):
            status = "contested"
        else:
            status = "unaligned"
        g2b.append(
            {
                "control_id": src["control_id"],
                "control_type": src.get("control_type"),
                "strength": src.get("strength"),
                "surface": rec.get("surface"),
                "lemma_odycy": od,
                "lemma_perseus": pe,
                "lemma_proiel": pr,
                "status": status,
                "aligned": rec.get("aligned"),
            }
        )

    # Disagreements: union of 60 + 5k, frequency-ranked by surface+ody lemma
    freq = Counter()
    for rec in dis60 + dis5k:
        if rec.get("aligned"):
            freq[(rec["surface"], rec["lemma_odycy"])] += 1
    disag_rows = []
    seen_keys = set()
    for rec in sorted(dis60 + dis5k, key=lambda r: (-freq[(r["surface"], r["lemma_odycy"])], r["surface"])):
        if not rec.get("aligned"):
            continue
        key = (rec["work_stem"], rec["token_index"], rec["sample"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        disag_rows.append(
            {
                **rec,
                "pair_token_count_in_samples": freq[(rec["surface"], rec["lemma_odycy"])],
                "g2a_odycy_perseus": classify_lemma_disagreement(
                    rec["lemma_odycy"], rec.get("lemma_perseus") or ""
                ),
                "g2a_odycy_proiel": classify_lemma_disagreement(
                    rec["lemma_odycy"], rec.get("lemma_proiel") or ""
                ),
            }
        )

    _write_csv(
        out_dir / "m2_disagreements.csv",
        disag_rows,
        [
            "sample",
            "work_stem",
            "token_index",
            "pos",
            "surface",
            "lemma_odycy",
            "lemma_perseus",
            "lemma_proiel",
            "odycy_eq_perseus",
            "odycy_eq_proiel",
            "perseus_eq_proiel",
            "pair_token_count_in_samples",
            "g2a_odycy_perseus",
            "g2a_odycy_proiel",
        ],
    )
    _write_csv(
        out_dir / "m2_random60_verdicts.csv",
        s60,
        [
            "work_stem",
            "token_index",
            "pos",
            "surface",
            "lemma_odycy",
            "lemma_perseus",
            "lemma_proiel",
            "aligned",
            "odycy_eq_perseus",
            "odycy_eq_proiel",
            "perseus_eq_proiel",
            "three_way",
        ],
    )

    # G2a hand-print: 20 random disagreements (prefer 5k+60 aligned disagrees)
    rng = random.Random(SAMPLE_5K_SEED)
    pool = [r for r in disag_rows if r.get("sample") in {"random60", "random5000"}]
    if len(pool) > G2A_HANDPRINT_N:
        hand = rng.sample(pool, G2A_HANDPRINT_N)
    else:
        hand = pool
    hand_out = []
    n_artifact = 0
    for rec in hand:
        pe_cls = rec.get("g2a_odycy_perseus")
        pr_cls = rec.get("g2a_odycy_proiel")
        artifact = pe_cls == "encoding_artifact" or pr_cls == "encoding_artifact"
        if artifact and pe_cls != "real_disagreement" and pr_cls != "real_disagreement" and pe_cls != "accent_only" and pr_cls != "accent_only":
            n_artifact += 1
            kind = "encoding_artifact"
        elif pe_cls == "accent_only" or pr_cls == "accent_only":
            kind = "accent_only"
        else:
            kind = "real_disagreement"
        hand_out.append({**rec, "g2a_class": kind})
    g2a_fail = n_artifact > G2A_ARTIFACT_MAX
    _write_csv(
        out_dir / "m2_g2a_handprint.csv",
        hand_out,
        [
            "g2a_class",
            "sample",
            "work_stem",
            "token_index",
            "surface",
            "lemma_odycy",
            "lemma_perseus",
            "lemma_proiel",
            "g2a_odycy_perseus",
            "g2a_odycy_proiel",
        ],
    )

    mean_loss = (
        sum(s["alignment_loss_a"] for s in align_stats_acc) / len(align_stats_acc)
        if align_stats_acc
        else 0.0
    )
    summary = {
        "stanza_version": stanza_version,
        "packages": list(PACKAGES),
        "processors": PROCESSORS,
        "seeds": {"random60": RANDOM60_SEED, "random5000": SAMPLE_5K_SEED},
        "n_works": len(ody_by_stem),
        "work_alignment_loss_mean": round(mean_loss, 4),
        "flag_work_alignment_loss": mean_loss > 0.05,
        "random60": sum60,
        "random5000": sum5k,
        "g2a": {
            "n": len(hand_out),
            "encoding_artifacts": n_artifact,
            "threshold": G2A_ARTIFACT_MAX,
            "passed": not g2a_fail,
            "note": "If >2/20 are encoding artifacts, fix normalization and rerun.",
        },
        "g2b_controls": g2b,
        "honesty_clause": sum5k["honesty_clause"],
    }
    write_json(out_dir / "m2_agreement_summary.json", summary)
    print(
        f"M2 random60 odyCy↔consensus {sum60['odycy_vs_stanza_consensus']['pct']}% "
        f"| 5k pairwise odyCy↔perseus {sum5k['pairwise']['odycy_perseus']['pct']}% "
        f"| G2a artifacts {n_artifact}/{len(hand_out)} pass={not g2a_fail}"
    )
    return 0 if not g2a_fail else 2


if __name__ == "__main__":
    raise SystemExit(main())
