"""LS-Gold, stage 1a — index every held Latin TEI edition by CTS locator and freeze its token stream.

For each data/latin_corpus/raw_xml/<stem>.xml (PerseusDL/canonical-latinLit):
  * units in document order, keyed the way Lewis & Short's URNs locate them: nested textpart divs joined by ':'
    (Livy 39:6:7, Cicero Verr. 2:4:35), book div + <l n> for verse (Aeneid 1:5, bare line numbers when there is no
    book div), and `milestone unit="section"` inside a textpart (Pliny NH 37:14: book div, section milestone; the
    chapter div is not what L&S cites, so a milestone unit is keyed by the nearest BOOK-level ancestor path and the
    milestone's n; the chapter path is kept as an alias so either locator form resolves);
  * the token stream: every TOKEN_RE word of the body text in document order, notes/apparatus/heads/speakers
    dropped, numbered i from 0, written to data/latin_corpus/tokens/<stem>.jsonl as {"i","surface","unit"}.
    This stream IS the project's Latin tokenisation: the gold's token_index points into it and every scored system is
    run on it pre-tokenised, so no alignment step exists in the Latin benchmark.
  * data/latin_corpus/units/<stem>.json: {"units": [[key, first_i, n_tokens], ...], "aliases": {chapter_key: [keys]}}

Run (.venv): python -X utf8 -I pipeline/lsgold/tokenize_editions.py [--only stem,stem]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from latnorm import tokens as latin_tokens  # noqa: E402

GDM = HERE.parent.parent
CORPUS = GDM / "data" / "latin_corpus"
SKIP = ("note", "bibl", "ref", "head", "speaker", "label", "app", "rdg", "wit", "teiHeader", "front", "back", "figDesc", "del")
LSKIP = ("note", "bibl", "ref", "app", "rdg", "wit", "del")
CONTAINERS = ("part", "volume", "decade", "index", "pentad", "work")


def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def index_edition(xml_path: Path) -> tuple[list[tuple[str, list[str]]], dict[str, list[str]]]:
    parser = etree.XMLParser(recover=True, huge_tree=True, remove_comments=True, remove_pis=True)
    tree = etree.parse(str(xml_path), parser)
    body = tree.xpath("//*[local-name()='body']")
    if not body:
        return [], {}
    segs: list[tuple[str, int, str]] = []       # (key, uid, text) in document order
    aliases: dict[str, set[str]] = {}
    state = {"uid": 0, "ms": None}               # ms: (key, uid) of the current section milestone, or None
    lines: set[int] = set()

    def new_uid() -> int:
        state["uid"] += 1
        return state["uid"]

    def emit(unit, text):
        if unit is not None and text and text.strip():
            segs.append((unit[0], unit[1], text))

    def line_text(el) -> str:
        parts = [el.text or ""]
        for g in el:
            if local(g.tag) not in LSKIP:
                parts.append("".join(g.itertext()))
            parts.append(g.tail or "")
        return " ".join(parts)

    def cur(ctx):
        return state["ms"] if state["ms"] is not None else ctx

    def walk(el, path: list[str], book_path: list[str], ctx, has_ms: bool):
        emit(cur(ctx) if has_ms else ctx, el.text)
        for ch in el:
            t = local(ch.tag)
            if t == "milestone":
                if has_ms and ch.get("unit") == "section" and ch.get("n"):
                    k = ":".join(book_path + [ch.get("n")])
                    state["ms"] = (k, new_uid())
                    if path and path != book_path:
                        aliases.setdefault(":".join(path), set()).add(k)
            elif t in SKIP:
                pass
            elif t == "div" and ch.get("type") == "textpart" and (ch.get("subtype") or "").lower() in CONTAINERS:
                # a decade/volume/index wrapper (Livy lat2: part > book > chapter > section) is not part of the L&S locator
                walk(ch, path, book_path, ctx, has_ms)
            elif t == "div" and ch.get("type") == "textpart" and ch.get("n"):
                sub = (ch.get("subtype") or "").lower()
                p = path + [ch.get("n")]
                ms_below = any(local(d.tag) == "milestone" and d.get("unit") == "section" for d in ch.iter())
                # the book-level path for milestone keys: a chapter/section div that carries milestones is skipped
                bp = p if (sub in ("book", "actio", "part", "volume", "liber") or not ms_below or not path) else book_path
                if ms_below and sub not in ("book", "actio", "part", "volume", "liber") and path:
                    bp = book_path
                saved = state["ms"]
                if not ms_below:
                    state["ms"] = None
                walk(ch, p, bp if ms_below else p, (":".join(p), new_uid()), ms_below)
                if not ms_below:
                    state["ms"] = saved
            elif t == "l" and ch.get("n") and not has_ms:
                key = ":".join(path + [ch.get("n")]) if path else ch.get("n")
                u = new_uid()
                lines.add(u)
                emit((key, u), line_text(ch) or " ")
            elif t == "l" and not ch.get("n") and not has_ms:
                emit(ctx, line_text(ch))
            else:
                walk(ch, path, book_path, ctx, has_ms)
            emit(cur(ctx) if has_ms else ctx, ch.tail)

    walk(body[0], [], [], None, False)

    units: list[tuple[str, int, list[str]]] = []
    for key, uid, text in segs:
        if units and units[-1][1] == uid:
            units[-1][2].append(text)
        else:
            units.append((key, uid, [text]))
    owner: dict[str, int] = {}
    n_dup: Counter = Counter()
    uid_key: dict[int, str] = {}
    out: list[tuple[str, list[str]]] = []
    for key, uid, texts in units:
        toks = latin_tokens(" ".join(texts))
        if uid not in uid_key:
            if key in owner and owner[key] != uid:
                n_dup[key] += 1
                uid_key[uid] = f"{key}@{n_dup[key]}"
            else:
                owner[key] = uid
                uid_key[uid] = key
        if toks or uid in lines:
            out.append((uid_key[uid], toks))
    return out, {k: sorted(v) for k, v in aliases.items()}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-existing", action="store_true", help="leave editions that already have a units file alone")
    a = ap.parse_args()
    (CORPUS / "tokens").mkdir(parents=True, exist_ok=True)
    (CORPUS / "units").mkdir(parents=True, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    t0 = time.time()
    summary = {}
    for x in sorted((CORPUS / "raw_xml").glob("*.xml")):
        stem = x.stem
        if only and stem not in only:
            continue
        if a.skip_existing and (CORPUS / "units" / f"{stem}.json").exists() and (CORPUS / "tokens" / f"{stem}.jsonl").exists():
            continue
        passages, aliases = index_edition(x)
        i = 0
        units_out = []
        with (CORPUS / "tokens" / f"{stem}.jsonl").open("w", encoding="utf-8") as fh:
            for key, toks in passages:
                units_out.append([key, i, len(toks)])
                for s in toks:
                    fh.write(json.dumps({"i": i, "surface": s, "unit": key}, ensure_ascii=False) + "\n")
                    i += 1
        (CORPUS / "units" / f"{stem}.json").write_text(json.dumps({"units": units_out, "aliases": aliases}, ensure_ascii=False), encoding="utf-8")
        summary[stem] = {"units": len(units_out), "tokens": i, "aliases": len(aliases)}
        print(f"{stem}: {len(units_out)} units, {i} tokens, {len(aliases)} chapter aliases ({time.time()-t0:.0f}s)", flush=True)
    sp = CORPUS / "tokenize_summary.json"
    old = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    old.update(summary)
    sp.write_text(json.dumps(old, indent=1), encoding="utf-8")
    print(f"done {len(summary)} editions, {sum(v['tokens'] for v in summary.values()):,} tokens")


if __name__ == "__main__":
    main()
