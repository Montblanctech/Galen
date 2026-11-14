"""The five tools as plain functions over the public data. Every answer is short plain text.

No I/O here except through Store; no local paths in any answer; every answer about the drafts
carries the public page URL and the honesty line.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, OrderedDict, defaultdict
from importlib import resources
from urllib.parse import quote

from .store import PAGES_URL, DataUnavailable, Store, public_url
from .text import clip, fold, fold_beta, is_greek, parse_kuhn, stem_en, vol_label, words

HONESTY = "Machine first draft; no scholar has reviewed it."
TERM_INDEX = "galen-density-map/outputs/firstdrafts/_index/term_index.json"
GOLD = {
    "grc": {
        "name": "LSJ-Gold 1.0",
        "csv": "release/lsj-gold-1.0/lsj_gold.csv",
        "board": "release/lsj-gold-1.0/leaderboard.json",
        "page": PAGES_URL + "lsj-gold/",
        "licence": "data CC BY 4.0; underlying texts First1KGreek CC BY-SA 4.0, Perseus LSJ CC BY-SA 3.0",
        "dict": "LSJ",
    },
    "lat": {
        "name": "LS-Gold 1.0",
        "csv": "release/ls-gold-1.0/ls_gold.csv",
        "board": "release/ls-gold-1.0/leaderboard.json",
        "page": PAGES_URL + "ls-gold/",
        "licence": "CC BY-SA 4.0 (Lewis & Short via Perseus, Perseus Latin texts)",
        "dict": "Lewis & Short",
    },
}
DETAILS = ("concise", "full")
TEXT_CAP = 2500  # chars per text in a concise passage (the longest unit text is ~2,200)
MAX_LIMIT = 50


class ToolError(Exception):
    """An actionable error; the message is returned to the agent as the tool's error text."""


def _detail(detail: str) -> bool:
    d = (detail or "concise").strip().lower()
    if d not in DETAILS:
        raise ToolError(f'detail must be "concise" or "full", not "{detail}"')
    return d == "full"


