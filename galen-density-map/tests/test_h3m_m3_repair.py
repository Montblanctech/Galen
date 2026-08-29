"""F1 uniqueness + F3 mismatch taxonomy for repaired M3."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from lib.beta_keys import lemma_to_lookup_key
from h3m.m3_lsj_gold import (
    classify_mismatch,
    morpheus_validated_occurrences,
    share_stem,
)
from h3m.morpheus_client import MorpheusClient


class _FakeMorpheus:
    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self.mapping = mapping

    def analyze(self, surface: str) -> list[str]:
        return list(self.mapping.get(surface, []))


def test_uniqueness_zero_one_two():
    hw = "ἧπαρ"
    client = _FakeMorpheus(
        {
            "ἥπατος": ["ἥπατος", "ἧπαρ"],
            "φλέψ": ["φλέψ"],
            "ἥπατι": ["ἧπαρ"],
        }
    )
    assert morpheus_validated_occurrences(["φλέψ"], hw, client) == []
    assert morpheus_validated_occurrences(["ἥπατος"], hw, client) == ["ἥπατος"]
    two = morpheus_validated_occurrences(["ἥπατος", "x", "ἥπατι"], hw, client)
    assert two == ["ἥπατος", "ἥπατι"]
    assert len(two) != 1


def test_quoted_collocate_is_not_a_target():
    """φάρμακα is a collocate; Morpheus must not validate it as ἀμβλωτικός."""
    client = _FakeMorpheus({"φάρμακα": ["φάρμακον"], "ἀμβλωτικά": ["ἀμβλωτικός"]})
    hits = morpheus_validated_occurrences(
        ["ἀ.", "φάρμακα"],
        "ἀμβλωτικός",
        client,
    )
    assert hits == []
    hits2 = morpheus_validated_occurrences(
        ["ἀμβλωτικά", "φάρμακα"],
        "ἀμβλωτικός",
        client,
    )
    assert hits2 == ["ἀμβλωτικά"]


def test_share_stem_akantha():
    assert share_stem("ἄκανθα", "ἀκάνθη")
    assert share_stem("ἀγχίαλος", "ἀγχιάλη")
    assert not share_stem("ἄζυγος", "φλέψ")


def test_classify_passthrough_garble_variant_other():
    idx = {
        lemma_to_lookup_key("ἄκανθα"): {"lsj_exists": True},
        lemma_to_lookup_key("ἀκάνθη"): {"lsj_exists": True},
        lemma_to_lookup_key("φλέψ"): {"lsj_exists": True},
    }
    surfaces = {
        "αἰδεσθήσῃ": {"αἰδεσθήσῃ"},
        "αἱμεηρῶ": {"γαστρός"},
        "ἀκάνθη": {"ἀκάνθης"},
        "φλέψ": {"φλεβός", "φλέβα"},
    }
    assert (
        classify_mismatch("αἰδέομαι", "αἰδεσθήσῃ", "αἰδεσθήσῃ", idx, surfaces)
        == "passthrough"
    )
    assert classify_mismatch("αἷμα", "αἱματηρῷ", "αἱμεηρῶ", idx, surfaces) == "garble"
    assert classify_mismatch("ἄκανθα", "ἀκάνθης", "ἀκάνθη", idx, surfaces) == "variant_headword"
    assert classify_mismatch("ἄζυγος", "φλέβα", "φλέψ", idx, surfaces) == "other_substitution"


def test_cache_writer_utf8_and_loader_skips_corrupt(tmp_path):
    path = tmp_path / "morpheus_by_surface.jsonl"
    client = MorpheusClient(path, base_url="http://127.0.0.1:9", source_label="test")
    row = {"surface_nfc": "καί", "lemmas": ["καί"], "ok": True}
    client._append_cache(row)
    raw = path.read_bytes()
    assert b"\n" in raw
    raw.decode("utf-8")
    # inject a non-UTF-8 line (0x96) and a good line
    path.write_bytes(raw + b"\x96 not-json\n")
    client2 = MorpheusClient(path, base_url="http://127.0.0.1:9", source_label="test")
    assert "καί" in client2._cache
    assert "bad" not in client2._cache
    stats = client2.repair_corrupt_lines()
    assert stats["corrupt_lines"] >= 1
    path.read_bytes().decode("utf-8")
