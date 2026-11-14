"""T2b v1 evaluation without training: held-out works -> scriptio continua -> injected HTR confusions.

  holdout   pick held-out works (seeded): test, dev, and the real case (Philodemus) -> outputs/t2b/holdout_works.json
            then run `t2b_scorer.py build --holdout outputs/t2b/holdout_works.json` so none of them is counted
  lines     sample "HTR lines" (20-40 letters, whole words) from the held-out works and inject noise
            -> outputs/t2b/testset_{split}.jsonl (gold words, clean string, noisy strings per level)
  run       score every system on every level -> outputs/t2b/eval_{split}.json + eval_{split}.md

Noise (per letter, seeded; the rates are assumptions, not measured HTR error rates):
  in-channel   within-class confusion Α/Λ/Δ, Ε/Θ/Ο/Σ, Η/Ν, Ι/Τ  (the scorer's channel can undo these)
  off-channel  any other letter (the scorer cannot undo these; they keep the test honest)
  lost letter  deletion
Metrics (in the coordinates of the noisy string):
  boundary P/R/F1   word boundaries; a boundary is a position between two letters
  word recovery     gold word recovered with its span and its spelling
  line top-1/top-5  the whole line's gold word sequence is the first / among the first five readings
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t2b_scorer as T  # noqa: E402

OUT = T.PROJECT / "outputs" / "t2b"
HOLDOUT = OUT / "holdout_works.json"
LEVELS = {
    "clean": dict(sub=0.0, off=0.0, dele=0.0),
    "light": dict(sub=0.03, off=0.005, dele=0.01),
    "heavy": dict(sub=0.08, off=0.01, dele=0.03),
}
REAL_WORKS = ["tlg1595.tlg221", "tlg1595.tlg370"]   # Philodemus (Herculaneum papyri), the real case


def pick_holdout(root: Path, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    ref = [p for p in sorted((root / "reference_corpus" / "extracted_text").glob("urn_cts_greekLit_tlg*.txt"))
           if 100_000 <= p.stat().st_size <= 1_500_000 and T.work_id(p) not in REAL_WORKS]
    gal = [p for p in sorted((root / "extracted_text").glob("urn_cts_greekLit_tlg0057*.txt"))
           if 100_000 <= p.stat().st_size <= 1_500_000]
    by_work: dict[str, Path] = {}
    for p in ref:
        by_work.setdefault(T.work_id(p), p)
    works = sorted(by_work)
    rng.shuffle(works)
    gw = sorted({T.work_id(p) for p in gal})
    rng.shuffle(gw)
    return {"seed": seed, "test": sorted(works[:10] + gw[:2]), "dev": sorted(works[10:14] + gw[2:3]),
            "real": REAL_WORKS,
            "rule": "First1K reference works of 100 KB - 1.5 MB (+ Galen works of the same size), seeded shuffle; "
                    "every edition of a held-out work is excluded from the counts"}


def files_for(root: Path, works: list[str]) -> list[Path]:
    ws = set(works)
    return [p for p in T.corpus_files(root) if T.work_id(p) in ws]


def inject(clean: str, lv: dict, rng: random.Random, events: list | None = None) -> tuple[str, list[int]]:
    """Return the noisy string and, for each clean position 0..n, the noisy position (for boundaries).
    If `events` is a list, (clean_index, kind) is appended for every injected error."""
    out = []
    pos = []
    for k, ch in enumerate(clean):
        pos.append(len(out))
        r = rng.random()
        if r < lv["dele"]:
            if events is not None:
                events.append((k, "del"))
            continue
        r = rng.random()
        cls = next((c for c in T.CONFUSION_CLASSES if ch in c), None)
        if cls and r < lv["sub"]:
            out.append(rng.choice([c for c in cls if c != ch]))
            if events is not None:
                events.append((k, "sub"))
        elif r < lv["sub"] + lv["off"]:
            out.append(rng.choice([c for c in T.LETTERS if c != ch and (not cls or c not in cls)]))
            if events is not None:
                events.append((k, "off"))
        else:
            out.append(ch)
    pos.append(len(out))
    return "".join(out), pos


def recoverable(words: list[str], events: list) -> bool:
    """True if the scorer's channel can in principle undo every injected error: no off-channel
    substitution, at most one lost letter per word, and no word lost entirely."""
    starts, i = [], 0
    for w in words:
        starts.append((i, i + len(w)))
        i += len(w)
    dels = [0] * len(words)
    for k, kind in events:
        if kind == "off":
            return False
        if kind == "del":
            wi = next(n for n, (a, b) in enumerate(starts) if a <= k < b)
            dels[wi] += 1
    return all(d <= 1 and (d < len(w)) for d, w in zip(dels, words))


def make_lines(root: Path, works: list[str], per_work: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    lines = []
    for w in works:
        fs = files_for(root, [w])
        toks = T.continua_words(fs[0].read_text(encoding="utf-8", errors="replace"))
        if len(toks) < 200:
            continue
        for n in range(per_work):
            target = rng.randint(20, 40)
            st = rng.randrange(0, len(toks) - 40)
            words, L = [], 0
            while L < target:
                words.append(toks[st + len(words)])
                L += len(words[-1])
            clean = "".join(words)
            row = {"id": f"{w}:{n}", "work": w, "gold": words, "clean": clean, "noisy": {}}
            for name, lv in LEVELS.items():
                ev: list = []
                noisy, pos = inject(clean, lv, random.Random(f"{seed}:{w}:{n}:{name}"), ev)
                row["noisy"][name] = {"s": noisy, "pos": pos, "errors": len(ev),
                                      "recoverable": recoverable(words, ev)}
            lines.append(row)
    return lines


def gold_spans(words: list[str], pos: list[int]) -> tuple[set[int], list[tuple[int, int, str]]]:
    spans, b, i = [], set(), 0
    for w in words:
        spans.append((pos[i], pos[i + len(w)], w))
        i += len(w)
    n = pos[-1]
    for s, e, _ in spans[:-1]:
        if 0 < e < n:
            b.add(e)
    return b, spans


def evaluate(lines: list[dict], level: str, system, k: int = 5) -> dict:
    tp = fp = fn = 0
    wtp = wpred = wgold = 0
    top1 = top5 = 0
    rec_n = rec1 = rec5 = 0
    t0 = time.time()
    samples = []
    for row in lines:
        nz = row["noisy"][level]
        gb, gs = gold_spans(row["gold"], nz["pos"])
        reads = system(nz["s"], k)
        best = reads[0]
        pb = best.boundaries
        tp += len(pb & gb)
        fp += len(pb - gb)
        fn += len(gb - pb)
        ps = {(x.start, x.end, x.form) for x in best.segments if x.form is not None}
        gss = {g for g in gs if g[1] > g[0]}
        wtp += len(ps & gss)
        wpred += len(best.segments)
        wgold += len(gs)
        hit = [r.words == row["gold"] for r in reads[:k]]
        top1 += bool(hit and hit[0])
        top5 += any(hit)
        if nz.get("recoverable"):
            rec_n += 1
            rec1 += bool(hit and hit[0])
            rec5 += any(hit)
        if len(samples) < 40:
            samples.append({"id": row["id"], "noisy": nz["s"], "gold": " ".join(row["gold"]), "top1": best.text,
                            "rank_of_gold": (hit.index(True) + 1) if any(hit) else None})
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    n = len(lines)
    return {"lines": n, "boundary_P": round(P, 4), "boundary_R": round(R, 4),
            "boundary_F1": round(2 * P * R / (P + R), 4) if P + R else 0.0,
            "word_recovery_R": round(wtp / wgold, 4) if wgold else 0.0,
            "word_recovery_P": round(wtp / wpred, 4) if wpred else 0.0,
            "line_top1": round(top1 / n, 4), "line_top5": round(top5 / n, 4),
            "recoverable_lines": rec_n, "recoverable_top1": round(rec1 / rec_n, 4) if rec_n else None,
            "recoverable_top5": round(rec5 / rec_n, 4) if rec_n else None,
            "seconds": round(time.time() - t0, 1), "samples": samples}


def systems(root: Path, which: list[str], min_count: int):
    out = {}
    base = None
    for name in which:
        if name == "dilemma_bigram":
            seg = T.load_model(root, dilemma=True, min_count=min_count, log=lambda m: print(m, file=sys.stderr))
            out[name] = seg.segment
            continue
        if base is None:
            base = T.load_counts(T.cache_path())
        if name == "greedy":
            lex = T.Lexicon(base, min_count=min_count, channel=False)
            out[name] = lambda s, k, lex=lex: [T.greedy_longest(lex, s)]
        elif name == "unigram":
            out[name] = T.Segmenter(T.Lexicon(base, min_count=min_count), bigram=False).segment
        elif name == "bigram_nochannel":
            out[name] = T.Segmenter(T.Lexicon(base, min_count=min_count, channel=False)).segment
        elif name == "bigram":
            out[name] = T.Segmenter(T.Lexicon(base, min_count=min_count)).segment
        elif name == "bigram_spelling":
            out[name] = T.Segmenter(T.Lexicon(base, min_count=min_count, spelling=T.load_spelling())).segment
    return out


def table(res: dict) -> str:
    rows = ["| system | level | lines | boundary P | boundary R | boundary F1 | word rec. | line top-1 | line top-5 "
            "| recoverable lines | rec. top-1 | rec. top-5 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for sysname, by in res.items():
        for lv, r in by.items():
            rows.append(f"| {sysname} | {lv} | {r['lines']} | {r['boundary_P']:.3f} | {r['boundary_R']:.3f} | "
                        f"**{r['boundary_F1']:.3f}** | {r['word_recovery_R']:.3f} | {r['line_top1']:.3f} | {r['line_top5']:.3f} | "
                        f"{r.get('recoverable_lines', '')} | {r.get('recoverable_top1') or 0:.3f} | {r.get('recoverable_top5') or 0:.3f} |")
    return "\n".join(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("holdout")
    li = sub.add_parser("lines")
    li.add_argument("--split", default="test")
    li.add_argument("--per-work", type=int, default=50)
    ru = sub.add_parser("run")
    ru.add_argument("--split", default="test")
    ru.add_argument("--systems", default="greedy,unigram,bigram_nochannel,bigram")
    ru.add_argument("--levels", default="clean,light,heavy")
    ru.add_argument("--min-count", type=int, default=T.MIN_COUNT)
    ru.add_argument("--limit", type=int, default=0)
    ru.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    root = T.data_root(a.data_root)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "holdout":
        h = pick_holdout(root)
        HOLDOUT.write_text(json.dumps(h, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in h.items() if k != "rule"}))
        return
    h = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    path = OUT / f"testset_{a.split}.jsonl"
    if a.cmd == "lines":
        lines = make_lines(root, h[a.split], a.per_work, seed=7 if a.split == "test" else 11)
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", encoding="utf-8")
        print(f"{len(lines)} lines -> {path}")
        return
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if a.limit:
        lines = lines[: a.limit]
    res: dict = {}
    for name, fn in systems(root, a.systems.split(","), a.min_count).items():
        res[name] = {}
        for lv in a.levels.split(","):
            r = evaluate(lines, lv, fn)
            res[name][lv] = r
            print(f"{name:18s} {lv:6s} F1 {r['boundary_F1']:.3f} word {r['word_recovery_R']:.3f} "
                  f"top1 {r['line_top1']:.3f} top5 {r['line_top5']:.3f} ({r['seconds']}s)", flush=True)
    tag = f"_{a.tag}" if a.tag else ""
    (OUT / f"eval_{a.split}{tag}.json").write_text(json.dumps(
        {"split": a.split, "min_count": a.min_count, "levels": LEVELS, "results": res}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (OUT / f"eval_{a.split}{tag}.md").write_text(table(res) + "\n", encoding="utf-8")
    print(table(res))


if __name__ == "__main__":
    main()
