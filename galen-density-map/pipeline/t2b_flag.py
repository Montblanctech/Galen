"""T2b v1 real case: flag low-plausibility readings in an edited papyrus text (Philodemus, First1K tlg1595).

The edited text keeps the Leiden marks. For every word we record which of its letters the editor read and
which were restored ([...]), reduce it to the scriptio-continua key (papyri.normalize_token first, then
t2b_scorer.to_continua), and score it in context with the same counts and channel as the segmenter. Philodemus
is held out of the counts (outputs/t2b/holdout_works.json, "real"), so his own words do not attest themselves.

Flags (one row per flagged word; nothing is corrected):
  unattested     the key occurs < 2 times in the 21.6M counted tokens (no in-channel alternative is)
  alternative    a form reachable through the HTR channel (Α/Λ/Δ, Ε/Θ/Ο/Σ, Η/Ν, Ι/Τ, one lost letter) scores
                 better in context than the edited reading by more than --margin nats, counting
                 P(word | previous) + P(next | word) + channel cost
  unattested+alt both
Words touching an unread gap (dots), and letter strings the editor left unarticulated (no accent, no
breathing, not an enclitic: τελον, αεως), are fragments and never flagged; elided words (οὔτ᾿) are
not flagged either (the elided key is short and the channel always "restores" the vowel).

  python -I -X utf8 pipeline/t2b_flag.py [--works tlg1595.tlg221,tlg1595.tlg370] [--margin 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "audit-kit"))
import t2b_scorer as T  # noqa: E402
from greek_lemma_audit.papyri import normalize_token  # noqa: E402

OUT = T.PROJECT / "outputs" / "t2b"


# words that are normally written without accent or breathing (enclitics); anything else that has neither
# is a string of letters the editor read but did not articulate into words (τελον, αεως)
UNMARKED_OK = set("ΤΕ ΓΕ ΤΙ ΤΙΣ ΤΙΝΟΣ ΤΙΝΙ ΤΙΝΑ ΤΙΝΕΣ ΤΙΝΩΝ ΤΙΣΙ ΤΙΣΙΝ ΤΙΝΑΣ ΠΟΥ ΠΗ ΠΟΙ ΠΩΣ ΠΟΤΕ ΠΟΤ ΠΩ ΠΕΡ ΤΟΙ "
                  "ΝΥΝ ΜΟΙ ΜΟΥ ΜΕ ΣΟΙ ΣΟΥ ΣΕ ΦΗΣΙ ΦΗΣΙΝ ΦΑΣΙ ΦΑΣΙΝ".split())
_MARKS_ACC = {"̀", "́", "͂", "̓", "̔", "̈"}


def unarticulated(form: str, key: str) -> bool:
    d = T.unicodedata.normalize("NFD", form)
    return (len(key) >= 2 and key not in UNMARKED_OK and not any(c in _MARKS_ACC for c in d)
            and form[:1].islower())


def adscript_left(form: str) -> bool:
    """True if the word still ends in ω/η + plain ι (no diaeresis) after papyri.normalize_token."""
    d = T.unicodedata.normalize("NFD", form.rstrip("’'ʼ"))
    if not d or d[-1] not in "ιΙ":
        return False
    base = [c for c in d[:-1] if not T.unicodedata.combining(c)]
    return bool(base) and base[-1] in "ωηΩΗ"


def leiden_words(text: str) -> list[dict]:
    """Edited text -> words with per-letter restored flags. Hyphenated line ends are joined; supplement
    brackets may span words and lines."""
    text = re.sub(r"-\s*\n\s*", "", text)
    inside = False
    words = []
    for raw in text.split():
        letters, restored = [], []
        gap = "." in raw or "?" in raw
        for ch in raw:
            if ch == "[":
                inside = True
            elif ch == "]":
                inside = False
            k = T.to_continua(ch)
            if k:
                letters.append(k)
                restored.append(inside)
        if not letters:
            if gap and words:
                words[-1]["gap_after"] = True
            continue
        norm = normalize_token(raw)
        key = T.to_continua(norm.form)
        if not key:
            continue
        if adscript_left(norm.form):
            key = key[:-1]          # ὧι, ἧι, ᾗι: final adscript that papyri.ADSCRIPT misses (breathing on ω/η)
        words.append({"raw": raw, "form": norm.form, "key": key, "n": len(letters),
                      "restored": sum(restored), "gap": gap, "gap_after": False,
                      "elided": raw.rstrip(",.·;:")[-1:] in "’'ʼ᾿᾽",
                      "unarticulated": unarticulated(norm.form, key)})
    for i, w in enumerate(words):
        w["fragment"] = (w["gap"] or w["gap_after"] or (i > 0 and words[i - 1]["gap_after"])
                         or w["unarticulated"])
    return words


def restored_class(w: dict) -> str:
    if w["restored"] == 0:
        return "read"
    if w["restored"] >= w["n"]:
        return "restored"
    return "partly_restored"


def flag_words(seg: T.Segmenter, words: list[dict], margin: float) -> list[dict]:
    lex = seg.lex
    ids = [lex.exact.get(w["key"], -1) for w in words]
    rows = []

    def lp(prev: int, wid: int) -> float:
        if wid < 0:
            return math.log(T.P_UNK) + 3 * math.log(1 / 24)     # unknown, length-neutral
        return float(seg.lm_grid(T.np.array([prev], dtype=T.np.int64), T.np.array([wid], dtype=T.np.int64))[0, 0])

    for i, w in enumerate(words):
        if w["fragment"] or w["elided"]:
            continue
        prev = ids[i - 1] if i else -1
        nxt = ids[i + 1] if i + 1 < len(ids) else None
        wid = ids[i]
        base = lp(prev, wid) + (lp(wid, nxt) if nxt is not None and nxt >= 0 else 0.0)
        best = None
        for cid, chan, tag in lex.candidates(w["key"], top=12):
            if cid == wid:
                continue
            sc = lp(prev, cid) + chan + (lp(cid, nxt) if nxt is not None and nxt >= 0 else 0.0)
            if best is None or sc > best[0]:
                best = (sc, cid, tag)
        unatt = wid < 0
        alt = best is not None and best[0] - base > margin
        if not (unatt or alt):
            continue
        kind = "unattested+alt" if unatt and alt else ("unattested" if unatt else "alternative")
        ctx = " ".join(x["form"] for x in words[max(0, i - 3): i + 4])
        rows.append({"i": i, "raw": w["raw"], "form": w["form"], "key": w["key"], "letters": w["n"],
                     "restored_letters": w["restored"], "class": restored_class(w), "kind": kind,
                     "count": int(lex.c.uni[wid]) if wid >= 0 else 0,
                     "best_alternative": lex.c.forms[best[1]] if best else "",
                     "alt_edit": best[2] if best else "",
                     "alt_count": int(lex.c.uni[best[1]]) if best else 0,
                     "margin_nats": round(best[0] - base, 2) if best else None, "context": ctx})
    return rows


def division_check(seg: T.Segmenter, text: str, limit: int = 0) -> dict:
    """The papyrus lines the editor read in full (no brackets, dots, insertions, digits), reduced to scriptio
    continua and segmented; the editor's word division is the reference. Line-final hyphenated words and the
    continuation at the next line's start are partial words: they stay in the string (as on the papyrus) and
    only the boundaries inside the line are scored."""
    tp = fp = fn = exact = n = 0
    samples = []
    prev_hyphen = False
    for line in text.splitlines():
        s = line.strip()
        hyph = s.endswith("-")
        bad = (not s) or re.search(r"[\[\]〈〉<>{}.?\d†A-Za-z]", s)
        if bad:
            prev_hyphen = hyph
            continue
        words = [T.to_continua(w) for w in s.rstrip("-").split()]
        words = [w for w in words if w]
        prev_hyphen, starts_partial = hyph, prev_hyphen
        if len(words) < 2:
            continue
        cont = "".join(words)
        gold, pos = set(), 0
        for w in words[:-1]:
            pos += len(w)
            gold.add(pos)
        best = seg.segment(cont, k=1)[0]
        pred = best.boundaries
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)
        exact += pred == gold
        n += 1
        if len(samples) < 30 and pred != gold:
            samples.append({"line": s, "editor": " ".join(words), "scorer": best.text,
                            "edge_partial": [starts_partial, hyph]})
        if limit and n >= limit:
            break
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    return {"lines": n, "boundary_P": round(P, 4), "boundary_R": round(R, 4),
            "boundary_F1": round(2 * P * R / (P + R), 4) if P + R else 0.0,
            "line_division_exact": round(exact / n, 4) if n else 0.0, "disagreements_sample": samples}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--works", default="tlg1595.tlg221,tlg1595.tlg370")
    ap.add_argument("--margin", type=float, default=4.0)
    a = ap.parse_args(argv)
    root = T.data_root(a.data_root)
    hold = json.loads((OUT / "holdout_works.json").read_text(encoding="utf-8"))
    works = a.works.split(",")
    missing = [w for w in works if w not in set(hold.get("real", []) + hold.get("test", []) + hold.get("dev", []))]
    if missing:
        raise SystemExit(f"{missing} are not held out of the counts; their words would attest themselves")
    seg = T.load_model(root, log=lambda m: print(m, file=sys.stderr))
    all_rows, summary = [], {"margin_nats": a.margin, "works": {}}
    for w in works:
        files = [p for p in T.corpus_files(root) if T.work_id(p) == w]
        text = files[0].read_text(encoding="utf-8", errors="replace")
        words = leiden_words(text)
        rows = flag_words(seg, words, a.margin)
        div = division_check(seg, text)
        print(w, "division", {k: v for k, v in div.items() if k != "disagreements_sample"}, flush=True)
        for r in rows:
            r["work"] = w
        all_rows += rows
        scored = [x for x in words if not (x["fragment"] or x["elided"])]
        by_cls = Counter(restored_class(x) for x in scored)
        fl_cls = Counter(r["class"] for r in rows)
        kinds = Counter(r["kind"] for r in rows)
        summary["works"][w] = {
            "file": files[0].name, "words": len(words), "fragments_or_elided_not_scored": len(words) - len(scored),
            "scored": len(scored), "flagged": len(rows), "by_kind": dict(kinds), "word_division_check": div,
            "flag_rate_by_class": {c: {"words": by_cls[c], "flagged": fl_cls[c],
                                       "rate": round(fl_cls[c] / by_cls[c], 4) if by_cls[c] else None}
                                   for c in ("read", "partly_restored", "restored")}}
        print(w, json.dumps(summary["works"][w]["flag_rate_by_class"]), dict(kinds), flush=True)
    all_rows.sort(key=lambda r: -(r["margin_nats"] or 0))
    cols = ["work", "i", "raw", "form", "key", "class", "letters", "restored_letters", "kind", "count",
            "best_alternative", "alt_edit", "alt_count", "margin_nats", "context"]
    with open(OUT / "philodemus_flags.csv", "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for r in all_rows:
            wr.writerow({c: r[c] for c in cols})
    (OUT / "philodemus_flags_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    print(f"{len(all_rows)} flags -> {OUT / 'philodemus_flags.csv'}")


if __name__ == "__main__":
    main()
