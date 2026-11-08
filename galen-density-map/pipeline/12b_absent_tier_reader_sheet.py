"""Stage 12b — blind reader sheet for the ``absent`` punch-list tier (ROADMAP item 8, 2026-11-06).

Question put to each reader, lemma by lemma, with no lemmatizer output shown: *is this string a
real dictionary headword, or an artifact (inflected form, mis-accented form, stem fragment,
pooled word) of some other headword?* The sheet carries the 734 ``absent``-tier punch lemmas
as targets plus salted controls, shuffled with a seed; the key stays private until scoring.

Controls (M5 convention, gate replayed by 12c):
  anchor  40 ``thin``-tier lemmas that Dilemma also returns as the headword (stage 12
          ``same_headword``), Morpheus-admissible, LSJ sense_count 1: expected ``real_headword``.
  plant   20 inflected surfaces of rich-tier (LSJ senses >= 3) Galen nouns/adjectives presented
          *as if they were lemmas*, with their own contexts: expected ``artifact`` with the odyCy
          headword (Morpheus-admissible for that surface) as the answer.

Per row the reader sees: lemma string, POS, Galen token count, up to three contexts from
different works (+-6 tokens, target bracketed) and the four most frequent surfaces. Nothing
from Dilemma, the LSJ, or the tier is shown. Readers answer ``verdict`` in
{real_headword, artifact, unsure}, ``headword`` (the dictionary headword the tokens belong to:
for an artifact, the real word; for a real headword, the correctly accented headword),
``proper_name`` in {y, n} and an optional ``note``.

Outputs: outputs/phase3/reader_pass/absent_tier_reader_sheet.csv (+ reader_instructions.txt,
sheet_meta.json); PRIVATE key to --key-out (outside the repo until 12c has scored).
Run under the audit venv (no Dilemma needed here: stage 12's CSV is read instead).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.beta_keys import lemma_to_lookup_key  # noqa: E402
from lib.census import load_census, medical_urn_stems  # noqa: E402
from lib.config import load_config  # noqa: E402

OUT = ROOT / "outputs" / "phase3" / "reader_pass"
SEED = 20261106
N_ANCHOR, N_PLANT, WIDTH = 40, 20, 6


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def blind(s: str) -> str:
    return lemma_to_lookup_key(nfc(s))


def ctx(tokens: list[dict], i: int, width: int = WIDTH) -> str:
    lo, hi = max(0, i - width), min(len(tokens), i + width + 1)
    return " ".join(f"[{tokens[j]['surface']}]" if j == i else tokens[j]["surface"] for j in range(lo, hi))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-out", required=True, type=Path, help="PRIVATE key CSV (outside the repo)")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    cfg = load_config()
    census = load_census((ROOT.parent / "phase1" / "galen_ogl_census.json").resolve())
    med_stems = medical_urn_stems(cfg, census)
    OUT.mkdir(parents=True, exist_ok=True)
    a.key_out.parent.mkdir(parents=True, exist_ok=True)

    hw_map = list(csv.DictReader((ROOT / "outputs" / "phase3" / "absent_tier_headword_map.csv").open(encoding="utf-8")))
    by_lemma = {nfc(r["lemma"]): r for r in hw_map}
    targets = [r for r in hw_map if r["lsj_tier"] == "absent"]
    anchors_pool = [r for r in hw_map if r["lsj_tier"] == "thin" and r["machine_class"] == "same_headword"
                    and r["lemma_string_is_own_headword"] == "1" and r["m1_admissible_share"] not in ("",) and float(r["m1_admissible_share"]) >= 0.9
                    and int(r["n_surface_tokens"]) >= 5]
    anchors = rng.sample(anchors_pool, N_ANCHOR)
    print(f"targets {len(targets)}; anchor pool {len(anchors_pool)} -> {len(anchors)}", flush=True)

    # LSJ + Morpheus for plant selection
    lsj = json.load((ROOT / "data" / "lsj" / "_lsj_index.json").open(encoding="utf-8"))
    morph: dict[str, set[str]] = {}
    with (ROOT / "data" / "qc" / "h3m" / "cache" / "morpheus_by_surface.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok") and r.get("lemmas"):
                morph[nfc(r["surface_nfc"])] = {blind(x) for x in r["lemmas"]}

    punch_set = set(by_lemma)
    # --- scan medical tokens: contexts for targets/anchors; candidate plants
    want = {nfc(r["lemma"]) for r in targets} | {nfc(r["lemma"]) for r in anchors}
    occ: dict[str, list[tuple[str, str]]] = defaultdict(list)  # lemma -> [(work, ctx)]
    surf_pos: dict[tuple[str, str], Counter] = defaultdict(Counter)  # (surface, lemma) -> pos counter
    surf_occ: dict[str, list[tuple[str, str]]] = defaultdict(list)
    lem_dir = ROOT / "data" / "lemmatized" / "galen"
    works = [p for p in sorted(lem_dir.glob("*.jsonl")) if p.stem in med_stems]
    for p in works:
        toks = [json.loads(l) for l in p.open(encoding="utf-8")]
        for i, t in enumerate(toks):
            lem = nfc(t.get("lemma", ""))
            surf = nfc(t.get("surface", ""))
            if lem in want and len(occ[lem]) < 60:
                occ[lem].append((p.stem, ctx(toks, i)))
            if t.get("pos") in ("NOUN", "ADJ") and lem not in punch_set and surf and blind(surf) != blind(lem):
                surf_pos[(surf, lem)][t.get("pos")] += 1
                if len(surf_occ[surf]) < 30:
                    surf_occ[surf].append((p.stem, ctx(toks, i)))
    print(f"scanned {len(works)} works", flush=True)

    # --- plants: frequent inflected surfaces of rich LSJ headwords, Morpheus-admissible, one per headword
    cands = []
    for (surf, lem), pc in surf_pos.items():
        n = sum(pc.values())
        if n < 10:
            continue
        hit = lsj.get(lemma_to_lookup_key(lem))
        if not hit or int(hit.get("lsj_sense_count") or 0) < 3:
            continue
        if surf not in morph or blind(lem) not in morph[surf]:
            continue
        if not surf[0].islower():
            continue
        cands.append((surf, lem, n, pc.most_common(1)[0][0]))
    rng.shuffle(cands)
    plants, seen = [], set()
    for surf, lem, n, pos in cands:
        if blind(lem) in seen:
            continue
        seen.add(blind(lem))
        plants.append((surf, lem, n, pos))
        if len(plants) == N_PLANT:
            break
    print(f"plant candidates {len(cands)} -> {len(plants)}", flush=True)

    def pick_ctx(items: list[tuple[str, str]]) -> list[str]:
        by_work: dict[str, list[str]] = defaultdict(list)
        for w, c in items:
            by_work[w].append(c)
        out = []
        for w in sorted(by_work, key=lambda k: -len(by_work[k])):
            out.append(rng.choice(by_work[w]))
            if len(out) == 3:
                break
        return out

    rows, key = [], []
    for r in targets:
        lem = nfc(r["lemma"])
        rows.append({"lemma": lem, "pos": r["pos"], "galen_count": r["n_surface_tokens"], "surfaces": r["example_surfaces"],
                     "ctx": pick_ctx(occ[lem])})
        key.append({"lemma": lem, "kind": "target", "expected_verdict": "", "expected_headword": "",
                    "machine_class": r["machine_class"], "dilemma_top_headword": r["dilemma_top_headword"],
                    "dilemma_top_share": r["dilemma_top_share"], "top_headword_lsj_tier": r["top_headword_lsj_tier"],
                    "m1_admissible_share": r["m1_admissible_share"]})
    for r in anchors:
        lem = nfc(r["lemma"])
        rows.append({"lemma": lem, "pos": r["pos"], "galen_count": r["n_surface_tokens"], "surfaces": r["example_surfaces"],
                     "ctx": pick_ctx(occ[lem])})
        key.append({"lemma": lem, "kind": "anchor", "expected_verdict": "real_headword", "expected_headword": lem,
                    "machine_class": r["machine_class"], "dilemma_top_headword": r["dilemma_top_headword"],
                    "dilemma_top_share": r["dilemma_top_share"], "top_headword_lsj_tier": "thin",
                    "m1_admissible_share": r["m1_admissible_share"]})
    for surf, lem, n, pos in plants:
        rows.append({"lemma": surf, "pos": pos, "galen_count": n, "surfaces": f"{surf}:{n}", "ctx": pick_ctx(surf_occ[surf])})
        key.append({"lemma": surf, "kind": "plant", "expected_verdict": "artifact", "expected_headword": lem,
                    "machine_class": "", "dilemma_top_headword": "", "dilemma_top_share": "", "top_headword_lsj_tier": "rich",
                    "m1_admissible_share": ""})

    order = list(range(len(rows)))
    rng.shuffle(order)
    sheet_cols = ["row_id", "lemma", "pos", "galen_count", "surfaces", "context_1", "context_2", "context_3",
                  "verdict(real_headword/artifact/unsure)", "headword", "proper_name(y/n)", "note"]
    with (OUT / "absent_tier_reader_sheet.csv").open("w", encoding="utf-8", newline="") as fs, a.key_out.open("w", encoding="utf-8", newline="") as fk:
        ws = csv.writer(fs)
        ws.writerow(sheet_cols)
        wk = csv.DictWriter(fk, fieldnames=["row_id"] + list(key[0].keys()))
        wk.writeheader()
        for n, idx in enumerate(order, 1):
            rid = f"R{n:03d}"
            r = rows[idx]
            c = (r["ctx"] + ["", "", ""])[:3]
            ws.writerow([rid, r["lemma"], r["pos"], r["galen_count"], r["surfaces"], c[0], c[1], c[2], "", "", "", ""])
            wk.writerow({"row_id": rid, **key[idx]})
    instructions = f"""ABSENT-TIER READER SHEET — instructions (stage 12b, seed {a.seed})

