"""LS-Gold -- lemmatize the project's Latin token streams with every contestant system, PRE-TOKENISED.

Input: data/latin_corpus/tokens/<stem>.jsonl ({"i", "surface", "unit"}, document order). The token list IS the input:
no system re-tokenises; exactly one lemma per input token, same count, same order.
Output: data/latin_corpus/caches/<system>/<stem>.jsonl, lines {"i", "surface", "lemma"}; the lemma is as the system
prints it (the scorer normalises with latnorm.key). Written to a .part file and renamed when complete; an existing
cache with the right line count is skipped (resumable).

Systems
  stanza_ittb / stanza_perseus / stanza_proiel / stanza_llct
        stanza.Pipeline('la', package=P, processors='tokenize,pos,lemma', tokenize_pretokenized=True, use_gpu=False);
        the stream has no sentence boundaries, so it is cut into pseudo-sentences of <= 60 tokens; each word's lemma
        is mapped back to its token by position (count asserted per batch).
  latincy_lg
        spaCy la_core_web_lg (LatinCy 3.9.x); Doc(nlp.vocab, words=chunk) of ~200 words, then every pipe except
        parser/ner (the lemmatizers sit before them). LatinCy's first pipe, enclitic_splitter, splits -que/-ne/-ve
        into their own tokens ('virumque' -> 'virum' + 'que'); the split keeps character offsets, so every output token
        is mapped back to the input word containing its first character and the word takes the lemma of its first
        piece (the host word) -- the same host-word rule the scorer documents for enclitics.
  cltk  cltk.lemmatize.lat.LatinBackoffLemmatizer().lemmatize(tokens) -> (token, lemma) pairs, chunks of 200 tokens
        (its backoff chain is context-sensitive only within the list it is given). Needs lat_models_cltk in
        ~/cltk_data (FetchCorpus('lat').import_corpus('lat_models_cltk')).
  collatinus_first / whitaker_first
        context-free lexicon-first BASELINES: the first lemma the oracle route returns for the surface (Oracle.first:
        the first analysis pycollatinus / whitakers_words yields, as printed). They are the oracle's own first choice
        and therefore partly circular with the oracle validation; they are reported as baselines, not contestants.

A system whose model fails to load is reported and skipped, never fatal.

CLI: python -X utf8 -I pipeline/lsgold/latin_caches.py [--systems a,b] [--stems s1,s2] [--threads N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROOT = HERE.parents[1]
TOKENS = ROOT / "data" / "latin_corpus" / "tokens"
CACHES = ROOT / "data" / "latin_corpus" / "caches"
ORACLE_CACHE = ROOT / "data" / "latin_corpus" / "oracle_cache.jsonl"

STANZA = {"stanza_ittb": "ittb", "stanza_perseus": "perseus", "stanza_proiel": "proiel", "stanza_llct": "llct"}
SYSTEMS = list(STANZA) + ["latincy_lg", "cltk", "collatinus_first", "whitaker_first"]


def read_tokens(path: Path) -> list[tuple[int, str]]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                out.append((int(r["i"]), r["surface"]))
    return out


def chunks(seq, n):
    for k in range(0, len(seq), n):
        yield seq[k:k + n]


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


# ---------------------------------------------------------------- system runners: build() -> fn(list[str]) -> list[str]
def build_stanza(pkg: str):
    import stanza
    try:  # parallel runs race on stanza's resources.json; the models are usually present already
        stanza.download("la", package=pkg, processors="tokenize,pos,lemma", verbose=False)
    except Exception as e:  # noqa: BLE001
        print(f"  stanza.download({pkg}) failed ({type(e).__name__}); trying the installed model", flush=True)
    nlp = stanza.Pipeline("la", package=pkg, processors="tokenize,pos,lemma", tokenize_pretokenized=True,
                          use_gpu=False, download_method=None, verbose=False)

    def run(words: list[str]) -> list[str]:
        out: list[str] = []
        sents = list(chunks(words, 60))
        for batch in chunks(sents, 50):  # 3,000 tokens per call
            doc = nlp(batch)
            got = [w.lemma if w.lemma is not None else "" for s in doc.sentences for w in s.words]
            if len(got) != sum(len(s) for s in batch):
                raise RuntimeError(f"stanza returned {len(got)} words for {sum(len(s) for s in batch)} tokens")
            out.extend(got)
        return out
    return run


def build_latincy(model: str = "la_core_web_lg"):
    import spacy
    from spacy.tokens import Doc
    nlp = spacy.load(model, exclude=["parser", "ner"])
    pipes = list(nlp.pipeline)

    def run(words: list[str]) -> list[str]:
        out: list[str] = []
        for chunk in chunks(words, 200):
            doc = Doc(nlp.vocab, words=chunk)
            for _, proc in pipes:
                doc = proc(doc)
            starts, pos = [], 0
            for w in chunk:
                starts.append(pos)
                pos += len(w) + 1
            lem = [None] * len(chunk)
            j = 0
            for t in doc:
                while j + 1 < len(chunk) and t.idx >= starts[j + 1]:
                    j += 1
                if lem[j] is None:
                    lem[j] = t.lemma_
            if doc.text.rstrip() != " ".join(chunk) or any(x is None for x in lem):
                raise RuntimeError("latincy changed the text; cannot align tokens")
            out.extend(lem)
        return out
    return run


def build_cltk():
    from cltk.lemmatize.lat import LatinBackoffLemmatizer
    lem = LatinBackoffLemmatizer()

    def run(words: list[str]) -> list[str]:
        out: list[str] = []
        for chunk in chunks(words, 200):
            pairs = lem.lemmatize(list(chunk))
            if len(pairs) != len(chunk):
                raise RuntimeError("cltk returned a different token count")
            out.extend("" if p[1] is None else str(p[1]) for p in pairs)
        return out
    return run


def build_first(route: str):
    from oracle import Oracle
    o = Oracle(ORACLE_CACHE)
    memo: dict[str, str] = {}

    def run(words: list[str]) -> list[str]:
        out = []
        for w in words:
            s = w.lower()
            if s not in memo:
                memo[s] = o.first(s).get(route, "")
            out.append(memo[s])
        return out
    return run


def builder(system: str):
    if system in STANZA:
        return lambda: build_stanza(STANZA[system])
    if system == "latincy_lg":
        return build_latincy
    if system == "cltk":
        return build_cltk
    if system == "collatinus_first":
        return lambda: build_first("collatinus")
    if system == "whitaker_first":
        return lambda: build_first("whitaker")
    raise KeyError(system)


# ---------------------------------------------------------------- driver
def run_system(system: str, stems: list[str]) -> dict:
    rep = {"system": system, "loaded": False, "error": None, "tokens": 0, "seconds": 0.0, "files": 0, "skipped": 0}
    todo = []
    for stem in stems:
        src = TOKENS / f"{stem}.jsonl"
        dst = CACHES / system / f"{stem}.jsonl"
        n = count_lines(src)
        if dst.exists() and count_lines(dst) == n:
            rep["skipped"] += 1
            print(f"[{system}] {stem}: cached ({n} lines), skip", flush=True)
            continue
        todo.append((stem, src, dst))  # tokens are read per file below (keeps memory flat on big runs)
    if not todo:
        rep["loaded"] = None
        return rep
    t = time.time()
    try:
        fn = builder(system)()
    except Exception as e:  # noqa: BLE001
        rep["error"] = f"{type(e).__name__}: {e}"
        print(f"[{system}] LOAD FAILED: {rep['error']}", flush=True)
        traceback.print_exc()
        return rep
    rep["loaded"] = True
    rep["load_seconds"] = round(time.time() - t, 1)
    print(f"[{system}] loaded in {rep['load_seconds']}s", flush=True)
    for stem, src, dst in todo:
        try:
            toks = read_tokens(src)
        except Exception as e:  # noqa: BLE001 -- e.g. a token file still being written by the tokenizer
            print(f"[{system}] {stem}: unreadable token file, skipped ({type(e).__name__}: {e})", flush=True)
            continue
        if dst.exists() and count_lines(dst) == len(toks):
            continue
        words = [s for _, s in toks]
        t = time.time()
        try:
            lemmas = fn(words)
            if len(lemmas) != len(words):
                raise RuntimeError(f"{len(lemmas)} lemmas for {len(words)} tokens")
        except Exception as e:  # noqa: BLE001
            print(f"[{system}] {stem}: FAILED {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            rep.setdefault("file_errors", {})[stem] = repr(e)
            continue
        dt = time.time() - t
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_suffix(".jsonl.part")
        with part.open("w", encoding="utf-8") as fh:
            for (i, s), lem in zip(toks, lemmas):
                fh.write(json.dumps({"i": i, "surface": s, "lemma": lem}, ensure_ascii=False) + "\n")
        os.replace(part, dst)
        rep["tokens"] += len(words)
        rep["seconds"] += dt
        rep["files"] += 1
        print(f"[{system}] {stem}: {len(words)} tokens in {dt:.1f}s ({len(words) / dt if dt else 0:.0f} tok/s)",
              flush=True)
    if rep["seconds"]:
        rep["tok_per_s"] = round(rep["tokens"] / rep["seconds"])
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default=",".join(SYSTEMS))
    ap.add_argument("--stems", default="")
    ap.add_argument("--threads", type=int, default=0, help="torch threads (0 = library default)")
    a = ap.parse_args()
    if a.threads:
        try:
            import torch
            torch.set_num_threads(a.threads)
        except Exception:  # noqa: BLE001
            pass
    systems = [s.strip() for s in a.systems.split(",") if s.strip()]
    bad = [s for s in systems if s not in SYSTEMS]
    if bad:
        sys.exit(f"unknown systems {bad}; known {SYSTEMS}")
    stems = [s.strip() for s in a.stems.split(",") if s.strip()] or sorted(p.stem for p in TOKENS.glob("*.jsonl"))
    reports = []
    for system in systems:
        reports.append(run_system(system, stems))
    print("SUMMARY")
    for r in reports:
        state = "cached" if r["loaded"] is None else ("ok" if r["loaded"] else "NOT LOADED")
        print(f"  {r['system']:17s} {state:10s} files {r['files']} (+{r['skipped']} cached) tokens {r['tokens']}"
              f" {r.get('tok_per_s', '-')} tok/s" + (f"  error: {r['error']}" if r["error"] else ""))


if __name__ == "__main__":
    main()
