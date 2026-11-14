"""T2b spelling rules, measured on papyri they were not learned from (the test documents of t2b_spelling_data).

1. Words. Every (written, regularized) pair of the test documents whose regularized form is in our counts and
   whose written form is not (so the spelling layer is asked; an attested written form is read as written):
   is the regularized form the channel's best reading of the written word on its own (unigram + channel), and
   is it accepted as a spelling (t2b_flag's rule: rate >= 1e-3)? Baseline: the HTR channel alone (letter
   classes, one lost letter).
2. Slips. The scribal slips the editors corrected (<sic>/<corr>): how many the spelling layer would excuse
   (accepted as a spelling), which it should not.
3. Lines. Windows of five words of a test document as the scribe wrote them, run together as scriptio continua
   and segmented with and without the spelling layer: word division (boundary F1) and how many of the
   misspelled words come out as the editor's regularized form.

  python -I -X utf8 pipeline/t2b_spelling_eval.py [--windows 600]
writes outputs/t2b/spelling_eval.json and .md
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t2b_scorer as T  # noqa: E402
import t2b_spelling as S  # noqa: E402
import t2b_spelling_data as D  # noqa: E402

OUT = T.PROJECT / "outputs" / "t2b"
MIN_COST = math.log(1e-3)


def word_eval(lex_sp: T.Lexicon, lex_base: T.Lexicon, pairs: list[dict]) -> dict:
    n = top_sp = acc_sp = top_base = reachable = 0
    n_all = attested_written = reg_missing = 0
    by_kind: Counter = Counter()
    by_kind_ok: Counter = Counter()
    misses = []
    for x in pairs:
        n_all += 1
        o, r = x["orig"], x["reg"]
        if o in lex_sp.exact:
            attested_written += 1
            continue
        if r not in lex_sp.exact:
            reg_missing += 1
            continue
        n += 1
        rid = lex_sp.exact[r]
        cs = lex_sp.candidates(o, top=12)
        best = cs[0] if cs else None
        ok = best is not None and best[0] == rid
        top_sp += ok
        var = [c for c in cs if c[2].startswith("var:")]
        if any(c[0] == rid for c in var):
            reachable += 1
        acc = ok and best[2].startswith("var:") and best[1] >= MIN_COST
        acc_sp += acc
        cb = lex_base.candidates(o, top=12)
        top_base += bool(cb) and cb[0][0] == rid
        rs = S.rules_of_pair(o, r)
        kind = "two or more changes" if rs and len(rs) > 1 else (
            (S.kind_of(rs[0][0], rs[0][1], rs[0][2]) or "not a spelling rule") if rs else "not alignable")
        by_kind[kind] += 1
        by_kind_ok[kind] += ok
        if not ok and len(misses) < 25:
            misses.append({"written": o, "regularized": r, "best": lex_sp.c.forms[best[0]] if best else None,
                           "best_edit": best[2] if best else None})
    return {"pairs": n_all, "written_attested_skipped": attested_written, "regularized_not_in_counts": reg_missing,
            "asked": n, "best_is_regularized_spelling": round(top_sp / n, 4) if n else None,
            "best_is_regularized_htr_only": round(top_base / n, 4) if n else None,
            "accepted_as_spelling": round(acc_sp / n, 4) if n else None,
            "regularized_reachable_by_one_rule": round(reachable / n, 4) if n else None,
            "by_kind": {k: {"pairs": v, "best_is_regularized": round(by_kind_ok[k] / v, 4)} for k, v in by_kind.most_common()},
            "misses_sample": misses}


def slip_eval(lex_sp: T.Lexicon, slips: list[dict]) -> dict:
    n = excused = unattested = 0
    ex = []
    for x in slips:
        a, b = x["sic"], x["corr"]
        n += 1
        if a in lex_sp.exact:
            continue
        unattested += 1
        cs = lex_sp.candidates(a, top=12)
        if cs and cs[0][2].startswith("var:") and cs[0][1] >= MIN_COST:
            excused += 1
            if len(ex) < 15:
                ex.append({"written": a, "editor": b, "read_as": lex_sp.c.forms[cs[0][0]],
                           "rule": lex_sp.spelling.label(int(cs[0][2][4:]))})
    return {"slips": n, "unattested_as_written": unattested, "excused_as_spelling": excused,
            "excused_share_of_unattested": round(excused / unattested, 4) if unattested else None,
            "excused_sample": ex}


def windows(files: list[Path], k: int, rng: random.Random, size: int = 5) -> list[dict]:
    """Windows of `size` words without gaps, from aligned test documents, with at least one misspelled word."""
    out = []
    rng.shuffle(files)
    for p in files:
        o = D.edition_words(p, "orig")
        r = D.edition_words(p, "reg")
        if not o or len(o) != len(r):
            continue
        ko = [D._key(w) if D.GAP not in w else "" for w in o]
        kr = [D._key(w) if D.GAP not in w else "" for w in r]
        cands = [i for i in range(len(ko) - size + 1)
                 if all(ko[j] and kr[j] for j in range(i, i + size)) and any(ko[j] != kr[j] for j in range(i, i + size))]
        if not cands:
            continue
        i = rng.choice(cands)
        out.append({"doc": p.stem, "orig": ko[i:i + size], "reg": kr[i:i + size]})
        if len(out) >= k:
            break
    return out


def line_eval(segs: dict, wins: list[dict]) -> dict:
    res = {}
    for name, seg in segs.items():
        tp = fp = fn = 0
        fixed = mis = 0
        t0 = time.time()
        for w in wins:
            s = "".join(w["orig"])
            gold, pos = set(), 0
            spans = []
            for x in w["orig"]:
                spans.append((pos, pos + len(x)))
                pos += len(x)
            gold = {e for _, e in spans[:-1]}
            rd = seg.segment(s, k=1)[0]
            pred = rd.boundaries
            tp += len(pred & gold)
            fp += len(pred - gold)
            fn += len(gold - pred)
            got = {(g.start, g.end): g.form for g in rd.segments}
            for (a, b), o, r in zip(spans, w["orig"], w["reg"]):
                if o != r:
                    mis += 1
                    fixed += got.get((a, b)) == r
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / (tp + fn) if tp + fn else 0.0
        res[name] = {"windows": len(wins), "boundary_P": round(P, 4), "boundary_R": round(R, 4),
                     "boundary_F1": round(2 * P * R / (P + R), 4) if P + R else 0.0,
                     "misspelled_words": mis, "read_as_regularized": round(fixed / mis, 4) if mis else None,
                     "seconds": round(time.time() - t0, 1)}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, default=600)
    ap.add_argument("--idp", default=str(T.PROJECT / "data" / "external" / "idp.data"))
    a = ap.parse_args(argv)
    counts = T.load_counts(T.cache_path())
    lex_sp = T.Lexicon(counts, spelling=S.SpellingRules.load())
    lex_base = T.Lexicon(counts)
    pairs, slips = [], []
    for line in open(T.PROJECT / "data" / T.CACHE_DIR_NAME / "spelling_pairs.jsonl", encoding="utf-8"):
        x = json.loads(line)
        if x["split"] != "test":
            continue
        if x.get("type") == "sic":
            slips.append(x)
        elif not x.get("near_gap"):
            pairs.append(x)
    words = word_eval(lex_sp, lex_base, pairs)
    sl = slip_eval(lex_sp, slips)
    idp = Path(a.idp)
    files = [p for p in sorted(list((idp / "DDbDP").rglob("*.xml")) + list((idp / "DCLP").rglob("*.xml")))
             if D.split_of(p.name) == "test"]
    wins = windows(files, a.windows, random.Random(2026))
    lines = line_eval({"without spelling rules": T.Segmenter(lex_base), "with spelling rules": T.Segmenter(lex_sp)}, wins)
    rep = {"source": "papyri.info DDbDP + DCLP test documents (1 in 10 by a seeded hash), not used to learn the rules",
           "n_rules": len(lex_sp.spelling.rules), "words": words, "slips": sl, "lines": lines}
    (OUT / "spelling_eval.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Spelling rules on held-out papyri", "",
          f"Rules: {rep['n_rules']}, learned on the train documents. Test: {rep['source']}.", "",
          "## Words (written form unattested, regularized form attested)", "",
          "| pairs asked | best reading = editor's form, spelling rules | same, HTR channel only | accepted as a spelling |",
          "|---|---|---|---|",
          f"| {words['asked']:,} | {words['best_is_regularized_spelling']:.3f} | {words['best_is_regularized_htr_only']:.3f} | {words['accepted_as_spelling']:.3f} |",
          "", f"Of {words['pairs']:,} test pairs, {words['written_attested_skipped']:,} have a written form that is itself attested "
          f"(read as written) and {words['regularized_not_in_counts']:,} a regularized form not in the counts (names, documentary words).",
          "", "## Scribal slips (sic / corr)", "",
          f"{sl['slips']:,} slips; {sl['unattested_as_written']:,} unattested as written; "
          f"{sl['excused_as_spelling']:,} would be excused as a spelling ({(sl['excused_share_of_unattested'] or 0):.1%}).",
          "", "## Lines (five words as written, run together)", "",
          "| system | windows | boundary F1 | misspelled words | read as the editor's form |", "|---|---|---|---|---|"]
    for k, v in lines.items():
        md.append(f"| {k} | {v['windows']} | {v['boundary_F1']:.3f} | {v['misspelled_words']} | {v['read_as_regularized']:.3f} |")
    (OUT / "spelling_eval.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
