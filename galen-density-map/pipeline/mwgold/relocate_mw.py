"""MW-Gold, stage 2 — relocate Monier-Williams' citations into token positions of the DCS stream.

Inputs: data/sanskrit_feasibility/mw_citations.jsonl (mw_parse.py), data/sanskrit_corpus/units/<stem>.json with
`refs` (align_verses.py) and tokens/<stem>.jsonl (tokenize_dcs.py). The in-scope texts and how an MW locus becomes
a reference are in SCOPE below (mirrors data/sanskrit_feasibility/mw_abbrev_map.json).

Rule (the Latin twin's, with the Sanskrit token unit):
  window   verse-level texts: the sentences whose ref equals the cited verse, plus the sentences of verse-1 and
           verse+1 in the same chapter (cited unit ± 1 sibling); chapter-level texts (TS, MS, KS, AB, PB, KauśS,
           GautDhS: the DCS chapter is MW's unit and the dump has nothing finer): every sentence of the chapter, and
           the locus is flagged window_kind = chapter.
  validate dcs      the token's DCS lemma key equals the headword key;
           dcs_cpd  a span of 2-6 consecutive DCS tokens inside one compound (all but the last Case=Cpd) whose
                    lemma keys joined with vowel sandhi, or whose unsandhied member forms + final lemma joined, equal
                    the headword key; the locus points at the first token and records the span;
           vidyut   the DCS lemma differs, but vidyut-kosha's analyses of the unsandhied form contain the headword key
                    and the DCS lemma shares the headword's first three letters (a citation-form convention, not a
                    different word); reported as its own route;
           surface  the unsandhied token itself equals the headword (MW's adverb and indeclinable entries such as
                    kālam, channam, where DCS lemmatizes to the stem) and the DCS lemma shares three letters; the
                    Sanskrit counterpart of the twins' quoted-form route, reported as its own route.
           dcs_tmesis  Vedic tmesis: MW enters the compound verb (anu-kruś, pary-añc, apa-dhā) and the text separates
                    the preverb from the verb; DCS lemmatizes the verb token to the bare root (kruś, añc, dhā) and the
                    preverb as its own token. A VERB token whose lemma key is the headword minus a leading preverb (or
                    two), with that preverb (those preverbs) standing as separate tokens within four tokens of the verb,
                    is a locus of route dcs_tmesis; the locus is the verb token. Reported as its own route. The scorer
                    counts a system that prints the bare root as WRONG on these loci (the headword is MW's compound verb,
                    exactly as the twins count convention differences against a system); the route column shows the
                    size of that effect, and every DCS-trained system is expected to fail the route.
  Compound runs start at a Case=Cpd token or at the negative particle a/an (DCS splits a-viśeṣatas as a + viśeṣatas,
  tagged PART, not Cpd). The final member of a span may also match MW's own member list with the inflection left on
  the token (MW members [kośa, hīna] against tokens kośa + hīnaḥ), because DCS lemmatizes participles and
  derivatives to the root (hīna -> hā) while MW enters the derivative.
  decide   exactly one distinct candidate -> gold; several -> if the cited verse's own sentences hold exactly one, that
           one (center_resolved), else ambiguous; none -> not_located; the cited verse absent from the aligned
           edition (or the chapter absent from DCS) -> locator_not_in_edition.
Outputs data/qc/mwgold/mw_gold_v0.csv, unlocated.csv, relocation_stats.json, mw_citation_counts.json (locus-bearing
MW citations per entry, for the citation-frequency stratum). Report only.

Run (.venv-skt): python -X utf8 -I pipeline/mwgold/relocate_mw.py [--texts stem,stem] [--no-oracle]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sktnorm import key as skey, join_members  # noqa: E402

GDM = HERE.parent.parent
CORPUS = GDM / "data" / "sanskrit_corpus"
FEAS = GDM / "data" / "sanskrit_feasibility"
OUT = GDM / "data" / "qc" / "mwgold"

# abbrev -> (stem, kind, parts_expected, mapper) ; mapper(parts) -> (chapter tuple, verse or None)
KSS_SIZES: dict[int, int] = {}   # lambaka -> number of taraṅgas, filled from the GRETIL refs at run time


def kss_map(parts):
    t, v = parts
    lam = 1
    while lam in KSS_SIZES and t > KSS_SIZES[lam]:
        t -= KSS_SIZES[lam]
        lam += 1
    return (lam, t), v


MEGH_N1 = [0]


def megh_map(parts):
    v = parts[0]
    n1 = MEGH_N1[0] or 66
    return ((1,), v) if v <= n1 else ((2,), v - n1)


SCOPE = {
    "RV.": ("rgveda", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "Mn.": ("manusmrti", "verse", 2, lambda p: ((p[0],), p[1])),
    "AV.": ("atharvaveda", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "BhP.": ("bhagavatapurana", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "Kathās.": ("kathasaritsagara", "verse", 2, kss_map),
    "Kum.": ("kumarasambhava", "verse", 2, lambda p: ((p[0],), p[1])),
    "Kir.": ("kiratarjuniya", "verse", 2, lambda p: ((p[0],), p[1])),
    "Bhartṛ.": ("satakatraya", "verse", 2, lambda p: ((p[0],), p[1])),
    "Gīt.": ("gitagovinda", "verse", 2, lambda p: ((p[0],), p[1])),
    "Bcar.": ("buddhacarita", "verse", 2, lambda p: ((p[0],), p[1])),
    "Megh.": ("meghaduta", "verse", 1, megh_map),
    "Amar.": ("amarusataka", "verse", 1, lambda p: ((), p[0])),   # ambuda ids AmrShtk.N carry the verse alone
    "Ṛtus.": ("rtusamhara", "verse", 2, lambda p: ((p[0],), p[1])),
    "Hit.": ("hitopadesa", "verse", 2, lambda p: ((p[0],), p[1])),
    "Pāṇ.": ("astadhyayi", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "ŚBr.": ("satapathabrahmana", "verse", 4, lambda p: ((p[0], p[1], p[2]), p[3])),
    "KātyŚr.": ("katyayanasrautasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "ĀpŚr.": ("apastambasrautasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "Lāṭy.": ("latyayanasrautasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "ŚāṅkhŚr.": ("sankhayanasrautasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "ĀśvŚr.": ("asvalayanasrautasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "ĀśvGṛ.": ("asvalayanagrhyasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "Gobh.": ("gobhilagrhyasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "ŚāṅkhGṛ.": ("sankhayanagrhyasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    "Āp.": ("apastambadharmasutra", "verse", 3, lambda p: ((p[0], p[1]), p[2])),
    # chapter-level: the DCS chapter is the cited unit
    "TS.": ("taittiriyasamhita", "chapter", (3, 4), lambda p: ((p[0], p[1], p[2]), None)),
    "MaitrS.": ("maitrayanisamhita", "chapter", 3, lambda p: ((p[0], p[1], p[2]), None)),
    "Kāṭh.": ("kathakasamhita", "chapter", 2, lambda p: ((p[0], p[1]), None)),
    "AitBr.": ("aitareyabrahmana", "chapter", (2, 3), lambda p: ((p[0], p[1]), None)),
    "TāṇḍyaBr.": ("pancavimsabrahmana", "chapter", (2, 3), lambda p: ((p[0], p[1]), None)),
    "Kauś.": ("kausikasutra", "chapter", 1, lambda p: (("kandika", p[0]), None)),
    "Gaut.": ("gautamadharmasutra", "chapter", 2, lambda p: (("adhyaya", p[0]), None)),
}
MIN_SPAN, MAX_SPAN = 2, 6
PREVERBS = ["ati", "adhi", "anu", "antar", "apa", "api", "abhi", "ava", "ā", "ud", "upa", "ni", "nis", "parā", "pari", "pra", "prati", "vi", "sam", "sa", "tiras", "puras"]


def chapter_parts(ch: str) -> tuple:
    from align_verses import chapter_parts as cp
    return cp(ch)


class Text:
    def __init__(self, stem: str):
        self.stem = stem
        u = json.loads((CORPUS / "units" / f"{stem}.json").read_text(encoding="utf-8"))
        self.sents = u["sentences"]
        self.refs = u.get("refs") or [None] * len(self.sents)
        self.method = u.get("ref_method", "chapter")
        self.tokens: list[dict] = []
        with (CORPUS / "tokens" / f"{stem}.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                self.tokens.append(json.loads(line))
        # chapter tuple -> sentence indexes (in order); ordered chapter list for order-based texts
        self.by_chapter: dict[tuple, list[int]] = defaultdict(list)
        self.chapter_order: list[tuple] = []
        for i, s in enumerate(self.sents):
            cp = chapter_parts(s[1])
            if cp not in self.by_chapter:
                self.chapter_order.append(cp)
            self.by_chapter[cp].append(i)
        # verse -> sentences
        self.by_ref: dict[tuple, list[int]] = defaultdict(list)
        for i, r in enumerate(self.refs):
            if r:
                self.by_ref[tuple(r)].append(i)
        self.all_refs = set(self.by_ref)

    def window(self, chapter: tuple, verse, kind: str) -> tuple[list[int], list[int], bool]:
        """-> (sentence indexes of the window, of the center, found)."""
        if kind == "chapter":
            if chapter and chapter[0] == "kandika":        # Kauśika: the n-th DCS chapter in order
                n = chapter[1]
                if 1 <= n <= len(self.chapter_order):
                    idx = self.by_chapter[self.chapter_order[n - 1]]
                    return idx, idx, True
                return [], [], False
            if chapter and chapter[0] == "adhyaya":        # Gautama: adhyāyas 1-28 in DCS order
                n = chapter[1]
                if 1 <= n <= len(self.chapter_order):
                    idx = self.by_chapter[self.chapter_order[n - 1]]
                    return idx, idx, True
                return [], [], False
            idx = self.by_chapter.get(chapter, [])
            return idx, idx, bool(idx)
        ref = tuple(chapter) + (verse,)
        center = self.by_ref.get(ref, [])
        if not center:
            return [], [], False
        win = list(center)
        for d in (-1, 1):
            win += self.by_ref.get(tuple(chapter) + (verse + d,), [])
        return sorted(set(win)), center, True

    def sentence_tokens(self, si: int) -> list[dict]:
        s = self.sents[si]
        return self.tokens[s[3]: s[3] + s[4]]


def candidates(toks: list[dict], hk: str, members_keys: list[str], oracle) -> list[tuple[int, int, str, dict]]:
    """-> [(token_index, span, route, token)] for one sentence."""
    out = []
    n = len(toks)
    for j, t in enumerate(toks):
        lk = skey(t["lemma"])
        if lk and lk == hk:
            out.append((t["i"], 1, "dcs", t))
            continue
        if lk and lk[:3] == hk[:3] and lk != hk:
            uk = skey(t.get("unsandhied") or t["surface"])
            if uk == hk:
                out.append((t["i"], 1, "surface", t))
                continue
            if oracle is not None:
                an = oracle.lemmas(t.get("unsandhied") or t["surface"])
                if hk in an:
                    out.append((t["i"], 1, "vidyut", t))

    # Vedic tmesis: preverb(s) + root, the preverbs standing as separate tokens near the verb
    if hk and len(hk) > 3:
        for t_i, t in enumerate(toks):
            if t["upos"] != "VERB":
                continue
            root = skey(t["lemma"])
            if not root or not hk.endswith(root) or root == hk:
                continue
            pre = hk[: len(hk) - len(root)]
            # split the prefix into one or two preverbs (sandhi-joined: abhy-ā -> abhyā, pary-ā -> paryā, ud-ā -> udā)
            near = [skey(x["lemma"]) for x in toks[max(0, t_i - 4): t_i]] + [skey(x["lemma"]) for x in toks[t_i + 1: t_i + 5]]
            found = False
            for p1 in PREVERBS:
                if pre == p1 and p1 in near:
                    found = True
                    break
                for p2 in PREVERBS:
                    if join_members([p1, p2]) == pre or p1 + p2 == pre:
                        if p1 in near and p2 in near:
                            found = True
                            break
                if found:
                    break
            if found and (t["i"], 1) not in {(o[0], o[1]) for o in out}:
                out.append((t["i"], 1, "dcs_tmesis", t))

    def starts_run(x: dict) -> bool:
        return x["cpd"] or (x["upos"] == "PART" and skey(x["lemma"]) in ("a", "an"))

    # compound spans: runs of Case=Cpd tokens (or the negative particle) ending at the first non-Cpd token
    j = 0
    while j < n:
        if not starts_run(toks[j]):
            j += 1
            continue
        k = j
        while k < n and starts_run(toks[k]):
            k += 1
        run = toks[j: min(k + 1, n)]            # members + the inflected final member (if present)
        for a in range(len(run)):
            for b in range(a + MIN_SPAN, min(len(run), a + MAX_SPAN) + 1):
                span = run[a:b]
                lem = [skey(x["lemma"]) for x in span]
                if join_members(lem) == hk or "".join(lem) == hk:
                    out.append((span[0]["i"], len(span), "dcs_cpd", span[0]))
                    continue
                surf = [skey(x.get("unsandhied") or x["surface"]) for x in span[:-1]] + [skey(span[-1]["lemma"])]
                if join_members(surf) == hk or "".join(surf) == hk:
                    out.append((span[0]["i"], len(span), "dcs_cpd", span[0]))
                    continue
                if members_keys and len(members_keys) == len(span):
                    us = [skey(x.get("unsandhied") or x["surface"]) for x in span]
                    head_ok = all(m == l or m == u for m, l, u in zip(members_keys[:-1], lem[:-1], us[:-1]))
                    m_last, l_last, u_last = members_keys[-1], lem[-1], us[-1]
                    last_ok = m_last == l_last or m_last == u_last or (len(m_last) >= 3 and u_last.startswith(m_last) and len(u_last) - len(m_last) <= 4)
                    if head_ok and last_ok:
                        out.append((span[0]["i"], len(span), "dcs_cpd", span[0]))
        j = k + 1
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", default="")
    ap.add_argument("--no-oracle", action="store_true")
    ap.add_argument("--oracle-cache", type=Path, default=CORPUS / "oracle_cache_vidyut.jsonl")
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(a.texts.split(",")) if a.texts else None
    # Kathāsaritsāgara lambaka sizes and Meghadūta's pūrvamegha length from the aligned references
    try:
        u = json.loads((CORPUS / "units" / "kathasaritsagara.json").read_text(encoding="utf-8"))
        mx: dict[int, int] = {}
        for r in u.get("refs") or []:
            if r:
                mx[r[0]] = max(mx.get(r[0], 0), r[1])
        # GRETIL's own reference list is the authority for sizes (DCS holds a part of the work)
        import re
        g = (CORPUS / "gretil" / "sa_somadeva-kathAsaritsAgara.txt").read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"sokss_(\d+),(\d+)\.", g):
            l, t = int(m.group(1)), int(m.group(2))
            mx[l] = max(mx.get(l, 0), t)
        KSS_SIZES.update(mx)
    except Exception as exc:  # noqa: BLE001
        print(f"KSS sizes unavailable: {exc}")
    try:
        u = json.loads((CORPUS / "units" / "meghaduta.json").read_text(encoding="utf-8"))
        MEGH_N1[0] = max(r[1] for r in (u.get("refs") or []) if r and r[0] == 1)
    except Exception:  # noqa: BLE001
        pass

    cites = [json.loads(l) for l in (FEAS / "mw_citations.jsonl").open(encoding="utf-8")]
    per_entry: Counter = Counter(c["L"].split(".")[0] for c in cites)
    (OUT / "mw_citation_counts.json").write_text(json.dumps(dict(per_entry), ensure_ascii=False), encoding="utf-8")

    oracle = None
    if not a.no_oracle:
        try:
            from skt_oracle import Oracle
            oracle = Oracle(a.oracle_cache)
        except Exception as exc:  # noqa: BLE001
            print(f"vidyut oracle unavailable ({exc}); DCS routes only")

    by_text: dict[str, list[dict]] = defaultdict(list)
    stats: Counter = Counter()
    for c in cites:
        sc = SCOPE.get(c["abbrev"])
        if not sc:
            stats["out_of_scope"] += 1
            continue
        stem, kind, nparts, mapper = sc
        if only and stem not in only:
            continue
        nums = [p for p in c["parts"] if isinstance(p, int)]
        ok = (len(nums) in nparts) if isinstance(nparts, tuple) else (len(nums) == nparts)
        if not ok or len(nums) != len(c["parts"]):
            stats["malformed_locus"] += 1
            continue
        by_text[stem].append(c)

    gold, unloc = [], []
    for stem, rows in sorted(by_text.items(), key=lambda kv: -len(kv[1])):
        if not (CORPUS / "units" / f"{stem}.json").exists():
            stats["text_missing"] += len(rows)
            continue
        T = Text(stem)
        n_before = stats["located"]
        for c in rows:
            stem_, kind, nparts, mapper = SCOPE[c["abbrev"]]
            nums = [p for p in c["parts"] if isinstance(p, int)]
            chapter, verse = mapper(nums)
            win, center, found = T.window(chapter, verse, kind)
            ordered = bool(chapter) and chapter[0] in ("kandika", "adhyaya")
            c = dict(c, text=stem, chapter=str(chapter[1]) if ordered else ":".join(str(x) for x in chapter),
                     ref=str(chapter[1]) if ordered else ":".join(str(x) for x in (tuple(chapter) + ((verse,) if verse is not None else ()))),
                     window_kind=kind)
            if not found:
                c["status"] = "locator_not_in_edition"
                unloc.append(c)
                stats["locator_not_in_edition"] += 1
                continue
            hk = skey(c["headword"])
            mkeys = [skey(m) for m in c.get("members", [])] if len(c.get("members", [])) > 1 else []
            cands = []
            for si in win:
                for ti, span, route, tok in candidates(T.sentence_tokens(si), hk, mkeys, oracle):
                    cands.append((si, ti, span, route, tok))
            uniq = {(ti, span) for _, ti, span, _, _ in cands}
            if len(uniq) > 1 and kind == "verse":
                inner = [x for x in cands if x[0] in set(center)]
                if len({(ti, span) for _, ti, span, _, _ in inner}) == 1:
                    cands = inner
                    uniq = {(ti, span) for _, ti, span, _, _ in cands}
                    stats["center_resolved"] += 1
            if len(uniq) == 1:
                si, ti, span, route, tok = cands[0]
                s = T.sents[si]
                gold.append({**c, "sent_id": s[0], "token_index": ti, "span": span, "surface": tok["surface"], "unsandhied": tok.get("unsandhied", ""),
                             "dcs_lemma": tok["lemma"], "upos": tok["upos"], "validation": route, "status": "located"})
                stats["located"] += 1
                stats[f"located_{route}"] += 1
                stats[f"located_window_{kind}"] += 1
            elif len(uniq) > 1:
                c["status"] = "ambiguous"
                c["candidates"] = "; ".join(sorted({f"{t['surface']}({r})" for _, _, _, r, t in cands}))
                unloc.append(c)
                stats["ambiguous"] += 1
            else:
                c["status"] = "not_located"
                unloc.append(c)
                stats["not_located"] += 1
        print(f"{stem}: {len(rows)} citations, {stats['located'] - n_before} located ({time.time()-t0:.0f}s)", flush=True)

    cols = ["headword", "k1", "k2", "hom", "L", "abbrev", "locus", "text", "chapter", "ref", "window_kind", "sent_id", "token_index", "span",
            "surface", "unsandhied", "dcs_lemma", "upos", "validation", "status", "members"]
    for g in gold:
        g["members"] = "-".join(g.get("members", []))
    with (OUT / "mw_gold_v0.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(gold)
    for u_ in unloc:
        u_["members"] = "-".join(u_.get("members", []))
    with (OUT / "unlocated.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[c for c in cols if c not in ("sent_id", "token_index", "span", "surface", "unsandhied", "dcs_lemma", "upos", "validation")] + ["candidates"], extrasaction="ignore")
        w.writeheader()
        w.writerows(unloc)
    per_text = Counter(g["text"] for g in gold)
    per_abbrev = Counter(g["abbrev"] for g in gold)
    summary = {"date": time.strftime("%Y-%m-%d"), "citations_in_scope": sum(len(v) for v in by_text.values()), "located": len(gold),
               "located_per_text": dict(per_text.most_common()), "located_per_abbrev": dict(per_abbrev.most_common()),
               "distinct_headwords": len({g["k1"] for g in gold}), "distinct_entries": len({g["L"].split(".")[0] for g in gold}),
               "status_counts": dict(stats), "oracle": oracle is not None, "kss_lambaka_sizes": KSS_SIZES, "megh_purva_verses": MEGH_N1[0],
               "elapsed_s": round(time.time() - t0, 1),
               "rule": "window = sentences of the cited verse ± 1 verse (chapter for TS/MS/KS/AB/PB/KauśS/GautDhS, flagged); validation dcs (DCS lemma key = headword key) "
                       "/ dcs_cpd (compound span, incl. a/an-, whose members join to the headword or match MW's member list) / vidyut (kosha analyses contain the headword, DCS lemma shares 3 letters) / surface (token = headword, DCS lemma shares 3 letters) / dcs_tmesis (Vedic tmesis: verb token whose root + nearby separate preverb(s) = headword); "
                       "exactly one candidate -> gold; several -> the cited verse decides if it holds exactly one; else ambiguous; none -> not_located"}
    (OUT / "relocation_stats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
