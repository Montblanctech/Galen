"""H3-M lemma equality and Morpheus payload parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from h3m.lemma_eq import (
    admissibility_verdict,
    analyses_have_lemma,
    classify_lemma_disagreement,
    lemmas_equal_blind,
    lemmas_equal_strict,
)
from h3m.morpheus_client import parse_morpheus_payload
from h3m.stats_util import wilson_ci


README_JSON = {
    "RDF": {
        "Annotation": {
            "Body": {
                "rest": {
                    "entry": {
                        "dict": {
                            "hdwd": {"lang": "grc", "$": "ἄνθρωπος"},
                        }
                    }
                }
            }
        }
    }
}

MULTI_BODY = {
    "RDF": {
        "Annotation": {
            "Body": [
                {"rest": {"entry": {"dict": {"hdwd": {"$": "λύω"}}}}},
                {"rest": {"entry": {"dict": {"hdwd": {"$": "λύω2"}}}}},
            ]
        }
    }
}

EMPTY_JSON = {
    "RDF": {
        "Annotation": {
            "about": "urn:TuftsMorphologyService:andros:morpheusgrc",
            "title": {},
        }
    }
}


def test_accent_blind_membership():
    assert lemmas_equal_blind("νεῦρον", "νεύρον")
    assert not lemmas_equal_strict("νεῦρον", "νεύρον")
    assert analyses_have_lemma("νεύρον", ["νεῦρον"], accent_blind=True)
    assert not analyses_have_lemma("νεύρον", ["νεῦρον"], accent_blind=False)


def test_sigma_and_nfc():
    assert lemmas_equal_strict("τοῖς", "τοῖϲ")
    assert lemmas_equal_blind("φάρμακον", "φαρμάκον")


def test_verdicts():
    assert admissibility_verdict("γαστήρ", ["γαστήρ"]) == "admissible"
    assert admissibility_verdict("γαήτσρ", ["γαστήρ"]) == "inadmissible"
    assert admissibility_verdict("γαήτσρ", []) == "no_analysis"
    assert admissibility_verdict("δείκνυμι", ["δείκνυμι", "δεικνύω"]) == "admissible"


def test_g2a_classes():
    assert classify_lemma_disagreement("τοῖς", "τοῖϲ") == "encoding_artifact"
    assert classify_lemma_disagreement("νεῦρον", "νεύρον") == "accent_only"
    assert classify_lemma_disagreement("φλέψ", "φλεβά") == "real_disagreement"
    assert classify_lemma_disagreement("α", "") == "missing_lemma"


def test_parse_readme_json():
    lemmas = parse_morpheus_payload(README_JSON)
    assert lemmas == ["ἄνθρωπος"]


def test_parse_multi_and_empty():
    assert parse_morpheus_payload(MULTI_BODY) == ["λύω", "λύω2"]
    assert parse_morpheus_payload(EMPTY_JSON) == []
    assert parse_morpheus_payload(json.dumps(EMPTY_JSON), "application/json") == []


def test_parse_xml_hdwd():
    xml = """<?xml version="1.0"?>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <entry><dict><hdwd xml:lang="grc">γαστήρ</hdwd></dict></entry>
    </rdf:RDF>"""
    assert parse_morpheus_payload(xml, "application/rdf+xml") == ["γαστήρ"]


def test_wilson_ci_bounds():
    lo, hi = wilson_ci(50, 100)
    assert 0.4 < lo < 0.5 < hi < 0.6
    lo0, hi0 = wilson_ci(0, 0)
    assert lo0 != lo0  # nan
