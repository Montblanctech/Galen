"""Build a small LSJ entry index for the target lemmas of a work (spec: firstdrafts_v0_spec.md).

Reads the Perseus LSJ XML parts in data/lsj/ (iterparse), keeps every entryFree whose normalised Beta
Code key matches a wanted lemma (accent-blind, lib/beta_keys.lemma_to_lookup_key), and writes
outputs/firstdrafts/<slug>/lsj_entries.json: key -> {lsj_entry_id, lsj_key, lsj_headword, lsj_sense_count,
lsj_entry_text (plain, Beta Code Greek rendered as Unicode, WHOLE entry, v0.2: no truncation),
lsj_senses (the text of every <sense>, in order), lsj_first_sense_gloss (v0.2 anchor source), lsj_part}. The lookup is the one
stage 06 and stage 11 use; when several entries share a key the one with more senses wins (stage 06 rule).
Usage: .venv/Scripts/python -X utf8 pipeline/firstdrafts/lsj_index.py --work adversus-lycum
A work whose config names the Lewis & Short lexicon (lexicon.name = "ls") gets the same file from the Perseus L&S XML
(build_ls; keys lsgold.latnorm.key; anchor gloss = the first italic English of the first sense).
"""
from __future__ import annotations

import argparse
import csv
import json
import re

import beta_code
from lxml import etree

from common import GDM, nfc, out_dir, work_config

from lib.beta_keys import betacode_headword_to_unicode, lemma_to_lookup_key, normalize_betacode_key  # noqa: E402

GREEK_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")


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


def sense_texts(entry) -> list[str]:
    return [t for t in (entry_text(s) for s in entry.iter("{*}sense", "sense")) if t]


def first_sense_gloss(senses: list[str], entry_txt: str) -> str:
    """v0.2 anchor gloss: the first English run of the first sense (falls back to the entry text), cut at the
    first ',', ';', ':' or author citation, with parentheticals, '= <Greek>' cross references, sense letters
    and grammatical labels removed. Validated later by checks.valid_anchor_gloss."""
    src = senses[0] if senses else entry_txt
    text = re.sub(r"\s+", " ", src or "")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"=\s*[^,;]*[,;]", " ", text)
    text = re.sub(r"^\s*[A-Z]?\s*[IVX]*\.?\s*\d*\.?\s*", "", text)  # sense numbering
    for m in re.finditer(r"(?<![A-Za-z])([a-z][a-z\-']+(?: [a-zA-Z\-']+)*)", text):
        seg = text[m.start(1):]
        seg = re.split(r"[,;:]| [A-Z][a-z]{1,5}\. ?| v\. | cf\. |\d", seg)[0].strip(" .")
        if seg:
            return seg
    return ""


def ls_gloss(entry, senses: list[str], entry_txt: str) -> str:
    """Lewis & Short anchor gloss: the first italic run (<hi rend="ital">, where L&S prints its English sense) of the
    first <sense>, trimmed of trailing punctuation; falls back to first_sense_gloss."""
    for sense in entry.iter("{*}sense", "sense"):
        for hi in sense.iter("{*}hi", "hi"):
            t = re.sub(r"\s+", " ", "".join(hi.itertext())).strip(" ;,:.")
            if re.search(r"[a-z]{3}", t):
                return t
        break
    return first_sense_gloss(senses, entry_txt)


def build_ls(out) -> None:
    """lsj_entries.json for a Latin work: the same fields as the LSJ index, from the Perseus Lewis & Short XML
    (data/latin_feasibility/lat.ls.perseus-eng2.xml), keyed by lsgold.latnorm.key; when several entries share a key
    the one with more senses wins (the LSJ rule)."""
    from lsgold.latnorm import key as lkey  # noqa: E402

    wanted: dict[str, set[str]] = {}
    for r in csv.DictReader((out / "targets.csv").open(encoding="utf-8")):
        for lem in (r["dilemma_lemma"], r["odycy_lemma"]):
            if lem and lkey(lem):
                wanted.setdefault(lkey(lem), set()).add(nfc(lem))
    path = GDM / "data" / "latin_feasibility" / "lat.ls.perseus-eng2.xml"
    found: dict[str, dict] = {}
    n_scanned = 0
    for _, el in etree.iterparse(str(path), events=("end",), tag=("{*}entryFree", "entryFree"), recover=True, huge_tree=True):
        n_scanned += 1
        key_attr = el.get("key") or ""
        orths = [o.text for o in el.iter("{*}orth", "orth") if o.text]
        senses = len(list(el.iter("{*}sense", "sense")))
        for hw in [key_attr] + orths:
            k = lkey(re.sub(r"\d+$", "", hw))
            if k in wanted and (k not in found or senses > found[k]["lsj_sense_count"]):
                txt = entry_text(el)
                sts = sense_texts(el)
                found[k] = {"lsj_entry_id": el.get("id") or "", "lsj_key": key_attr, "lsj_headword": (orths[0] if orths else key_attr).strip(),
                            "lsj_sense_count": senses, "lsj_entry_text": txt, "lsj_entry_chars": len(txt), "lsj_senses": sts,
                            "lsj_first_sense_gloss": ls_gloss(el, sts, txt), "lsj_part": path.name, "lemmas": sorted(wanted[k])}
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]
    print(f"{path.name}: {n_scanned} entries, {len(found)}/{len(wanted)} keys resolved", flush=True)
    (out / "lsj_entries.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sorted(k for k in wanted if k not in found)
    (out / "lsj_entries_missing.json").write_text(json.dumps({k: sorted(wanted[k]) for k in missing}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"resolved {len(found)} of {len(wanted)} lemma keys; missing {len(missing)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="adversus-lycum")
    a = ap.parse_args()
    out = out_dir(a.work)
    lexicon = work_config(a.work)["lexicon"]["name"]   # lsj (Galen and Greek configs) or ls (Lewis & Short)
    if lexicon == "ls":
        build_ls(out)
        return
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
                    sts = sense_texts(el)
                    found[hit] = {"lsj_entry_id": el.get("id") or "", "lsj_key": key_attr, "lsj_headword": betacode_headword_to_unicode(re.sub(r"\d+$", "", key_attr)),
                                  "lsj_sense_count": senses, "lsj_entry_text": txt, "lsj_entry_chars": len(txt), "lsj_senses": sts,
                                  "lsj_first_sense_gloss": first_sense_gloss(sts, txt), "lsj_part": path.name, "lemmas": sorted(wanted[hit])}
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
