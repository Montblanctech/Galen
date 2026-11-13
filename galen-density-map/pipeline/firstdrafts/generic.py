"""First Drafts, generic front end: any TEI text + a work config + a lexicon -> units.jsonl, targets.csv, units_meta.json.

The same three files units.py writes for a Galen work (same field and column names, so translate.py, checks.py and
page.py read them unchanged), driven by a work config instead of hard-coded Galen facts. Methods note: RECIPE.md.

Stages (deterministic; no model call anywhere in this module):
  1. TEI -> token stream (`tei_tokens`): whitespace tokens of the edition div, notes/apparatus skipped; every unit
     boundary element of the config (a <pb>, a <milestone>, or a <div> of some subtype) becomes an inline marker token
     "[ref]", and every token carries the current ref and the current structural levels (book, chapter, ...).
  2. Boundaries (`unit_boundaries`): at each marker, snap back to the last sentence end since the previous boundary
     (so no unit starts or ends mid-sentence); a unit shorter than `min_tokens` is merged forward; a title line
     alone joins the unit it heads; a trailing segment with no words joins the previous unit. This is units.py's
     rule with its constants made parameters (the title-line rule never fires on the fourteen Galen works).
  3. Tagger adapter -> lemma + UPOS per word:
       odycy_precomputed  a frozen odyCy stream (data/lemmatized/...), aligned to the TEI words (h3m.align, as units.py)
       latincy            LatinCy la_core_web_lg over the TEI words themselves (run in .venv-lat by latin_tagger.py;
                          the stream IS the TEI words, so no alignment), Collatinus as the fallback to a lexicon headword
  4. Lexicon adapter -> headword, entry id, sense count, tier per NOUN/ADJ token:
       lsj  Dilemma (lang grc, LSJ convention) lemma, looked up in the stage-06 LSJ index data/lsj/_lsj_index.json
       ls   LatinCy lemma, else Collatinus' first lemma, else Collatinus' only lemma with an entry, looked up in an index
            of Perseus Lewis & Short (data/latin_feasibility/lat.ls.perseus-eng2.xml), built once and cached
     tier: absent (no entry), thin (entry with <= thin_max_senses senses; 1, the Galen punch-list threshold), rich.
  5. Targets, one of two rules:
       galen            units.py's rule exactly: punch list + four-way genuinely_hard, rarest in whole Galen first
       lexicon_rarity   any text: NOUN/ADJ tokens whose lemma is outside the top `freq_top_n` lemmas of a reference
                        corpus lemmatized by the same tagger (odyCy reference corpus for grc, LatinCy over the 173
                        Perseus Latin editions minus the work itself for lat); ranked lexicon-thin first, then rich,
                        then absent (absent is mostly lemmatizer debris: Galen absent-tier reader pass), rarest in the
                        reference corpus first; distinct lemmas, `cap` per unit.

Usage (from galen-density-map/):
  ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/generic.py --work adversus-lycum --out <scratch>
  ../.venv/Scripts/python -X utf8 pipeline/firstdrafts/generic.py --config pipeline/firstdrafts/configs/vitruvius-3.json \
      --out outputs/firstdrafts/_smoke_lat
Writes <out>/<slug>/units.jsonl, targets.csv, units_meta.json, front_end.json (config, hashes, versions), and
cost_estimate.json (grc only; the Greek token proxy) or tagged.jsonl (the tagger stream, when the tagger ran here).
Refuses to overwrite a published work's units.jsonl unless --overwrite.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from lxml import etree

from common import GDM, REPO, SENTENCE_END, WORKS, nfc, sha256, strip_punct, write_jsonl

TEI_NS = "{http://www.tei-c.org/ns/1.0}"
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
CACHE = GDM / "data" / "firstdrafts_cache"
SCRIPT_RE = {"grc": r"[Ͱ-Ͽἀ-῿]", "lat": r"[A-Za-zÀ-ɏ]"}


# ------------------------------------------------------------------ config
def galen_config(slug: str) -> dict:
    """The work config of a Galen work in common.WORKS (Kühn pages from First1KGreek <pb n>, the Galen target rule)."""
    w = WORKS[slug]
    unit = {
        "break": {"tag": "pb", "attr": "n", "ref": "{n}"},
        "levels": [{"name": "book", "tag": "div", "match": {"subtype": "book"}, "attr": "n"},
                   {"name": "chapter", "tag": "div", "match": {"subtype": "chapter"}, "attr": "n"}],
        "reset_ref_on_level": False,
        "sentence_end": list(SENTENCE_END), "sentence_end_strip": "", "not_sentence_end_re": None,
        "min_tokens": 25,
        "ref_sort": "int", "chapter_sort": "key", "book_sort": "int",
        "id": {"prefix": f"K{w['kuhn_vol_short']}.", "range": "-"},
        "locus": {"prefix": f"K. {w['kuhn_vol']} ", "range": "–"},
        "keep": {"level": "book", "values": list(w["books"])} if w.get("books") else None,
        "extra": {"kuhn_vol": w["kuhn_vol"]},
    }
    return {
        "slug": slug, "lang": "grc", "profile": "galen",
        "tei": f"data/raw_xml/{w['stem']}.xml", "urn": w["urn"], "source_note": w["source_note"],
        "text": {"normalize": "greek", "skip": ["note", "app", "rdg", "teiHeader"]},
        "unit": unit,
        "tagger": {"name": "odycy_precomputed", "path": f"data/lemmatized/{w['lemmatized_dir']}/{w['stem']}.jsonl", "align_window": 12},
        "lexicon": {"name": "lsj"},
        "targets": {"rule": "galen", "pos": ["NOUN", "ADJ"], "cap": 8},
    }


DEFAULT_UNIT = {"reset_ref_on_level": False, "sentence_end": [".", "?", "!"], "sentence_end_strip": "", "not_sentence_end_re": None,
                "min_tokens": 25, "ref_sort": "doc", "chapter_sort": "doc", "book_sort": "doc", "keep": None, "extra": {}}
DEFAULT_TARGETS = {"rule": "lexicon_rarity", "pos": ["NOUN", "ADJ"], "cap": 8, "thin_max_senses": 1, "freq_top_n": 5000}


def load_config(path: Path) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("profile", "generic")
    cfg.setdefault("text", {})
    cfg["text"].setdefault("normalize", "greek" if cfg["lang"] == "grc" else "nfc")
    cfg["text"].setdefault("skip", ["note", "app", "rdg", "teiHeader"])
    cfg["unit"] = {**DEFAULT_UNIT, **cfg["unit"]}
    cfg["targets"] = {**DEFAULT_TARGETS, **cfg.get("targets", {})}
    return cfg


# ------------------------------------------------------------------ stage 1: TEI -> tokens
def chapter_key(c: str) -> list:
    """'2.3a' -> [2, 3, 'a'] (units.py's chapter sort)."""
    out = []
    for part in c.split("."):
        m = re.match(r"(\d+)(.*)", part)
        out += [int(m.group(1)), m.group(2)] if m else [10**6, part]
    return out


def _matches(el, tag: str, spec: dict) -> bool:
    if etree.QName(el).localname != spec.get("tag", tag):
        return False
    return all(el.get(k) == v for k, v in (spec.get("match") or {}).items())


def tei_tokens(xml_path, cfg: dict) -> list[dict]:
    """Token stream of the edition. Each token: surface, page (the current unit ref), chapter (the level path, None
    until the deepest level is set), book (the level named 'book'), head; boundary elements become marker tokens
    {"surface": "[ref]", "pb": True}. Comments and processing instructions are skipped (their tails are kept)."""
    u, tx = cfg["unit"], cfg["text"]
    if tx["normalize"] == "greek":
        from lib.greek_normalize import normalize_lunate_sigma  # noqa: E402

        def norm(s: str) -> str:
            return normalize_lunate_sigma(nfc(s))
    else:
        norm = nfc
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    root = etree.parse(str(xml_path), parser).getroot()
    edition = None
    for xp in (f".//{TEI_NS}div[@type='edition']", ".//div[@type='edition']", f".//{TEI_NS}body", ".//body"):
        edition = root.find(xp)
        if edition is not None:   # (an lxml element with no children is falsy: test against None)
            break
    brk, levels = u["break"], u["levels"]
    names = [lv["name"] for lv in levels]
    skip = set(tx["skip"])
    state = {"page": None, "head": False, **{n: None for n in names}}
    toks: list[dict] = []

    def chap() -> str | None:
        if not names or state[names[-1]] is None:
            return None
        return ".".join(state[n] for n in names if state[n] is not None)

    def emit(text: str) -> None:
        for m in re.finditer(r"\S+", norm(text)):
            toks.append({"surface": m.group(0), "page": state["page"], "chapter": chap(), "book": state.get("book"), "head": state["head"]})

    def walk(el) -> None:
        if not isinstance(el.tag, str):
            return
        tag = etree.QName(el).localname
        if tag in skip:
            return
        for k, lv in enumerate(levels):
            if _matches(el, "div", lv):
                state[lv["name"]] = el.get(lv.get("attr", "n"))
                for deeper in names[k + 1:]:
                    state[deeper] = None
                if u["reset_ref_on_level"]:
                    state["page"] = None
                break
        if _matches(el, "pb", brk):
            n = el.get(brk.get("attr", "n"))
            ref = brk["ref"].format(n=n, **{x: state[x] for x in names}) if n is not None else None
            state["page"] = ref
            toks.append({"surface": f"[{ref}]", "page": ref, "chapter": chap(), "book": state.get("book"), "head": False, "pb": True})
        elif tag == "head":
            state["head"] = True
        if el.text and tag not in {"pb", "milestone"}:
            emit(el.text)
        for ch in el:
            walk(ch)
            if ch.tail:
                emit(ch.tail)
        if tag == "head":
            state["head"] = False

    walk(edition)
    return toks


# ------------------------------------------------------------------ stage 2: boundaries
def sentence_end_fn(ucfg: dict):
    ends = tuple(ucfg["sentence_end"])
    strip = ucfg.get("sentence_end_strip") or ""
    not_end = re.compile(ucfg["not_sentence_end_re"]) if ucfg.get("not_sentence_end_re") else None

    def is_end(surface: str) -> bool:
        s = surface.rstrip(strip) if strip else surface
        if not s.endswith(ends):
            return False
        return not (not_end and not_end.match(s))
    return is_end


def unit_boundaries(toks: list[dict], ucfg: dict) -> list[int]:
    """units.py's boundary rule: snap each break back to the last sentence end; merge short units; drop an empty tail."""
    is_end_s = sentence_end_fn(ucfg)
    min_tokens = int(ucfg["min_tokens"])
    n = len(toks)
    is_end = [(not t.get("pb")) and is_end_s(t["surface"]) for t in toks]
    boundaries = [0]
    for i, t in enumerate(toks):
        if t.get("pb") and i > 0:
            j = i - 1
            while j > boundaries[-1] and not is_end[j]:
                j -= 1
            cut = j + 1 if j > boundaries[-1] else i
            # a title line alone (head tokens only, e.g. 'LIBER III' before the first section) joins the unit it heads
            if all(x.get("pb") or x["head"] for x in toks[boundaries[-1]:cut]):
                continue
            if cut > boundaries[-1]:
                boundaries.append(cut)
    boundaries.append(n)
    merged = [boundaries[0]]
    for b in boundaries[1:]:
        if b - merged[-1] < min_tokens and len(merged) > 1 and b != n:
            continue
        merged.append(b)
    boundaries = merged
    if len(boundaries) > 2 and not any(not t.get("pb") for t in toks[boundaries[-2]:boundaries[-1]]):
        del boundaries[-2]
    return boundaries


def _ordered(values, how: str) -> list:
    vals = [v for v in values if v]
    if how == "int":
        return sorted(set(vals), key=int)
    if how == "key":
        return sorted(set(vals), key=chapter_key)
    return list(dict.fromkeys(vals))


# ------------------------------------------------------------------ stage 3: tagger adapters
def tag_odycy_precomputed(words: list[dict], tcfg: dict) -> dict:
    from h3m.align import align_surfaces  # noqa: E402

    path = GDM / tcfg["path"]
    odycy = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    pairs, loss = align_surfaces([strip_punct(t["surface"]) for t in words], [strip_punct(t["surface"]) for t in odycy], window=int(tcfg.get("align_window", 12)))
    tei2ody = {i: j for i, j in pairs}
    for i, t in enumerate(words):
        j = tei2ody.get(i)
        t["ody_i"] = j
        t["lemma"] = nfc(odycy[j]["lemma"]) if j is not None else ""
        t["pos"] = odycy[j]["pos"] if j is not None else ""
    return {"stream": str(path.relative_to(GDM)).replace("\\", "/"), "n_stream_tokens": len(odycy), "alignment_loss": loss, "rows": odycy}


def _latin_worker(payload: dict, tcfg: dict) -> dict:
    py = REPO / tcfg.get("python", ".venv-lat/Scripts/python.exe")
    with tempfile.TemporaryDirectory() as td:
        fin, fout = Path(td) / "in.json", Path(td) / "out.json"
        fin.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([str(py), "-X", "utf8", str(Path(__file__).with_name("latin_tagger.py")), str(fin), str(fout)], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(f"latin_tagger.py failed ({py}):\n{r.stderr[-3000:]}")
        return json.loads(fout.read_text(encoding="utf-8"))


def latin_lemmas_in_context(texts: list[str], tcfg: dict) -> list[list[tuple[str, str, dict]]]:
    """Per text, (word, LatinCy lemma, Collatinus analyses) for every Latin word, the texts lemmatized in order (one
    worker call; LatinCy sees each word in its sentence, as the source stream was tagged)."""
    per = [[strip_punct(w).replace("—", "") for w in t.split()] for t in texts]
    per = [[w for w in ws if re.search(SCRIPT_RE["lat"], w)] for ws in per]
    flat = [w for ws in per for w in ws]
    if not flat:
        return [[] for _ in texts]
    res = _latin_worker({"words": flat, "model": tcfg.get("model", "la_core_web_lg"), "collatinus_all": True}, tcfg)
    out, k = [], 0
    for ws in per:
        out.append([(w, res["lemma"][k + i], res["collatinus"].get(w.lower()) or {}) for i, w in enumerate(ws)])
        k += len(ws)
    return out


def tag_latincy(words: list[dict], tcfg: dict, wanted: list[bool]) -> dict:
    """LatinCy over the TEI words themselves, so no alignment is needed. The stream (tagged.jsonl) holds the words that
    carry Latin letters, in order; ody_i is a word's POSITION IN THAT STREAM (fixed 2026-11-12: it was the TEI word
    index, which drifts from the stream position at every numeral or Greek word, so checks.py sliced the wrong lemmas).
    Runs latin_tagger.py in the Latin venv (.venv-lat holds spaCy + la_core_web_lg + pycollatinus); only `wanted`
    words are sent (the kept books)."""
    idx = [i for i, t in enumerate(words) if wanted[i] and re.search(SCRIPT_RE["lat"], strip_punct(t["surface"]))]
    payload = {"words": [strip_punct(words[i]["surface"]).replace("—", "").replace("-", "") or words[i]["surface"] for i in idx],
               "model": tcfg.get("model", "la_core_web_lg")}
    res = _latin_worker(payload, tcfg)
    for t in words:
        t["ody_i"], t["lemma"], t["pos"], t["collatinus"] = None, "", "", None
    for k, i in enumerate(idx):
        t = words[i]
        t["ody_i"], t["lemma"], t["pos"] = k, nfc(res["lemma"][k]), res["pos"][k]
        t["collatinus"] = res["collatinus"].get(payload["words"][k].lower())
    return {"stream": "tagged.jsonl", "n_stream_tokens": len(idx), "alignment_loss": None, "versions": res["versions"]}


# ------------------------------------------------------------------ stage 4: lexicon adapters
def ls_index(xml_path: Path) -> dict:
    """Lewis & Short index (cached): latnorm key of the entry key and of every <orth> -> the entry with most senses:
    {id, key, headword (first orth, as printed), senses, n_bibl}."""
    from lsgold.latnorm import key as lkey  # noqa: E402

    cache = CACHE / "ls_index.json"
    stamp = f"{xml_path.name}:{xml_path.stat().st_size}"
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("_source") == stamp:
            return d["index"]
    index: dict[str, dict] = {}
    for _, el in etree.iterparse(str(xml_path), events=("end",), tag=("{*}entryFree", "entryFree"), recover=True, huge_tree=True):
        key_attr = el.get("key") or ""
        orths = [o.text for o in el.iter("{*}orth", "orth") if o.text]
        senses = len(list(el.iter("{*}sense", "sense")))
        rec = {"id": el.get("id") or "", "key": key_attr, "headword": (orths[0] if orths else key_attr).strip(),
               "senses": senses, "n_bibl": len(list(el.iter("{*}bibl", "bibl")))}
        for hw in [key_attr] + orths:
            k = lkey(re.sub(r"\d+$", "", hw))
            if k and (k not in index or senses > index[k]["senses"]):
                index[k] = rec
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"_source": stamp, "index": index}, ensure_ascii=False), encoding="utf-8")
    return index


