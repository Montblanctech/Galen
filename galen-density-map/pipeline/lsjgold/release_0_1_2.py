"""Package LSJ-Gold 0.1.2 as release/lsj-gold-0.1.2/ (2026-11-11). Every number in the card is read from the files.

Inputs: data/qc/lsjgold/lsj_gold_v0_1_2.csv and its three set-aside files (recheck_0_1_2.py apply), lsj_gold_scores.json
(score.py --gold lsj_gold_v0_1_2.csv --from-scored <0.1.1 scored>), docs/lsj-gold/leaderboard.json (leaderboard.py),
and the 0.1.1 release folder for LICENSE. Checksums are computed on the bytes written, LF line endings.

  python -X utf8 release_0_1_2.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parents[1]
REPO = GDM.parent
QC = GDM / "data" / "qc" / "lsjgold"
OUT = REPO / "release" / "lsj-gold-0.1.2"
PREV = REPO / "release" / "lsj-gold-0.1.1"
V = "0.1.2"
LABELS = {"stoicheia": "Stoicheia tagger-parser (2026)", "dilemma": "Dilemma 1.3.15 (Open Greek, lexicon-first)",
          "stanza_perseus": "Stanza 1.14 grc-perseus", "odycy": "odyCy 0.7.0 (grc_odycy_joint_trf)", "stanza_proiel": "Stanza 1.14 grc-proiel"}


def n_rows(p: Path) -> int:
    with p.open(encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"lsj_gold.csv": QC / "lsj_gold_v0_1_2.csv", "lsj_gold_0_1_2_dropped.csv": QC / "lsj_gold_0_1_2_dropped.csv",
             "lsj_gold_0_1_2_duplicates.csv": QC / "lsj_gold_0_1_2_duplicates.csv", "lsj_gold_0_1_2_conflicts.csv": QC / "lsj_gold_0_1_2_conflicts.csv",
             "lsj_gold_scores.json": QC / "lsj_gold_scores.json", "leaderboard.json": REPO / "docs" / "lsj-gold" / "leaderboard.json",
             "LICENSE": PREV / "LICENSE"}
    for name, src in files.items():
        (OUT / name).write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))
    sc = json.loads((QC / "lsj_gold_scores.json").read_text(encoding="utf-8"))
    n = n_rows(OUT / "lsj_gold.csv")
    nd, ndup, nc = (n_rows(OUT / f) for f in ("lsj_gold_0_1_2_dropped.csv", "lsj_gold_0_1_2_duplicates.csv", "lsj_gold_0_1_2_conflicts.csv"))
    prev = n_rows(PREV / "lsj_gold.csv")
    assert n + nd + ndup + nc == prev, "0.1.2 and its set-aside files do not add up to 0.1.1"
    with (OUT / "lsj_gold_0_1_2_conflicts.csv").open(encoding="utf-8") as fh:
        n_tok = len({(r["author"], r["work"], r["token_index"]) for r in csv.DictReader(fh)})
    summ = json.loads((QC / "recheck_0_1_2" / "summary.json").read_text(encoding="utf-8"))
    S = sc["systems"]
    order = sorted(S, key=lambda s: -S[s]["match_blind"]["pct"])
    neural = next(S[s]["scored"] for s in S if s != "dilemma")
    rows = []
    for s in order:
        b = S[s]
        ci = b["match_blind"]["wilson95"]
        c = b.get("by_lsj_citations", {})
        rows.append(f"| {LABELS.get(s, s)} | {b['scored']:,} | **{b['match_blind']['pct']:.1f}** [{ci[0]:.1f}–{ci[1]:.1f}] | "
                    f"{c.get('1', {}).get('pct', 0):.1f} | {c.get('6+', {}).get('pct', 0):.1f} |")
    authors = len(sc["loci_per_author"])
    card = f"""---
license: cc-by-4.0
language:
  - grc
tags:
  - ancient-greek
  - lemmatization
  - evaluation
  - lexicography
  - benchmark
task_categories:
  - token-classification
pretty_name: LSJ-Gold
size_categories:
  - 10K<n<100K
