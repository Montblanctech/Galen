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


def _gap_marks(raw: str) -> bool:
    """Unread letters (Leiden dots) or a query in the token. One full stop right after a letter at the end of
    the token is punctuation (ὅλως.), not an unread letter."""
    core = raw
    if len(core) >= 2 and core.endswith(".") and core[-2] not in ". ":
        core = core[:-1]
    return "." in core or "?" in core


def leiden_words(text: str) -> list[dict]:
    """Edited text -> words with per-letter restored flags. Hyphenated line ends are joined; supplement
    brackets may span words and lines. Each word records whether it ends its line (eol) and whether a token
    without letters (a stray bracket, a line number, a column mark) follows it (stray_after)."""
    text = re.sub(r"-\s*\n\s*", "", text)
    inside = False
    words = []
    raws = []
    for line in text.splitlines():
        toks = line.split()
        for j, raw in enumerate(toks):
            raws.append((raw, j == len(toks) - 1))
    for raw, last_on_line in raws:
        letters, restored = [], []
        gap = _gap_marks(raw)
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
            elif words:
                words[-1]["stray_after"] = True
            if last_on_line and words:
                words[-1]["eol"] = True
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
                      "unarticulated": unarticulated(norm.form, key), "eol": last_on_line, "stray_after": False})
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


ONE_LETTER_WORDS = {"Ο", "Η", "Ω"}      # ὁ, ἡ/ἤ/ᾗ, ὦ; any other lone letter is debris of a broken line
SPELLING_MIN_RATE = 1e-3                # a rule rarer than this explains a word only as the writer's habit


def mark_debris(words: list[dict]) -> None:
    for w in words:
        if len(w["key"]) == 1 and w["key"] not in ONE_LETTER_WORDS:
            w["fragment"] = True


JOIN_MARGIN = 4.0   # nats: two attested halves are joined only if the whole is this much more likely


def _gapped(words: list[dict], i: int) -> bool:
    w = words[i]
    return w["gap"] or w["gap_after"] or (i > 0 and words[i - 1]["gap_after"])


def join_splits(lex: T.Lexicon, words: list[dict]) -> int:
    """A word split in the digital text: two neighbours (neither touching an unread gap, the first not elided)
    whose joined key is attested, and either (a) one half is unattested, or (b) the first half ends its line or
    is followed by a stray mark (a bracket, a line number) and the joined word is more likely than the two
    halves by JOIN_MARGIN nats (unigram counts: ῥυ | θμῶν, παι] | γνίων). The first half may be unaccented,
    since the editor puts the accent on the half that carries it. They become one word; its fragment flag is
    recomputed. Returns the number of joins."""
    out, n, i = [], 0, 0
    logN = math.log(lex.c.n_tokens)
    while i < len(words):
        w = words[i]
        if i + 1 < len(words) and not (_gapped(words, i) or _gapped(words, i + 1) or w["elided"]):
            v = words[i + 1]
            joined = w["key"] + v["key"]
            jid = lex.exact.get(joined)
            a, b = lex.exact.get(w["key"]), lex.exact.get(v["key"])
            ok = False
            if jid is not None:
                if a is None or b is None:
                    ok = True
                elif w.get("eol") or w.get("stray_after"):
                    lj = math.log(lex.c.uni[jid]) - logN
                    la = math.log(lex.c.uni[a]) - logN
                    lb = math.log(lex.c.uni[b]) - logN
                    ok = lj > la + lb + JOIN_MARGIN
            if ok:
                form = w["form"] + v["form"]
                un = unarticulated(form, joined)
                out.append({**w, "raw": w["raw"] + " " + v["raw"], "form": form, "key": joined,
                            "n": w["n"] + v["n"], "restored": w["restored"] + v["restored"],
                            "gap_after": v["gap_after"], "elided": v["elided"], "joined": True,
                            "unarticulated": un, "fragment": un, "eol": v.get("eol"),
                            "stray_after": v.get("stray_after")})
                n += 1
                i += 2
                continue
        out.append(w)
        i += 1
    words[:] = out
    return n


