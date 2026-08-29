"""Kühn vol/page alignment tests and token-stream alignment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from h3m.align import align_surfaces
from h3m.kuhn_ref import parse_kuhn_ref


def test_kuhn_plain():
    r = parse_kuhn_ref("11.46")
    assert r is not None
    assert r.volume == 11 and r.page == 46 and r.part is None


def test_kuhn_split_volume():
    r = parse_kuhn_ref("18(1).793")
    assert r is not None
    assert r.volume == 18 and r.part == 1 and r.page == 793
    r2 = parse_kuhn_ref("Gal. 17(2).337")
    assert r2 is not None and r2.volume == 17 and r2.part == 2 and r2.page == 337


def test_kuhn_comma_and_spaces():
    r = parse_kuhn_ref("4, 763")
    assert r is not None and r.volume == 4 and r.page == 763


def test_align_identical():
    pairs, stats = align_surfaces(["α", "β", "γ"], ["α", "β", "γ"])
    assert len(pairs) == 3
    assert stats["alignment_loss_a"] == 0
    assert not stats["flag_alignment_loss"]


def test_align_divergent_region():
    a = ["α", "β", "γ", "δ", "ε"]
    b = ["α", "xxx", "γ", "δ", "ε"]
    pairs, stats = align_surfaces(a, b, window=4)
    aligned_a = [i for i, _ in pairs]
    assert 0 in aligned_a and 2 in aligned_a
    assert stats["alignment_loss_a"] > 0
    assert stats["alignment_loss_a"] < 0.5


LSJ_SNIPPET = """
<entryFree key="a)baqh/s" type="main">
  <sense>
    <cit>
      <quote lang="greek">nu\\c a).</quote>
      <bibl>
        <author>Gal.</author>
        <biblScope>19.481</biblScope>
      </bibl>
    </cit>
    <bibl>
      <author>Gal.</author>
      <biblScope>5.122</biblScope>
    </bibl>
  </sense>
</entryFree>
"""


def test_lsj_gal_citation_extract():
    from lxml import etree
    from h3m.m3_lsj_gold import extract_citations_from_entry

    entry = etree.fromstring(LSJ_SNIPPET.encode("utf-8"))
    rows = extract_citations_from_entry(entry)
    vols_pages = {(r["kuhn_volume"], r["kuhn_page"]) for r in rows}
    assert (19, 481) in vols_pages
    assert (5, 122) in vols_pages
    quoted = [r for r in rows if r["kuhn_page"] == 481][0]
    assert quoted["quoted_form"]  # converted from Beta Code
    assert "ἀβαθ" in quoted["headword"] or quoted["headword"]

