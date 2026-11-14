import pytest

from conftest import no_local_paths
from galen_mcp.core import HONESTY, ToolError

PAGES = "https://montblanctech.github.io/Galen/"
CONCISE_MAX = 6000  # chars, i.e. about 1,500 tokens


def tok(s: str) -> int:
    return len(s) // 4


# ------------------------------------------------------------------ list_works
def test_list_works(galen):
    out = galen.list_works()
    assert out.count("\n- ") == 14
    assert "hirudinibus · K. XI 317–322" in out and "in-hipp-acut · K. XV 514–919, books 2–4" in out
    assert PAGES + "first-drafts/hirudinibus/" in out
    assert "no scholar has reviewed" in out
    assert tok(out) < 1500 and no_local_paths(out)
    full = galen.list_works("full")
    assert "earlier translations:" in full and len(full) > len(out)


def test_bad_detail(galen):
    with pytest.raises(ToolError, match='"concise" or "full"'):
        galen.list_works("everything")


# ------------------------------------------------------------------ get_passage
@pytest.mark.parametrize("cit", ["K15.609", "K. XV 609", "Kühn XV, 609", "15.609"])
def test_passage_by_kuhn_page(galen, cit):
    out = galen.get_passage(cit)
    first = out.splitlines()[0]
    assert first.startswith("K15.609-610 · in-hipp-acut, book 2 · K. XV 609–610")
    assert f"Page: {PAGES}first-drafts/in-hipp-acut/book-2.html#K15.609-610" in out
    assert "\nGreek: " in out and "\nA: " in out and "\nB: " in out
    assert "Checks (automatic, not a review): unit pass" in out
    assert "Also on that page: K15.608-609" in out and "Next: K15.610-611" in out
    assert out.endswith(HONESTY)
    assert len(out) < CONCISE_MAX and no_local_paths(out)


def test_passage_by_unit_id_and_work(galen):
    out = galen.get_passage("K11.317-318", work="hirudinibus")
    assert out.startswith("K11.317-318 · hirudinibus")
    assert f"{PAGES}first-drafts/hirudinibus/#K11.317-318" in out  # single-page work: no book file
    assert "Prev: K11.317" in out


def test_passage_full_has_key_terms(galen):
    c = galen.get_passage("K11.317")
    f = galen.get_passage("K11.317", detail="full")
    assert "Key terms" in f and "Key terms" not in c
    assert "A (claude-" in f and "(a) A: term recall" in f
    assert "ὄνυξ" in f


def test_passage_typo_gives_nearest(galen):
    with pytest.raises(ToolError) as e:
        galen.get_passage("K15.6091")
    msg = str(e.value)
    assert msg.startswith("no unit at K15.6091; nearest: K15.609-610")
    assert "514–919 (in-hipp-acut)" in msg


def test_passage_uncovered_volume(galen):
    with pytest.raises(ToolError, match="no First Draft covers Kühn vol. III; covered volumes: VII, XI, XIII, XV, XVIIIA"):
        galen.get_passage("K3.100")


def test_passage_wrong_work_and_garbage(galen):
    with pytest.raises(ToolError, match="hirudinibus is not in Kühn vol. XV; it covers K. XI 317–322"):
        galen.get_passage("K15.609", work="hirudinibus")
    with pytest.raises(ToolError, match="could not read"):
        galen.get_passage("the chapter on leeches")
    with pytest.raises(ToolError, match='no work "nope"'):
        galen.get_passage("K15.609", work="nope")


def test_passage_work_by_title_fragment(galen):
    assert galen.get_passage("K11.317", work="leeches").startswith("K11.317 · hirudinibus")


def test_passage_vitruvius(galen):
    out = galen.get_passage("Vitr.3.1.5")
    assert out.startswith("Vitr.3.1.5 · vitruvius-3")
    assert "\nLatin: " in out and f"{PAGES}method/vitruvius-3/#Vitr.3.1.5" in out
    # a section inside a multi-section unit
    assert galen.get_passage("3.2.1", work="vitruvius-3").startswith("Vitr.3.1.9-3.2.2")
    with pytest.raises(ToolError, match="no unit at Vitr.9.9.9"):
        galen.get_passage("Vitr.9.9.9")


