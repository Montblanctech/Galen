"""LSJ-Gold, stage 1 — relocate CTS-tagged LSJ citations into the token streams we hold (spec: lsj_gold_benchmark_spec.md).

The Perseus LSJ XML carries ``<bibl n="urn:cts:greekLit:tlg0085.tlg005.perseus-grc1:1172">`` on ~420k
citations. For every cited (author, work) that this project holds as a First1K TEI edition + odyCy token
JSONL, this stage:
  1. extracts (headword, locator, quoted form) per citation (quote logic reused from h3m/m3_lsj_gold.py);
  2. indexes the TEI by CTS locator: ``<l n>`` lines for drama, nested ``div[@type='textpart'][@n]`` paths
     ("1:2:2") for prose; the passage's tokens come from the element's own text;
  3. aligns passage tokens to the work's JSONL token indices (sequential greedy alignment, same TEI source);
  4. validates candidate surfaces in a window (cited unit ± 1 sibling) against the LSJ headword:
       morpheus  — the surface's Morpheus analyses contain the headword (accent-blind; cache first,
                   online only for surfaces that share the headword's first two letters, rate-limited);
       quoted    — the surface equals LSJ's quoted form for that citation (accent-blind), used only when
                   Morpheus has no analysis for it;
     exactly one validated token in the window -> gold locus; several -> ambiguous; none -> not_located.
Report only; nothing is edited. Outputs data/qc/lsjgold/lsj_gold_v0.csv (+ relocation_stats.json, unlocated.csv).

Usage (.venv): python -X utf8 pipeline/lsjgold/relocate.py [--online --max-online N] [--authors tlg0085,tlg0627]
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
GDM = PIPE.parent
sys.path.insert(0, str(PIPE))
from lib.beta_keys import betacode_headword_to_unicode, lemma_to_lookup_key  # noqa: E402
from lib.greek_normalize import TOKEN_RE  # noqa: E402

OUT = GDM / "data" / "qc" / "lsjgold"
URN_RE = re.compile(r"urn:cts:greekLit:(tlg\d{4})\.(tlg\d{3})\.([A-Za-z0-9-]+):([^\s\"]*)")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


def _load_m3():
    spec = importlib.util.spec_from_file_location("m3_lsj_gold", PIPE / "h3m" / "m3_lsj_gold.py")
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(PIPE))
    spec.loader.exec_module(m)
    return m


def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


_EDGE = re.compile(r"^[^\wͰ-Ͽἀ-῿]+|[^\wͰ-Ͽἀ-῿᾽᾿’ʼ']+$")


def clean_tokens(toks: list[str]) -> list[str]:
    """Strip punctuation glued to TEI words (πέδον, -> πέδον; Προμηθεῦ: -> Προμηθεῦ), keep elision marks,
    drop tokens without a Greek letter (apparatus sigla, Latin editor names)."""
    out = []
    for t in toks:
        t = _EDGE.sub("", t)
        if re.search(r"[Ͱ-Ͽἀ-῿]", t):
            out.append(t)
    return out


# ---------------------------------------------------------------- held works
def held_works() -> dict[tuple[str, str], tuple[Path, Path]]:
    """(author, work) -> (tei xml, token jsonl) for works we hold (First1K reference + Galen)."""
    out = {}
    pairs = [(GDM / "data" / "reference_corpus" / "raw_xml", GDM / "data" / "lemmatized" / "reference"),
             (GDM / "data" / "raw_xml", GDM / "data" / "lemmatized" / "galen"),
             (GDM / "data" / "perseus_corpus" / "raw_xml", GDM / "data" / "perseus_corpus" / "lemmatized")]
    for xml_dir, lem_dir in pairs:
        if not xml_dir.exists():
            continue
        for x in sorted(xml_dir.glob("urn_cts_greekLit_tlg*.xml")):
            m = re.match(r"urn_cts_greekLit_(tlg\d{4})\.(tlg\d{3})\.(.+)", x.stem)
            if not m:
                continue
            j = lem_dir / f"{x.stem}.jsonl"
            if j.exists() and (m.group(1), m.group(2)) not in out:
                out[(m.group(1), m.group(2))] = (x, j)
    return out


# ---------------------------------------------------------------- TEI passage index
def passage_index(xml_path: Path) -> list[tuple[str, list[str]]]:
    """Ordered [(locator, tokens)] for a TEI edition: lines (n) or textpart div paths joined by ':'."""
    parser = etree.XMLParser(recover=True, huge_tree=True, remove_comments=True, remove_pis=True)
    tree = etree.parse(str(xml_path), parser)
    body = tree.xpath("//*[local-name()='body']")
    if not body:
        return []
    out: list[tuple[str, list[str]]] = []

    def has_units(el) -> bool:
        """Does this element contain textpart divs or lines anywhere below? (then its text is theirs, not ours)"""
        for d in el.iter():
            if d is el:
                continue
            t = local(d.tag)
            if (t == "div" and d.get("type") == "textpart" and d.get("n")) or (t == "l" and d.get("n"))                     or (t == "milestone" and d.get("unit") == "section" and d.get("n")):
                return True
        return False

    def own_tokens(el) -> list[str]:
        # text of this element excluding nested units (handled as their own units), notes and apparatus
        parts = []
        if el.text:
            parts.append(el.text)
        for ch in el:
            t = local(ch.tag)
            if t in ("note", "bibl", "ref", "head", "speaker", "label", "app", "rdg", "wit"):
                pass
            elif (t == "div" and ch.get("type") == "textpart") or t == "l" or has_units(ch):
                pass
            else:
                parts.append("".join(ch.itertext()))
            if ch.tail:
                parts.append(ch.tail)
        return TOKEN_RE.findall(" ".join(parts))

    def milestone_units(el, path: list[str]) -> bool:
        """Stephanus-style sections: <milestone unit="section" n="327a"/> splitting the running text of an element.
        Emits one unit per milestone (text up to the next milestone, nested elements' text included, notes dropped)."""
        ms = [g for g in el if local(g.tag) == "milestone" and g.get("unit") == "section" and g.get("n")]
        if not ms:
            return False
        cur = None
        buf: list[str] = []
        def flush():
            if cur is not None:
                toks = clean_tokens(TOKEN_RE.findall(" ".join(buf)))
                if toks:
                    out.append((cur, toks))
        if el.text:
            buf.append(el.text)
        for g in el:
            t = local(g.tag)
            if t == "milestone" and g.get("unit") == "section" and g.get("n"):
                flush()
                cur, buf = g.get("n"), []
            elif t in ("note", "bibl", "ref", "head", "speaker", "label", "app", "rdg", "wit", "milestone"):
                pass
            else:
                sub = [t2 for t2 in g.iter() if local(t2.tag) == "milestone" and t2.get("unit") == "section"]
                if sub:
                    # a nested element that itself carries section milestones: recurse into it with the same cursor
                    for part in _split_by_milestones(g):
                        if part[0] is None:
                            buf.append(part[1])
                        else:
                            flush()
                            cur, buf = part[0], [part[1]]
                else:
                    buf.append("".join(g.itertext()))
            if g.tail:
                buf.append(g.tail)
        flush()
        return True

    def _split_by_milestones(g):
        """[(None, text)] then (n, text) chunks for an element with section milestones anywhere inside."""
        parts: list[tuple[str | None, str]] = []
        cur_text: list[str] = []
        cur_key = None
        def push():
            parts.append((cur_key, " ".join(cur_text)))
        if g.text:
            cur_text.append(g.text)
        for ch in g:
            t = local(ch.tag)
            if t == "milestone" and ch.get("unit") == "section" and ch.get("n"):
                push()
                cur_key, cur_text = ch.get("n"), []
            elif t in ("note", "bibl", "ref", "head", "speaker", "label", "app", "rdg", "wit", "milestone"):
                pass
            else:
                for k2, txt in _split_by_milestones(ch):
                    if k2 is None:
                        cur_text.append(txt)
                    else:
                        push()
                        cur_key, cur_text = k2, [txt]
            if ch.tail:
                cur_text.append(ch.tail)
        push()
        return parts

    def walk(el, path: list[str]):
        if milestone_units(el, path):
            return
        for ch in el:
            t = local(ch.tag)
            if t == "div" and ch.get("type") == "textpart" and ch.get("n"):
                p = path + [ch.get("n")]
                if not milestone_units(ch, p):
                    own = own_tokens(ch)
                    own = clean_tokens(own)
                    if own:
                        out.append((":".join(p), own))
                    walk(ch, p)
            elif t == "l" and ch.get("n"):
                parts = [ch.text or ""]
                for g in ch:  # drop editorial notes/apparatus nested in the line, keep its words
                    if local(g.tag) not in ("note", "bibl", "ref", "app", "rdg", "wit"):
                        parts.append("".join(g.itertext()))
                    parts.append(g.tail or "")
                key = ":".join(path + [ch.get("n")]) if path else ch.get("n")  # Homer "1:5"; drama keeps the bare line number
                out.append((key, clean_tokens(TOKEN_RE.findall(" ".join(parts)))))
            elif t in ("note",):
                continue
            else:
                walk(ch, path)

    walk(body[0], [])
    seen: dict[str, int] = {}
    uniq: list[tuple[str, list[str]]] = []
    for k, toks in out:
        if k in seen:
            seen[k] += 1
            uniq.append((f"{k}@{seen[k]}", toks))  # unreachable by an LSJ locator, still aligned
        else:
            seen[k] = 0
            uniq.append((k, toks))
    return uniq


def align_to_jsonl(passages: list[tuple[str, list[str]]], jsonl: Path) -> dict[str, list[tuple[str, int | None]]]:
    raw = [nfc(json.loads(l)["surface"]) for l in jsonl.open(encoding="utf-8")]
    # the project's tokens sometimes keep glued punctuation ("τρόπον)."): compare both sides cleaned the same way
    toks = [_EDGE.sub("", t) or t for t in raw]
    bkeys = [blind(t) for t in toks]
    j = 0
    miss_streak = 0
    out: dict[str, list[tuple[str, int | None]]] = {}
    flat = [(loc, nfc(p)) for loc, ptoks in passages for p in ptoks]
    for n, (loc, pn) in enumerate(flat):
        nxt = flat[n + 1][1] if n + 1 < len(flat) else None
        nxt2 = flat[n + 2][1] if n + 2 < len(flat) else None
        idx = None
        # 1. exact NFC match within a short lookahead (TEI apparatus tokens are skipped by leaving the pointer alone)
        for d in range(0, 40):
            if j + d < len(toks) and toks[j + d] == pn:
                idx = j + d
                break
        # 2. accent/case-blind match within a shorter window
        if idx is None:
            pb = blind(pn)
            if pb:
                for d in range(0, 8):
                    if j + d < len(toks) and bkeys[j + d] == pb:
                        idx = j + d
                        break
        # 3. long resync only when genuinely lost (8+ consecutive misses: front matter, a hypothesis, a gap), and only
        #    on a three-token confirmation so a pair of function words cannot drag the pointer away
        if idx is None and miss_streak >= 8 and nxt is not None and nxt2 is not None:
            bn, bn2 = blind(nxt), blind(nxt2)
            for d in range(0, 3000):
                k = j + d
                if k + 2 < len(toks) and toks[k] == pn and bkeys[k + 1] == bn and bkeys[k + 2] == bn2:
                    idx = k
                    break
        if idx is not None:
            j = idx + 1
            miss_streak = 0
        else:
            miss_streak += 1
        out.setdefault(loc, []).append((raw[idx] if idx is not None else pn, idx))
    return out


# ---------------------------------------------------------------- citations
def citations(lsj_dir: Path, held: set[tuple[str, str]], m3) -> list[dict]:
    rows = []
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    for path in sorted(lsj_dir.glob("grc.lsj.perseus-eng*.xml"), key=lambda p: int(re.sub(r"\D", "", p.stem.split("eng")[-1]) or 0)):
        tree = etree.parse(str(path), parser)
        for entry in tree.xpath("//*[local-name()='entryFree'] | //*[local-name()='entry']"):
            key = entry.get("key") or ""
            headword = betacode_headword_to_unicode(re.sub(r"\d+$", "", key)) if key else ""
            if not headword:
                continue
            for bibl in entry.xpath(".//*[local-name()='bibl']"):
                n = bibl.get("n") or ""
                m = URN_RE.search(n)
                if not m:
                    continue
                a, w, ed, loc = m.groups()
                if (a, w) not in held:
                    continue
                q = m3._quote_near_bibl(bibl)
                rows.append({"headword": headword, "headword_key": blind(headword), "author": a, "work": w, "cited_edition": ed,
                             "locator": loc.strip(), "quoted_form": m3._to_unicode_form(q) if q else "", "lsj_part": path.name,
                             "entry_key": key})
    return rows


def sibling_window(index_keys: list[str], loc: str) -> list[str]:
    """The cited unit and its neighbours in document order; falls back to prefix match (e.g. '1:2' for '1:2:2' units)."""
    if loc in index_keys:
        i = index_keys.index(loc)
        return index_keys[max(0, i - 1) : i + 2]
    pref = [k for k in index_keys if k.startswith(loc + ":")]
    if pref:
        return pref
    # a locator that drops a trailing letter or a lyric-restart suffix
    if ":" not in loc:
        tails = [k for k in index_keys if k.endswith(":" + loc)]
        if len(tails) == 1:
            i = index_keys.index(tails[0])
            return index_keys[max(0, i - 1) : i + 2]
    base = re.sub(r"[a-z]$", "", loc)
    if base in index_keys:
        i = index_keys.index(base)
        return index_keys[max(0, i - 1) : i + 2]
    return []


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--authors", default="", help="comma list of tlg ids to restrict to")
    ap.add_argument("--online", action="store_true", help="query Morpheus for uncached candidate surfaces (prefix-filtered)")
    ap.add_argument("--max-online", type=int, default=0)
    ap.add_argument("--rate", type=float, default=0.5)
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    m3 = _load_m3()
    held = held_works()
    if a.authors:
        keep = set(a.authors.split(","))
        held = {k: v for k, v in held.items() if k[0] in keep}
    print(f"held works: {len(held)}", flush=True)

    cites = citations(GDM / "data" / "lsj", set(held), m3)
    print(f"citations into held works: {len(cites)} ({time.time()-t0:.0f}s)", flush=True)
    by_work = defaultdict(list)
    for c in cites:
        by_work[(c["author"], c["work"])].append(c)

    # Morpheus: project cache read-only + own cache for new lookups
    from h3m.morpheus_client import MorpheusClient  # type: ignore

    main_cache = GDM / "data" / "qc" / "h3m" / "cache" / "morpheus_by_surface.jsonl"
    client = MorpheusClient(OUT / "morpheus_lsjgold.jsonl")
    extra = {}
    if main_cache.exists():
        for line in main_cache.open(encoding="utf-8", errors="ignore"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("surface_nfc"):
                extra[r["surface_nfc"]] = r
    print(f"morpheus cache: {len(extra)} project surfaces + {len(client._cache)} own", flush=True)
    n_online = 0

    def analyses(surface: str) -> list[str] | None:
        nonlocal n_online
        r = extra.get(surface) or client._cache.get(surface)
        if r is not None:
            return list(r.get("lemmas") or []) if r.get("ok") else []
        if not a.online or (a.max_online and n_online >= a.max_online):
            return None
        n_online += 1
        time.sleep(a.rate)
        try:
            return list(client.analyze(surface) or [])
        except Exception:
            return None

    gold, unlocated = [], []
    stats = Counter()
    for (au, wk), rows in sorted(by_work.items(), key=lambda kv: -len(kv[1])):
        xml, jsonl = held[(au, wk)]
        passages = passage_index(xml)
        keys = [k for k, _ in passages]
        aligned = align_to_jsonl(passages, jsonl)
        n_tok = sum(len(v) for v in aligned.values())
        n_al = sum(1 for v in aligned.values() for _, i in v if i is not None)
        stats[f"{au}.{wk}:passages"] = len(keys)
        print(f"{au}.{wk}: {len(rows)} citations, {len(keys)} units, aligned {n_al}/{n_tok} tokens ({time.time()-t0:.0f}s)", flush=True)
        for c in rows:
            win = sibling_window(keys, c["locator"])
            if not win:
                c.update(status="locator_not_in_edition")
                unlocated.append(c)
                stats["locator_not_in_edition"] += 1
                continue
            hk = c["headword_key"]
            qk = blind(c["quoted_form"]) if c["quoted_form"] else ""
            cands = []
            for k in win:
                for surf, idx in aligned.get(k, []):
                    sk = blind(surf)
                    if not sk:
                        continue
                    an = analyses(surf) if sk[:2] == hk[:2] else analyses(surf) if surf in extra else None
                    if an:
                        if any(blind(x) == hk for x in an):
                            cands.append((k, surf, idx, "morpheus"))
                            continue
                    elif an is None and qk and sk == qk:
                        cands.append((k, surf, idx, "quoted"))
                    elif an == [] and qk and sk == qk:
                        cands.append((k, surf, idx, "quoted"))
            # a quoted multi-word form: accept the single quoted token that shares the headword prefix
            if not cands and qk:
                qtoks = [blind(t) for t in TOKEN_RE.findall(c["quoted_form"])]
                qtoks = [t for t in qtoks if t[:2] == hk[:2]]
                for k in win:
                    for surf, idx in aligned.get(k, []):
                        if blind(surf) in qtoks:
                            cands.append((k, surf, idx, "quoted"))
            uniq = {(s, i) for _, s, i, _ in cands}
            if len(uniq) == 1 and cands[0][2] is not None:
                k, surf, idx, how = cands[0]
                gold.append({**c, "unit": k, "token_index": idx, "surface": surf, "validation": how, "status": "located"})
                stats["located"] += 1
                stats[f"located_{how}"] += 1
            elif len(uniq) > 1:
                c.update(status="ambiguous", candidates="; ".join(sorted({s for _, s, _, _ in cands})))
                unlocated.append(c)
                stats["ambiguous"] += 1
            else:
                c.update(status="not_located" if any(len(aligned.get(k, [])) for k in win) else "unit_empty")
                unlocated.append(c)
                stats[c["status"]] += 1

    cols = ["headword", "headword_key", "author", "work", "cited_edition", "locator", "unit", "token_index", "surface", "validation",
            "quoted_form", "lsj_part", "entry_key", "status"]
    with (OUT / "lsj_gold_v0.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(gold)
    with (OUT / "unlocated.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[c for c in cols if c not in ("unit", "token_index", "surface", "validation")] + ["candidates"], extrasaction="ignore")
        w.writeheader()
        w.writerows(unlocated)
    per_author = Counter(g["author"] for g in gold)
    summary = {"date": time.strftime("%Y-%m-%d"), "citations_into_held_works": len(cites), "located": len(gold),
               "located_per_author": dict(per_author.most_common()), "status_counts": {k: v for k, v in stats.items() if ":" not in k},
               "online_lookups": n_online, "elapsed_s": round(time.time() - t0, 1),
               "rule": "window = cited unit ±1 sibling; validation morpheus (headword in analyses, accent-blind) else quoted-form equality when Morpheus has no analysis; exactly one validated surface -> gold"}
    (OUT / "relocation_stats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
