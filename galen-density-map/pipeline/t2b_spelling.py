"""T2b spelling rules: how often ancient writers spelled a sound one way or another, learned from editors' marks.

Input: data/t2b_cache/spelling_pairs.jsonl and spelling_regwords.jsonl (t2b_spelling_data.py), train documents
only. Every (orig, reg) word pair is aligned letter by letter; each difference is one rule

    reg -> orig, before a vowel (V), a consonant (C) or at the word end (#)

e.g. ΟΙ -> Ο before V (ποιητικόν written ποητικόν), Ι -> ΕΙ (κινεῖν written κεινεῖν), Ν -> Μ before C. A letter
added or dropped is attached to its neighbour, preferring the side where it makes a diphthong or a doubled
letter (so Ι dropped after Ο is ΟΙ -> Ο, not a free deletion). Pairs with more than two differences, or a
difference longer than two letters, are left out (they are usually different words, not spellings).

rate(rule) = times the rule was applied / times its reg side occurs with that right context in the train
documents' regularized words. A rule is kept if it was applied at least MIN_APPS times and its rate is at least
MIN_RATE. The channel cost of reading a written form as its regularized form is log(rate); one rule per word.

  python -I -X utf8 pipeline/t2b_spelling.py learn
writes outputs/t2b/spelling_rules.json (the table the Python scorer and the browser engine both read).
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RULES_PATH = PROJECT / "outputs" / "t2b" / "spelling_rules.json"

VOWELS = set("ΑΕΗΙΟΥΩ")
DIGRAPHS = {"ΑΙ", "ΕΙ", "ΟΙ", "ΥΙ", "ΑΥ", "ΕΥ", "ΗΥ", "ΟΥ", "ΩΥ"}
MIN_APPS = 20
MIN_RATE = 1e-4
MAX_SIDE = 3
# a rule that this document uses at least this often is taken as the writer's habit (see adapt_costs)
HABIT_MIN = 3
HABIT_PRIOR = 20.0      # pseudo-opportunities of the corpus-wide rate when a document's own rate is estimated
HABIT_P = 1e-3          # a habit: this many uses would happen by chance at the papyri's own rate less often than this


def right_class(ch: str | None) -> str:
    if not ch:
        return "#"
    return "V" if ch in VOWELS else "C"


def _attach(reg: str, orig: str, i1: int, i2: int, j1: int, j2: int):
    """A pure insertion or deletion -> (R, O, position in reg after R) with a neighbour letter attached."""
    x = orig[j1:j2] if i1 == i2 else reg[i1:i2]          # the letters added (insert) or dropped (delete)
    ins = i1 == i2
    left = reg[i1 - 1] if i1 > 0 else None
    right = reg[i2] if i2 < len(reg) else None

    def mk(side):
        if side == "L":
            R = left + ("" if ins else x)
            O = left + (x if ins else "")
            return R, O, i2, i1 - 1
        R = ("" if ins else x) + right
        O = (x if ins else "") + right
        return R, O, i2 + 1, i1

    good_r = right is not None and ((x + right) in DIGRAPHS or (len(x) == 1 and x == right))
    good_l = left is not None and ((left + x) in DIGRAPHS or (len(x) == 1 and x == left))
    if good_r and not good_l:
        return mk("R")
    if left is not None:
        return mk("L")
    if right is not None:
        return mk("R")
    return None


def rules_of_pair(orig: str, reg: str) -> list[tuple[str, str, str, bool]] | None:
    """The rules that turn reg into orig: (R, O, right class, at word start). None if the pair is not a spelling."""
    if abs(len(orig) - len(reg)) > 2 or min(len(orig), len(reg)) < 2:
        return None
    ops = [o for o in difflib.SequenceMatcher(None, reg, orig, autojunk=False).get_opcodes() if o[0] != "equal"]
    if not ops or len(ops) > 2:
        return None
    out = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace":
            R, O, after, start = reg[i1:i2], orig[j1:j2], i2, i1
        else:
            a = _attach(reg, orig, i1, i2, j1, j2)
            if a is None:
                return None
            R, O, after, start = a
        if not R or not O or len(R) > MAX_SIDE or len(O) > MAX_SIDE:
            return None
        out.append((R, O, right_class(reg[after] if after < len(reg) else None), start == 0))
    return out


# Consonant interchanges that are sound changes in Koine Greek (Gignac 1976, vol. 1): same place of
# articulation (voicing, aspiration), nasals, liquids, Σ/Ζ. Anything else at word end is usually a grammatical
# regularization (case endings) or an abbreviation, which are not spellings and are left out.
CONS_GROUPS = ["ΚΓΧ", "ΤΔΘ", "ΠΒΦ", "ΝΜΓ", "ΛΡ", "ΣΖ"]
NASALS = set("ΝΜΓ")
DOUBLE = {("Ξ", "ΚΣ"), ("Ξ", "ΓΣ"), ("Ξ", "ΧΣ"), ("Ψ", "ΠΣ"), ("Ψ", "ΦΣ")}


def _core(R: str, O: str) -> tuple[str, str]:
    i = 0
    while i < min(len(R), len(O)) and R[i] == O[i]:
        i += 1
    j = 0
    while j < min(len(R), len(O)) - i and R[-1 - j] == O[-1 - j]:
        j += 1
    return R[i:len(R) - j], O[i:len(O) - j]


def kind_of(R: str, O: str, right: str) -> str | None:
    """The phonological class of a rule, or None if it is not a spelling (grammar, abbreviation, other)."""
    r, o = _core(R, O)
    if all(c in VOWELS for c in r + o):
        return "vowel"
    if (r, o) in DOUBLE or (o, r) in DOUBLE:
        return "double letter"
    if len(r) == 1 and len(o) == 1 and any(r in g and o in g for g in CONS_GROUPS):
        return "consonant"
    if {len(r), len(o)} == {0, 1}:
        x = r or o
        if (R == x + x and O == x) or (O == x + x and R == x) or (x in R and x in O and (x + x in R or x + x in O)):
            return "double consonant"
        if x == "Ν" and right == "#":
            return "final nu"
        if x in NASALS and right == "C":
            return "nasal before consonant"
    return None


def learn(pairs_path: Path, regwords_path: Path) -> dict:
    apps: Counter = Counter()
    examples: dict = defaultdict(list)
    n_pairs = n_used = 0
    for line in open(pairs_path, encoding="utf-8"):
        x = json.loads(line)
        if x.get("type") == "sic" or x["split"] != "train" or x.get("near_gap"):
            continue
        n_pairs += 1
        rs = rules_of_pair(x["orig"], x["reg"])
        if not rs:
            continue
        n_used += 1
        for r in rs:
            apps[r] += 1
            if len(examples[r]) < 3 and (x["orig"], x["reg"]) not in examples[r]:
                examples[r].append((x["orig"], x["reg"]))
    cand = [r for r, k in apps.items() if k >= MIN_APPS]
    sides = {r[0] for r in cand}
    maxl = max((len(s) for s in sides), default=1)
    opp: Counter = Counter()
    n_words = 0
    for line in open(regwords_path, encoding="utf-8"):
        d = json.loads(line)
        if d["split"] != "train":
            continue
        for w in d["words"]:
            n_words += 1
            for i in range(len(w)):
                for L in range(1, maxl + 1):
                    s = w[i:i + L]
                    if len(s) < L:
                        break
                    if s in sides:
                        rc = right_class(w[i + L] if i + L < len(w) else None)
                        opp[(s, rc, False)] += 1
                        if i == 0:
                            opp[(s, rc, True)] += 1
    rules = []
    dropped = Counter()
    for r in cand:
        R, O, rc, start = r
        kind = kind_of(R, O, rc)
        if kind is None:
            dropped["not a spelling (grammar, abbreviation, other)"] += 1
            continue
        o = opp[(R, rc, start)] if start else opp[(R, rc, False)]
        if not o:
            continue
        rate = apps[r] / o
        if rate < MIN_RATE or rate >= 1:
            dropped["rate below MIN_RATE"] += 1
            continue
        rules.append({"reg": R, "orig": O, "right": rc, "start": start, "kind": kind, "apps": apps[r], "opps": o,
                      "rate": round(rate, 6), "cost": round(math.log(rate), 4),
                      "examples": [f"{a} for {b}" for a, b in examples[r]]})
    rules.sort(key=lambda d: (-d["apps"], d["reg"], d["orig"], d["right"], d["start"]))
    return {"source": "papyri.info DDbDP + DCLP regularizations (<choice><reg>/<orig>), CC BY 3.0; train documents",
            "min_apps": MIN_APPS, "min_rate": MIN_RATE, "habit_min": HABIT_MIN, "habit_prior": HABIT_PRIOR, "habit_p": HABIT_P,
            "pairs_seen": n_pairs, "pairs_used": n_used, "reg_words": n_words, "n_rules": len(rules),
            "candidates": len(cand), "dropped": dict(dropped),
            "by_kind": dict(Counter(x["kind"] for x in rules)),
            "rules": rules}


# ---------------------------------------------------------------------------------------------
# the channel side (used by t2b_scorer.Lexicon)
# ---------------------------------------------------------------------------------------------

class SpellingRules:
    """Read a written form as its regularized form: every way one rule, applied backwards, rewrites `obs`."""

    def __init__(self, table: dict, costs: list[float] | None = None):
        self.table = table
        self.rules = table["rules"]
        self.base = [r["cost"] for r in self.rules]
        self.costs = list(costs) if costs is not None else list(self.base)
        self.by_orig: dict[str, list[int]] = defaultdict(list)
        for k, r in enumerate(self.rules):
            self.by_orig[r["orig"]].append(k)
        self.lens = sorted({len(o) for o in self.by_orig})

    @classmethod
    def load(cls, path: Path = RULES_PATH) -> "SpellingRules":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def rewrites(self, obs: str, positions: bool = False):
        """(regularized string, rule index, cost) for every single-rule rewrite of `obs`, in a fixed order:
        position ascending, then orig length ascending, then rule index. positions=True adds (i, len(orig))."""
        n = len(obs)
        for i in range(n):
            for L in self.lens:
                if i + L > n:
                    break
                ks = self.by_orig.get(obs[i:i + L])
                if not ks:
                    continue
                rc = right_class(obs[i + L] if i + L < n else None)
                for k in ks:
                    r = self.rules[k]
                    if r["right"] != rc or (r["start"] and i != 0):
                        continue
                    if positions:
                        yield obs[:i] + r["reg"] + obs[i + L:], k, self.costs[k], i, L
                    else:
                        yield obs[:i] + r["reg"] + obs[i + L:], k, self.costs[k]

    def label(self, k: int) -> str:
        r = self.rules[k]
        where = {"V": "before a vowel", "C": "before a consonant", "#": "at the word end"}[r["right"]]
        return f"{r['reg']} written {r['orig']} {where}" + (" (word start)" if r["start"] else "")


def poisson_tail(u: int, lam: float) -> float:
    """P(X >= u) for X ~ Poisson(lam), as 1 - sum_{j<u} e^-lam lam^j / j!"""
    s, term = 0.0, math.exp(-lam)
    for j in range(u):
        s += term
        term *= lam / (j + 1)
    return 1.0 - s


def adapt_costs(sp: SpellingRules, uses: Counter, opps: Counter) -> list[float] | None:
    """The writer's habits: a rule this text uses at least HABIT_MIN times, and so often that its papyri-wide
    rate would give that many uses by chance with probability below HABIT_P (Poisson, opportunities x rate),
    gets the text's own rate, shrunk toward the corpus rate: (uses + prior * rate) / (opportunities + prior).
    Other rules keep the corpus cost. None if no rule qualifies."""
    out = list(sp.base)
    changed = False
    for k, u in uses.items():
        if u < HABIT_MIN:
            continue
        r = sp.rules[k]
        o = max(opps.get(k, 0), u)
        if poisson_tail(u, o * r["rate"]) >= HABIT_P:
            continue
        rate = (u + HABIT_PRIOR * r["rate"]) / (o + HABIT_PRIOR)
        c = math.log(min(rate, 0.5))
        if c > out[k]:
            out[k] = c
            changed = True
    return out if changed else None


def opportunities(sp: SpellingRules, forms: list[str]) -> Counter:
    """How often each rule's reg side (with its right context) occurs in a list of regularized forms."""
    by_reg: dict[str, list[int]] = defaultdict(list)
    for k, r in enumerate(sp.rules):
        by_reg[r["reg"]].append(k)
    lens = sorted({len(s) for s in by_reg})
    c: Counter = Counter()
    for w in forms:
        for i in range(len(w)):
            for L in lens:
                if i + L > len(w):
                    break
                for k in by_reg.get(w[i:i + L], ()):
                    r = sp.rules[k]
                    if r["right"] == right_class(w[i + L] if i + L < len(w) else None) and (not r["start"] or i == 0):
                        c[k] += 1
    return c


