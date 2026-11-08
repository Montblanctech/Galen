"""M1 — Morpheus admissibility (error floor), per system.

Logic follows ``galen-density-map/pipeline/h3m/m1_admissibility.py`` (attribution):
unique (surface, lemma) pairs with token weights; verdict per pair is
``admissible`` / ``inadmissible`` / ``no_analysis`` (coverage gap, excluded from
the denominator). The kit adds a fourth, equally separate outcome,
``not_in_cache``: the surface was never queried (offline run) — it is *not* a
coverage gap and *not* an error, and it is reported with its own share so a
cache-only run over a new author cannot pass off missing lookups as anything.

Gates reproduced: G1c (no_analysis share of tokens > 15% -> flag) and, when a
controls file is given, the G1b controls replay with the same expectations.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .corpus import Token, Work
from .morpheus import MorpheusStore
from .normalize import BLIND_KEY_BACKEND, admissibility_verdict, analyses_have_lemma, convention_neutral, surface_nfc
from .stats import pct, wilson_ci

G1C_COVERAGE_MAX = 0.15
CACHE_GAP_FLAG = 0.15
VERDICTS = ("admissible", "inadmissible", "no_analysis", "not_in_cache")


def rate_block(adm: int, inadm: int, none: int, missing: int = 0) -> dict[str, Any]:
    ana = adm + inadm
    tot = adm + inadm + none + missing
    lo, hi = wilson_ci(adm, ana) if ana else (float("nan"), float("nan"))
    return {
        "admissible": adm,
        "inadmissible": inadm,
        "no_analysis": none,
        "not_in_cache": missing,
        "total": tot,
        "analyzable": ana,
        "admissible_pct_of_analyzable": pct(adm, ana),
        "inadmissible_pct_of_analyzable": pct(inadm, ana),
        "no_analysis_pct_of_all": pct(none, tot),
        "not_in_cache_pct_of_all": pct(missing, tot),
        "admissible_wilson95_lo_pct": None if ana == 0 else round(100.0 * lo, 2),
        "admissible_wilson95_hi_pct": None if ana == 0 else round(100.0 * hi, 2),
    }


def expected_g1b(control_id: str, strength: str, control_type: str, provenance: str = "") -> list[str]:
    if control_id == "C01" or "non-word" in (provenance or ""):
        return ["inadmissible", "no_analysis"]
    if control_type == "wrong_plant" and strength == "unambiguous":
        return ["inadmissible"]
    if control_type == "right_anchor":
        return ["admissible"]
    if control_type == "wrong_plant" and strength == "accent":
        return ["admissible"]  # accent-blind primary membership
    return ["admissible", "inadmissible", "no_analysis"]


class M1Accumulator:
    def __init__(self, systems: list[str]) -> None:
        self.systems = list(systems)
        # (system) -> (surface, lemma) -> record
        self.pairs: dict[str, dict[tuple[str, str], dict[str, Any]]] = {s: {} for s in systems}
        self.tokens_seen: Counter[str] = Counter()
        self.tokens_skipped_empty: Counter[str] = Counter()

    def consume(self, work: Work, outputs: dict[str, list[Token]]) -> None:
        for system, toks in outputs.items():
            if system not in self.pairs:
                continue
            table = self.pairs[system]
            for t in toks:
                if not t.surface or not t.lemma:
                    self.tokens_skipped_empty[system] += 1
                    continue
                self.tokens_seen[system] += 1
                key = (t.surface, t.lemma)
                rec = table.get(key)
                if rec is None:
                    rec = {"surface": t.surface, "lemma": t.lemma, "n": 0, "pos": Counter(),
                           "works": set(), "authors": Counter(), "subcorpora": Counter()}
                    table[key] = rec
                rec["n"] += 1
                rec["pos"][t.pos] += 1
                rec["works"].add(work.stem)
                rec["authors"][work.author] += 1
                rec["subcorpora"][work.subcorpus] += 1

    def unique_surfaces(self) -> set[str]:
        out: set[str] = set()
        for table in self.pairs.values():
            for surface, _lemma in table:
                out.add(surface_nfc(surface))
        return out

    def finalize(self, store: MorpheusStore, out_dir: Path, controls: list[dict[str, str]] | None = None) -> dict[str, Any]:
        out_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {
            "method": "Morpheus admissibility: is the system's lemma among the analyzer's readings for the surface "
                      "(accent-blind H4b key)? inadmissible = near-certain error (floor). no_analysis and not_in_cache "
                      "are excluded from the denominator and reported separately.",
            "accent_policy": {"primary": "accent-blind lemma_to_lookup_key (NFC+casefold+BetaCode strip)",
                              "diagnostic": "accent-strict NFC+casefold+sigma", "blind_key_backend": BLIND_KEY_BACKEND},
            "morpheus": store.info(),
            "systems": {},
        }
        for system in self.systems:
            table = self.pairs.get(system) or {}
            if not table:
                result["systems"][system] = {"status": "no_tokens"}
                continue
            tok = Counter()
            typ = Counter()
            strict_tok = strict_typ = 0
            conv_tok = conv_typ = 0  # article-convention-neutral admissible (ἡ/τό/τῶν... -> ὁ before lookup)
            by_pos: dict[str, Counter] = defaultdict(Counter)
            by_author: dict[str, Counter] = defaultdict(Counter)
            by_sub: dict[str, Counter] = defaultdict(Counter)
            rows_by_verdict: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for rec in table.values():
                analyses = store.lookup(rec["surface"])
                if analyses is None:
                    verdict = "not_in_cache"
                    n_an = 0
                else:
                    verdict = admissibility_verdict(rec["lemma"], analyses)
                    n_an = len(analyses)
                n = rec["n"]
                tok[verdict] += n
                typ[verdict] += 1
                if analyses and analyses_have_lemma(rec["lemma"], analyses, accent_blind=False):
                    strict_tok += n
                    strict_typ += 1
                if analyses and (verdict == "admissible" or analyses_have_lemma(convention_neutral(rec["lemma"]) or "", analyses, accent_blind=True)):
                    conv_tok += n
                    conv_typ += 1
                pos = rec["pos"].most_common(1)[0][0] if rec["pos"] else ""
                by_pos[pos][verdict] += n
                for a, c in rec["authors"].items():
                    by_author[a][verdict] += c
                for s, c in rec["subcorpora"].items():
                    by_sub[s][verdict] += c
                if verdict != "admissible":
                    rows_by_verdict[verdict].append({
                        "surface": rec["surface"], "lemma": rec["lemma"], "pos": pos, "token_count": n,
                        "work_count": len(rec["works"]), "works": ";".join(sorted(rec["works"])),
                        "authors": ";".join(f"{a}:{c}" for a, c in rec["authors"].most_common()),
                        "n_morpheus_analyses": n_an,
                        "morpheus_analyses_sample": ";".join((analyses or [])[:8]),
                    })
            tw = rate_block(tok["admissible"], tok["inadmissible"], tok["no_analysis"], tok["not_in_cache"])
            analyzable = tw["analyzable"]
            total = tw["total"]
            no_an_frac = tok["no_analysis"] / total if total else 0.0
            cache_gap_frac = tok["not_in_cache"] / total if total else 0.0
            sys_res: dict[str, Any] = {
                "status": "ok",
                "token_weighted": tw,
                "type_level": rate_block(typ["admissible"], typ["inadmissible"], typ["no_analysis"], typ["not_in_cache"]),
                "accent_strict_admissible_tokens": strict_tok,
                "accent_strict_admissible_pct_of_analyzable": pct(strict_tok, analyzable),
                "accent_strict_admissible_types": strict_typ,
                "article_neutral_admissible_tokens": conv_tok,
                "article_neutral_admissible_pct_of_analyzable": pct(conv_tok, analyzable),
                "article_neutral_admissible_types": conv_typ,
                "article_neutral_note": "lemma mapped through the article convention table (ἡ, τό, τῶν ... -> ὁ) before the accent-blind lookup; reported beside the strict figure, never instead of it",
                "tokens_skipped_empty_surface_or_lemma": self.tokens_skipped_empty[system],
                "by_pos": {p: rate_block(c["admissible"], c["inadmissible"], c["no_analysis"], c["not_in_cache"])
                           for p, c in sorted(by_pos.items(), key=lambda kv: -sum(kv[1].values()))},
                "by_author": {a: rate_block(c["admissible"], c["inadmissible"], c["no_analysis"], c["not_in_cache"])
                              for a, c in sorted(by_author.items(), key=lambda kv: -sum(kv[1].values()))},
                "by_subcorpus": {s: rate_block(c["admissible"], c["inadmissible"], c["no_analysis"], c["not_in_cache"])
                                 for s, c in sorted(by_sub.items())},
                "gates": {
                    "g1c_no_analysis_frac": round(no_an_frac, 4),
                    "g1c_flag_coverage": no_an_frac > G1C_COVERAGE_MAX,
                    "cache_gap_frac": round(cache_gap_frac, 4),
                    "flag_cache_gap": cache_gap_frac > CACHE_GAP_FLAG,
                    "floor_ready": analyzable > 0 and no_an_frac <= G1C_COVERAGE_MAX and cache_gap_frac <= CACHE_GAP_FLAG,
                    "note": "floor_ready=false means the floor covers too little of the corpus: run with --online to "
                            "fill the cache, or treat the rate as provisional.",
                },
                "files": {},
            }
            for verdict in ("inadmissible", "no_analysis", "not_in_cache"):
                rows = rows_by_verdict.get(verdict) or []
                path = out_dir / f"m1_{verdict}_{system}.csv"
                _write_rows(path, rows)
                sys_res["files"][verdict] = path.name
                sys_res["files"][f"{verdict}_rows"] = len(rows)
            result["systems"][system] = sys_res
        if controls:
            result["g1b_controls_replay"] = self._g1b(store, controls)
        return result

    @staticmethod
    def _g1b(store: MorpheusStore, controls: list[dict[str, str]]) -> dict[str, Any]:
        details = []
        mismatches = []
        n_missing = 0
        for row in controls:
            cid = row.get("control_id", "")
            surface = row.get("surface_form", "")
            lemma = row.get("lemma_produced", "")
            analyses = store.lookup(surface)
            if analyses is None:
                verdict = "not_in_cache"
                n_missing += 1
                strict = False
            else:
                verdict = admissibility_verdict(lemma, analyses)
                strict = analyses_have_lemma(lemma, analyses, accent_blind=False)
            expected = expected_g1b(cid, row.get("strength", ""), row.get("control_type", ""), row.get("provenance", ""))
            ok = verdict in expected
            if not ok:
                mismatches.append(cid)
            details.append({"control_id": cid, "control_type": row.get("control_type"), "strength": row.get("strength"),
                            "surface": surface, "lemma_produced": lemma, "expected_verdicts": expected,
                            "verdict": verdict, "accent_strict_admissible": strict,
                            "analyses_sample": (analyses or [])[:8], "matches_expected": ok})
        return {"n": len(controls), "matched_expected": len(controls) - len(mismatches),
                "mismatches": mismatches, "not_in_cache": n_missing, "details": details}


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["surface", "lemma", "pos", "token_count", "work_count", "works", "authors",
              "n_morpheus_analyses", "morpheus_analyses_sample"]
    ranked = sorted(rows, key=lambda r: (-int(r["token_count"]), r["surface"], r["lemma"]))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(ranked)
