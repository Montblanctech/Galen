#!/usr/bin/env python3
"""Build the H3 salted-control set from real lemmatized Galen tokens.

Controls are known-answer rows shuffled invisibly into the random-60 reviewer
sheet to detect a guessing/careless annotator. Two kinds:
  - wrong_plant : odyCy produced a lemma we KNOW is wrong (documented errors).
                  A genuine reader flags it (n) and supplies the right headword.
  - right_anchor: odyCy produced the CORRECT headword for an inflected form.
                  A genuine reader confirms it (y).

Ground truth comes from data/qc/suspect_high_freq_lemmas.csv,
h3_fragmentation_pairs.csv, h3_irregular_carryover.csv (the documented error set).
Output row format matches accuracy_sample_random60.csv exactly, PLUS hidden
expected-answer columns (strip these before the sheet goes to a reviewer).
"""
from __future__ import annotations
import csv, json, sys, unicodedata
from pathlib import Path

QC = Path(__file__).resolve().parent
LEMDIR = QC.parent / "lemmatized" / "galen"
SAMPLE = QC / "accuracy_sample_random60.csv"
OUT = QC / "accuracy_controls.csv"
CTX = 7  # words either side

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

# (produced_lemma, correct_lemma, strength, note)
WRONG_PLANTS = [
    ("γαήτσρ", "γαστήρ", "unambiguous", "neural hallucination / garbled non-word; any reader flags it"),
    ("δεικέω", "δείκνυμι", "unambiguous", "C4a: consistently-wrong lemma for irregular verb"),
    ("φλεβά", "φλέψ", "unambiguous", "fragmentation: inflected stem emitted as lemma"),
    ("ἥπατος", "ἧπαρ", "unambiguous", "fragmentation: genitive stem as lemma"),
    ("ἀρτηριόν", "ἀρτηρία", "unambiguous", "wrong/variant headword for artery"),
    ("κινήσεως", "κίνησις", "unambiguous", "genitive form used as the lemma"),
    ("νεύρον", "νεῦρον", "accent", "accent error (acute for circumflex) — sensitivity item"),
    ("φαρμάκον", "φάρμακον", "accent", "accent error — sensitivity item"),
]
# correct headwords; we require an INFLECTED surface (surface != lemma) so it is a
# real lemmatization, not identity passthrough.
RIGHT_ANCHORS = ["αἷμα", "θερμός", "ψυχρός", "καρδία", "ὀστέον", "νόσος"]

def load_exclusions():
    excl = set()
    if SAMPLE.exists():
        with SAMPLE.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                excl.add((r["work_stem"], r["token_index"]))
    return excl

def scan(targets_lemmas):
    """Return {lemma: (work_stem, i, surface, pos)} first hit per target lemma."""
    want = {nfc(l) for l in targets_lemmas}
    hits = {}
    for jf in sorted(LEMDIR.glob("*.jsonl")):
        stem = jf.stem
        with jf.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                t = json.loads(line)
                lem = nfc(t.get("lemma", ""))
                surf = t.get("surface", "")
                if lem in want and surf:
                    key = (lem, surf.lower() != lem.lower())  # track inflected-ness
                    if lem not in hits:
                        hits[lem] = (stem, t["i"], surf, t.get("pos", ""), surf.lower() != lem.lower())
        # early exit if all found
        if all(l in hits for l in want):
            break
    return hits

def context_for(stem, idx):
    jf = LEMDIR / f"{stem}.jsonl"
    surs = []
    with jf.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                surs.append(json.loads(line)["surface"])
    lo, hi = max(0, idx - CTX), min(len(surs), idx + CTX + 1)
    parts = []
    for j in range(lo, hi):
        parts.append(f"[{surs[j]}]" if j == idx else surs[j])
    return " ".join(parts)

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    excl = load_exclusions()
    rows = []
    cid = 0

    # wrong plants
    hits = scan([p[0] for p in WRONG_PLANTS])
    for produced, correct, strength, note in WRONG_PLANTS:
        h = hits.get(nfc(produced))
        if not h:
            print(f"  MISS wrong_plant produced={produced} (no token found)")
            continue
        stem, i, surf, pos, _ = h
        if (stem, str(i)) in excl:
            print(f"  SKIP {produced} — collides with random-60")
            continue
        cid += 1
        rows.append(dict(
            control_id=f"C{cid:02d}", control_type="wrong_plant", strength=strength,
            surface_form=surf, lemma_produced=produced, pos=pos,
            one_line_context=context_for(stem, i),
            work_stem=stem, token_index=i,
            EXPECTED_answer="n", EXPECTED_correct_lemma=correct, provenance=note,
        ))

    # right anchors (need inflected surface)
    ah = scan(RIGHT_ANCHORS)
    for lem in RIGHT_ANCHORS:
        h = ah.get(nfc(lem))
        if not h or not h[4]:  # require inflected
            print(f"  MISS/identity right_anchor {lem}")
            continue
        stem, i, surf, pos, _ = h
        if (stem, str(i)) in excl:
            continue
        cid += 1
        rows.append(dict(
            control_id=f"C{cid:02d}", control_type="right_anchor", strength="unambiguous",
            surface_form=surf, lemma_produced=lem, pos=pos,
            one_line_context=context_for(stem, i),
            work_stem=stem, token_index=i,
            EXPECTED_answer="y", EXPECTED_correct_lemma="", provenance="correct headword of an inflected form",
        ))

    cols = ["control_id","control_type","strength","surface_form","lemma_produced","pos",
            "one_line_context","work_stem","token_index",
            "EXPECTED_answer","EXPECTED_correct_lemma","provenance"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    n_wrong = sum(1 for r in rows if r["control_type"] == "wrong_plant")
    n_right = sum(1 for r in rows if r["control_type"] == "right_anchor")
    print(f"\nWrote {OUT.name}: {len(rows)} controls ({n_wrong} wrong_plant, {n_right} right_anchor)")
    for r in rows:
        exp = r["EXPECTED_answer"] + ("→"+r["EXPECTED_correct_lemma"] if r["EXPECTED_correct_lemma"] else "")
        print(f"  {r['control_id']} {r['control_type']:12s} {r['strength']:11s} "
              f"{r['surface_form']:>14s}  lemma={r['lemma_produced']:<10s} expect={exp}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