---

# LSJ-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek

**LSJ-Gold** measures Ancient Greek lemmatizers on the words the dictionary itself cites. Every citation in the Perseus Liddell–Scott–Jones XML that points, by CTS URN, into a free Greek edition we hold (First1KGreek and Perseus editions) is relocated to its exact token and validated by Morpheus (the surface's analyses contain the headword) or by the single word LSJ quotes at the citation. {V}: **{n:,} loci over {authors} authors.**

A system is scored by comparing its lemma at `token_index` with `headword`: accent-blind (the headline figure), strict, and article-convention-neutral figures are all printed by the reference scorer. Wilson 95% intervals in `lsj_gold_scores.json`.

## What changed from 0.1.1

1. **The weakest loci were read.** {summ['weak_loci']} loci rested only on the single word LSJ quotes, where Dilemma gives that form another lemma (and one Morpheus-validated locus of πόλεων under πολύς, found wrong earlier). A sample read had found about one in seven of their pairs wrong: LSJ often quotes a related or cross-referenced word in an entry, and that word passed as the headword's own form (θυμιήματα under θυμιάω, σπονδήν under σπένδω, Πατρέες under πάτραι). Each locus was read blind by two readers (Claude Opus and Claude Sonnet, each in its own session with only the sheet), with 10 anchors and 10 near-miss plants per sheet of 163 at unmarked positions, under a rule fixed before any answer was read: a locus stays only if both readers say yes. **{summ['kept']} stay; {nd} are dropped** (`lsj_gold_0_1_2_dropped.csv`, with both readers' answers). One sheet failed its anchor gate twice and, as the rule says, all 163 of its loci are dropped, including 117 that both its readers accepted; the two anchors every reader of that sheet rejected are LSJ filing conventions (τῷ "in what way" under τις, whose accent-blind key it shares with τίς; ὅπουπερ under ὅπου) that the instructions did not state.
2. **A locus counts once.** {ndup:,} rows repeated a locus already listed (the same token under the same headword, where LSJ cites the passage more than once in the entry). They are removed (`lsj_gold_0_1_2_duplicates.csv`); in 0.1.1 those loci weighed double.
3. **A token cannot be gold for two headwords.** {n_tok} tokens were gold under two different headwords (ἀγών and ἀγωνάρχης, κλίνω and κλίνη); at most one can be right, so all {nc} of their rows are set aside (`lsj_gold_0_1_2_conflicts.csv`).

{n:,} + {nd} + {ndup:,} + {nc} = {prev:,}, the rows of 0.1.1. Nothing was edited or added: the kept rows are 0.1.1 rows, in the same order. Every system is rescored on the same outputs as 0.1.1.

**What a reader should know.** The read only touched loci where Dilemma disagreed with the gold, so every dropped locus is a Dilemma miss; most were also missed by the other systems (the dropped golds were mostly wrong for everyone), and every system's figure rises. Dilemma's figure on once-cited headwords rises most (89.0 to {S['dilemma']['by_lsj_citations']['1']['pct']:.1f}), because the dropped loci sit mostly under headwords LSJ cites once and were chosen by Dilemma's disagreement. A sample of 50 dropped loci read afterwards held about 29 wrong golds, about 13 right ones lost to a split vote, and 8 unclear; 50 of 50 kept loci read were right. Keeping the failed sheet's 117 doubly accepted loci would give Stoicheia 92.71 and Dilemma 92.61 instead of the figures below: the two are level within their intervals either way. The readers are language models, not Greek specialists. Record: `galen-density-map/data/qc/lsjgold/recheck_0_1_2/` in the repository.

## Reference table ({sc['date']})

| system | loci | headword match % | once-cited headwords % | cited 6+ times % |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

The four neural rows are on the same {neural:,} loci. Per-author columns for every system are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/lsj-gold/.

