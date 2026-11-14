import pytest

from galen_mcp.text import clip, fold, fold_beta, is_greek, parse_kuhn, roman_to_int, stem_en, vol_label


def test_fold_greek_and_latin():
    assert fold("ὄνυξι,") == "ονυξι"
    assert fold("νεῦρον") == fold("νευρον") == fold("ΝΕΥΡΟΝ")
    assert fold("Ἀνεμέσητος") == "ανεμεσητοσ"  # final sigma folded
    assert fold("consīdĕrātĭo") == "consideratio"
    assert fold("ab-dico") == "abdico"
    assert fold("Iuuenis") == fold("juvenis")


def test_beta_and_script():
    assert fold_beta("gnw/risma") == "gnwrisma"
    assert is_greek("ἀᾶται") and not is_greek("acrid")


@pytest.mark.parametrize("s,want", [
    ("K15.609", ("15", 609, None)),
    ("K. XV 609", ("15", 609, None)),
    ("Kühn XV, 609", ("15", 609, None)),
    ("K18a.196", ("18a", 196, None)),
    ("K XVIII A 196-197", ("18a", 196, 197)),
    ("K XVIIIA 196", ("18a", 196, None)),
    ("15.609–610", ("15", 609, 610)),
    ("K15.609-610", ("15", 609, 610)),
    ("vol. 7 p. 760", ("7", 760, None)),
])
def test_parse_kuhn(s, want):
    assert parse_kuhn(s) == want


@pytest.mark.parametrize("s", ["", "nerve", "K15", "Vitr.3.1.5", "K15:abc"])
def test_parse_kuhn_rejects(s):
    assert parse_kuhn(s) is None


def test_roman_and_labels():
    assert roman_to_int("XVIII") == 18 and roman_to_int("XIV") == 14 and roman_to_int("q") is None
    assert vol_label("18a") == "XVIIIA" and vol_label("15") == "XV"


def test_clip_and_stem():
    t, dropped = clip("one two three four five", 12)
    assert t.endswith("…") and dropped > 0
    assert clip("short", 10) == ("short", 0)
    assert stem_en("nerves") == "nerve" and stem_en("arteries") == "artery" and stem_en("bias") == "bias"
