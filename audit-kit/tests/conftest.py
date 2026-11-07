from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# A tiny synthetic corpus: two "authors", JSONL in the project format, a Morpheus
# cache covering most surfaces, a second "system" cache in the Stanza layout,
# and a controls file in the project format.
WORK_A = [  # tlg9001 — 8 tokens; one planted non-word lemma, one surface uncached
    ("καὶ", "καί", "CCONJ"), ("τὸ", "ὁ", "DET"), ("σῶμα", "σῶμα", "NOUN"), ("τῆς", "ὁ", "DET"),
    ("γαστρὸς", "γαήτσρ", "NOUN"), ("ἐστι", "εἰμί", "VERB"), ("θερμὸν", "θερμός", "ADJ"), ("ξενικόν", "ξενικός", "ADJ"),
]
WORK_B = [  # tlg9002 — 6 tokens
    ("ὁ", "ὁ", "DET"), ("λόγος", "λόγος", "NOUN"), ("δὲ", "δέ", "CCONJ"), ("νεύρου", "νεύρον", "NOUN"),
    ("καὶ", "καί", "CCONJ"), ("φλεβῶν", "φλεβά", "NOUN"),
]
MORPHEUS = {
    "καὶ": ["καί"], "τὸ": ["ὁ"], "σῶμα": ["σῶμα"], "τῆς": ["ὁ"], "γαστρὸς": ["γαστήρ"], "ἐστι": ["εἰμί"],
    "θερμὸν": ["θερμός"], "ὁ": ["ὁ"], "λόγος": ["λόγος"], "δὲ": ["δέ"], "νεύρου": ["νεῦρον"], "φλεβῶν": ["φλέψ"],
    # ξενικόν deliberately absent -> not_in_cache
}
# second system: mostly agrees, disagrees on γαστρὸς (right) and νεύρου (accent only), splits one token
SYS2_A = [("καὶ", "καί"), ("τὸ", "ὁ"), ("σῶμα", "σῶμα"), ("τῆς", "ὁ"), ("γαστρὸς", "γαστήρ"), ("ἐστι", "εἰμί"),
          ("θερμὸν", "θερμός"), ("ξενι", "ξενικός"), ("κόν", "κόν")]
SYS2_B = [("ὁ", "ὁ"), ("λόγος", "λόγος"), ("δὲ", "δέ"), ("νεύρου", "νεῦρον"), ("καὶ", "καί"), ("φλεβῶν", "φλέψ")]


@pytest.fixture
def tiny_corpus(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "lemmatized"
    sub = root / "reference"
    sub.mkdir(parents=True)
    for stem, rows in (("urn_cts_greekLit_tlg9001.tlg001.1st1K-grc1", WORK_A), ("urn_cts_greekLit_tlg9002.tlg001.1st1K-grc1", WORK_B)):
        with (sub / f"{stem}.jsonl").open("w", encoding="utf-8") as fh:
            for i, (s, l, p) in enumerate(rows):
                fh.write(json.dumps({"i": i, "surface": s, "lemma": l, "pos": p, "morph": {}}, ensure_ascii=False) + "\n")
    cache = tmp_path / "morpheus.jsonl"
    with cache.open("w", encoding="utf-8") as fh:
        for s, lem in MORPHEUS.items():
            fh.write(json.dumps({"surface_nfc": s, "lemmas": lem, "ok": True, "source": "test"}, ensure_ascii=False) + "\n")
    stanza_cache = tmp_path / "h3m_cache"
    d = stanza_cache / "stanza_perseus"
    d.mkdir(parents=True)
    for stem, rows in (("urn_cts_greekLit_tlg9001.tlg001.1st1K-grc1", SYS2_A), ("urn_cts_greekLit_tlg9002.tlg001.1st1K-grc1", SYS2_B)):
        with (d / f"{stem}.jsonl").open("w", encoding="utf-8") as fh:
            for i, (s, l) in enumerate(rows):
                fh.write(json.dumps({"i": str(i), "surface": s, "lemma": l}, ensure_ascii=False) + "\n")
    controls = tmp_path / "controls.csv"
    controls.write_text(
        "control_id,control_type,strength,surface_form,lemma_produced,pos,one_line_context,work_stem,token_index,EXPECTED_answer,EXPECTED_correct_lemma,provenance\n"
        "C01,wrong_plant,unambiguous,γαστρὸς,γαήτσρ,NOUN,τῆς [γαστρὸς] ἐστι,w,4,n,γαστήρ,neural hallucination / garbled non-word\n"
        "C02,wrong_plant,unambiguous,φλεβῶν,φλεβά,NOUN,καὶ [φλεβῶν],w,5,n,φλέψ,fragmentation\n"
        "C03,wrong_plant,accent,νεύρου,νεύρον,NOUN,δὲ [νεύρου] καὶ,w,3,n,νεῦρον,accent error\n"
        "C04,right_anchor,unambiguous,θερμὸν,θερμός,ADJ,ἐστι [θερμὸν] ξενικόν,w,6,y,,correct headword\n",
        encoding="utf-8",
    )
    return {"root": root, "cache": cache, "stanza_cache": stanza_cache, "controls": controls, "tmp": tmp_path}
