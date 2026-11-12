"""Headline numbers: one file, computed from the data, and a check that no text carries an old one (2026-11-11).

Every headline figure the project publishes (works drafted, Greek words, findings, LSJ-Gold and LS-Gold sizes and
scores, lexicon pairs, census totals) is computed here from the files it describes and written to
galen-density-map/facts.json. Nobody types these numbers. The site generators read them from there.

Prose that people write (README, CITATION.cff, .zenodo.json, notes, drafts for posting) cannot fill itself in, so
`check` looks for old values instead: when a figure changes, `build` keeps the old value in the file's history, and
`check` fails on any text that still carries it, outside the changelog, the versioned release folders and the
reviewed history mentions in facts_allow.tsv. Text already posted elsewhere (GitHub issues, Zenodo records) is listed
in facts_external.json with a local copy of what was posted; `check` names the ones that now carry an old value, so
they can be corrected by hand.

  python -X utf8 facts.py build       recompute facts.json from the data (lab or public checkout)
  python -X utf8 facts.py check       fail (exit 1) on any old value in our text; list posted places to correct
  python -X utf8 facts.py fix [--write]   replace old values with current ones in our text (shows each change; writes with --write)
  python -X utf8 facts.py mentions    write facts_mentions.md: every place each current figure appears

`check` needs only facts.json and the text files, so it also runs in CI on the public repository.
"""
from __future__ import annotations

import csv
import fnmatch
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

GDM = Path(__file__).resolve().parents[1]
REPO = GDM.parent
FACTS = GDM / "facts.json"
ALLOW = GDM / "facts_allow.tsv"
EXTERNAL = GDM / "facts_external.json"
MENTIONS = GDM / "facts_mentions.md"

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
         11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
         18: "eighteen", 19: "nineteen", 20: "twenty"}

