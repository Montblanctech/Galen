"""T2b v1 — transcription plausibility scorer ("ancient Greek autocorrect") for HTR output of papyri.

Input: a scriptio-continua Greek string (uppercase, no accents, no spaces), e.g. an HTR line.
Output: the k best segmentations into attested word forms, each word possibly corrected through a
small, declared HTR confusion channel; scored by attestation frequency plus bigram collocation.
No training: every number comes from counting our own corpora, and the five constants below are set
by hand (and checked on a dev split, never on the test split).

Evidence
  forms + unigram counts  our corpora (First1K reference corpus + Galen extracted text), held-out works
                          removed; optionally plus Dilemma's form_profile.db (Open Greek / First1K /
                          GLAUx / Diorisis / PG / PTA attestation), which is read in place, not copied
  bigram counts           our corpora only (Dilemma ships no collocation table)
  LM                      interpolated absolute discounting, d = 0.75 (Ney et al. 1994; the textbook
                          default, not fitted)
Channel (what the model may correct; everything else is read as written)
  confusable letter classes  Α/Λ/Δ, Ε/Θ/Ο/Σ (lunate C), Η/Ν, Ι/Τ
  lost letter                at most one per word
  unreadable or unattested   an "unknown" segment, penalised per letter

Keys: all forms are reduced to the scriptio-continua key (NFD, combining marks dropped, uppercase,
ς and lunate ϲ/C -> Σ), so accent minimal pairs collapse, as they do on the papyrus.

CLI (Greek venv; corpus root defaults to galen-density-map/data, override with --data-root or GALEN_DATA;
the counts cache is written to this checkout's data/t2b_cache/):
  python -I -X utf8 pipeline/t2b_scorer.py build --holdout outputs/t2b/holdout_works.json
  python -I -X utf8 pipeline/t2b_scorer.py segment ΚΑΙΤΟΝΛΟΓΟΝ [-k 5] [--dilemma]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
CACHE_DIR_NAME = "t2b_cache"
SHIFT = 23                      # bigram key = left_id << SHIFT | right_id
MAXV = 1 << SHIFT

LETTERS = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
CONFUSION_CLASSES = ["ΑΛΔ", "ΕΘΟΣ", "ΗΝ", "ΙΤ"]
FOLD = {}
CLASS_SIZE = {}
for _cls in CONFUSION_CLASSES:
    for _c in _cls:
        FOLD[ord(_c)] = _cls[0]
        CLASS_SIZE[_c] = len(_cls)
FOLD_TABLE = str.maketrans({chr(k): v for k, v in FOLD.items()})
FOLD_ALPHABET = sorted({c.translate(FOLD_TABLE) for c in LETTERS})

# hand-set constants (declared, not fitted; see README "Constants")
EPS_SUB = 0.03        # per-letter rate of a within-class confusion
EPS_DEL = 0.01        # per-letter rate of a lost letter
DISCOUNT = 0.75       # absolute discount for the bigram LM
P_UNK = 1e-4          # prior for an unknown segment, then 1/24 per letter
MIN_COUNT = 2         # a form must be attested at least this often to be proposed

_MARKS = re.compile(r"[̀-ͯ]")
_NONLETTER = re.compile(r"[^Α-ΩΣ]+")
_TOKEN = re.compile(r"[Α-Ω]+")
_EDITORIAL = re.compile(r"[\[\]〈〉⟨⟩<>{}⟦⟧]")


def to_continua(text: str) -> str:
    """Any Greek text -> scriptio-continua key: uppercase letters only, no marks, no spaces."""
    t = unicodedata.normalize("NFD", text or "")
    t = _MARKS.sub("", t).upper()
    t = t.replace("Ϲ", "Σ").replace("C", "Σ").replace("ς", "Σ")
    return _NONLETTER.sub("", t)


def continua_words(text: str) -> list[str]:
    """Greek text -> list of word keys (word boundaries kept). Editorial brackets are removed first,
    so a restored letter stays inside its word."""
    t = unicodedata.normalize("NFD", _EDITORIAL.sub("", text or ""))
    t = _MARKS.sub("", t).upper().replace("Ϲ", "Σ")
    return _TOKEN.findall(t)


def file_words(p: Path, chunk: int = 1 << 20):
    """Word keys of a file, read in ~1 MB pieces split at line ends (small memory footprint)."""
    with open(p, encoding="utf-8", errors="replace") as fh:
        rest = ""
        while True:
            block = fh.read(chunk)
            if not block:
                break
            block = rest + block
            cut = block.rfind(chr(10))
            if cut < 0:
                rest = block
                continue
            rest = block[cut + 1:]
            yield from continua_words(block[:cut])
        if rest:
            yield from continua_words(rest)


def fold(s: str) -> str:
    return s.translate(FOLD_TABLE)


# ---------------------------------------------------------------------------------------------
# corpora and counts
# ---------------------------------------------------------------------------------------------

_WORK = re.compile(r"greekLit_([a-z]+\d+[a-z]?)\.([A-Za-z0-9]+)\.")


def work_id(path: str | Path) -> str | None:
    m = _WORK.search(Path(path).name)
    return f"{m.group(1)}.{m.group(2)}" if m else None


def data_root(arg: str | None = None) -> Path:
    for cand in (arg, os.environ.get("GALEN_DATA"), str(PROJECT / "data")):
        if cand and (Path(cand) / "reference_corpus" / "extracted_text").is_dir():
            return Path(cand)
    raise SystemExit("no corpus found: pass --data-root <galen-density-map/data> or set GALEN_DATA")


def corpus_files(root: Path) -> list[Path]:
    files = sorted((root / "reference_corpus" / "extracted_text").glob("urn_cts_greekLit_*.txt"))
    files += sorted((root / "extracted_text").glob("urn_cts_greekLit_*.txt"))
    return files


@dataclass
class Counts:
    forms: list[str]
    uni: np.ndarray            # float64 counts per id (may be mixed with scaled Dilemma counts)
    bkeys: np.ndarray          # int64 sorted unique bigram keys
    bcounts: np.ndarray        # int64
    ctx: np.ndarray            # per id: total bigram count with id on the left
    n1: np.ndarray             # per id: number of distinct right neighbours
    meta: dict = field(default_factory=dict)
    index: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.index:
            self.index = {f: i for i, f in enumerate(self.forms)}

    @property
    def n_tokens(self) -> float:
        return float(self.meta.get("n_tokens_ours") or self.uni.sum())

    def count(self, form: str) -> float:
        i = self.index.get(form)
        return float(self.uni[i]) if i is not None else 0.0


def build_counts(files: list[Path], holdout: set[str], keep_min: int = 2, log=print) -> Counts:
    """Two passes, sized for a small memory budget: (1) form counts; (2) bigrams over the forms
    attested >= keep_min times, every rarer form sharing one id (the last). Bigram counts are
    compressed per file and merged in chunks."""
    from collections import Counter
    use = [p for p in files if work_id(p) not in holdout]
    t0 = time.time()
    cnt: Counter = Counter()
    for p in use:
        cnt.update(file_words(p))
    n_tok = sum(cnt.values())
    kept = [(w, c) for w, c in cnt.most_common() if c >= keep_min]
    n_rare_types = len(cnt) - len(kept)
    n_rare_tokens = n_tok - sum(c for _, c in kept)
    del cnt
    forms = [w for w, _ in kept] + ["<RARE>"]
    uni = np.array([c for _, c in kept] + [0], dtype=np.float64)   # <RARE> never proposed
    rare = len(forms) - 1
    index = {w: i for i, w in enumerate(forms[:-1])}
    if len(forms) >= MAXV:
        raise RuntimeError("vocabulary too large for the bigram key")
    # pass 2: per-file unique bigrams, appended to disk partitions by contiguous left-id range (equal
    # token mass per partition), so each partition is merged alone and the concatenation stays sorted
    P = 48
    mass = np.cumsum(uni) / max(uni.sum(), 1)
    bounds = np.searchsorted(mass, np.arange(1, P) / P, side="right")      # left id -> partition
    tmp = PROJECT / "data" / CACHE_DIR_NAME / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    fk = [open(tmp / f"k{q}.bin", "wb") for q in range(P)]
    fc = [open(tmp / f"c{q}.bin", "wb") for q in range(P)]
    for p in use:
        ids = np.fromiter((index.get(w, rare) for w in file_words(p)), dtype=np.int64)
        if len(ids) < 2:
            continue
        u, c = np.unique((ids[:-1] << SHIFT) | ids[1:], return_counts=True)
        part = np.searchsorted(bounds, u >> SHIFT, side="right")
        cut = np.searchsorted(part, np.arange(P + 1))        # u is sorted, so part is sorted
        for q in range(P):
            if cut[q + 1] > cut[q]:
                u[cut[q]:cut[q + 1]].tofile(fk[q])
                c[cut[q]:cut[q + 1]].astype(np.int32).tofile(fc[q])
    for f in fk + fc:
        f.close()
    ks, cs = [], []
    for q in range(P):
        k = np.fromfile(tmp / f"k{q}.bin", dtype=np.int64)
        c = np.fromfile(tmp / f"c{q}.bin", dtype=np.int32)
        if len(k):
            uq, inv = np.unique(k, return_inverse=True)
            ks.append(uq)
            cs.append(np.bincount(inv, weights=c).astype(np.int32))
        del k, c
        (tmp / f"k{q}.bin").unlink()
        (tmp / f"c{q}.bin").unlink()
    run_k = np.concatenate(ks) if ks else np.zeros(0, np.int64)
    run_c = np.concatenate(cs) if cs else np.zeros(0, np.int32)
    del ks, cs
    bkeys, bcounts = run_k, run_c
    n_files = len(use)
    log(f"counted {n_tok:,} tokens, {len(forms) - 1:,} forms >= {keep_min} (+{n_rare_types:,} rarer types, "
        f"{n_rare_tokens:,} tokens, pooled), {len(bkeys):,} bigram types from {n_files} files in {time.time() - t0:.0f}s")
    left = bkeys >> SHIFT
    ctx = np.bincount(left, weights=bcounts, minlength=len(forms)).astype(np.int64)
    n1 = np.bincount(left, minlength=len(forms)).astype(np.int64)
    meta = {"n_tokens_ours": n_tok, "n_files": n_files, "holdout": sorted(holdout), "keep_min": keep_min,
            "rare_types_pooled": n_rare_types, "rare_tokens_pooled": n_rare_tokens}
    return Counts(forms, uni, bkeys, bcounts, ctx, n1, meta, index)


def save_counts(c: Counts, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, forms=np.array("\n".join(c.forms)), uni=c.uni, bkeys=c.bkeys, bcounts=c.bcounts,
             ctx=c.ctx, n1=c.n1, meta=np.array(json.dumps(c.meta, ensure_ascii=False)))


def load_counts(path: Path) -> Counts:
    z = np.load(path, allow_pickle=False)
    forms = str(z["forms"]).split("\n")
    return Counts(forms, z["uni"], z["bkeys"], z["bcounts"], z["ctx"], z["n1"], json.loads(str(z["meta"])))


def dilemma_profile_path() -> Path | None:
    for d in (os.environ.get("DILEMMA_DATA_DIR"), str(Path.home() / ".cache" / "dilemma" / "data")):
        if d and (Path(d) / "form_profile.db").is_file():
            return Path(d) / "form_profile.db"
    return None


def add_dilemma(c: Counts, db: Path, log=print) -> Counts:
    """Add Dilemma's attestation (total_count per surface form) as extra unigram evidence, scaled to
    our corpus size. Read-only from Dilemma's own SQLite file; nothing is copied into the repo.
    CAUTION: Dilemma's sources include First1K, so held-out works are inside these counts."""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    agg: dict[str, int] = {}
    for form, tot in conn.execute("SELECT f.form, p.total_count FROM forms f JOIN form_profile p USING(form_id)"):
        k = to_continua(form)
        if k:
            agg[k] = agg.get(k, 0) + int(tot or 0)
    conn.close()
    n_dil = sum(agg.values())
    alpha = c.n_tokens / n_dil
    forms = list(c.forms)
    index = dict(c.index)
    extra = []
    for k in agg:
        if k not in index:
            index[k] = len(forms)
            forms.append(k)
            extra.append(k)
    uni = np.zeros(len(forms), dtype=np.float64)
    uni[: len(c.uni)] = c.uni
    for k, v in agg.items():
        uni[index[k]] += alpha * v
    pad = len(forms) - len(c.ctx)
    meta = dict(c.meta, dilemma=str(db), dilemma_tokens=n_dil, dilemma_alpha=alpha, dilemma_new_forms=len(extra))
    log(f"Dilemma: {len(agg):,} keys, {len(extra):,} new to our counts, alpha {alpha:.4f}")
    return Counts(forms, uni, c.bkeys, c.bcounts, np.concatenate([c.ctx, np.zeros(pad, np.int64)]),
                  np.concatenate([c.n1, np.zeros(pad, np.int64)]), meta, index)


