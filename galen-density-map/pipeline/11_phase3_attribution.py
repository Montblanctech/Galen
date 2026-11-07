#!/usr/bin/env python3
"""Phase 3 v0: the attributed punch list (compile and attribute, never adjudicate).

One row per lemma in ``outputs/punch_list.csv``. Every cell names its source
(see ``outputs/phase3/README_phase3_v0.md``). Report-only: reads frozen
``data/lemmatized/**``, ``data/lsj``, ``data/qc/h3m/**``, ``data/raw_xml`` and
Phase 2 ``outputs/*``; writes only under ``outputs/phase3/``.

Stdlib + already-pinned deps (lxml, beta-code, PyYAML). No network, no model calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))

import beta_code  # pinned in requirements.txt

from h3m.kuhn_index import (KUHN_PAGE_RE, PB_INT_RE, NS, _choose_volume, _edition_roots, _local as _tei_local,
                            _should_skip, parse_kuhn_ranges)
from lib.greek_normalize import normalize_extracted_text, TOKEN_RE
from h3m.kuhn_ref import GAL_IN_TEXT_RE
from h3m.lemma_eq import analyses_have_lemma, surface_nfc
from lib.beta_keys import betacode_headword_to_unicode, lemma_to_lookup_key, normalize_betacode_key
from lib.config import load_config, project_root, resolve_path
from lib.greek_normalize import casefold_greek, nfc
from lib.io_utils import ensure_dir, read_json, write_json

SCRIPT_VERSION = "phase3_v0 (2026-11-05)"
SANITY_SEED = 20261105
CONTEXT = 6          # KWIC ±6 tokens
COLLOC_WINDOW = 3    # collocates ±3 tokens
COLLOC_TOP = 8
COLLOC_POS = {"NOUN", "ADJ", "VERB"}
KWIC_MAX = 12
KUHN_MAX = 10
LSJ_TEXT_MAX = 600
ALIGN_LOOKAHEAD = 40
ALIGN_BACK = 3

# --- Tradition columns: attribution by URN textgroup prefix ONLY (spec §rules). ---
# The spec's TLG numbers were checked against data/reference_corpus/_first1k_catalog.json
# (group_name / work_name per URN). Resolved on disk:
#   tlg0627 Hippocrates              -> present (53 editions)
#   tlg0656 Dioscorides Pedanius     -> present (De materia medica; Περὶ ἁπλῶν φαρμάκων).
#        The spec wrote tlg0094; in First1K tlg0094 is Pseudo-Plutarch, De fluviis, so
#        0094 is NOT used. Dioscorides is counted from tlg0656.
#   tlg0722 Oribasius, tlg0718 Aetius, tlg0719 Aretaeus -> not in the reference set.
#   tlg0565 is Soranus in First1K (not Paulus Aegineta, whose TLG number is 0715; not on
#        disk). tradition_paulus is therefore empty and Soranus counts as other_medical.
TRADITION_PREFIX = {
    "tradition_hippocrates": "tlg0627",
    "tradition_dioscorides": "tlg0656",
    "tradition_oribasius": "tlg0722",
    "tradition_aetius": "tlg0718",
    "tradition_paulus": "tlg0715",
    "tradition_aretaeus": "tlg0719",
}
# Other medical authors in the frozen reference set, by URN prefix. Nothing on disk marks
# reference authors as medical (data/stoplists/authors.txt is a name stoplist; the census
# covers Galen only), so this list is the auditable marking; group/work names are the
# First1K catalog's.
OTHER_MEDICAL_PREFIX = {
    "tlg0565": "Soranus (Gynaecia; De signis fracturarum; De fasciis; Vita Hippocratis)",
    "tlg0564": "Rufus of Ephesus (De renum et vesicae affectionibus)",
    "tlg0530": "Pseudo-Galen (De fasciis; Ad Gaurum; Introductio seu medicus; De remediis parabilibus; De theriaca ad Pamphilianum; De optima secta)",
    "tlg0643": "Anonymus Londinensis (Iatrica + fragmenta)",
    "tlg0657": "Crateuas (fragmenta)",
    "tlg0671": "Philumenus (De venenatis animalibus)",
    "tlg0733": "Cassius Iatrosophista (Quaestiones medicae)",
    "tlg0751": "pseudo-Hippocrates (De septimestri partu; Hermeneia peri energon lithon)",
    "tlg1118": "Pseudo-Dioscorides (De lapidibus)",
    "tlg0022": "Nicander (Theriaca; Alexipharmaca)",
}
TRADITION_COLS = list(TRADITION_PREFIX) + ["tradition_other_medical", "tradition_nonmedical"]

GREEK_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")
NON_GREEK_RE = re.compile(r"[^Ͱ-Ͽἀ-῿]+")
XML_PARSER = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
LEMMA_FAST_RE = re.compile(r'"lemma": "([^"]*)"')


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def stem_to_urn(stem: str) -> str:
    if stem.startswith("urn_cts_"):
        after = stem[len("urn_cts_"):]
        if "_" in after:
            lit, rest = after.split("_", 1)
            return f"urn:cts:{lit}:{rest}"
    return stem


def urn_prefix(stem: str) -> str:
    """Textgroup prefix (tlg0627) from a safe-filename stem; URN only, no name heuristic."""
    urn = stem_to_urn(stem)
    try:
        return urn.split(":")[3].split(".")[0]
    except IndexError:
        return ""


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def clean_greek(token: str) -> str:
    return NON_GREEK_RE.sub("", nfc(token or ""))


# ---------------------------------------------------------------------------
# Kühn (volume, page) map: reuse pipeline/h3m/kuhn_index.extract_pages_from_tei
# ---------------------------------------------------------------------------

def kuhn_token_stream(xml_path: Path) -> list[tuple[tuple[int, int] | None, str]]:
    """Document-order token stream labelled with the current Kühn (vol, page).

    Mirrors pipeline/h3m/kuhn_index.extract_pages_from_tei (same header volume ranges,
    same <pb n>/milestone handling, same element drops, same Stage-02 normalization) but
    keeps DOCUMENT order instead of sorted (vol, page) order, which is what a monotone
    alignment against the lemmatized token stream needs. Tokens before the first page
    marker carry label None. Returns [] if the edition has no Kühn page markers."""
    tree = etree.parse(str(xml_path), XML_PARSER)
    is_kuhn, ranges = parse_kuhn_ranges(tree)
    if not is_kuhn and not tree.xpath('.//tei:milestone[@unit="Kühn_page"]', namespaces=NS):
        return []
    state = {"vol": ranges[0].volume if ranges else None, "page": None, "any": False}
    chunks: list[tuple[tuple[int, int] | None, str]] = []

    def label() -> tuple[int, int] | None:
        if state["vol"] is None or state["page"] is None:
            return None
        return (state["vol"], state["page"])

    def flush(text: str) -> None:
        if text and text.strip():
            chunks.append((label(), text))

    def handle_pb(el: etree._Element) -> None:
        local = _tei_local(el.tag)
        if local == "milestone":
            unit = el.get("unit") or ""
            if unit == "Kühn_page" or "kuhn" in unit.lower():
                m = KUHN_PAGE_RE.search(el.get("n") or "")
                if m:
                    state["vol"] = int(m.group("vol"))
                    state["page"] = int(m.group("page"))
                    state["any"] = True
            return
        n_attr = (el.get("n") or "").strip()
        if not PB_INT_RE.match(n_attr):
            return
        n = int(n_attr)
        state["vol"] = _choose_volume(n, ranges, state["vol"])
        state["page"] = n
        state["any"] = True

    def walk(el: etree._Element) -> None:
        local = _tei_local(el.tag)
        if local in {"pb", "milestone"}:
            handle_pb(el)
        if _should_skip(el):
            if el.tail:
                flush(el.tail)
            return
        if el.text and local not in {"pb", "milestone"}:
            flush(el.text)
        for child in el:
            walk(child)
        if el.tail:
            flush(el.tail)

    for node in _edition_roots(tree):
        walk(node)
    if not state["any"]:
        return []
    # Join contiguous same-page text nodes with "" exactly as Stage 02 does, so a word
    # broken by <lb/> or another inline element stays one token.
    runs: list[tuple[tuple[int, int] | None, list[str]]] = []
    for lab, raw in chunks:
        if lab is not None and (lab[0] is None or lab[0] <= 0 or lab[1] <= 0):
            lab = None
        if runs and runs[-1][0] == lab:
            runs[-1][1].append(raw)
        else:
            runs.append((lab, [raw]))
    stream: list[tuple[tuple[int, int] | None, str]] = []
    for lab, parts in runs:
        text, _stats = normalize_extracted_text("".join(parts))
        for tok in TOKEN_RE.findall(text):
            c = clean_greek(tok)
            if c:
                stream.append((lab, c))
    return stream


def build_kuhn_page_streams(raw_xml: Path, stems: set[str]) -> dict[str, list[tuple[tuple[int, int] | None, str]]]:
    """stem -> document-ordered page-token stream [((vol, page) | None, clean_token), ...]."""
    streams: dict[str, list[tuple[tuple[int, int] | None, str]]] = {}
    for stem in sorted(stems):
        xml_path = raw_xml / f"{stem}.xml"
        if not xml_path.exists():
            continue
        try:
            stream = kuhn_token_stream(xml_path)
        except Exception as exc:  # report, never abort
            print(f"  WARN Kühn page extraction failed for {stem}: {exc}", flush=True)
            continue
        if stream:
            streams[stem] = stream
    return streams


def align_pages(surfaces: list[str], stream: list[tuple[tuple[int, int] | None, str]]) -> tuple[list[tuple[int, int] | None], int]:
    """Assign a (vol, page) to each lemmatized token by a monotone walk over the page
    token stream (both derive from the same TEI through the same normalization; spaCy
    splits punctuation and crasis off, so compare Greek letters only and allow a surface
    to match inside a stream token). A forward jump of more than 2 stream tokens must be
    confirmed by the next surface matching the next stream token, so a word the stream
    has split (page break inside a word) cannot ratchet the pointer ahead. Returns
    (pages, n_matched)."""
    n = len(stream)
    m = len(surfaces)
    cleaned = [clean_greek(x) for x in surfaces]
    p = 0
    out: list[tuple[int, int] | None] = []
    matched = 0

    def tok_match(c: str, st: str) -> bool:
        return st == c or (len(c) >= 2 and c in st)

    for i, c in enumerate(cleaned):
        hit = -1
        if c:
            start = max(0, p - ALIGN_BACK)
            limit = min(n, p + ALIGN_LOOKAHEAD)
            for k in range(start, limit):
                if not tok_match(c, stream[k][1]):
                    continue
                if k - p <= 2:
                    hit = k
                    break
                nxt = cleaned[i + 1] if i + 1 < m else ""
                if not nxt or (k + 1 < n and tok_match(nxt, stream[k + 1][1])):
                    hit = k
                    break
        if hit >= 0:
            p = hit
            matched += 1
            out.append(stream[hit][0])
        else:
            out.append(stream[p][0] if p < n else None)
    return out, matched


# ---------------------------------------------------------------------------
# LSJ: Perseus XML (Beta Code headwords) → headword, sense count, plain text, Gal. cite
# ---------------------------------------------------------------------------

def _entry_plain_text(entry: etree._Element) -> str:
    """Entry text with Beta Code Greek (lang=greek nodes) rendered as Unicode."""
    parts: list[str] = []

    def walk(el: etree._Element) -> None:
        lang = (el.get("lang") or "").lower()
        is_greek = lang in {"greek", "grc"}
        if el.text:
            parts.append(_beta_or_text(el.text) if is_greek else el.text)
        for child in el:
            walk(child)
            if child.tail:
                parts.append(_beta_or_text(child.tail) if is_greek else child.tail)

    walk(entry)
    text = "".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return nfc(text)


def _beta_or_text(s: str) -> str:
    if not s or GREEK_RE.search(s):
        return s
    s = s.replace("^", "").replace("_", "")  # Beta Code long/short vowel marks
    try:
        return beta_code.beta_code_to_greek(s)
    except Exception:
        return s


def _entry_cites_galen(entry: etree._Element) -> bool:
    for bibl in entry.xpath(".//*[local-name()='bibl']"):
        for a in bibl.xpath(".//*[local-name()='author']"):
            t = (a.text or "").strip().rstrip(".").lower()
            if t in {"gal", "galen", "galenus"}:
                return True
        if re.match(r"Gal\.?\s*\d", bibl.get("n") or "", re.I):
            return True
    blob = " ".join(entry.itertext())
    return bool(GAL_IN_TEXT_RE.search(blob))


def scan_lsj(lsj_dir: Path, wanted_keys: set[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Same selection rule as 06_lsj_crossref.build_lsj_index (key attr + orth forms;
    on key collision keep the entry with the most <sense>), restricted to wanted keys."""
    parts = sorted(lsj_dir.glob("grc.lsj.perseus-eng*.xml"), key=lambda p: int(re.sub(r"\D", "", p.stem.split("eng")[-1]) or 0))
    found: dict[str, dict[str, Any]] = {}
    for path in parts:
        tree = etree.parse(str(path), XML_PARSER)
        entries = tree.xpath("//*[local-name()='entryFree'] | //*[local-name()='entry']")
        for entry in entries:
            key_attr = entry.get("key") or ""
            headwords = [key_attr] if key_attr else []
            for orth in entry.xpath(".//*[local-name()='orth']"):
                if orth.text:
                    headwords.append(orth.text)
            keys_here: list[tuple[str, str]] = []
            for hw in headwords:
                hw_clean = re.sub(r"\d+$", "", hw)
                norm = normalize_betacode_key(hw_clean)
                if norm and norm in wanted_keys:
                    keys_here.append((norm, hw_clean))
            if not keys_here:
                continue
            sense_count = len(entry.xpath(".//*[local-name()='sense']"))
            rec = None
            for norm, hw_clean in keys_here:
                prev = found.get(norm)
                if prev is None or sense_count > prev["lsj_sense_count"]:
                    if rec is None:
                        rec = {
                            "lsj_sense_count": sense_count,
                            "lsj_entry_text": _entry_plain_text(entry),
                            "lsj_cites_galen": _entry_cites_galen(entry),
                            "lsj_entry_id": entry.get("id") or "",
                            "lsj_part": path.name,
                        }
                    found[norm] = dict(rec, lsj_headword=betacode_headword_to_unicode(hw_clean))
        print(f"  LSJ {path.name}: {len(entries)} entries scanned, {len(found)} punch keys resolved so far", flush=True)
    return found, [p.name for p in parts]


