"""Build (Kühn volume, page) → edition URN + normalized page text from First1K TEI."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.greek_normalize import TOKEN_RE, normalize_extracted_text
from lib.urns import urn_to_safe_filename

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS, "xml": XML_NS}

DROP_LOCAL = {"app", "rdg", "note", "bibl", "ref", "teiHeader", "facsimile"}
KUHN_PAGE_RE = re.compile(r"v(?P<vol>\d+)\.p(?P<page>\d+)", re.I)
PB_INT_RE = re.compile(r"^\d+$")


@dataclass
class VolRange:
    volume: int
    page_from: int
    page_to: int


@dataclass
class PageSpan:
    volume: int
    page: int
    edition_urn: str
    stem: str
    text: str
    tokens: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _should_skip(el: etree._Element) -> bool:
    local = _local(el.tag)
    if local in DROP_LOCAL:
        return True
    lang = el.get(f"{{{XML_NS}}}lang") or el.get("lang")
    if lang and lang not in {"grc", "greek", "eng"}:
        # keep header (eng) out via teiHeader skip; skip non-grc body
        if local not in {"TEI", "text", "body", "div", "p", "lb", "pb", "milestone"}:
            if lang not in {"grc", "greek"}:
                return True
    if local == "supplied" or local == "gap":
        return True
    return False


def parse_kuhn_ranges(tree: etree._ElementTree) -> tuple[bool, list[VolRange]]:
    """Return (is_kuhn_edition, volume page ranges from the header)."""
    editors = tree.xpath(".//tei:teiHeader//tei:editor", namespaces=NS)
    is_kuhn = any("kühn" in ((el.text or "") + " ").lower() or "kuhn" in ((el.text or "")).lower() for el in editors)
    ranges: list[VolRange] = []
    for imprint in tree.xpath(".//tei:teiHeader//tei:imprint", namespaces=NS):
        vols = imprint.xpath("./tei:biblScope[@unit='vol']", namespaces=NS)
        pps = imprint.xpath("./tei:biblScope[@unit='pp']", namespaces=NS)
        if not vols:
            continue
        try:
            vol = int(re.sub(r"\D+", "", (vols[0].text or vols[0].get("n") or "") ) or "0")
        except ValueError:
            continue
        if vol <= 0:
            continue
        pf = pt = None
        if pps:
            el = pps[0]
            pf = el.get("from")
            pt = el.get("to")
            if not pf:
                m = re.search(r"(\d+)\s*[-–]\s*(\d+)", el.text or "")
                if m:
                    pf, pt = m.group(1), m.group(2)
        if pf and pt:
            ranges.append(VolRange(vol, int(pf), int(pt)))
        else:
            ranges.append(VolRange(vol, 1, 9999))
    return is_kuhn, ranges


def _choose_volume(n: int, ranges: list[VolRange], current: int | None) -> int | None:
    if not ranges:
        return current
    for rng in ranges:
        if rng.page_from <= n <= rng.page_to:
            return rng.volume
    if current is not None:
        return current
    return ranges[0].volume


def _edition_roots(tree: etree._ElementTree) -> list[etree._Element]:
    root = tree.getroot()
    edition_nodes = root.xpath('.//tei:div[@type="edition"]', namespaces=NS)
    if edition_nodes:
        return list(edition_nodes)
    bodies = root.xpath(".//tei:body", namespaces=NS)
    return list(bodies) if bodies else [root]


def _stem_to_urn(stem: str) -> str:
    # urn_cts_greekLit_tlg0057.tlg075.1st1K-grc1 → urn:cts:greekLit:tlg0057.tlg075.1st1K-grc1
    s = stem
    if s.startswith("urn_cts_"):
        s = "urn:cts:" + s[len("urn_cts_") :]
        s = s.replace("greekLit_", "greekLit:", 1)
    return s


def extract_pages_from_tei(xml_path: Path) -> list[PageSpan]:
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    tree = etree.parse(str(xml_path), parser)
    is_kuhn, ranges = parse_kuhn_ranges(tree)
    stem = xml_path.stem
    urn = _stem_to_urn(stem)

    pages: dict[tuple[int, int], list[str]] = {}
    current_vol: int | None = ranges[0].volume if ranges else None
    current_page: int | None = None
    used_kuhn_milestone = False

    def flush_text(text: str) -> None:
        if current_vol is None or current_page is None or not text:
            return
        pages.setdefault((current_vol, current_page), []).append(text)

    def handle_pb(el: etree._Element) -> None:
        nonlocal current_vol, current_page, used_kuhn_milestone
        n_attr = (el.get("n") or "").strip()
        unit = (el.get("unit") or "") if _local(el.tag) == "milestone" else ""
        if _local(el.tag) == "milestone":
            if (el.get("unit") or "") == "Kühn_page" or "kuhn" in (el.get("unit") or "").lower():
                m = KUHN_PAGE_RE.search(el.get("n") or "")
                if m:
                    current_vol = int(m.group("vol"))
                    current_page = int(m.group("page"))
                    used_kuhn_milestone = True
                    pages.setdefault((current_vol, current_page), [])
            return
        if not PB_INT_RE.match(n_attr):
            return
        n = int(n_attr)
        current_vol = _choose_volume(n, ranges, current_vol)
        current_page = n
        pages.setdefault((current_vol or 0, n), [])

    def walk(el: etree._Element) -> None:
        local = _local(el.tag)
        if local in {"pb", "milestone"}:
            handle_pb(el)
        if _should_skip(el):
            if el.tail:
                flush_text(el.tail)
            return
        if el.text and local not in {"pb", "milestone"}:
            flush_text(el.text)
        for child in el:
            walk(child)
        if el.tail:
            flush_text(el.tail)

    if not is_kuhn:
        # Still walk if Kühn_page milestones exist (e.g. tlg033 Helmreich).
        has_ms = bool(tree.xpath('.//tei:milestone[@unit="Kühn_page"]', namespaces=NS))
        if not has_ms:
            return []

    for node in _edition_roots(tree):
        walk(node)

    out: list[PageSpan] = []
    for (vol, page), chunks in sorted(pages.items()):
        if vol <= 0 or page <= 0:
            continue
        raw = " ".join(chunks)
        text, _stats = normalize_extracted_text(raw)
        tokens = TOKEN_RE.findall(text)
        out.append(
            PageSpan(
                volume=vol,
                page=page,
                edition_urn=urn,
                stem=stem,
                text=text,
                tokens=tokens,
            )
        )
    return out


def build_kuhn_index(raw_xml_dir: Path) -> dict[tuple[int, int], list[PageSpan]]:
    index: dict[tuple[int, int], list[PageSpan]] = {}
    files = sorted(p for p in raw_xml_dir.glob("*.xml") if not p.name.startswith("_"))
    print(f"Indexing Kühn pages in {len(files)} TEI files", flush=True)
    n_pages = 0
    n_kuhn_files = 0
    for path in files:
        spans = extract_pages_from_tei(path)
        if not spans:
            continue
        n_kuhn_files += 1
        for span in spans:
            index.setdefault((span.volume, span.page), []).append(span)
            n_pages += 1
    print(f"Kühn index: {n_kuhn_files} editions, {n_pages} page spans, {len(index)} unique (vol,page)", flush=True)
    return index


def window_text(index: dict[tuple[int, int], list[PageSpan]], vol: int, page: int, pad: int = 1) -> list[tuple[PageSpan, str]]:
    """For each edition covering this page, concatenate ±pad pages from the same stem."""
    hits = index.get((vol, page)) or []
    out: list[tuple[PageSpan, str]] = []
    for span in hits:
        parts = []
        for p in range(page - pad, page + pad + 1):
            for other in index.get((vol, p), []):
                if other.stem == span.stem:
                    parts.append(other.text)
                    break
        out.append((span, " ".join(t for t in parts if t)))
    return out
