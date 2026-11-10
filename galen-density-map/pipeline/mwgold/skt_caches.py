"""MW-Gold — lemmatize the project's Sanskrit token streams with every contestant system, PRE-SEGMENTED.

Input: data/sanskrit_corpus/tokens/<stem>.jsonl (DCS words, document order, {"i", "surface", "unsandhied", ...}) and
units/<stem>.json (sentence boundaries). The DCS word list IS the input: a system gets the sandhi-resolved words of
one sentence and must return exactly one lemma per word, same order; a system that re-segments is mapped back by
position and a count mismatch leaves the sentence without lemmas (counted, reported).
Output: data/sanskrit_corpus/caches/<system>/<stem>.jsonl, lines {"i", "surface", "lemma"} (lemma as the system
prints it, IAST; the scorer normalises with sktnorm.key); .part file renamed when complete; resumable per file.

Systems
  stanza_sa     stanza.Pipeline('sa', processors='tokenize,pos,lemma', tokenize_pretokenized=True); package vedic_nocharlm
                (UD_Sanskrit-Vedic). Sentences are the DCS sentences.
  vidyut_cheda  vidyut.cheda.Chedaka on the sentence's unsandhied words joined by spaces (SLP1 in, SLP1 out); the
                segmenter may split or merge words, so its tokens are mapped back to input words by character offsets
                of the concatenated text; an input word takes the lemma of the first output token starting inside it.
  byt5          chronbmm/sanskrit5-multitask (ByT5-Sanskrit, Apache 2.0) run locally on CPU in `lemma` mode ("L " prefix,
                as the authors' run_inf.py): input is the unsandhied sentence, output the lemmas joined by '_' (smoke
                test 2026-11-09: ~1 s a sentence on 16 CPU threads, identical output for sandhied and unsandhied
                input); mapped by position when the count
                equals the word count, else the sentence is left without lemmas. --sentences FILE restricts the run to
                the sentence ids listed (the gold sentences), because a 582M-parameter model on CPU cannot cover 1.2M
                tokens in a day; the restriction is recorded in the cache header line.
  vidyut_first  context-free BASELINE: the first lemma vidyut-kosha returns for the unsandhied word (skt_oracle.Oracle
                .first); circular with the `vidyut` validation route, printed in italics on the leaderboard.

CLI: python -X utf8 -I pipeline/mwgold/skt_caches.py --systems stanza_sa,vidyut_cheda,vidyut_first [--stems a,b]
     python -X utf8 -I pipeline/mwgold/skt_caches.py --systems byt5 --sentences data/qc/mwgold/gold_sentences.json
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
from sktnorm import iast_to_slp1, slp1_to_iast  # noqa: E402

ROOT = HERE.parents[1]
CORPUS = ROOT / "data" / "sanskrit_corpus"
TOKENS = CORPUS / "tokens"
UNITS = CORPUS / "units"
CACHES = CORPUS / "caches"
ORACLE_CACHE = CORPUS / "oracle_cache_vidyut.jsonl"
SYSTEMS = ["stanza_sa", "vidyut_cheda", "byt5", "vidyut_first"]


def read_text(stem: str):
    toks = []
    with (TOKENS / f"{stem}.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                toks.append(json.loads(line))
    units = json.loads((UNITS / f"{stem}.json").read_text(encoding="utf-8"))
    return toks, units["sentences"]


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as fh:
        return sum(1 for l in fh if l.strip() and not l.startswith("#"))


# ---------------------------------------------------------------- runners: build() -> fn(list[list[str]] sentences of words) -> list[list[str|None]]
def build_stanza():
    import stanza
    try:
        stanza.download("sa", verbose=False)
    except Exception as e:  # noqa: BLE001
        print(f"  stanza.download(sa) failed ({type(e).__name__}); trying the installed model", flush=True)
    nlp = stanza.Pipeline("sa", processors="tokenize,pos,lemma", tokenize_pretokenized=True, use_gpu=False, download_method=None, verbose=False)

    def run(sents):
        out = []
        for k in range(0, len(sents), 200):
            batch = sents[k:k + 200]
            doc = nlp(batch)
            got = [[w.lemma if w.lemma is not None else "" for w in s.words] for s in doc.sentences]
            if len(got) != len(batch) or any(len(g) != len(b) for g, b in zip(got, batch)):
                raise RuntimeError("stanza changed the token count")
            out.extend(got)
        return out
    return run


def _cheda_norm(x: str) -> str:
    """SLP1 comparison form for aligning cheda's output to the input words: visarga and final s/r, anusvāra and m."""
    return x.replace("H", "s").replace("M", "m")