class LSJLexicon:
    name = "lsj"
    source = "data/lsj/_lsj_index.json (stage 06 index of Perseus LSJ; key = lib.beta_keys.lemma_to_lookup_key)"

    def __init__(self, thin_max: int):
        from dilemma import Dilemma  # type: ignore
        from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

        self.key = lemma_to_lookup_key
        self.index = json.loads((GDM / "data" / "lsj" / "_lsj_index.json").read_text(encoding="utf-8"))
        self.dil = Dilemma(lang="grc", convention="lsj")
        self.thin_max = thin_max
        self.memo: dict[str, str] = {}
        self.version = "dilemma " + __import__("dilemma").__version__

    def lexicon_lemma(self, t: dict) -> str:
        s = strip_punct(t["surface"])
        if s not in self.memo:
            try:
                self.memo[s] = nfc(self.dil.lemmatize(s, guess=True) or "")
            except Exception:
                self.memo[s] = ""
        return self.memo[s]

    def resolve(self, t: dict) -> dict:
        dl = self.lexicon_lemma(t)
        for lem, route in ((dl, "dilemma"), (t["lemma"], "tagger")):
            e = self.index.get(self.key(lem)) if lem else None
            if e:
                n = int(e.get("lsj_sense_count", 0))
                return {"lemma": dl, "headword": e.get("lsj_headword", ""), "entry_id": "", "senses": n, "route": route,
                        "tier": "thin" if n <= self.thin_max else "rich"}
        return {"lemma": dl, "headword": "", "entry_id": "", "senses": 0, "route": "", "tier": "absent"}

    def is_proper(self, t: dict) -> bool:
        return self.lexicon_lemma(t)[:1].isupper()


