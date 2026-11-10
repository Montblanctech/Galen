"""MW-Gold, stage 0 — parse the Cologne Monier-Williams (1899) digitization and extract its text citations.

Source: data/sanskrit_feasibility/mw_src/mw.txt (sanskrit-lexicon/csl-orig, v02/mw/mw.txt, CC BY-SA 4.0). Format
(mw-meta2.txt): one entry per `<L>id<pc>page<k1>key<k2>key2[<h>hom]<e>level` meta line + body + `<LEND>`; k1/k2 are
SLP1 (k2 keeps the hyphenation of compounds: `karaRa—grAma`); citations are `<ls>Abbr. locus</ls>` or, for a
continued citation to the same text, `<ls n="Abbr.">locus</ls>` / `<ls n="Mn. viii,">52</ls>` (the n attribute
carries the omitted prefix).

A locus is kept when it carries at least one digit; its segments are split on commas and converted (Roman -> int,
`1 f.`, `1 ff.`, `1-3` -> first number, trailing letters `a`/`b` dropped but recorded). The abbreviation is taken
as the leading dotted tokens (`Kathās.`, `ŚāṅkhŚr.`, `R. (ed. Gorr.)` -> `R.` with edition note `Gorr.`).

Outputs (both under data/sanskrit_feasibility/): mw_citations.jsonl (one line per locus-bearing citation:
entry id L, k1, k2, hom, headword IAST, members IAST, abbrev, locus string, parts) and mw_citation_census.json
(per abbreviation: total citations, with locus, parsed, locus depth histogram, examples).

Run (.venv-skt): python -X utf8 -I pipeline/mwgold/mw_parse.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
FEAS = GDM / "data" / "sanskrit_feasibility"
MW_TXT = FEAS / "mw_src" / "mw.txt"

sys.path.insert(0, str(HERE))
from sktnorm import slp1_to_iast  # noqa: E402

META_RE = re.compile(r"<L>(?P<L>\S+?)<pc>(?P<pc>\S+?)<k1>(?P<k1>\S+?)<k2>(?P<k2>\S+?)(?:<h>(?P<h>\S+?))?<e>(?P<e>\S+)")
LS_RE = re.compile(r'<ls(?:\s+n="(?P<n>[^"]*)")?>(?P<body>[^<]*)</ls>')
ABBR_RE = re.compile(r"^\s*(?P<ab>(?:[A-ZĀĪŪṚṢŚṬḌṄÑṆḤ][A-Za-zĀāĪīŪūṚṛṢṣŚśṬṭḌḍṄṅÑñṆṇḤḥṂṃ'’]*\.\s?)+)(?P<rest>.*)$")
ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
ROMAN_RE = re.compile(r"^[ivxlcdm]+$")
EDNOTE_RE = re.compile(r"\((?:ed\.\s*)?([^)]*)\)")


def roman(s: str) -> int | None:
    s = s.lower()
    if not ROMAN_RE.match(s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def parse_locus(rest: str) -> tuple[str, list[int | str], str]:
    """'iii, 1234.' -> ('iii, 1234', [3, 1234], ''); 'i, 45, 7, 3' -> [1,45,7,3]; returns (clean, parts, note).
    Letters that qualify a number (a/b pāda, 'f.', 'ff.', 'sq.') are stripped; a range keeps its first number;
    text in parentheses becomes the note (edition remarks such as '(ed. Gorr.)' or '(B.)')."""
    note = ""
    m = EDNOTE_RE.search(rest)
    if m:
        note = m.group(1).strip()
        rest = EDNOTE_RE.sub(" ", rest)
    rest = rest.replace("&c.", " ").replace("sqq.", " ").replace("sq.", " ").replace("ff.", " ").replace("f.", " ")
    rest = rest.strip().rstrip(".;,: ").strip()
    parts: list[int | str] = []
    for seg in re.split(r"\s*[,;]\s*", rest):
        seg = seg.strip().strip(".")
        if not seg:
            continue
        seg = re.sub(r"[-–—]\s*\d+[a-z]?$", "", seg)      # range -> first number
        seg = re.sub(r"(?<=\d)[a-z]$", "", seg)            # 12a -> 12
        seg = seg.strip()
        if seg.isdigit():
            parts.append(int(seg))
        elif roman(seg) is not None:
            parts.append(roman(seg))
        else:
            parts.append(seg)                              # leave words (Introd., Sū., Utt. ...) as strings
    return rest, parts, note


def headword_members(k2: str) -> list[str]:
    """Compound members from k2's hyphenation (`karaRa—grAma`, `a—kAra`; accents '/' and '\\' dropped)."""
    k = re.sub(r"[/\\^]", "", k2)
    return [m for m in re.split(r"[—-]", k) if m]


