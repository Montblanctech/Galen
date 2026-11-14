"""T2b v1: segmenter, channel, baseline, eval metrics and the Leiden reader, on a toy corpus."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import t2b_scorer as T  # noqa: E402
import t2b_eval as E  # noqa: E402

TOY = [
    "ὁ λόγος ἐστὶν ἀληθής καὶ ὁ λόγος ἐστὶν καλός",
    "καὶ τὴν ψυχὴν ἀθάνατον εἶναι λέγει ὁ λόγος",
    "ὁ ἰατρὸς τὴν ψυχὴν θεραπεύει καὶ τὸ σῶμα",
    "ἡ ψυχὴ ἀθάνατος καὶ ὁ λόγος ἀληθής",
    "τὸ σῶμα καὶ ἡ ψυχή, τὸ σῶμα καὶ ὁ λόγος",
]


@pytest.fixture(scope="module")
def toy(tmp_path_factory):
    d = tmp_path_factory.mktemp("corpus")
    files = []
    for n, t in enumerate(TOY):
        p = d / f"urn_cts_greekLit_tlg9{n:03d}.tlg001.1st1K-grc1.txt"
        p.write_text((t + "\n") * 3, encoding="utf-8")
        files.append(p)
    held = d / "urn_cts_greekLit_tlg8000.tlg001.1st1K-grc1.txt"
    held.write_text("ξενικὸν ῥῆμα μόνον ἐνθάδε\n" * 5, encoding="utf-8")
    files.append(held)
    c = T.build_counts(files, {"tlg8000.tlg001"}, log=lambda m: None)
    return c


def seg_of(c, **kw):
    lex = T.Lexicon(c, min_count=2, channel=kw.pop("channel", True))
    return T.Segmenter(lex, **kw)


def test_to_continua_strips_marks_spaces_and_unifies_sigma():
    assert T.to_continua("ὁ λόγος, καὶ τῷ") == "ΟΛΟΓΟΣΚΑΙΤΩ"
    assert T.to_continua("ΛΟΓΟC ϲοφός") == "ΛΟΓΟΣΣΟΦΟΣ"


def test_continua_words_keep_restored_letters():
    assert T.continua_words("κα[ὶ] λό]γος 〈τὸ〉") == ["ΚΑΙ", "ΛΟΓΟΣ", "ΤΟ"]


def test_work_id_parses_editions_and_letter_suffixed_groups():
    assert T.work_id("urn_cts_greekLit_tlg0057.tlg001.1st1K-grc2.txt") == "tlg0057.tlg001"
    assert T.work_id("urn_cts_greekLit_stoa0033a.tlg028.1st1K-grc1.txt") == "stoa0033a.tlg028"


def test_build_counts_excludes_holdout_and_pools_rare(toy):
    assert toy.count("ΛΟΓΟΣ") == 3 * 5
    assert toy.count("ΞΕΝΙΚΟΝ") == 0          # held-out work never counted
    assert toy.meta["holdout"] == ["tlg8000.tlg001"]
    assert toy.forms[-1] == "<RARE>"
    # bigram keys sorted, counts consistent with the unigram total minus one per file
    assert (T.np.diff(toy.bkeys) > 0).all()
    assert int(toy.bcounts.sum()) == toy.n_tokens - 5


def test_segment_clean_string(toy):
    seg = seg_of(toy)
    r = seg.segment("ΚΑΙΤΗΝΨΥΧΗΝΑΘΑΝΑΤΟΝΕΙΝΑΙ", k=3)
    assert r[0].words == ["ΚΑΙ", "ΤΗΝ", "ΨΥΧΗΝ", "ΑΘΑΝΑΤΟΝ", "ΕΙΝΑΙ"]
    assert len({tuple(x.words) for x in r}) == len(r)          # k-best are distinct readings
    assert r[0].boundaries == {3, 6, 11, 19}


def test_channel_undoes_confusion_and_lost_letter(toy):
    seg = seg_of(toy)
    r = seg.segment("ΟΑΟΓΟΣΕΣΤΙΝΑΛΗΘΗΣ")               # Λ read as Α
    assert r[0].words == ["Ο", "ΛΟΓΟΣ", "ΕΣΤΙΝ", "ΑΛΗΘΗΣ"]
    assert any(x.edit == "sub1" for x in r[0].segments)
    r = seg.segment("ΤΟΣΩΜΑΚΑΙΗΨΥΗ")                   # Χ lost
    assert r[0].words[-1] == "ΨΥΧΗ"
    assert r[0].segments[-1].edit.startswith("lost:Χ")


def test_without_channel_confusions_stay_unknown(toy):
    seg = seg_of(toy, channel=False)
    r = seg.segment("ΟΑΟΓΟΣΕΣΤΙΝΑΛΗΘΗΣ")
    assert "ΛΟΓΟΣ" not in r[0].words


def test_greedy_takes_longest_attested_match(toy):
    lex = T.Lexicon(toy, min_count=2, channel=False)
    r = T.greedy_longest(lex, "ΚΑΙΟΛΟΓΟΣΖ")
    assert r.words == ["ΚΑΙ", "Ο", "ΛΟΓΟΣ", "Ζ"]
    assert r.segments[-1].form is None


def test_inject_positions_and_gold_boundaries():
    clean = "ΚΑΙΤΟΝ"
    noisy, pos = E.inject(clean, {"sub": 0.0, "off": 0.0, "dele": 0.0}, random.Random(1))
    assert noisy == clean and pos == list(range(7))
    b, spans = E.gold_spans(["ΚΑΙ", "ΤΟΝ"], pos)
    assert b == {3} and spans == [(0, 3, "ΚΑΙ"), (3, 6, "ΤΟΝ")]
    noisy, pos = E.inject(clean, {"sub": 0.0, "off": 0.0, "dele": 1.0}, random.Random(1))
    assert noisy == "" and pos[-1] == 0


def test_evaluate_perfect_system_scores_one(toy):
    seg = seg_of(toy)
    words = ["ΚΑΙ", "ΤΗΝ", "ΨΥΧΗΝ"]
    clean = "".join(words)
    row = {"id": "x", "gold": words, "noisy": {"clean": {"s": clean, "pos": list(range(len(clean) + 1))}}}
    r = E.evaluate([row], "clean", seg.segment)
    assert r["boundary_F1"] == 1.0 and r["line_top1"] == 1.0 and r["word_recovery_R"] == 1.0


def test_leiden_words_tracks_restored_letters_across_lines():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "audit-kit"))
    import t2b_flag as F
    ws = F.leiden_words("εἶναι περὶ μο[υ-\nσικὴ]ν. . . ἁμαρ[τ-\nόντα γ]ὰρ τῶι ὧι")
    by = {w["key"]: w for w in ws}
    assert by["ΜΟΥΣΙΚΗΝ"]["restored"] == 5 and F.restored_class(by["ΜΟΥΣΙΚΗΝ"]) == "partly_restored"
    assert F.restored_class(by["ΕΙΝΑΙ"]) == "read"
    assert "ΤΩ" in by and "Ω" in by                         # adscript ωι, incl. ὧι with breathing
    assert by["ΑΜΑΡΤΟΝΤΑ"]["fragment"]                      # touches the unread gap


def test_unarticulated_letters_are_fragments_but_enclitics_are_not():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "audit-kit"))
    import t2b_flag as F
    assert F.unarticulated("τελον", "ΤΕΛΟΝ") and F.unarticulated("αεως", "ΑΕΩΣ")
    assert not F.unarticulated("τε", "ΤΕ") and not F.unarticulated("λόγος", "ΛΟΓΟΣ")
    assert not F.unarticulated("ἐν", "ΕΝ")