class LSLexicon:
    name = "ls"
    source = "Perseus Lewis & Short, data/latin_feasibility/lat.ls.perseus-eng2.xml (CC BY-SA 4.0); key = lsgold.latnorm.key"

    def __init__(self, thin_max: int):
        from lsgold.latnorm import key as lkey  # noqa: E402

        self.key = lkey
        self.xml = GDM / "data" / "latin_feasibility" / "lat.ls.perseus-eng2.xml"
        self.index = ls_index(self.xml)
        self.thin_max = thin_max
        self.version = "Lewis & Short perseus-eng2"

    def resolve(self, t: dict) -> dict:
        col = t.get("collatinus") or {}
        tries = [(t["lemma"], "tagger"), (col.get("first", ""), "collatinus_first")]
        present = [k for k in col.get("all", []) if k in self.index]
        if len(present) == 1:
            tries.append((present[0], "collatinus_unique"))
        for lem, route in tries:
            e = self.index.get(self.key(lem)) if lem else None
            if e:
                n = int(e["senses"])
                return {"lemma": re.sub(r"\d+$", "", e["key"]), "headword": e["headword"], "entry_id": e["id"], "senses": n, "route": route,
                        "tier": "thin" if n <= self.thin_max else "rich"}
        return {"lemma": t["lemma"], "headword": "", "entry_id": "", "senses": 0, "route": "", "tier": "absent"}

    def is_proper(self, t: dict) -> bool:
        """LatinCy lowercases most proper-adjective lemmas (Phocaeus -> 'phocaeus'), so a name is also: an L&S headword
        that is capitalised (Thăsus, Bȳzantĭum), or a capitalised surface that does not start a sentence."""
        return (t["lemma"][:1].isupper() or t["pos"] == "PROPN" or (t.get("lex") or {}).get("headword", "")[:1].isupper()
                or (t["surface"][:1].isupper() and not t.get("sent_initial", True)))


