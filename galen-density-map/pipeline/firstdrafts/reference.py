"""Galen First Drafts v0.2: the calibration set for Composition of Drugs by Kind (spec: firstdrafts_v02_spec.md §(d)).

Zainaldin et al. 2026 (arXiv 2602.24119) published, in github.com/campattison/galen_project, a reference
English translation of ten passages of De compositione medicamentorum per genera by Manuela Marai under
CC BY 4.0 (the Greek is Kühn's, public domain). This script

  fetch   downloads, at a pinned commit, mt_eval/input/on_comp.txt (Greek + English, ten chunks),
          analysis/data/passage_locations.csv (Kühn loci), the repository LICENSE (MIT, code) and README
          (the licence statement for the data) into outputs/firstdrafts/comp-per-genera/reference/, checks
          the SHA-256 of on_comp.txt against the one the repository's REFERENCES.md lists, and writes
          LICENCE.md stating what is under which licence and how it is attributed.
  map     splits on_comp.txt into passages, maps each to our units by Kühn page (passage_locations.csv)
          and confirms the mapping by matching the passage's Greek against the units' Greek (token
          recall after accent-blind normalisation), writes reference/calibration_map.json and
          reference/passages.jsonl.

No model is involved. Usage:
  python reference.py fetch --work comp-per-genera
  python reference.py map   --work comp-per-genera
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

from common import WORKS, nfc, out_dir, read_jsonl, strip_punct, write_jsonl

RAW = "https://raw.githubusercontent.com/campattison/galen_project/{commit}/{path}"
FILES = {"on_comp.txt": "mt_eval/input/on_comp.txt", "passage_locations.csv": "analysis/data/passage_locations.csv",
         "REFERENCES.md": "mt_eval/input/REFERENCES.md", "LICENSE_code_MIT.txt": "LICENSE", "README_upstream.md": "README.md"}
LOCUS_RE = re.compile(r"XIII\.(\d+),(\d+)[–-](\d+),(\d+) K\.")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fetch(slug: str) -> None:
    w = WORKS[slug]
    ref = w["reference"]
    rd = out_dir(slug) / "reference"
    rd.mkdir(exist_ok=True)
    for local, path in FILES.items():
        url = RAW.format(commit=ref["commit"], path=path)
        data = urllib.request.urlopen(url, timeout=60).read()
        (rd / local).write_bytes(data)
        print(f"fetched {path} -> {local} ({len(data):,} bytes)")
    # checksum of on_comp.txt as listed in the upstream REFERENCES.md
    refs = (rd / "REFERENCES.md").read_text(encoding="utf-8")
    m = re.search(r"([0-9a-f]{64})\s+mt_eval/input/on_comp\.txt", refs)
    listed = m.group(1) if m else ""
    got = sha256_file(rd / "on_comp.txt")
    readme = (rd / "README_upstream.md").read_text(encoding="utf-8")
    lic_line = next((l.strip() for l in readme.splitlines() if "on_comp.txt" in l and "CC BY" in l), "")
    (rd / "LICENCE.md").write_text(
        "# Licence of the files in this folder\n\n"
        f"Source: {ref['repo']} at commit `{ref['commit']}` (fetched {__import__('datetime').date.today().isoformat()}).\n\n"
        "- `on_comp.txt`: the Greek of ten passages of Galen, *De compositione medicamentorum per genera* (Kühn XIII, public domain) with the English "
        "reference translation made for Zainaldin et al. 2026 by **Manuela Marai**, released under **CC BY 4.0** "
        "(https://creativecommons.org/licenses/by/4.0/). The upstream README states: \"" + lic_line.replace("- ", "", 1) + "\". "
        "Attribution required on any reuse: *Manuela Marai, reference translation for Zainaldin et al. 2026, CC BY 4.0, via github.com/campattison/galen_project*.\n"
        "- `passage_locations.csv`, `REFERENCES.md`: data and documentation of the same repository, MIT (see `LICENSE_code_MIT.txt`, © 2026 Cameron Pattison).\n"
        "- `README_upstream.md`, `LICENSE_code_MIT.txt`: the repository's own README and LICENSE, copied for the record.\n\n"
        f"Integrity: SHA-256 of `on_comp.txt` = `{got}`; the upstream REFERENCES.md lists `{listed or 'not found'}` → {'MATCH' if listed == got else 'MISMATCH'}.\n\n"
        "Use in this project: calibration only (spec `firstdrafts_v02_spec.md`, check (d)). The reference English is never shown to a translator, "
        "back-translator or judge; it is compared with the finished renderings after the fact. The reference text is not reproduced on the public page; "
        "the page links to the upstream file.\n", encoding="utf-8")
    print("checksum", "MATCH" if listed == got else "MISMATCH", got)
    if listed != got:
        sys.exit("on_comp.txt checksum does not match upstream REFERENCES.md")


def split_passages(txt: str) -> list[dict]:
    """on_comp.txt: 'Chunk N' line, Greek paragraph, English paragraph, blank lines."""
    out, cur = [], None
    for line in txt.splitlines():
        s = line.strip()
        m = re.fullmatch(r"Chunk (\d+)", s)
        if m:
            cur = {"passage": int(m.group(1)), "greek": "", "english": ""}
            out.append(cur)
        elif s and cur is not None:
            if not cur["greek"]:
                cur["greek"] = s
            elif not cur["english"]:
                cur["english"] = s
            else:
                cur["english"] += " " + s
    return out


def gkey(tok: str) -> str:
    """accent-blind, lower-case, final-sigma-blind key for Greek tokens."""
    t = strip_punct(nfc(tok)).lower().replace("ς", "σ")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))
    return t


def map_passages(slug: str) -> None:
    rd = out_dir(slug) / "reference"
    units = read_jsonl(out_dir(slug) / "units.jsonl")
    by_page: dict[str, list[str]] = {}
    for u in units:
        for p in u["pages"]:
            by_page.setdefault(p, []).append(u["unit_id"])
    uni = {u["unit_id"]: u for u in units}
    passages = split_passages((rd / "on_comp.txt").read_text(encoding="utf-8"))
    loci = {}
    for line in (rd / "passage_locations.csv").read_text(encoding="utf-8").splitlines()[1:]:
        text, n, loc = line.split(",", 2)
        if text == "Comp":
            loci[int(n)] = loc.strip().strip('"')
    rows, cm = [], {"work": slug, "source": WORKS[slug]["reference"], "n_passages": len(passages), "passages": []}
    for p in passages:
        loc = loci.get(p["passage"], "")
        m = LOCUS_RE.search(loc)
        p0, p1 = (int(m.group(1)), int(m.group(3))) if m else (None, None)
        cand = []
        if p0:
            for pg in range(p0, p1 + 1):
                for uid in by_page.get(str(pg), []):
                    if uid not in cand:
                        cand.append(uid)
        # confirm by Greek token recall: keep the units that contain the passage's tokens
        ptoks = [gkey(t) for t in p["greek"].split() if gkey(t)]
        pset = set(ptoks)
        kept, per_unit = [], {}
        for uid in cand:
            utoks = {gkey(t) for t in uni[uid]["greek_plain"].split()}
            share = len(pset & utoks) / len(pset) if pset else 0
            per_unit[uid] = round(share, 3)
            if share >= 0.10:
                kept.append(uid)
        covered = set()
        for uid in kept:
            covered |= {gkey(t) for t in uni[uid]["greek_plain"].split()}
        recall = round(len(pset & covered) / len(pset), 3) if pset else 0
        entry = {"passage": p["passage"], "locus": loc, "kuhn_pages": [p0, p1], "candidate_units": cand, "unit_ids": kept, "token_recall_in_units": recall,
                 "per_unit_share": per_unit, "n_greek_words": len(p["greek"].split()), "n_english_words": len(p["english"].split())}
        cm["passages"].append(entry)
        rows.append({**p, **{k: entry[k] for k in ("locus", "kuhn_pages", "unit_ids", "token_recall_in_units")}})
        print(f"passage {p['passage']:2d} {loc:28s} units {kept} recall {recall}")
    cm["calibration_unit_ids"] = sorted({u for e in cm["passages"] for u in e["unit_ids"]}, key=lambda x: [uni[x]["unit_id"] == x and units.index(uni[x])])
    cm["n_calibration_units"] = len(cm["calibration_unit_ids"])
    cm["note"] = ("A passage is a Kühn line range inside one or two pages; our units are whole pages snapped to sentence ends, so a calibration unit "
                  "contains more Greek than its passage. Check (d) scores only the targets whose Greek token falls inside the passage (reference.py "
                  "records token recall; checks.py restricts by token membership).")
    (rd / "calibration_map.json").write_text(json.dumps(cm, ensure_ascii=False, indent=1), encoding="utf-8")
    write_jsonl(rd / "passages.jsonl", rows)
    print(json.dumps({"n_passages": len(passages), "calibration_units": cm["calibration_unit_ids"], "min_recall": min(e["token_recall_in_units"] for e in cm["passages"])}, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "map"])
    ap.add_argument("--work", default="comp-per-genera")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.work)
    else:
        map_passages(a.work)


if __name__ == "__main__":
    main()
