"""Tests for the cross-work term index (pipeline/firstdrafts/term_index.py).

Synthetic term-table rows for the keying, the per-work summaries, the divergence flags, the grouping heuristic and the
ranking; a temporary drafts page for the anchor scan; and data-dependent checks against the 13 published Galen works
(skipped when their term tables or pages are not in the checkout).
"""
import csv
import json
import re
import sys
from pathlib import Path

import pytest

GDM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GDM / "pipeline"))
sys.path.insert(0, str(GDM / "pipeline" / "firstdrafts"))
sys.path.insert(0, str(GDM / "pipeline" / "mt2026"))

import term_index as T  # noqa: E402
from common import REPO, out_dir  # noqa: E402


def row(work, unit, lemma, a, b, entry="n1", page="1", pos="NOUN", gloss="first sense", text="", na=None, nb=None):
    from score_consistency import norm
    na = norm(a) if na is None else na
    nb = norm(b) if nb is None else nb
    return {"work": work, "unit_id": unit, "dilemma_lemma": lemma, "odycy_lemma": lemma, "pos": pos, "page": page,
            "lsj_entry_id": entry, "lsj_headword": lemma, "lsj_key": "x", "lsj_sense_count": "2", "lsj_entry_text": text,
            "lsj_first_sense_gloss": gloss, "rendering_A": a, "rendering_B": b, "norm_A": na, "norm_B": nb,
            "agree": "" if not (a and b) else ("y" if na == nb else "n")}


def anchors_for(rows):
    out = {}
    for r in rows:
        out.setdefault(r["work"], {})[r["unit_id"]] = "index.html"
    return out


def test_lemma_key_entry_then_lemma():
    assert T.lemma_key({"lsj_entry_id": "n5", "dilemma_lemma": "a", "odycy_lemma": "b"}) == "n5"
    assert T.lemma_key({"lsj_entry_id": "", "dilemma_lemma": "", "odycy_lemma": "b"}) == "lemma:b"
    k = lambda l: T.lemma_key({"lsj_entry_id": "", "dilemma_lemma": l, "odycy_lemma": l})  # noqa: E731
    assert k("καταγματικός") == k("καταγματῖκός") == "lemma:καταγματικοσ"


def test_modal_is_deterministic_on_ties():
    from collections import Counter
    assert T.modal(Counter({"b": 2, "a": 2, "c": 1})) == "a"
    assert T.modal(Counter()) == ""


def test_core_merges_degree_and_adverb_forms():
    assert T.core("more rarely") == T.core("rare") == T.core("rarer")
    assert T.core("complete most") == T.core("complete")
    assert T.core("drier") == T.core("dry")
    assert T.core("hotter") == T.core("hot")
    assert T.core("nerve") != T.core("sinew")
    assert T.core("") == ""


def test_clean_gloss_drops_fragments():
    assert T.clean_gloss("deep sleep") == "deep sleep"
    for junk in ("cf", "etc", "cf. εἷς)", "is dub.)", "etc.)", ""):
        assert T.clean_gloss(junk) == ""


def test_variants_of_one_entry_fall_together():
    rows = [row("de-comate", "K7.643", "πτύελον", "sputum", "sputum"), row("de-comate", "K7.644", "πτύελος", "sputum", "spittle")]
    ix = T.build(rows, anchors_for(rows))
    assert len(ix["lemmas"]) == 1
    r = ix["lemmas"][0]
    assert r["variants"] == ["πτύελον", "πτύελος"] and r["n"] == 2 and r["n_works"] == 1
    assert r["diverges"] is None  # one work: no cross-work verdict
    w = r["works"][0]
    assert w["modal"] == "sputum" and w["A"] == [["sputum", "sputum", 2]] and w["agree_ab"] == 1 and w["both_ab"] == 2


