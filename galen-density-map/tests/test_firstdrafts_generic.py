"""Tests for the generic First Drafts front end (pipeline/firstdrafts/generic.py): TEI tokenizer + unit splitter.

Synthetic TEI for the two unit modes (page breaks snapped to sentence ends, as for Kühn pages; section divs, as for a
Perseus Latin edition), the Latin sentence-end rule, and a data-dependent regression against a published Galen work.
"""
import json
import sys
from pathlib import Path

import pytest

GDM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GDM / "pipeline"))
sys.path.insert(0, str(GDM / "pipeline" / "firstdrafts"))

import generic  # noqa: E402

TEI = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><title>x</title></teiHeader><text><body><div type="edition">{}</div></body></text></TEI>'


def write_tei(tmp_path, body: str) -> Path:
    p = tmp_path / "t.xml"
    p.write_text(TEI.format(body), encoding="utf-8")
    return p


def units_of(toks, bounds):
    return [[t["surface"] for t in toks[a:b]] for a, b in zip(bounds, bounds[1:])]


def pb_cfg(min_tokens=1):
    cfg = generic.galen_config("adversus-lycum")
    cfg["unit"]["min_tokens"] = min_tokens
    return cfg


def test_page_break_snaps_back_to_sentence_end(tmp_path):
    xml = write_tei(tmp_path, '<div type="textpart" subtype="chapter" n="1"><p><pb n="10"/>α β. γ δ <pb n="11"/>ε ζ. η θ.</p></div>')
    cfg = pb_cfg()
    toks = generic.tei_tokens(xml, cfg)
    assert [t["surface"] for t in toks] == ["[10]", "α", "β.", "γ", "δ", "[11]", "ε", "ζ.", "η", "θ."]
    assert toks[3]["page"] == "10" and toks[6]["page"] == "11" and toks[1]["chapter"] == "1"
    bounds = generic.unit_boundaries(toks, cfg["unit"])
    # the break at [11] falls mid-sentence ('γ δ [11] ε ζ.'), so the unit boundary moves back to after 'β.'
    assert units_of(toks, bounds) == [["[10]", "α", "β."], ["γ", "δ", "[11]", "ε", "ζ.", "η", "θ."]]


def test_break_without_sentence_end_cuts_at_the_break_and_short_units_merge(tmp_path):
    xml = write_tei(tmp_path, '<p><pb n="1"/>a b c <pb n="2"/>d e. f <pb n="3"/>g h.</p>')
    cfg = pb_cfg()
    toks = generic.tei_tokens(xml, cfg)
    b1 = generic.unit_boundaries(toks, cfg["unit"])
    assert units_of(toks, b1) == [["[1]", "a", "b", "c"], ["[2]", "d", "e."], ["f", "[3]", "g", "h."]]
    cfg["unit"]["min_tokens"] = 4   # the 3-token middle unit merges forward into the next one
    b2 = generic.unit_boundaries(toks, cfg["unit"])
    assert units_of(toks, b2) == [["[1]", "a", "b", "c"], ["[2]", "d", "e.", "f", "[3]", "g", "h."]]


def test_trailing_page_break_with_no_words_joins_previous_unit(tmp_path):
    xml = write_tei(tmp_path, '<p><pb n="1"/>a b. c d.<pb n="2"/></p>')
    cfg = pb_cfg()
    toks = generic.tei_tokens(xml, cfg)
    assert units_of(toks, generic.unit_boundaries(toks, cfg["unit"])) == [["[1]", "a", "b.", "c", "d.", "[2]"]]


SECTION_UNIT = {
    "break": {"tag": "div", "match": {"subtype": "section"}, "attr": "n", "ref": "{book}.{chapter}.{n}"},
    "levels": [{"name": "book", "tag": "div", "match": {"subtype": "book"}, "attr": "n"},
               {"name": "chapter", "tag": "div", "match": {"subtype": "chapter"}, "attr": "n"}],
    "reset_ref_on_level": True, "sentence_end": [".", "?", "!"], "sentence_end_strip": ")]\"'",
    "not_sentence_end_re": r"^(?:[A-Z]|Cn|Sp)\.$", "min_tokens": 1,
    "id": {"prefix": "X.", "range": "-"}, "locus": {"prefix": "X ", "range": "–"},
}


def lat_cfg(**unit):
    return {"lang": "lat", "text": {"normalize": "nfc", "skip": ["note", "app", "rdg", "teiHeader", "del"]},
            "unit": {**generic.DEFAULT_UNIT, **SECTION_UNIT, **unit}}