RUST_TABLE = PROJECT.parent / "t2b-wasm" / "src" / "spelling_table.rs"
_LETTERS = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"


def export_rust(table: dict, path: Path = RUST_TABLE) -> None:
    """The rule table as Rust source for the browser engine (same rules, same order, same float values)."""
    def codes(x: str) -> str:
        return "&[" + ", ".join(str(_LETTERS.index(c)) for c in x) + "]"
    rc = {"V": 0, "C": 1, "#": 2}
    lines = ["//! Generated by galen-density-map/pipeline/t2b_spelling.py export-rust from outputs/t2b/spelling_rules.json;",
             "//! do not edit. Spelling rules learned from papyri.info regularizations (DDbDP + DCLP, CC BY 3.0).",
             "",
             "pub struct Rule {",
             "    /// regularized side, letter codes",
             "    pub reg: &'static [u8],",
             "    /// written side, letter codes",
             "    pub orig: &'static [u8],",
             "    /// right context: 0 vowel, 1 consonant, 2 word end",
             "    pub right: u8,",
             "    /// only at the word start",
             "    pub start: bool,",
             "    pub rate: f64,",
             "    pub cost: f64,",
             "}",
             "",
             f"pub const HABIT_MIN: u32 = {table['habit_min']};",
             f"pub const HABIT_PRIOR: f64 = {float(table['habit_prior'])!r};",
             f"pub const HABIT_P: f64 = {float(table['habit_p'])!r};",
             "",
             "pub static RULES: &[Rule] = &["]
    for r in table["rules"]:
        lines.append(f"    Rule {{ reg: {codes(r['reg'])}, orig: {codes(r['orig'])}, right: {rc[r['right']]}, "
                     f"start: {'true' if r['start'] else 'false'}, rate: {float(r['rate'])!r}, cost: {float(r['cost'])!r} }},")
    lines.append("];")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["learn", "export-rust"])
    a = ap.parse_args(argv)
    if a.cmd == "export-rust":
        export_rust(json.loads(RULES_PATH.read_text(encoding="utf-8")))
        print(f"-> {RUST_TABLE}")
        return
    cache = PROJECT / "data" / "t2b_cache"
    t = learn(cache / "spelling_pairs.jsonl", cache / "spelling_regwords.jsonl")
    RULES_PATH.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{t['n_rules']} rules from {t['pairs_used']:,} of {t['pairs_seen']:,} pairs -> {RULES_PATH}")
    for r in t["rules"][:40]:
        print(f"{r['reg']:>4} -> {r['orig']:<4} {r['right']} {'^' if r['start'] else ' '} {r['apps']:>6} / {r['opps']:>8}"
              f"  {r['rate']:.4f}  {r['examples'][:2]}")


