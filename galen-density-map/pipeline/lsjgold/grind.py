"""LSJ-Gold toward a stable set: read every doubtful locus until none is left open (2026-11-11).

One ledger (data/qc/lsjgold/grind/ledger.csv) holds every locus that has a reason for doubt, every reader's verdict on
it in every round, and its status. Rounds repeat until no locus is open; then `apply` writes the stable gold.

Pools (one reason each, first that applies):
  sheet3      dropped by 0.1.2 only because its sheet failed the anchor gate twice
  split       dropped by 0.1.2 on a split or unsure vote
  conflict    a token gold under two headwords (each row is read on its own)
  allmiss     every scored system misses the gold: the strongest sign of a wrong gold
  quoted_dm   a quoted-route locus Dilemma misses, not read in 0.1.2
  sample_dm   a seeded random sample of Morpheus-route loci only Dilemma misses (estimates that stratum)
  sample_ok   a seeded random sample of the rest (estimates the stratum every system gets right)
Loci the 0.1.2 readers both rejected (no/no) stay dropped and are not re-read.

Rules (fixed before any round-1 answer is read):
  - Sheets of up to 150 open loci, plus 10 anchors (Morpheus-validated, the surface equal to LSJ's quoted form, every
    system agreeing) and 10 near-miss plants, at unmarked positions. Reader A Claude Opus, reader B Claude Sonnet,
    each with only the sheet. The instructions state LSJ's filing conventions (accent-blind headwords; -περ/-γε forms
    and adverbs under the simple word).
  - Gate per reader and sheet: 9/10 anchors yes, 8/10 plants no. A reader who fails is replaced once; if the
    replacement fails too, the sheet's loci stay open for the next round (nothing is decided by a failed sheet).
  - yes/yes: keep. no/no: drop. Anything else: a third reader (Claude Opus, fresh, its own sheet with controls) reads
    it; the locus is kept if two of the three say yes, dropped otherwise.
  - Conflict tokens: a row is kept only if it is kept by the rule above and the token's other headword is not.
  - Samples: decided like every other locus; the share of drops estimates the error rate of the stratum they come from.
  - A locus open after round 3 is dropped and listed.

  python -X utf8 grind.py queue                           build the ledger (once)
  python -X utf8 grind.py sheets --round N --key-out F    sheets for every open locus (key outside the repo)
  python -X utf8 grind.py tiebreak --round N --key-out F  third-reader sheet for the round's splits
  python -X utf8 grind.py score --round N --key F [--tiebreak-key F2]
  python -X utf8 grind.py status
  python -X utf8 grind.py apply                           write lsj_gold_grind.csv from 0.1.1's distinct loci
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsjgold"
G = QC / "grind"
LEDGER = G / "ledger.csv"
SEED, PER_SHEET, N_ANCHOR, N_PLANT, WIDTH = 20261112, 150, 10, 10, 12
N_SAMPLE_DM, N_SAMPLE_OK = 200, 100
SYSTEMS = ["odycy", "stanza_perseus", "stanza_proiel", "stoicheia", "dilemma"]
GATE = {"anchors_min_yes": 9, "plants_min_no": 8}
LCOLS = ["locus", "pool", "headword", "surface", "author", "work", "token_index", "status", "verdicts", "note"]

INSTRUCTIONS = """LSJ-GOLD READING SHEET