# ------------------------------------------------------------------ search_terms
def test_search_greek_accentless(galen):
    out = galen.search_terms("νευρον")
    assert "- νεῦρον · NOUN · LSJ \"sinew\"" in out and "matched Greek" in out
    assert "usual: nerves (5 works), sinews (1 work)" in out
    assert f"{PAGES}first-drafts/terms/#q=" in out and out.endswith(HONESTY)


def test_search_english_and_beta(galen):
    assert galen.search_terms("acrid").splitlines()[1].startswith("- δριμύς")
    assert galen.search_terms("nerve").splitlines()[1].startswith("- νεῦρον")
    assert "γνώρισμα" in galen.search_terms("gnw/risma")
    assert "χυμός" in galen.search_terms("humour")


def test_search_paging(galen):
    out = galen.search_terms("ο", limit=3)  # Greek part-match: many hits
    assert out.count("\n- ") == 3 and "more; pass offset=3" in out
    nxt = galen.search_terms("ο", limit=3, offset=3)
    assert "(showing 4–6" in nxt
    with pytest.raises(ToolError, match="past the end"):
        galen.search_terms("ο", offset=10_000)


def test_search_no_hit_and_empty(galen):
    assert galen.search_terms("zzzqqq").startswith('no target term matches "zzzqqq"')
    with pytest.raises(ToolError, match="give a query"):
        galen.search_terms("  ")


# ------------------------------------------------------------------ get_term
def test_term_concise(galen):
    out = galen.get_term("γνωρισμα")
    lines = out.splitlines()
    assert lines[0].startswith("γνώρισμα · NOUN · LSJ \"that by which a thing is made known\"")
    assert "25× in 7 works" in lines[0]
    assert any(l.startswith("- in-hipp-acut 7×: A signs 7 | B recognisable signs 7 | A=B 0/7") for l in lines)
    assert "differs across works" in out and out.endswith(HONESTY)
    assert len(out) < CONCISE_MAX and no_local_paths(out)


def test_term_full_pages(galen):
    out = galen.get_term("δριμύς", detail="full")
    assert out.count("\n- ") == 40 and "44 more; pass offset=40" in out
    assert f"{PAGES}first-drafts/comp-per-genera/book-1.html#K13.410-411" in out
    last = galen.get_term("δριμύς", detail="full", offset=80)
    assert last.count("\n- ") == 4 and "more;" not in last


def test_term_full_with_work_sentences(galen):
    out = galen.get_term("ὄνυξ", work="hirudinibus", detail="full")
    assert "- K11.317 ὄνυξι: A nails = B nails" in out
    assert "τοῖς ὄνυξι" in out and "  A: At the time of use" in out


def test_term_errors(galen):
    with pytest.raises(ToolError, match="closest: "):
        galen.get_term("νευρ")
    with pytest.raises(ToolError, match="is not a target term in hirudinibus; it occurs in: "):
        galen.get_term("γνώρισμα", work="hirudinibus")


def test_term_latin_method_work(galen):
    out = galen.get_term("symmetria", work="vitruvius-3")
    assert out.startswith("symmetria · NOUN · Lewis & Short")
    with pytest.raises(ToolError, match="commonest target terms"):
        galen.get_term("columna", work="vitruvius-3")


# ------------------------------------------------------------------ lsj_gold_lemma
def test_gold_greek(galen):
    out = galen.lsj_gold_lemma("ἀᾶται")
    assert out.startswith("ἀᾶται → ἀάω (1 of 1 loci, e.g. Homer (tlg0012.tlg001) 19:91)")
    assert "LSJ-Gold 1.0" in out and PAGES + "lsj-gold/" in out
    blind = galen.lsj_gold_lemma("αγαθον")
    assert blind.startswith("No exact form αγαθον; accent/case-blind: ") and "→ ἀγαθός" in blind
    assert "itself a headword in LSJ" not in blind


def test_gold_headword_and_latin(galen):
    assert "is itself a headword in LSJ" in galen.lsj_gold_lemma("ἀγαθός")
    out = galen.lsj_gold_lemma("abdicavit")
    assert out.startswith("abdicavit → ab-dico") and "LS-Gold 1.0" in out and "Pliny" in out


def test_gold_miss(galen):
    with pytest.raises(ToolError, match="is not among the LSJ-Gold 1.0 forms"):
        galen.lsj_gold_lemma("ξξξ")
