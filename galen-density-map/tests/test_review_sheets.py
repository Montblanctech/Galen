"""Tests for the review worksheets (pipeline/review_sheets.py): the seeded sampling rule, the sheet build on a synthetic
First Drafts work, the scorer's label mapping and estimates, and a data-dependent check against the published outputs."""
import csv
import json
import sys
from pathlib import Path

import pytest

GDM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GDM / "pipeline"))

import review_sheets as rs  # noqa: E402


def stats(n, disagree=None, fail=()):
    disagree = disagree or {}
    return [{"unit_id": f"U{i:03d}", "n_targets": 8, "n_both": 8, "n_disagree": disagree.get(i, 0),
             "disagree_rate": round(disagree.get(i, 0) / 8, 3), "a": "pass", "b": "fail" if i in fail else "pass", "c": "",
             "any_fail": i in fail, "unit_verdict": "pass"} for i in range(n)]


# ---------------------------------------------------------------------------------------------------------- sampling

def test_sample_is_deterministic_and_seed_sensitive():
    st = stats(60, {i: i % 5 for i in range(60)}, fail=range(0, 60, 3))
    a = rs.sample_work(st, "w", seed="1")
    assert a == rs.sample_work(st, "w", seed="1")
    assert [x["unit_id"] for x in a] != [x["unit_id"] for x in rs.sample_work(st, "w", seed="2")]
    assert [x["unit_id"] for x in a] != [x["unit_id"] for x in rs.sample_work(st, "other", seed="1")]


def test_strata_follow_the_rule():
    dis = {5: 6, 9: 6, 12: 5, 20: 4, 30: 4, 31: 1}
    fail = {1, 2, 3, 5, 40}
    st = stats(50, dis, fail)
    s = rs.sample_work(st, "w")
    assert len(s) == rs.N_PER_WORK
    by = {x["unit_id"]: x for x in s}
    d = sorted(u for u, x in by.items() if x["stratum"] == "D")
    # top four by disagreeing terms: 5, 9 (6 each), 12 (5), then one of 20/30 (4 each, seeded tie-break)
    assert {"U005", "U009", "U012"} <= set(d) and len(d) == 4 and set(d) - {"U005", "U009", "U012"} <= {"U020", "U030"}
    for x in s:
        if x["stratum"] == "F":
            assert int(x["unit_id"][1:]) in fail and x["unit_id"] not in d
        if x["stratum"] == "R":
            assert int(x["unit_id"][1:]) not in fail
    assert sum(1 for x in s if x["stratum"] == "F") == 3
    f_pop = {f"U{i:03d}" for i in fail} - set(d)
    assert all(x["stratum_N"] == len(f_pop) for x in s if x["stratum"] == "F")
    assert all(x["stratum_N"] == 50 - 4 - len(f_pop) for x in s if x["stratum"] == "R")
    assert sorted(x["sheet_no"] for x in s) == list(range(1, 11))


def test_first_sheets_mix_the_strata():
    st = stats(80, {i: 3 for i in range(10)}, fail=range(10, 40))
    s = rs.sample_work(st, "w")
    assert len({x["stratum"] for x in s[:3]}) == 3


def test_small_work_taken_whole_and_short_control_backfilled_from_f():
    s = rs.sample_work(stats(6, {0: 2}), "w")
    assert len(s) == 6 and {x["stratum"] for x in s} == {"D", "R"}
    st = stats(20, {i: 1 for i in range(4)}, fail=range(4, 18))   # R has 2 units only
    s = rs.sample_work(st, "w")
    c = {k: sum(1 for x in s if x["stratum"] == k) for k in "DFR"}
    assert c == {"D": 4, "F": 4, "R": 2}


def test_display_swap_recorded():
    s = rs.sample_work(stats(40, {0: 1}), "w")
    assert all({x["shown_1"], x["shown_2"]} == {"A", "B"} for x in s)
    assert len({x["shown_1"] for x in s}) == 2   # both orders occur in ten coins (seeded)


