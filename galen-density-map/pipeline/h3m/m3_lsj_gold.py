#!/usr/bin/env python3
"""H3-M M3: LSJ Galen-citation micro-gold (timeboxed, report-only)."""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.beta_keys import betacode_headword_to_unicode, lemma_to_lookup_key
from lib.config import load_config, resolve_path
from lib.edit_distance import has_neighbor_within, levenshtein
from lib.greek_normalize import TOKEN_RE, casefold_greek, nfc
from lib.io_utils import read_json, read_jsonl, write_json

from h3m.kuhn_ref import GAL_IN_TEXT_RE, KuhnRef, parse_kuhn_ref
from h3m.kuhn_index import PageSpan, build_kuhn_index, window_text
from h3m.lemma_eq import (
    analyses_have_lemma,
    lemma_blind_key,
    lemma_nfc,
    lemmas_equal_blind,
    lemmas_equal_strict,
    surface_nfc,
)
from h3m.morpheus_client import MorpheusClient
from h3m.paths import G3A_AUDIT_N, M3_MIN_SCORED, SAMPLE_5K_SEED, h3m_cache_dir, h3m_dir
from h3m.stats_util import pct, wilson_ci

GAL_AUTHORS = {"gal.", "gal", "galen", "galenus"}
XML_PARSER = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el: etree._Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _looks_greek_or_beta(s: str) -> bool:
    if not s:
        return False
    if re.search(r"[\u0370-\u03FF\u1F00-\u1FFF]", s):
        return True
    if re.search(r"[a-zA-Z][)(/\\=|+\d]*", s) and re.search(r"[aeiouhwrtyipsdfgklzcbnmAEIOU]", s):
        return True
    return False


