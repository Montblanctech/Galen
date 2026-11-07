"""End-to-end: run the audit on the tiny corpus, then score a fake reader."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from greek_lemma_audit.audit import AuditConfig, run_audit
from greek_lemma_audit.cli import main
from greek_lemma_audit.corpus import author_of, discover_works, tokenize_text
from greek_lemma_audit.m5 import score_sheet


def test_discover_and_author_filter(tiny_corpus):
    refs = discover_works(tiny_corpus["root"])
    assert [r.author for r in refs] == ["tlg9001", "tlg9002"]
    assert [r.subcorpus for r in refs] == ["reference", "reference"]
    assert len(discover_works(tiny_corpus["root"], authors=["tlg9002"])) == 1
    assert author_of("urn_cts_greekLit_tlg0057.tlg008.1st1K-grc1") == "tlg0057"
    assert author_of("plain_text_file") == "unknown"


def test_tokenize_text_strips_punctuation():
    toks = tokenize_text("Ἐν ἀρχῇ, ἦν· ὁ λόγος. 12")
    assert [t.surface for t in toks] == ["Ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]


def _run(tiny_corpus, **over):
    out = tiny_corpus["tmp"] / "out"
    params = dict(out_dir=out, corpus_root=tiny_corpus["root"], systems=["reference", "stanza-perseus"],
                  morpheus_caches=[tiny_corpus["cache"]], stanza_caches=[tiny_corpus["stanza_cache"]],
                  key_out=tiny_corpus["tmp"] / "private" / "key.csv", controls_path=tiny_corpus["controls"],
                  m5_n=5, seed=7, m2_sample=4, no_m3=True, text_root=None)
    params.update(over)
    summary, code = run_audit(AuditConfig(**params))
    return summary, code, out


def test_full_audit_numbers(tiny_corpus):
    summary, code, out = _run(tiny_corpus)
    assert code == 0
    assert (out / "audit_summary.json").exists() and (out / "audit_report.md").exists()

    # M1 reference: 14 tokens; ξενικόν uncached (1); γαήτσρ, φλεβά inadmissible (2); νεύρον admissible accent-blind
    tw = summary["m1_admissibility"]["systems"]["reference"]["token_weighted"]
    assert tw["total"] == 14 and tw["not_in_cache"] == 1 and tw["inadmissible"] == 2 and tw["no_analysis"] == 0
    assert tw["analyzable"] == 13 and tw["admissible"] == 11
    assert tw["admissible_pct_of_analyzable"] == round(100 * 11 / 13, 2)
    assert tw["admissible_wilson95_lo_pct"] < tw["admissible_pct_of_analyzable"] < tw["admissible_wilson95_hi_pct"]
    by_author = summary["m1_admissibility"]["systems"]["reference"]["by_author"]
    assert by_author["tlg9001"]["total"] == 8 and by_author["tlg9002"]["total"] == 6
    g1b = summary["m1_admissibility"]["g1b_controls_replay"]
    assert g1b["matched_expected"] == 4 and g1b["mismatches"] == []
    # accent-strict diagnostic: νεύρον vs νεῦρον fails strictly -> 10 strict of 13
    assert summary["m1_admissibility"]["systems"]["reference"]["accent_strict_admissible_tokens"] == 10
    # stanza-perseus M1 also reported (its own lemmas): γαστήρ admissible, κόν / ξενι not cached
    assert summary["m1_admissibility"]["systems"]["stanza-perseus"]["token_weighted"]["inadmissible"] == 0

    # M2: ξενικόν unaligned (split in system 2) -> 13 aligned of 14 eligible;
    # disagreements γαστρὸς (real), φλεβῶν (real), νεύρου (accent only)
    pop = summary["m2_agreement"]["population"]
    assert pop["n_eligible_tokens"] == 14 and pop["n_fully_aligned"] == 13 and pop["alignment_drop"] == 1
    pw = pop["pairwise"]["reference__stanza-perseus"]
    assert pw["k"] == 10 and pw["n"] == 13
    assert pop["reference_vs_consensus_of_others"]["k"] == 10
    dis = summary["m2_agreement"]["disagreements"]
    assert dis["n_rows"] == 3 and dis["g2a_class_counts"] == {"real_disagreement": 2, "accent_only": 1}
    rows = list(csv.DictReader((out / "disagreements.csv").open(encoding="utf-8")))
    assert {r["surface"] for r in rows} == {"γαστρὸς", "νεύρου", "φλεβῶν"}
    assert {r["pattern"] for r in rows} == {"audit_disagrees_with_consensus"}
    assert all("[" in r["context"] for r in rows)
    sample = summary["m2_agreement"]["sample"]
    assert sample["n_emitted"] == 4 and sample["seed"] == 7 and sample["population_tokens"] == 14

    # M5 sheet: 5 random + 4 controls, blind columns only; key has the gate roles and the M2 flag
    sheet = list(csv.DictReader((out / "reviewer_sheet.csv").open(encoding="utf-8")))
    assert len(sheet) == 9 and "control_id" not in sheet[0]
    key = list(csv.DictReader((tiny_corpus["tmp"] / "private" / "key.csv").open(encoding="utf-8")))
    roles = {r["control_id"]: r["gate_role"] for r in key if r["kind"] == "control"}
    assert roles == {"C01": "nonword", "C02": "wrong_unambiguous", "C03": "wrong_accent", "C04": "anchor"}
    flagged = [r for r in key if r["m2_flag"] == "y"]
    assert all(r["surface_form"] in {"γαστρὸς", "νεύρου", "φλεβῶν"} for r in flagged)
    assert summary["m5_reviewer_sheet"]["scored"] is False
    br = summary["bounded_range"]
    assert br["floor_m1"]["admissible_pct_of_analyzable"] == tw["admissible_pct_of_analyzable"]
    assert br["upper_bound_m2"]["audit_vs_consensus_pct"] == pop["reference_vs_consensus_of_others"]["agree_pct"]
    assert summary["m3_lsj_citation_gold"]["status"] == "skipped"
    assert "Morpheus" in (out / "audit_report.md").read_text(encoding="utf-8")


def test_reproducible_seeds(tiny_corpus):
    s1, _, out = _run(tiny_corpus)
    k1 = (tiny_corpus["tmp"] / "private" / "key.csv").read_text(encoding="utf-8")
    s2, _, _ = _run(tiny_corpus)
    k2 = (tiny_corpus["tmp"] / "private" / "key.csv").read_text(encoding="utf-8")
    assert k1 == k2
    assert s1["m2_agreement"]["sample"] == s2["m2_agreement"]["sample"]


def test_missing_key_out_skips_sheet(tiny_corpus):
    summary, code, _ = _run(tiny_corpus, key_out=None)
    assert code == 0 and summary["m5_reviewer_sheet"]["status"] == "skipped"


def _force_unavailable(monkeypatch, *classes):
    """Make the given System classes probe as unavailable, whatever this machine has installed."""
    from greek_lemma_audit.systems.base import Availability

    for cls in classes:
        untested = cls.__name__ == "DilemmaSystem"
        monkeypatch.setattr(cls, "probe", lambda self, _u=untested: Availability(False, "forced unavailable (test)", untested=_u))


def test_unavailable_systems_are_reported_not_fatal(tiny_corpus, monkeypatch):
    from greek_lemma_audit.systems import DilemmaSystem, StanzaSystem

    _force_unavailable(monkeypatch, DilemmaSystem, StanzaSystem)
    summary, code, _ = _run(tiny_corpus, systems=["reference", "dilemma", "stanza-proiel"], stanza_caches=[])
    assert code == 0
    assert summary["systems"]["dilemma"]["status"] == "skipped"
    assert summary["systems"]["dilemma"]["untested_adapter"] is True
    assert summary["systems"]["stanza-proiel"]["status"] == "skipped"  # no cache, no model
    assert summary["m2_agreement"]["status"] == "skipped"
    report = (tiny_corpus["tmp"] / "out" / "audit_report.md").read_text(encoding="utf-8")
    assert "no cross-system upper bound" in report


def test_audit_system_unavailable_is_an_error(tiny_corpus, monkeypatch):
    from greek_lemma_audit.systems import OdycySystem

    _force_unavailable(monkeypatch, OdycySystem)
    summary, code, _ = _run(tiny_corpus, systems=["odycy", "reference"], audit_system="odycy")
    assert code == 2 and "odycy" in summary["error"]


def test_score_sheet_gate_and_kappa(tiny_corpus):
    summary, code, out = _run(tiny_corpus)
    key_path = tiny_corpus["tmp"] / "private" / "key.csv"
    key = list(csv.DictReader(key_path.open(encoding="utf-8")))

    def answers(path: Path, perfect: bool):
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_id", "answer", "correct_lemma_if_wrong"])
            for r in key:
                if r["kind"] == "control":
                    a = r["expected"] if perfect else ("y" if r["gate_role"] == "nonword" else r["expected"])
                    w.writerow([r["row_id"], a, r["expected_lemma"] if a == "n" else ""])
                else:
                    w.writerow([r["row_id"], "y" if r["lemma_produced"] not in {"γαήτσρ", "φλεβά"} else "n", ""])

    a1 = tiny_corpus["tmp"] / "r1.csv"
    a2 = tiny_corpus["tmp"] / "r2.csv"
    answers(a1, perfect=True)
    answers(a2, perfect=False)  # misses the non-word -> FAIL
    res = score_sheet(key_path, [a1, a2], out / "score", ["r1", "r2"])
    assert res["readers"]["r1"]["gate"] == "PASS"
    assert res["readers"]["r2"]["gate"] == "FAIL" and "non-word" in res["readers"]["r2"]["gate_fail_reasons"][0]
    assert res["n_random"] == 5
    r = res["readers"]["r1"]["random"]
    assert r["y"] + r["n"] + r["unsure"] == 5 and r["wilson95_lower_bound_variant"] is not None
    assert res["agreement_random"]["cohen_kappa_3cat"] == 1.0
    assert (out / "score" / "control_audit.csv").exists() and (out / "score" / "verdicts.csv").exists()


def test_cli_run_and_score(tiny_corpus, capsys):
    out = tiny_corpus["tmp"] / "cli_out"
    key = tiny_corpus["tmp"] / "p" / "key.csv"
    code = main(["run", "--out", str(out), "--corpus-root", str(tiny_corpus["root"]), "--author", "tlg9001",
                 "--systems", "reference", "--morpheus-cache", str(tiny_corpus["cache"]), "--key-out", str(key),
                 "--m5-n", "3", "--no-m3", "--quiet"])
    assert code == 0
    summary = json.loads((out / "audit_summary.json").read_text(encoding="utf-8"))
    assert summary["corpus"]["n_works"] == 1 and summary["corpus"]["author_filter"] == ["tlg9001"]
    assert summary["kit"]["command_line"].startswith("run ")
    assert main(["systems"]) == 0
    assert "reference" in capsys.readouterr().out
