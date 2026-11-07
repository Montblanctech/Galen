"""LSJ-Gold scorer: score any lemmatizer on the LSJ-cited benchmark without the project's pipeline.

Ported from ``galen-density-map/pipeline/lsjgold/score.py`` and made standalone. Every gold row is a token
in a First1KGreek edition that LSJ cites for a headword, relocated to its token index. A system is scored
by comparing the lemma it produced at that token with the LSJ headword.

Input layout (one directory per system, one JSONL per work, one line per token)::

    DIR/<system>/urn_cts_greekLit_tlgAAAA.tlgWWW.<edition>.jsonl      {"i": 0, "lemma": "...", ["surface": "..."]}

Only works that exist in a system's directory are scored for that system; every other gold row is reported
as ``missing`` (never as wrong). When one work has several editions in a directory, the edition whose token
at the gold index carries the gold surface is used (when the cache stores surfaces), else the first edition.

Match definitions: ``match_blind`` accent/case-blind key equality (the kit's H4b key), ``match_strict``
accent-preserving equality (NFC + casefold + sigma), ``match_article_neutral`` blind equality after mapping
the article forms to one headword. Wilson 95% intervals throughout.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .normalize import convention_neutral, lemma_nfc, lemma_to_lookup_key
from .stats import pct, wilson_ci

DEFAULT_GOLD = Path(__file__).resolve().parent / "data" / "lsj_gold.csv"
DEFAULT_MIN_AUTHOR_ROWS = 100
AUTHOR_NAMES = {"tlg0085": "Aeschylus", "tlg0011": "Sophocles", "tlg0627": "Hippocrates",
                "tlg0086": "Aristotle", "tlg0031": "Xenophon", "tlg0057": "Galen", "tlg0012": "Homer"}


def rate_block(k: int, n: int) -> dict[str, Any]:
    if not n:
        return {"k": k, "n": n, "pct": None, "wilson95": None}
    lo, hi = wilson_ci(k, n)
    return {"k": k, "n": n, "pct": pct(k, n), "wilson95": [round(100 * lo, 2), round(100 * hi, 2)]}


def load_gold(path: Path | None = None) -> list[dict[str, str]]:
    p = Path(path) if path else DEFAULT_GOLD
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _stems_by_work(sysdir: Path) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for f in sorted(sysdir.glob("urn_cts_greekLit_tlg*.jsonl")):
        parts = f.stem.split("_")
        if len(parts) < 4:
            continue
        ids = parts[3].split(".")
        if len(ids) >= 2:
            out[(ids[0], ids[1])].append(f.stem)
    return out


def _load_tokens(path: Path, wanted: set[int]) -> dict[int, tuple[str, str | None]]:
    """index -> (lemma, surface or None) for the wanted indices only."""
    res: dict[int, tuple[str, str | None]] = {}
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            i = int(r.get("i", n))
            if i in wanted:
                res[i] = (r.get("lemma") or "", r.get("surface"))
    return res


def _surface_ok(gold_surface: str, cached: str | None) -> bool:
    if cached is None:
        return True
    return lemma_to_lookup_key(cached) == lemma_to_lookup_key(gold_surface)


def gold_key(row: dict[str, str]) -> str:
    return row.get("headword_key") or lemma_to_lookup_key(row["headword"])


def collect_system(sysdir: Path, gold: list[dict[str, str]]) -> tuple[dict[int, str | None], int]:
    """Return ({gold row position: lemma or None}, n_misaligned) for one system directory."""
    stems = _stems_by_work(sysdir)
    need: dict[str, set[int]] = defaultdict(set)
    for r in gold:
        for stem in stems.get((r["author"], r["work"]), []):
            need[stem].add(int(r["token_index"]))
    tok = {stem: _load_tokens(sysdir / f"{stem}.jsonl", idxs) for stem, idxs in need.items()}
    got: dict[int, str | None] = {}
    misaligned = 0
    for pos, r in enumerate(gold):
        idx = int(r["token_index"])
        lemma: str | None = None
        mis = False
        for stem in stems.get((r["author"], r["work"]), []):
            hit = tok[stem].get(idx)
            if hit is None:
                continue
            if _surface_ok(r["surface"], hit[1]):
                lemma = hit[0]
                mis = False
                break
            mis = True
        if mis and lemma is None:
            misaligned += 1
        got[pos] = lemma or None
    return got, misaligned


def score_systems(gold: list[dict[str, str]], system_dirs: dict[str, Path], *, min_author_rows: int = DEFAULT_MIN_AUTHOR_ROWS,
                  lsj_index: dict[str, Any] | None = None) -> dict[str, Any]:
    authors = sorted({r["author"] for r in gold})
    works_in_gold = sorted({(r["author"], r["work"]) for r in gold})
    tiers = None
    if lsj_index is not None:
        tiers = []
        for r in gold:
            hit = lsj_index.get(lemma_to_lookup_key(r["headword"]))
            senses = int((hit or {}).get("lsj_sense_count") or 0)
            tiers.append("absent" if senses == 0 else ("thin" if senses == 1 else "rich"))
    res: dict[str, Any] = {
        "gold_rows": len(gold),
        "gold_works": len(works_in_gold),
        "rows_per_author": dict(Counter(r["author"] for r in gold)),
        "min_author_rows": min_author_rows,
        "systems": {},
    }
    for name, sysdir in system_dirs.items():
        got, misaligned = collect_system(sysdir, gold)
        c: Counter = Counter()
        works_present = {w for w in works_in_gold if _stems_by_work(sysdir).get(w)}
        for pos, r in enumerate(gold):
            lem = got[pos]
            if lem is None:
                c["missing"] += 1
                continue
            hk = gold_key(r)
            b = lemma_to_lookup_key(lem) == hk
            s = lemma_nfc(lem) == lemma_nfc(r["headword"])
            a = lemma_to_lookup_key(convention_neutral(lem) or "") == hk
            c["n"] += 1
            c["blind"] += b
            c["strict"] += s
            c["conv"] += a
            c[f"author:{r['author']}:n"] += 1
            c[f"author:{r['author']}:k"] += b
            c[f"val:{r['validation']}:n"] += 1
            c[f"val:{r['validation']}:k"] += b
            if tiers is not None:
                c[f"tier:{tiers[pos]}:n"] += 1
                c[f"tier:{tiers[pos]}:k"] += b
        block: dict[str, Any] = {
            "scored": c["n"],
            "missing": c["missing"],
            "misaligned_surface": misaligned,
            "gold_works_covered": len(works_present),
            "match_blind": rate_block(c["blind"], c["n"]),
            "match_strict": rate_block(c["strict"], c["n"]),
            "match_article_neutral": rate_block(c["conv"], c["n"]),
            "by_author": {au: rate_block(c[f"author:{au}:k"], c[f"author:{au}:n"]) for au in authors
                          if c[f"author:{au}:n"] >= min_author_rows},
            "by_author_below_min": {au: c[f"author:{au}:n"] for au in authors if 0 < c[f"author:{au}:n"] < min_author_rows},
            "by_validation": {v: rate_block(c[f"val:{v}:k"], c[f"val:{v}:n"]) for v in ("morpheus", "quoted") if c[f"val:{v}:n"]},
        }
        if tiers is not None:
            block["by_lsj_tier"] = {t: rate_block(c[f"tier:{t}:k"], c[f"tier:{t}:n"]) for t in ("rich", "thin", "absent") if c[f"tier:{t}:n"]}
        res["systems"][name] = block
    return res


def discover_systems(cache_dirs: list[Path]) -> dict[str, Path]:
    """Each --system-cache DIR holds <system>/ subdirectories."""
    out: dict[str, Path] = {}
    for d in cache_dirs:
        d = Path(d)
        if not d.is_dir():
            raise FileNotFoundError(f"system cache not found: {d}")
        for sub in sorted(d.iterdir()):
            if sub.is_dir() and any(sub.glob("urn_cts_greekLit_tlg*.jsonl")):
                out[sub.name] = sub
    return out


def _cell(r: dict[str, Any] | None) -> str:
    if not r or r.get("pct") is None:
        return "-"
    return f"{r['pct']} ({r['n']})"


def render_markdown(res: dict[str, Any]) -> str:
    authors = sorted(res["rows_per_author"])
    shown = [au for au in authors if any(au in b["by_author"] for b in res["systems"].values())]
    head = ["system", "scored", "missing", "blind % [Wilson 95]", "strict %", "article-neutral %"] + [AUTHOR_NAMES.get(a, a) for a in shown]
    lines = [f"LSJ-Gold: {res['gold_rows']} loci in {res['gold_works']} works. Match = accent-blind headword equality; "
             f"authors with fewer than {res['min_author_rows']} scored rows are not broken out.", "",
             "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, b in res["systems"].items():
        mb = b["match_blind"]
        ci = f" [{mb['wilson95'][0]}-{mb['wilson95'][1]}]" if mb.get("wilson95") else ""
        row = [name, str(b["scored"]), str(b["missing"]), f"**{mb['pct']}**{ci}" if mb.get("pct") is not None else "-",
               str(b["match_strict"].get("pct", "-")), str(b["match_article_neutral"].get("pct", "-"))]
        row += [_cell(b["by_author"].get(a)) for a in shown]
        lines.append("| " + " | ".join(row) + " |")
    for name, b in res["systems"].items():
        extra = ", ".join(f"{v} {_cell(r)}" for v, r in b["by_validation"].items())
        if extra:
            lines.append(f"\n{name}, by validation route (blind %, n): {extra}")
        if b.get("by_lsj_tier"):
            lines.append(f"{name}, by LSJ tier: " + ", ".join(f"{t} {_cell(r)}" for t, r in b["by_lsj_tier"].items()))
        if b["by_author_below_min"]:
            lines.append(f"{name}, authors under the minimum: " + ", ".join(f"{AUTHOR_NAMES.get(a, a)} n={n}" for a, n in b["by_author_below_min"].items()))
        if b["misaligned_surface"]:
            lines.append(f"{name}: {b['misaligned_surface']} rows skipped because the cached surface did not match the gold surface (token streams misaligned).")
    lines.append("\nLSJ cites the rare, dictionary-worthy stratum: this is not overall accuracy.")
    return "\n".join(lines)