if __name__ == "__main__":
    main()


def segment_text(seg, text: str, k: int = 5) -> tuple[list, list[dict]]:
    """A whole text, one input per non-empty line, with the writer's habits (the reference for the browser's
    segment_text_json): pass 1 reads every line with the table's costs; rules the best readings use often enough
    (adapt_costs) get the text's own rate; every line is read again. Returns (readings per line, habits); the
    lexicon's costs are restored."""
    lines = [l for l in text.splitlines() if l.strip()]
    lex = seg.lex
    sp = lex.spelling
    uses: Counter = Counter()
    forms: list[str] = []
    for l in lines:
        r = seg.segment(l, k=1)[0]
        for g in r.segments:
            if g.edit.startswith("var:"):
                uses[int(g.edit[4:])] += 1
            if g.form is not None:
                forms.append(g.form)
    opps = opportunities(sp, forms)
    costs = adapt_costs(sp, uses, opps)
    habits = []
    if costs is not None:
        for q in sorted(uses, key=lambda q: (-uses[q], q)):
            if costs[q] == sp.base[q]:
                continue
            habits.append({"rule": q, "label": sp.label(q), "uses": uses[q], "opportunities": opps.get(q, 0),
                           "corpus_rate": sp.rules[q]["rate"], "text_rate": math.exp(costs[q])})
        lex.set_spelling_costs(costs)
    try:
        out = [seg.segment(l, k=k) for l in lines]
    finally:
        lex.set_spelling_costs(None)
    return out, habits
