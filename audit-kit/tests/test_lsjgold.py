from __future__ import annotations

import csv
import json

from greek_lemma_audit.cli import main
from greek_lemma_audit.lsjgold import discover_systems, load_gold, score_systems
from greek_lemma_audit.normalize import lemma_to_lookup_key

FIELDS = ["headword", "headword_key", "author", "work", "cited_edition", "locator", "unit", "token_index",
          "surface", "validation", "quoted_form", "lsj_part", "entry_key", "status"]
# (headword, author, work, token_index, surface, validation)
ROWS = [
    ("λόγος", "tlg9001", "tlg001", 0, "λόγου", "morpheus"),
    ("σῶμα", "tlg9001", "tlg001", 1, "σώματος", "morpheus"),
    ("ὁ", "tlg9001", "tlg001", 2, "τῆς", "morpheus"),
    ("νεῦρον", "tlg9001", "tlg001", 3, "νεύρου", "quoted"),
    ("φλέψ", "tlg9001", "tlg001", 4, "φλεβῶν", "quoted"),
    ("ἀγαθός", "tlg9002", "tlg002", 0, "ἀγαθοῦ", "morpheus"),
    ("κακός", "tlg9002", "tlg002", 1, "κακῶν", "morpheus"),
    ("τέχνη", "tlg9002", "tlg002", 2, "τέχνης", "quoted"),
    ("ἔργον", "tlg9002", "tlg002", 3, "ἔργα", "quoted"),
    ("ψυχή", "tlg9003", "tlg003", 0, "ψυχῆς", "morpheus"),
]
# system "toy": right, accent-only error, article via a different form, wrong, right; work tlg9002 right except one; tlg9003 absent
TOY = {
    "tlg9001.tlg001": ["λόγος", "σωμα", "τῆς", "χεῖρ", "φλέψ"],
    "tlg9002.tlg002": ["ἀγαθός", "κακός", "τέχνη", "ἔργον"],
}


def _gold(tmp_path):
    p = tmp_path / "gold.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for hw, au, wk, idx, surf, val in ROWS:
            w.writerow({"headword": hw, "headword_key": lemma_to_lookup_key(hw), "author": au, "work": wk,
                        "cited_edition": "perseus-grc1", "locator": "1", "unit": "1", "token_index": idx,
                        "surface": surf, "validation": val, "quoted_form": surf, "lsj_part": "x", "entry_key": hw,
                        "status": "located"})
    return p


def _cache(tmp_path):
    root = tmp_path / "cache" / "toy"
    root.mkdir(parents=True)
    for work, lemmas in TOY.items():
        surf = {r[3]: r[4] for r in ROWS if f"{r[1]}.{r[2]}" == work}
        with (root / f"urn_cts_greekLit_{work}.ed1.jsonl").open("w", encoding="utf-8") as fh:
            for i, lem in enumerate(lemmas):
                fh.write(json.dumps({"i": i, "surface": surf[i], "lemma": lem}, ensure_ascii=False) + "\n")
    return tmp_path / "cache"


def test_counts_and_missing_work(tmp_path):
    gold = load_gold(_gold(tmp_path))
    assert len(gold) == 10
    systems = discover_systems([_cache(tmp_path)])
    assert list(systems) == ["toy"]
    res = score_systems(gold, systems, min_author_rows=3)
    b = res["systems"]["toy"]
    assert b["scored"] == 9 and b["missing"] == 1  # tlg9003 is not in the system's cache
    assert b["gold_works_covered"] == 2 and res["gold_works"] == 3
    # blind: σωμα counts (accent-blind); τῆς (article) and χεῖρ do not -> 7 of 9
    assert b["match_blind"]["k"] == 7 and b["match_blind"]["n"] == 9
    # strict: also loses σωμα -> 6 of 9
    assert b["match_strict"]["k"] == 6
    # article-neutral recovers τῆς -> 8 of 9
    assert b["match_article_neutral"]["k"] == 8
    assert set(b["by_author"]) == {"tlg9001", "tlg9002"}  # tlg9003 has 0 rows; min 3 met by both others
    assert b["by_author"]["tlg9001"]["k"] == 3 and b["by_author"]["tlg9001"]["n"] == 5
    assert b["by_validation"]["quoted"]["n"] == 4
    assert b["match_blind"]["wilson95"][0] < b["match_blind"]["pct"] < b["match_blind"]["wilson95"][1]


def test_min_author_rows_and_misaligned(tmp_path):
    gold = load_gold(_gold(tmp_path))
    cache = _cache(tmp_path)
    f = cache / "toy" / "urn_cts_greekLit_tlg9002.tlg002.ed1.jsonl"
    lines = f.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0]); rec["surface"] = "ΖΖΖ"
    lines[0] = json.dumps(rec, ensure_ascii=False)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = score_systems(gold, discover_systems([cache]), min_author_rows=100)
    b = res["systems"]["toy"]
    assert b["by_author"] == {} and b["by_author_below_min"]["tlg9001"] == 5
    assert b["misaligned_surface"] == 1 and b["missing"] == 2


def test_cli_lsjgold(tmp_path, capsys):
    out = tmp_path / "s" / "scores.json"
    rc = main(["lsjgold", "--system-cache", str(_cache(tmp_path)), "--gold", str(_gold(tmp_path)),
               "--out", str(out), "--min-author-rows", "3"])
    assert rc == 0
    md = capsys.readouterr().out
    assert "| toy | 9 | 1 |" in md
    assert json.loads(out.read_text(encoding="utf-8"))["systems"]["toy"]["scored"] == 9
    assert main(["lsjgold", "--system-cache", str(tmp_path / "nope")]) == 2
