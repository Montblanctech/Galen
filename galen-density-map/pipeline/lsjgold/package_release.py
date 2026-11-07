"""LSJ-Gold — package a dataset release folder for Will's Zenodo / Hugging Face upload (no network; files only).

release/lsj-gold-<version>/: lsj_gold.csv, lsj_gold_scores.json, leaderboard.json, README.md (dataset card),
SCHEMA.md, LICENSE (CC BY 4.0 text pointer), CITATION.cff, CHECKSUMS.sha256.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
ROOT = GDM.parent
QC = GDM / "data" / "qc" / "lsjgold"
VERSION = "0.1"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out = ROOT / "release" / f"lsj-gold-{VERSION}"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(QC / "lsj_gold_v0.csv", out / "lsj_gold.csv")
    shutil.copy(QC / "lsj_gold_scores.json", out / "lsj_gold_scores.json")
    lb = ROOT / "docs" / "lsj-gold" / "leaderboard.json"
    if lb.exists():
        shutil.copy(lb, out / "leaderboard.json")
    n = sum(1 for _ in csv.DictReader((QC / "lsj_gold_v0.csv").open(encoding="utf-8")))
    card = (ROOT / "drafts" / "hf_dataset_card.md").read_text(encoding="utf-8") if (ROOT / "drafts" / "hf_dataset_card.md").exists() else "# LSJ-Gold\n"
    card = card.replace("LSJ-Gold v0 + the Galen Density Project punch list (v3)", f"LSJ-Gold {VERSION} ({n} loci)")
    (out / "README.md").write_text(card, encoding="utf-8")
    (out / "SCHEMA.md").write_text(
        "# lsj_gold.csv schema\n\n| column | meaning |\n|---|---|\n"
        "| headword | LSJ headword (Unicode, from the entry key) |\n| headword_key | accent/case-blind Beta Code key used for matching |\n"
        "| author, work | TLG ids of the cited work |\n| cited_edition | the edition the LSJ URN names (Perseus) |\n| locator | CTS passage locator in the citation |\n"
        "| unit | the unit found in our First1K edition (line number or div path) |\n| token_index | 0-based index into the project's token JSONL for that edition (urn_cts_greekLit_<author>.<work>.<edition>.jsonl) |\n"
        "| surface | the token |\n| validation | morpheus (Morpheus analyses contain the headword) or quoted (equals LSJ's quoted form; used when Morpheus had no analysis) |\n"
        "| quoted_form | the form LSJ quotes near the citation, if any |\n| lsj_part, entry_key | provenance in the Perseus LSJ XML |\n| status | located |\n\n"
        "Scoring: a system matches when its lemma at token_index equals headword after accent/case normalisation (blind); strict = exact; article-neutral maps the article's forms to ὁ first.\n",
        encoding="utf-8")
    (out / "LICENSE").write_text("Data: Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/\n"
                                 "Underlying texts: First1KGreek (CC BY-SA 4.0), Perseus LSJ XML (CC BY-SA 3.0), Morpheus analyses via Perseids.\n", encoding="utf-8")
    (out / "CITATION.cff").write_text(
        "cff-version: 1.2.0\nmessage: \"If you use LSJ-Gold, cite it and the Galen Density Project preprint.\"\n"
        f"title: \"LSJ-Gold {VERSION}: lemmatizer accuracy on the dictionary-cited stratum of Ancient Greek\"\ntype: dataset\nversion: \"{VERSION}\"\n"
        "date-released: 2026-11-07\nlicense: CC-BY-4.0\nauthors:\n  - family-names: Pepperman\n    given-names: William\n    affiliation: \"Montblanc Tech LLC (independent researcher)\"\n"
        "references:\n  - type: article\n    title: \"A density map of under-described vocabulary in the Galenic corpus\"\n    authors:\n      - family-names: Pepperman\n        given-names: William\n    year: 2026\n    doi: 10.5281/zenodo.22162810\n", encoding="utf-8")
    sums = []
    for p in sorted(out.iterdir()):
        if p.name != "CHECKSUMS.sha256":
            sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (out / "CHECKSUMS.sha256").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"release_dir": str(out), "files": [p.name for p in sorted(out.iterdir())], "loci": n}, indent=2))


if __name__ == "__main__":
    main()
