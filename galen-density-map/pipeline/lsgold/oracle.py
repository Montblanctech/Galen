"""LS-Gold -- the lexicon oracle: every lemma two offline Latin morphological analysers allow for a surface form.

Oracle(cache_path).lemmas(surface) -> {"collatinus": [keys], "whitaker": [keys]}; each list is the sorted, deduplicated
set of latnorm.key(lemma) over every analysis the route returns (context-free: all readings, no disambiguation).

Routes
------
collatinus  pycollatinus 0.1.6, `Lemmatiseur().lemmatise(form)` (a generator of dicts); the headword is the dict's
            'lemma' field (macrons/breves/homograph digits stripped by key()). Enclitic forms: Collatinus returns the
            host word's lemma for -que/-ne/-ve forms ('virumque' -> 'uir'); kept as given. `lemmatise_multiple` is only
            a Python loop over `lemmatise` (pycollatinus/lemmatiseur.py), so bulk() calls `lemmatise` per distinct
            surface -- same speed, no risk of the multi-word splitter disagreeing with our token boundaries.
            pycollatinus 0.1.6 imports `collections.Callable` (removed in Python 3.10); this module restores the alias
            from collections.abc before the import (no edit to site-packages).
whitaker    whitakers_words 0.7.0 (blagae's port), `Parser(frequency="X").parse(form)` -> Word; for each
            `word.forms[*].analyses.values()` (Analysis) the lexeme is `analysis.lexeme`. `lexeme.roots` are STEMS
            ('arm', 'uir'), not headwords, so the headword is rebuilt the way the package's own Whitaker-format output
            does it: `whitakers_words.formatter.WordsFormatter().format_parts(analysis)` prints the dictionary line
            ('armum, armi  N (2nd) N', 'cano, canere, cecini, cantus  V (3rd)', 'saeuus, saeua -um, ...  ADJ',
            'et  CONJ'); the headword is the text before its first comma / double space. format_parts returns '' for
            pronouns, adverbs, numerals, deponent-less special cases and Unique (irregular) forms, so:
              PRON / NUM / irregular V  the citation cell (NOM S M/C [CARD], else NOM P; verbs PRES ACT/PASS IND
                          1 S) looked up in whitakers_words.generated.paradigms for the lexeme's class pooled with its
                          general class (most frequent ending first), then sibling subclasses; the ending is added to
                          roots[entry['stem']] ('qu'+'i' -> 'qui', 'ips'+'e' -> 'ipse', 'n'+'os' -> 'nos', 'tr'+'es' ->
                          'tres', 'ed'+'o' -> 'edo', 'inqu'+'am' -> 'inquam'); is/idem -> 'is', reflexive -> 'sui'
              V deponent  roots[0] + find_infl(V, category, PRES PASSIVE IND 1 S) ('f'+'or' -> 'for', not 'fo')
              ADV / other roots[0] (Whitaker stores adverbs' positive form whole)
              Unique      Whitaker's UNIQUES list has no headword; forms of esse (V 5 1) map to 'sum' when the form is
                          a plain form of sum, otherwise the unique orth itself is kept.
            A stem printed as '-' (form not attested) gives no headword for that analysis.
            frequency="X" admits every stem and inflection (the package default "C" hides D-F-frequency stems, so
            'litora' and 'genus, generis' were missing); this is an oracle of possibilities, so breadth is right.
            Whitaker splits enclitics itself ('virumque' -> uir + que); the host word's headword is used.

Cache: JSONL at cache_path, one line per lower-cased surface {"surface", "collatinus", "whitaker"}; loaded on
construction, appended as new surfaces are seen. A route that raises returns [] for that surface and the failure is
counted in self.failures[route]; one failing library never stops a run.

CLI: python -X utf8 -I pipeline/lsgold/oracle.py <tokens.jsonl> [--cache data/latin_corpus/oracle_cache.jsonl]
"""
from __future__ import annotations

import argparse
import collections
import collections.abc
import json
import sys
import time
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from latnorm import key  # noqa: E402

if not hasattr(collections, "Callable"):
    collections.Callable = collections.abc.Callable  # pycollatinus 0.1.6 on Python >= 3.10

ROUTES = ("collatinus", "whitaker")
SUM_FORMS = set("""sum es est sumus estis sunt eram eras erat eramus eratis erant ero eris erit erimus eritis erunt
sim sis sit simus sitis sint essem esses esset essemus essetis essent forem fores foret foremus foretis forent esse
fore este esto estote sunto fui fuisti fuit fuimus fuistis fuerunt fuere fueram fueras fuerat fueramus fueratis
fuerant fuero fueris fuerit fuerimus fueritis fuerint fuerim fuissem fuisses fuisset fuissemus fuissetis fuissent
fuisse futurus futura futurum siem sies siet escit""".split())


