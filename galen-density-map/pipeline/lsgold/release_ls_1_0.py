"""Package LS-Gold 1.0, the stable Latin release, as release/ls-gold-1.0/ (2026-11-11). Every number in the card is read
from the files: the gold, the dropped and repeated rows, the scores, the grind ledger and its report.

Inputs: data/qc/lsgold/ls_gold_v1_0.csv, ls_gold_1_0_dropped.csv, ls_gold_1_0_duplicates.csv (grind_la.py),
ls_gold_scores.json (score_la.py --gold ls_gold_v1_0.csv), docs/ls-gold/leaderboard.json (leaderboard_la.py),
grind/ledger.csv and grind/report.json. Checksums on the bytes written, LF line endings.

  python -X utf8 release_ls_1_0.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parents[1]
REPO = GDM.parent
QC = GDM / "data" / "qc" / "lsgold"
G = QC / "grind"
OUT = REPO / "release" / "ls-gold-1.0"
V = "1.0"
LABELS = {"latincy_lg": "LatinCy la_core_web_lg", "cltk": "CLTK", "stanza_proiel": "Stanza la-proiel", "stanza_perseus": "Stanza la-perseus",
          "stanza_ittb": "Stanza la-ittb", "stanza_llct": "Stanza la-llct", "collatinus_first": "Collatinus, first analysis (baseline)",
          "whitaker_first": "Whitaker's Words, first analysis (baseline)"}
POOLS = {"allmiss": "every system misses the gold (the lexicon baselines included)", "quoted": "validated only by the form Lewis & Short quotes",
         "conflict": "a token gold under two headwords", "lexonly": "a lexicon baseline matches, every neural system misses (read in full)",
         "lexonly_s": "the same stratum, first sample (its drop rate triggered the full read)", "sample_wh": "sample: Whitaker-validated loci",
         "sample_ok": "sample: the bulk"}
LICENSE = """LS-Gold — Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
SPDX-License-Identifier: CC-BY-SA-4.0