# Values these facts had before facts.json existed, so the check catches them from the start (dates: when replaced).
SEED_HISTORY = {
    "first_drafts.works": [{"value": 9, "until": "2026-11-10"}],
    "first_drafts.greek_words": [{"value": 257016, "until": "2026-11-11"}],
    "lsjgold.loci": [{"value": 93926, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.neural_loci": [{"value": 90452, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.score.dilemma": [{"value": 90.1, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.score.stoicheia": [{"value": 87.7, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.score.stanza_perseus": [{"value": 79.6, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.score.odycy": [{"value": 75.7, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.score.stanza_proiel": [{"value": 72.0, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.once.dilemma": [{"value": 83.8, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lsjgold.once.stoicheia": [{"value": 75.0, "until": "2026-11-10", "note": "LSJ-Gold 0.1"}],
    "lexicon.pairs": [{"value": 45886, "until": "2026-11-10", "note": "lexicon 0.1"},
                      {"value": 29858, "until": "2026-11-11", "note": "lexicon 0.1.1"}],
}

# Never scanned: history by design (changelog, versioned releases, the Phase 2 preprint), data tables, lab-only pages.
EXEMPT = ["CHANGELOG.md", "release/*", "paper/*", "submissions/*", "audit-kit/greek_lemma_audit/data/*",
          "docs/mw-gold/*", "docs/first-drafts/*/data.json", "galen-density-map/facts*",
          "*.csv", "*.tsv", "*.jsonl", "*.png", "*.pdf", "*.zip", "*.sha256", "*.bib", "*.sty", "*.bst"]
TEXT = (".md", ".html", ".cff", ".json", ".txt", ".yml", ".yaml", ".tex", ".py", ".toml")


# ---------------------------------------------------------------- build

def _json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def compute() -> dict[str, dict]:
    """Every fact from its source file. kind: int (thousands-separated), count (small, with a noun), pct, text."""
    F: dict[str, dict] = {}

    def put(key, value, source, kind="int", label="", noun=""):
        F[key] = {"value": value, "kind": kind, "label": label, "source": source, **({"noun": noun} if noun else {})}

    # Galen First Drafts: the works with a published page
    sys.path.insert(0, str(GDM / "pipeline" / "firstdrafts"))
    from common import draft_words, out_dir   # noqa: E402
    fd = REPO / "docs" / "first-drafts"
    slugs = sorted(p.parent.name for p in fd.glob("*/data.json"))
    words = sum(draft_words(s) for s in slugs)
    units = sum(_json(out_dir(s) / "units_meta.json")["n_units"] for s in slugs)
    put("first_drafts.works", len(slugs), "docs/first-drafts/*/data.json", "count", "works with a First Drafts page", "works")
    put("first_drafts.greek_words", words, "outputs/firstdrafts/*/units.jsonl (n_tokens)", "int", "Greek words drafted")
    put("first_drafts.passages", units, "outputs/firstdrafts/*/units_meta.json", "int", "passages drafted", "passages")
    ff = REPO / "docs" / "findings" / "findings.json"
    put("findings.items", len(_json(ff)), "docs/findings/findings.json", "int", "findings catalogue items", "items")

    # LSJ-Gold (current release, from the published leaderboard)
    lb = _json(REPO / "docs" / "lsj-gold" / "leaderboard.json")
    put("lsjgold.version", lb["version"].split()[0], "docs/lsj-gold/leaderboard.json", "text", "LSJ-Gold version")
    put("lsjgold.loci", lb["n_loci"], "docs/lsj-gold/leaderboard.json", "int", "LSJ-Gold loci", "loci")
    put("lsjgold.authors", len(lb["loci_per_author"]), "docs/lsj-gold/leaderboard.json", "count", "LSJ-Gold authors", "authors")
    neural = [r for r in lb["rows"] if r["system"] != "dilemma"]
    put("lsjgold.neural_loci", min(r["scored"] for r in neural), "docs/lsj-gold/leaderboard.json", "int",
        "loci scored for every neural system", "loci")
    for r in lb["rows"]:
        put(f"lsjgold.score.{r['system']}", round(r["blind_pct"], 1), "docs/lsj-gold/leaderboard.json", "pct", f"LSJ-Gold {r['label']}")
        once = (r.get("by_lsj_citations") or {}).get("1")
        if once:
            put(f"lsjgold.once.{r['system']}", round(once["pct"], 1), "docs/lsj-gold/leaderboard.json", "pct",
                f"LSJ-Gold once-cited headwords, {r['label']}")

    # LS-Gold
    ls = _json(REPO / "docs" / "ls-gold" / "leaderboard.json")
    put("lsgold.loci", ls["n_loci"], "docs/ls-gold/leaderboard.json", "int", "LS-Gold loci", "loci")
    put("lsgold.authors", len(ls["loci_per_author"]), "docs/ls-gold/leaderboard.json", "count", "LS-Gold authors", "authors")
    lsq = GDM / "data" / "qc" / "lsgold"
    lsfile = next(lsq / f for f in ("ls_gold_v1_0.csv", "ls_gold_v0.csv") if (lsq / f).exists())   # the newest LS-Gold
    lsrows = _rows(lsfile)
    put("lsgold.quoted", sum(r["validation"] == "quoted" for r in lsrows), f"data/qc/lsgold/{lsfile.name}", "int", "LS-Gold loci by quoted form")
    put("lsgold.headwords", len({r["headword_key"] for r in lsrows}), f"data/qc/lsgold/{lsfile.name}", "int", "LS-Gold headwords", "headwords")
    for r in ls["rows"]:
        put(f"lsgold.score.{r['system']}", round(r["blind_pct"], 1), "docs/ls-gold/leaderboard.json", "pct", f"LS-Gold {r['label']}")

    # LSJ-Gold lexicon (newest release folder)
    lex = sorted(REPO.glob("release/lsj-gold-lexicon-*/stats.json"), key=lambda p: [int(x) for x in p.parent.name.split("-")[-1].split(".")])[-1]
    st = _json(lex)
    put("lexicon.version", lex.parent.name.split("-")[-1], lex.parent.relative_to(REPO).as_posix(), "text", "lexicon version")
    put("lexicon.pairs", st["lexicon_all_rows"], lex.relative_to(REPO).as_posix(), "int", "lexicon form-lemma pairs", "pairs")
    put("lexicon.headwords", st["lexicon_headwords"], lex.relative_to(REPO).as_posix(), "int", "lexicon headwords", "headwords")
    put("lexicon.review_pairs", st.get("review_pairs", 0), lex.relative_to(REPO).as_posix(), "int", "lexicon pairs set aside for review")

    # Phase 2 and Phase 3 lists
    put("punchlist.terms", len(_rows(GDM / "outputs" / "punch_list.csv")), "outputs/punch_list.csv", "int", "punch-list terms")
    put("fourway.lemmas", len(_rows(GDM / "outputs" / "four_way_classification.csv")), "outputs/four_way_classification.csv", "int",
        "lemmas in the four-way classification")
    v3 = _rows(GDM / "outputs" / "phase3" / "punch_list_v3.csv")
    tk = next(k for k in v3[0] if k in ("tier_v3", "v3_tier", "tier"))
    tiers: dict[str, int] = {}
    for r in v3:
        tiers[r[tk]] = tiers.get(r[tk], 0) + 1
    for t, n in sorted(tiers.items()):
        put(f"punchlist_v3.{t}", n, "outputs/phase3/punch_list_v3.csv", "int", f"punch list v3, tier {t}")
    put("punchlist_v3.total", len(v3), "outputs/phase3/punch_list_v3.csv", "int", "punch list v3, all terms")
    put("punchlist_v3.thin_all", tiers.get("thin", 0) + tiers.get("thin_contested", 0), "outputs/phase3/punch_list_v3.csv", "int",
        "front page: thin, one-sense entry")
    put("punchlist_v3.no_entry", tiers.get("real_no_perseus_lsj", 0) + tiers.get("real_contested", 0), "outputs/phase3/punch_list_v3.csv",
        "int", "front page: no entry in the digital LSJ")

    # Census
    cs = _json(REPO / "phase1" / "galen_ogl_census.json")["summary"]
    put("census.editions", cs["total_editions_listed"], "phase1/galen_ogl_census.json", "count", "census editions", "editions")
    put("census.works", cs["distinct_tlg_works"], "phase1/galen_ogl_census.json", "count", "census distinct works", "works")
    put("census.catalog_words", cs["total_wordcount_grc_editions"], "phase1/galen_ogl_census.json", "int", "census words (catalog)")
    put("census.file_words", cs["total_greek_words_in_files"], "phase1/galen_ogl_census.json", "int", "census Greek words in the files")
    put("census.catalog_errors", cs["catalog_errors_found"], "phase1/galen_ogl_census.json", "count", "catalog entries that disagree with their files", "catalog")
    return F


def displays(f: dict) -> list[str]:
    """How a value is written in prose. Only forms distinctive enough to search for."""
    v, k, noun = f["value"], f["kind"], f.get("noun", "")
    if k == "int":
        out = [f"{v:,}"] if v >= 1000 else ([f"{v} {noun}"] if noun else [])
        if v >= 10000 and noun == "loci":
            out.append(f"{v} loci")
        return out
    if k == "count":
        out = [f"{v} {noun}"] if noun else []
        if noun and v in WORDS:
            out += [f"{WORDS[v]} {noun}", f"{WORDS[v].capitalize()} {noun}"]
        return out
    if k == "pct":
        return [f"{v:.1f}%"]
    return []


def build() -> None:
    old = _json(FACTS) if FACTS.exists() else {"facts": {}, "history": {}}
    hist: dict[str, list] = old.get("history") or {k: list(v) for k, v in SEED_HISTORY.items()}
    for k, v in SEED_HISTORY.items():
        hist.setdefault(k, list(v))
    new = compute()
    today = date.today().isoformat()
    changed = []
    for k, f in new.items():
        prev = old.get("facts", {}).get(k)
        if prev and prev["value"] != f["value"]:
            hist.setdefault(k, []).append({"value": prev["value"], "until": today})
            changed.append((k, prev["value"], f["value"]))
    for k, f in new.items():
        f["display"] = displays(f)
    for k, hs in hist.items():
        kind = new.get(k, {}).get("kind", "int")
        for h in hs:
            h["display"] = displays({"value": h["value"], "kind": kind, "noun": new.get(k, {}).get("noun", "")})
    out = {"generated": today, "how": "galen-density-map/pipeline/facts.py build; never edit by hand", "facts": new, "history": hist}
    FACTS.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"facts.json: {len(new)} facts")
    for k, a, b in changed:
        print(f"   changed: {k} {a} -> {b}   (run facts.py check: every text with the old value fails until corrected)")


def load() -> dict[str, dict]:
    """For the site generators: the current facts, keyed by name."""
    return _json(FACTS)["facts"]


def fmt(key: str) -> str:
    f = load()[key]
    v = f["value"]
    return f"{v:,}" if f["kind"] == "int" else (f"{v:.1f}%" if f["kind"] == "pct" else str(v))


# ---------------------------------------------------------------- check

def _pattern(d: str) -> re.Pattern:
    e = re.escape(d)
    if d[0].isdigit():
        return re.compile(r"(?<![\d.,])" + e + r"(?![\d]|[.,]\d)")
    return re.compile(r"\b" + e + r"\b")


def stale_displays(data: dict) -> dict[str, list[tuple[str, str]]]:
    """display -> [(fact, current display)] for every old display that is not also a current one."""
    current = {d for f in data["facts"].values() for d in f.get("display", [])}
    out: dict[str, list] = {}
    for k, hs in data["history"].items():
        cur = data["facts"].get(k, {}).get("display", [])
        for h in hs:
            for i, d in enumerate(h.get("display", [])):
                if d not in current:
                    out.setdefault(d, []).append((k, cur[i] if i < len(cur) else ""))
    return out


# Phrases that always name a headline figure: every match must equal the current value (catches a number typed wrong
# from the start, which the history cannot). Each alternative is a tuple of fact keys, one per group; one must fit.
ANCHORS = [
    ("words of Greek", re.compile(r"(\d[\d,]{4,}) words of Greek"), [("first_drafts.greek_words",)]),
    ("works of Galen", re.compile(r"\b([A-Za-z]+|\d+) works of Galen\b"), [("first_drafts.works",)]),
    ("works with no complete English", re.compile(r"\b([A-Za-z]+|\d+) (?:Galenic )?works (?:of Galen )?with no complete English"), [("first_drafts.works",)]),
    ("loci over N authors", re.compile(r"(\d[\d,]{4,}) (?:relocated )?loci over (\d+) authors"),
     [("lsjgold.loci", "lsjgold.authors"), ("lsgold.loci", "lsgold.authors")]),
    ("findings items", re.compile(r"(?:catalogue of|[Pp]lus) (\d+) (?:items|things)"), [("findings.items",)]),
    ("census editions", re.compile(r"(\d+) editions (?:across|/) (\d+)"), [("census.editions", "census.works")]),
]
NUM_WORDS = {w: n for n, w in WORDS.items()}


def _num(s: str):
    s = s.strip()
    return NUM_WORDS.get(s.lower()) if s.isalpha() else int(s.replace(",", ""))


def anchor_hits(files: list[str], facts: dict, rules) -> list[tuple[str, int, str, str]]:
    hits = []
    for rel in files:
        try:
            text = _text_of(REPO / rel)
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for name, rx, alts in ANCHORS:
                for m in rx.finditer(line):
                    got = tuple(_num(g) for g in m.groups())
                    if None in got:
                        continue
                    if any(got == tuple(facts[k]["value"] for k in alt) for alt in alts if all(k in facts for k in alt)):
                        continue
                    if any(fnmatch.fnmatch(rel, g) and v == m.group(0) and ctx in line for g, v, ctx in rules):
                        continue
                    want = " or ".join("/".join(str(facts[k]["value"]) for k in alt) for alt in alts if all(k in facts for k in alt))
                    hits.append((rel, i, m.group(0), f"{name}: expected {want}"))
    return hits


def our_files() -> list[str]:
    """Text files that are public (on origin/master, or tracked here when this is the public checkout)."""
    try:
        names = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", "origin/master"],
                               capture_output=True, text=True, encoding="utf-8", check=True).stdout.split("\n")
    except Exception:
        names = []
    if not names or names == [""]:
        names = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, encoding="utf-8").stdout.split("\n")
    keep = []
    for n in names:
        n = n.strip()
        if not n or not n.endswith(TEXT) or any(fnmatch.fnmatch(n, e) for e in EXEMPT):
            continue
        if (REPO / n).exists():
            keep.append(n)
    return keep


def allow_rules() -> list[tuple[str, str, str]]:
    if not ALLOW.exists():
        return []
    rules = []
    for line in ALLOW.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rules.append((parts[0], parts[1], parts[2]))
    return rules


def _text_of(path: Path) -> str:
    t = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json" and "issue_backups" in path.as_posix():
        d = json.loads(t)
        return d.get("body") or ""
    return t


def scan(files: list[str], stale: dict, rules) -> list[tuple[str, int, str, str, list]]:
    pats = {d: _pattern(d) for d in stale}
    hits = []
    for rel in files:
        p = REPO / rel
        try:
            text = _text_of(p)
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for d, pat in pats.items():
                if pat.search(line):
                    if any(fnmatch.fnmatch(rel, g) and d == v and ctx in line for g, v, ctx in rules):
                        continue
                    hits.append((rel, i, d, line.strip(), stale[d]))
    return hits


def check() -> int:
    data = _json(FACTS)
    stale = stale_displays(data)
    rules = allow_rules()
    ext = _json(EXTERNAL) if EXTERNAL.exists() else {"outgoing": [], "posted": []}
    files = our_files()
    outgoing = [o["file"] for o in ext.get("outgoing", []) if (REPO / o["file"]).exists()]
    hits = scan(files + outgoing, stale, rules)
    bad = 0
    if hits:
        print(f"OLD VALUES in our text ({len(hits)}): correct them (facts.py fix), or, if the line is history on purpose, add it to facts_allow.tsv")
        for rel, i, d, line, facts in hits:
            print(f"  {rel}:{i}  '{d}' is an old value of {', '.join(k for k, _ in facts)} (now {', '.join(c or '?' for _, c in facts)})")
            print(f"      {line[:220]}")
        bad = 1
    wrong = anchor_hits(files + outgoing, data["facts"], rules)
    if wrong:
        print(f"\nWRONG FIGURES in our text ({len(wrong)}): a phrase that names a headline figure does not match facts.json")
        for rel, i, phrase, why in wrong:
            print(f"  {rel}:{i}  '{phrase}'  ({why})")
        bad = 1
    posted_hits = []
    for e in ext.get("posted", []):
        cps = [c for c in e.get("copies", []) if (REPO / c).exists()]
        for rel, i, d, line, facts in scan(cps, stale, rules):
            posted_hits.append((e, rel, d, facts))
    # a posted text that names the version its figures belong to ("labelled" in facts_external.json) is superseded,
    # not wrong: it is listed apart, once, so the old values in it are not mistaken for errors
    stale_posts = [h for h in posted_hits if not h[0].get("labelled")]
    labelled = {(h[0]["where"], h[0].get("labelled")) for h in posted_hits if h[0].get("labelled")}
    if stale_posts:
        print(f"\nPOSTED ELSEWHERE with an old value (correct by hand, then refresh the local copy):")
        for e, rel, d, facts in stale_posts:
            print(f"  {e['where']} {e.get('url', '')}: '{d}' (now {', '.join(c or '?' for _, c in facts)})  [copy: {rel}]")
    if labelled:
        print("\nPOSTED, SUPERSEDED (the text names the version its figures are for; a short note when convenient, no correction needed):")
        for where, lab in sorted(labelled):
            print(f"  {where}: figures for {lab}")
    posted_hits = stale_posts
    print(f"\nchecked {len(files)} public text files and {len(outgoing)} outgoing drafts against {len(stale)} old values; "
          f"{len(hits)} in our text, {len(posted_hits)} in posted places; {len(ANCHORS)} figure phrases, {len(wrong)} wrong")
    return bad


def fix(write: bool) -> None:
    data = _json(FACTS)
    stale = stale_displays(data)
    hits = scan(our_files(), stale, allow_rules())
    by_file: dict[str, list] = {}
    for h in hits:
        by_file.setdefault(h[0], []).append(h)
    for rel, hs in by_file.items():
        p = REPO / rel
        lines = p.read_text(encoding="utf-8").split("\n")
        for _, i, d, _, facts in hs:
            news = {c for _, c in facts if c}
            if len(news) != 1:
                print(f"  {rel}:{i} '{d}' is ambiguous ({facts}); fix by hand")
                continue
            new = news.pop()
            before = lines[i - 1]
            lines[i - 1] = _pattern(d).sub(new, before)
            print(f"  {rel}:{i}: '{d}' -> '{new}'")
        if write:
            p.write_text("\n".join(lines), encoding="utf-8")
    print("written" if write else "(dry run; --write to apply)")


def mentions() -> None:
    data = _json(FACTS)
    ext = _json(EXTERNAL) if EXTERNAL.exists() else {"outgoing": [], "posted": []}
    files = our_files() + [o["file"] for o in ext.get("outgoing", []) if (REPO / o["file"]).exists()]
    posted = {c: e for e in ext.get("posted", []) for c in e.get("copies", []) if (REPO / c).exists()}
    lines = ["# Where each headline figure appears", "",
             f"Generated {date.today().isoformat()} by `galen-density-map/pipeline/facts.py mentions` from `facts.json`; do not edit.",
             "When a figure changes, `facts.py check` fails on every place below that still has the old value.", ""]
    texts = {}
    for rel in files + list(posted):
        try:
            texts[rel] = _text_of(REPO / rel).splitlines()
        except Exception:
            pass
    for k, f in data["facts"].items():
        if not f.get("display"):
            continue
        pats = [_pattern(d) for d in f["display"]]
        here = [f"{rel}:{i}" for rel, ls in texts.items() if rel not in posted for i, l in enumerate(ls, 1) if any(p.search(l) for p in pats)]
        there = sorted({f"{posted[rel]['where']} ({rel})" for rel, ls in texts.items() if rel in posted for l in ls if any(p.search(l) for p in pats)})
        lines.append(f"## `{k}` = {', '.join(f['display'])}  ({f['label']}; from `{f['source']}`)")
        lines.append("")
        lines += [f"- {h}" for h in here] or ["- (not mentioned in our text)"]
        lines += [f"- posted: {t}" for t in there]
        lines.append("")
    MENTIONS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", MENTIONS.relative_to(REPO))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "build":
        build()
    elif cmd == "check":
        sys.exit(check())
    elif cmd == "fix":
        fix("--write" in sys.argv)
    elif cmd == "mentions":
        mentions()
    else:
        print(__doc__)
        sys.exit(2)
