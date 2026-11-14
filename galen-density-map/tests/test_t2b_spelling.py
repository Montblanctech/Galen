"""T2b spelling layer: rule extraction from editors' regularizations, the rule filter, the channel side (only
unattested forms, the ending gate), the writer's habits, and the flagger's joins and debris."""
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import t2b_scorer as T  # noqa: E402
import t2b_spelling as S  # noqa: E402
import t2b_spelling_data as D  # noqa: E402
import t2b_flag as F  # noqa: E402


def test_rules_attach_dropped_letters_where_they_make_a_diphthong():
    # ποιητικόν written ποητικόν: Ι dropped after Ο -> ΟΙ written Ο before a vowel
    assert S.rules_of_pair("ΠΟΗΤΙΚΟΝ", "ΠΟΙΗΤΙΚΟΝ") == [("ΟΙ", "Ο", "V", False)]
    # κινεῖν written κεινεῖν: Ε added before Ι -> Ι written ΕΙ before a consonant
    assert S.rules_of_pair("ΚΕΙΝΕΙΝ", "ΚΙΝΕΙΝ") == [("Ι", "ΕΙ", "C", False)]
    assert S.rules_of_pair("ΤΟΜ", "ΤΟΝ") == [("Ν", "Μ", "#", False)]
    # too different to be a spelling
    assert S.rules_of_pair("ΑΒΓΔΕΖ", "ΚΛΜΝΞΟ") is None


def test_rule_filter_keeps_sound_changes_and_drops_grammar():
    assert S.kind_of("ΕΙ", "Ι", "C") == "vowel"
    assert S.kind_of("Γ", "Ν", "C") == "consonant"
    assert S.kind_of("ΜΜ", "Μ", "V") == "double consonant"
    assert S.kind_of("ΙΝ", "Ι", "#") == "final nu"
    assert S.kind_of("ΟΝ", "Ο", "C") == "nasal before consonant"
    assert S.kind_of("Σ", "Υ", "#") is None          # ἀριθμοῦ for ἀριθμός: a case ending, not a spelling
    assert S.kind_of("ΝΟΣ", "Ν", "#") is None        # an abbreviation


def test_poisson_tail():
    assert abs(S.poisson_tail(0, 2.0) - 1.0) < 1e-15
    assert abs(S.poisson_tail(1, 2.0) - (1 - math.exp(-2.0))) < 1e-15
    assert S.poisson_tail(23, 2.27) < 1e-12


TABLE = {"rules": [
    {"reg": "ΟΙ", "orig": "Ο", "right": "V", "start": False, "rate": 0.0124, "cost": math.log(0.0124)},
    {"reg": "Ω", "orig": "Ο", "right": "C", "start": False, "rate": 0.0068, "cost": math.log(0.0068)},
    {"reg": "Ε", "orig": "Α", "right": "C", "start": False, "rate": 0.0003, "cost": math.log(0.0003)},
]}


def test_rewrites_respect_right_context():
    sp = S.SpellingRules(TABLE)
    outs = [r for r, _, _ in sp.rewrites("ΠΟΗΤΗΣ")]
    assert "ΠΟΙΗΤΗΣ" in outs                         # Ο before Η (a vowel)
    assert "ΠΩΗΤΗΣ" not in outs                      # the Ω rule wants a consonant after


def test_habits_need_more_uses_than_chance():
    sp = S.SpellingRules(TABLE)
    # 23 uses in 183 chances of a rule at 1.24%: a habit
    c = S.adapt_costs(sp, Counter({0: 23}), Counter({0: 183}))
    assert c is not None and c[0] > sp.base[0]
    # 4 uses in 2,357 chances of a rule at 0.03%: could be chance (p ~ 0.009 > 0.001), not a habit
    assert S.adapt_costs(sp, Counter({2: 4}), Counter({2: 2357})) is None
    assert S.adapt_costs(sp, Counter({0: 2}), Counter({0: 5})) is None   # below HABIT_MIN


def _toy_counts(tmp_path):
    words = ("ὁ ποιητὴς καὶ τὰ ποιήματα καὶ ὁ ποιητὴς λέγει τὸν λόγον καλῶς καὶ καλὸς ὁ λόγος " * 4).split()
    p = tmp_path / "urn_cts_greekLit_tlg9001.tlg001.1st1K-grc1.txt"
    p.write_text(" ".join(words) + "\n", encoding="utf-8")
    return T.build_counts([p], set(), log=lambda m: None)


def test_channel_reads_an_ancient_spelling_only_when_unattested(tmp_path):
    c = _toy_counts(tmp_path)
    lex = T.Lexicon(c, min_count=2, spelling=S.SpellingRules(TABLE))
    cs = lex.candidates("ΠΟΗΤΗΣ")
    assert cs and c.forms[cs[0][0]] == "ΠΟΙΗΤΗΣ" and cs[0][2] == "var:0"
    # ΚΑΛΟΣ is attested as written: no spelling candidate (ΚΑΛΩΣ) is offered for it
    assert all(not t.startswith("var:") for _, _, t in lex.candidates("ΚΑΛΟΣ"))


def test_ending_gate_and_stem(tmp_path):
    c = _toy_counts(tmp_path)
    lex = T.Lexicon(c, min_count=2, spelling=S.SpellingRules(TABLE))
    assert lex.common_ending("ΑΛΛΟΓΟΣ")               # -ΓΟΣ ends a counted word (ΛΟΓΟΣ)
    assert not lex.common_ending("ΞΞΞΞ")


def test_split_words_are_joined_and_lone_letters_are_debris(tmp_path):
    c = _toy_counts(tmp_path)
    lex = T.Lexicon(c, min_count=2)
    words = F.leiden_words("ὁ ποι ητὴς λ καὶ")
    n = F.join_splits(lex, words)
    F.mark_debris(words)
    assert n == 1 and [w["key"] for w in words] == ["Ο", "ΠΟΙΗΤΗΣ", "Λ", "ΚΑΙ"]
    assert words[2]["fragment"] and not words[0]["fragment"]
    # two attested halves across a line end, the first unaccented: joined when the whole is far more likely
    words = F.leiden_words("τὰ ποι\nητὴς καὶ")
    assert F.join_splits(lex, words) == 1 and words[1]["key"] == "ΠΟΙΗΤΗΣ" and not words[1]["fragment"]
    # the same pair inside a line is left as the editor divided it
    words = F.leiden_words("ὁ λόγος καλὸς")
    assert F.join_splits(lex, words) == 0


def test_a_final_full_stop_is_punctuation_not_an_unread_letter():
    w = F.leiden_words("καλῶς. κα.ὸς . . .")
    assert not w[0]["gap"] and w[1]["gap"]


def test_epidoc_rendering_keeps_orig_and_reg_apart(tmp_path):
    x = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition"><ab>'
         '<lb n="1"/>καὶ <choice><reg>ποιητὴς</reg><orig>ποητὴς</orig></choice> γεν'
         '<lb n="2" break="no"/>ήματα <gap reason="lost"/> τέλος</ab></div></body></text></TEI>')
    p = tmp_path / "1.xml"
    p.write_text(x, encoding="utf-8")
    assert D.edition_words(p, "orig")[:3] == ["καὶ", "ποητὴς", "γενήματα"]
    pairs, n, skipped = D.doc_pairs(p)
    assert pairs == [{"orig": "ΠΟΗΤΗΣ", "reg": "ΠΟΙΗΤΗΣ", "near_gap": False}] and skipped == 0
