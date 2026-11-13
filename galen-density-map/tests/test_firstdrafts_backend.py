"""Tests for the config-driven First Drafts back end (translate / lsj_index / align / checks / page, 2026-11-12).

The Galen prompts are pinned by SHA-256 to the cycle 1-4 text; the Latin prompts are the same wording with the
config's facts; the Latin sentence split never cuts at ';'; Lewis & Short links and glosses; the Latin tagger stream
is indexed by position. No test calls a model.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest
from lxml import etree

GDM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GDM / "pipeline"))
sys.path.insert(0, str(GDM / "pipeline" / "firstdrafts"))

import align  # noqa: E402
import checks  # noqa: E402
import common  # noqa: E402
import generic  # noqa: E402
import lsj_index  # noqa: E402
import page  # noqa: E402
import translate  # noqa: E402

CYCLE_1_4 = {  # SHA-256 of the system prompts every Galen request of cycles 1-4 carried
    "translate": "f07aec7627cdf271f5edc78729de10f6c051bff51c27ae4ca5ad33b0dedd1052",
    "backtranslate": "8fc5fa88c47652d7dd461e0854fcc85bd89dacb69ca610ed6f56f7452bc9783d",
    "judge": "170c01b6004100ebf561b52f85dbddf1236cc30fd88121e82119f89caa8d169d",
}


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_galen_prompts_are_the_cycle_1_4_prompts():
    g = common.work_config("adversus-lycum")
    assert sha(translate.SYSTEM) == sha(translate.system_for(g)) == CYCLE_1_4["translate"]
    assert sha(checks.BT_SYSTEM) == sha(checks.bt_system_for(g)) == CYCLE_1_4["backtranslate"]
    assert sha(checks.JUDGE_SYSTEM) == sha(checks.judge_system_for(g)) == CYCLE_1_4["judge"]


def test_work_config_resolves_galen_and_configs():
    g = common.work_config("comp-per-genera")
    assert g["galen"] and g["lang"] == "grc" and g["kuhn_vol"] == "XIII" and g["lexicon"]["name"] == "lsj"
    v = common.work_config("vitruvius-3")
    assert not v["galen"] and v["lang"] == "lat" and v["lexicon"]["name"] == "ls" and v["author"] == "Vitruvius"
    with pytest.raises(SystemExit):
        common.work_config("no-such-work")


def test_latin_prompts_name_the_work_language_and_lexicon():
    v = common.work_config("vitruvius-3")
    s = translate.system_for(v)
    assert s.startswith("You are translating Vitruvius from Latin into English") and "bracketed section marker such as [" in s
    assert "Krohn's 1912 Teubner edition" in s and '"uncertain_latin"' in s
    assert not re.search(r"Galen|Greek|Kühn", s)
    # same neutral wording: with the work facts blanked out, the Latin prompt IS the Galen prompt
    lat = (s.replace("uncertain_latin", "uncertain_L").replace("Vitruvius", "A").replace("Latin", "L")
           .replace("Krohn's 1912 Teubner edition", "D"))
    lat = re.sub(r"bracketed section marker such as \[[^\]]+\]", "bracketed M marker such as E", lat)
    grc = (translate.SYSTEM.replace("uncertain_greek", "uncertain_L").replace("Galen", "A").replace("Ancient Greek", "L")
           .replace("Greek", "L").replace("Kühn's 1829 edition", "D").replace("bracketed page marker such as [197]", "bracketed M marker such as E"))
    assert lat == grc
    b = checks.bt_system_for(v)
    assert "into Latin prose of the kind Vitruvius writes" in b and '{"latin": "<the Latin>"}' in b and "Greek" not in b
    j = checks.judge_system_for(v)
    assert "Lewis & Short (A Latin Dictionary, 1879) entry" in j and "one Latin word" in j and "LSJ" not in j
    item = {"item_id": "J00001", "greek_sentence": "Aedium compositio constat ex symmetria,", "surface": "symmetria,", "lemma": "symmetria",
            "lsj_headword": "symmē^trĭa", "lsj_entry": "symmetria, ae, f.", "english": "symmetry"}
    u = checks.judge_user([item], v)
    assert "LATIN SENTENCE: Aedium" in u and "Lewis & Short headword symmē^trĭa" in u and "LEWIS & SHORT ENTRY:" in u
    assert "GREEK SENTENCE" in checks.judge_user([item]) and "LSJ ENTRY" in checks.judge_user([item])


def test_translate_user_prompt_for_a_config_work():
    v = common.work_config("vitruvius-3")
    unit = {"unit_id": "Vitr.3.1.1-3.1.2", "locus": "Vitr. 3.1.1–3.1.2", "chapters": ["3.1"], "greek": "[3.1.1] Aedium compositio constat ex symmetria."}
    u = translate.build_user(unit, None, None, [{"target_no": 3, "surface": "symmetria."}], v)
    assert u.startswith("Work: Vitruvius, De architectura, liber III (On Architecture, Book 3), ed. F. Krohn")
    assert "skipping the bracketed section markers" in u and "Kühn" not in u


def test_latin_sentence_split_never_cuts_at_semicolon():
    v = common.work_config("vitruvius-3")
    is_end = generic.sentence_end_fn(v["unit"])
    mark = re.compile(common.marker_re(v))
    s = align.split_greek("[3.1.1] Primum dicam; deinde scribam. Quid est? Nihil [3.1.2] C. Iulius venit.", mark, is_end)
    assert [x["text"] for x in s] == ["[3.1.1] Primum dicam; deinde scribam.", "Quid est?", "Nihil [3.1.2] C. Iulius venit."]
    assert [(x["start"], x["end"]) for x in s] == [(0, 4), (4, 6), (6, 10)]
    g = align.split_greek("α β; γ δ. [12] ε.")   # Galen: ';' is the Greek question mark
    assert [x["text"] for x in g] == ["α β;", "γ δ.", "[12] ε."]


def test_markers_and_links():
    v = common.work_config("vitruvius-3")
    assert re.findall(common.marker_re(v), "see [3.pr.1] and [3.5.15] but not [the] or [197]") == ["3.pr.1", "3.5.15"]
    assert re.findall(common.GENERIC_MARKER, "[197] [3.pr.1] [the]") == ["197", "3.pr.1"]
    assert page.link_headword("com-mŏdŭlātĭo") == "commodulatio" and page.link_headword("symmē^trĭa") == "symmetria"
    t = page.page_text(v, False)
    assert t["label"] == "section" and t["lex"]["short"] == "Lewis & Short" and t["col"] == "Latin (Krohn)"
    assert page.page_text(common.WORKS["adversus-lycum"], True)["label"] == "Kühn page"


def test_ls_gloss_is_the_first_italic_english_of_the_first_sense():
    xml = ('<entryFree key="abacus" id="n11"><orth>ăbăcus</orth>, i, m. <sense n="I"><hi rend="ital">a square tablet;</hi> hence '
           '<hi rend="ital">a sideboard</hi></sense><sense n="II"><hi rend="ital">a counting-board</hi></sense></entryFree>')
    el = etree.fromstring(xml)
    senses = lsj_index.sense_texts(el)
    assert lsj_index.ls_gloss(el, senses, lsj_index.entry_text(el)) == "a square tablet"


SMOKE = GDM / "outputs" / "firstdrafts" / "_smoke_lat" / "vitruvius-3"


@pytest.mark.skipif(not (SMOKE / "tagged.jsonl").exists(), reason="needs the committed Latin smoke outputs")
def test_latin_tagger_stream_is_indexed_by_position():
    stream = [json.loads(l) for l in (SMOKE / "tagged.jsonl").open(encoding="utf-8")]
    assert [r["i"] for r in stream] == list(range(len(stream)))
    for u in (json.loads(l) for l in (SMOKE / "units.jsonl").open(encoding="utf-8")):
        words = [common.strip_punct(w).replace("—", "").replace("-", "") for w in u["greek_plain"].split()]
        words = [w for w in words if re.search(generic.SCRIPT_RE["lat"], w)]
        assert [r["surface"] for r in stream[u["odycy_start"]:u["odycy_end"] + 1]] == words, u["unit_id"]