def test_divergence_across_works_and_per_model():
    rows = [row("de-comate", "K7.643", "ἀραιός", "rare", "loose-textured", entry="n9"),
            row("de-comate", "K7.644", "ἀραιός", "rare", "rare", entry="n9"),
            row("hirudinibus", "K11.317", "ἀραιός", "loose-textured", "loose-textured", entry="n9"),
            row("hirudinibus", "K11.318", "ἀραιός", "loose-textured", "loose-textured", entry="n9")]
    r = T.build(rows, anchors_for(rows))["lemmas"][0]
    assert r["diverges"] is True and r["diverges_surface"] is True
    assert r["cross_work_agreement"] == 0.5 and r["distinct_modal"] == 2
    assert r["flag_A"] is True   # A: rare in one work, loose-textured in the other
    assert r["flag_B"] is False  # B: a 1-1 tie in de-comate goes to the alphabetically first, "loose textured", as in hirudinibus
    assert {p["work"]: p["modal"] for p in r["works"]} == {"de-comate": "rare", "hirudinibus": "loose textured"}


def test_degree_forms_do_not_diverge():
    rows = [row("de-comate", "K7.643", "θερμός", "hot", "hot", entry="n3", pos="ADJ"),
            row("hirudinibus", "K11.317", "θερμός", "hotter", "hotter", entry="n3", pos="ADJ")]
    r = T.build(rows, anchors_for(rows))["lemmas"][0]
    assert r["diverges_surface"] is True and r["diverges"] is False and r["cross_work_agreement"] == 1.0


def test_empty_renderings_do_not_count():
    rows = [row("de-comate", "K7.643", "λ", "", "", entry="n4"), row("hirudinibus", "K11.317", "λ", "word", "word", entry="n4")]
    r = T.build(rows, anchors_for(rows))["lemmas"][0]
    assert r["diverges"] is None and r["works"][0]["modal"] == ""


def test_kuhn_citation_and_missing_anchor():
    rows = [row("de-comate", "K7.650", "κῶμα", "coma", "coma", page="650")]
    ix = T.build(rows, {"de-comate": {}})
    loc = ix["lemmas"][0]["works"][0]["loci"][0]
    assert loc["kuhn"] == "K. VII 650" and loc["file"] == ""
    assert ix["missing_anchors"] == [("de-comate", "K7.650")]


def test_cycle1_gloss_filled_from_same_entry():
    rows = [row("adversus-lycum", "K18a.196", "κῶμα", "coma", "coma", entry="n7", gloss=""),
            row("de-comate", "K7.643", "κῶμα", "coma", "coma", entry="n7", gloss="deep sleep")]
    rows[0].pop("lsj_first_sense_gloss")
    assert T.build(rows, anchors_for(rows))["lemmas"][0]["lsj_first_sense"] == "deep sleep"


@pytest.mark.parametrize("pos,rend,gloss,text,group", [
    ("NOUN", ["plaster"], "", "", "drugs"),
    ("NOUN", ["vein"], "", "", "anatomy"),
    ("NOUN", ["fever"], "", "", "diseases"),
    ("ADJ", ["astringent"], "", "", "qualities"),
    ("ADJ", ["arm"], "", "", "other"),                      # an adjective is never anatomy
    ("NOUN", ["summary"], "of the head", "head", "other"),  # the entry alone does not decide
    ("NOUN", ["chief point"], "", "", "other"),
])
def test_classify(pos, rend, gloss, text, group):
    assert T.classify(pos, rend, gloss, text)[0] == group


