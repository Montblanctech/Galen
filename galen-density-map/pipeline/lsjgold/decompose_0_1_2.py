"""How much of each system's change from LSJ-Gold 0.1.1 to 0.1.2 comes from each step. Reads the 0.1.1 scored CSV.

  python -X utf8 decompose_0_1_2.py <folder holding lsj_gold_scored_0_1_1.csv>
"""
import csv, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
QC = Path(__file__).resolve().parents[2] / "data" / "qc" / "lsjgold"
S = Path(sys.argv[1])
rows = list(csv.DictReader((S / "lsj_gold_scored_0_1_1.csv").open(encoding="utf-8")))
lid = lambda r: f'{r["author"]}.{r["work"]}:{r["token_index"]}:{r["headword_key"]}'
dec = {}
for d in csv.DictReader((QC / "recheck_0_1_2" / "decisions.csv").open(encoding="utf-8")):
    if d["locus"] not in dec or d["decision"] == "drop":
        dec[d["locus"]] = d
sheet3_yy = {d["locus"] for d in dec.values() if d["row_id"].startswith("S3-") and d["reader_A"] == "yes" and d["reader_B"] == "yes"}
conf = {(r["author"], r["work"], r["token_index"]) for r in csv.DictReader((QC / "lsj_gold_0_1_2_conflicts.csv").open(encoding="utf-8"))}
SYS = ["stoicheia", "dilemma", "stanza_perseus", "odycy", "stanza_proiel"]
NEURAL = [s for s in SYS if s != "dilemma"]


def pct(rs, s):
    # neural systems are reported on the loci every neural system scored; Dilemma on its own scored loci
    if s in NEURAL:
        rs = [r for r in rs if all(r[f"{x}_blind"] != "" for x in NEURAL)]
    else:
        rs = [r for r in rs if r[f"{s}_blind"] != ""]
    return round(100 * sum(r[f"{s}_blind"] == "1" for r in rs) / len(rs), 2), len(rs)


seen, dedup = set(), []
for r in rows:
    if lid(r) not in seen:
        dedup.append(r); seen.add(lid(r))
steps = {"0.1.1": rows, "+ one row per locus": dedup}
recheck = [r for r in dedup if dec.get(lid(r), {}).get("decision") != "drop"]
steps["+ re-check drops (0.1.2 minus conflicts)"] = recheck
final = [r for r in recheck if (r["author"], r["work"], r["token_index"]) not in conf]
steps["+ conflicting tokens out = 0.1.2"] = final
sens = final + [r for r in dedup if lid(r) in sheet3_yy and (r["author"], r["work"], r["token_index"]) not in conf]
steps["sensitivity: 0.1.2 + sheet 3's yes/yes loci"] = sens
for name, rs in steps.items():
    print(f"{name:45s} loci {len(rs):6d}  " + "  ".join(f"{s} {pct(rs, s)[0]}" for s in SYS))
# among dropped loci (passing sheets), who missed them
dl = [r for r in dedup if dec.get(lid(r), {}).get("decision") == "drop"]
print("dropped loci:", len(dl), "missed by:", {s: sum(r[f"{s}_blind"] == "0" for r in dl) for s in SYS})
