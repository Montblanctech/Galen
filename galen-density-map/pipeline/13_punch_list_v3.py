"""Stage 13 — the v3.0 punch list: re-tiered with attributed machine and reader columns (2026-11-06).

Nothing in ``outputs/punch_list.csv`` is edited. This stage joins it with stage 12 (Dilemma headword
map), stage 12c (two blind readers) and Phase 3 v0 (attribution) and writes a NEW table whose
``tier_v3`` label says what the evidence says, row by row:

  thin                     LSJ entry with one sense (as before) and Dilemma returns the same headword
  thin_contested           LSJ thin, but Dilemma maps the tokens to another headword (review queue)
  artifact_suspect         absent tier; both blind readers call it an artifact (machine class agrees or not)
  artifact_suspect_machine absent tier; readers disagree or did not both say artifact, Dilemma says artifact
  real_no_perseus_lsj      absent tier; both readers call it a real headword (38 names, 70 medical words)
  real_contested           absent tier; readers split real/artifact

Every row keeps the old ``lsj_tier`` and carries: machine_class, dilemma_top_headword (+ share, LSJ
tier of that headword), reader verdicts/headwords/proper-name flags, a ``headword_consensus``
(readers agree on a headword; else Dilemma's where both readers called artifact without agreeing;
else blank) and ``consensus_source``. Plan §3: no gloss is written, no lemma is changed; the
headwords are attributed to the system or reader that produced them.

Outputs (outputs/phase3/): punch_list_v3.csv (1,433 rows), real_headwords_no_perseus_lsj.csv
(the 108, with concordance counts and Kühn loci from attributed_punch_list.csv), punch_list_v3_summary.json.
"""
from __future__ import annotations

import csv
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402

OUT = ROOT / "outputs" / "phase3"
R1, R2 = "reader1_fable-5-1", "reader2_opus-5-5"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    punch = list(csv.DictReader((ROOT / "outputs" / "punch_list.csv").open(encoding="utf-8")))
    hw = {nfc(r["lemma"]): r for r in csv.DictReader((OUT / "absent_tier_headword_map.csv").open(encoding="utf-8"))}
    verdicts = {nfc(r["lemma"]): r for r in csv.DictReader((OUT / "reader_pass" / "absent_tier_verdicts.csv").open(encoding="utf-8")) if r["kind"] == "target"}
    attrib = {}
    ap = OUT / "attributed_punch_list.csv"
    if ap.exists():
        attrib = {nfc(r["lemma"]): r for r in csv.DictReader(ap.open(encoding="utf-8"))}

    rows = []
    tiers = Counter()
    for r in punch:
        lem = nfc(r["lemma"])
        h = hw.get(lem, {})
        v = verdicts.get(lem)
        cls = h.get("machine_class", "")
        dil = h.get("dilemma_top_headword", "")
        v1 = v2 = h1 = h2 = p1 = p2 = ""
        if v:
            v1, v2 = v[f"{R1}_verdict"], v[f"{R2}_verdict"]
            h1, h2 = nfc(v[f"{R1}_headword"]), nfc(v[f"{R2}_headword"])
            p1, p2 = v[f"{R1}_proper_name"], v[f"{R2}_proper_name"]
        if r["lsj_tier"] == "thin":
            tier = "thin" if cls == "same_headword" else "thin_contested"
        else:
            if v1 == v2 == "artifact":
                tier = "artifact_suspect"
            elif v1 == v2 == "real_headword":
                tier = "real_no_perseus_lsj"
            elif "artifact" in (v1, v2) and "real_headword" in (v1, v2):
                tier = "real_contested"
            elif cls in ("relemmatized_lsj", "relemmatized_no_lsj", "split"):
                tier = "artifact_suspect_machine"
            else:
                tier = "real_contested"
        tiers[tier] += 1
        # headword consensus
        if h1 and h2 and blind(h1) == blind(h2):
            cons, src = h1, "readers_agree"
        elif v1 == v2 == "artifact" and dil and (blind(dil) == blind(h1) or blind(dil) == blind(h2)):
            cons, src = dil, "dilemma_plus_one_reader"
        elif v1 == v2 == "real_headword":
            cons, src = (h1 or h2 or lem), "readers_agree_real"
        else:
            cons, src = "", ""
        a = attrib.get(lem, {})
        rows.append({
            "lemma": lem, "pos": r["pos"], "galen_raw_count": r["galen_raw_count"], "galen_per10k": r["galen_per10k"],
            "log_likelihood": r["log_likelihood"], "lsj_tier_v2": r["lsj_tier"], "lsj_sense_count": r["lsj_sense_count"],
            "tier_v3": tier,
            "machine_class": cls, "dilemma_top_headword": dil, "dilemma_top_share": h.get("dilemma_top_share", ""),
            "dilemma_headword_lsj_tier": h.get("top_headword_lsj_tier", ""), "dilemma_headword_key_in_map": h.get("top_headword_key_in_mapA", ""),
            "m1_admissible_share": h.get("m1_admissible_share", ""),
            f"{R1}_verdict": v1, f"{R1}_headword": h1, f"{R1}_proper_name": p1,
            f"{R2}_verdict": v2, f"{R2}_headword": h2, f"{R2}_proper_name": p2,
            "headword_consensus": cons, "consensus_source": src,
            "proper_name": "y" if p1 == p2 == "y" else ("n" if p1 == p2 == "n" else (p1 or p2)),
            "n_attestations": a.get("concordance_n", ""), "n_works": a.get("n_works", ""),
            "kuhn_loci_listed_v0_cap10": len([x for x in (a.get("kuhn_loci") or "").split(";") if x.strip()]) if a else "",
            "kuhn_loci_sample": ";".join([x for x in (a.get("kuhn_loci") or "").split(";") if x.strip()][:3]),
            "lsj_headword_v2": a.get("lsj_headword", ""), "tradition_hippocrates": a.get("tradition_hippocrates", ""),
            "tradition_dioscorides": a.get("tradition_dioscorides", ""), "machine_flags_v0": a.get("machine_flags", ""),
            "example_context": r.get("example_context", ""),
        })
    cols = list(rows[0].keys())
    with (OUT / "punch_list_v3.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    real = [x for x in rows if x["tier_v3"] == "real_no_perseus_lsj"]
    real.sort(key=lambda x: (x["proper_name"] == "y", -float(x["log_likelihood"])))
    with (OUT / "real_headwords_no_perseus_lsj.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(real)
    summary = {
        "date": "2026-11-06", "stage": "13_punch_list_v3", "report_only": True, "n": len(rows),
        "tier_v3": dict(tiers), "tier_v2": dict(Counter(x["lsj_tier_v2"] for x in rows)),
        "real_no_perseus_lsj": {"n": len(real), "proper_names": sum(x["proper_name"] == "y" for x in real),
                                "common_words": sum(x["proper_name"] != "y" for x in real)},
        "headword_consensus_sources": dict(Counter(x["consensus_source"] for x in rows if x["consensus_source"])),
        "attributed_columns_present": bool(attrib),
        "headline_list": "thin (" + str(tiers["thin"]) + ") + real_no_perseus_lsj (" + str(tiers["real_no_perseus_lsj"]) + "); the artifact_suspect rows stay in the file, labelled, with their attributed headword",
    }
    (OUT / "punch_list_v3_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
