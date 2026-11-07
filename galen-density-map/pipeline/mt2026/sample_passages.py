"""MT-2026 consistency probe — stage 1: sample passages and target terms.

Report-only. Reads the frozen lemmatized JSONL and outputs/punch_list.csv; writes under
data/qc/mt2026/. No Greek judgment: every selection is mechanical.

Design (see mt2026_consistency_probe_spec.md):
- Works: De temperamentis (tlg009.grc1; translated, Zainaldin's 'easy' work) and
  De compositione medicamentorum per genera (tlg077; untranslated, Zainaldin's 'hard' work).
- Passages: contiguous windows of ~PASSAGE_TOKENS tokens, no overlap, whole corpus of each
  work tiled; punch-list density = punch-list lemmas per 100 tokens (NOUN/ADJ only).
- Stratified sample: per work, N_PER_WORK passages drawn evenly from density terciles.
- Targets per passage: every punch-list token (class 'punch') plus an equal number of
  control tokens: NOUN/ADJ tokens whose lemma is NOT on the punch list and whose LSJ sense
  count is >= CONTROL_MIN_SENSES (i.e. well-described vocabulary), chosen at random.
- The translator sheet lists target surfaces by position only; the class column lives in the
  private targets file so the translating model cannot see which words are 'hard'.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LEMMATIZED = ROOT / "data" / "lemmatized" / "galen"
OUTPUTS = ROOT / "outputs"
OUT = ROOT / "data" / "qc" / "mt2026"

WORKS = {
    "temp": "urn_cts_greekLit_tlg0057.tlg009.1st1K-grc1",   # De temperamentis
    "cmpg": "urn_cts_greekLit_tlg0057.tlg077.1st1K-grc1",   # De comp. med. per genera
}
PASSAGE_TOKENS = 120
N_PER_WORK = 20
CONTROL_MIN_SENSES = 3
TARGET_POS = {"NOUN", "ADJ"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def load_tokens(stem: str) -> list[dict]:
    p = LEMMATIZED / f"{stem}.jsonl"
    with p.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--key-dir", required=True, help="directory OUTSIDE the repo for the class key")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    key_dir = Path(a.key_dir)
    key_dir.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    punch = {nfc(r["lemma"]): r for r in csv.DictReader((OUTPUTS / "punch_list.csv").open(encoding="utf-8"))}
    lsj_senses: dict[str, int] = {}
    kl = OUTPUTS / "keyness_with_lsj.csv"
    if kl.exists():
        for r in csv.DictReader(kl.open(encoding="utf-8")):
            try:
                lsj_senses[nfc(r["lemma"])] = int(r.get("lsj_sense_count") or 0)
            except ValueError:
                pass

    passages, targets, translator_rows = [], [], []
    for wkey, stem in WORKS.items():
        toks = load_tokens(stem)
        windows = []
        for start in range(0, len(toks) - PASSAGE_TOKENS + 1, PASSAGE_TOKENS):
            seg = toks[start:start + PASSAGE_TOKENS]
            n_punch = sum(1 for t in seg if t.get("pos") in TARGET_POS and nfc(t["lemma"]) in punch)
            windows.append((start, n_punch / PASSAGE_TOKENS * 100.0))
        windows.sort(key=lambda w: w[1])
        k = len(windows) // 3
        terciles = [windows[:k], windows[k:2 * k], windows[2 * k:]]
        per = [N_PER_WORK // 3 + (1 if i < N_PER_WORK % 3 else 0) for i in range(3)]
        chosen = []
        for tier, n in zip(terciles, per):
            chosen += [(w, t) for w, t in zip(rng.sample(tier, n), [("low", "mid", "high")[terciles.index(tier)]] * n)]
        chosen.sort(key=lambda c: c[0][0])
        for (start, dens), tier in chosen:
            pid = f"{wkey}-{start:06d}"
            seg = toks[start:start + PASSAGE_TOKENS]
            text = " ".join(t["surface"] for t in seg)
            punch_idx = [j for j, t in enumerate(seg) if t.get("pos") in TARGET_POS and nfc(t["lemma"]) in punch]
            ctrl_pool = [j for j, t in enumerate(seg) if t.get("pos") in TARGET_POS and nfc(t["lemma"]) not in punch
                         and lsj_senses.get(nfc(t["lemma"]), 0) >= CONTROL_MIN_SENSES]
            ctrl_idx = rng.sample(ctrl_pool, min(len(punch_idx), len(ctrl_pool))) if punch_idx else []
            tgt = sorted([(j, "punch") for j in punch_idx] + [(j, "control") for j in ctrl_idx])
            passages.append({"passage_id": pid, "work": wkey, "work_stem": stem, "start_index": start,
                             "n_tokens": len(seg), "punch_density_per100": round(dens, 2), "density_tier": tier,
                             "n_punch_targets": len(punch_idx), "n_control_targets": len(ctrl_idx), "text": text})
            for j, cls in tgt:
                t = seg[j]
                targets.append({"passage_id": pid, "target_no": j, "surface": t["surface"], "lemma": nfc(t["lemma"]),
                                "pos": t.get("pos"), "class": cls, "lsj_tier": punch.get(nfc(t["lemma"]), {}).get("lsj_tier", ""),
                                "lsj_sense_count": lsj_senses.get(nfc(t["lemma"]), "")})
                translator_rows.append({"passage_id": pid, "target_no": j, "surface": t["surface"]})

    with (OUT / "passages.jsonl").open("w", encoding="utf-8") as fh:
        for p in passages:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with (OUT / "translator_targets.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["passage_id", "target_no", "surface"])
        w.writeheader(); w.writerows(translator_rows)
    with (key_dir / "mt2026_target_classes.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(targets[0].keys()))
        w.writeheader(); w.writerows(targets)
    meta = {"seed": a.seed, "passage_tokens": PASSAGE_TOKENS, "n_per_work": N_PER_WORK, "works": WORKS,
            "control_min_lsj_senses": CONTROL_MIN_SENSES, "n_passages": len(passages),
            "n_targets": len(targets), "n_punch": sum(t["class"] == "punch" for t in targets),
            "n_control": sum(t["class"] == "control" for t in targets),
            "class_key_location": "outside the repository until scoring; published with results"}
    (OUT / "sample_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