def flag_words(seg: T.Segmenter, words: list[dict], margin: float, spellings: list | None = None) -> list[dict]:
    """Flags, as described in the module docstring. With a spelling channel on the lexicon, an unattested word
    that one learned spelling rule turns into an attested form is an ancient spelling, not a flag (it goes to
    `spellings`), unless the rule is rarer than SPELLING_MIN_RATE in the papyri and this text does not use it
    habitually (adapted cost, t2b_spelling.adapt_costs), or a misreading explains the word much better."""
    lex = seg.lex
    ids = [lex.exact.get(w["key"], -1) for w in words]
    rows = []
    sp = lex.spelling
    min_cost = math.log(SPELLING_MIN_RATE)

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
        var = None
        for cid, chan, tag in lex.candidates(w["key"], top=12):
            if cid == wid:
                continue
            sc = lp(prev, cid) + chan + (lp(cid, nxt) if nxt is not None and nxt >= 0 else 0.0)
            if tag.startswith("var:"):
                if var is None or sc > var[0]:
                    var = (sc, cid, tag, chan)
                continue
            if best is None or sc > best[0]:
                best = (sc, cid, tag)
        unatt = wid < 0
        if unatt and var is not None and sp is not None:
            k = int(var[2][4:])
            accepted = sp.costs[k] >= min_cost and var[3] >= min_cost
            misread_better = best is not None and best[0] - var[0] > margin
            if spellings is not None:
                spellings.append({"i": i, "raw": w["raw"], "form": w["form"], "key": w["key"],
                                  "regularized": lex.c.forms[var[1]], "rule": k, "rule_label": sp.label(k),
                                  "rule_cost": round(sp.costs[k], 3), "accepted": accepted and not misread_better,
                                  "class": restored_class(w)})
            if accepted and not misread_better:
                continue
        alt = best is not None and best[0] - base > margin
        if not (unatt or alt):
            continue
        alt_spelling = ""
        if alt and sp is not None:
            # the misreading the channel proposes is also a known spelling of the same word (τύπανον, τύμπανον)
            for reg, k, cost in lex.spelling.rewrites(w["key"]):
                if reg == lex.c.forms[best[1]] and cost >= min_cost:
                    alt_spelling = sp.label(k)
                    break
        kind = "unattested+alt" if unatt and alt else ("unattested" if unatt else "alternative")
        ctx = " ".join(x["form"] for x in words[max(0, i - 3): i + 4])
        rows.append({"i": i, "raw": w["raw"], "form": w["form"], "key": w["key"], "letters": w["n"],
                     "restored_letters": w["restored"], "class": restored_class(w), "kind": kind,
                     "count": int(lex.c.uni[wid]) if wid >= 0 else 0,
                     "best_alternative": lex.c.forms[best[1]] if best else "",
                     "alt_edit": best[2] if best else "",
                     "alt_count": int(lex.c.uni[best[1]]) if best else 0,
                     "margin_nats": round(best[0] - base, 2) if best else None, "context": ctx,
                     "joined": bool(w.get("joined")),
                     "alt_spelling": alt_spelling,
                     "stem_attested": bool(unatt and sp is not None and lex.stem_attested(w["key"])),
                     "spelling_option": (lex.c.forms[var[1]] + " (" + sp.label(int(var[2][4:])) + ")")
                     if (unatt and var is not None and sp is not None) else ""})
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
    ap.add_argument("--no-spelling", action="store_true", help="the v1 flagger: no spelling rules, joins or debris")
    ap.add_argument("--tag", default="", help="suffix for the output files")
    a = ap.parse_args(argv)
    root = T.data_root(a.data_root)
    hold = json.loads((OUT / "holdout_works.json").read_text(encoding="utf-8"))
    works = a.works.split(",")
    missing = [w for w in works if w not in set(hold.get("real", []) + hold.get("test", []) + hold.get("dev", []))]
    if missing:
        raise SystemExit(f"{missing} are not held out of the counts; their words would attest themselves")
    seg = T.load_model(root, log=lambda m: print(m, file=sys.stderr), spelling=not a.no_spelling)
    sp = seg.lex.spelling
    all_rows, all_sp, summary = [], [], {"margin_nats": a.margin, "spelling": not a.no_spelling, "works": {}}
    for w in works:
        files = [p for p in T.corpus_files(root) if T.work_id(p) == w]
        text = files[0].read_text(encoding="utf-8", errors="replace")
        words = leiden_words(text)
        joins = 0
        habits = []
        spellings: list = []
        if sp is not None:
            joins = join_splits(seg.lex, words)
            mark_debris(words)
            # pass 1: corpus rule costs; then the text's own habits (t2b_spelling.adapt_costs); pass 2 with them
            first: list = []
            flag_words(seg, words, a.margin, first)
            uses = Counter(x["rule"] for x in first)
            by_i = {x["i"]: x["regularized"] for x in first}
            forms = [by_i.get(i, x["key"]) for i, x in enumerate(words) if not (x["fragment"] or x["elided"])]
            import t2b_spelling as S
            opps = S.opportunities(sp, forms)
            costs = S.adapt_costs(sp, uses, opps)
            seg.lex.set_spelling_costs(costs)
            if costs is not None:
                habits = [{"rule": k, "label": sp.label(k), "uses": uses[k], "opportunities": opps.get(k, 0),
                           "corpus_rate": sp.rules[k]["rate"], "text_rate": round(math.exp(costs[k]), 4)}
                          for k in sorted(uses, key=lambda k: -uses[k]) if costs[k] != sp.base[k]]
        rows = flag_words(seg, words, a.margin, spellings)
        if sp is not None:
            seg.lex.set_spelling_costs(None)
            for x in spellings:
                x["work"] = w
            all_sp += spellings
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
            "split_words_joined": joins,
            "flags_unattested_attested_stem": sum(1 for r in rows if r.get("stem_attested")),
            "flags_alternative_is_spelling": sum(1 for r in rows if r.get("alt_spelling")),
            "spellings_accepted": sum(1 for x in spellings if x["accepted"]),
            "spellings_rejected": sum(1 for x in spellings if not x["accepted"]),
            "spelling_profile": [{"label": lab, "words": n} for lab, n in
                                 Counter(x["rule_label"] for x in spellings if x["accepted"]).most_common()],
            "habits": habits,
            "flag_rate_by_class": {c: {"words": by_cls[c], "flagged": fl_cls[c],
                                       "rate": round(fl_cls[c] / by_cls[c], 4) if by_cls[c] else None}
                                   for c in ("read", "partly_restored", "restored")}}
        print(w, json.dumps(summary["works"][w]["flag_rate_by_class"]), dict(kinds), flush=True)
    all_rows.sort(key=lambda r: -(r["margin_nats"] or 0))
    cols = ["work", "i", "raw", "form", "key", "class", "letters", "restored_letters", "kind", "count",
            "best_alternative", "alt_edit", "alt_count", "margin_nats", "context", "joined", "spelling_option",
            "alt_spelling", "stem_attested"]
    if sp is not None:
        sc = ["work", "i", "raw", "form", "key", "regularized", "rule_label", "rule_cost", "accepted", "class"]
        with open(OUT / f"philodemus_spellings{a.tag}.csv", "w", encoding="utf-8", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=sc)
            wr.writeheader()
            for r in all_sp:
                wr.writerow({c: r[c] for c in sc})
    with open(OUT / f"philodemus_flags{a.tag}.csv", "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for r in all_rows:
            wr.writerow({c: r.get(c, "") for c in cols})
    (OUT / f"philodemus_flags_summary{a.tag}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    print(f"{len(all_rows)} flags -> {OUT / ('philodemus_flags' + a.tag + '.csv')}")


if __name__ == "__main__":
    main()