def _cheda_input(w: str) -> str:
    """vidyut-cheda accepts ASCII SLP1 only and raises NonAsciiText on the Vedic letters DCS prints (ṁ, m̐, ḻ, ḻh) and on
    accent marks: map them to their classical equivalents (ṃ, ḍ, ḍh), transliterate, drop whatever is still not ASCII."""
    w = w.replace("m̐", "ṃ").replace("ṁ", "ṃ").replace("ḻh", "ḍh").replace("ḻ", "ḍ")
    x = iast_to_slp1(w)
    return "".join(ch for ch in x if ord(ch) < 128) or "a"


def build_cheda():
    """vidyut-cheda re-segments its input (akalpaH -> ak + alpas) and prints pausa forms (malAH -> malAs), so its
    tokens are mapped back to the input words by a character alignment of the concatenated SLP1 strings (difflib on
    _cheda_norm'd text, spaces removed): each output token is placed at the input position its first character aligns
    to, and an input word takes the lemma of the first output token placed inside it; a word with no token placed in
    it takes the lemma of the token covering its first character. (Fixed 2026-11-09 after the first cache mapped by
    exact substring search and put lemmas on the wrong words: that cache was discarded, not scored.)"""
    import bisect
    import difflib
    from vidyut.cheda import Chedaka
    c = Chedaka(str(CORPUS / "vidyut_data"))

    def run(sents):
        out = []
        for words in sents:
            slp = [_cheda_input(w) for w in words]
            lem = [None] * len(words)
            try:
                toks = c.run(" ".join(slp))
            except Exception:  # noqa: BLE001
                out.append(lem)
                continue
            A = "".join(_cheda_norm(w) for w in slp)
            starts, pos = [], 0
            for w in slp:
                starts.append(pos)
                pos += len(w)
            B_parts = [_cheda_norm(t.text) for t in toks]
            B = "".join(B_parts)
            if not A or not B:
                out.append(lem)
                continue
            b_starts, pos = [], 0
            for b in B_parts:
                b_starts.append(pos)
                pos += len(b)
            sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
            blocks = [m for m in sm.get_matching_blocks() if m.size]
            b2a = {}
            for m in blocks:
                for k in range(m.size):
                    b2a[m.b + k] = m.a + k
            placed = []   # (input position, token index)
            for ti, bs in enumerate(b_starts):
                ap = b2a.get(bs)
                if ap is None:   # first char unmatched: the next matched char of this token
                    for k in range(bs, bs + len(B_parts[ti])):
                        if k in b2a:
                            ap = b2a[k]
                            break
                if ap is not None:
                    placed.append((ap, ti))
            placed.sort()
            for ap, ti in placed:
                wj = bisect.bisect_right(starts, ap) - 1
                if 0 <= wj < len(words) and lem[wj] is None:
                    lem[wj] = slp1_to_iast(toks[ti].lemma) if toks[ti].lemma else ""
            for wj in range(len(words)):
                if lem[wj] is None and placed:
                    prev = [ti for ap, ti in placed if ap <= starts[wj]]
                    if prev:
                        t = toks[prev[-1]]
                        lem[wj] = slp1_to_iast(t.lemma) if t.lemma else ""
            out.append(lem)
        return out
    return run


def build_byt5(batch_size: int = 8):
    import torch
    from transformers import AutoTokenizer, T5ForConditionalGeneration
    name = "chronbmm/sanskrit5-multitask"
    tok = AutoTokenizer.from_pretrained(name)
    # bfloat16 halves the committed memory (the float32 load failed on this machine with "paging file too small");
    # greedy decoding in bf16 can differ from float32 on rare tokens: recorded in the README
    model = T5ForConditionalGeneration.from_pretrained(name, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True)
    model.eval()
    torch.set_num_threads(max(1, os.cpu_count() or 1))

    def run(sents):
        out = []
        for k in range(0, len(sents), batch_size):
            batch = sents[k:k + batch_size]
            inputs = ["L " + " ".join(words) for words in batch]       # the analyzers' lemma-mode prefix
            enc = tok(inputs, return_tensors="pt", padding=True, truncation=True, max_length=512)
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=512, num_beams=1)
            dec = tok.batch_decode(gen, skip_special_tokens=True)
            for words, d in zip(batch, dec):
                # lemma mode prints the lemmas joined by '_' (the analyzers' postprocess replaces '_' with ' ')
                lem = [x for x in d.strip().strip("_").split("_") if x != ""] if "_" in d else d.strip().split()
                out.append(lem if len(lem) == len(words) else [None] * len(words))
        return out
    return run


def build_first():
    from skt_oracle import Oracle
    o = Oracle(ORACLE_CACHE)

    def run(sents):
        return [[o.first(w) for w in words] for words in sents]
    return run


