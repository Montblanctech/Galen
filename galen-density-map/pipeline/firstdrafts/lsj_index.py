"""Build a small LSJ entry index for the target lemmas of a work (spec: firstdrafts_v0_spec.md).

Reads the Perseus LSJ XML parts in data/lsj/ (iterparse), keeps every entryFree whose normalised Beta
Code key matches a wanted lemma (accent-blind, lib/beta_keys.lemma_to_lookup_key), and writes
outputs/firstdrafts/<slug>/lsj_entries.json: key -> {lsj_entry_id, lsj_key, lsj_headword, lsj_sense_count,
lsj_entry_text (plain, Beta Code Greek rendered as Unicode, truncated), lsj_part}. The lookup is the one
stage 06 and stage 11 use; when several entries share a key the one with more senses wins (stage 06 rule).
Usage: .venv/Scripts/python -X utf8 pipeline/firstdrafts/lsj_index.py --work adversus-lycum
"""
from __future__ import annotations

import argparse
import csv
import json
import re

import beta_code
from lxml import etree

from common import GDM, nfc, out_dir

from lib.beta_keys import betacode_headword_to_unicode, lemma_to_lookup_key, normalize_betacode_key  # noqa: E402

GREEK_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")
TEXT_MAX = 1200


def _beta_or_text(s: str) -> str:
    if not s or GREEK_RE.search(s):
        return s
    s = s.replace("^", "").replace("_", "")
    try:
        return beta_code.beta_code_to_greek(s)
    except Exception:
        return s


def entry_text(entry) -> str:
    parts: list[str] = []

    def walk(el) -> None:
        lang = (el.get("lang") or "").lower()
        greek = lang in {"greek", "grc"}
        if el.text:
            parts.append(_beta_or_text(el.text) if greek else el.text)
        for ch in el:
            walk(ch)
            if ch.tail:
                parts.append(_beta_or_text(ch.tail) if greek else ch.tail)

    walk(entry)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="adversus-lycum")
    a = ap.parse_args()
    out = out_dir(a.work)
    wanted: dict[str, set[str]] = {}
    for r in csv.DictReader((out / "targets.csv").open(encoding="utf-8")):
        for lem in (r["dilemma_lemma"], r["odycy_lemma"]):
            if lem:
                wanted.setdefault(lemma_to_lookup_key(lem), set()).add(nfc(lem))
    found: dict[str, dict] = {}
    parts = sorted((GDM / "data" / "lsj").glob("grc.lsj.perseus-eng*.xml"), key=lambda p: int(re.search(r"eng(\d+)", p.name).group(1)))
    for path in parts:
        n_scanned = 0
        for _, el in etree.iterparse(str(path), events=("end",), tag=("{*}entryFree", "entryFree"), recover=True, huge_tree=True):
            n_scanned += 1
            key_attr = el.get("key") or ""
            heads = [key_attr] + [o.text for o in el.iter("{*}orth", "orth") if o.text]
            senses = len(list(el.iter("{*}sense", "sense")))
            hit = None
            for hw in heads:
                k = normalize_betacode_key(re.sub(r"\d+$", "", hw))
                if k in wanted:
                    hit = k
                    break
            if hit is not None:
                prev = found.get(hit)
                if prev is None or senses > prev["lsj_sense_count"]:
                    txt = entry_text(el)
                    found[hit] = {"lsj_entry_id": el.get("id") or "", "lsj_key": key_attr, "lsj_headword": betacode_headword_to_unicode(re.sub(r"\d+$", "", key_attr)),
                                  "lsj_sense_count": senses, "lsj_entry_text": txt[:TEXT_MAX] + ("…" if len(txt) > TEXT_MAX else ""), "lsj_part": path.name,
                                  "lemmas": sorted(wanted[hit])}
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]
        print(f"{path.name}: {n_scanned} entries, {len(found)}/{len(wanted)} keys resolved", flush=True)
    (out / "lsj_entries.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sorted(k for k in wanted if k not in found)
    (out / "lsj_entries_missing.json").write_text(json.dumps({k: sorted(wanted[k]) for k in missing}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"resolved {len(found)} of {len(wanted)} lemma keys; missing {len(missing)}")


if __name__ == "__main__":
    main()