## Files
- `lsj_gold.csv` — one row per locus: `headword`, `headword_key` (accent-blind Beta Code), `author`, `work` (TLG ids), `cited_edition`, `locator` (CTS passage), `unit`, `token_index` (0-based, into the project's token JSONL for that edition), `surface`, `validation` (`morpheus` or `quoted`), `quoted_form`, `lsj_part`, `entry_key`, `status`. Columns are described in `SCHEMA.md`.
- `lsj_gold_scores.json` — the reference scores with strata (LSJ tier, validation route, citation frequency) and per-author figures.
- `leaderboard.json` — the table as the leaderboard page renders it.
- `lsj_gold_0_1_2_dropped.csv` ({nd}), `lsj_gold_0_1_2_duplicates.csv` ({ndup:,}), `lsj_gold_0_1_2_conflicts.csv` ({nc}) — the 0.1.1 rows set aside, same columns (the dropped file adds both readers' answers).
- `SCHEMA.md`, `CITATION.cff`, `LICENSE`, `CHECKSUMS.sha256` (computed on the files as stored; `sha256sum -c CHECKSUMS.sha256` passes on the archive and on any checkout).

## How to score your lemmatizer
```
pip install "git+https://github.com/Montblanctech/Galen#subdirectory=audit-kit"
greek-lemma-audit lsjgold --system-cache DIR
```
`DIR` holds one `<system>/<stem>.jsonl` token file per covered edition, with your lemma on each token of the project's token stream (the stems and tokenisation are in the repository under `galen-density-map/pipeline/lsjgold/`). A pull request adding such caches under `submissions/<system>/` in the repository is scored by CI and gets its row.

## What the numbers mean, and what they do not
LSJ cites what a lexicographer found worth citing: this is the rare, dictionary-worthy stratum, not overall accuracy, and treebank test scores are not comparable with it. The Perseus LSJ XML is incomplete. Loci exist only for works held in a free edition; citations into works we do not hold, or by a locator scheme the edition does not carry, are counted but not located. Nothing here patches any system's output; every figure traces to a row.

## Source and citation
Repository and method: https://github.com/Montblanctech/Galen (concept DOI 10.5281/zenodo.21561962). Failure catalogues by system, the medical-vocabulary gap package and the blind reading sheets are in the repository under `galen-density-map/data/qc/lsjgold/`.

Pepperman, W. (2026). *LSJ-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962 (concept DOI: it resolves to the newest version; 0.1 and 0.1.1 stay citable at their own releases)

Underlying texts: First1KGreek (CC BY-SA 4.0), Perseus Digital Library editions and LSJ XML (CC BY-SA 3.0), Morpheus analyses via Perseids. Data: CC BY 4.0.
"""
    (OUT / "README.md").write_bytes(card.encode("utf-8"))
    schema = (PREV / "SCHEMA.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    schema = schema.split("`lsj_gold_0_1_1_dropped.csv`")[0].rstrip() + (
        f"\n\nThe three set-aside files (`lsj_gold_0_1_2_dropped.csv`, `_duplicates.csv`, `_conflicts.csv`) have the same columns; "
        "the dropped file adds `reader_A`, `reader_A_headword`, `reader_B`, `reader_B_headword` (the two blind readers' answers).\n")
    (OUT / "SCHEMA.md").write_bytes(schema.encode("utf-8"))
    cff = (PREV / "CITATION.cff").read_text(encoding="utf-8").replace("\r\n", "\n")
    cff = cff.replace("LSJ-Gold 0.1.1:", f"LSJ-Gold {V}:").replace('version: "0.1.1"', f'version: "{V}"')
    cff = "\n".join(f"date-released: {date.today().isoformat()}" if l.startswith("date-released:") else l for l in cff.split("\n"))
    (OUT / "CITATION.cff").write_bytes(cff.encode("utf-8"))
    names = sorted(p.name for p in OUT.iterdir() if p.name != "CHECKSUMS.sha256")
    sums = "".join(f"{hashlib.sha256((OUT / f).read_bytes()).hexdigest()} *{f}\n" for f in names)
    (OUT / "CHECKSUMS.sha256").write_bytes(sums.encode("utf-8"))
    print(f"release/lsj-gold-{V}: {n:,} loci; set aside {nd} + {ndup} + {nc}; files {names}")


if __name__ == "__main__":
    main()
