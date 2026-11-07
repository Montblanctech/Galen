"""LSJ-Gold, Perseus editions — build per-token lemma caches for odyCy and Stanza.

For each token JSONL in data/perseus_corpus/lemmatized (written by perseus_tokens.py: surface tokens only, one per
line, lemma fields empty) this writes OUT/<system>/<stem>.jsonl with {"i", "surface", "lemma"} for every token, in
the source order, so score.py --system-cache OUT can merge it by stem and token_index.

Systems (one per process run is recommended; models are loaded lazily, one at a time):
  odycy           audit-kit OdycySystem, token-level mode (Docs built from the source words; no re-tokenization)
  stanza_perseus  audit-kit StanzaSystem pipeline config (tokenize,pos,lemma; grc/perseus), fed pretokenized
  stanza_proiel   same, grc/proiel
Stanza is fed the source tokens as pretokenized pseudo-sentences; should it ever drop or merge a token the output
is realigned to the source by NFC surface (audit-kit align_surfaces) and unaligned tokens get lemma "".
Alignment check: cache surface == source surface for every i (asserted per work; a failing work is reported and
not written). Output is written atomically (.tmp then rename); works whose output exists are skipped.

Usage: python -X utf8 pipeline/lsjgold/perseus_caches.py --systems odycy [--only tlg0033] [--out DIR]
stoicheia: run under .venv-sto with STOICHEIA_DIR set; checkpoints <stem>.partial.jsonl every 2,000 tokens.
Stanza needs STANZA_RESOURCES_DIR pointing at the 1.14.0 resources (models are never downloaded).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
REPO = GDM.parent
sys.path.insert(0, str(REPO / "audit-kit"))
from greek_lemma_audit.align import align_surfaces  # noqa: E402
from greek_lemma_audit.corpus import Token, Work, WorkRef, author_of  # noqa: E402
# odycy / stanza / stoicheia adapters are imported lazily: they live in different venvs (stoicheia needs transformers 5).

LEM = GDM / "data" / "perseus_corpus" / "lemmatized"
DEFAULT_OUT = Path("C:/Users/W/AppData/Local/Temp/claude/3d58b1488e5f774d/c8b67b7e-4794-4ccf-9e64-fada4fc17b0d/scratchpad/perseus_caches/cache")
SYSTEMS = ("odycy", "stanza_perseus", "stanza_proiel")  # + "stoicheia" (explicit only; .venv-sto)
STO_CHUNK = 2000  # tokens per stoicheia call = checkpoint size (multiple of the adapter's 40-word sentences)
STANZA_SENT = 100  # words per pretokenized pseudo-sentence (source tokens carry no punctuation)
STANZA_BATCH = 50  # pseudo-sentences per nlp() call


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def read_source(path: Path, strict_i: bool = True) -> list[Token]:
    toks: list[Token] = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if strict_i and int(row["i"]) != n:
                raise ValueError(f"{path.name}: line {n} carries i={row['i']}")
            toks.append(Token(i=n, surface=row.get("surface") or "", lemma="", pos=""))
    return toks


class OdycyRunner:
    def __init__(self) -> None:
        from greek_lemma_audit.systems.odycy import OdycySystem

        self.sys = OdycySystem()

    def run(self, stem: str, src: list[Token]) -> list[tuple[str, str]]:
        work = Work(ref=WorkRef(stem=stem, path=LEM / f"{stem}.jsonl", kind="jsonl", subcorpus="perseus",
                                author=author_of(stem)), tokens=src, text=None)
        out = self.sys.run(work)
        if out is None:
            raise RuntimeError(f"odyCy skipped: {self.sys.last_skip_reason}")
        return [(t.surface, t.lemma) for t in out]


class StanzaRunner:
    def __init__(self, package: str) -> None:
        from greek_lemma_audit.systems.stanza import PROCESSORS, StanzaSystem

        self._processors = PROCESSORS
        self.sys = StanzaSystem(package)
        av = self.sys.availability()
        if not av.ok or not av.version.get("model_downloaded"):
            raise RuntimeError(f"stanza {package} unavailable: {av.detail}")
        import stanza

        # Same pipeline as StanzaSystem._load (no download), plus pretokenized input.
        self.sys._nlp = stanza.Pipeline(lang="grc", package=package, processors=self._processors, verbose=False,
                                        download_method=None, tokenize_pretokenized=True)

    def run(self, stem: str, src: list[Token]) -> list[tuple[str, str]]:
        nlp = self.sys._nlp
        words = [t.surface for t in src]
        sents = [words[b : b + STANZA_SENT] for b in range(0, len(words), STANZA_SENT)]
        got: list[tuple[str, str]] = []
        for b in range(0, len(sents), STANZA_BATCH):
            doc = nlp(sents[b : b + STANZA_BATCH])
            for s in doc.sentences:
                for w in s.words:
                    got.append((w.text or "", w.lemma or ""))
        if len(got) == len(words) and all(nfc(a) == nfc(b[0]) for a, b in zip(words, got)):
            return got
        # Realign dropped/merged tokens by form.
        pairs, stats = align_surfaces(words, [g[0] for g in got])
        print(f"  {stem}: stanza realigned by form ({len(got)} vs {len(words)}; {stats})", flush=True)
        lem = {ia: got[ib][1] for ia, ib in pairs}
        return [(w, lem.get(i, "")) for i, w in enumerate(words)]


class StoicheiaRunner:
    """Stoicheia tagger-parser via the audit-kit adapter, fed STO_CHUNK-token chunks; each finished chunk is appended
    to <out>/stoicheia/<stem>.partial.jsonl so a native crash (ACCESS_VIOLATION) resumes instead of restarting."""

    def __init__(self, odir: Path) -> None:
        from greek_lemma_audit.systems.stoicheia import StoicheiaSystem

        self.sys = StoicheiaSystem()  # words_per_sentence=40, STOICHEIA_DIR from env
        av = self.sys.availability()
        if not av.ok:
            raise RuntimeError(f"stoicheia unavailable: {av.detail}")
        self.sys._load()
        self.odir = odir

    def run(self, stem: str, src: list[Token]) -> list[tuple[str, str]]:
        partial = self.odir / f"{stem}.partial.jsonl"
        res: list[tuple[str, str]] = []
        if partial.exists():
            for line in partial.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    break  # torn last line from a crash
                res.append((r["surface"], r.get("lemma") or ""))
            res = res[: len(res) // STO_CHUNK * STO_CHUNK]
            if len(res) > len(src) or any(nfc(a[0]) != nfc(b.surface) for a, b in zip(res, src)):
                res = []
            with partial.open("w", encoding="utf-8", newline="\n") as fh:  # rewrite exactly the validated prefix
                for t, (s_, l_) in zip(src, res):
                    fh.write(json.dumps({"i": t.i, "surface": s_, "lemma": l_}, ensure_ascii=False) + "\n")
            if res:
                print(f"  {stem}: resumed from checkpoint at {len(res)}/{len(src)}", flush=True)
        for b in range(len(res), len(src), STO_CHUNK):
            chunk = [Token(i=k, surface=t.surface, lemma="", pos="") for k, t in enumerate(src[b : b + STO_CHUNK])]
            work = Work(ref=WorkRef(stem=stem, path=LEM / f"{stem}.jsonl", kind="jsonl", subcorpus="perseus",
                                    author=author_of(stem)), tokens=chunk, text=None)
            out = self.sys.run(work)
            if out is None:
                raise RuntimeError(f"stoicheia skipped: {self.sys.last_skip_reason}")
            new = [(t.surface, t.lemma) for t in out]
            with partial.open("a", encoding="utf-8", newline="\n") as fh:
                for t, (s_, l_) in zip(src[b : b + STO_CHUNK], new):
                    fh.write(json.dumps({"i": t.i, "surface": s_, "lemma": l_}, ensure_ascii=False) + "\n")
            res.extend(new)
        return res


def first1k_files() -> list[Path]:
    """Project First1K/reference JSONLs that hold gold rows (same author+work -> stem mapping as score.py)."""
    import csv

    held: dict[tuple[str, str], str] = {}
    for xml_dir in (GDM / "data" / "reference_corpus" / "raw_xml", GDM / "data" / "raw_xml",
                    GDM / "data" / "perseus_corpus" / "raw_xml"):
        for x in xml_dir.glob("urn_cts_greekLit_tlg*.xml"):
            parts = x.stem.split("_")[3].split(".")
            held.setdefault((parts[0], parts[1]), x.stem)
    gold = csv.DictReader((GDM / "data" / "qc" / "lsjgold" / "lsj_gold_v0.csv").open(encoding="utf-8"))
    stems = sorted({held[(g["author"], g["work"])] for g in gold if (g["author"], g["work"]) in held})
    out = []
    for stem in stems:
        for d in (GDM / "data" / "lemmatized" / "reference", GDM / "data" / "lemmatized" / "galen"):
            if (d / f"{stem}.jsonl").exists():
                out.append(d / f"{stem}.jsonl")
                break
    return out


def make_runner(name: str, odir: Path | None = None):
    if name == "stoicheia":
        return StoicheiaRunner(odir)
    if name == "odycy":
        return OdycyRunner()
    if name.startswith("stanza_"):
        return StanzaRunner(name.split("_", 1)[1])
    raise SystemExit(f"unknown system {name}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default=",".join(SYSTEMS))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="comma list of substrings a stem must contain (e.g. tlg0033)")
    ap.add_argument("--first1k", action="store_true",
                    help="Stanza caches for the project (First1K/reference) JSONLs holding gold rows; i = JSONL line")
    args = ap.parse_args()
    if args.first1k:
        files = first1k_files()
        if "odycy" in args.systems.split(","):
            args.systems = ",".join(s for s in args.systems.split(",") if s != "odycy")
            print("--first1k: odycy dropped (First1K odyCy lemmas already live in the project JSONL)", flush=True)
    else:
        files = sorted(LEM.glob("urn_cts_greekLit_*.jsonl"))
    if args.only:
        keys = [k for k in args.only.split(",") if k]
        files = [f for f in files if any(k in f.stem for k in keys)]
    failures: list[str] = []
    for name in [s.strip() for s in args.systems.split(",") if s.strip()]:
        odir = args.out / name
        odir.mkdir(parents=True, exist_ok=True)
        todo = [f for f in files if not (odir / f"{f.stem}.jsonl").exists()]
        print(f"[{name}] {len(files) - len(todo)} done, {len(todo)} to run", flush=True)
        if not todo:
            continue
        t0 = time.time()
        runner = make_runner(name, odir)
        print(f"[{name}] model loaded in {time.time() - t0:.1f}s", flush=True)
        for f in todo:
            src = read_source(f, strict_i=not args.first1k)
            t1 = time.time()
            try:
                res = runner.run(f.stem, src)
            except Exception as exc:  # report, keep going
                failures.append(f"{name}/{f.stem}: {type(exc).__name__}: {exc}")
                print(f"  FAIL {f.stem}: {exc}", flush=True)
                continue
            bad = [i for i, (t, r) in enumerate(zip(src, res)) if nfc(r[0]) != nfc(t.surface)]
            if len(res) != len(src) or bad:
                msg = f"{name}/{f.stem}: alignment failed (len {len(res)} vs {len(src)}, mismatches {len(bad)}, first {bad[:5]})"
                failures.append(msg)
                print("  " + msg, flush=True)
                continue
            dt = time.time() - t1
            tmp = odir / f"{f.stem}.jsonl.tmp"
            with tmp.open("w", encoding="utf-8", newline="\n") as fh:
                for t, (_s, lemma) in zip(src, res):
                    fh.write(json.dumps({"i": t.i, "surface": t.surface, "lemma": lemma}, ensure_ascii=False) + "\n")
            os.replace(tmp, odir / f"{f.stem}.jsonl")
            (odir / f"{f.stem}.partial.jsonl").unlink(missing_ok=True)
            n_lem = sum(1 for r in res if r[1])
            print(f"  {f.stem}: tokens {len(src)} mismatches 0 lemmatized {n_lem} {dt:.1f}s "
                  f"({len(src) / max(dt, 1e-9):.0f} tok/s)", flush=True)
        del runner
    if failures:
        print("FAILURES:\n" + "\n".join(failures), flush=True)
        return 1
    print("all done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