_M = ["NOM S M", "NOM S C", "NOM S X"]
_MP = ["NOM P M", "NOM P C", "NOM P X"]
_FN = ["NOM S N", "NOM S F", "NOM P N", "NOM P F"]
_CARD = lambda fs: [f + " CARD" for f in fs]  # noqa: E731
_V1 = ["PRES ACTIVE IND 1 S", "PRES PASSIVE IND 1 S"]
_VX = ["PERF ACTIVE IND 1 S", "PRES ACTIVE IND 3 S", "PRES PASSIVE IND 3 S"]
# (forms, which class group) tiers per part of speech: 'own' = the lexeme's class ab pooled with its general class a0,
# 'sib' = sibling subclasses a1..a9. Masculine/common citation cells are preferred over a feminine/neuter one so that
# the relative 'qu-' lexemes cite as 'qui', not 'quae'/'quod'; numerals cite in the plural in their own class (tres).
_TIERS = {
    "PRON": [(_M + _MP, "own"), (_M, "sib"), (_FN, "own")],
    "NUM": [(_CARD(_M + _MP) + ["X X X CARD"], "own"), (_CARD(_M), "sib")],
    "V": [(_V1, "own"), (_V1, "sib"), (_VX, "own")],
}
# Pronoun classes whose stems cannot rebuild the L&S head: is/ea/id and idem (stem 'i'), the reflexive (no nominative).
_PRON_FIXED = {(4, 1): "is", (4, 2): "is", (5, 4): "sui"}


def _cite(typ: str, cat, roots: list[str]):
    """Citation form for a PRON/NUM/V lexeme whose dictionary line the package cannot print: the citation cell looked up
    in whitakers_words.generated.paradigms, ending appended to roots[entry['stem']] (0-based stem index)."""
    try:
        from whitakers_words.generated.paradigms import paradigms
        par = paradigms[typ]
        a, b = int(cat[0]), int(cat[1])
    except Exception:  # noqa: BLE001
        return None
    if typ == "PRON" and (a, b) in _PRON_FIXED:
        return _PRON_FIXED[(a, b)]
    groups = {"own": [str(10 * a + b), str(10 * a)], "sib": [str(10 * a + k) for k in range(1, 10) if k != b]}
    for forms, grp in _TIERS.get(typ, []):
        for f in forms:
            cands = [c for spec in groups[grp] for c in par.get(spec, {}).get(f, [])]
            cands = [c for c in sorted(cands, key=lambda c: c["props"][1])
                     if c.get("stem", 0) < len(roots) and roots[c.get("stem", 0)] not in ("", "-")]
            if cands:
                c = cands[0]
                return roots[c.get("stem", 0)] + c["ending"]
    return None