def test_rank_needs_works_with_two_occurrences_and_drops_other_adjectives():
    def lem(lemma, pos, group, works):
        return {"lemma": lemma, "pos": pos, "group": group, "n": sum(n for _, n in works), "diverges": True,
                "works": [{"modal_core": m, "n": n} for m, n in works]}
    a = lem("α", "NOUN", "other", [("x", 2), ("y", 2), ("z", 2)])
    b = lem("β", "NOUN", "drugs", [("x", 2), ("x", 2), ("y", 2)])
    c = lem("γ", "NOUN", "drugs", [("x", 2), ("y", 1), ("z", 1)])   # only one work with n >= 2
    d = lem("δ", "ADJ", "other", [("x", 2), ("y", 2), ("z", 2)])    # quantity adjective
    got = T.inconsistency_rank([b, c, d, a])
    assert [r["lemma"] for r in got] == ["α", "β"]
    assert got[0]["rank_agreement"] == pytest.approx(1 / 3) or got[0]["rank_agreement"] == 0.333
    assert [r["lemma"] for r in T.inconsistency_rank([d], terms_only=False)] == ["δ"]


def test_page_anchors_reads_book_pages(tmp_path):
    d = tmp_path / "w"
    d.mkdir()
    (d / "index.html").write_text('<div class="unit " id="K1.1">', encoding="utf-8")
    (d / "book-2.html").write_text('<div class="unit fail" id="K1.2-3">x</div><div class="unit " id="K1.4">', encoding="utf-8")
    assert T.page_anchors("w", tmp_path) == {"K1.1": "index.html", "K1.2-3": "book-2.html", "K1.4": "book-2.html"}
    assert T.page_anchors("missing", tmp_path) == {}


def test_outputs_and_page(tmp_path):
    rows = [row("de-comate", "K7.643", "κῶμα", "coma", "coma", entry="n7", page="643"),
            row("hirudinibus", "K11.317", "κῶμα", "lethargy </script>", "coma", entry="n7", page="317")]
    ix = T.build(rows, anchors_for(rows))
    sm = T.write_outputs(ix, tmp_path / "out")
    assert sm["lemmas"] == 1 and sm["occurrences"] == 2 and sm["missing_anchors"] == 0 and sm["units_cited"] == 2
    occ = list(csv.DictReader((tmp_path / "out" / "term_occurrences.csv").open(encoding="utf-8")))
    assert [o["anchor"] for o in occ] == ["de-comate/index.html#K7.643", "hirudinibus/index.html#K11.317"]
    per = list(csv.DictReader((tmp_path / "out" / "term_index.csv").open(encoding="utf-8")))
    assert len(per) == 2 and per[0]["kuhn_loci"] == "K. VII 643"
    p = T.write_page(ix, sm, tmp_path / "page", base="../")
    h = p.read_text(encoding="utf-8")
    m = re.search(r'<script id=d type="application/json">(.*?)</script>', h, re.S)
    data = json.loads(m.group(1))   # the </script> inside a rendering is escaped, so the JSON block is whole
    assert data["lemmas"][0][0] == "κῶμα" and len(data["lemmas"][0][11]) == 2
    assert "docs/" not in str(p)


# ---------------------------------------------------------------- data-dependent (the published works)

HAVE_DATA = (out_dir("de-comate") / "term_table.csv").exists() and (REPO / "docs" / "first-drafts" / "de-comate" / "index.html").exists()


@pytest.mark.skipif(not HAVE_DATA, reason="term tables or drafts pages not in this checkout")
def test_real_index_every_locus_has_an_anchor():
    slugs = T.galen_slugs()
    assert len(slugs) == 13
    rows = T.read_rows(slugs)
    anchors = {s: T.page_anchors(s, REPO / "docs" / "first-drafts") for s in slugs}
    ix = T.build(rows, anchors)
    assert ix["missing_anchors"] == []
    assert sum(r["n"] for r in ix["lemmas"]) == len(rows)
    # every page file cited exists and holds the anchor
    texts = {}
    for r in ix["lemmas"]:
        for p in r["works"]:
            for l in p["loci"]:
                f = REPO / "docs" / "first-drafts" / p["work"] / l["file"]
                if f not in texts:
                    texts[f] = f.read_text(encoding="utf-8")
                assert f'id="{l["unit"]}"' in texts[f]