# ---------------------------------------------------------------------------
# Galen medical scan: works, attestations, KWIC, collocate windows, surfaces, pages
# ---------------------------------------------------------------------------

def scan_galen_medical(
    galen_dir: Path,
    punch: set[str],
    page_streams: dict[str, list[tuple[tuple[int, int] | None, str]]],
) -> dict[str, Any]:
    work_counts: dict[str, Counter[str]] = defaultdict(Counter)
    attestations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    colloc: dict[str, Counter[str]] = defaultdict(Counter)
    colloc_window_n: Counter[str] = Counter()
    surfaces: dict[str, set[str]] = defaultdict(set)
    corpus_class_counts: Counter[str] = Counter()
    corpus_class_total = 0
    align_stats = {"editions_with_kuhn_pages": 0, "tokens_aligned": 0, "tokens_total_in_kuhn_editions": 0}
    files = sorted(galen_dir.glob("*.jsonl"))
    print(f"Scanning Galen medical subcorpus: {len(files)} files", flush=True)
    for path in files:
        stem = path.stem
        urn = stem_to_urn(stem)
        rows = list(iter_jsonl(path))
        surfs = [r.get("surface") or "" for r in rows]
        lemmas_cf = [casefold_greek(r.get("lemma") or "") for r in rows]
        poss = [r.get("pos") or "" for r in rows]
        for lem, pos in zip(lemmas_cf, poss):
            if pos in COLLOC_POS and lem:
                corpus_class_counts[lem] += 1
                corpus_class_total += 1
        pages: list[tuple[int, int] | None] | None = None
        stream = page_streams.get(stem)
        if stream:
            pages, n_ok = align_pages(surfs, stream)
            align_stats["editions_with_kuhn_pages"] += 1
            align_stats["tokens_aligned"] += n_ok
            align_stats["tokens_total_in_kuhn_editions"] += len(surfs)
        n = len(rows)
        for i, lem in enumerate(lemmas_cf):
            if lem not in punch:
                continue
            work_counts[lem][urn] += 1
            surfaces[lem].add(surfs[i])
            left = " ".join(s for s in surfs[max(0, i - CONTEXT):i] if s)
            right = " ".join(s for s in surfs[i + 1:i + 1 + CONTEXT] if s)
            att = {
                "work": urn,
                "i": rows[i].get("i", i),
                "surface": surfs[i],
                "pos": poss[i],
                "left": left,
                "right": right,
            }
            if pages is not None:
                pg = pages[i]
                att["kuhn"] = f"{pg[0]}.{pg[1]}" if pg else ""
            attestations[lem].append(att)
            for j in range(max(0, i - COLLOC_WINDOW), min(n, i + COLLOC_WINDOW + 1)):
                if j == i:
                    continue
                if poss[j] in COLLOC_POS and lemmas_cf[j] and lemmas_cf[j] != lem:
                    colloc[lem][lemmas_cf[j]] += 1
                    colloc_window_n[lem] += 1
    return {
        "work_counts": work_counts,
        "attestations": attestations,
        "colloc": colloc,
        "colloc_window_n": colloc_window_n,
        "surfaces": surfaces,
        "corpus_class_counts": corpus_class_counts,
        "corpus_class_total": corpus_class_total,
        "align_stats": align_stats,
        "n_files": len(files),
    }


