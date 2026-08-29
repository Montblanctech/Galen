#!/usr/bin/env python3
"""Stage 02: TEI/EpiDoc XML -> plain NFC Greek text with orthographic normalization."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, resolve_path
from lib.greek_normalize import normalize_extracted_text
from lib.io_utils import ensure_dir, write_json

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS, "xml": XML_NS}

DROP_TAGS = {
    f"{{{TEI_NS}}}app",
    f"{{{TEI_NS}}}note",
    f"{{{TEI_NS}}}bibl",
    f"{{{TEI_NS}}}ref",
    f"{{{TEI_NS}}}teiHeader",
    f"{{{TEI_NS}}}facsimile",
}


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def should_skip_element(el: etree._Element, include_supplied: bool, include_gap: bool) -> bool:
    if el.tag in DROP_TAGS:
        return True
    local = _local(el.tag)
    if local in {"app", "rdg", "note", "teiHeader", "facsimile"}:
        return True
    lang = el.get(f"{{{XML_NS}}}lang") or el.get("lang")
    if lang and lang not in {"grc", "greek"}:
        return True
    if not include_supplied and local == "supplied":
        return True
    if not include_gap and local == "gap":
        return True
    return False


def extract_raw_greek(xml_path: Path, include_supplied: bool, include_gap: bool) -> str:
    parser = etree.XMLParser(resolve_entities=False, recover=True, huge_tree=True)
    tree = etree.parse(str(xml_path), parser)
    root = tree.getroot()

    edition_nodes = root.xpath('.//tei:div[@type="edition"]', namespaces=NS)
    if edition_nodes:
        roots = edition_nodes
    else:
        bodies = root.xpath(".//tei:body", namespaces=NS)
        roots = bodies if bodies else [root]

    chunks: list[str] = []

    def walk(el: etree._Element) -> None:
        if should_skip_element(el, include_supplied, include_gap):
            return
        if el.text:
            chunks.append(el.text)
        for child in el:
            walk(child)
            if child.tail:
                chunks.append(child.tail)

    for node in roots:
        walk(node)

    text = "".join(chunks)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_dir(
    src: Path,
    dest: Path,
    include_supplied: bool,
    include_gap: bool,
    norm_log_path: Path | None = None,
) -> tuple[int, int, dict]:
    ensure_dir(dest)
    ok = fail = 0
    aggregate = {
        "lunate_sigma_chars": 0,
        "all_caps_tokens_stripped": 0,
        "crasis_expanded": 0,
        "crasis_unknown_dropped": 0,
        "crasis_unknown_types": 0,
        "per_file": [],
    }
    unknown_types: set[str] = set()

    for xml_path in sorted(src.glob("*.xml")):
        if xml_path.name.startswith("_"):
            continue
        out_path = dest / (xml_path.stem + ".txt")
        try:
            raw = extract_raw_greek(xml_path, include_supplied, include_gap)
            text, stats = normalize_extracted_text(raw)
            out_path.write_text(text + "\n", encoding="utf-8")
            words = len(text.split())
            print(
                f"  OK  {xml_path.name} -> {words} words "
                f"(caps_stripped={stats['all_caps_tokens_stripped']}, "
                f"lunate={stats['lunate_sigma_chars']}, "
                f"crasis_exp={stats['crasis_expanded']}, "
                f"crasis_drop={stats['crasis_unknown_dropped']})"
            )
            ok += 1
            for k in (
                "lunate_sigma_chars",
                "all_caps_tokens_stripped",
                "crasis_expanded",
                "crasis_unknown_dropped",
            ):
                aggregate[k] += stats[k]
            unknown_types.update(stats.get("crasis_unknown_examples") or [])
            aggregate["per_file"].append({"file": xml_path.name, **{k: stats[k] for k in (
                "lunate_sigma_chars",
                "all_caps_tokens_stripped",
                "crasis_expanded",
                "crasis_unknown_dropped",
            )}, "words": words})
        except Exception as exc:
            print(f"  FAIL {xml_path.name}: {exc}")
            fail += 1

    aggregate["crasis_unknown_types"] = len(unknown_types)
    aggregate["crasis_unknown_examples"] = sorted(unknown_types)[:100]
    if norm_log_path is not None:
        write_json(norm_log_path, aggregate)
    return ok, fail, aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--include-reference", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    extract_cfg = cfg.get("extract", {})
    include_supplied = bool(extract_cfg.get("include_supplied", False))
    include_gap = bool(extract_cfg.get("include_gap_placeholders", False))

    raw_xml = resolve_path(cfg, "raw_xml")
    extracted = resolve_path(cfg, "extracted_text")
    print(f"Extracting + normalizing Galen texts from {raw_xml}")
    ok, fail, agg = extract_dir(
        raw_xml,
        extracted,
        include_supplied,
        include_gap,
        norm_log_path=extracted / "_normalize_stats_galen.json",
    )
    print(
        f"Galen extract: ok={ok} fail={fail} | "
        f"caps_stripped={agg['all_caps_tokens_stripped']} "
        f"lunate_chars={agg['lunate_sigma_chars']} "
        f"crasis_expanded={agg['crasis_expanded']} "
        f"crasis_unknown_dropped={agg['crasis_unknown_dropped']}"
    )

    if args.include_reference:
        ref_raw = resolve_path(cfg, "reference_corpus") / "raw_xml"
        ref_txt = resolve_path(cfg, "reference_corpus") / "extracted_text"
        if ref_raw.exists():
            print(f"Extracting + normalizing reference texts from {ref_raw}")
            rok, rfail, _ = extract_dir(
                ref_raw,
                ref_txt,
                include_supplied,
                include_gap,
                norm_log_path=ref_txt / "_normalize_stats_reference.json",
            )
            print(f"Reference extract: ok={rok} fail={rfail}")
        else:
            print(f"No reference raw_xml at {ref_raw}; skip.")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
