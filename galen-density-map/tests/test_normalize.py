import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from lib.beta_keys import lemma_to_lookup_key, normalize_betacode_key
from lib.greek_normalize import (
    casefold_greek,
    is_all_caps_greek_token,
    normalize_extracted_text,
    normalize_lemma_orthography,
    normalize_lunate_sigma,
)


def test_lunate_sigma_medial_and_final():
    assert "τοῖς" in normalize_lunate_sigma("τοῖϲ")
    assert "ἐστι" in normalize_lunate_sigma("ἐϲτι")


def test_all_caps_header():
    assert is_all_caps_greek_token("ΓΑΛΗΝΟΥ")
    assert not is_all_caps_greek_token("Γαληνοῦ")
    assert not is_all_caps_greek_token("καί")


def test_crasis_expand():
    text, stats = normalize_extracted_text("κᾀνταῦθα δὲ οὐδ' ἄλλο")
    assert "καὶ" in text
    assert "ἐνταῦθα" in text
    assert "οὐδέ" in text
    assert "κᾀνταῦθα" not in text
    assert stats["crasis_expanded"] >= 1


def test_casefold_collapses_hippocrates():
    assert casefold_greek("Ἱπποκράτης") == casefold_greek("ἱπποκράτης")


def test_beta_sigma_and_capital():
    assert normalize_betacode_key("toi=s3") == normalize_betacode_key("toi=s")
    assert normalize_betacode_key("*fa/rmakon") == "farmakon"
    assert lemma_to_lookup_key("τοῖϲ") == lemma_to_lookup_key("τοῖς")
    assert lemma_to_lookup_key("φάρμακον") == "farmakon"


def test_lemma_orthography_gignomai_doubled_gamma():
    out, fired = normalize_lemma_orthography("γίγγνομαι")
    assert out == "γίγνομαι"
    assert "doubled_gamma_gignomai" in fired
    untouched, fired2 = normalize_lemma_orthography("φάρμακον")
    assert untouched == "φάρμακον"
    assert fired2 == []