Each row shows a headword from the Liddell-Scott-Jones lexicon (LSJ) and a Greek token in [brackets] inside its context
(the edition's text as a token stream, punctuation removed). Decide whether the bracketed token is a form of that
headword, as LSJ files words.

Answer is_instance:
  yes     the token is a form of the headword: any inflection, dialect form, accent or breathing variant, elided or
          crasis form. Count as yes what LSJ files under the headword:
            - headwords are compared without accents or breathings: τις covers both τις and τίς, ὁ covers ὅ, etc.
            - an adverb under its adjective (σαφῶς under σαφής), a comparative or superlative under its positive,
              a participle under its verb;
            - a form with an enclitic particle under the simple word (ὅπουπερ under ὅπου, ἔγωγε under ἐγώ).
  no      the token is a different word: a compound or a simple form of it, a derivative (a noun under its verb, a
          verb under its noun), a proper name under a common noun or the reverse, or an unrelated word.
  unsure  the context does not let you decide.
If no, give the headword the token really belongs to.

Use only this sheet and your own knowledge of Greek: no lemmatizer, no dictionary file, no web search, no other file.
Answer every row. Some rows are controls placed at unmarked positions.

Write your answers as CSV with exactly these columns: row_id,is_instance,right_headword_if_no,note
"""


def lid(r: dict) -> str:
    return f'{r["author"]}.{r["work"]}:{r["token_index"]}:{r["headword_key"]}'


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(p: Path, cols: list[str], rows: list[dict]) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def distinct_0_1_1() -> list[dict]:
    seen, out = set(), []
    for r in read_csv(QC / "lsj_gold_v0_1_1.csv"):
        if lid(r) not in seen:
            seen.add(lid(r)); out.append(r)
    return out


def scored() -> dict[str, dict]:
    return {lid(r): r for r in read_csv(QC / "lsj_gold_scored.csv")}


def queue() -> None:
    if LEDGER.exists():
        raise SystemExit("ledger exists; the queue is built once")
    G.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    base = {lid(r): r for r in distinct_0_1_1()}
    sc = scored()
    dec: dict[str, dict] = {}
    for d in read_csv(QC / "recheck_0_1_2" / "decisions.csv"):
        if d["locus"] not in dec or d["decision"] == "drop":
            dec[d["locus"]] = d
    conflicts = {lid(r) for r in read_csv(QC / "lsj_gold_0_1_2_conflicts.csv")}
    kept = {lid(r) for r in read_csv(QC / "lsj_gold_v0_1_2.csv")}
    rows, pooled = [], set()

    def add(k: str, pool: str) -> None:
        if k in pooled:
            return
        r = base[k]
        pooled.add(k)
        rows.append({"locus": k, "pool": pool, "headword": r["headword"], "surface": r["surface"], "author": r["author"],
                     "work": r["work"], "token_index": r["token_index"], "status": "open", "verdicts": "", "note": ""})

    for k, d in dec.items():
        if d["decision"] != "drop":
            continue
        if d["sheet_gate"] == "fail":
            add(k, "sheet3")
        elif not (d["reader_A"] == "no" and d["reader_B"] == "no"):
            add(k, "split")
    for k in sorted(conflicts):
        add(k, "conflict")

    def miss(k: str, s: str) -> bool:
        return sc.get(k, {}).get(f"{s}_blind") == "0"

    def all_miss(k: str) -> bool:
        x = sc.get(k)
        return bool(x) and x["dilemma_blind"] == "0" and all(x[f"{s}_blind"] in ("0", "") for s in SYSTEMS)

    for k in sorted(kept):
        if all_miss(k):
            add(k, "allmiss")
    for k in sorted(kept):
        if base[k]["validation"] == "quoted" and miss(k, "dilemma") and k not in dec:
            add(k, "quoted_dm")
    dm = sorted(k for k in kept if k not in pooled and base[k]["validation"] == "morpheus" and miss(k, "dilemma"))
    for k in rng.sample(dm, min(N_SAMPLE_DM, len(dm))):
        add(k, "sample_dm")
    ok = sorted(k for k in kept if k not in pooled and not miss(k, "dilemma"))
    for k in rng.sample(ok, min(N_SAMPLE_OK, len(ok))):
        add(k, "sample_ok")
    write_csv(LEDGER, LCOLS, rows)
    strata = {"sample_dm": len(dm), "sample_ok": len(ok)}
    (G / "strata.json").write_text(json.dumps(strata, indent=1) + "\n", encoding="utf-8")
    (G / "reader_instructions.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    print("ledger:", len(rows), dict(Counter(r["pool"] for r in rows)), "| strata sampled from:", strata)


def extend2() -> None:
    """Round 2 pools, fixed after round 1 showed where the bulk's errors are (a Morpheus parse of a homograph that the
    context rules out, so the context-free Dilemma agrees with a wrong gold and the context systems do not):
      ctxmiss    every context system (odyCy, Stanza x2, Stoicheia) misses while Dilemma matches: all read
      ctx3       three of the four miss: a seeded sample of 200
      sample_ok2 the rest of the bulk (at most two context systems miss): 300 more, seeded
      sample_dm2 Morpheus-route loci only Dilemma misses: 200 more, seeded
    Same rules as round 1."""
    led = read_csv(LEDGER)
    if any(r["pool"] == "ctxmiss" for r in led):
        raise SystemExit("round-2 pools already added")
    rng = random.Random(SEED + 2)
    base = {lid(r): r for r in distinct_0_1_1()}
    sc = scored()
    kept = {lid(r) for r in read_csv(QC / "lsj_gold_v0_1_2.csv")}
    pooled = {r["locus"] for r in led}
    ctx = ["odycy", "stanza_perseus", "stanza_proiel", "stoicheia"]
    four, three, rest, dm = [], [], [], []
    for k in sorted(kept - pooled):
        x = sc.get(k)
        if not x:
            continue
        if x["dilemma_blind"] == "1":
            m = sum(x[f"{s}_blind"] == "0" for s in ctx)
            (four if m == 4 else three if m == 3 else rest).append(k)
        elif x["dilemma_blind"] == "0" and base[k]["validation"] == "morpheus":
            dm.append(k)
    pick = [(k, "ctxmiss") for k in four] + [(k, "ctx3") for k in rng.sample(three, 200)] + \
           [(k, "sample_ok2") for k in rng.sample(rest, 300)] + [(k, "sample_dm2") for k in rng.sample(dm, 200)]
    for k, pool in pick:
        r = base[k]
        led.append({"locus": k, "pool": pool, "headword": r["headword"], "surface": r["surface"], "author": r["author"],
                    "work": r["work"], "token_index": r["token_index"], "status": "open", "verdicts": "", "note": ""})
    write_csv(LEDGER, LCOLS, led)
    strata = {"ctxmiss": len(four), "ctx3": len(three), "sample_ok2": len(rest), "sample_dm2": len(dm)}
    (G / "strata_round2.json").write_text(json.dumps(strata, indent=1) + "\n", encoding="utf-8")
    print("round-2 pools added:", dict(Counter(p for _, p in pick)), "| strata:", strata)


def _streams():
    sys.path.insert(0, str(HERE))
    from relocate import held_works
    hw = held_works()
    cache: dict = {}

    def context(r: dict) -> str:
        x, j = hw[(r["author"], r["work"])]
        if j not in cache:
            cache[j] = [json.loads(l)["surface"] for l in j.open(encoding="utf-8")]
        toks, i = cache[j], int(r["token_index"])
        if toks[i] != r["surface"]:
            raise SystemExit(f"token stream mismatch at {r['author']}.{r['work']}:{i}")
        lo, hi = max(0, i - WIDTH), min(len(toks), i + WIDTH + 1)
        return " ".join(f"[{toks[k]}]" if k == i else toks[k] for k in range(lo, hi))
    return hw, context


def _controls(rng: random.Random, used: set, hw) -> tuple[list[dict], list[tuple[dict, str]]]:
    base = distinct_0_1_1()
    sc = scored()
    led = {r["locus"] for r in read_csv(LEDGER)}
    certain = [g for g in base if g["validation"] == "morpheus" and g["quoted_form"].strip() == g["surface"].strip()
               and lid(g) not in led and lid(g) not in used and (g["author"], g["work"]) in hw
               and all(sc.get(lid(g), {}).get(f"{s}_blind") == "1" for s in SYSTEMS)]
    heads = sorted({(g["headword"], g["headword_key"]) for g in base})
    strip = lambda s: "".join(c for c in __import__("unicodedata").normalize("NFD", s.lower()) if c.isalpha() and ord(c) < 0x300 or "α" <= c <= "ω")
    anchors = rng.sample(certain, N_ANCHOR)
    rest = [g for g in certain if g not in anchors]
    plants = []
    for g in rng.sample(rest, N_PLANT):
        b = strip(g["headword"])
        near = [h for h, k in heads if k != g["headword_key"] and strip(h)[:3] == b[:3] and strip(h) != b]
        far = [h for h, k in heads if k != g["headword_key"] and strip(h)[:1] == b[:1] and strip(h) != b]
        plants.append((g, rng.choice(near or far)))
    for g in anchors + [p for p, _ in plants]:
        used.add(lid(g))
    return anchors, plants


def _write_sheets(tag: str, items: list[dict], key_out: Path, seed: int) -> int:
    rng = random.Random(seed)
    hw, context = _streams()
    base = {lid(r): r for r in distinct_0_1_1()}
    items = list(items)
    rng.shuffle(items)
    n_sheets = max(1, -(-len(items) // PER_SHEET))
    keys, used = [], set()
    for s in range(n_sheets):
        part = items[s::n_sheets]
        anchors, plants = _controls(rng, used, hw)
        rows = [("open", base[x["locus"]], base[x["locus"]]["headword"]) for x in part]
        rows += [("anchor", a, a["headword"]) for a in anchors] + [("plant", p, w) for p, w in plants]
        rng.shuffle(rows)
        name = f"{tag}_sheet_{s + 1}"
        with (G / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["row_id", "headword_shown", "surface", "context", "author"])
            for n, (kind, r, shown) in enumerate(rows, 1):
                rid = f"{tag}-{s + 1}-{n:03d}"
                w.writerow([rid, shown, r["surface"], context(r), r["author"]])
                keys.append({"row_id": rid, "sheet": name, "kind": kind, "locus": lid(r), "shown": shown})
    write_csv(key_out, ["row_id", "sheet", "kind", "locus", "shown"], keys)
    print(f"{tag}: {len(items)} loci on {n_sheets} sheets")
    return n_sheets


def sheets(rnd: int, key_out: Path) -> None:
    open_ = [r for r in read_csv(LEDGER) if r["status"] == "open"]
    _write_sheets(f"r{rnd}", open_, key_out, SEED + rnd)


def _verdicts(r: dict) -> list[dict]:
    return json.loads(r["verdicts"]) if r["verdicts"] else []


def _gate(key: list[dict], sheet: str, ans: dict) -> dict:
    ks = [k for k in key if k["sheet"] == sheet]
    anc = sum(ans.get(k["row_id"], "") == "yes" for k in ks if k["kind"] == "anchor")
    pla = sum(ans.get(k["row_id"], "") == "no" for k in ks if k["kind"] == "plant")
    miss = sum(k["row_id"] not in ans for k in ks)
    return {"anchors_yes": anc, "plants_no": pla, "missing": miss,
            "pass": miss == 0 and anc >= GATE["anchors_min_yes"] and pla >= GATE["plants_min_no"]}


def _answers(p: Path) -> dict[str, dict]:
    return {r["row_id"].strip(): {"a": (r.get("is_instance") or "").strip().lower(), "h": (r.get("right_headword_if_no") or "").strip()}
            for r in read_csv(p)}


def _read_sheet_answers(key: list[dict], sheet: str, readers: list[str]) -> tuple[dict, dict, bool]:
    """For each reader: first answers file, or the replacement (_r2) if the first failed. Returns answers, gates, ok."""
    got, gates, ok = {}, {}, True
    for rd in readers:
        last = None
        for suffix in ("", "_r2"):
            p = G / f"answers_{sheet}_{rd}{suffix}.csv"
            if not p.exists():
                if suffix == "":
                    raise SystemExit(f"missing {p.name}")
                break
            a = _answers(p)
            last = f"{sheet}_{rd}{suffix}"
            gates[last] = _gate(key, sheet, {k: v["a"] for k, v in a.items()})
            got[rd] = a
            if gates[last]["pass"]:
                break
        ok &= gates[last]["pass"]
    return got, gates, ok


def score(rnd: int, key_path: Path, tb_path: Path | None) -> None:
    led = read_csv(LEDGER)
    by = {r["locus"]: r for r in led}
    key = read_csv(key_path)
    gates_all = {}
    # the round's two-reader verdicts are applied once; a later call with --tiebreak-key adds only the third reader
    done = any(x.get("round") == rnd and "A" in x for r in led for x in _verdicts(r))
    for sheet in ([] if done else sorted({k["sheet"] for k in key})):
        got, gates, ok = _read_sheet_answers(key, sheet, ["A", "B"])
        gates_all.update(gates)
        for k in key:
            if k["sheet"] != sheet or k["kind"] != "open":
                continue
            r = by[k["locus"]]
            v = _verdicts(r)
            if not ok:
                v.append({"round": rnd, "sheet": sheet, "gate": "fail"})
                r["verdicts"] = json.dumps(v, ensure_ascii=False)
                continue
            A, B = got["A"].get(k["row_id"], {}), got["B"].get(k["row_id"], {})
            v.append({"round": rnd, "sheet": sheet, "A": A.get("a"), "A_h": A.get("h"), "B": B.get("a"), "B_h": B.get("h")})
            r["verdicts"] = json.dumps(v, ensure_ascii=False)
            if A.get("a") == "yes" and B.get("a") == "yes":
                r["status"] = "keep"
            elif A.get("a") == "no" and B.get("a") == "no":
                r["status"] = "drop"
            else:
                r["status"] = "tiebreak"
    if tb_path:
        tkey = read_csv(tb_path)
        for sheet in sorted({k["sheet"] for k in tkey}):
            got, gates, ok = _read_sheet_answers(tkey, sheet, ["C"])
            gates_all.update(gates)
            for k in tkey:
                if k["sheet"] != sheet or k["kind"] != "open":
                    continue
                r = by[k["locus"]]
                v = _verdicts(r)
                if not ok:
                    r["status"] = "open"
                    v.append({"round": rnd, "sheet": sheet, "gate": "fail"})
                else:
                    C = got["C"].get(k["row_id"], {})
                    last = next(x for x in reversed(v) if "A" in x)
                    yes = [last["A"], last["B"], C.get("a")].count("yes")
                    last.update({"C": C.get("a"), "C_h": C.get("h")})
                    r["status"] = "keep" if yes >= 2 else "drop"
                r["verdicts"] = json.dumps(v, ensure_ascii=False)
    # a conflict token keeps a row only if its other headword's row is not also kept
    toks: dict = {}
    for r in led:
        if r["pool"] == "conflict":
            toks.setdefault((r["author"], r["work"], r["token_index"]), []).append(r)
    for rs in toks.values():
        if sum(x["status"] == "keep" for x in rs) > 1:
            for x in rs:
                if x["status"] == "keep":
                    x["status"] = "drop"; x["note"] = "both headwords accepted for one token"
    if rnd >= 3:
        for r in led:
            if r["status"] in ("open", "tiebreak"):
                r["status"] = "drop"; r["note"] = "still open after round 3"
    write_csv(LEDGER, LCOLS, led)
    (G / f"gates_round{rnd}.json").write_text(json.dumps(gates_all, indent=1) + "\n", encoding="utf-8")
    shutil.copy(key_path, G / f"key_round{rnd}_PUBLISHED_AFTER_SCORING.csv")
    if tb_path:
        shutil.copy(tb_path, G / f"key_round{rnd}_tiebreak_PUBLISHED_AFTER_SCORING.csv")
    print(json.dumps({"gates_failed": [k for k, g in gates_all.items() if not g["pass"]]}, ensure_ascii=False))
    status()


def tiebreak(rnd: int, key_out: Path) -> None:
    items = [r for r in read_csv(LEDGER) if r["status"] == "tiebreak"]
    if not items:
        print("no splits"); return
    _write_sheets(f"r{rnd}tb", items, key_out, SEED + 100 + rnd)


def status() -> None:
    led = read_csv(LEDGER)
    c = Counter((r["pool"], r["status"]) for r in led)
    pools = sorted({r["pool"] for r in led})
    out = {p: {s: c[(p, s)] for s in ("open", "tiebreak", "keep", "drop") if c[(p, s)]} for p in pools}
    print(json.dumps(out, ensure_ascii=False))
    print("open:", sum(r["status"] in ("open", "tiebreak") for r in led), "of", len(led))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def report() -> dict:
    """Counts by pool, and the residual error of the strata that were sampled, not read in full (grind/report.json)."""
    led = read_csv(LEDGER)
    s1 = json.loads((G / "strata.json").read_text(encoding="utf-8"))
    s2 = json.loads((G / "strata_round2.json").read_text(encoding="utf-8"))
    pools = {}
    for r in led:
        pools.setdefault(r["pool"], Counter())[r["status"]] += 1
    # sampled strata after round 2: the bulk (sample_ok + sample_ok2 drawn from it), the Dilemma-only-miss stratum
    # (sample_dm + sample_dm2), and the three-of-four-miss stratum (ctx3)
    strata = {
        "bulk (Dilemma and at least two context systems match)": (["sample_ok", "sample_ok2"], s2["sample_ok2"]),
        "Morpheus-validated, only Dilemma misses": (["sample_dm", "sample_dm2"], s2["sample_dm2"]),
        "Dilemma matches, three of four context systems miss": (["ctx3"], s2["ctx3"] - pools.get("ctx3", Counter()).total()),
    }
    est, total_lo, total_mid, total_hi = {}, 0.0, 0.0, 0.0
    for name, (ps, size) in strata.items():
        n = sum(pools.get(p, Counter()).total() for p in ps)
        k = sum(pools.get(p, Counter())["drop"] for p in ps)
        lo, hi = wilson(k, n)
        est[name] = {"sampled": n, "dropped": k, "rate": round(k / n, 4) if n else 0, "wilson95": [round(lo, 4), round(hi, 4)],
                     "unread_loci": size, "expected_wrong": [round(lo * size), round(k / n * size) if n else 0, round(hi * size)]}
        total_lo += lo * size; total_mid += (k / n * size if n else 0); total_hi += hi * size
    out = {"pools": {p: dict(c) for p, c in sorted(pools.items())}, "ledger_loci": len(led),
           "residual": est, "residual_total_expected_wrong": [round(total_lo), round(total_mid), round(total_hi)]}
    (G / "report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def apply() -> None:
    led = {r["locus"]: r for r in read_csv(LEDGER)}
    if any(r["status"] in ("open", "tiebreak") for r in led.values()):
        raise SystemExit("loci still open; run another round")
    base = distinct_0_1_1()
    kept012 = {lid(r) for r in read_csv(QC / "lsj_gold_v0_1_2.csv")}
    with (QC / "lsj_gold_v0_1_1.csv").open(encoding="utf-8") as fh:
        cols = list(csv.DictReader(fh).fieldnames or [])
    out, drop = [], []
    for r in base:
        k = lid(r)
        st = led[k]["status"] if k in led else ("keep" if k in kept012 else "drop")
        (out if st == "keep" else drop).append(r)
    write_csv(QC / "lsj_gold_grind.csv", cols, out)
    write_csv(QC / "lsj_gold_grind_dropped.csv", cols, drop)
    print(f"stable candidate: {len(out)} loci; dropped {len(drop)} of {len(base)} distinct 0.1.1 loci")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["queue", "extend2", "sheets", "tiebreak", "score", "status", "report", "apply"])
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--key-out", type=Path)
    ap.add_argument("--key", type=Path)
    ap.add_argument("--tiebreak-key", type=Path)
    a = ap.parse_args()
    {"queue": queue, "extend2": extend2, "status": status, "report": report, "apply": apply}.get(a.cmd, lambda: None)()
    if a.cmd == "sheets":
        sheets(a.round, a.key_out)
    elif a.cmd == "tiebreak":
        tiebreak(a.round, a.key_out)
    elif a.cmd == "score":
        score(a.round, a.key, a.tiebreak_key)
