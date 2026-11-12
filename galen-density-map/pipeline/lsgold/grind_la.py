"""LS-Gold toward a stable 1.0: read every doubtful Latin locus until none is left open (2026-11-11). The Latin twin of
pipeline/lsjgold/grind.py, with the same ledger, rules and commands.

Starting point: LS-Gold v0 (data/qc/lsgold/ls_gold_v0.csv), one row per locus (a locus repeated in Lewis & Short counts
once; the repeats are listed, not read). Pools (one reason each, first that applies):
  conflict    a token gold under two headwords (each row read on its own)
  quoted      validated only by the form Lewis & Short quotes (no analyser accepted it)
  allmiss     every system misses the gold, the lexicon baselines (Collatinus-first, Whitaker-first) included
  lexonly_s   a seeded sample of 300 loci where a lexicon baseline matches and every neural system misses (the analysers
              validated the gold, so this is where a homograph the context rules out would hide). If its drop rate is
              above 1%, every locus of that stratum is read in round 2 (pool lexonly).
  sample_wh   a seeded sample of 100 Whitaker-validated loci not pooled above
  sample_ok   a seeded sample of 400 of the rest (the bulk)

Rules (fixed before any answer is read), as in the Greek grind:
  - Sheets of up to 150 open loci, plus 10 anchors (analyser-validated loci every system matches; Lewis & Short quotes phrases,
    so the Greek anchor rule cannot apply) and 10 near-miss plants, at unmarked positions. Reader A Claude Opus, reader B Claude Sonnet, each with only
    the sheet, in a reading folder that holds nothing else.
  - Gate per reader and sheet: 9/10 anchors yes, 8/10 plants no. A failing reader is replaced once; if the replacement
    fails too, the sheet's loci stay open for the next round.
  - yes/yes keep, no/no drop, anything else to a third reader (a fresh Claude Opus): kept on two yes of three.
  - A conflict token keeps a row only if its other headword's row is not also kept.
  - A locus open after round 3 is dropped and listed.

  python -X utf8 grind_la.py queue | extend2 | sheets --round N --key-out F | tiebreak --round N --key-out F
  python -X utf8 grind_la.py score --round N --key F [--tiebreak-key F2] | status | report | apply
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
import unicodedata as ud
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
QC = GDM / "data" / "qc" / "lsgold"
G = QC / "grind"
LEDGER = G / "ledger.csv"
TOKENS = GDM / "data" / "latin_corpus" / "tokens"
SEED, PER_SHEET, N_ANCHOR, N_PLANT, WIDTH = 20261114, 150, 10, 10, 12
NEURAL = ["cltk", "latincy_lg", "stanza_ittb", "stanza_llct", "stanza_perseus", "stanza_proiel"]
LEX = ["collatinus_first", "whitaker_first"]
SYSTEMS = NEURAL + LEX
GATE = {"anchors_min_yes": 9, "plants_min_no": 8}
LCOLS = ["locus", "pool", "headword", "surface", "author", "work", "edition_stem", "token_index", "status", "verdicts", "note"]

INSTRUCTIONS = """LS-GOLD READING SHEET (Latin)

Each row shows a headword from Lewis & Short's Latin Dictionary and a Latin token in [brackets] inside its context (the
edition's text as a token stream, punctuation removed). Decide whether the bracketed token is a form of that headword, as
Lewis & Short files words.

Answer is_instance:
  yes     the token is a form of the headword: any inflection; spelling variants (u/v, i/j, assimilated prefixes such as
          adf-/aff-, inl-/ill-, archaic spellings); an enclitic -que, -ne, -ve, -ce on the token does not matter. Count as
          yes what Lewis & Short files under the headword:
            - a headword stands for every word spelled the same: cum covers the preposition and the conjunction, est
              under sum or edo is judged by the spelling shown, not by the homograph;
            - a participle under its verb, a comparative or superlative under its positive;
            - an adverb under its adjective when it is formed from it (-e, -iter, -ter).
  no      the token is a different word: a compound or simple form of it, a derivative (a noun under its verb, a verb
          under its noun), a proper name under a common noun or the reverse, or an unrelated word.
  unsure  the context does not let you decide.
If no, give the headword the token really belongs to.

Use only this sheet and your own knowledge of Latin: no lemmatizer, no dictionary file, no web search, no other file.
Answer every row. Some rows are controls placed at unmarked positions.