def builder(system: str):
    return {"stanza_sa": build_stanza, "vidyut_cheda": build_cheda, "byt5": build_byt5, "vidyut_first": build_first}[system]


# ---------------------------------------------------------------- driver
def run_system(system: str, stems: list[str], sentence_filter: dict | None) -> dict:
    rep = {"system": system, "loaded": False, "error": None, "tokens": 0, "seconds": 0.0, "files": 0, "skipped": 0, "unaligned_sentences": 0}
    todo = []
    for stem in stems:
        sents = json.loads((UNITS / f"{stem}.json").read_text(encoding="utf-8"))["sentences"]
        keep = sents
        if sentence_filter is not None:
            ids = set(sentence_filter.get(stem, []))
            keep = [s for s in sents if s[0] in ids]
            if not keep:
                continue
        dst = CACHES / system / f"{stem}.jsonl"
        n_expected = sum(s[4] for s in keep)
        if dst.exists() and count_lines(dst) == n_expected:
            rep["skipped"] += 1
            print(f"[{system}] {stem}: cached ({n_expected} lines), skip", flush=True)
            continue
        todo.append((stem, keep, dst))   # tokens are read per file below (one text in memory at a time)
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
    for stem, keep, dst in todo:
        toks, _ = read_text(stem)
        words = [[toks[s[3] + j]["unsandhied"] or toks[s[3] + j]["surface"] for j in range(s[4])] for s in keep]
        t = time.time()
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_suffix(".jsonl.part")
        appending = dst.exists() and sentence_filter is not None
        if appending:
            part.write_text(dst.read_text(encoding="utf-8"), encoding="utf-8")
        n_tok = 0
        n_un = 0
        try:
            with part.open("a" if appending else "w", encoding="utf-8") as fh:
                if sentence_filter is not None:
                    fh.write(json.dumps({"#": "restricted to the listed sentences", "n_sentences": len(keep)}) + "\n")
                step = 500 if system != "byt5" else 64
                for k in range(0, len(keep), step):
                    chunk_s = keep[k:k + step]
                    chunk_w = words[k:k + step]
                    lemmas = fn(chunk_w)
                    for s, ws, ls in zip(chunk_s, chunk_w, lemmas):
                        if all(l is None for l in ls):
                            n_un += 1
                        for j, (w, l) in enumerate(zip(ws, ls)):
                            fh.write(json.dumps({"i": toks[s[3] + j]["i"], "surface": toks[s[3] + j]["surface"], "lemma": l if l is not None else ""}, ensure_ascii=False) + "\n")
                            n_tok += 1
                    if system == "byt5":
                        print(f"[{system}] {stem}: {min(k + step, len(keep))}/{len(keep)} sentences ({time.time()-t:.0f}s)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[{system}] {stem}: FAILED {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            rep.setdefault("file_errors", {})[stem] = repr(e)
            continue
        os.replace(part, dst)
        dt = time.time() - t
        rep["tokens"] += n_tok
        rep["seconds"] += dt
        rep["files"] += 1
        rep["unaligned_sentences"] += n_un
        print(f"[{system}] {stem}: {n_tok} tokens, {len(keep)} sentences ({n_un} without lemmas) in {dt:.1f}s ({n_tok / dt if dt else 0:.0f} tok/s)", flush=True)
    if rep["seconds"]:
        rep["tok_per_s"] = round(rep["tokens"] / rep["seconds"])
    return rep


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="stanza_sa,vidyut_cheda,vidyut_first")
    ap.add_argument("--stems", default="")
    ap.add_argument("--sentences", type=Path, default=None, help="JSON {stem: [sent_id, ...]} restricting the run (byt5)")
    a = ap.parse_args()
    systems = [s for s in a.systems.split(",") if s]
    bad = [s for s in systems if s not in SYSTEMS]
    if bad:
        sys.exit(f"unknown systems {bad}; known {SYSTEMS}")
    stems = [s for s in a.stems.split(",") if s] or sorted(p.stem for p in TOKENS.glob("*.jsonl"))
    filt = json.loads(a.sentences.read_text(encoding="utf-8")) if a.sentences else None
    if filt is not None:
        stems = [s for s in stems if s in filt]
    reports = [run_system(s, stems, filt) for s in systems]
    print("SUMMARY")
    for r in reports:
        state = "cached" if r["loaded"] is None else ("ok" if r["loaded"] else "NOT LOADED")
        print(f"  {r['system']:14s} {state:10s} files {r['files']} (+{r['skipped']} cached) tokens {r['tokens']} {r.get('tok_per_s', '-')} tok/s"
              f" unaligned sentences {r['unaligned_sentences']}" + (f"  error: {r['error']}" if r["error"] else ""))


if __name__ == "__main__":
    main()
