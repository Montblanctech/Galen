#!/usr/bin/env python3
"""Stage 01: fetch First1KGreek TEI XML for Galen subset + reference corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.census import filter_galen_works, load_census
from lib.config import load_config, project_root, resolve_path
from lib.http_fetch import RateLimitedSession
from lib.io_utils import ensure_dir, write_json
from lib.urns import urn_to_github_raw_url, urn_to_safe_filename


FIRST1K_CATALOG_URL = (
    "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/catalog.json"
)


def fetch_one(session: RateLimitedSession, urn: str, out_dir: Path, error_log) -> bool:
    url = urn_to_github_raw_url(urn)
    out_path = out_dir / urn_to_safe_filename(urn, ".xml")
    if out_path.exists() and out_path.stat().st_size > 0:
        return True
    resp = session.get(url)
    if resp.status_code == 404:
        error_log.write(f"404\t{urn}\t{url}\n")
        error_log.flush()
        return False
    if resp.status_code != 200:
        error_log.write(f"{resp.status_code}\t{urn}\t{url}\n")
        error_log.flush()
        return False
    out_path.write_bytes(resp.content)
    return True


def load_first1k_catalog(session: RateLimitedSession, cache_path: Path) -> list[dict]:
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        resp = session.get(FIRST1K_CATALOG_URL)
        resp.raise_for_status()
        data = resp.json()
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # First1KGreek catalog.json: { nodeCount, greekWords, ..., catalog: [...] }
    if isinstance(data, dict) and isinstance(data.get("catalog"), list):
        return data["catalog"]
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [{"urn": k, **(v if isinstance(v, dict) else {})} for k, v in data.items()]
    raise ValueError("Unrecognized First1KGreek catalog.json shape")


def extract_urns_from_catalog(entries: list[dict]) -> list[str]:
    urns: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key in ("urn", "URN", "cts_urn", "id"):
            urn = entry.get(key)
            if isinstance(urn, str) and urn.startswith("urn:cts:"):
                urns.append(urn)
                break
        for ed in entry.get("editions", []) or []:
            if not isinstance(ed, dict):
                continue
            ed_urn = ed.get("urn") or ed.get("URN")
            if isinstance(ed_urn, str) and ed_urn.startswith("urn:cts:"):
                urns.append(ed_urn)
        # Some entries nest works
        for work in entry.get("works", []) or []:
            if isinstance(work, dict):
                w_urn = work.get("urn")
                if isinstance(w_urn, str) and w_urn.startswith("urn:cts:"):
                    urns.append(w_urn)
    seen: set[str] = set()
    out: list[str] = []
    for u in urns:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--skip-reference",
        action="store_true",
        help="Only fetch Galen subset (skip overnight reference corpus)",
    )
    parser.add_argument(
        "--all-galen",
        action="store_true",
        help=(
            "Fetch EVERY tlg0057 grc edition in the census (not just category_scope). "
            "Resume-safe: skips files already on disk. Needed for the whole-Galen frequency axis."
        ),
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    root = project_root()
    census_path = (root / cfg["census_file"]).resolve()
    census = load_census(census_path)
    galen_works = filter_galen_works(cfg, census, all_categories=bool(args.all_galen))

    raw_xml = resolve_path(cfg, "raw_xml")
    ref_dir = resolve_path(cfg, "reference_corpus") / "raw_xml"
    ensure_dir(raw_xml)
    ensure_dir(ref_dir)

    fetch_cfg = cfg.get("fetch", {})
    session = RateLimitedSession(
        rate_limit_seconds=float(fetch_cfg.get("rate_limit_seconds", 1.0)),
        timeout_seconds=float(fetch_cfg.get("timeout_seconds", 60)),
        max_retries=int(fetch_cfg.get("max_retries", 3)),
    )

    error_log_path = raw_xml / "_fetch_errors.log"
    manifest = {
        "galen": [],
        "reference": [],
        "galen_ok": 0,
        "galen_fail": 0,
        "all_galen": bool(args.all_galen),
    }

    scope_note = "ALL census categories (whole-Galen)" if args.all_galen else "medical category_scope"
    print(f"Fetching {len(galen_works)} Galen works ({scope_note}) into {raw_xml}")
    with error_log_path.open("a", encoding="utf-8") as err:
        for work in galen_works:
            urn = work["urn"]
            out_path = raw_xml / urn_to_safe_filename(urn, ".xml")
            already = out_path.exists() and out_path.stat().st_size > 0
            ok = fetch_one(session, urn, raw_xml, err)
            manifest["galen"].append(
                {
                    "urn": urn,
                    "ok": ok,
                    "title": work.get("title"),
                    "category": work.get("category"),
                    "skipped_existing": already,
                }
            )
            if ok:
                manifest["galen_ok"] += 1
                print(f"  {'SKIP' if already else 'OK '} {urn} [{work.get('category')}]")
            else:
                manifest["galen_fail"] += 1
                print(f"  FAIL {urn}")

    if not args.skip_reference and cfg.get("reference_corpus", {}).get("mode") == "first1k_minus_galen":
        catalog_cache = resolve_path(cfg, "reference_corpus") / "_first1k_catalog.json"
        ensure_dir(catalog_cache.parent)
        print("Loading First1KGreek catalog for reference corpus…")
        try:
            entries = load_first1k_catalog(session, catalog_cache)
            all_urns = extract_urns_from_catalog(entries)
        except Exception as exc:
            print(f"WARNING: could not parse catalog.json ({exc}); falling back to GitHub tree walk skipped.")
            all_urns = []

        # Exclude Galen (tlg0057); keep Greek editions only (skip eng/lat/deu witnesses)
        ref_urns = [
            u
            for u in all_urns
            if "tlg0057" not in u and ("-grc" in u or u.endswith("grc1") or ".grc" in u)
        ]

        max_works = cfg.get("reference_corpus", {}).get("max_works")
        if max_works is not None:
            ref_urns = ref_urns[: int(max_works)]

        ref_err = ref_dir / "_fetch_errors.log"
        print(f"Fetching {len(ref_urns)} reference works into {ref_dir}")
        ok_n = fail_n = 0
        with ref_err.open("a", encoding="utf-8") as err:
            for i, urn in enumerate(ref_urns, 1):
                ok = fetch_one(session, urn, ref_dir, err)
                manifest["reference"].append({"urn": urn, "ok": ok})
                if ok:
                    ok_n += 1
                else:
                    fail_n += 1
                if i % 25 == 0:
                    print(f"  … {i}/{len(ref_urns)} (ok={ok_n}, fail={fail_n})")
        manifest["reference_ok"] = ok_n
        manifest["reference_fail"] = fail_n
    else:
        print("Skipping reference corpus fetch.")

    write_json(raw_xml / "_fetch_manifest.json", manifest)
    print(
        f"Done. Galen ok={manifest['galen_ok']} fail={manifest['galen_fail']}. "
        f"Manifest: {raw_xml / '_fetch_manifest.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