# ---------------------------------------------------------------------------------------------
# lexicon with the confusion channel
# ---------------------------------------------------------------------------------------------

def sub_cost(obs: str, form: str) -> tuple[float, int]:
    """log-cost of reading `form` as `obs` (same length, fold-equal) and the number of substitutions."""
    n = 0
    cost = 0.0
    for a, b in zip(obs, form):
        if a != b:
            n += 1
            cost += math.log(EPS_SUB / (CLASS_SIZE.get(b, 2) - 1) / (1 - EPS_SUB))
    return cost, n


LOG_DEL = math.log(EPS_DEL)


class Lexicon:
    def __init__(self, counts: Counts, min_count: int = MIN_COUNT, deletions: bool = True,
                 channel: bool = True, max_len: int = 24):
        self.c = counts
        self.min_count = min_count
        self.channel = channel
        self.max_len = max_len
        N = counts.n_tokens
        self.logN = math.log(N)
        keep = np.nonzero(counts.uni >= min_count)[0]
        self.deletions = deletions and channel
        self.exact: dict[str, int] = {}
        self.by_fold: dict[str, list[int]] = {}
        for i in keep.tolist():
            f = counts.forms[i]
            if len(f) > max_len:
                continue
            self.exact[f] = i
            if channel:
                self.by_fold.setdefault(fold(f), []).append(i)
        self.max_len = max((len(f) for f in self.exact), default=1)
        self._cache: dict[str, list] = {}

    def unigram_logp(self, i: int) -> float:
        return math.log(self.c.uni[i]) - self.logN

    def candidates(self, obs: str, top: int = 8) -> list[tuple[int, float, str]]:
        """Forms that could have produced `obs`: (id, channel log-cost, edit tag). Best `top` by
        unigram + channel."""
        hit = self._cache.get(obs)
        if hit is not None:
            return hit
        res = self._candidates(obs, top)
        if len(self._cache) > 200_000:
            self._cache.clear()
        self._cache[obs] = res
        return res

    def _candidates(self, obs: str, top: int) -> list[tuple[int, float, str]]:
        out: dict[int, tuple[float, str]] = {}
        if not self.channel:
            i = self.exact.get(obs)
            return [(i, 0.0, "")] if i is not None else []
        fo = fold(obs)
        for i in self.by_fold.get(fo, ()):
            cost, n = sub_cost(obs, self.c.forms[i])
            tag = f"sub{n}" if n else ""
            if i not in out or cost > out[i][0]:
                out[i] = (cost, tag)
        if self.deletions and 2 <= len(obs) < self.max_len:
            # a lost letter: the intended form is `obs` with one letter put back (fold alphabet, any slot)
            for p in range(len(fo) + 1):
                for ch in FOLD_ALPHABET:
                    key = fo[:p] + ch + fo[p:]
                    for i in self.by_fold.get(key, ()):
                        form = self.c.forms[i]
                        cost, n = sub_cost(obs, form[:p] + form[p + 1:])
                        cost += LOG_DEL
                        if i not in out or cost > out[i][0]:
                            out[i] = (cost, f"lost:{form[p]}@{p}" + (f"+sub{n}" if n else ""))
        ranked = sorted(out.items(), key=lambda kv: -(self.unigram_logp(kv[0]) + kv[1][0]))[:top]
        return [(i, cost, tag) for i, (cost, tag) in ranked]