def test_first_sense_fallback():
    assert rs.first_sense_gloss("κῶμα, ατος, τό, (perh. cogn. with κεῖμαι) deep sleep, αὐτῷ Il. 14.359") == "deep sleep"
    assert rs.first_sense_gloss("") == ""


# ----------------------------------------------------------------------------------------------- build on a fake work

def fake_work(root: Path, slug="fake", n=14):
    d = root / slug
    d.mkdir(parents=True)
    with (d / "units.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"unit_id": f"K1.{i}", "locus": f"K. I {i}", "greek": f"[{i}] λόγος {i}. [None] ἔτι"}, ensure_ascii=False) + "\n")
    units = {}
    for i in range(n):
        units[f"K1.{i}"] = {"a": {"verdict": "fail" if i in (2, 3) else "pass"}, "b": {"verdict": "pass"}, "c": {"verdict": "judge_failed_gate"}, "verdict": "pass"}
    (d / "checks.json").write_text(json.dumps({"units": units}), encoding="utf-8")
    cols = ["unit_id", "surface", "dilemma_lemma", "odycy_lemma", "lsj_entry_id", "lsj_headword", "lsj_sense_count",
            "lsj_entry_text", "lsj_first_sense_gloss", "rendering_A", "rendering_B", "agree"]
    with (d / "term_table.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i in range(n):
            w.writerow({"unit_id": f"K1.{i}", "surface": "λόγος,", "dilemma_lemma": "λόγος", "lsj_entry_id": "n1", "lsj_headword": "λόγος",
                        "lsj_sense_count": "9", "lsj_entry_text": "λόγος, ὁ, computation, reckoning", "lsj_first_sense_gloss": "",
                        "rendering_A": f"word{i}", "rendering_B": "word" if i < 5 else f"word{i}", "agree": "n" if i < 5 else "y"})
    for lab, model in rs.RENDERINGS.items():
        with (d / f"renderings_{model}.jsonl").open("w", encoding="utf-8") as fh:
            for i in range(n):
                fh.write(json.dumps({"unit_id": f"K1.{i}", "response": {"translation": f"[{i}] {lab} text {i}. [None] more"}}) + "\n")
    return {slug: {"title_lat": "Fake", "title_eng": "Fake", "kuhn_vol": "I", "kuhn_pages": "0-13"}}


def test_build_and_score_round_trip(tmp_path):
    works = fake_work(tmp_path / "fd")
    out = tmp_path / "out"
    summ = rs.build(tmp_path / "fd", out, works=works)
    assert summ["fake"]["sampled"] == 10 and summ["fake"]["strata"]["D"] == {"N": 4, "n": 4}
    html_ = (out / "fake.html").read_text(encoding="utf-8")
    assert "[None]" not in html_ and "fable" not in html_ and "opus" not in html_   # no model names on the sheet
    assert "computation" in html_   # first sense from the entry text when the column is empty
    rows = list(csv.DictReader((out / "fake.csv").open(encoding="utf-8-sig")))
    key = list(csv.DictReader((out / "key" / "sample_key.csv").open(encoding="utf-8-sig")))
    assert [r["unit_id"] for r in rows] == [k["unit_id"] for k in key]
    # rendering_1 on the sheet is the model the key names as shown_1
    for r, k in zip(rows, key):
        lab = "A" if k["shown_1"] == rs.RENDERINGS["A"] else "B"
        assert r["rendering_1"].split(" text ")[0].endswith(lab)
    # fill: reviewer always prefers the A model and marks a term wrong in the B model on D/F units only
    for r, k in zip(rows, key):
        a_lab = "1" if k["shown_1"] == rs.RENDERINGS["A"] else "2"
        b_lab = "2" if a_lab == "1" else "1"
        r.update(reviewer="X", better=a_lab, term_wrong=b_lab if k["stratum"] in "DF" else "none", sense_wrong="None")
    rows[-1].update(better="maybe")   # unreadable value: reported, row skipped
    filled = tmp_path / "filled.csv"
    with filled.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    res = rs.score([filled], out / "key" / "sample_key.csv", tmp_path / "scores")
    s = res["works"]["fake"]
    assert len(res["problems"]) == 1 and "maybe" in res["problems"][0]
    assert s["n_units"] == 9
    A, B = rs.RENDERINGS["A"], rs.RENDERINGS["B"]
    assert s["preference"][A] == 9 and s["preference"][B] == 0 and s["preference"]["sign_test_p"] < 0.01
    assert s["term_wrong"][A]["units"]["k"] == 0
    n_flag = sum(1 for k in key[:-1] if k["stratum"] in "DF")
    assert s["term_wrong"][B]["units"]["k"] == n_flag
    assert s["any_error"]["control_R"]["k"] == 0 and s["any_error"]["flagged_D_F"]["k"] == n_flag
    # work estimate = share of the work's units in D+F (every flagged unit has an error, no control has one)
    pops = {k["stratum"]: int(k["stratum_N"]) for k in key}
    if all(any(k["stratum"] == st for k in key[:-1]) for st in pops):
        assert s["any_error"]["work_estimate_pct"] == round(100 * (pops.get("D", 0) + pops.get("F", 0)) / 14, 1)
    assert (tmp_path / "scores" / "summary.md").read_text(encoding="utf-8").count("| fake |") == 1


def test_norm_aliases():
    assert rs.norm(" In both ", rs.WRONG) == "both" and rs.norm("1+2", rs.WRONG) == "both"
    assert rs.norm("", rs.WRONG) == "" and rs.norm("maybe", rs.WRONG) is None
    assert rs.norm("Neither", rs.BETTER) == "neither"


def test_weighted_estimate_and_agreement():
    def r(u, st, N, x, rev="a"):
        return {"unit_id": u, "stratum": st, "stratum_N": N, "work_N": 100, "reviewer": rev}
    units = {"u1": [r("u1", "D", 4, 1)], "u2": [r("u2", "F", 36, 1)], "u3": [r("u3", "R", 60, 0)], "u4": [r("u4", "R", 60, 0)]}
    vals = {"u1": 1.0, "u2": 0.0, "u3": 1.0, "u4": 0.0}
    assert rs.weighted_estimate(units, vals) == round(100 * (0.04 * 1 + 0.36 * 0 + 0.60 * 0.5), 1)
    assert rs.weighted_estimate(units, {"u1": 1.0}) is None   # strata F and R unread
    two = {"u1": [{"better": "1", "term_wrong": "none", "sense_wrong": ""}, {"better": "1", "term_wrong": "2", "sense_wrong": ""}]}
    ag = rs.agreement(two)
    assert ag["better"]["k"] == 1 and ag["term_wrong"]["k"] == 0 and "sense_wrong" not in ag


def test_binom_and_wilson():
    assert rs.binom_two_sided(5, 10) == 1.0
    assert rs.binom_two_sided(10, 10) == round(2 / 1024, 4)
    assert rs.wilson(0, 0) is None and rs.wilson(5, 10)[0] < 50 < rs.wilson(5, 10)[1]


# ------------------------------------------------------------------------------------------------- published outputs

@pytest.mark.skipif(not (rs.FD_ROOT / "de-comate" / "checks.json").exists(), reason="First Drafts outputs not present")
def test_published_work_sample(tmp_path):
    w = rs.load_work("de-comate")
    st = rs.unit_stats(w)
    assert len(st) == 23 and sum(x["n_disagree"] for x in st) == 44   # README: 131 of 175 targets agree
    s = rs.sample_work(st, "de-comate")
    assert len(s) == 10 and sum(1 for x in s if x["stratum"] == "D") == 4
    key = rs.OUT_ROOT / "key" / "sample_key.csv"
    if key.exists():   # the committed key matches the rule
        rows = [r for r in csv.DictReader(key.open(encoding="utf-8-sig")) if r["work"] == "de-comate"]
        assert [r["unit_id"] for r in rows] == [x["unit_id"] for x in s]