def test_section_divs_give_hierarchical_refs_and_skip_notes_but_keep_tails(tmp_path):
    body = ('<div type="textpart" subtype="book" n="3"><head>LIBER III</head>'
            '<div type="textpart" subtype="chapter" n="pr"><div type="textpart" subtype="section" n="1">'
            '<p>Una duae <del>falsa</del> tres. <!-- c --> quattuor<note>n</note> quinque.</p></div>'
            '<div type="textpart" subtype="section" n="2"><p>Sex septem.</p></div></div>'
            '<div type="textpart" subtype="chapter" n="1"><div type="textpart" subtype="section" n="1"><p>Octo novem.</p></div></div></div>')
    xml = write_tei(tmp_path, body)
    cfg = lat_cfg()
    toks = generic.tei_tokens(xml, cfg)
    surf = [t["surface"] for t in toks]
    assert surf == ["LIBER", "III", "[3.pr.1]", "Una", "duae", "tres.", "quattuor", "quinque.", "[3.pr.2]", "Sex", "septem.", "[3.1.1]", "Octo", "novem."]
    head = toks[0]
    assert head["head"] and head["page"] is None and head["book"] == "3"   # ref reset on entering the book div
    assert toks[3]["chapter"] == "3.pr" and toks[12]["chapter"] == "3.1" and toks[12]["page"] == "3.1.1"
    bounds = generic.unit_boundaries(toks, cfg["unit"])
    # the title line joins the first section's unit instead of becoming a unit of its own
    assert units_of(toks, bounds) == [surf[0:8], surf[8:11], surf[11:]]


def test_latin_sentence_end_rule():
    is_end = generic.sentence_end_fn(lat_cfg()["unit"])
    assert is_end("dixit.") and is_end('dixit."') and is_end("dixit.)") and is_end("venit?")
    assert not is_end("C.") and not is_end("Cn.") and not is_end("dixit,") and not is_end("dixit;")
    galen_end = generic.sentence_end_fn(generic.galen_config("adversus-lycum")["unit"])
    assert galen_end("λέγει;") and galen_end("λέγει.") and not galen_end("λέγει·")   # Greek ; is the question mark


def test_ordered_refs():
    assert generic._ordered(["10", None, "9", "10"], "int") == ["9", "10"]
    assert generic._ordered(["3.pr.2", "3.pr.1", "3.pr.2"], "doc") == ["3.pr.2", "3.pr.1"]
    assert generic._ordered(["2.3a", "2.10", "2.3"], "key") == ["2.3", "2.3a", "2.10"]


def test_shipped_configs_load():
    cfg = generic.load_config(GDM / "pipeline" / "firstdrafts" / "configs" / "vitruvius-3.json")
    assert cfg["lang"] == "lat" and cfg["unit"]["break"]["tag"] == "div" and cfg["targets"]["rule"] == "lexicon_rarity"
    g = generic.galen_config("adversus-lycum")
    assert g["unit"]["id"]["prefix"] == "K18a." and g["targets"]["rule"] == "galen" and g["unit"]["min_tokens"] == 25
    shipped = generic.load_config(GDM / "pipeline" / "firstdrafts" / "configs" / "adversus-lycum.json")
    assert {k: shipped[k] for k in ("unit", "tagger", "lexicon", "tei", "text", "profile")} == {k: g[k] for k in ("unit", "tagger", "lexicon", "tei", "text", "profile")}


PUBLISHED = GDM / "outputs" / "firstdrafts" / "adversus-lycum"
NEEDS = [GDM / "data" / "raw_xml" / "urn_cts_greekLit_tlg0057.tlg093.1st1K-grc1.xml",
         GDM / "data" / "lemmatized" / "galen_nonmedical" / "urn_cts_greekLit_tlg0057.tlg093.1st1K-grc1.jsonl", PUBLISHED / "units.jsonl"]


@pytest.mark.skipif(not all(p.exists() for p in NEEDS), reason="needs the Galen TEI, odyCy stream and published units")
def test_galen_config_reproduces_published_adversus_lycum():
    res = generic.build(generic.galen_config("adversus-lycum"))
    old = [json.loads(l) for l in (PUBLISHED / "units.jsonl").open(encoding="utf-8")]
    new = [{k: v for k, v in u.items() if k != "books"} for u in res["units"]]   # 'books' was added to units.py after cycle 1
    assert new == old
    import csv
    assert res["targets"] == [{**r, "target_no": int(r["target_no"])} for r in csv.DictReader((PUBLISHED / "targets.csv").open(encoding="utf-8"))]