# ---------------------------------------------------------------------------------------------
# segmenter
# ---------------------------------------------------------------------------------------------

@dataclass
class Segment:
    start: int          # span in the observed string
    end: int
    observed: str
    form: str | None    # attested form (key), None = unknown segment
    edit: str = ""      # "", "sub1", "lost:Ν@3", "unknown"


@dataclass
class Reading:
    score: float
    segments: list[Segment]

    @property
    def words(self) -> list[str]:
        return [s.form if s.form is not None else s.observed for s in self.segments]

    @property
    def text(self) -> str:
        return " ".join(s.form if s.form is not None else f"?{s.observed}?" for s in self.segments)

    @property
    def boundaries(self) -> set[int]:
        return {s.end for s in self.segments[:-1]}


class Segmenter:
    def __init__(self, lex: Lexicon, bigram: bool = True, beam: int = 48, per_last: int = 4,
                 cand_top: int = 8, max_unk: int = 10):
        self.lex = lex
        self.c = lex.c
        self.bigram = bigram
        self.beam = beam
        self.per_last = per_last
        self.cand_top = cand_top
        self.max_unk = max_unk
        self._uni_logp = np.log(np.maximum(self.c.uni, 1e-12)) - lex.logN
        self._ctx = self.c.ctx.astype(np.float64)
        self._n1 = self.c.n1.astype(np.float64)
        self._unk_letter = math.log(1 / 24)

    # log P(w | v) for a grid of previous ids (H) x candidate ids (C); -1 = none / unknown
    def lm_grid(self, prev: np.ndarray, cand: np.ndarray) -> np.ndarray:
        cw = np.maximum(cand, 0)
        pu = np.exp(self._uni_logp[cw])                       # (C,)
        out = np.broadcast_to(np.log(pu), (len(prev), len(cand))).copy()
        if not self.bigram:
            return out
        valid_prev = prev >= 0
        if not valid_prev.any():
            return out
        pv = np.maximum(prev, 0)
        cv = self._ctx[pv]                                    # (H,)
        has_ctx = valid_prev & (cv > 0)
        if not has_ctx.any():
            return out
        keys = (pv[:, None] << SHIFT) | cw[None, :]
        pos = np.searchsorted(self.c.bkeys, keys)
        pos = np.minimum(pos, len(self.c.bkeys) - 1)
        hit = self.c.bkeys[pos] == keys
        cvw = np.where(hit, self.c.bcounts[pos], 0).astype(np.float64)
        cvs = np.where(cv > 0, cv, 1.0)[:, None]
        p = np.maximum(cvw - DISCOUNT, 0) / cvs + DISCOUNT * self._n1[pv][:, None] / cvs * pu[None, :]
        out = np.where(has_ctx[:, None], np.log(np.maximum(p, 1e-300)), out)
        return out

    def _candidates(self, s: str):
        n = len(s)
        cands = [[] for _ in range(n)]       # cands[i] = list of (j, id, chan_cost, edit)
        for i in range(n):
            for L in range(1, min(self.lex.max_len + 1, n - i) + 1):
                obs = s[i:i + L]
                for wid, cost, tag in self.lex.candidates(obs, self.cand_top):
                    cands[i].append((i + L, wid, cost, tag))
                if L <= self.max_unk:
                    cands[i].append((i + L, -1, math.log(P_UNK) + L * self._unk_letter, "unknown"))
        return cands

    def segment(self, s: str, k: int = 5) -> list[Reading]:
        s = to_continua(s)
        n = len(s)
        if n == 0:
            return [Reading(0.0, [])]
        cands = self._candidates(s)
        # hypothesis: (score, last_id, parent, (i, j, wid, chan, edit))
        hyps: list[list[tuple]] = [[] for _ in range(n + 1)]
        hyps[0] = [(0.0, -1, None, None)]
        for i in range(n):
            H = self._prune(hyps[i])
            hyps[i] = H
            if not H or not cands[i]:
                continue
            prev = np.array([h[1] for h in H], dtype=np.int64)
            hs = np.array([h[0] for h in H])
            C = cands[i]
            cid = np.array([c[1] for c in C], dtype=np.int64)
            chan = np.array([c[2] for c in C])
            lm = self.lm_grid(prev, cid)
            unk = cid < 0
            lm[:, unk] = 0.0                                    # unknown: cost is all in chan
            tot = hs[:, None] + lm + chan[None, :]
            js = np.array([c[0] for c in C])
            for j in np.unique(js):
                cols = np.nonzero(js == j)[0]
                sub = tot[:, cols]
                flat = sub.ravel()
                m = min(self.beam, flat.size)
                top = np.argpartition(-flat, m - 1)[:m]
                for t in top.tolist():
                    hi, ci = divmod(t, len(cols))
                    c = C[cols[ci]]
                    hyps[j].append((float(flat[t]), c[1], H[hi], (i, c[0], c[1], c[2], c[3])))
        final = sorted(hyps[n], key=lambda h: -h[0])
        out, seen = [], set()
        for h in final:
            segs = self._backtrace(h, s)
            key = tuple(x.form if x.form is not None else "?" + x.observed for x in segs)
            if key in seen:
                continue
            seen.add(key)
            out.append(Reading(h[0], segs))
            if len(out) >= k:
                break
        return out

    def _prune(self, H):
        H = sorted(H, key=lambda h: -h[0])
        out, per = [], {}
        for h in H:
            c = per.get(h[1], 0)
            if c >= self.per_last:
                continue
            per[h[1]] = c + 1
            out.append(h)
            if len(out) >= self.beam:
                break
        return out

    def _backtrace(self, h, s):
        segs = []
        while h is not None and h[3] is not None:
            i, j, wid, _chan, tag = h[3]
            segs.append(Segment(i, j, s[i:j], self.c.forms[wid] if wid >= 0 else None, tag))
            h = h[2]
        return segs[::-1]

    def score_words(self, words: list[str]) -> list[float]:
        """Per-word log P(w | previous) of a GIVEN word sequence under the same LM (unattested -> unknown cost)."""
        out = []
        prev = -1
        for w in words:
            wid = self.lex.exact.get(w, -1)
            if wid < 0:
                out.append(math.log(P_UNK) + len(w) * self._unk_letter)
            else:
                out.append(float(self.lm_grid(np.array([prev], dtype=np.int64), np.array([wid], dtype=np.int64))[0, 0]))
            prev = wid
        return out


