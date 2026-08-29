#!/usr/bin/env python3
"""Stage 06: cross-reference key lemmas against Perseus LSJ XML sense counts.

Perseus LSJ XML stores headwords in Beta Code (e.g. ``fa/rmakon``), not Unicode.
Lookup uses diacritic-stripped Beta Code keys, including sigma variants and ``*``.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.beta_keys import (
    betacode_headword_to_unicode,
    lemma_to_lookup_key,
    normalize_betacode_key,
)
from lib.config import load_config, resolve_path
from lib.http_fetch import RateLimitedSession
from lib.io_utils import ensure_dir, read_json, write_json


def fetch_lsj_parts(cfg: dict, cache_dir: Path, session: RateLimitedSession) -> list[Path]:
    ensure_dir(cache_dir)
    base = cfg.get("lsj_base_url")
    n_parts = int(cfg.get("lsj_parts", 27))
    paths: list[Path] = []
    for i in range(1, n_parts + 1):
        name = f"grc.lsj.perseus-eng{i}.xml"
        path = cache_dir / name
        if path.exists() and path.stat().st_size > 0:
            paths.append(path)
            continue
        url = f"{base}/{name}"
        print(f"  fetching {name}")
        resp = session.get(url)
        if resp.status_code != 200:
            print(f"  WARN {resp.status_code} for {url}")
            continue
        path.write_bytes(resp.content)
        paths.append(path)
    return paths


def build_lsj_index(xml_paths: list[Path]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    for path in xml_paths:
        print(f"  indexing {path.name}")
        try:
            tree = etree.parse(str(path), parser)
        except Exception as exc:
            print(f"  FAIL parse {path.name}: {exc}")
            continue
        entries = tree.xpath("//*[local-name()='entryFree'] | //*[local-name()='entry']")
        for entry in entries:
            key_attr = entry.get("key") or ""
            orths = entry.xpath(".//*[local-name()='orth']")
            headwords = []
            if key_attr:
                headwords.append(key_attr)
            for orth in orths:
                if orth.text:
                    headwords.append(orth.text)
            senses = entry.xpath(".//*[local-name()='sense']")
            sense_count = len(senses)
            for hw in headwords:
                hw_clean = re.sub(r"\d+$", "", hw)
                norm = normalize_betacode_key(hw_clean)
                if not norm:
                    continue
                head_unicode = betacode_headword_to_unicode(hw_clean)
                prev = index.get(norm)
                if prev is None or sense_count > prev.get("lsj_sense_count", 0):
                    index[norm] = {
                        "lsj_exists": True,
                        "lsj_sense_count": sense_count,
                        "lsj_headword": head_unicode,
                    }
    return index


def lookup(index: dict, lemma: str) -> dict | None:
    return index.get(lemma_to_lookup_key(lemma))


def verify_top50_common(index: dict, freq_path: Path, skip: set[str] | None = None) -> dict:
    """Resolve LSJ for the 50 most frequent *real* Galen lemmas — must be ~100%.

    Skips auditable unit/numeral/author stoplist debris (e.g. δραχ) so the check
    measures Beta Code matching on words actually in LSJ.
    """
    if not freq_path.exists():
        return {"n": 0, "matched": 0, "rate_pct": 0.0, "misses": []}
    from lib.stoplists import is_numeral_lemma

    skip = skip or set()
    freq = read_json(freq_path)
    ranked = sorted(
        freq.get("lemmas", {}).items(),
        key=lambda kv: kv[1].get("raw_count", 0),
        reverse=True,
    )
    lemmas = []
    for lemma, info in ranked:
        if lemma in skip or is_numeral_lemma(lemma):
            continue
        lemmas.append((lemma, info))
        if len(lemmas) >= 50:
            break
    misses = []
    matched = 0
    details = []
    for lemma, info in lemmas:
        hit = lookup(index, lemma)
        ok = hit is not None
        if ok:
            matched += 1
        else:
            misses.append(lemma)
        details.append(
            {
                "lemma": lemma,
                "raw_count": info.get("raw_count"),
                "lookup_key": lemma_to_lookup_key(lemma),
                "matched": ok,
                "lsj_sense_count": hit.get("lsj_sense_count") if hit else 0,
            }
        )
    n = len(lemmas)
    rate = round(100.0 * matched / n, 2) if n else 0.0
    print(f"LSJ top-50 common lemmas: {matched}/{n} ({rate}%)")
    if misses:
        print(f"  MISSES ({len(misses)}): {', '.join(misses[:20])}")
    return {"n": n, "matched": matched, "rate_pct": rate, "misses": misses, "details": details}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--rebuild-index", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)

    outputs = resolve_path(cfg, "outputs")
    keyness_path = outputs / "keyness_scores.csv"
    if not keyness_path.exists():
        print(f"Missing {keyness_path}; run 05_keyness.py first.")
        return 1

    min_ll = float(cfg.get("keyness_min_log_likelihood", 15.13))
    candidates = []
    with keyness_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("direction") != "overused":
                continue
            if float(row["log_likelihood"]) < min_ll:
                continue
            candidates.append(row)

    print(f"Candidates after G²/overused filter: {len(candidates)}")

    cache_dir = resolve_path(cfg, "lsj_cache")
    index_cache = cache_dir / "_lsj_index.json"
    fetch_cfg = cfg.get("fetch", {})
    session = RateLimitedSession(
        rate_limit_seconds=float(fetch_cfg.get("rate_limit_seconds", 1.0)),
        timeout_seconds=float(fetch_cfg.get("timeout_seconds", 60)),
        max_retries=int(fetch_cfg.get("max_retries", 3)),
    )

    if index_cache.exists() and not args.rebuild_index:
        index = read_json(index_cache)
        sample_keys = list(index.keys())[:20]
        looks_ascii = all(re.fullmatch(r"[a-z]+", k or "") for k in sample_keys if k)
        # Rebuild if index predates sigma/capital normalization (detect by presence of digits)
        has_digit_keys = any(re.search(r"\d", k or "") for k in sample_keys)
        if not looks_ascii or has_digit_keys:
            print("Cached LSJ index looks stale; rebuilding…")
            index = None
        else:
            print(f"Loading cached LSJ index {index_cache}")
    else:
        index = None

    if index is None:
        print("Fetching/indexing Perseus LSJ XML parts…")
        parts = fetch_lsj_parts(cfg, cache_dir, session)
        index = build_lsj_index(parts)
        write_json(index_cache, index)
        print(f"Indexed {len(index)} LSJ headwords")

    from lib.config import project_root
    from lib.stoplists import default_stoplist_dir, load_stoplist

    stop_dir = default_stoplist_dir(project_root())
    skip_common = load_stoplist(stop_dir / "units_numerals.txt") | load_stoplist(
        stop_dir / "authors.txt"
    )
    top50 = verify_top50_common(
        index, outputs / "lemma_frequency_galen.json", skip=skip_common
    )
    write_json(outputs / "lsj_top50_common_check.json", top50)
    if top50["rate_pct"] < 95.0:
        print(
            "ERROR: top-50 common LSJ resolution < 95%. "
            "Beta Code normalization is still wrong — fix before trusting sense counts."
        )

    out_rows = []
    matched = 0
    for row in candidates:
        lemma = row["lemma"]
        hit = lookup(index, lemma)
        out = dict(row)
        if hit:
            matched += 1
            out["lsj_exists"] = True
            out["lsj_sense_count"] = int(hit["lsj_sense_count"])
            out["lsj_headword"] = hit.get("lsj_headword", "")
        else:
            out["lsj_exists"] = False
            out["lsj_sense_count"] = 0
            out["lsj_headword"] = ""
        out_rows.append(out)

    ensure_dir(outputs)
    out_path = outputs / "keyness_with_lsj.csv"
    fieldnames = [
        "lemma",
        "pos",
        "galen_raw",
        "galen_per10k",
        "reference_raw",
        "reference_per10k",
        "log_likelihood",
        "direction",
        "lsj_exists",
        "lsj_sense_count",
        "lsj_headword",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    thin = sum(
        1
        for r in out_rows
        if int(r["lsj_sense_count"]) <= int(cfg.get("punch_list_thin_gloss_threshold", 1))
    )
    overall_rate = round(100.0 * matched / len(out_rows), 2) if out_rows else 0.0
    notes = outputs / "lsj_crossref_notes.txt"
    notes.write_text(
        "LSJ thin-gloss heuristic notes\n"
        "================================\n"
        "Perseus LSJ XML headwords are Beta Code. Lookup keys strip diacritics,\n"
        "digits, sigma variants (s/s1/s2/s3), and the leading * capital marker.\n\n"
        "Thin sense_count is an approximate prioritization aid, not a lexicon gap claim.\n"
        f"\nCandidates: {len(out_rows)}\n"
        f"Matched overall: {matched}/{len(out_rows)} ({overall_rate}%)\n"
        f"Top-50 common lemmas: {top50['matched']}/{top50['n']} ({top50['rate_pct']}%)\n"
        f"Sense count <= threshold: {thin}\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {out_path} (overall matched {matched}/{len(out_rows)} = {overall_rate}%) "
        f"| top-50 common {top50['rate_pct']}%"
    )
    return 0 if top50["rate_pct"] >= 95.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