# ------------------------------------------------------------------ reference frequency (lexicon_rarity rule)
def reference_counts(cfg: dict) -> tuple[Counter, str]:
    """Lemma counts of a reference corpus lemmatized by the same tagger family, keyed like the lexicon lookup."""
    fcfg = cfg["targets"].get("freq") or {}
    if cfg["lang"] == "grc":
        from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

        path = GDM / fcfg.get("path", "outputs/lemma_frequency_reference.json")
        d = json.loads(path.read_text(encoding="utf-8"))
        c: Counter = Counter()
        for lem, r in d["lemmas"].items():
            k = lemma_to_lookup_key(lem)
            if k:
                c[k] += int(r["raw_count"])
        return c, f"{path.relative_to(GDM).as_posix()} (odyCy over the reference corpus, {d.get('files')} files, {d.get('corpus_total_tokens')} tokens)"
    from lsgold.latnorm import key as lkey  # noqa: E402

    src = GDM / fcfg.get("dir", "data/latin_corpus/caches/latincy_lg")
    excl = fcfg.get("exclude_prefix", "")
    tag = re.sub(r"[^A-Za-z0-9.]+", "_", f"{src.name}_excl-{excl or 'none'}")
    cache = CACHE / f"freq_lat_{tag}.json"
    files = sorted(p for p in src.glob("*.jsonl") if not (excl and p.name.startswith(excl)))
    stamp = [f"{p.name}:{p.stat().st_size}" for p in files]
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("_files") == stamp:
            return Counter(d["counts"]), d["_desc"]
    c = Counter()
    for p in files:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                k = lkey(json.loads(line).get("lemma", ""))
                if k:
                    c[k] += 1
    desc = f"LatinCy la_core_web_lg caches {src.relative_to(GDM).as_posix()} ({len(files)} editions, {sum(c.values())} tokens; excluded prefix '{excl}')"
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"_files": stamp, "_desc": desc, "counts": c}, ensure_ascii=False), encoding="utf-8")
    return c, desc