Each row is a string that a lemmatizer emitted as a lemma for the bracketed tokens in the contexts
(Galen, First1KGreek text). Decide, from the contexts and the surface forms only:

  verdict = real_headword  : the string IS the dictionary headword of these tokens (accent may be off;
                             say so in the note but still answer real_headword if the headword is right)
          = artifact       : the string is an inflected form, a mis-accented or mis-spelled form, a stem
                             fragment, or pools tokens that belong to another headword
          = unsure         : you cannot tell from what is shown
  headword               : the correctly accented dictionary headword the bracketed tokens belong to
                           (for real_headword: repeat it, corrected; for artifact: the real word; blank if unsure)
  proper_name            : y if the headword is a personal, place or ethnic name (these are real headwords
                           that standard lexica often omit), else n
  note                   : optional, short

Do not consult a lemmatizer. Do not look rows up in this project's files. Answer every row.
Rows {len(rows)}: targets plus salted controls; the control positions are not marked.
Write answers back into the four empty columns and save as CSV with the same row_id values.
"""
    (OUT / "reader_instructions.txt").write_text(instructions, encoding="utf-8")
    meta = {"date": "2026-11-06", "seed": a.seed, "n_rows": len(rows), "n_targets": len(targets), "n_anchors": len(anchors),
            "n_plants": len(plants), "context_width": WIDTH, "key_out": "PRIVATE (outside repo until 12c scores)",
            "gate": {"plants_min_caught": 16, "anchors_min_correct": 36},
            "anchor_rule": "thin tier, Dilemma same_headword, lemma string is own Dilemma headword, M1 admissible >= .9, n >= 5",
            "plant_rule": "lower-case inflected NOUN/ADJ surface (n >= 10) of a non-punch lemma with LSJ senses >= 3, Morpheus-admissible, surface != lemma accent-blind, one per headword"}
    (OUT / "sheet_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