Write your answers as CSV with exactly these columns: row_id,is_instance,right_headword_if_no,note
"""


def lid(r: dict) -> str:
    return f'{r["edition_stem"]}:{r["token_index"]}:{r["headword_key"]}'


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(p: Path, cols: list[str], rows: list[dict]) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def distinct() -> tuple[list[dict], list[dict]]:
    seen, out, dup = set(), [], []
    for r in read_csv(QC / "ls_gold_v0.csv"):
        (dup if lid(r) in seen else out).append(r)
        seen.add(lid(r))
    return out, dup


def scored() -> dict[str, dict]:
    return {lid(r): r for r in read_csv(QC / "ls_gold_scored.csv")}


def miss(x: dict, s: str) -> bool:
    return x.get(f"{s}_blind") == "0"


def hit(x: dict, s: str) -> bool:
    return x.get(f"{s}_blind") == "1"


def _add(rows: list, pooled: set, r: dict, pool: str) -> None:
    k = lid(r)
    if k in pooled:
        return
    pooled.add(k)
    rows.append({"locus": k, "pool": pool, "headword": r["headword"], "surface": r["surface"], "author": r["author"],
                 "work": r["work"], "edition_stem": r["edition_stem"], "token_index": r["token_index"], "status": "open",
                 "verdicts": "", "note": ""})


def queue() -> None:
    if LEDGER.exists():
        raise SystemExit("ledger exists; the queue is built once")
    G.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    base, dup = distinct()
    write_csv(QC / "ls_gold_1_0_duplicates.csv", list(base[0].keys()), dup)
    sc = scored()
    rows, pooled = [], set()
    heads: dict = {}
    for r in base:
        heads.setdefault((r["edition_stem"], r["token_index"]), set()).add(r["headword_key"])
    clash = {k for k, v in heads.items() if len(v) > 1}
    for r in base:
        if (r["edition_stem"], r["token_index"]) in clash:
            _add(rows, pooled, r, "conflict")
    for r in base:
        if r["validation"] == "quoted":
            _add(rows, pooled, r, "quoted")
    for r in base:
        x = sc.get(lid(r), {})
        if x and all(x.get(f"{s}_blind") in ("0", "") for s in SYSTEMS) and any(miss(x, s) for s in SYSTEMS):
            _add(rows, pooled, r, "allmiss")
    lexonly = [r for r in base if lid(r) not in pooled and (lambda x: x and all(miss(x, s) for s in NEURAL)
               and any(hit(x, s) for s in LEX))(sc.get(lid(r), {}))]
    for r in rng.sample(lexonly, min(300, len(lexonly))):
        _add(rows, pooled, r, "lexonly_s")
    wh = [r for r in base if lid(r) not in pooled and r["validation"] == "whitaker"]
    for r in rng.sample(wh, min(100, len(wh))):
        _add(rows, pooled, r, "sample_wh")
    lexset = {lid(r) for r in lexonly}
    rest = [r for r in base if lid(r) not in pooled and r["validation"] != "whitaker" and lid(r) not in lexset]
    for r in rng.sample(rest, 400):
        _add(rows, pooled, r, "sample_ok")
    write_csv(LEDGER, LCOLS, rows)
    strata = {"distinct_loci": len(base), "repeats": len(dup), "lexonly": len(lexonly), "whitaker": len(wh), "bulk": len(rest)}
    (G / "strata.json").write_text(json.dumps(strata, indent=1) + "\n", encoding="utf-8")
    (G / "reader_instructions.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    print("ledger:", len(rows), dict(Counter(r["pool"] for r in rows)), "| strata:", strata)


def extend2() -> None:
    """Round 2 (fixed before round 1 was read): if the lexonly sample drops more than 1%, read every lexonly locus."""
    led = read_csv(LEDGER)
    if any(r["pool"] == "lexonly" for r in led):
        raise SystemExit("round-2 pool already added")
    s = [r for r in led if r["pool"] == "lexonly_s"]
    if any(r["status"] in ("open", "tiebreak") for r in s):
        raise SystemExit("the lexonly sample is not decided yet")
    rate = sum(r["status"] == "drop" for r in s) / len(s)
    if rate <= 0.01:
        print(f"lexonly sample drop rate {rate:.3f} <= 1%: no round-2 pool"); return
    base, _ = distinct()
    sc = scored()
    pooled = {r["locus"] for r in led}
    n = 0
    for r in base:
        x = sc.get(lid(r), {})
        if lid(r) not in pooled and x and all(miss(x, s_) for s_ in NEURAL) and any(hit(x, s_) for s_ in LEX):
            _add(led, pooled, r, "lexonly"); n += 1
    write_csv(LEDGER, LCOLS, led)
    print(f"lexonly sample drop rate {rate:.3f} > 1%: {n} lexonly loci added for round 2")


def _context_fn():
    cache: dict = {}

    def context(r: dict) -> str:
        stem, i = r["edition_stem"], int(r["token_index"])
        if stem not in cache:
            cache[stem] = [json.loads(l)["surface"] for l in (TOKENS / f"{stem}.jsonl").open(encoding="utf-8")]
        toks = cache[stem]
        if toks[i] != r["surface"]:
            raise SystemExit(f"token stream mismatch at {stem}:{i}")
        lo, hi = max(0, i - WIDTH), min(len(toks), i + WIDTH + 1)
        return " ".join(f"[{toks[k]}]" if k == i else toks[k] for k in range(lo, hi))
    return context


def _key(s: str) -> str:
    s = ud.normalize("NFD", s.lower()).replace("j", "i").replace("v", "u")
    return "".join(c for c in s if c.isalpha() and not ud.combining(c))


def _controls(rng: random.Random, used: set, base: list[dict], sc: dict, led: set):
    # Lewis & Short quotes phrases, not single forms, so an anchor is an analyser-validated locus every system matches
    certain = [g for g in base if g["validation"] in ("collatinus", "whitaker") and lid(g) not in led and lid(g) not in used
               and all(hit(sc.get(lid(g), {}), s) for s in SYSTEMS)]
    heads = sorted({(g["headword"], g["headword_key"]) for g in base})
    anchors = rng.sample(certain, N_ANCHOR)
    rest = [g for g in certain if g not in anchors]
    plants = []
    for g in rng.sample(rest, N_PLANT):
        b = _key(g["headword"])
        near = [h for h, k in heads if k != g["headword_key"] and _key(h)[:3] == b[:3] and _key(h) != b]
        far = [h for h, k in heads if k != g["headword_key"] and _key(h)[:1] == b[:1] and _key(h) != b]
        plants.append((g, rng.choice(near or far)))
    for g in anchors + [p for p, _ in plants]:
        used.add(lid(g))
    return anchors, plants


def _write_sheets(tag: str, items: list[dict], key_out: Path, seed: int) -> None:
    rng = random.Random(seed)
    context = _context_fn()
    base, _ = distinct()
    by = {lid(r): r for r in base}
    sc = scored()
    led = {r["locus"] for r in read_csv(LEDGER)}
    items = list(items)
    rng.shuffle(items)
    n_sheets = max(1, -(-len(items) // PER_SHEET))
    keys, used = [], set()
    for s in range(n_sheets):
        part = items[s::n_sheets]
        anchors, plants = _controls(rng, used, base, sc, led)
        rows = [("open", by[x["locus"]], by[x["locus"]]["headword"]) for x in part]
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


def sheets(rnd: int, key_out: Path) -> None:
    _write_sheets(f"r{rnd}", [r for r in read_csv(LEDGER) if r["status"] == "open"], key_out, SEED + rnd)


def tiebreak(rnd: int, key_out: Path) -> None:
    items = [r for r in read_csv(LEDGER) if r["status"] == "tiebreak"]
    if not items:
        print("no splits"); return
    _write_sheets(f"r{rnd}tb", items, key_out, SEED + 100 + rnd)


def _verdicts(r: dict) -> list[dict]:
    return json.loads(r["verdicts"]) if r["verdicts"] else []


def _answers(p: Path) -> dict[str, dict]:
    return {r["row_id"].strip(): {"a": (r.get("is_instance") or "").strip().lower(), "h": (r.get("right_headword_if_no") or "").strip()}
            for r in read_csv(p)}


def _gate(key: list[dict], sheet: str, ans: dict) -> dict:
    ks = [k for k in key if k["sheet"] == sheet]
    anc = sum(ans.get(k["row_id"], "") == "yes" for k in ks if k["kind"] == "anchor")
    pla = sum(ans.get(k["row_id"], "") == "no" for k in ks if k["kind"] == "plant")
    miss_ = sum(k["row_id"] not in ans for k in ks)
    return {"anchors_yes": anc, "plants_no": pla, "missing": miss_,
            "pass": miss_ == 0 and anc >= GATE["anchors_min_yes"] and pla >= GATE["plants_min_no"]}


def _read_sheet(key: list[dict], sheet: str, readers: list[str]):
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
    gates_all = {}
    # a sheet's two-reader verdicts are applied once (a sheet read later is applied on its own)
    applied = {x.get("sheet") for r in led for x in _verdicts(r) if x.get("round") == rnd and ("A" in x or x.get("gate") == "fail")}
    done = bool(tb_path) and bool(applied)
    key = read_csv(key_path)
    for sheet in ([] if done else sorted({k["sheet"] for k in key} - applied)):
        if not (G / f"answers_{sheet}_A.csv").exists() or not (G / f"answers_{sheet}_B.csv").exists():
            print(f"{sheet}: not read yet; its loci stay open")   # e.g. a reading stopped part-way
            continue
        got, gates, ok = _read_sheet(key, sheet, ["A", "B"])
        gates_all.update(gates)
        for k in key:
            if k["sheet"] != sheet or k["kind"] != "open":
                continue
            r = by[k["locus"]]
            v = _verdicts(r)
            if not ok:
                v.append({"round": rnd, "sheet": sheet, "gate": "fail"})
            else:
                A, B = got["A"].get(k["row_id"], {}), got["B"].get(k["row_id"], {})
                v.append({"round": rnd, "sheet": sheet, "A": A.get("a"), "A_h": A.get("h"), "B": B.get("a"), "B_h": B.get("h")})
                r["status"] = "keep" if A.get("a") == B.get("a") == "yes" else ("drop" if A.get("a") == B.get("a") == "no" else "tiebreak")
            r["verdicts"] = json.dumps(v, ensure_ascii=False)
    if tb_path:
        tkey = read_csv(tb_path)
        for sheet in sorted({k["sheet"] for k in tkey}):
            got, gates, ok = _read_sheet(tkey, sheet, ["C"])
            gates_all.update(gates)
            for k in tkey:
                if k["sheet"] != sheet or k["kind"] != "open":
                    continue
                r = by[k["locus"]]
                v = _verdicts(r)
                if not ok:
                    r["status"] = "open"; v.append({"round": rnd, "sheet": sheet, "gate": "fail"})
                else:
                    C = got["C"].get(k["row_id"], {})
                    last = next(x for x in reversed(v) if "A" in x)
                    last.update({"C": C.get("a"), "C_h": C.get("h")})
                    r["status"] = "keep" if [last["A"], last["B"], C.get("a")].count("yes") >= 2 else "drop"
                r["verdicts"] = json.dumps(v, ensure_ascii=False)
    toks: dict = {}
    for r in led:
        if r["pool"] == "conflict":
            toks.setdefault((r["edition_stem"], r["token_index"]), []).append(r)
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
    suffix = "_tiebreak" if done else ""
    (G / f"gates_round{rnd}{suffix}.json").write_text(json.dumps(gates_all, indent=1) + "\n", encoding="utf-8")
    shutil.copy(key_path, G / f"key_round{rnd}_PUBLISHED_AFTER_SCORING.csv")
    if tb_path:
        shutil.copy(tb_path, G / f"key_round{rnd}_tiebreak_PUBLISHED_AFTER_SCORING.csv")
    print(json.dumps({"gates_failed": [k for k, g in gates_all.items() if not g["pass"]]}))
    status()


def status() -> None:
    led = read_csv(LEDGER)
    c = Counter((r["pool"], r["status"]) for r in led)
    print(json.dumps({p: {s: c[(p, s)] for s in ("open", "tiebreak", "keep", "drop") if c[(p, s)]} for p in sorted({r["pool"] for r in led})}))
    print("open:", sum(r["status"] in ("open", "tiebreak") for r in led), "of", len(led))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def report() -> dict:
    led = read_csv(LEDGER)
    st = json.loads((G / "strata.json").read_text(encoding="utf-8"))
    pools: dict = {}
    for r in led:
        pools.setdefault(r["pool"], Counter())[r["status"]] += 1
    full_lex = "lexonly" in pools
    strata = {"bulk (analyser-validated, some system matches)": (["sample_ok"], st["bulk"] - 400),
              "validated by Whitaker's Words only": (["sample_wh"], st["whitaker"] - 100)}
    if not full_lex:
        strata["lexicon baseline matches, every neural system misses"] = (["lexonly_s"], st["lexonly"] - 300)
    est, tl, tm, th = {}, 0.0, 0.0, 0.0
    for name, (ps, size) in strata.items():
        n = sum(pools.get(p, Counter()).total() for p in ps); k = sum(pools.get(p, Counter())["drop"] for p in ps)
        lo, hi = wilson(k, n)
        est[name] = {"sampled": n, "dropped": k, "rate": round(k / n, 4) if n else 0, "wilson95": [round(lo, 4), round(hi, 4)],
                     "unread_loci": size, "expected_wrong": [round(lo * size), round(k / n * size) if n else 0, round(hi * size)]}
        tl += lo * size; tm += (k / n * size if n else 0); th += hi * size
    out = {"pools": {p: dict(c) for p, c in sorted(pools.items())}, "ledger_loci": len(led), "residual": est,
           "residual_total_expected_wrong": [round(tl), round(tm), round(th)]}
    (G / "report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def apply() -> None:
    led = {r["locus"]: r for r in read_csv(LEDGER)}
    if any(r["status"] in ("open", "tiebreak") for r in led.values()):
        raise SystemExit("loci still open; run another round")
    base, _ = distinct()
    cols = list(base[0].keys())
    keep = [r for r in base if led.get(lid(r), {}).get("status", "keep") == "keep"]
    drop = [r for r in base if led.get(lid(r), {}).get("status", "keep") == "drop"]
    write_csv(QC / "ls_gold_v1_0.csv", cols, keep)
    write_csv(QC / "ls_gold_1_0_dropped.csv", cols, drop)
    print(f"LS-Gold 1.0 candidate: {len(keep)} loci; dropped {len(drop)} of {len(base)} distinct v0 loci")


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