# ------------------------------------------------------------------ stage 5: targets
GALEN_COLUMNS = ["unit_id", "target_no", "surface", "surface_clean", "odycy_lemma", "dilemma_lemma", "pos", "punch_tier", "tier_v3", "fourway", "class", "page"]
GENERIC_EXTRA = ["lex_headword", "lex_entry_id", "lex_senses", "lex_route", "ref_count"]


class GalenRule:
    """units.py's target rule, unchanged (needs the Galen punch list, v3 tiers and four-way classification)."""

    def __init__(self, cfg: dict):
        from dilemma import Dilemma  # type: ignore

        o = GDM / "outputs"
        self.punch = {nfc(r["lemma"]): r["lsj_tier"] for r in csv.DictReader((o / "punch_list.csv").open(encoding="utf-8"))}
        self.v3 = {nfc(r["lemma"]): r["tier_v3"] for r in csv.DictReader((o / "phase3" / "punch_list_v3.csv").open(encoding="utf-8"))}
        self.fourway, self.whole_freq = {}, {}
        for r in csv.DictReader((o / "four_way_classification.csv").open(encoding="utf-8")):
            self.fourway[nfc(r["lemma"])] = r["quadrant"]
            self.whole_freq[nfc(r["lemma"])] = int(r.get("wholegalen_raw") or 0)
        self.dil = Dilemma(lang="grc", convention="lsj")
        self.memo: dict[str, str] = {}
        self.pos = set(cfg["targets"]["pos"])
        self.cap = int(cfg["targets"]["cap"])
        self.columns = GALEN_COLUMNS
        self.version = __import__("dilemma").__version__

    def dlem(self, surface: str) -> str:
        s = strip_punct(surface)
        if s not in self.memo:
            try:
                self.memo[s] = nfc(self.dil.lemmatize(s, guess=True) or "")
            except Exception:
                self.memo[s] = ""
        return self.memo[s]

    def density_hits(self, wds: list[dict]) -> tuple[int, Counter]:
        hits = [t for t in wds if t["pos"] in self.pos and t["lemma"] in self.punch]
        return len(hits), Counter(self.punch[t["lemma"]] for t in hits)

    def select(self, uid: str, wds: list[dict]) -> list[dict]:
        cands = []
        for j, t in enumerate(wds):
            if t["pos"] not in self.pos:
                continue
            cls = []
            if t["lemma"] in self.punch:
                cls.append(f"punch:{self.punch[t['lemma']]}")
            if self.fourway.get(t["lemma"]) == "genuinely_hard":
                cls.append("fourway:genuinely_hard")
            if t["head"] or self.dlem(t["surface"])[:1].isupper():
                continue
            if cls:
                cands.append((0 if t["lemma"] in self.punch else 1, self.whole_freq.get(t["lemma"], 10**9), j, t, cls))
        cands.sort(key=lambda c: (c[0], c[1], c[2]))
        rows, seen = [], set()
        for _, _, j, t, cls in cands:
            if t["lemma"] in seen or len(rows) >= self.cap:
                continue
            seen.add(t["lemma"])
            rows.append({"unit_id": uid, "target_no": j, "surface": t["surface"], "surface_clean": strip_punct(t["surface"]),
                         "odycy_lemma": t["lemma"], "dilemma_lemma": self.dlem(t["surface"]), "pos": t["pos"],
                         "punch_tier": self.punch.get(t["lemma"], ""), "tier_v3": self.v3.get(t["lemma"], ""), "fourway": self.fourway.get(t["lemma"], ""),
                         "class": "+".join(cls), "page": t["page"]})
        rows.sort(key=lambda r: r["target_no"])
        return rows