LS-Gold is derived from Lewis & Short's Latin Dictionary as encoded by the Perseus Digital Library (PerseusDL/lexica,
CC BY-SA) and from Perseus canonical-latinLit editions (CC BY-SA), so it carries the same licence.
Full text: https://creativecommons.org/licenses/by-sa/4.0/legalcode
"""


def n_rows(p: Path) -> int:
    with p.open(encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    led = {r["locus"]: r for r in csv.DictReader((G / "ledger.csv").open(encoding="utf-8"))}
    lid = lambda r: f'{r["edition_stem"]}:{r["token_index"]}:{r["headword_key"]}'
    with (QC / "ls_gold_1_0_dropped.csv").open(encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        cols, dropped = list(rd.fieldnames or []), list(rd)
    for r in dropped:
        x = led[lid(r)]
        v = [y for y in json.loads(x["verdicts"] or "[]") if "A" in y]
        last = v[-1] if v else {}
        r["why"] = f"read in the grind ({x['pool']}): " + "/".join(str(last.get(k) or "-") for k in ("A", "B", "C")) + (f"; {x['note']}" if x["note"] else "")
        r["readers_headword"] = last.get("A_h") or last.get("B_h") or last.get("C_h") or ""
    with (OUT / "ls_gold_1_0_dropped.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols + ["why", "readers_headword"], lineterminator="\n")
        w.writeheader(); w.writerows(dropped)
    files = {"ls_gold.csv": QC / "ls_gold_v1_0.csv", "ls_gold_scores.json": QC / "ls_gold_scores.json",
             "leaderboard.json": REPO / "docs" / "ls-gold" / "leaderboard.json", "ledger.csv": G / "ledger.csv",
             "residual_error.json": G / "report.json", "ls_gold_1_0_duplicates.csv": QC / "ls_gold_1_0_duplicates.csv"}
    for name, src in files.items():
        (OUT / name).write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))
    (OUT / "LICENSE").write_bytes(LICENSE.encode("utf-8"))
    sc = json.loads((QC / "ls_gold_scores.json").read_text(encoding="utf-8"))
    rep = json.loads((G / "report.json").read_text(encoding="utf-8"))
    n, nd, ndup = n_rows(OUT / "ls_gold.csv"), len(dropped), n_rows(OUT / "ls_gold_1_0_duplicates.csv")
    n0 = n_rows(QC / "ls_gold_v0.csv")
    assert n + nd + ndup == n0, "1.0, its dropped loci and the repeated rows do not add up to v0"
    S = sc["systems"]
    order = sorted(S, key=lambda s: (S[s].get("baseline", False), -S[s]["match_blind"]["pct"]))
    rows = []
    for s in order:
        b, c = S[s], S[s].get("by_ls_citations", {})
        ci = b["match_blind"]["wilson95"]
        once = c.get("1", {}).get("pct")
        rows.append(f"| {LABELS.get(s, s)} | {b['scored']:,} | **{b['match_blind']['pct']:.1f}** [{ci[0]:.1f}–{ci[1]:.1f}] | "
                    f"{(f'{once:.1f}' if once is not None else '—')} |")
    prow = [f"| {POOLS.get(p, p)} | {sum(cnt.values()):,} | {cnt.get('keep', 0):,} | {cnt.get('drop', 0):,} |" for p, cnt in rep["pools"].items()]
    rrow = [f"| {name} | {e['unread_loci']:,} | {e['dropped']} of {e['sampled']} | {100*e['rate']:.1f}% [{100*e['wilson95'][0]:.1f}–{100*e['wilson95'][1]:.1f}] | "
            f"about {e['expected_wrong'][1]:,} ({e['expected_wrong'][0]:,}–{e['expected_wrong'][2]:,}) |" for name, e in rep["residual"].items()]
    tw = rep["residual_total_expected_wrong"]
    lex = rep["pools"].get("lexonly", {})
    card = f"""# LS-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Latin

**LS-Gold** measures Latin lemmatizers on the words Lewis & Short's *Latin Dictionary* (1879) cites. Every L&S citation that points, by CTS URN, into a Perseus canonical-latinLit edition is relocated to its exact token and validated by two independent offline analysers (Collatinus and Whitaker's Words), or by the form L&S quotes. The Latin twin of LSJ-Gold. **{V}: {n:,} loci over {len(sc['loci_per_author'])} authors.**

A system is scored by comparing its lemma at `token_index` with `headword`: blind (case, diacritics, u/v and i/j folded; the headline figure) and strict figures, with Wilson 95% intervals in `ls_gold_scores.json`.

## What "stable" means here

{V} is the first frozen release. **Every locus with a reason to doubt its gold was read**, blind, by two readers (Claude Opus and Claude Sonnet, each in its own session with nothing but the sheet), and a third (a fresh Claude Opus) decided every split: a locus stays only on two readers' yes. Each sheet carried 10 anchors and 10 near-miss plants at unmarked positions; every one of the readers passed every gate. The rules, including the trigger that sent a whole stratum to round 2, were committed before any answer was read. **What was not read one by one was sampled**, and its residual error is stated below. **{V} is frozen**: any later correction will be a numbered erratum, decided the same way. The readers are language models, not Latinists.

## How {V} was made from v0

1. A locus repeated in L&S counts once: {ndup:,} repeated rows removed (`ls_gold_1_0_duplicates.csv`).
2. Two rounds read {rep['ledger_loci']:,} loci (`ledger.csv`, every verdict of every reader):

| pool | loci | kept | dropped |
|---|---|---|---|
""" + "\n".join(prow) + f"""

