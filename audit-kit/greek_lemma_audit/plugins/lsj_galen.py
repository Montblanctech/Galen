"""M3 plugin — LSJ-citation gold (Galen only, for now).

The project's M3 (``galen-density-map/pipeline/h3m/m3_lsj_gold.py``) mines LSJ
for ``Gal.`` citations by Kühn volume.page, maps each locus to a First1K edition
through the TEI page markers, relocates the cited token as the unique
Morpheus-validated surface in the ±1-page window, and scores odyCy's lemma
against the lexicographers' headword. That mining needs the Perseus LSJ XML, the
Galen TEI and a Morpheus cache, and a Kühn map exists only for Galen — so the
full pipeline stays in the project and this plugin does two cheaper things:

1. **Re-score any system on the published loci.** Given the project's
   ``m3_lsj_citation_gold.csv`` (headword, edition_urn, matched_surface, ...),
   the plugin finds every occurrence of the matched surface in the system's
   token stream for that edition. If *all* occurrences carry the same lemma the
   system's lemma at the cited locus is determined whatever the exact position,
   and the row is scored (accent-blind and accent-strict match to the headword).
   Rows whose surface is absent (``not_located``) or lemmatised inconsistently
   across occurrences (``ambiguous``) are dropped and counted. The funnel is
   reported in full (G3b).
2. **Carry the project's own M3 summary** (``m3_summary.json`` next to the gold
   file) as an external artifact with provenance, so the audit JSON shows the
   rare-stratum point estimate for the reference system.

For a non-Galen author the plugin reports ``not_applicable`` and says why. Bias
caveat (verbatim from the project): LSJ-cited tokens skew toward
lexicographically interesting, often rarer, vocabulary — this is rare-stratum
accuracy, not overall accuracy.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..corpus import Token, Work
from ..normalize import lemma_nfc, lemmas_equal_blind, lemmas_equal_strict, surface_nfc
from ..stats import rate_block

BIAS = ("LSJ-cited tokens skew toward lexicographically interesting (often rarer) vocabulary — rare-stratum "
        "accuracy, not overall accuracy.")


def urn_to_stem(urn: str) -> str:
    return urn.replace(":", "_").replace("/", "_")


class LsjGalenPlugin:
    name = "m3_lsj_citation_gold"

    def __init__(self, gold_path: Path | None, systems: list[str]) -> None:
        self.gold_path = Path(gold_path) if gold_path else None
        self.systems = list(systems)
        self.by_stem: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.n_gold = 0
        self.results: dict[str, list[dict[str, Any]]] = {s: [] for s in systems}
        self.stems_seen: set[str] = set()
        self.load_error = ""
        if self.gold_path and self.gold_path.exists():
            with self.gold_path.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    if not row.get("edition_urn") or not row.get("matched_surface") or not row.get("headword"):
                        continue
                    self.n_gold += 1
                    self.by_stem[urn_to_stem(row["edition_urn"])].append(row)
        elif self.gold_path:
            self.load_error = f"gold file not found: {self.gold_path}"

    @property
    def active(self) -> bool:
        return self.n_gold > 0

    def consume(self, work: Work, outputs: dict[str, list[Token]]) -> None:
        rows = self.by_stem.get(work.stem)
        if not rows:
            return
        self.stems_seen.add(work.stem)
        for system, toks in outputs.items():
            if system not in self.results:
                continue
            index: dict[str, list[str]] = defaultdict(list)
            for t in toks:
                if t.surface:
                    index[surface_nfc(t.surface)].append(t.lemma or "")
            for g in rows:
                occ = index.get(surface_nfc(g["matched_surface"]), [])
                rec = {"headword": g["headword"], "edition_urn": g["edition_urn"], "kuhn": f'{g.get("kuhn_volume","")}.{g.get("kuhn_page","")}',
                       "matched_surface": g["matched_surface"], "n_occurrences": len(occ), "system_lemma": ""}
                if not occ:
                    rec["status"] = "not_located"
                else:
                    distinct = {lemma_nfc(l) for l in occ}
                    if len(distinct) != 1 or "" in distinct:
                        rec["status"] = "ambiguous"
                        rec["system_lemmas"] = ";".join(sorted(distinct))
                    else:
                        lemma = occ[0]
                        rec["system_lemma"] = lemma
                        rec["status"] = "scored"
                        rec["match_blind"] = lemmas_equal_blind(lemma, g["headword"])
                        rec["match_strict"] = lemmas_equal_strict(lemma, g["headword"])
                self.results[system].append(rec)

    def finalize(self, out_dir: Path, author_filter: list[str] | None = None) -> dict[str, Any]:
        base: dict[str, Any] = {"plugin": self.name, "scope": "Galen only (Kühn map exists only for Galen); optional plugin",
                                "bias_caveat": BIAS}
        if self.load_error:
            return {**base, "status": "skipped", "reason": self.load_error}
        if not self.gold_path:
            return {**base, "status": "skipped", "reason": "no --m3-gold file given and none found in the project"}
        if not self.active:
            return {**base, "status": "skipped", "reason": f"gold file has no usable rows: {self.gold_path}"}
        if not self.stems_seen:
            why = "no work in this corpus selection matches a cited Galen edition"
            if author_filter and not any(a.lower() == "tlg0057" for a in author_filter):
                why += f" (author filter {author_filter}; LSJ citation gold is Galen tlg0057 only)"
            return {**base, "status": "not_applicable", "reason": why, "gold_file": str(self.gold_path), "n_gold_rows": self.n_gold}
        out: dict[str, Any] = {**base, "status": "ok", "gold_file": str(self.gold_path), "n_gold_rows": self.n_gold,
                               "n_editions_in_selection": len(self.stems_seen),
                               "method": "surface-unique relocation: every occurrence of the matched surface in the edition "
                                         "must carry the same system lemma; otherwise ambiguous (dropped, counted)",
                               "systems": {}}
        out_dir.mkdir(parents=True, exist_ok=True)
        for system, recs in self.results.items():
            if not recs:
                continue
            funnel = Counter(r["status"] for r in recs)
            scored = [r for r in recs if r["status"] == "scored"]
            kb = sum(1 for r in scored if r["match_blind"])
            ks = sum(1 for r in scored if r["match_strict"])
            path = out_dir / f"m3_rescored_{system}.csv"
            fields = ["status", "headword", "kuhn", "edition_urn", "matched_surface", "n_occurrences", "system_lemma",
                      "system_lemmas", "match_blind", "match_strict"]
            with path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                w.writeheader()
                w.writerows(recs)
            out["systems"][system] = {
                "funnel": {"gold_rows_in_selection": len(recs), "not_located": funnel["not_located"],
                           "ambiguous": funnel["ambiguous"], "scored": funnel["scored"]},
                "match_blind": rate_block(kb, len(scored), "match"),
                "match_strict": rate_block(ks, len(scored), "match"),
                "file": path.name,
            }
        ext = self.gold_path.parent / "m3_summary.json"
        if ext.exists():
            try:
                d = json.loads(ext.read_text(encoding="utf-8"))
                out["project_artifact"] = {
                    "file": str(ext), "applies_to": "reference system (odyCy) in the project's own run",
                    "n_scored": d.get("n_scored"), "rate_blind_pct": d.get("rate_blind_pct"),
                    "wilson95_blind": [d.get("wilson95_lo_pct"), d.get("wilson95_hi_pct")],
                    "rate_strict_pct": d.get("rate_strict_pct"),
                    "wilson95_strict": [d.get("wilson95_strict_lo_pct"), d.get("wilson95_strict_hi_pct")],
                    "mismatch_class_counts": d.get("mismatch_class_counts"), "funnel": d.get("funnel"),
                }
            except Exception as exc:  # pragma: no cover
                out["project_artifact_error"] = str(exc)[:200]
        return out