class Oracle:
    def __init__(self, cache_path: Path):
        self.cache_path = Path(cache_path)
        self.cache: dict[str, dict[str, list[str]]] = {}
        self.failures = {r: 0 for r in ROUTES}
        self._lem = None
        self._parser = None
        self._fmt = None
        self._load_errors: dict[str, str] = {}
        if self.cache_path.exists():
            with self.cache_path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.cache[rec["surface"]] = {r: rec.get(r, []) for r in ROUTES}

    # ---- library loading (lazy, each route independently) ----
    def _collatinus(self):
        if self._lem is None and "collatinus" not in self._load_errors:
            try:
                from pycollatinus import Lemmatiseur
                self._lem = Lemmatiseur()
            except Exception as e:  # noqa: BLE001
                self._load_errors["collatinus"] = repr(e)
        return self._lem

    def _whitaker(self):
        if self._parser is None and "whitaker" not in self._load_errors:
            try:
                from whitakers_words.parser import Parser
                from whitakers_words.formatter import WordsFormatter
                self._parser = Parser(frequency="X")
                self._fmt = WordsFormatter()
            except Exception as e:  # noqa: BLE001
                self._load_errors["whitaker"] = repr(e)
        return self._parser

    # ---- routes ----
    def _route_collatinus(self, s: str) -> list[str]:
        lem = self._collatinus()
        if lem is None:
            self.failures["collatinus"] += 1
            return []
        try:
            out = {key(d.get("lemma", "")) for d in lem.lemmatise(s)}
        except Exception:  # noqa: BLE001
            self.failures["collatinus"] += 1
            return []
        out.discard("")
        return sorted(out)

    def _whitaker_headword(self, analysis) -> str:
        from whitakers_words.enums import WordType
        from whitakers_words.finder import find_infl
        from whitakers_words.parser import UniqueLexeme
        lex = analysis.lexeme
        wt = lex.wordType
        if isinstance(lex, UniqueLexeme):
            orth = analysis.inflections[0].stem if analysis.inflections else ""
            cat = getattr(analysis.inflections[0], "category", None) if analysis.inflections else None
            if wt == WordType.V and cat and int(cat[0]) == 5 and orth.lower() in SUM_FORMS:
                return "sum"
            return orth
        roots = list(lex.roots or [])
        if wt == WordType.V and "DEP" in (lex.form or []) and roots and roots[0] != "-":
            try:
                return roots[0] + find_infl(WordType.V, lex.category, ["PRES", "PASSIVE", "IND", "1", "S"])
            except Exception:  # noqa: BLE001
                pass
        try:
            line = self._fmt.format_parts(analysis)
        except Exception:  # noqa: BLE001
            line = ""
        head = line.split(",")[0].split("  ")[0].strip() if line else ""
        if head and not head.startswith("-"):
            return head
        if wt.name in _TIERS:
            head = _cite(wt.name, lex.category, roots)
            if head:
                return head
        if not roots or roots[0] == "-":
            return ""
        return roots[0]

    def _route_whitaker(self, s: str) -> list[str]:
        p = self._whitaker()
        if p is None:
            self.failures["whitaker"] += 1
            return []
        try:
            word = p.parse(s)
            out = set()
            for form in word.forms:
                for a in form.analyses.values():
                    out.add(key(self._whitaker_headword(a)))
        except Exception:  # noqa: BLE001
            self.failures["whitaker"] += 1
            return []
        out.discard("")
        return sorted(out)

    # ---- public ----
    def _compute(self, s: str) -> dict[str, list[str]]:
        return {"collatinus": self._route_collatinus(s), "whitaker": self._route_whitaker(s)}

    def _append(self, recs: list[dict]) -> None:
        if not recs:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def lemmas(self, surface: str) -> dict[str, list[str]]:
        s = (surface or "").strip().lower()
        if s in self.cache:
            return self.cache[s]
        res = self._compute(s)
        self.cache[s] = res
        self._append([{"surface": s, **res}])
        return res

    def first(self, surface: str) -> dict[str, str]:
        """The FIRST lemma each route yields for the surface, as the library prints it (not cached; used by the
        context-free collatinus_first / whitaker_first baselines in latin_caches.py). '' when the route has none."""
        s = (surface or "").strip().lower()
        res = {"collatinus": "", "whitaker": ""}
        lem = self._collatinus()
        if lem is not None:
            try:
                for d in lem.lemmatise(s):
                    if d.get("lemma"):
                        res["collatinus"] = d["lemma"]
                        break
            except Exception:  # noqa: BLE001
                self.failures["collatinus"] += 1
        p = self._whitaker()
        if p is not None:
            try:
                for form in p.parse(s).forms:
                    for a in form.analyses.values():
                        h = self._whitaker_headword(a)
                        if key(h):
                            res["whitaker"] = h
                            break
                    if res["whitaker"]:
                        break
            except Exception:  # noqa: BLE001
                self.failures["whitaker"] += 1
        return res

    def bulk(self, surfaces: Iterable[str], flush_every: int = 2000, progress: bool = False) -> int:
        todo = sorted({(x or "").strip().lower() for x in surfaces} - set(self.cache) - {""})
        buf: list[dict] = []
        t0 = time.time()
        for n, s in enumerate(todo, 1):
            res = self._compute(s)
            self.cache[s] = res
            buf.append({"surface": s, **res})
            if len(buf) >= flush_every:
                self._append(buf)
                buf = []
                if progress:
                    print(f"  {n}/{len(todo)}  {n / (time.time() - t0):.0f}/s", flush=True)
        self._append(buf)
        return len(todo)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tokens", type=Path)
    here = Path(__file__).resolve().parents[2]
    ap.add_argument("--cache", type=Path, default=here / "data" / "latin_corpus" / "oracle_cache.jsonl")
    a = ap.parse_args()
    surfaces = set()
    with a.tokens.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                surfaces.add(json.loads(line)["surface"].lower())
    o = Oracle(a.cache)
    t = time.time()
    n = o.bulk(surfaces, progress=True)
    dt = time.time() - t
    print(f"distinct surfaces {len(surfaces)}; newly analysed {n} in {dt:.1f}s ({n / dt if dt else 0:.0f}/s)")
    for r in ROUTES:
        cov = sum(1 for s in surfaces if o.cache[s][r]) / max(1, len(surfaces))
        print(f"  {r:10s} coverage {cov:.1%}  failures {o.failures[r]}")
    both = sum(1 for s in surfaces if o.cache[s]["collatinus"] and o.cache[s]["whitaker"]) / max(1, len(surfaces))
    anyr = sum(1 for s in surfaces if o.cache[s]["collatinus"] or o.cache[s]["whitaker"]) / max(1, len(surfaces))
    print(f"  both {both:.1%}  either {anyr:.1%}")
    if o._load_errors:
        print("load errors:", o._load_errors)


if __name__ == "__main__":
    main()