def log_likelihood(o1: int, n1: int, o2: int, n2: int) -> float:
    if o1 <= 0 or n1 <= 0 or n2 <= 0:
        return 0.0
    tot = o1 + o2
    e1 = n1 * tot / (n1 + n2)
    e2 = n2 * tot / (n1 + n2)
    g2 = 0.0
    if o1 > 0 and e1 > 0:
        g2 += o1 * math.log(o1 / e1)
    if o2 > 0 and e2 > 0:
        g2 += o2 * math.log(o2 / e2)
    g2 *= 2.0
    if (o1 / n1) < (o2 / n2):
        g2 = -g2
    return g2


def top_collocates(counter: Counter[str], n1: int, corpus: Counter[str], n2: int) -> list[tuple[str, int, float]]:
    scored = []
    for lem, o1 in counter.items():
        o2 = corpus.get(lem, 0)
        g2 = log_likelihood(o1, n1, o2, n2)
        if g2 > 0:
            scored.append((lem, o1, round(g2, 2)))
    scored.sort(key=lambda t: (-t[2], -t[1], t[0]))
    return scored[:COLLOC_TOP]


def select_kwic(atts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Up to KWIC_MAX lines, one per distinct work first (in corpus order), then
    further attestations round-robin across works."""
    by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order: list[str] = []
    for a in atts:
        if a["work"] not in by_work:
            order.append(a["work"])
        by_work[a["work"]].append(a)
    chosen: list[dict[str, Any]] = []
    depth = 0
    while len(chosen) < KWIC_MAX:
        added = False
        for w in order:
            lst = by_work[w]
            if depth < len(lst):
                chosen.append(lst[depth])
                added = True
                if len(chosen) >= KWIC_MAX:
                    break
        if not added:
            break
        depth += 1
    return chosen


def fmt_kwic(a: dict[str, Any]) -> str:
    return f"{a['work']}#{a['i']}: {a['left']} [{a['surface']}] {a['right']}".strip()


# ---------------------------------------------------------------------------
# Reference (First1KGreek minus Galen) streaming counts by URN prefix
# ---------------------------------------------------------------------------

def stream_reference_counts(ref_dir: Path, punch: set[str]) -> tuple[dict[str, Counter[str]], dict[str, Any]]:
    """lemma -> Counter(prefix -> token count). Only lemmas in ``punch`` are kept."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    files = sorted(ref_dir.glob("*.jsonl"))
    prefixes: Counter[str] = Counter()
    n_tokens = 0
    t0 = time.time()
    print(f"Streaming reference subcorpus: {len(files)} files", flush=True)
    for k, path in enumerate(files, 1):
        pref = urn_prefix(path.stem)
        prefixes[pref] += 1
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                m = LEMMA_FAST_RE.search(line)
                if m is None:
                    if not line.strip():
                        continue
                    lemma = json.loads(line).get("lemma") or ""
                else:
                    lemma = m.group(1)
                if not lemma:
                    continue
                n_tokens += 1
                lem = casefold_greek(lemma)
                if lem in punch:
                    counts[lem][pref] += 1
        if k % 100 == 0:
            print(f"  {k}/{len(files)} files, {n_tokens} tokens, {time.time() - t0:.0f}s", flush=True)
    return counts, {"files": len(files), "tokens": n_tokens, "prefixes": len(prefixes), "seconds": round(time.time() - t0, 1)}


def count_nonmedical(nonmed_dir: Path, punch: set[str]) -> tuple[Counter[str], dict[str, set[str]], int]:
    counts: Counter[str] = Counter()
    surfaces: dict[str, set[str]] = defaultdict(set)
    files = sorted(nonmed_dir.glob("*.jsonl"))
    print(f"Scanning Galen non-medical subcorpus: {len(files)} files", flush=True)
    for path in files:
        for row in iter_jsonl(path):
            lem = casefold_greek(row.get("lemma") or "")
            if lem in punch:
                counts[lem] += 1
                surfaces[lem].add(row.get("surface") or "")
    return counts, surfaces, len(files)


# ---------------------------------------------------------------------------
# H3-M machine QC (report-only inputs)
# ---------------------------------------------------------------------------

def load_morpheus_cache(path: Path) -> dict[str, list[str]]:
    cache: dict[str, list[str]] = {}
    if not path.exists():
        return cache
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = row.get("surface_nfc") or ""
            if key:
                cache[key] = list(row.get("lemmas") or [])
    return cache


def morpheus_fraction(lemma: str, surfaces: set[str], cache: dict[str, list[str]]) -> dict[str, Any]:
    adm = inadm = none = 0
    for s in surfaces:
        if not s:
            continue
        analyses = cache.get(surface_nfc(s))
        if analyses is None or not analyses:
            none += 1
        elif analyses_have_lemma(lemma, analyses, accent_blind=True):
            adm += 1
        else:
            inadm += 1
    analyzable = adm + inadm
    return {
        "surfaces": len([s for s in surfaces if s]),
        "admissible": adm,
        "inadmissible": inadm,
        "no_analysis": none,
        "fraction": round(adm / analyzable, 4) if analyzable else None,
    }


def load_m1_flags(path: Path) -> dict[str, int]:
    out: Counter[str] = Counter()
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out[casefold_greek(row.get("lemma") or "")] += 1
    return out


def load_m2_flags(path: Path) -> dict[str, int]:
    out: Counter[str] = Counter()
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out[casefold_greek(row.get("lemma_odycy") or "")] += 1
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "lemma", "pos", "galen_raw_count", "galen_per10k", "log_likelihood", "lsj_tier", "quadrant",
    "n_works", "works",
    "kuhn_loci",
    "concordance_n", "concordance",
    "collocates",
    "lsj_headword", "lsj_sense_count", "lsj_entry_text", "lsj_cites_galen",
    *TRADITION_COLS,
    "galen_nonmedical_count",
    "morpheus_admissible",
    "machine_flags",
    "attribution_note",
]