class RarityRule:
    """Lexicon-rarity rule for any text (see module docstring). Column names are units.py's: odycy_lemma = the tagger's
    lemma, dilemma_lemma = the lexicon-convention lemma, punch_tier = the lexicon tier when thin/absent."""

    RANK = {"thin": 0, "rich": 1, "absent": 2}

    def __init__(self, cfg: dict):
        t = cfg["targets"]
        thin = int(t["thin_max_senses"])
        self.lex = LSJLexicon(thin) if cfg["lexicon"]["name"] == "lsj" else LSLexicon(thin)
        self.counts, self.freq_source = reference_counts(cfg)
        self.top_n = int(t["freq_top_n"])
        self.top = {k for k, _ in self.counts.most_common(self.top_n)}
        self.freq_class = f"freq:outside_top{self.top_n}"
        self.pos = set(t["pos"])
        self.cap = int(t["cap"])
        self.script = re.compile(SCRIPT_RE[cfg["lang"]])
        self.columns = GALEN_COLUMNS + GENERIC_EXTRA
        self.version = self.lex.version
        self.coverage = Counter()

    def fkey(self, lemma: str) -> str:
        return self.lex.key(lemma) if lemma else ""

    def candidate(self, t: dict) -> dict | None:
        """The token's lexicon resolution and classes when it is eligible (NOUN/ADJ, script, not head, not a proper
        name, lemma outside the reference top-N), else None."""
        if t["pos"] not in self.pos or t["head"] or not self.script.search(strip_punct(t["surface"])):
            return None
        if "lex" not in t:
            t["lex"] = self.lex.resolve(t)
            self.coverage[t["lex"]["tier"]] += 1
        if self.lex.is_proper(t):
            return None
        # both lemmas are tried: a tagger that returns an inflected form as the lemma (odyCy 'παραδείγματός') must not
        # make a common word look rare, so the word is common if EITHER lemma is in the top-N
        keys = [k for k in (self.fkey(t["lex"]["lemma"]), self.fkey(t["lemma"])) if k]
        if not keys or any(k in self.top for k in keys):
            return None
        cls = [self.freq_class] + ([f"lex:{t['lex']['tier']}"] if t["lex"]["tier"] in {"thin", "absent"} else [])
        return {"cls": cls, "ref_count": max(self.counts.get(k, 0) for k in keys), "key": keys[0]}

    def density_hits(self, wds: list[dict]) -> tuple[int, Counter]:
        tiers = Counter()
        for t in wds:
            c = self.candidate(t)
            if c and t["lex"]["tier"] in {"thin", "absent"}:
                tiers[t["lex"]["tier"]] += 1
        return sum(tiers.values()), tiers

    def select(self, uid: str, wds: list[dict]) -> list[dict]:
        cands = []
        for j, t in enumerate(wds):
            c = self.candidate(t)
            if c:
                cands.append((self.RANK[t["lex"]["tier"]], c["ref_count"], j, t, c))
        cands.sort(key=lambda x: (x[0], x[1], x[2]))
        rows, seen = [], set()
        for _, _, j, t, c in cands:
            if c["key"] in seen or len(rows) >= self.cap:
                continue
            seen.add(c["key"])
            lx = t["lex"]
            rows.append({"unit_id": uid, "target_no": j, "surface": t["surface"], "surface_clean": strip_punct(t["surface"]),
                         "odycy_lemma": t["lemma"], "dilemma_lemma": lx["lemma"], "pos": t["pos"],
                         "punch_tier": lx["tier"] if lx["tier"] in {"thin", "absent"} else "", "tier_v3": "", "fourway": "",
                         "class": "+".join(c["cls"]), "page": t["page"],
                         "lex_headword": lx["headword"], "lex_entry_id": lx["entry_id"], "lex_senses": lx["senses"], "lex_route": lx["route"],
                         "ref_count": c["ref_count"]})
        rows.sort(key=lambda r: r["target_no"])
        return rows