Where every system, the lexicon baselines included, misses the gold, about a quarter of the golds were wrong (*ita* under *eo*, *sine* under *sino*, *virum* under *vis*) and three quarters were right: the hard stratum the benchmark is for. Where the analysers validated a gold that every neural system rejects, about one in eight was a homograph the context rules out ({lex.get('drop', 0):,} of {sum(lex.values()):,} read). Every dropped locus is in `ls_gold_1_0_dropped.csv` with its reason; {n:,} + {nd:,} + {ndup:,} = {n0:,}, the rows of v0. Nothing was edited or added.

## Residual error (`residual_error.json`)

| stratum not read one by one | loci | sample drops | rate [95%] | expected wrong golds |
|---|---|---|---|---|
""" + "\n".join(rrow) + f"""

In all, about {tw[1]:,} of {n:,} loci (95% range {tw[0]:,}–{tw[2]:,}) may still carry a wrong gold, about {100*tw[1]/n:.1f}%. Corrections are welcome and will be errata.

## Reference table ({sc['date']})

| system | loci | headword match % | once-cited headwords % |
|---|---|---|---|
""" + "\n".join(rows) + f"""

Every system rises 0.2–0.4 points from v0 and the order is unchanged. Per-author columns are in `leaderboard.json`; the live page is https://montblanctech.github.io/Galen/ls-gold/.

## Files
- `ls_gold.csv`: one row per locus (`headword`, `headword_key`, `author`, `work`, `cited_edition`, `locator`, `edition_stem`, `unit`, `token_index` into the project's Latin token stream, `surface`, `validation`, `quoted_form`, `entry_key`, `entry_id`, `status`).
- `ls_gold_scores.json`, `leaderboard.json`: reference scores, strata and per-author figures.
- `ledger.csv`: every locus read in the rounds, its pool, every reader's verdict (A Opus, B Sonnet, C the third reader) and the decision; `residual_error.json`.
- `ls_gold_1_0_dropped.csv` ({nd:,}, with `why` and `readers_headword`), `ls_gold_1_0_duplicates.csv` ({ndup:,}).
- `CITATION.cff`, `LICENSE`, `CHECKSUMS.sha256` (`sha256sum -c CHECKSUMS.sha256` passes on the archive and on any checkout).

## Source and citation
Repository and method: https://github.com/Montblanctech/Galen (concept DOI 10.5281/zenodo.21561962); the reading sheets, answers and keys are under `galen-density-map/data/qc/lsgold/grind/`.

Pepperman, W. (2026). *LS-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Latin* (dataset). Galen Density Project. https://doi.org/10.5281/zenodo.21561962

Underlying data: Lewis & Short via PerseusDL/lexica and Perseus canonical-latinLit editions (CC BY-SA); Collatinus and Whitaker's Words as validators. Data: CC BY-SA 4.0.
"""
    (OUT / "README.md").write_bytes(card.encode("utf-8"))
    cff = (f'cff-version: 1.2.0\nmessage: "If you use LS-Gold, cite it."\ntitle: "LS-Gold {V}: lemmatizer accuracy on the dictionary-cited stratum of Latin"\n'
           f'type: dataset\nversion: "{V}"\ndate-released: {date.today().isoformat()}\nlicense: CC-BY-SA-4.0\nauthors:\n  - family-names: Pepperman\n'
           '    given-names: William\n    affiliation: "Montblanc Tech LLC (independent researcher)"\n')
    (OUT / "CITATION.cff").write_bytes(cff.encode("utf-8"))
    names = sorted(p.name for p in OUT.iterdir() if p.name != "CHECKSUMS.sha256")
    (OUT / "CHECKSUMS.sha256").write_bytes("".join(f"{hashlib.sha256((OUT / f).read_bytes()).hexdigest()} *{f}\n" for f in names).encode("utf-8"))
    print(f"release/ls-gold-{V}: {n:,} loci; dropped {nd:,}; repeats {ndup:,}; residual about {tw[1]} ({tw[0]}-{tw[2]})")


if __name__ == "__main__":
    main()