def _to_unicode_form(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if re.search(r"[\u0370-\u03FF\u1F00-\u1FFF]", raw):
        return nfc(raw)
    return betacode_headword_to_unicode(raw)


def _quote_near_bibl(bibl: etree._Element) -> str:
    parent = bibl.getparent()
    if parent is not None and _local(parent.tag) == "cit":
        for q in parent.xpath(".//*[local-name()='quote'] | .//*[local-name()='foreign']"):
            t = "".join(q.itertext()).strip()
            if _looks_greek_or_beta(t) and len(t) >= 2:
                return t
    # preceding quote in the same sense
    prev = bibl.getprevious()
    for _ in range(6):
        if prev is None:
            break
        if _local(prev.tag) in {"quote", "foreign"}:
            t = "".join(prev.itertext()).strip()
            if _looks_greek_or_beta(t):
                return t
        prev = prev.getprevious()
    return ""


def extract_citations_from_entry(entry: etree._Element) -> list[dict[str, Any]]:
    key = entry.get("key") or ""
    orths = [(_text(o) or "") for o in entry.xpath(".//*[local-name()='orth']")]
    hw_raw = key or (orths[0] if orths else "")
    headword = _to_unicode_form(re.sub(r"\d+$", "", hw_raw))
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for bibl in entry.xpath(".//*[local-name()='bibl']"):
        authors = [_text(a).rstrip(".").lower() + ("." if _text(a).endswith(".") else "") for a in bibl.xpath(".//*[local-name()='author']")]
        authors_n = {a.lower().rstrip(".") + "." for a in authors if a}
        n_attr = bibl.get("n") or ""
        is_gal = bool(authors_n & GAL_AUTHORS) or bool(re.match(r"Gal\.?\s*\d", n_attr, re.I))
        if not is_gal:
            continue
        scope_txt = ""
        scopes = bibl.xpath(".//*[local-name()='biblScope']")
        if scopes:
            scope_txt = _text(scopes[0]) or (scopes[0].get("n") or "")
        if not scope_txt:
            scope_txt = n_attr
        ref = parse_kuhn_ref(scope_txt) or parse_kuhn_ref(n_attr)
        if ref is None:
            continue
        quote_raw = _quote_near_bibl(bibl)
        quote_u = _to_unicode_form(quote_raw) if quote_raw else ""
        key3 = (ref.volume, ref.page, quote_u)
        if key3 in seen:
            continue
        seen.add(key3)
        rows.append(
            {
                "headword": headword,
                "headword_key": lemma_blind_key(headword),
                "kuhn_volume": ref.volume,
                "kuhn_page": ref.page,
                "kuhn_part": ref.part,
                "quoted_raw": quote_raw,
                "quoted_form": quote_u,
                "source": "bibl",
            }
        )

    # Regex fallback on the entry's text for Gal. vol.page not already captured.
    blob = " ".join(entry.itertext())
    for m in GAL_IN_TEXT_RE.finditer(blob):
        ref = KuhnRef(int(m.group("vol")), int(m.group("page")), int(m.group("part")) if m.group("part") else None)
        key3 = (ref.volume, ref.page, "")
        if any(r["kuhn_volume"] == ref.volume and r["kuhn_page"] == ref.page for r in rows):
            continue
        rows.append(
            {
                "headword": headword,
                "headword_key": lemma_blind_key(headword),
                "kuhn_volume": ref.volume,
                "kuhn_page": ref.page,
                "kuhn_part": ref.part,
                "quoted_raw": "",
                "quoted_form": "",
                "source": "regex_fallback",
            }
        )
    return rows


def extract_all_citations(lsj_dir: Path) -> list[dict[str, Any]]:
    parts = sorted(lsj_dir.glob("grc.lsj.perseus-eng*.xml"))
    print(f"Extracting LSJ Gal. citations from {len(parts)} XML parts", flush=True)
    all_rows: list[dict[str, Any]] = []
    for path in parts:
        try:
            tree = etree.parse(str(path), XML_PARSER)
        except Exception as exc:
            print(f"  FAIL parse {path.name}: {exc}")
            continue
        entries = tree.xpath("//*[local-name()='entryFree'] | //*[local-name()='entry']")
        n_here = 0
        for entry in entries:
            got = extract_citations_from_entry(entry)
            all_rows.extend(got)
            n_here += len(got)
        print(f"  {path.name}: {n_here} Gal. cites", flush=True)
    print(f"Total Gal. citations extracted: {len(all_rows)}", flush=True)
    return all_rows


def _jsonl_for_stem(lem_root: Path, stem: str) -> Path | None:
    for sub in ("galen", "galen_nonmedical"):
        p = lem_root / sub / f"{stem}.jsonl"
        if p.exists():
            return p
    return None


def _load_ody(lem_root: Path, stem: str, ody_cache: dict[str, dict]) -> dict | None:
    if stem in ody_cache:
        return ody_cache[stem]
    jp = _jsonl_for_stem(lem_root, stem)
    if jp is None:
        return None
    rows = list(read_jsonl(jp))
    surfs = [r.get("surface") or "" for r in rows]
    nfc_surfs = [lemma_nfc(s) for s in surfs]
    by_nfc: dict[str, list[int]] = {}
    for i, k in enumerate(nfc_surfs):
        if not k:
            continue
        by_nfc.setdefault(k, []).append(i)
    bundle = {"rows": rows, "surfs": surfs, "nfc_surfs": nfc_surfs, "by_nfc": by_nfc}
    ody_cache[stem] = bundle
    return bundle


def window_token_list(win_text: str, span: PageSpan) -> list[str]:
    if win_text:
        return TOKEN_RE.findall(win_text)
    return list(span.tokens)


def morpheus_validated_occurrences(
    win_tokens: list[str],
    headword: str,
    client: MorpheusClient,
) -> list[str]:
    """Surfaces in the window whose Morpheus readings contain the LSJ headword (blind)."""
    hits: list[str] = []
    if not headword:
        return hits
    for tok in win_tokens:
        analyses = client.analyze(tok)
        if analyses_have_lemma(headword, analyses, accent_blind=True):
            hits.append(tok)
    return hits


def bind_odycy_lemma(
    surface: str,
    span: PageSpan,
    lem_root: Path,
    ody_cache: dict[str, dict],
) -> tuple[str, str]:
    """Map a Morpheus-validated page surface to a unique odyCy lemma.

    Returns (lemma, status) where status is ``unambiguous`` or
    ``invalid_location_rejected``.
    """
    bundle = _load_ody(lem_root, span.stem, ody_cache)
    if bundle is None:
        return "", "invalid_location_rejected"
    form_n = lemma_nfc(surface)
    idxs = bundle["by_nfc"].get(form_n) or []
    if not idxs:
        return "", "invalid_location_rejected"
    lemmas = {(bundle["rows"][i].get("lemma") or "") for i in idxs}
    lemmas.discard("")
    if len(lemmas) != 1:
        return "", "invalid_location_rejected"
    return next(iter(lemmas)), "unambiguous"


def share_stem(a: str, b: str) -> bool:
    """True if two lemmas share a stem (accent-blind key, edit-distance or prefix)."""
    ka, kb = lemma_blind_key(a), lemma_blind_key(b)
    if not ka or not kb or ka == kb:
        return bool(ka) and ka == kb
    if levenshtein(ka, kb) <= 2:
        return True
    n = min(len(ka), len(kb))
    if n < 4:
        return False
    pref = 0
    for ca, cb in zip(ka, kb):
        if ca != cb:
            break
        pref += 1
    return pref >= n - 1


def is_lsj_headword(lemma: str, lsj_index: dict) -> bool:
    key = lemma_to_lookup_key(lemma or "")
    return bool(key) and key in lsj_index


def collect_surfaces_by_lemma(*dirs: Path) -> dict[str, set[str]]:
    """P3-2 map: lemma (casefold) → surfaces assigned to it in the frozen JSONL."""
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


def classify_mismatch(
    headword: str,
    surface: str,
    odycy_lemma: str,
    lsj_index: dict,
    surfaces_by_lemma: dict[str, set[str]],
    max_ed: int = 2,
) -> str:
    """F3 taxonomy: passthrough / garble / variant_headword / other_substitution."""
    if not odycy_lemma:
        return "other_substitution"
    if lemma_nfc(odycy_lemma) == lemma_nfc(surface):
        return "passthrough"
    if is_lsj_headword(odycy_lemma, lsj_index) and share_stem(odycy_lemma, headword):
        return "variant_headword"
    own = surfaces_by_lemma.get(casefold_greek(odycy_lemma)) or set()
    if not is_lsj_headword(odycy_lemma, lsj_index) and not has_neighbor_within(
        casefold_greek(odycy_lemma), own, max_ed
    ):
        return "garble"
    return "other_substitution"


def locate_and_score(
    cit: dict[str, Any],
    index: dict,
    lem_root: Path,
    ody_cache: dict[str, dict],
    client: MorpheusClient,
) -> dict[str, Any]:
    """F1/F2: Morpheus-validated unique surface in the ±1 page window; then score odyCy."""
    vol, page = cit["kuhn_volume"], cit["kuhn_page"]
    windows = window_text(index, vol, page, pad=1)
    quoted = (cit.get("quoted_form") or "").strip()
    out = {
        **cit,
        "edition_urn": "",
        "matched_surface": "",
        "odycy_lemma": "",
        "match_verdict": "",
        "match_blind": "",
        "match_strict": "",
        "mismatch_class": "",
        "quoted_form_in_window": False,
        "disambiguation_status": "unmapped",
    }
    if not windows:
        return out

    headword = cit.get("headword") or ""
    validated: list[tuple[PageSpan, str]] = []
    quoted_seen = False
    qn = lemma_nfc(quoted) if quoted else ""
    for span, win_text in windows:
        toks = window_token_list(win_text, span)
        if qn and any(lemma_nfc(t) == qn for t in toks):
            quoted_seen = True
        for tok in morpheus_validated_occurrences(toks, headword, client):
            validated.append((span, tok))
    out["quoted_form_in_window"] = quoted_seen

    if not validated:
        out["disambiguation_status"] = "not_located"
        return out
    if len(validated) > 1:
        out["disambiguation_status"] = "ambiguous"
        out["edition_urn"] = validated[0][0].edition_urn
        out["matched_surface"] = validated[0][1]
        return out

    span, surface = validated[0]
    lemma, bind_status = bind_odycy_lemma(surface, span, lem_root, ody_cache)
    out["edition_urn"] = span.edition_urn
    out["matched_surface"] = surface
    if bind_status != "unambiguous":
        out["disambiguation_status"] = "invalid_location_rejected"
        return out
    out["odycy_lemma"] = lemma
    out["disambiguation_status"] = "unambiguous"
    blind = lemmas_equal_blind(lemma, headword)
    strict = lemmas_equal_strict(lemma, headword)
    out["match_blind"] = "match" if blind else "mismatch"
    out["match_strict"] = "match" if strict else "mismatch"
    out["match_verdict"] = out["match_blind"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--max-cites", type=int, default=0)
    args = parser.parse_args()
    _configure_stdio()
    cfg = load_config(args.config)

    out_dir = h3m_dir(cfg)
    cache_dir = h3m_cache_dir(cfg)
    lsj_dir = resolve_path(cfg, "lsj_cache")
    raw_xml = resolve_path(cfg, "raw_xml")
    lem_root = resolve_path(cfg, "lemmatized")
    galen_dir = lem_root / "galen"
    nonmed_dir = resolve_path(cfg, "lemmatized_galen_nonmedical")

    cites = extract_all_citations(lsj_dir)
    funnel = {
        "citations_found": len(cites),
        "mappable": 0,
        "located": 0,
        "unambiguous": 0,
        "scored": 0,
        "dropped_unmapped": 0,
        "dropped_not_located": 0,
        "dropped_ambiguous": 0,
        "invalid_location_rejected": 0,
        "regex_fallback": sum(1 for c in cites if c.get("source") == "regex_fallback"),
        "with_quoted_form": sum(1 for c in cites if c.get("quoted_form")),
    }
    if args.max_cites:
        cites = cites[: args.max_cites]

    index = build_kuhn_index(raw_xml)
    client = MorpheusClient(cache_dir / "morpheus_by_surface.jsonl")
    cache_hygiene = client.repair_corrupt_lines()

    mappable_cites: list[dict[str, Any]] = []
    for cit in cites:
        windows = window_text(index, cit["kuhn_volume"], cit["kuhn_page"], pad=1)
        if not windows:
            funnel["dropped_unmapped"] += 1
            continue
        funnel["mappable"] += 1
        mappable_cites.append(cit)

    # Pre-warm Morpheus on every surface in mappable windows (F1 needs the analyzer).
    warm: list[str] = []
    seen_surf: set[str] = set()
    for cit in mappable_cites:
        for span, win_text in window_text(index, cit["kuhn_volume"], cit["kuhn_page"], pad=1):
            for tok in window_token_list(win_text, span):
                k = surface_nfc(tok)
                if k and k not in seen_surf:
                    seen_surf.add(k)
                    warm.append(tok)
    print(f"F1 pre-warm: {len(warm)} unique window surfaces", flush=True)
    client.analyze_many(warm, progress_every=200)
    client.rewrite_cache_utf8()

    lsj_index_path = lsj_dir / "_lsj_index.json"
    lsj_index = read_json(lsj_index_path) if lsj_index_path.exists() else {}
    print(f"LSJ index: {len(lsj_index)} keys from {lsj_index_path.name}", flush=True)
    print("Collecting lemma→surface map for F3 hallucination test...", flush=True)
    surfaces_by_lemma = collect_surfaces_by_lemma(galen_dir, nonmed_dir)
    print(f"  lemmas with assigned surfaces: {len(surfaces_by_lemma)}", flush=True)

    ody_cache: dict[str, dict] = {}
    gold_rows: list[dict[str, Any]] = []
    mapped_for_audit: list[dict[str, Any]] = []

    for i, cit in enumerate(mappable_cites, 1):
        if i % 500 == 0:
            print(
                f"  locating {i}/{len(mappable_cites)} scored={funnel['scored']} "
                f"ambiguous={funnel['dropped_ambiguous']}",
                flush=True,
            )
        rec = locate_and_score(cit, index, lem_root, ody_cache, client)
        status = rec["disambiguation_status"]
        if status == "unmapped":
            funnel["dropped_unmapped"] += 1
            continue
        if status == "not_located":
            funnel["dropped_not_located"] += 1
            continue
        if status == "ambiguous":
            funnel["dropped_ambiguous"] += 1
            continue
        funnel["located"] += 1
        if status == "invalid_location_rejected":
            funnel["invalid_location_rejected"] += 1
            continue
        funnel["unambiguous"] += 1
        funnel["scored"] += 1
        if rec.get("match_verdict") == "mismatch":
            rec["mismatch_class"] = classify_mismatch(
                rec.get("headword") or "",
                rec.get("matched_surface") or "",
                rec.get("odycy_lemma") or "",
                lsj_index,
                surfaces_by_lemma,
            )
        gold_rows.append(rec)
        windows = window_text(index, cit["kuhn_volume"], cit["kuhn_page"], pad=1)
        win_txt = windows[0][1] if windows else ""
        needle = rec.get("matched_surface") or ""
        excerpt = win_txt[:400]
        if needle and win_txt:
            idx = win_txt.find(needle)
            if idx < 0:
                idx = lemma_nfc(win_txt).find(lemma_nfc(needle))
            if idx >= 0:
                excerpt = win_txt[max(0, idx - 160) : idx + len(needle) + 160]
        mapped_for_audit.append({**rec, "page_excerpt": excerpt})

    n = len(gold_rows)
    n_blind = sum(1 for r in gold_rows if r.get("match_blind") == "match")
    n_strict = sum(1 for r in gold_rows if r.get("match_strict") == "match")
    class_counts = Counter(r.get("mismatch_class") or "match" for r in gold_rows)
    n_variant = class_counts.get("variant_headword", 0)
    n_passthrough = class_counts.get("passthrough", 0)
    n_garble = class_counts.get("garble", 0)
    n_other = class_counts.get("other_substitution", 0)
    n_mismatch = n - n_blind
    lo_b, hi_b = wilson_ci(n_blind, n) if n else (float("nan"), float("nan"))
    lo_s, hi_s = wilson_ci(n_strict, n) if n else (float("nan"), float("nan"))
    n_variant_as_ok = n_blind + n_variant
    lo_v, hi_v = wilson_ci(n_variant_as_ok, n) if n else (float("nan"), float("nan"))
    n_ex_var = n - n_variant
    n_blind_ex = n_blind
    lo_e, hi_e = wilson_ci(n_blind_ex, n_ex_var) if n_ex_var else (float("nan"), float("nan"))

    fieldnames = [
        "headword",
        "kuhn_volume",
        "kuhn_page",
        "kuhn_part",
        "edition_urn",
        "quoted_form",
        "quoted_form_in_window",
        "matched_surface",
        "odycy_lemma",
        "match_verdict",
        "match_blind",
        "match_strict",
        "mismatch_class",
        "disambiguation_status",
        "source",
    ]
    gold_path = out_dir / "m3_lsj_citation_gold.csv"
    with gold_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(gold_rows)

    mismatch_rows = [r for r in gold_rows if r.get("match_blind") == "mismatch"]
    with (out_dir / "m3_mismatch_taxonomy.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(mismatch_rows)

    rng = random.Random(SAMPLE_5K_SEED)
    audit_pool = mapped_for_audit if mapped_for_audit else gold_rows
    audit = rng.sample(audit_pool, min(G3A_AUDIT_N, len(audit_pool))) if audit_pool else []
    audit_rows = []
    for rec in audit:
        excerpt = rec.get("page_excerpt") or ""
        q = rec.get("matched_surface") or ""
        present = bool(q) and (
            q in excerpt or (lemma_nfc(q) in lemma_nfc(excerpt) if excerpt else False)
        )
        audit_rows.append(
            {
                "headword": rec.get("headword"),
                "kuhn_volume": rec.get("kuhn_volume"),
                "kuhn_page": rec.get("kuhn_page"),
                "edition_urn": rec.get("edition_urn"),
                "quoted_form": rec.get("quoted_form"),
                "matched_surface": rec.get("matched_surface"),
                "form_in_page_excerpt": present,
                "page_excerpt": excerpt,
            }
        )
    with (out_dir / "m3_g3a_locus_audit.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "headword",
                "kuhn_volume",
                "kuhn_page",
                "edition_urn",
                "quoted_form",
                "matched_surface",
                "form_in_page_excerpt",
                "page_excerpt",
            ],
        )
        w.writeheader()
        w.writerows(audit_rows)

    parked = n < M3_MIN_SCORED
    rate_blind = pct(n_blind, n)
    rate_strict = pct(n_strict, n)
    summary = {
        "funnel": funnel,
        "n_scored": n,
        "n_match_blind": n_blind,
        "n_match_strict": n_strict,
        "rate_pct": rate_blind,
        "rate_blind_pct": rate_blind,
        "wilson95_lo_pct": None if n == 0 else round(100.0 * lo_b, 2),
        "wilson95_hi_pct": None if n == 0 else round(100.0 * hi_b, 2),
        "rate_strict_pct": rate_strict,
        "wilson95_strict_lo_pct": None if n == 0 else round(100.0 * lo_s, 2),
        "wilson95_strict_hi_pct": None if n == 0 else round(100.0 * hi_s, 2),
        "n_mismatch": n_mismatch,
        "mismatch_class_counts": {
            "passthrough": n_passthrough,
            "garble": n_garble,
            "variant_headword": n_variant,
            "other_substitution": n_other,
        },
        "rate_blind_treating_variant_as_ok_pct": pct(n_variant_as_ok, n),
        "wilson95_variant_as_ok_lo_pct": None if n == 0 else round(100.0 * lo_v, 2),
        "wilson95_variant_as_ok_hi_pct": None if n == 0 else round(100.0 * hi_v, 2),
        "rate_blind_excluding_variant_pct": pct(n_blind_ex, n_ex_var),
        "wilson95_excluding_variant_lo_pct": None if n_ex_var == 0 else round(100.0 * lo_e, 2),
        "wilson95_excluding_variant_hi_pct": None if n_ex_var == 0 else round(100.0 * hi_e, 2),
        "stratum": "LSJ-cited tokens (rare / lexicographically interesting); not overall accuracy",
        "parked": parked,
        "park_reason": (
            f"usable N={n} < {M3_MIN_SCORED}; M1+M2 still bound §5"
            if parked
            else ""
        ),
        "bias_caveat": (
            "LSJ-cited tokens skew toward lexicographically interesting (often rarer) "
            "vocabulary — report as rare-stratum accuracy, not overall accuracy. "
            "Location is Morpheus-validated (headword ∈ analyzer readings of the page "
            "surface); quoted LSJ text is context only, never the target token."
        ),
        "cache_hygiene": {
            "corrupt_lines": cache_hygiene.get("corrupt_lines"),
            "refetched": cache_hygiene.get("refetched"),
            "morpheus": client.info(),
        },
        "g3a": {
            "n": len(audit_rows),
            "form_in_excerpt": sum(1 for r in audit_rows if r["form_in_page_excerpt"]),
        },
        "g3b": "full funnel reported; no silent drops",
        "do_not_publish_old_rate": "59.79% from the quoted-collocate/circular locator is invalid",
    }
    write_json(out_dir / "m3_summary.json", summary)

    if parked:
        notes = out_dir / "m3_attempt_notes.md"
        notes.write_text(
            "# M3 attempt notes\n\n"
            f"Usable scored N = **{n}** (threshold {M3_MIN_SCORED}). "
            "Parked per spec; M1+M2 still bound §5.\n\n"
            "## Funnel\n\n"
            + "\n".join(f"- `{k}`: {v}" for k, v in funnel.items())
            + "\n\n"
            f"Accent-blind match rate: {rate_blind}% ({n_blind}/{n}).\n",
            encoding="utf-8",
        )
        print(f"M3 parked (N={n}). Wrote {notes}")
    else:
        print(
            f"M3 scored {n}: blind {rate_blind}% ({n_blind}/{n}; "
            f"95% CI {summary['wilson95_lo_pct']}-{summary['wilson95_hi_pct']}); "
            f"strict {rate_strict}% ({n_strict}/{n}; "
            f"95% CI {summary['wilson95_strict_lo_pct']}-{summary['wilson95_strict_hi_pct']})"
        )
        print(
            f"  mismatch classes: passthrough={n_passthrough} garble={n_garble} "
            f"variant_headword={n_variant} other={n_other}"
        )
        print(
            f"  funnel: mappable={funnel['mappable']} not_located={funnel['dropped_not_located']} "
            f"ambiguous={funnel['dropped_ambiguous']} "
            f"invalid_location_rejected={funnel['invalid_location_rejected']} scored={n}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