def _n(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _more(shown_to: int, total: int, hint: str) -> str:
    left = total - shown_to
    return f"{left} more; {hint}" if left > 0 else ""


class Galen:
    def __init__(self, store: Store | None = None, works_cache: int = 3):
        self.store = store or Store()
        cat = json.loads(resources.files("galen_mcp").joinpath("catalog.json").read_text(encoding="utf-8"))
        self.catalog: dict[str, dict] = {w["slug"]: w for w in cat["works"]}
        self._works: OrderedDict[str, dict] = OrderedDict()
        self._works_cache = works_cache
        self._ti = None
        self._golds: dict[str, dict] = {}

    # ================================================================== data access ==========
    def work_path(self, slug: str) -> str:
        w = self.catalog[slug]
        return f"docs/{'first-drafts' if w['kind'] == 'galen' else 'method'}/{slug}/data.json"

    def work_url(self, slug: str, unit: dict | None = None) -> str:
        w = self.catalog[slug]
        base = f"{PAGES_URL}{'first-drafts' if w['kind'] == 'galen' else 'method'}/{slug}/"
        if unit is None:
            return base
        books = unit.get("books") or []
        page = f"book-{books[0]}.html" if w["book_pages"] and books else ""
        return f"{base}{page}#{unit['unit_id']}"

    def terms_url(self, q: str) -> str:
        return f"{PAGES_URL}first-drafts/terms/#q={quote(q)}"

    def resolve_work(self, work: str | None) -> str | None:
        if work is None or not str(work).strip():
            return None
        q = str(work).strip().lower()
        if q in self.catalog:
            return q
        hits = [s for s, w in self.catalog.items()
                if q in s or q in (w["title_lat"] or "").lower() or q in (w["title_eng"] or "").lower()]
        if len(hits) == 1:
            return hits[0]
        if hits:
            raise ToolError(f'work "{work}" is ambiguous: {", ".join(hits)}; pass one slug')
        raise ToolError(f'no work "{work}"; slugs: {", ".join(self.catalog)}')

    def work(self, slug: str) -> dict:
        if slug in self._works:
            self._works.move_to_end(slug)
            return self._works[slug]
        raw = self.store.json(self.work_path(slug))
        units = [{k: u.get(k) for k in ("unit_id", "pages", "books", "locus", "chapters", "difficulty_tier",
                                         "punch_density_per100", "greek")} for u in raw["units"]]
        rend = {k: {r["unit_id"]: r for r in raw.get("renderings", {}).get(k, [])} for k in ("A", "B")}
        keep = ("unit_id", "surface", "dilemma_lemma", "pos", "lsj_entry_id", "lsj_headword", "lsj_key",
                "lsj_sense_count", "lsj_first_sense_gloss", "greek_sentence", "rendering_A", "rendering_B",
                "norm_A", "norm_B", "english_sentence_A", "english_sentence_B", "agree", "judge_B")
        terms = [{k: t.get(k, "") for k in keep} for t in raw.get("term_table", [])]
        by_unit = defaultdict(list)
        for t in terms:
            by_unit[t["unit_id"]].append(t)
        d = {
            "slug": slug,
            "units": units,
            "index": {u["unit_id"]: i for i, u in enumerate(units)},
            "rend": rend,
            "checks": (raw.get("checks") or {}).get("units") or {},
            "terms": terms,
            "terms_by_unit": by_unit,
        }
        self._works[slug] = d
        while len(self._works) > self._works_cache:
            self._works.popitem(last=False)
        return d

    def term_index(self) -> dict:
        if self._ti is None:
            raw = self.store.json(TERM_INDEX)
            lem = raw["lemmas"]
            by_fold, by_key, by_beta = defaultdict(list), {}, defaultdict(list)
            for r in lem:
                by_key[r["key"]] = r
                for v in {r["lemma"], *(r.get("variants") or [])}:
                    if r not in by_fold[fold(v)]:
                        by_fold[fold(v)].append(r)
                if r.get("lsj_key"):
                    by_beta[fold_beta(r["lsj_key"])].append(r)
            self._ti = {"lemmas": lem, "fold": by_fold, "key": by_key, "beta": by_beta,
                        "built": raw.get("summary", {}).get("built", ""),
                        "rank": {k: i for i, k in enumerate(raw.get("most_inconsistent") or [])}}
        return self._ti

    # ================================================================== list_works ===========
    def list_works(self, detail: str = "concise") -> str:
        full = _detail(detail)
        g = [w for w in self.catalog.values() if w["kind"] == "galen"]
        m = [w for w in self.catalog.values() if w["kind"] != "galen"]
        out = [f"Galen First Drafts: {len(g)} Galen works never before translated into English (and "
               f"{len(m)} method test). Each unit has two independent English renderings (A, B) and "
               "automatic checks. Greek and drafts CC BY-SA 4.0. Index: " + PAGES_URL + "first-drafts/",
               "Machine first drafts; no scholar has reviewed them."]
        for w in g + m:
            v = w["unit_verdicts"]
            if w["kind"] == "galen":
                where = f"K. {w['kuhn_vol']} {w['page_first']}–{w['page_last']}"
            else:
                where = f"{w['author']}, Latin; method test, English translations exist"
            books = f", books {w['books'][0]}–{w['books'][-1]}" if len(w["books"]) > 1 else ""
            line = (f"- {w['slug']} · {where}{books} · {w['n_units']} units, {v.get('pass', 0)} pass · "
                    f"{w['title_lat']} ({w['title_eng']}) · {self.work_url(w['slug'])}")
            out.append(line)
            if full:
                pc = w["checks_pass_pct"]
                out.append(f"  checks pass %: a {pc.get('a')}, b {pc.get('b')}, c {pc.get('c')}; "
                           f"verdicts {', '.join(f'{k} {n}' for k, n in v.items())}; "
                           f"A/B term agreement {w['b_term_agree_pct']}%; target terms {w['n_terms']}; "
                           f"units {w['first_unit']} … {w['last_unit']}")
                if w.get("authorship"):
                    out.append(f"  authorship: {w['authorship']}")
                if w.get("prior_translations"):
                    out.append(f"  earlier translations: {w['prior_translations']}")
                if w.get("claim") and w["kind"] != "galen":
                    out.append(f"  note: {w['claim']}")
        out.append('Next: get_passage("K15.609") for a passage, search_terms("nerve") for a term.')
        if full:
            out.append("Checks: (a) the back-translation recovers the key terms; (b) A and B agree on the "
                       "key terms; (c) the renderings fall inside the LSJ entry's senses. A unit fails "
                       "when it fails two of three. They are automatic, not a review.")
        return "\n".join(out)

    # ================================================================== get_passage ==========
    def _vol_works(self, vol: str) -> list[dict]:
        return sorted((w for w in self.catalog.values() if w["kind"] == "galen" and w["vol"] == vol),
                      key=lambda w: w["page_first"])

    def _nearest_unit(self, slug: str, page: int) -> dict:
        units = self.work(slug)["units"]
        def dist(u):
            ps = [int(p) for p in u["pages"] if str(p).isdigit()] or [10**6]
            return (min(abs(p - page) for p in ps), ps[0] != page)
        return min(units, key=dist)

    def _kuhn_miss(self, raw: str, vol: str, page: int, slug: str | None) -> ToolError:
        works = [self.catalog[slug]] if slug else self._vol_works(vol)
        works = [w for w in works if w["kind"] == "galen" and w["vol"] == vol]
        if not works:
            vols = sorted({w["vol"] for w in self.catalog.values() if w["kind"] == "galen"},
                          key=lambda v: (int(re.match(r"\d+", v).group()), v))
            if slug:
                w = self.catalog[slug]
                where = (f"K. {w['kuhn_vol']} {w['page_first']}–{w['page_last']}" if w["kind"] == "galen"
                         else f"units {w['first_unit']} … {w['last_unit']}")
                return ToolError(f'{slug} is not in Kühn vol. {vol_label(vol)}; it covers {where}')
            return ToolError(f"no First Draft covers Kühn vol. {vol_label(vol)}; covered volumes: "
                             f"{', '.join(vol_label(v) for v in vols)}. list_works shows the page spans.")
        guess = None
        for cand in (page // 10, page // 100, page * 10):  # a slipped digit (6091 -> 609)
            for w in works:
                if w["page_first"] <= cand <= w["page_last"]:
                    guess = (w["slug"], cand)
                    break
            if guess:
                break
        if guess is None:
            w = min(works, key=lambda w: min(abs(page - w["page_first"]), abs(page - w["page_last"])))
            guess = (w["slug"], w["page_first"] if page < w["page_first"] else w["page_last"])
        u = self._nearest_unit(*guess)
        spans = "; ".join(f"{w['page_first']}–{w['page_last']} ({w['slug']})" for w in works)
        return ToolError(f"no unit at {raw}; nearest: {u['unit_id']} ({guess[0]}). "
                         f"Kühn vol. {vol_label(vol)} is covered at {spans}.")

    def _find_unit(self, citation: str, slug: str | None) -> tuple[str, dict, list[str]]:
        s = (citation or "").strip()
        if not s:
            raise ToolError('give a Kühn citation such as "K15.609" or "K. XV 609", or a unit id')
        # Vitruvius / other method works: unit id or "3.1.2"
        method = [w for w in self.catalog.values() if w["kind"] != "galen"]
        if (slug and self.catalog[slug]["kind"] != "galen") or re.match(r"(?i)vitr", s):
            slug = slug or method[0]["slug"]
            key = re.sub(r"(?i)^vitr(uvius)?\.?\s*", "", s).replace(" ", "")
            key = re.sub(r"[,:]", ".", key)
            d = self.work(slug)
            uid = f"Vitr.{key}"
            if uid in d["index"]:
                return slug, d["units"][d["index"][uid]], []
            first = key.split("-")[0]
            hits = [u for u in d["units"] if first in (u["pages"] or [])]
            if hits:
                return slug, hits[0], [u["unit_id"] for u in hits[1:]]
            near = [u["unit_id"] for u in d["units"] if u["unit_id"].startswith(f"Vitr.{first.rsplit('.', 1)[0]}.")]
            raise ToolError(f"no unit at {s} in {slug}; "
                            + (f"units in that chapter: {', '.join(near[:8])}" if near else
                               f"units run {d['units'][0]['unit_id']} … {d['units'][-1]['unit_id']}"))
        k = parse_kuhn(s)
        if not k:
            raise ToolError(f'could not read "{s}" as a Kühn citation; use "K15.609", "K. XV 609", '
                            '"K18a.196" or a unit id like "K15.609-610" (Vitruvius: "Vitr.3.1.5")')
        vol, p1, p2 = k
        label = f"K{vol}.{p1}" + (f"-{p2}" if p2 else "")
        works = [self.catalog[slug]] if slug else self._vol_works(vol)
        works = [w for w in works if w["kind"] == "galen" and w["vol"] == vol and w["page_first"] <= p1 <= w["page_last"]]
        if not works:
            raise self._kuhn_miss(label, vol, p1, slug)
        w = works[0]
        d = self.work(w["slug"])
        if label in d["index"]:
            u = d["units"][d["index"][label]]
            others = [x["unit_id"] for x in d["units"] if str(p1) in (x["pages"] or []) and x is not u]
            return w["slug"], u, others
        hits = [u for u in d["units"] if str(p1) in (u["pages"] or [])]
        if not hits:
            raise self._kuhn_miss(label, vol, p1, w["slug"])
        hits.sort(key=lambda u: (u["pages"][0] != str(p1), len(u["pages"])))  # prefer the unit starting there
        return w["slug"], hits[0], [u["unit_id"] for u in hits[1:]]

    def _checks_line(self, c: dict | None, unit: dict) -> str:
        if not c:
            return f"Checks: not run · difficulty {unit.get('difficulty_tier')}"
        def part(key, label):
            x = c.get(key) or {}
            v = x.get("verdict", "n/a")
            if key == "b" and x.get("n"):
                return f"({key}) {label} {x['agree']}/{x['n']} {v}"
            if key == "c" and x.get("n"):
                return f"({key}) {label} {x['in_range']}/{x['n']} {v}"
            return f"({key}) {label} {v}"
        return (f"Checks (automatic, not a review): unit {c.get('verdict')} · {part('a', 'term recall')} · "
                f"{part('b', 'A=B on key terms')} · {part('c', 'in LSJ sense range')} · "
                f"difficulty {unit.get('difficulty_tier')}")

    def get_passage(self, citation_or_unit: str, work: str | None = None, detail: str = "concise") -> str:
        full = _detail(detail)
        slug = self.resolve_work(work)
        slug, u, others = self._find_unit(citation_or_unit, slug)
        d = self.work(slug)
        w = self.catalog[slug]
        uid = u["unit_id"]
        i = d["index"][uid]
        ch = ", ch. " + ", ".join(u["chapters"]) if u.get("chapters") and w["kind"] == "galen" else ""
        book = f", book {'–'.join(u['books'])}" if u.get("books") and len(w["books"]) > 1 else ""
        out = [f"{uid} · {slug}{book} · {u['locus']}{ch} · {w['title_lat']}",
               f"Page: {self.work_url(slug, u)}",
               self._checks_line(d["checks"].get(uid), u)]
        lang = "Latin" if w["lang"] == "lat" else "Greek"
        texts = [(lang, u.get("greek") or "")]
        for k in ("A", "B"):
            r = d["rend"][k].get(uid) or {}
            lab = f"{k} ({r.get('model')})" if full and r.get("model") else k
            texts.append((lab, r.get("translation") or "(no rendering)"))
        for lab, t in texts:
            if not full:
                t, dropped = clip(t, TEXT_CAP)
                if dropped:
                    t += f" [{dropped} chars more; detail=\"full\"]"
            out.append(f"{lab}: {t}")
        if full:
            c = d["checks"].get(uid) or {}
            a = c.get("a") or {}
            for k in ("A", "B"):
                x = a.get(k) or {}
                if x:
                    out.append(f"(a) {k}: term recall {x.get('term_recall')} of {x.get('n_terms')}, content recall "
                               f"{x.get('content_recall')} of {x.get('n_content')}")
            rows = d["terms_by_unit"].get(uid, [])
            if rows:
                out.append(f"Key terms ({len(rows)}): surface → lemma; LSJ first sense; A | B")
                for t in rows[:40]:
                    eq = "=" if t["agree"] == "y" else "≠"
                    j = f"; judge {t['judge_B']}" if t.get("judge_B") else ""
                    gl = f'; "{t["lsj_first_sense_gloss"]}"' if t.get("lsj_first_sense_gloss") else ""
                    out.append(f"- {t['surface'].strip(',.;·')} → {t['lsj_headword'] or t['dilemma_lemma']} "
                               f"({t['pos']}){gl}; {t['rendering_A']} {eq} "
                               f"{t['rendering_B']}{j}")
                if len(rows) > 40:
                    out.append(f"{len(rows) - 40} more key terms on the page.")
        nav = []
        if others:
            nav.append(f"Also on that page: {', '.join(others[:4])}")
        if i > 0:
            nav.append(f"Prev: {d['units'][i - 1]['unit_id']}")
        if i + 1 < len(d["units"]):
            nav.append(f"Next: {d['units'][i + 1]['unit_id']}")
        if nav:
            out.append(" · ".join(nav))
        if not full:
            out.append('detail="full" adds the key-term table and check figures.')
        out.append(HONESTY)
        return "\n".join(out)

    # ================================================================== terms ================
    @staticmethod
    def _renderings(rec: dict) -> set[str]:
        s = set()
        for w in rec.get("works") or []:
            for k in ("A", "B"):
                for item in w.get(k) or []:
                    s.update(x.lower() for x in item[:2] if x)
        if rec.get("global_core"):
            s.add(rec["global_core"].lower())
        return s

    def _score(self, rec: dict, q: str, qf: str, greek: bool, qwords: list[str]) -> tuple[int, str]:
        if greek:
            forms = {fold(rec["lemma"]), *(fold(v) for v in rec.get("variants") or [])}
            if qf in forms:
                return 100, "Greek"
            if any(f.startswith(qf) for f in forms):
                return 70, "Greek prefix"
            if any(qf in f for f in forms):
                return 50, "Greek part"
            return 0, ""
        best = (0, "")
        if qf and fold_beta(rec.get("lsj_key") or "") == fold_beta(q) and re.search(r"[/\\=()|]", q):
            return 95, "LSJ key"
        rend = self._renderings(rec)
        qs = " ".join(stem_en(w) for w in qwords)
        rstem = {" ".join(stem_en(w) for w in words(r)): r for r in rend}
        if q.lower() in rend or qs in rstem:
            best = max(best, (85, "English rendering"))
        elif qwords and any(all(stem_en(w) in rs.split() for w in qwords) for rs in rstem):
            best = max(best, (60, "English rendering (part)"))
        gloss = (rec.get("lsj_first_sense") or "").lower()
        gw = {stem_en(w) for w in words(gloss)}
        if gloss and (gloss == q.lower() or gloss.strip(" ,.;") == q.lower()):
            best = max(best, (80, "LSJ gloss"))
        elif qwords and all(stem_en(w) in gw for w in qwords):
            best = max(best, (55, "LSJ gloss"))
        if not best[0] and qf and len(qf) >= 4 and fold_beta(rec.get("lsj_key") or "").startswith(fold_beta(q)):
            best = (40, "LSJ key prefix")
        return best

    @staticmethod
    def _usual(rec: dict, k: int = 3) -> str:
        """Usual rendering per work, grouped by the index's core key, shown in a plain form."""
        c, shown = Counter(), {}
        for w in rec.get("works") or []:
            if w.get("modal"):
                key = w.get("modal_core") or w["modal"]
                c[key] += 1
                # the index keys are normalised ("biliou"); show the commonest surface form instead
                items = [x for x in (w.get("A") or []) + (w.get("B") or []) if x[1] == w["modal"]]
                plain = max(items, key=lambda x: x[2])[0].lower() if items else w["modal"]
                shown.setdefault(key, plain)
        parts = [f"{shown[r]} ({n} work{'s' if n > 1 else ''})" if len(c) > 1 else shown[r]
                 for r, n in c.most_common(k)]
        more = f" +{len(c) - k}" if len(c) > k else ""
        return ", ".join(parts) + more

    def _search(self, query: str) -> list[tuple[int, str, dict]]:
        ti = self.term_index()
        q = (query or "").strip()
        qf, greek = fold(q), is_greek(q)
        qwords = [w for w in words(q) if w not in ("the", "a", "an", "of", "to")] or words(q)
        hits = []
        for rec in ti["lemmas"]:
            sc, why = self._score(rec, q, qf, greek, qwords)
            if sc:
                hits.append((sc, why, rec))
        hits.sort(key=lambda h: (-h[0], -_n(h[2].get("n")), h[2]["lemma"]))
        return hits

    def search_terms(self, query: str, limit: int = 10, offset: int = 0) -> str:
        q = (query or "").strip()
        if not q:
            raise ToolError('give a query: Greek ("νεῦρον", accents optional: "νευρον"), an LSJ key '
                            '("neu=ron"), or English ("nerve", "acrid")')
        limit = max(1, min(int(limit or 10), MAX_LIMIT))
        offset = max(0, int(offset or 0))
        hits = self._search(q)
        if not hits:
            return (f'no target term matches "{q}". Target terms are the rarer nouns and adjectives of the '
                    "13 Galen works; try another English word, the Greek without accents, or a shorter "
                    f"prefix. Terms page: {self.terms_url(q)}")
        page = hits[offset:offset + limit]
        if not page:
            raise ToolError(f"offset {offset} is past the end ({len(hits)} matches)")
        out = [f'{len(hits)} term{"s" if len(hits) > 1 else ""} match "{q}" '
               f"(showing {offset + 1}–{offset + len(page)}; Galen works only):"]
        for sc, why, r in page:
            flag = " · renderings differ across works" if r.get("diverges") else ""
            gl = f' · LSJ "{r["lsj_first_sense"]}"' if r.get("lsj_first_sense") else ""
            out.append(f"- {r['lemma']} · {r.get('pos', '')}{gl} · {r['n']}× in {r['n_works']} "
                       f"work{'s' if r['n_works'] > 1 else ''} · usual: {self._usual(r)}{flag} · matched {why}")
        more = _more(offset + len(page), len(hits), f"pass offset={offset + len(page)} or narrow the query.")
        if more:
            out.append(more)
        out.append(f'Open one with get_term("{page[0][2]["lemma"]}"). Terms page: {self.terms_url(q)}')
        out.append(HONESTY)
        return "\n".join(out)

    def _records_from_table(self, slug: str) -> list[dict]:
        """Term-index-shaped records for a work outside the index (the Latin method test)."""
        d = self.work(slug)
        groups: OrderedDict[str, list[dict]] = OrderedDict()
        for t in d["terms"]:
            key = t["lsj_entry_id"] or "lemma:" + fold(t["dilemma_lemma"])
            groups.setdefault(key, []).append(t)
        recs = []
        for key, rows in groups.items():
            a = Counter((t["rendering_A"], t["norm_A"]) for t in rows if t["rendering_A"])
            b = Counter((t["rendering_B"], t["norm_B"]) for t in rows if t["rendering_B"])
            modal = Counter([n for (_, n) in a.elements()] + [n for (_, n) in b.elements()]).most_common(1)
            t0 = rows[0]
            recs.append({
                "key": key, "lemma": t0["dilemma_lemma"] or t0["lsj_headword"],
                "variants": sorted({t["dilemma_lemma"] for t in rows}), "pos": t0["pos"],
                "lsj_entry_id": t0["lsj_entry_id"], "lsj_key": t0["lsj_key"],
                "lsj_first_sense": t0["lsj_first_sense_gloss"], "lsj_senses": t0["lsj_sense_count"],
                "n": len(rows), "n_works": 1,
                "works": [{"work": slug, "n": len(rows),
                           "A": [[s, n, c] for (s, n), c in a.most_common()],
                           "B": [[s, n, c] for (s, n), c in b.most_common()],
                           "modal": modal[0][0] if modal else "", "modal_core": modal[0][0] if modal else "",
                           "agree_ab": sum(t["agree"] == "y" for t in rows), "both_ab": len(rows),
                           "loci": [{"unit": t["unit_id"], "A": t["rendering_A"], "B": t["rendering_B"],
                                     "agree": t["agree"]} for t in rows]}],
            })
        return recs

    def _resolve_lemma(self, lemma: str, slug: str | None) -> tuple[list[dict], bool]:
        """Records for a lemma; second value says whether they come from the index (else a work table)."""
        q = (lemma or "").strip()
        if slug and self.catalog[slug]["kind"] != "galen":
            recs = self._records_from_table(slug)
            qf = fold(q)
            hits = [r for r in recs if qf in {fold(r["lemma"]), *(fold(v) for v in r["variants"])}
                    or r["key"] == q]
            return hits, False
        ti = self.term_index()
        if q in ti["key"]:
            return [ti["key"][q]], True
        hits = list(ti["fold"].get(fold(q), []))
        if not hits and not is_greek(q) and re.search(r"[/\\=()|]", q):
            hits = list(ti["beta"].get(fold_beta(q), []))
        return hits, True

    def get_term(self, lemma: str, work: str | None = None, detail: str = "concise", offset: int = 0) -> str:
        full = _detail(detail)
        slug = self.resolve_work(work)
        offset = max(0, int(offset or 0))
        q = (lemma or "").strip()
        if not q:
            raise ToolError('give a lemma, e.g. get_term("νεῦρον") or get_term("νευρον"); '
                            'for English use search_terms("nerve")')
        recs, indexed = self._resolve_lemma(q, slug)
        if not recs:
            if not indexed:
                top = Counter(r["lemma"] for r in self._records_from_table(slug) for _ in range(r["n"]))
                raise ToolError(f'"{q}" is not a target term of {slug}; its commonest target terms: '
                                + ", ".join(l for l, _ in top.most_common(10)))
            sug = [h[2]["lemma"] for h in self._search(q)[:5]]
            hint = f"closest: {', '.join(sug)}" if sug else "no close match"
            raise ToolError(f'"{q}" is not a lemma in the term index ({hint}). get_term takes a Greek lemma '
                            '(accents optional) or an LSJ id; search_terms takes English too.')
        recs.sort(key=lambda r: -_n(r.get("n")))
        rec = recs[0]
        works = rec.get("works") or []
        if slug:
            works = [w for w in works if w["work"] == slug]
            if not works:
                where = ", ".join(f"{w['work']} ({w['n']}×)" for w in rec.get("works") or [])
                raise ToolError(f"{rec['lemma']} is not a target term in {slug}; it occurs in: {where}")
        gl = f' "{rec["lsj_first_sense"]}"' if rec.get("lsj_first_sense") else ""
        lsj = f"LSJ{gl} ({rec.get('lsj_senses') or '?'} senses; {rec['lsj_entry_id']})" if rec.get("lsj_entry_id") \
            else "no LSJ entry matched"
        if self.catalog.get(slug or "", {}).get("lang") == "lat":
            lsj = lsj.replace("LSJ", "Lewis & Short", 1)
        tot = sum(w["n"] for w in works)
        out = [f"{rec['lemma']} · {rec.get('pos', '')} · {lsj} · {tot}× in {len(works)} work"
               f"{'s' if len(works) > 1 else ''}" + (f" (of {rec['n']}× in {rec['n_works']})" if slug else "")]
        if len(recs) > 1:
            out.append("Also: " + ", ".join(f"{r['lemma']} ({r['key']}, {r['n']}×)" for r in recs[1:4]))
        if rec.get("diverges") and not slug:
            out.append("The usual rendering differs across works (each model kept a term memory of one work only).")

        def forms(items, k=3):
            s = "; ".join(f"{x[0]} {x[2]}" for x in (items or [])[:k])
            return s + (f"; +{len(items) - k}" if len(items or []) > k else "")

        if not full:
            for w in works:
                loci = [l["unit"] for l in w.get("loci") or []]
                ls = ", ".join(loci[:3]) + (f" +{len(loci) - 3}" if len(loci) > 3 else "")
                out.append(f"- {w['work']} {w['n']}×: A {forms(w.get('A'))} | B {forms(w.get('B'))} | "
                           f"A=B {w.get('agree_ab', 0)}/{w.get('both_ab', 0)} | {ls}")
            if slug:
                out.append('detail="full" lists every occurrence with the Greek and both English sentences.')
            else:
                out.append('detail="full" lists every locus with its page link; add work="<slug>" for the '
                           "Greek and English sentences.")
        elif not slug:
            rows = [(w, l) for w in works for l in w.get("loci") or []]
            cap = 40
            page = rows[offset:offset + cap]
            if offset and not page:
                raise ToolError(f"offset {offset} is past the end ({len(rows)} loci)")
            for w, l in page:
                eq = "=" if l.get("agree") == "y" else "≠"
                unit = {"unit_id": l["unit"], "books": self._books_of(w["work"], l)}
                out.append(f"- {w['work']} {l['unit']}: A {l['A']} {eq} B {l['B']} · {self.work_url(w['work'], unit)}")
            more = _more(offset + len(page), len(rows), f"pass offset={offset + len(page)}, or add work=\"<slug>\".")
            if more:
                out.append(more)
        else:
            d = self.work(slug)
            rows = [t for t in d["terms"] if self._row_is(t, rec)]
            cap = 8
            page = rows[offset:offset + cap]
            if offset and not page:
                raise ToolError(f"offset {offset} is past the end ({len(rows)} occurrences)")
            for t in page:
                u = d["units"][d["index"][t["unit_id"]]] if t["unit_id"] in d["index"] else {"unit_id": t["unit_id"]}
                eq = "=" if t["agree"] == "y" else "≠"
                out.append(f"- {t['unit_id']} {t['surface'].strip(',.;·')}: A {t['rendering_A']} {eq} B "
                           f"{t['rendering_B']} · {self.work_url(slug, u)}")
                out.append(f"  {clip(t['greek_sentence'], 300)[0]}")
                out.append(f"  A: {clip(t['english_sentence_A'], 300)[0]}")
                out.append(f"  B: {clip(t['english_sentence_B'], 300)[0]}")
            more = _more(offset + len(page), len(rows), f"pass offset={offset + len(page)}.")
            if more:
                out.append(more)
        if indexed:
            out.append(f"Terms page: {self.terms_url(rec['lemma'])}")
        else:
            out.append(f"Page: {self.work_url(slug)}")
        out.append(HONESTY)
        return "\n".join(out)

    @staticmethod
    def _row_is(t: dict, rec: dict) -> bool:
        if rec.get("lsj_entry_id"):
            return t["lsj_entry_id"] == rec["lsj_entry_id"]
        return fold(t["dilemma_lemma"]) in {fold(rec["lemma"]), *(fold(v) for v in rec.get("variants") or [])}

    def _books_of(self, slug: str, locus: dict) -> list[str]:
        f = locus.get("file") or ""
        m = re.match(r"book-(\d+)\.html", f)
        return [m.group(1)] if m else []

    # ================================================================== gold lemma ===========
    def _gold(self, lang: str) -> dict:
        if lang in self._golds:
            return self._golds[lang]
        g = GOLD[lang]

        def build(path):
            forms: dict[str, dict] = defaultdict(dict)
            heads: dict[str, list] = {}
            with open(path, encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    surf = row["surface"].strip()
                    hw = row["headword"]
                    cell = forms[fold(surf)].setdefault(f"{surf}\t{hw}", [0, ""])
                    cell[0] += 1
                    if not cell[1]:
                        cell[1] = f"{row['author']}.{row['work']} {row['locator']}"
                    h = heads.setdefault(fold(hw), [hw, 0])
                    h[1] += 1
            return {"forms": forms, "heads": heads}

        data = self.store.derived(f"{lang}_gold_forms", g["csv"], build)
        try:
            names = self.store.json(g["board"]).get("author_names") or {}
        except (DataUnavailable, ValueError):
            names = {}
        self._golds[lang] = {"forms": data["forms"], "heads": data["heads"], "names": names}
        return self._golds[lang]

    def lsj_gold_lemma(self, form: str, limit: int = 10) -> str:
        f = (form or "").strip().strip(",.;·:")
        if not f:
            raise ToolError('give a word form, e.g. lsj_gold_lemma("ἀᾶται") or a Latin form ("abdicavit")')
        lang = "grc" if is_greek(f) else "lat"
        limit = max(1, min(int(limit or 10), MAX_LIMIT))
        g, meta = self._gold(lang), GOLD[lang]
        cells = g["forms"].get(fold(f), {})

        def loc(ex: str) -> str:
            aw, _, where = ex.partition(" ")
            a, _, w = aw.partition(".")
            return f"{g['names'].get(a, a)} ({a}.{w}) {where}"

        rows = sorted(((k.split("\t"), v) for k, v in cells.items()), key=lambda x: -x[1][0])
        exact = [r for r in rows if r[0][0] == f]
        blind = [r for r in rows if r[0][0] != f]
        out = []
        if exact:
            tot = sum(v[0] for _, v in exact)
            out.append(f"{f} → " + "; ".join(f"{hw} ({v[0]} of {tot} loci, e.g. {loc(v[1])})"
                                             for (s, hw), v in exact[:limit]))
        if blind:
            shown = blind[: max(0, limit - len(exact[:limit]))] or blind[:3]
            out.append(("Accent/case-blind matches: " if exact else f"No exact form {f}; accent/case-blind: ")
                       + "; ".join(f"{s} → {hw} ({v[0]}×, e.g. {loc(v[1])})" for (s, hw), v in shown)
                       + (f"; {len(blind) - len(shown)} more" if len(blind) > len(shown) else ""))
        head = g["heads"].get(fold(f))
        if head:
            out.append(f"{head[0]} is itself a headword in {meta['dict']} with {head[1]} gold loci.")
        if not out:
            raise ToolError(f"{f} is not among the {meta['name']} forms (gold covers only words {meta['dict']} "
                            "cites at a passage it could locate). Try the form without punctuation, or a "
                            "lemmatizer for other words.")
        out.append(f"Gold = the headword {meta['dict']} itself cites at that passage, located in a free edition and "
                   "machine-validated; it says nothing about other contexts.")
        out.append(f"{meta['name']} ({meta['licence']}): {meta['page']}")
        return "\n".join(out)
