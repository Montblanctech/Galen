"""Translation-status column for the Phase 1 census (Galen First Drafts, cycle 1, 2026-11-09).

Adds three columns to phase1/galen_ogl_census.csv and the matching fields to every entry of
phase1/galen_ogl_census.json (works[] and pseudo_galen_excluded_from_main_count[]), leaving every
existing column untouched:

  translation_status   english | other_modern | latin_only | none | partial | unknown
  translation_source   short citations / URLs behind the claim
  translation_note     caveats, discrepancies between sources, coverage remarks

Sources, in order of precedence
  1. translation_sources/overrides.csv  - hand-entered claims, each with its citation (research pass
     drafts/untranslated_galen_research.md, 2026-11-08; Johnston & Papavramidou 2024; Zainaldin 2026).
  2. translation_sources/galenus_verbatim_catalogue_2026-11-09.json - the Galenus verbatim catalogue
     (https://galenus-verbatim.github.io/mera-galeni-folia/, parsed 2026-11-09): per work the
     "translationes recentiores" with ISO-639 language codes, and Fichtner's entry number.
  3. translation_sources/fichtner_translations_2026-11-09.json - the "T" (translation) lines of
     Fichtner, Corpus Galenicum (BBAW, 2023/12, https://cmg.bbaw.de/fileadmin/Webdateien/Dateien/
     Galen-Bibliographie.pdf), parsed from the PDF text per entry; language is NOT coded there.

Decision rule (one row = one edition of a work; the status is per work)
  override present                         -> override status, source, note
  GV lists a translation coded eng         -> english
  GV lists a modern-language translation   -> other_modern
  GV lists only lat-coded translations     -> latin_only
  GV lists nothing, Fichtner has no T line -> none
  GV lists nothing, Fichtner has T line(s) -> unknown (the T lines are quoted; language/coverage uncoded)
  work in neither catalogue                -> unknown
Kühn's own facing Latin (present for every Kühn work) is not counted as a translation.
Completeness is not coded by either catalogue; `partial` is assigned only where a source states partial
coverage (overrides). Report only: nothing is guessed; where a claim cannot be sourced the value is unknown.

Usage: python phase1/build_translation_status.py [--fichtner-text path/to/fichtner.txt]
  (the --fichtner-text option re-parses the PDF text into the JSON; without it the JSON is used as is)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "translation_sources"
CSV_PATH = HERE / "galen_ogl_census.csv"
JSON_PATH = HERE / "galen_ogl_census.json"
GV_PATH = SRC / "galenus_verbatim_catalogue_2026-11-09.json"
FICHT_PATH = SRC / "fichtner_translations_2026-11-09.json"
OVERRIDES = SRC / "overrides.csv"
README = HERE / "README_translation_status.md"

NEW_COLS = ["translation_status", "translation_source", "translation_note"]
MODERN = {"eng", "fra", "ita", "deu", "spa", "por", "rus", "jpn", "nld", "pol", "ell", "ces", "cze", "tur", "hun", "ron", "swe", "dan", "fin", "nor", "cat", "heb", "sve", "swe"}
NOT_TRANSLATION_LANGS = {"grc", "ara", "syr"}  # source languages shown in bilingual editions


def parse_fichtner_text(path: Path) -> dict:
    """Entries '↑ N Title' ... 'TLG-ID: 0057.NNN'; translation lines start with a tag set containing T
    (T, E,T, T,K, E,T,K ...). Wrapped lines are joined until the next tagged or labelled line."""
    t = path.read_text(encoding="utf-8")
    t = re.sub(r"\n=== PAGE \d+ ===\n", "\n", t)
    blocks = re.split(r"\n(?=↑ \d+ )", t)
    marker = re.compile(r"^((?:[A-Z]{1,2},)*T(?:,[A-Z]{1,2})*) (?!LG-ID)(.*)$")
    stop = re.compile(r"^(?:[A-Z]{1,2},)*[A-Z]{1,2} |^(?:Vgl\.|Incipit|Arab\.|Lat\.|Syr\.|Hebr\.|CMG-|andere|Alte|online-|TLG|T LG)")
    out = {}
    for b in blocks[1:]:
        m = re.match(r"↑ (\d+) (.*)", b)
        num, title = int(m.group(1)), m.group(2).strip()
        tlg = re.search(r"T\s*LG-ID:\s*(\d{4})\s*\.\s*(\d{3})", b)
        lines = b.split("\n")
        T, i = [], 0
        while i < len(lines):
            mm = marker.match(lines[i])
            if mm:
                cite, j = mm.group(2), i + 1
                while j < len(lines) and lines[j].strip() and not stop.match(lines[j]) and not lines[j].startswith("↑"):
                    cite += " " + lines[j].strip()
                    j += 1
                T.append({"tags": mm.group(1), "cite": re.sub(r"\s+", " ", cite).strip()})
                i = j
            else:
                i += 1
        key = f"tlg{tlg.group(1)}.tlg{tlg.group(2)}" if tlg else ""
        out[str(num)] = {"fichtner_no": num, "title": title, "tlg_id": key, "T": T}
    return out


def gv_langs(cite: str) -> set[str]:
    """Language codes of a GV citation such as 'Singer, 1997 (grc;eng) – source ;' (the trailing link
    text is left in by the parser): the last parenthesised group made of 3-letter codes."""
    groups = [g for g in re.findall(r"\(([A-Za-z;:,/\- ]{3,})\)", cite) if re.fullmatch(r"[A-Za-z]{3}([;:,/\-][A-Za-z]{3})*", g.replace(" ", ""))]
    if not groups:
        return set()
    return {c.strip().lower() for c in re.split(r"[;:,/\-]", groups[-1]) if c.strip()}


def decide(tlg: str, gv: dict | None, ficht: dict | None, override: dict | None) -> dict:
    if override:
        return {k: override[k] for k in NEW_COLS}
    if gv is None and ficht is None:
        return {"translation_status": "unknown", "translation_source": "not in the Galenus verbatim catalogue (2026-11-09) and no Fichtner entry matched by TLG id",
                "translation_note": "no source consulted lists this work; not a claim that no translation exists"}
    src, notes = [], []
    status = None
    fno = (gv or {}).get("fichtner") or (ficht or {}).get("fichtner_no") or ""
    gv_tr = (gv or {}).get("translations", [])
    langs_all = set()
    if gv is not None:
        if gv_tr:
            cites = "; ".join(t["cite"] + (f" <{t['url']}>" if t.get("url") else "") for t in gv_tr)
            src.append(f"Galenus verbatim catalogue tlg0057.{tlg} (Fichtner no. {fno}), translationes recentiores: {cites}")
            for t in gv_tr:
                langs_all |= gv_langs(t["cite"])
            tr_langs = langs_all - NOT_TRANSLATION_LANGS
            if "eng" in tr_langs:
                status = "english"
            elif tr_langs & MODERN:
                status = "other_modern"
            elif tr_langs == {"lat"}:
                status = "latin_only"
            elif not tr_langs:
                status = "unknown"
                notes.append("GV lists translation(s) without a language code")
            else:
                status = "other_modern"
                notes.append(f"uncoded language(s) {sorted(tr_langs)} treated as modern")
        else:
            src.append(f"Galenus verbatim catalogue tlg0057.{tlg} (Fichtner no. {fno}): no translationes recentiores listed")
    if ficht is not None:
        T = ficht.get("T", [])
        if T:
            src.append(f"Fichtner, Corpus Galenicum 2023/12, entry {ficht['fichtner_no']}: {len(T)} translation (T) line(s): " + " | ".join(x["cite"][:160] for x in T))
        else:
            src.append(f"Fichtner, Corpus Galenicum 2023/12, entry {ficht['fichtner_no']}: no T (translation) line")
        if status is None:
            gv_part = "GV lists no translation" if gv is not None else "not in the GV catalogue"
            if T:
                status = "unknown"
                notes.append(f"{gv_part} but Fichtner lists T line(s); their language and coverage are not coded, so the status is unknown rather than none")
            else:
                status = "none"
                notes.append(f"{gv_part}; Fichtner has no T line; Kühn's facing Latin (and any Renaissance/medieval Latin, Arabic or Syriac version) not counted")
        elif status in ("english", "other_modern") and not T:
            notes.append("GV lists a translation that Fichtner's T lines do not; coverage (complete vs. selection) not verified")
    elif status is None:
        status = "unknown"
        notes.append("Fichtner entry not matched by TLG id; GV lists nothing")
    if status in ("english", "other_modern"):
        notes.append("completeness not coded by the catalogues; a listed translation may be a selection")
    return {"translation_status": status, "translation_source": " || ".join(src), "translation_note": "; ".join(notes)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fichtner-text", type=Path, help="re-parse Fichtner PDF text into the JSON snapshot")
    a = ap.parse_args()
    if a.fichtner_text:
        FICHT_PATH.write_text(json.dumps(parse_fichtner_text(a.fichtner_text), ensure_ascii=False, indent=1), encoding="utf-8")
    ficht_raw = json.loads(FICHT_PATH.read_text(encoding="utf-8"))
    ficht_by_tlg = {v["tlg_id"]: v for v in ficht_raw.values() if v["tlg_id"]}
    ficht_by_no = {str(v["fichtner_no"]): v for v in ficht_raw.values()}
    gv = {d["urn"].split(":")[-1]: d for d in json.loads(GV_PATH.read_text(encoding="utf-8"))}  # 'tlg0057.tlg093'
    overrides = {r["tlg_number"]: r for r in csv.DictReader(OVERRIDES.open(encoding="utf-8"))}

    def lookup(author: str, tlg: str) -> dict:
        key = f"{author}.{tlg}"
        g = gv.get(key)
        f = ficht_by_tlg.get(key)
        if f is None and g and g.get("fichtner"):
            f = ficht_by_no.get(g["fichtner"])
        return decide(tlg, g, f, overrides.get(tlg) if author == "tlg0057" else None)

    # CSV
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = [f for f in reader.fieldnames if f not in NEW_COLS]
    for r in rows:
        r.update(lookup("tlg0057", r["tlg_number"]))
    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields + NEW_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # JSON
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for wk in data["works"]:
        wk.update(lookup("tlg0057", wk["tlg_number"]))
    for wk in data.get("pseudo_galen_excluded_from_main_count", []):
        m = re.search(r"(tlg0530)\.(tlg\d+)", wk["urn"])
        wk.update(lookup(m.group(1), m.group(2)))
    by_work = {}
    for r in rows:
        by_work.setdefault(r["tlg_number"], (r["translation_status"], int(r["wordcount"] or 0)))
    counts_works = Counter(s for s, _ in by_work.values())
    words = Counter()
    for s, wc in by_work.values():
        words[s] += wc
    data["translation_status_summary"] = {
        "built": "2026-11-09", "script": "phase1/build_translation_status.py",
        "sources": ["translation_sources/overrides.csv", "translation_sources/galenus_verbatim_catalogue_2026-11-09.json", "translation_sources/fichtner_translations_2026-11-09.json"],
        "distinct_works_by_status": dict(counts_works), "greek_words_by_status_first_edition": dict(words),
        "editions_by_status": dict(Counter(r["translation_status"] for r in rows)),
    }
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # README
    order = ["english", "other_modern", "partial", "latin_only", "none", "unknown"]
    lines = ["# Translation status of the Galen census (phase1), built 2026-11-09", "",
             "Three columns added to `galen_ogl_census.csv` and to every entry of `galen_ogl_census.json`: `translation_status`, `translation_source`, `translation_note`. Every existing column is untouched. Built by `build_translation_status.py`; report only, nothing guessed: where no source supports a claim the value is `unknown`.", "",
             "## Counts (97 distinct tlg0057 works, 103 edition rows; words = OGL Greek word count of the first listed edition)", "",
             "| status | works | editions | Greek words |", "|---|---|---|---|"]
    ed_counts = Counter(r["translation_status"] for r in rows)
    for s in order:
        lines.append(f"| `{s}` | {counts_works.get(s, 0)} | {ed_counts.get(s, 0)} | {words.get(s, 0):,} |")
    lines.append(f"| total | {len(by_work)} | {len(rows)} | {sum(words.values()):,} |")
    lines += ["", "### Works with no modern-language translation in either catalogue (`none`)", ""]
    for r in rows:
        if r["translation_status"] == "none" and r["edition_suffix"].endswith("grc1"):
            lines.append(f"- {r['tlg_number']} *{r['title']}* (Kühn {r['kuhn_volume_approx']}, {int(r['wordcount'] or 0):,} words)")
    lines += ["", "### `partial` (a source states that only part of the work is translated)", ""]
    for r in rows:
        if r["translation_status"] == "partial" and r["edition_suffix"].endswith("grc1"):
            lines.append(f"- {r['tlg_number']} *{r['title']}*: {r['translation_note']}")
    lines += ["", "### `unknown` (the sources disagree or are silent; not a claim either way)", ""]
    for r in rows:
        if r["translation_status"] == "unknown" and r["edition_suffix"].endswith("grc1"):
            lines.append(f"- {r['tlg_number']} *{r['title']}*: {r['translation_note']}")
    lines += ["", "## Method", "",
              "1. **Galenus verbatim catalogue** (Rousseau, Glorieux, Taaffe; https://galenus-verbatim.github.io/mera-galeni-folia/), fetched 2026-11-09 and parsed into `translation_sources/galenus_verbatim_catalogue_2026-11-09.json`: per work the Fichtner entry number, the Kühn locus, the critical editions and the *translationes recentiores*, each with ISO-639 language codes (e.g. `Singer, 1997 (grc;eng)`). The codes decide the status: any `eng` → `english`; any other modern language → `other_modern`; only `lat` → `latin_only`.",
              "2. **Fichtner, *Corpus Galenicum*** (BBAW, edition 2023/12, https://cmg.bbaw.de/fileadmin/Webdateien/Dateien/Galen-Bibliographie.pdf), text extracted from the PDF and parsed per entry into `translation_sources/fichtner_translations_2026-11-09.json`: the lines tagged `T` (translation; also `E,T`, `T,K`) joined to the work by its `TLG-ID` line, or by Fichtner's entry number via Galenus verbatim where the TLG id did not parse. Fichtner does not code the language, so a Fichtner T line alone never yields `english`/`other_modern`: a work with no GV translation and at least one Fichtner T line is `unknown`, and the lines are quoted in `translation_source` for a reader to judge. A work with no GV translation and no Fichtner T line is `none`.",
              "3. **Overrides** (`translation_sources/overrides.csv`), each with its citation: Johnston & Papavramidou 2024 (*Galen on the Pulses*, De Gruyter, doi:10.1515/9783110612677) for the four long pulse treatises (GV lists it under tlg059 only); the partial translations named in the research pass `drafts/untranslated_galen_research.md` (Simples bk I ch. 1–3 French; Composition by Place bk II Spanish; Victu acutorum bk I French; Aphorisms commentary bk VI Italian); Composition by Kind confirmed `none` by Fichtner entry 82 and Zainaldin et al. 2026 (arXiv:2602.24119).",
              "4. Kühn's own facing Latin (present for every Kühn work) and the medieval Arabic, Syriac, Hebrew and Latin versions Fichtner lists under *Übers.* are not counted as translations. `partial` is assigned only where a source states partial coverage; the catalogues do not code completeness, so an `english`/`other_modern` listing may in fact be a selection (the note says so on every such row).",
              "5. Works in the census but in neither catalogue, and pseudo-Galenic works (tlg0530, JSON only) with no catalogue data, are `unknown`.", "",
              "## Known limits", "",
              "- The catalogues are incomplete (the 2024 pulse volume was missing from GV for three of four works; found by the research pass). A `none` is a statement about two catalogues on 2026-11-09, not a proof.",
              "- German medical dissertations in Fichtner's T lines are often translations of a few chapters; they are quoted, not classified.",
              "- The Cambridge Galen Translations series, Johnston's Loebs and Singer's volumes enter only through the catalogues' listings (GV lists Johnston 2016/2018/2020, Singer 1997/2013, van der Eijk 2018 under the works they cover); no independent table of contents was consulted.", ""]
    README.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(data["translation_status_summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
