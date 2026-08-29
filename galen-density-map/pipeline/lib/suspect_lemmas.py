"""Judgment-free heuristics for residual high-frequency mis-lemmatization.

Plan §3: do NOT overwrite lemmas with guessed corrections. Emit a priority
worklist for Greek-literate spot-check (H3). Separate from the never-a-real-lemma
gate — consistently-wrong lemmas (νεῦρον→νεύρος) pass that gate.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from lib.greek_normalize import casefold_greek
from lib.io_utils import ensure_dir, read_jsonl

# Acc excluded: neuter Nom=Acc makes surface==lemma + Acc common and correct (σῶμα).
OBLIQUE_CASES = {"Gen", "Dat"}
PLURAL_NUMBERS = {"Plur", "Dual"}
# Doubled-consonant orthography artifacts (γιγγν- etc.); strip diacritics first.
DOUBLED_CONSONANT_RE = re.compile(
    r"(γιγγν|γγν|([βγδζθκλμνξπρστφχψ])\2{2,})",
    re.UNICODE,
)


def _strip_diacritics(text: str) -> str:
    import unicodedata

    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def _morph_is_oblique_or_plural(morph: dict | None) -> bool:
    if not morph:
        return False
    case = morph.get("Case") or ""
    number = morph.get("Number") or ""
    # spaCy Morph may use pipe-joined multi-values
    cases = set(case.split("|")) if case else set()
    numbers = set(number.split("|")) if number else set()
    if cases & OBLIQUE_CASES:
        return True
    if numbers & PLURAL_NUMBERS:
        return True
    return False


def _neighbor_tokens(surfaces: list[str], i: int, window: int = 3) -> set[str]:
    """Bag of neighboring surfaces (not full-window strings) for fragmentation Jaccard."""
    out: set[str] = set()
    for j in range(max(0, i - window), min(len(surfaces), i + 1 + window)):
        if j == i:
            continue
        s = surfaces[j]
        if s:
            out.add(casefold_greek(s))
    return out


def _normalized_edit_sim(a: str, b: str) -> float:
    """1 - edit_distance / max_len on diacritic-stripped forms; 0 if lengths diverge a lot."""
    aa, bb = _strip_diacritics(a), _strip_diacritics(b)
    if not aa or not bb:
        return 0.0
    if abs(len(aa) - len(bb)) > max(2, min(len(aa), len(bb)) // 2):
        return 0.0
    # Wagner-Fischer for short Greek lemmas
    prev = list(range(len(bb) + 1))
    for i, ca in enumerate(aa, 1):
        cur = [i]
        for j, cb in enumerate(bb, 1):
            ins, delete, sub = cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    dist = prev[-1]
    return 1.0 - (dist / max(len(aa), len(bb)))


CONTENT_POS = {"NOUN", "VERB", "ADJ"}


def scan_lemmatized(lemmatized_galen: Path) -> dict[str, Any]:
    """Aggregate per-lemma evidence from JSONL (requires morph from stage 03)."""
    lemma_raw: Counter[str] = Counter()
    surface_eq_oblique: Counter[str] = Counter()
    surface_eq_total: Counter[str] = Counter()
    pos_votes: dict[str, Counter[str]] = defaultdict(Counter)
    contexts: dict[str, set[str]] = defaultdict(set)
    has_morph = 0
    tokens = 0

    for path in sorted(lemmatized_galen.glob("*.jsonl")):
        rows = list(read_jsonl(path))
        surfaces = [r.get("surface") or "" for r in rows]
        for i, row in enumerate(rows):
            lemma = row.get("lemma")
            if not lemma:
                continue
            lemma = casefold_greek(lemma)
            surface = casefold_greek(row.get("surface") or "")
            morph = row.get("morph") or {}
            pos = (row.get("pos") or "").upper()
            if morph:
                has_morph += 1
            tokens += 1
            lemma_raw[lemma] += 1
            if pos:
                pos_votes[lemma][pos] += 1
            if surface == lemma:
                surface_eq_total[lemma] += 1
                if _morph_is_oblique_or_plural(morph):
                    surface_eq_oblique[lemma] += 1
            neighbors = _neighbor_tokens(surfaces, i)
            if neighbors:
                contexts[lemma].update(neighbors)

    majority_pos = {
        lem: votes.most_common(1)[0][0] if votes else ""
        for lem, votes in pos_votes.items()
    }
    return {
        "lemma_raw": lemma_raw,
        "surface_eq_oblique": surface_eq_oblique,
        "surface_eq_total": surface_eq_total,
        "contexts": contexts,
        "majority_pos": majority_pos,
        "tokens_with_morph": has_morph,
        "tokens_scanned": tokens,
    }


def _doubled_consonant(lemma: str) -> bool:
    bare = _strip_diacritics(casefold_greek(lemma))
    return bool(DOUBLED_CONSONANT_RE.search(bare))


def build_suspect_rows(scan: dict[str, Any], cfg: dict[str, Any]) -> list[dict]:
    """Rank suspect lemmas by judgment-free heuristic flags."""
    scfg = cfg.get("suspect_lemmas") or {}
    top_n = int(scfg.get("top_n", 50))
    min_raw = int(scfg.get("min_raw_count", 20))
    oblique_frac_min = float(scfg.get("oblique_surface_eq_lemma_min_frac", 0.50))
    jaccard_min = float(scfg.get("fragmentation_jaccard_min", 0.35))
    min_shared = int(scfg.get("fragmentation_min_shared_contexts", 8))
    edit_sim_min = float(scfg.get("fragmentation_edit_sim_min", 0.50))
    # Phantom citation form: almost never surface==lemma, but a near-duplicate
    # lemma IS well attested as surface (νεύρος vs νεῦρον). Plain low surface==lemma
    # on ADJ/VERB is normal inflection — do not flag those alone.
    unattested_max_frac = float(scfg.get("unattested_surface_max_frac", 0.005))
    unattested_min_raw = int(scfg.get("unattested_min_raw_count", 50))
    partner_min_surface_frac = float(scfg.get("unattested_partner_min_surface_frac", 0.15))

    lemma_raw: Counter[str] = scan["lemma_raw"]
    surface_eq_oblique: Counter[str] = scan["surface_eq_oblique"]
    surface_eq_total: Counter[str] = scan["surface_eq_total"]
    contexts: dict[str, set[str]] = scan["contexts"]
    majority_pos: dict[str, str] = scan["majority_pos"]
    max_raw = int(scfg.get("max_raw_count", 8000))  # drop closed-class giants

    candidates = [
        lem
        for lem, n in lemma_raw.most_common()
        if min_raw <= n <= max_raw and majority_pos.get(lem, "") in CONTENT_POS
    ]
    # Cap pair-search pool for runtime; keep the frequent end of the lexicon
    frag_pool = candidates[:800]

    frag_partners: dict[str, list[str]] = defaultdict(list)
    frag_best_j: dict[str, float] = {}
    for i, a in enumerate(frag_pool):
        ca = contexts.get(a) or set()
        if len(ca) < min_shared:
            continue
        for b in frag_pool[i + 1 :]:
            # Prefer near-duplicate lemma strings (fragmentation of one word)
            sim = _normalized_edit_sim(a, b)
            if sim < edit_sim_min:
                continue
            cb = contexts.get(b) or set()
            if len(cb) < min_shared:
                continue
            shared = ca & cb
            if len(shared) < min_shared:
                continue
            union = ca | cb
            jacc = len(shared) / len(union) if union else 0.0
            # Require stronger string similarity for fragmentation (avoid ὅσος/ὅλος-class noise)
            if sim >= 0.60 and jacc >= 0.12:
                pass
            elif sim >= edit_sim_min and jacc >= jaccard_min:
                pass
            else:
                continue
            frag_partners[a].append(b)
            frag_partners[b].append(a)
            score = max(jacc, sim)
            frag_best_j[a] = max(frag_best_j.get(a, 0.0), score)
            frag_best_j[b] = max(frag_best_j.get(b, 0.0), score)

    def _surface_frac(lem: str) -> float:
        raw = lemma_raw[lem]
        return (surface_eq_total[lem] / raw) if raw else 0.0

    rows: list[dict] = []
    for lemma in candidates:
        flags: list[str] = []
        details: list[str] = []
        seq = surface_eq_total[lemma]
        sob = surface_eq_oblique[lemma]
        frac = (sob / seq) if seq else 0.0
        raw = lemma_raw[lemma]
        pos = majority_pos.get(lemma, "")
        if seq >= 3 and frac >= oblique_frac_min:
            flags.append("oblique_or_plural_as_lemma")
            details.append(f"surface==lemma Gen/Dat/Plur {sob}/{seq} ({frac:.2f})")
        surface_frac = _surface_frac(lemma)
        # Phantom headword: almost never surface==lemma, but a near-duplicate IS attested.
        # Partner requirement filters ordinary inflected verbs/adjectives.
        if raw >= unattested_min_raw and surface_frac <= unattested_max_frac:
            partner = None
            partner_frac = 0.0
            # Search all frequency-eligible candidates (not just frag_pool) for a
            # better-attested near-duplicate — φλέψ can sit just outside the pair cap.
            for other in candidates:
                if other == lemma:
                    continue
                if _normalized_edit_sim(lemma, other) < 0.50:
                    continue
                ofrac = _surface_frac(other)
                if ofrac >= partner_min_surface_frac and ofrac > surface_frac + 0.10:
                    if ofrac > partner_frac:
                        partner, partner_frac = other, ofrac
            if partner is not None:
                flags.append("unattested_citation_form")
                details.append(
                    f"surface==lemma {seq}/{raw} ({surface_frac:.3f}); "
                    f"near-dup {partner} attested {partner_frac:.2f}"
                )
                if partner not in frag_partners[lemma]:
                    frag_partners[lemma].append(partner)
        if lemma in frag_partners:
            flags.append("fragmentation_near_duplicate")
            partners = ",".join(frag_partners[lemma][:5])
            details.append(f"sim/jaccard_max={frag_best_j.get(lemma, 0):.2f} partners={partners}")
        if _doubled_consonant(lemma):
            flags.append("doubled_consonant_orthography")
            details.append("matched doubled-consonant pattern")
        if not flags:
            continue
        # Deduplicate flags while preserving order
        seen_f: list[str] = []
        for f in flags:
            if f not in seen_f:
                seen_f.append(f)
        flags = seen_f
        rows.append(
            {
                "lemma": lemma,
                "pos": pos,
                "galen_raw_count": raw,
                "flags": ";".join(flags),
                "detail": " | ".join(details),
                "surface_eq_lemma_n": seq,
                "surface_eq_oblique_or_plur_n": sob,
                "surface_eq_oblique_or_plur_frac": round(frac, 3) if seq else "",
                "fragmentation_partners": ",".join(frag_partners.get(lemma, [])[:8]),
                "fragmentation_jaccard_max": round(frag_best_j[lemma], 3) if lemma in frag_best_j else "",
                "note": "Do NOT auto-correct; priority worklist for Greek-literate spot-check (H3).",
            }
        )

    def _rank_key(r: dict) -> tuple:
        fl = set(r["flags"].split(";"))
        score = 0
        if "unattested_citation_form" in fl:
            score += 12
        if "fragmentation_near_duplicate" in fl:
            score += 8
        if "oblique_or_plural_as_lemma" in fl:
            score += 10
        if "doubled_consonant_orthography" in fl:
            score += 5
        # Prefer zero-attestation phantoms
        seq = int(r["surface_eq_lemma_n"] or 0)
        return (-score, seq, -len(fl), -int(r["galen_raw_count"]), r["lemma"])

    rows.sort(key=_rank_key)

    # Stratify so each heuristic family appears in the top-N worklist.
    # Cap multi-flag intake so oblique-only irregulars (μύες, ἥπατος) are not crowded out.
    multi_cap = max(20, top_n // 2)
    per_flag_cap = max(10, top_n // 4)
    selected: list[dict] = []
    seen: set[str] = set()
    flag_names = [
        "unattested_citation_form",
        "oblique_or_plural_as_lemma",
        "fragmentation_near_duplicate",
        "doubled_consonant_orthography",
    ]
    # Prefer NOUN multi-flag rows (medical terminology) before verb inflection noise
    multi_pool = [r for r in rows if len(r["flags"].split(";")) >= 2]
    multi_pool.sort(
        key=lambda r: (
            0 if r.get("pos") == "NOUN" else 1,
            -int(r["galen_raw_count"]),
        )
    )
    for r in multi_pool[:multi_cap]:
        if r["lemma"] not in seen:
            selected.append(r)
            seen.add(r["lemma"])
    for fname in flag_names:
        taken = 0
        for r in rows:
            if r["lemma"] in seen:
                continue
            if fname not in r["flags"].split(";"):
                continue
            selected.append(r)
            seen.add(r["lemma"])
            taken += 1
            if taken >= per_flag_cap or len(selected) >= top_n:
                break
        if len(selected) >= top_n:
            break
    for r in rows:
        if len(selected) >= top_n:
            break
        if r["lemma"] not in seen:
            selected.append(r)
            seen.add(r["lemma"])
    return selected[:top_n]


def write_suspect_csv(rows: Iterable[dict], out_path: Path) -> int:
    ensure_dir(out_path.parent)
    fieldnames = [
        "lemma",
        "pos",
        "galen_raw_count",
        "flags",
        "detail",
        "surface_eq_lemma_n",
        "surface_eq_oblique_or_plur_n",
        "surface_eq_oblique_or_plur_frac",
        "fragmentation_partners",
        "fragmentation_jaccard_max",
        "note",
    ]
    rows = list(rows)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def run_suspect_report(lemmatized_galen: Path, out_path: Path, cfg: dict[str, Any]) -> dict:
    scan = scan_lemmatized(lemmatized_galen)
    rows = build_suspect_rows(scan, cfg)
    n = write_suspect_csv(rows, out_path)
    flag_counts: Counter[str] = Counter()
    for r in rows:
        for f in r["flags"].split(";"):
            flag_counts[f] += 1
    return {
        "path": str(out_path),
        "n_suspects": n,
        "tokens_scanned": scan["tokens_scanned"],
        "tokens_with_morph": scan["tokens_with_morph"],
        "morph_coverage_pct": round(
            100.0 * scan["tokens_with_morph"] / scan["tokens_scanned"], 2
        )
        if scan["tokens_scanned"]
        else 0.0,
        "flag_counts": dict(flag_counts),
        "head": [
            {"lemma": r["lemma"], "galen_raw_count": r["galen_raw_count"], "flags": r["flags"]}
            for r in rows[:15]
        ],
        # Separate gate from never-a-real-lemma: report must exist; morph should be present.
        "gate_report_emitted": n >= 0 and out_path.exists(),
        "gate_morph_present": scan["tokens_with_morph"] > 0,
    }