# ------------------------------------------------------------------ driver
def build(cfg: dict) -> dict:
    """Run stages 1-5; returns {"units", "targets", "meta", "front_end", "stream", "columns"} (nothing written)."""
    u = cfg["unit"]
    tei = GDM / cfg["tei"]
    toks = tei_tokens(tei, cfg)
    words = [t for t in toks if not t.get("pb")]
    is_end, prev_end = sentence_end_fn(u), True
    for t in words:   # sentence-initial flag (used by the Latin proper-name filter)
        t["sent_initial"], prev_end = prev_end, is_end(t["surface"])
    boundaries = unit_boundaries(toks, u)
    keep = u.get("keep")
    keep_vals = set(keep["values"]) if keep else None

    tname = cfg["tagger"]["name"]
    if tname == "odycy_precomputed":
        tag = tag_odycy_precomputed(words, cfg["tagger"])
    elif tname == "latincy":
        wanted = [True if not keep else t.get(keep["level"]) in keep_vals for t in words]   # tag only the kept books
        tag = tag_latincy(words, cfg["tagger"], wanted)
    else:
        raise SystemExit(f"unknown tagger {tname}")

    rule = GalenRule(cfg) if cfg["targets"]["rule"] == "galen" else RarityRule(cfg)
    ident, loc = u["id"], u["locus"]
    units, targets = [], []
    for k in range(len(boundaries) - 1):
        seg = toks[boundaries[k]:boundaries[k + 1]]
        wds = [t for t in seg if not t.get("pb")]
        pages = _ordered([t["page"] for t in seg], u["ref_sort"])
        chapters = _ordered([t["chapter"] for t in seg], u["chapter_sort"])
        books = _ordered([t.get("book") for t in seg], u["book_sort"])
        if not pages:
            pages = [chapters[0] if chapters else str(k + 1)]
        uid = f"{ident['prefix']}{pages[0]}" + (f"{ident['range']}{pages[-1]}" if len(pages) > 1 else "")
        while any(x["unit_id"] == uid for x in units):
            uid += "x"
        n_tok = len(wds)
        n_hits, tiers = rule.density_hits(wds)
        tgt_rows = rule.select(uid, wds)
        targets += tgt_rows
        ody_idx = [t["ody_i"] for t in wds if t["ody_i"] is not None]
        rec = {"unit_id": uid, "work": cfg["slug"], "urn": cfg["urn"], **u.get("extra", {}), "pages": pages, "books": books,
               "locus": f"{loc['prefix']}{pages[0]}" + (f"{loc['range']}{pages[-1]}" if len(pages) > 1 else ""),
               "chapters": chapters, "n_tokens": n_tok, "n_words_for_cost": n_tok,
               "greek": " ".join(t["surface"] for t in seg), "greek_plain": " ".join(t["surface"] for t in wds),
               "odycy_start": min(ody_idx) if ody_idx else None, "odycy_end": max(ody_idx) if ody_idx else None,
               "odycy_aligned_share": round(len(ody_idx) / n_tok, 3) if n_tok else 0,
               "punch_density_per100": round(100 * n_hits / n_tok, 2) if n_tok else 0.0,
               "n_punch_thin": tiers.get("thin", 0), "n_punch_absent": tiers.get("absent", 0),
               "n_content_tokens": sum(1 for t in wds if t["pos"] in CONTENT_POS),
               "n_targets": len(tgt_rows), "has_head": any(t["head"] for t in wds)}
        units.append(rec)
    if keep:
        lvl = {"book": "books", "chapter": "chapters"}.get(keep["level"], keep["level"])
        kept = {x["unit_id"] for x in units if x[lvl] and set(x[lvl]) <= keep_vals}
        units = [x for x in units if x["unit_id"] in kept]
        targets = [r for r in targets if r["unit_id"] in kept]

    stream = None
    if tname == "latincy":   # the tagger stream, cut to the kept units and renumbered so odycy_start/end index it
        lo = min(x["odycy_start"] for x in units if x["odycy_start"] is not None)
        hi = max(x["odycy_end"] for x in units if x["odycy_end"] is not None)
        stream = [{"i": t["ody_i"] - lo, "surface": strip_punct(t["surface"]), "lemma": t["lemma"], "pos": t["pos"],
                   "lex_lemma": (t.get("lex") or {}).get("lemma", "")} for t in words if t["ody_i"] is not None and lo <= t["ody_i"] <= hi]
        for x in units:
            if x["odycy_start"] is not None:
                x["odycy_start"] -= lo
                x["odycy_end"] -= lo

    dens = sorted(x["punch_density_per100"] for x in units)
    t1, t2 = dens[len(dens) // 3], dens[2 * len(dens) // 3]
    for x in units:
        x["difficulty_tier"] = "low" if x["punch_density_per100"] <= t1 else ("mid" if x["punch_density_per100"] <= t2 else "high")

    meta = {"work": cfg["slug"], "urn": cfg["urn"], "source": cfg["source_note"], "n_units": len(units), "n_tei_words": len(words),
            "n_odycy_tokens": tag["n_stream_tokens"], "alignment_loss": tag["alignment_loss"], "n_targets": len(targets),
            "targets_by_class": dict(Counter(t["class"] for t in targets)), "density_terciles": [t1, t2],
            "units_per_tier": dict(Counter(x["difficulty_tier"] for x in units)),
            "n_books": len({b for x in units for b in x["books"]}), "n_chapters": len({c for x in units for c in x["chapters"]}),
            "pages_per_unit": dict(Counter(len(x["pages"]) for x in units)), "dilemma_version": rule.version}
    if cfg["profile"] != "galen":   # generic additions (a Galen config keeps units.py's meta exactly)
        meta.pop("dilemma_version")
        meta.update({"lang": cfg["lang"], "tagger": tname, "tagger_stream": tag["stream"], "lexicon": rule.lex.source if hasattr(rule, "lex") else "",
                     "lexicon_version": rule.version, "target_rule": cfg["targets"]["rule"],
                     "n_drafted_words": sum(x["n_tokens"] for x in units)})
        if isinstance(rule, RarityRule):
            meta.update({"reference_frequency": rule.freq_source, "freq_top_n": rule.top_n,
                         "freq_top_n_cutoff_count": rule.counts.most_common(rule.top_n)[-1][1] if rule.counts else None,
                         "lexicon_tier_of_noun_adj_tokens": dict(rule.coverage)})
    fe = {"front_end": "pipeline/firstdrafts/generic.py", "config": cfg, "config_sha256": sha256(json.dumps(cfg, sort_keys=True, ensure_ascii=False)),
          "tei_sha256": __import__("hashlib").sha256(tei.read_bytes()).hexdigest(), "tagger": tname, "tagger_versions": tag.get("versions"),
          "lexicon_version": rule.version, "n_drafted_words": sum(x["n_tokens"] for x in units)}
    if cfg["lang"] != "grc":
        w = fe["n_drafted_words"]
        fe["cost_projection_usd"] = {"rate": "~$1.80 per 1,000 source words, ±2x, measured on the Galen cycles",
                                     "point": round(w / 1000 * 1.80, 2), "low": round(w / 1000 * 0.90, 2), "high": round(w / 1000 * 3.60, 2)}
    return {"units": units, "targets": targets, "meta": meta, "front_end": fe, "stream": stream, "columns": rule.columns}


def write(res: dict, out: Path, cfg: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "units.jsonl", res["units"])
    with (out / "targets.csv").open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=res["columns"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(res["targets"])
    (out / "units_meta.json").write_text(json.dumps(res["meta"], indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "front_end.json").write_text(json.dumps(res["front_end"], indent=1, ensure_ascii=False), encoding="utf-8")
    if res["stream"] is not None:
        write_jsonl(out / "tagged.jsonl", res["stream"])
    if cfg["lang"] == "grc":
        from units import write_estimate  # noqa: E402

        write_estimate(out, res["units"], res["targets"])


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--config", help="work config JSON (see configs/)")
    g.add_argument("--work", help="a Galen work slug in common.WORKS (config built by galen_config)")
    ap.add_argument("--out", help="output root (default FIRSTDRAFTS_OUT or outputs/firstdrafts); files go to <out>/<slug>/")
    ap.add_argument("--targets-rule", choices=["galen", "lexicon_rarity"], help="override the config's target rule")
    ap.add_argument("--overwrite", action="store_true", help="allow writing over an existing published units.jsonl")
    a = ap.parse_args()
    cfg = galen_config(a.work) if a.work else load_config(Path(a.config))
    if a.targets_rule and a.targets_rule != cfg["targets"]["rule"]:
        cfg["targets"] = {**DEFAULT_TARGETS, **{k: v for k, v in cfg["targets"].items() if k in ("pos", "cap")}, "rule": a.targets_rule}
        cfg["profile"] = "generic"
    root = Path(a.out).resolve() if a.out else (Path(os.environ["FIRSTDRAFTS_OUT"]) if os.environ.get("FIRSTDRAFTS_OUT") else GDM / "outputs" / "firstdrafts")
    out = root / cfg["slug"]
    if (out / "units.jsonl").exists() and root.resolve() == (GDM / "outputs" / "firstdrafts").resolve() and not a.overwrite:
        raise SystemExit(f"{out} already has units.jsonl (a published or running work); use --out <scratch> or --overwrite")
    res = build(cfg)
    write(res, out, cfg)
    print(json.dumps(res["meta"], indent=1, ensure_ascii=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