def entries(text: str):
    for block in text.split("<LEND>"):
        m = META_RE.search(block)
        if not m:
            continue
        body = block[m.end():]
        yield m.groupdict(), body


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    text = MW_TXT.read_text(encoding="utf-8")
    out = FEAS / "mw_citations.jsonl"
    census: dict[str, dict] = defaultdict(lambda: {"total": 0, "with_locus": 0, "depth": Counter(), "examples": [], "notes": Counter()})
    n_entries = n_tags = n_kept = 0
    unparsed: Counter = Counter()
    with out.open("w", encoding="utf-8") as fh:
        for meta, body in entries(text):
            n_entries += 1
            members = headword_members(meta["k2"])
            hw = slp1_to_iast(meta["k1"])
            for ls in LS_RE.finditer(body):
                n_tags += 1
                n_attr, b = ls.group("n"), ls.group("body")
                if n_attr:
                    pref = n_attr.strip()
                    m = ABBR_RE.match(pref)
                    if not m:
                        unparsed[pref[:20]] += 1
                        continue
                    ab = re.sub(r"\s+", "", m.group("ab"))
                    rest = (m.group("rest") + " " + b).strip()
                else:
                    m = ABBR_RE.match(b)
                    if not m:
                        unparsed[b.strip()[:20]] += 1
                        continue
                    ab = re.sub(r"\s+", "", m.group("ab"))
                    rest = m.group("rest")
                c = census[ab]
                c["total"] += 1
                if not re.search(r"\d", rest):
                    continue
                clean, parts, note = parse_locus(rest)
                nums = [p for p in parts if isinstance(p, int)]
                if not nums:
                    continue
                c["with_locus"] += 1
                c["depth"][len(parts)] += 1
                if note:
                    c["notes"][note] += 1
                if len(c["examples"]) < 5:
                    c["examples"].append(clean)
                n_kept += 1
                fh.write(json.dumps({"L": meta["L"], "k1": meta["k1"], "k2": meta["k2"], "hom": meta["h"] or "", "level": meta["e"],
                                     "headword": hw, "members": [slp1_to_iast(x) for x in members], "abbrev": ab, "locus": clean,
                                     "parts": parts, "note": note}, ensure_ascii=False) + "\n")
    cen = {ab: {"total": c["total"], "with_locus": c["with_locus"], "depth": dict(c["depth"]), "examples": c["examples"],
                "edition_notes": dict(c["notes"].most_common(8))} for ab, c in sorted(census.items(), key=lambda kv: -kv[1]["with_locus"])}
    summary = {"entries": n_entries, "ls_tags": n_tags, "citations_with_locus": n_kept, "abbreviations": len(cen),
               "unparsed_tags": sum(unparsed.values()), "unparsed_top": unparsed.most_common(12), "by_abbrev": cen}
    (FEAS / "mw_citation_census.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"entries {n_entries}; <ls> tags {n_tags}; citations with a numeric locus {n_kept}; abbreviations {len(cen)}; unparsed {sum(unparsed.values())}")
    for ab, c in list(cen.items())[:40]:
        print(f"{ab:14s} total {c['total']:6d} locus {c['with_locus']:6d} depth {c['depth']} e.g. {c['examples'][:2]} {c['edition_notes'] if c['edition_notes'] else ''}")


if __name__ == "__main__":
    main()
