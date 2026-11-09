"""LS-Gold, stage 1b — relocate Lewis & Short's CTS-tagged citations into the project's Latin token streams.

The Perseus Lewis & Short XML (data/latin_feasibility/lat.ls.perseus-eng2.xml, CC BY-SA 4.0) carries
``<bibl n="urn:cts:latinLit:phi0474.phi005.perseus-lat1:2:4:35">`` on ~280k citations. For every cited work this
project holds (data/latin_corpus/units + tokens, written by tokenize_editions.py), this stage:
  1. extracts (headword, locator, quoted form) per citation: headword = the entry's first <orth> (macrons stripped,
     latnorm.key for comparison), quoted form = the <quote> that precedes the <bibl> inside one <cit>;
  2. resolves the locator to a unit of one of the work's editions (several editions per work are tried in file
     order: Livy's decades are four files), window = cited unit ± 1 sibling, with the Greek fall-backs (prefix match,
     chapter -> section aliases for Pliny, pr/praef spellings, empty locator segments removed);
  3. validates each surface in the window against the headword with two offline morphological oracles
     (oracle.py): collatinus — Collatinus's analyses of the surface contain the headword (key-blind);
     whitaker — Whitaker's Words' analyses do; quoted — the surface equals L&S's quoted form for that citation and
     shares the headword's first two letters, used only when neither oracle analyses the surface at all;
     exactly one validated token in the window -> gold locus; several -> ambiguous; none -> not_located.
Report only; nothing is edited. Outputs data/qc/lsgold/ls_gold_v0.csv (+ relocation_stats.json, unlocated.csv,
ls_citation_counts.json = Latin CTS citations per L&S entry id, for the citation-frequency stratum).

Run (.venv-lat): python -X utf8 -I pipeline/lsgold/relocate_la.py [--works phi0690.phi003,phi0474.phi005] [--no-oracle]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from latnorm import key as lkey, strip_marks, tokens as latin_tokens  # noqa: E402

GDM = HERE.parent.parent
CORPUS = GDM / "data" / "latin_corpus"
LS_XML = GDM / "data" / "latin_feasibility" / "lat.ls.perseus-eng2.xml"
OUT = GDM / "data" / "qc" / "lsgold"
URN_RE = re.compile(r"urn:cts:latinLit:((?:phi|stoa)\d{4})\.((?:phi|stoa)\d{3})(?:\.([A-Za-z0-9-]+))?(?::([^\s\"]*))?")
PRAEF = {"pr", "praef", "pref", "prooem", "proem", "prol", "prologus", "praefatio"}
# Lewis & Short numbers Horace's Odes phi0893.phi002 (book:ode:line); in canonical-latinLit phi002 is the Carmen Saeculare
# and the Odes are phi001. A three-part L&S locator on phi002 is an Odes citation.
WORK_REMAP = {("phi0893", "phi002", 3): "phi0893.phi001"}


def edition_work(au: str, wk: str, loc: str) -> str:
    depth = len([p for p in loc.split(":") if p])
    return WORK_REMAP.get((au, wk, depth), f"{au}.{wk}")


def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


# ---------------------------------------------------------------- held works
def held_works() -> dict[str, list[str]]:
    """work id (phi0474.phi005) -> [edition stems in file order] for which units + tokens exist."""
    out: dict[str, list[str]] = defaultdict(list)
    for u in sorted((CORPUS / "units").glob("*.json")):
        stem = u.stem
        if not (CORPUS / "tokens" / f"{stem}.jsonl").exists():
            continue
        m = re.match(r"((?:phi|stoa)\d{4}\.(?:phi|stoa)\d{3})\.", stem)
        if m:
            out[m.group(1)].append(stem)
    return dict(out)


class Edition:
    def __init__(self, stem: str):
        d = json.loads((CORPUS / "units" / f"{stem}.json").read_text(encoding="utf-8"))
        self.stem = stem
        self.keys: list[str] = [u[0] for u in d["units"]]
        self.pos: dict[str, int] = {k: i for i, k in enumerate(self.keys)}
        self.span: dict[str, tuple[int, int]] = {u[0]: (u[1], u[1] + u[2]) for u in d["units"]}
        self.aliases: dict[str, list[str]] = d.get("aliases", {})
        self.surfaces: list[str] = []
        with (CORPUS / "tokens" / f"{stem}.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                self.surfaces.append(json.loads(line)["surface"])
        # locator variants: pr/praef family and lower-case keys; a prologue keyed 'prologue:pr:14' answers to 'prol:14'
        self.alt: dict[str, str] = {}
        for k in self.keys:
            parts = k.split(":")
            if any(p.lower() in PRAEF for p in parts):
                for v in PRAEF:
                    self.alt[":".join(v if p.lower() in PRAEF else p for p in parts)] = k
                if len(parts) >= 2:
                    for v in PRAEF:
                        self.alt.setdefault(f"{v}:{parts[-1]}", k)
            if k != k.lower():
                self.alt[k.lower()] = k
        # children per prefix, in document order, for scene-relative line numbers (Plautus: L&S 'act:scene:line-in-scene')
        self.children: dict[str, list[str]] = defaultdict(list)
        for k in self.keys:
            parts = k.split(":")
            if len(parts) >= 2 and "@" not in k:
                self.children[":".join(parts[:-1])].append(k)

    def _around(self, i: int) -> list[str]:
        """The unit at i and its neighbours; remembers the cited unit so a common headword found in several units
        of the window is taken from the cited unit itself when it occurs there exactly once."""
        self.center = self.keys[i]
        return self.keys[max(0, i - 1): i + 2]

    def _hit(self, loc: str) -> list[str]:
        k = loc if loc in self.pos else self.alt.get(loc) or self.alt.get(loc.lower())
        if k is not None:
            i = self.pos[k]
            return self._around(i)
        if loc in self.aliases:                       # Pliny chapter -> its sections
            return [a for a in self.aliases[loc] if a in self.pos]
        return []

    def window(self, loc: str) -> list[str]:
        """Units to search for a Lewis & Short locator. Forms tried in order: the locator itself (empty segments
        dropped: 'Orat::1:25:117' -> 'Orat:1:25:117'); without leading non-numeric labels ('1:25:117'); first and
        last segment only (book:section where the edition has no chapter level: De Oratore '1:117'); a unique unit with
        the same first and last segment one level deeper (Verrines 'actio 1 § 12' -> '1:x:12'); prefix match; a trailing
        letter dropped; then the locator shortened from the right (a section cited into an edition that stops at the
        chapter). Returns [] when nothing resolves."""
        self.center = None
        parts = [p for p in loc.split(":") if p != ""]
        parts = [re.sub(r"[^\w.-]", "", p) for p in parts]
        parts = [p for p in parts if p]
        if not parts:
            return []
        forms = [":".join(parts)]
        num = parts
        while num and not re.match(r"^\d", num[0]) and num[0].lower() not in PRAEF and len(num) > 1:
            num = num[1:]
        if num != parts:
            forms.append(":".join(num))
        if len(num) >= 3:
            forms.append(f"{num[0]}:{num[-1]}")
        for f in forms:
            w = self._hit(f)
            if w:
                return w
        base = ":".join(num)
        if len(num) >= 2:
            same = [x for x in self.keys if x.startswith(num[0] + ":") and x.endswith(":" + num[-1]) and x.count(":") == len(num)]
            if len(same) == 1:
                i = self.pos[same[0]]
                return self._around(i)
        # the edition carries one level more at the front (Juvenal book:satire:line for L&S satire:line; Seneca
        # book:letter:section; Catullus genre:poem:line): a unique unit ending in the whole locator
        deeper = [x for x in self.keys if x.endswith(":" + base) and x.count(":") == len(num)]
        if len(deeper) == 1:
            i = self.pos[deeper[0]]
            return self._around(i)
        # scene-relative line numbers (Plautus/Terence: L&S act:scene:line-in-scene, the edition numbers lines through the play)
        if len(num) == 3 and num[-1].isdigit():
            kids = self.children.get(":".join(num[:-1]), [])
            n = int(num[-1])
            if kids and 1 <= n <= len(kids):
                i = self.pos[kids[n - 1]]
                return self._around(i)
        pref = [x for x in self.keys if x.startswith(base + ":")]
        if pref:
            return pref
        if len(num) == 1:
            tails = [x for x in self.keys if x.endswith(":" + base)]
            if len(tails) == 1:
                i = self.pos[tails[0]]
                return self._around(i)
        stripped = re.sub(r"[a-z]$", "", base)
        if stripped != base:
            w = self._hit(stripped)
            if w:
                return w
        short = list(num)
        while len(short) > 1:
            short = short[:-1]
            w = self._hit(":".join(short))
            if w:
                return w
        return []

    def tokens_in(self, unit_key: str) -> list[tuple[str, int]]:
        a, b = self.span.get(unit_key, (0, 0))
        return [(self.surfaces[i], i) for i in range(a, b)]


# ---------------------------------------------------------------- citations
def citations(held: set[str]) -> tuple[list[dict], Counter]:
    rows: list[dict] = []
    per_entry: Counter = Counter()
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    tree = etree.parse(str(LS_XML), parser)
    for entry in tree.xpath("//*[local-name()='entryFree'] | //*[local-name()='entry']"):
        ekey = entry.get("key") or ""
        eid = entry.get("id") or ekey
        orth = entry.xpath("./*[local-name()='orth']")
        head_raw = "".join(orth[0].itertext()).strip() if orth else re.sub(r"\d+$", "", ekey)
        headword = strip_marks(head_raw)
        hk = lkey(headword)
        if not hk:
            continue
        for bibl in entry.xpath(".//*[local-name()='bibl']"):
            n = bibl.get("n") or ""
            m = URN_RE.search(n)
            if not m:
                continue
            au, wk, ed, loc = m.groups()
            if not loc:
                continue
            per_entry[eid] += 1
            if edition_work(au, wk, loc) not in held:
                continue
            quote = ""
            par = bibl.getparent()
            if par is not None and local(par.tag) == "cit":
                qs = [q for q in par if local(q.tag) == "quote"]
                if qs:
                    quote = " ".join("".join(qs[0].itertext()).split())
            rows.append({"headword": headword, "headword_key": hk, "author": au, "work": wk, "cited_edition": ed or "",
                         "locator": loc.strip(), "quoted_form": quote, "entry_key": ekey, "entry_id": eid})
    return rows, per_entry


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", default="", help="comma list of work ids (phi0690.phi003) to restrict to")
    ap.add_argument("--no-oracle", action="store_true", help="quoted-form validation only (oracle unavailable)")
    ap.add_argument("--oracle-cache", type=Path, default=CORPUS / "oracle_cache.jsonl")
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    held = held_works()
    if a.works:
        keep = set(a.works.split(","))
        held = {k: v for k, v in held.items() if k in keep}
    print(f"held works: {len(held)} ({sum(len(v) for v in held.values())} editions)", flush=True)

    cites, per_entry = citations(set(held))
    (OUT / "ls_citation_counts.json").write_text(json.dumps(dict(per_entry), ensure_ascii=False), encoding="utf-8")
    print(f"citations into held works: {len(cites)}; entries with Latin CTS citations: {len(per_entry)} ({time.time()-t0:.0f}s)", flush=True)
    by_work: dict[str, list[dict]] = defaultdict(list)
    for c in cites:
        by_work[edition_work(c["author"], c["work"], c["locator"])].append(c)

    oracle = None
    if not a.no_oracle:
        try:
            from oracle import Oracle  # type: ignore
            oracle = Oracle(a.oracle_cache)
        except Exception as exc:
            print(f"oracle unavailable ({exc}); quoted-form validation only", flush=True)

    gold, unlocated = [], []
    stats: Counter = Counter()
    for work, rows in sorted(by_work.items(), key=lambda kv: -len(kv[1])):
        eds = [Edition(s) for s in held[work]]
        # oracle fill for every surface in every window of this work, in one bulk call
        if oracle is not None:
            need = set()
            for c in rows:
                for ed in eds:
                    for k in ed.window(c["locator"]):
                        for s, _ in ed.tokens_in(k):
                            need.add(s.lower())
            try:
                oracle.bulk(sorted(need))
            except Exception as exc:
                print(f"  oracle bulk failed on {work}: {exc}", flush=True)
        n_loc_before = stats["located"]
        for c in rows:
            hk = c["headword_key"]
            qk = lkey(c["quoted_form"]) if c["quoted_form"] else ""
            qtoks = [lkey(t) for t in latin_tokens(c["quoted_form"])] if c["quoted_form"] else []
            qtoks = [t for t in qtoks if t and t[:2] == hk[:2]]
            cands: list[tuple[str, str, str, int, str]] = []
            win_found = False
            for ed in eds:
                win = ed.window(c["locator"])
                if not win:
                    continue
                win_found = True
                for k in win:
                    for surf, idx in ed.tokens_in(k):
                        sk = lkey(surf)
                        if not sk:
                            continue
                        an = oracle.lemmas(surf) if oracle is not None else None
                        has_analysis = bool(an) and (an.get("collatinus") or an.get("whitaker"))
                        if has_analysis:
                            if hk in (an.get("collatinus") or []):
                                cands.append((ed.stem, k, surf, idx, "collatinus"))
                            elif hk in (an.get("whitaker") or []):
                                cands.append((ed.stem, k, surf, idx, "whitaker"))
                        elif qk and sk[:2] == hk[:2] and (sk == qk or sk in qtoks):
                            cands.append((ed.stem, k, surf, idx, "quoted"))
                if cands:
                    # a headword found in several units of the window: the cited unit decides when it holds it exactly once
                    if len({(s, i) for _, _, s, i, _ in cands}) > 1 and ed.center:
                        inner = [x for x in cands if x[1] == ed.center]
                        if len({(s, i) for _, _, s, i, _ in inner}) == 1:
                            cands = inner
                            stats["center_resolved"] += 1
                    break   # the first edition that yields a validated token is this citation's edition
            if not win_found:
                c.update(status="locator_not_in_edition")
                unlocated.append(c)
                stats["locator_not_in_edition"] += 1
                continue
            uniq = {(s, i) for _, _, s, i, _ in cands}
            if len(uniq) == 1:
                stem, k, surf, idx, how = cands[0]
                gold.append({**c, "edition_stem": stem, "unit": k, "token_index": idx, "surface": surf, "validation": how, "status": "located"})
                stats["located"] += 1
                stats[f"located_{how}"] += 1
            elif len(uniq) > 1:
                c.update(status="ambiguous", candidates="; ".join(sorted({s for _, _, s, _, _ in cands})))
                unlocated.append(c)
                stats["ambiguous"] += 1
            else:
                c.update(status="not_located")
                unlocated.append(c)
                stats["not_located"] += 1
        print(f"{work}: {len(rows)} citations, {stats['located']-n_loc_before} located ({time.time()-t0:.0f}s)", flush=True)

    cols = ["headword", "headword_key", "author", "work", "cited_edition", "locator", "edition_stem", "unit", "token_index", "surface",
            "validation", "quoted_form", "entry_key", "entry_id", "status"]
    with (OUT / "ls_gold_v0.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(gold)
    with (OUT / "unlocated.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[c for c in cols if c not in ("edition_stem", "unit", "token_index", "surface", "validation")] + ["candidates"], extrasaction="ignore")
        w.writeheader()
        w.writerows(unlocated)
    per_author = Counter(g["author"] for g in gold)
    summary = {"date": time.strftime("%Y-%m-%d"), "citations_into_held_works": len(cites), "located": len(gold),
               "located_per_author": dict(per_author.most_common()), "status_counts": {k: v for k, v in stats.items()},
               "oracle": oracle is not None, "elapsed_s": round(time.time() - t0, 1),
               "rule": "window = cited unit ±1 sibling (editions of a work tried in file order; chapter aliases; pr/praef; empty segments dropped); "
                       "validation collatinus or whitaker (headword among the oracle's lemma keys) else quoted-form equality sharing the headword's "
                       "first two letters when neither oracle analyses the surface; exactly one validated surface -> gold"}
    (OUT / "relocation_stats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