def main() -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    t_start = time.time()

    root = project_root()
    outputs = resolve_path(cfg, "outputs")
    out_dir = ensure_dir(outputs / "phase3")
    lemmatized = resolve_path(cfg, "lemmatized")
    galen_dir = lemmatized / "galen"
    nonmed_dir = resolve_path(cfg, "lemmatized_galen_nonmedical")
    ref_dir = lemmatized / "reference"
    lsj_dir = resolve_path(cfg, "lsj_cache")
    raw_xml = resolve_path(cfg, "raw_xml")
    qc_dir = resolve_path(cfg, "qc")
    h3m_dir = qc_dir / "h3m"

    # 1. Phase 2 inputs (carried)
    punch_rows: list[dict[str, str]] = []
    with (outputs / "punch_list.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            row["lemma"] = casefold_greek(row["lemma"])
            punch_rows.append(row)
    punch = {r["lemma"] for r in punch_rows}
    print(f"Punch list: {len(punch_rows)} rows, {len(punch)} distinct lemmas", flush=True)

    quadrant: dict[str, str] = {}
    with (outputs / "four_way_classification.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            quadrant[casefold_greek(row["lemma"])] = row.get("quadrant") or ""

    ref_freq = read_json(outputs / "lemma_frequency_reference.json")
    nonmed_freq_path = outputs / "lemma_frequency_galen_nonmedical.json"
    nonmed_freq = read_json(nonmed_freq_path)["lemmas"] if nonmed_freq_path.exists() else {}

    # 2. Kühn page streams for the medical editions (reuse h3m.kuhn_index)
    t = time.time()
    medical_stems = {p.stem for p in galen_dir.glob("*.jsonl")}
    page_streams = build_kuhn_page_streams(raw_xml, medical_stems)
    print(f"Kühn page streams: {len(page_streams)}/{len(medical_stems)} medical editions carry page markers ({time.time() - t:.0f}s)", flush=True)

    # 3. Galen medical scan
    t = time.time()
    med = scan_galen_medical(galen_dir, punch, page_streams)
    print(f"Medical scan done ({time.time() - t:.0f}s); align {med['align_stats']}", flush=True)

    # 4. Galen non-medical
    t = time.time()
    nonmed_counts, nonmed_surfaces, nonmed_files = count_nonmedical(nonmed_dir, punch)
    print(f"Non-medical scan done ({time.time() - t:.0f}s)", flush=True)

    # 5. Reference streaming
    ref_counts, ref_stats = stream_reference_counts(ref_dir, punch)
    print(f"Reference streaming done: {ref_stats}", flush=True)
    present_prefixes: set[str] = set()
    for p in ref_dir.glob("*.jsonl"):
        present_prefixes.add(urn_prefix(p.stem))

    # 6. LSJ
    t = time.time()
    wanted_keys = {lemma_to_lookup_key(l) for l in punch}
    lsj, lsj_parts = scan_lsj(lsj_dir, wanted_keys)
    print(f"LSJ scan done: {len(lsj)} keys resolved of {len(wanted_keys)} ({time.time() - t:.0f}s)", flush=True)
    lsj_index_cached = read_json(lsj_dir / "_lsj_index.json") if (lsj_dir / "_lsj_index.json").exists() else {}

    # 7. H3-M machine QC inputs
    morph_cache = load_morpheus_cache(h3m_dir / "cache" / "morpheus_by_surface.jsonl")
    m1 = load_m1_flags(h3m_dir / "m1_inadmissible.csv")
    m2 = load_m2_flags(h3m_dir / "m2_disagreements.csv")
    print(f"Morpheus cache: {len(morph_cache)} surfaces; M1 flagged lemmas {len(m1)}; M2 flagged lemmas {len(m2)}", flush=True)

    # 8. Assemble rows
    csv_rows: list[dict[str, Any]] = []
    jsonl_rows: list[dict[str, Any]] = []
    counts = Counter()
    sense_mismatch: list[str] = []
    work_sum_mismatch: list[str] = []
    for prow in punch_rows:
        lem = prow["lemma"]
        tier = prow.get("lsj_tier") or ""
        note: list[str] = []
        wc = med["work_counts"].get(lem, Counter())
        works_sorted = wc.most_common()
        n_works = len(works_sorted)
        if sum(wc.values()) != int(prow.get("galen_raw_count") or 0):
            work_sum_mismatch.append(lem)
        atts = med["attestations"].get(lem, [])
        kwic = select_kwic(atts)
        loci_by_work: dict[str, list[str]] = defaultdict(list)
        seen = set()
        for a in atts:
            k = a.get("kuhn")
            if k and (a["work"], k) not in seen:
                seen.add((a["work"], k))
                loci_by_work[a["work"]].append(k)
        for lst in loci_by_work.values():
            lst.sort(key=lambda s: tuple(int(x) for x in s.split(".")))
        loci_all = sorted({k for _w, k in seen}, key=lambda s: tuple(int(x) for x in s.split(".")))
        # CSV shows up to KUHN_MAX loci spread across works: round-robin over the works in
        # descending token-count order, lowest page first within each work.
        loci_sorted: list[str] = []
        depth = 0
        while len(loci_sorted) < len(loci_all):
            added = False
            for w, _c in works_sorted:
                lst = loci_by_work.get(w) or []
                if depth < len(lst) and lst[depth] not in loci_sorted:
                    loci_sorted.append(lst[depth])
                    added = True
            if not added:
                break
            depth += 1
        col = top_collocates(med["colloc"].get(lem, Counter()), med["colloc_window_n"].get(lem, 0),
                             med["corpus_class_counts"], med["corpus_class_total"])
        entry = lsj.get(lemma_to_lookup_key(lem))
        rc = ref_counts.get(lem, Counter())
        trad: dict[str, Any] = {}
        for colname, pref in TRADITION_PREFIX.items():
            trad[colname] = rc.get(pref, 0) if pref in present_prefixes else None
        other_med = sum(v for p, v in rc.items() if p in OTHER_MEDICAL_PREFIX)
        named = set(TRADITION_PREFIX.values())
        nonmed_ref = sum(v for p, v in rc.items() if p not in OTHER_MEDICAL_PREFIX and p not in named)
        trad["tradition_other_medical"] = other_med
        trad["tradition_nonmedical"] = nonmed_ref
        ref_total = sum(rc.values())
        surfaces = set(med["surfaces"].get(lem, set())) | set(nonmed_surfaces.get(lem, set()))
        morph = morpheus_fraction(lem, surfaces, morph_cache)
        flags: list[str] = []
        if m1.get(lem):
            flags.append("m1_inadmissible")
        if m2.get(lem):
            flags.append("m2_disagreement")
        if tier == "absent":
            flags.append("hallucination_screen_pass")

        # attribution note: exactly which sources were available for this lemma
        note.append(f"galen_medical:{n_works} works/{sum(wc.values())} tokens (frozen odyCy JSONL)")
        note.append(f"kuhn_loci:{len(loci_all)} distinct pages" if loci_all else "kuhn_loci:none (no page markers in attesting editions)")
        note.append(f"collocates:{'yes' if col else 'none'}")
        if entry:
            note.append(f"lsj:{entry['lsj_part']}#{entry['lsj_entry_id']}")
            if int(prow.get("lsj_sense_count") or 0) != entry["lsj_sense_count"]:
                sense_mismatch.append(lem)
                note.append(f"lsj_sense_count differs from Phase 2 ({prow.get('lsj_sense_count')})")
        else:
            note.append("lsj:no entry (H4b Beta Code key)")
        note.append(f"reference:{ref_total} tokens in {len(rc)} textgroups" if ref_total else "reference:absent")
        missing_trad = [c for c, v in trad.items() if v is None]
        if missing_trad:
            note.append("not on disk: " + ",".join(c.replace("tradition_", "") for c in missing_trad))
        note.append(f"galen_nonmedical:{nonmed_counts.get(lem, 0)}")
        note.append(f"morpheus:{morph['admissible']}/{morph['admissible'] + morph['inadmissible']} surfaces admissible, {morph['no_analysis']} no analysis")
        note.append("flags:" + (",".join(flags) if flags else "none"))

        csv_row = {
            "lemma": lem,
            "pos": prow.get("pos", ""),
            "galen_raw_count": prow.get("galen_raw_count", ""),
            "galen_per10k": prow.get("galen_per10k", ""),
            "log_likelihood": prow.get("log_likelihood", ""),
            "lsj_tier": tier,
            "quadrant": quadrant.get(lem, ""),
            "n_works": n_works,
            "works": ";".join(f"{w}:{c}" for w, c in works_sorted),
            "kuhn_loci": ";".join(loci_sorted[:KUHN_MAX]),
            "concordance_n": len(atts),
            "concordance": " || ".join(fmt_kwic(a) for a in kwic),
            "collocates": ";".join(f"{l}:{g}" for l, _o, g in col),
            "lsj_headword": entry["lsj_headword"] if entry else "",
            "lsj_sense_count": entry["lsj_sense_count"] if entry else "",
            "lsj_entry_text": (entry["lsj_entry_text"][:LSJ_TEXT_MAX] + "…") if entry and len(entry["lsj_entry_text"]) > LSJ_TEXT_MAX else (entry["lsj_entry_text"] if entry else ""),
            "lsj_cites_galen": ("true" if entry["lsj_cites_galen"] else "false") if entry else "",
            **{c: ("" if v is None else v) for c, v in trad.items()},
            "galen_nonmedical_count": nonmed_counts.get(lem, 0),
            "morpheus_admissible": "" if morph["fraction"] is None else f"{morph['fraction']:.4f}",
            "machine_flags": ";".join(flags),
            "attribution_note": " | ".join(note),
        }
        csv_rows.append(csv_row)
        jrow = dict(csv_row)
        jrow.update({
            "works": [{"work": w, "count": c} for w, c in works_sorted],
            "kuhn_loci": loci_all,
            "kuhn_loci_n": len(loci_all),
            "concordance": [fmt_kwic(a) for a in kwic],
            "attestations": atts,
            "collocates": [{"lemma": l, "window_count": o, "log_likelihood": g} for l, o, g in col],
            "collocate_window_tokens": med["colloc_window_n"].get(lem, 0),
            "lsj_entry_text": entry["lsj_entry_text"] if entry else "",
            "lsj_entry_id": entry["lsj_entry_id"] if entry else "",
            "lsj_part": entry["lsj_part"] if entry else "",
            "lsj_cites_galen": entry["lsj_cites_galen"] if entry else None,
            "lsj_sense_count": entry["lsj_sense_count"] if entry else None,
            **trad,
            "reference_by_textgroup": dict(rc.most_common()),
            "reference_total": ref_total,
            "morpheus": morph,
            "morpheus_admissible": morph["fraction"],
            "machine_flags": flags,
            "m1_inadmissible_pairs": m1.get(lem, 0),
            "m2_disagreement_tokens": m2.get(lem, 0),
            "attribution_note": note,
        })
        jsonl_rows.append(jrow)

        counts["rows"] += 1
        counts["with_lsj_entry"] += bool(entry)
        counts["with_lsj_cites_galen"] += bool(entry and entry["lsj_cites_galen"])
        counts["with_kuhn_loci"] += bool(loci_all)
        counts["with_concordance"] += bool(atts)
        counts["with_collocates"] += bool(col)
        counts["with_any_tradition"] += bool(ref_total)
        counts["with_named_tradition"] += bool(any(v for c, v in trad.items() if c in TRADITION_PREFIX and v))
        counts["with_hippocrates"] += bool(trad["tradition_hippocrates"])
        counts["with_dioscorides"] += bool(trad["tradition_dioscorides"])
        counts["with_other_medical"] += bool(other_med)
        counts["with_no_tradition"] += not ref_total
        counts["with_galen_nonmedical"] += bool(nonmed_counts.get(lem, 0))
        counts["with_morpheus_fraction"] += morph["fraction"] is not None
        counts["flag_m1_inadmissible"] += "m1_inadmissible" in flags
        counts["flag_m2_disagreement"] += "m2_disagreement" in flags
        counts["flag_hallucination_screen_pass"] += "hallucination_screen_pass" in flags
        counts[f"tier_{tier}"] += 1
        counts[f"tier_{tier}_with_lsj_entry"] += bool(entry)

    # 9. Write outputs
    csv_path = out_dir / "attributed_punch_list.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(csv_rows)
    jsonl_path = out_dir / "attributed_punch_list.jsonl"
    n_att = 0
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for r in jsonl_rows:
            n_att += len(r["attestations"])
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 10. Sanity: 5 random lemmas, reference total vs lemma_frequency_reference.json
    rng = random.Random(SANITY_SEED)
    sample = rng.sample(sorted(punch), 5)
    sanity = []
    for lem in sample:
        mine = sum(ref_counts.get(lem, Counter()).values())
        theirs = int((ref_freq.get("lemmas", {}).get(lem) or {}).get("raw_count", 0))
        sanity.append({"lemma": lem, "phase3_reference_total": mine, "lemma_frequency_reference_raw_count": theirs, "match": mine == theirs})
    # whole-set cross-checks (not required by spec; cheap)
    ref_all_match = sum(1 for l in punch if sum(ref_counts.get(l, Counter()).values()) == int((ref_freq.get("lemmas", {}).get(l) or {}).get("raw_count", 0)))
    nonmed_all_match = sum(1 for l in punch if nonmed_counts.get(l, 0) == int((nonmed_freq.get(l) or {}).get("raw_count", 0)))
    lsj_cached_match = 0
    for l in punch:
        e = lsj.get(lemma_to_lookup_key(l))
        c = lsj_index_cached.get(lemma_to_lookup_key(l))
        if (e is None and c is None) or (e and c and e["lsj_sense_count"] == c.get("lsj_sense_count")):
            lsj_cached_match += 1

    runtime = round(time.time() - t_start, 1)
    lem_sum = read_json(lemmatized / "_lemmatize_summary_galen.json") if (lemmatized / "_lemmatize_summary_galen.json").exists() else {}
    catalog_path = resolve_path(cfg, "reference_corpus") / "_first1k_catalog.json"
    catalog = read_json(catalog_path) if catalog_path.exists() else {}
    summary = {
        "script": SCRIPT_VERSION,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runtime_seconds": runtime,
        "counts": dict(sorted(counts.items())),
        "attestations_total_in_jsonl": n_att,
        "gates": {
            "rows_expected": 1433,
            "rows_out": counts["rows"],
            "lsj_entry_found_ge_690": counts["with_lsj_entry"] >= 690,
            "thin_tier_all_have_entry": counts.get("tier_thin", 0) == counts.get("tier_thin_with_lsj_entry", 0),
            "concordance_for_all": counts["with_concordance"] == counts["rows"],
        },
        "sanity_check_5_lemmas": {"seed": SANITY_SEED, "rows": sanity, "all_match": all(s["match"] for s in sanity)},
        "cross_checks": {
            "reference_total_matches_lemma_frequency_reference": f"{ref_all_match}/{len(punch)}",
            "galen_nonmedical_matches_lemma_frequency_galen_nonmedical": f"{nonmed_all_match}/{len(punch)}",
            "per_work_sum_matches_galen_raw_count": f"{len(punch) - len(work_sum_mismatch)}/{len(punch)}",
            "per_work_sum_mismatch_examples": work_sum_mismatch[:10],
            "lsj_sense_count_matches_cached_index": f"{lsj_cached_match}/{len(punch)}",
            "lsj_sense_count_differs_from_phase2": sense_mismatch[:20],
        },
        "kuhn_alignment": {
            **med["align_stats"],
            "editions": {stem_to_urn(st): {"volumes": sorted({lab[0] for lab, _t in strm if lab}), "pages": len({lab for lab, _t in strm if lab}), "tokens_before_first_page_marker": sum(1 for lab, _t in strm if lab is None)} for st, strm in sorted(page_streams.items())},
            "caveat": "volume labels come from the TEI header biblScope ranges via h3m.kuhn_index._choose_volume; an edition spanning two Kuhn volumes without per-volume page ranges is labelled with its first volume",
            "aligned_pct": round(100.0 * med["align_stats"]["tokens_aligned"] / med["align_stats"]["tokens_total_in_kuhn_editions"], 2) if med["align_stats"]["tokens_total_in_kuhn_editions"] else None,
            "method": "monotone walk of lemmatized surfaces over the document-order TEI <pb n>/Kühn-milestone page token stream (same walk as pipeline/h3m/kuhn_index.py), Greek letters only, lookahead 40 / lookback 3 tokens, forward jumps >2 need next-token confirmation",
        },
        "tradition_attribution": {
            "method": "URN textgroup prefix only",
            "columns": {c: {"prefix": p, "on_disk": p in present_prefixes} for c, p in TRADITION_PREFIX.items()},
            "spec_deviations": [
                "tradition_dioscorides uses tlg0656 (First1K: Dioscorides Pedanius, De materia medica); the spec's tlg0094 is Pseudo-Plutarch De fluviis in First1K and is counted as nonmedical",
                "tradition_paulus: spec's tlg0565 is Soranus in First1K (counted as other_medical); Paulus Aegineta (tlg0715) is not in the reference set -> column empty",
                "tradition_oribasius (tlg0722), tradition_aetius (tlg0718), tradition_aretaeus (tlg0719): not in the reference set -> columns empty",
                "no on-disk 'medical' marking exists for reference authors; OTHER_MEDICAL_PREFIX in the script is the auditable list",
            ],
            "other_medical_prefixes": OTHER_MEDICAL_PREFIX,
            "reference_stream": ref_stats,
        },
        "sources": {
            "galen_medical_lemmatized": {"dir": str(galen_dir.relative_to(root)), "files": med["n_files"], "lemmatizer": lem_sum.get("backend"), "model": lem_sum.get("model")},
            "galen_nonmedical_lemmatized": {"dir": str(nonmed_dir.relative_to(root)), "files": nonmed_files},
            "reference_lemmatized": {"dir": str(ref_dir.relative_to(root)), "files": ref_stats["files"], "tokens": ref_stats["tokens"], "source": "First1KGreek (OpenGreekAndLatin), catalog nodeCount " + str(catalog.get("nodeCount")), "catalog": str(catalog_path.relative_to(root))},
            "odycy": {"model_name": "grc_odycy_joint_trf", "model_version": (lem_sum.get("model") or {}).get("model_version", "0.7.0"), "spacy_version": (lem_sum.get("model") or {}).get("spacy_version")},
            "lsj": {"source": "Perseus Digital Library LSJ XML (CC-BY-SA), PerseusDL/lexica CTS_XML_TEI/perseus/pdllex/grc/lsj", "base_url": cfg.get("lsj_base_url"), "parts": lsj_parts, "key_canonicalisation": "lib.beta_keys.lemma_to_lookup_key (H4b)"},
            "kuhn_pages": {"source": "First1KGreek TEI <pb n> + biblScope vol/pp headers and milestone unit=Kühn_page, via pipeline/h3m/kuhn_index.py", "editions_with_pages": len(page_streams), "raw_xml": str(raw_xml.relative_to(root))},
            "four_way": "outputs/four_way_classification.csv",
            "phase2_carried": "outputs/punch_list.csv",
            "h3m": {"morpheus_cache": "data/qc/h3m/cache/morpheus_by_surface.jsonl (Perseids Morpheus, surfaces " + str(len(morph_cache)) + ")", "m1": "data/qc/h3m/m1_inadmissible.csv", "m2": "data/qc/h3m/m2_disagreements.csv", "hallucination_screen": "pipeline/07_punchlist.py P3-2 (sense_count==0 rows only)"},
        },
        "outputs": {
            "csv": str(csv_path.relative_to(root)),
            "jsonl": str(jsonl_path.relative_to(root)),
        },
    }
    write_json(out_dir / "phase3_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {csv_path} ({len(csv_rows)} rows) and {jsonl_path} ({n_att} attestations) in {runtime}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