def greedy_longest(lex: Lexicon, s: str) -> Reading:
    """Baseline: at each position take the longest attested form (exact, no channel), else one letter."""
    s = to_continua(s)
    segs, i = [], 0
    while i < len(s):
        for L in range(min(lex.max_len, len(s) - i), 0, -1):
            w = s[i:i + L]
            if w in lex.exact:
                segs.append(Segment(i, i + L, w, w, ""))
                i += L
                break
        else:
            segs.append(Segment(i, i + 1, s[i], None, "unknown"))
            i += 1
    return Reading(0.0, segs)


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

def cache_path(root: Path | None = None, name: str = "counts") -> Path:
    """The counts cache lives in THIS checkout's data dir (gitignored), never in the corpus root, which
    may be another checkout that must not be written to. `root` is accepted and ignored."""
    return PROJECT / "data" / CACHE_DIR_NAME / f"{name}.npz"


def load_model(root: Path, dilemma: bool = False, min_count: int = MIN_COUNT, channel: bool = True,
               bigram: bool = True, log=print) -> Segmenter:
    p = cache_path(root)
    if not p.is_file():
        raise SystemExit(f"no counts cache at {p}; run `t2b_scorer.py build` first")
    c = load_counts(p)
    if dilemma:
        db = dilemma_profile_path()
        if db is None:
            raise SystemExit("Dilemma form_profile.db not found (python -m dilemma download --with-attestation)")
        c = add_dilemma(c, db, log=log)
    t0 = time.time()
    lex = Lexicon(c, min_count=min_count, channel=channel)
    log(f"lexicon: {len(lex.exact):,} forms (count >= {min_count}), "
        f"{time.time() - t0:.0f}s")
    return Segmenter(lex, bigram=bigram)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-root", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="count forms and bigrams over our corpora, minus held-out works")
    b.add_argument("--holdout", default=None, help="JSON with a list 'works' (or test/dev/real lists) to exclude")
    s = sub.add_parser("segment", help="k best segmentations of scriptio-continua strings")
    s.add_argument("strings", nargs="+")
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--dilemma", action="store_true", help="add Dilemma form attestation to the unigram evidence")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = data_root(a.data_root)
    if a.cmd == "build":
        hold: set[str] = set()
        if a.holdout:
            h = json.loads(Path(a.holdout).read_text(encoding="utf-8"))
            for key in ("works", "test", "dev", "real"):
                hold |= set(h.get(key, []))
        c = build_counts(corpus_files(root), hold)
        save_counts(c, cache_path(root))
        print(f"saved {cache_path(root)} (held out {len(hold)} works)")
        return
    seg = load_model(root, dilemma=a.dilemma, log=lambda m: print(m, file=sys.stderr))
    res = []
    for st in a.strings:
        rs = seg.segment(st, k=a.k)
        res.append({"input": to_continua(st), "readings": [
            {"score": round(r.score, 3), "text": r.text,
             "edits": [{"span": [x.start, x.end], "observed": x.observed, "form": x.form, "edit": x.edit}
                       for x in r.segments if x.edit]} for r in rs]})
        if not a.json:
            print(to_continua(st))
            for n, r in enumerate(rs, 1):
                ed = ", ".join(f"{x.observed}->{x.form or '?'} [{x.edit}]" for x in r.segments if x.edit)
                print(f"  {n}. {r.score:8.2f}  {r.text}" + (f"   ({ed})" if ed else ""))
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
