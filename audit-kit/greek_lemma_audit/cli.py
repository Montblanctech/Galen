"""``greek-lemma-audit`` command line.

    greek-lemma-audit run   --out DIR [--corpus-root DIR] [--author tlg0057] [--systems reference,stanza-perseus,...] ...
    greek-lemma-audit score --key KEY.csv --answers READER.csv [--answers READER2.csv] --out DIR
    greek-lemma-audit lsjgold --system-cache DIR [--gold CSV] [--out scores.json]
    greek-lemma-audit systems            # probe which lemmatizer systems can run here
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from . import KIT_NAME, __version__
from .audit import (
    DEFAULT_CORPUS_ROOT,
    DEFAULT_M3_GOLD,
    DEFAULT_MORPHEUS_CACHE,
    DEFAULT_STANZA_CACHE,
    DEFAULT_TEXT_ROOT,
    DEFAULT_TEXT_ROOTS,
    AuditConfig,
    run_audit,
)
from .m5 import merge_answer_files, score_sheet, write_batches
from .systems import SYSTEM_NAMES, make_system


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _csv_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=KIT_NAME,
        description=(
            "Lemmatizer Audit Kit (Galen Density Project T1). Audits any Ancient Greek lemmatizer output over any "
            "corpus, author-stratified, and emits a bounded accuracy range (M1 Morpheus admissibility floor, M2 "
            "cross-system agreement upper bound, M3 LSJ-citation rare-stratum point estimate where a Kuhn map exists), "
            "a frequency-ranked disagreement worklist, a blind salted reviewer sheet (M5) and a citable JSON. "
            "Report-only: the corpus is never modified."
        ),
    )
    p.add_argument("--version", action="version", version=f"{KIT_NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="audit a corpus directory", description="Run M1/M2/M3/M5 over a corpus and write <out>/audit_summary.json.")
    r.add_argument("--out", required=True, type=Path, help="output directory (created)")
    r.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT,
                   help="directory tree of token JSONL ({i,surface,lemma,pos,morph}) or plain-text .txt works "
                        f"(default: {DEFAULT_CORPUS_ROOT})")
    r.add_argument("--subcorpus", action="append", default=[], metavar="NAME",
                   help="restrict to a first-level subdirectory of the corpus root (repeatable; e.g. galen, reference)")
    r.add_argument("--author", action="append", default=[], metavar="tlgNNNN",
                   help="restrict to works whose URN carries this author id (repeatable)")
    r.add_argument("--max-works", type=int, default=0, help="debug cap on the number of works")
    r.add_argument("--systems", type=_csv_list, default=["reference"],
                   help=f"comma list from: {', '.join(SYSTEM_NAMES)} (default: reference = lemmas in the JSONL). "
                        "Unavailable systems are skipped and reported, never installed.")
    r.add_argument("--audit-system", default=None, help="the system under audit / alignment anchor (default: first of --systems)")
    r.add_argument("--key-out", type=Path, default=None,
                   help="path for the PRIVATE reviewer-sheet key (required to build the M5 sheet; keep it outside anything you publish)")
    r.add_argument("--controls", type=Path, default=None,
                   help="controls CSV in the project's accuracy_controls.csv format: salts the sheet and replays G1b")
    r.add_argument("--morpheus-cache", action="append", type=Path, default=None, metavar="JSONL",
                   help=f"Morpheus by-surface cache(s), opened read-only (repeatable; default: {DEFAULT_MORPHEUS_CACHE} if present)")
    r.add_argument("--online", action="store_true",
                   help="query morph.perseids.org for surfaces missing from the cache (rate-limited, single-threaded; "
                        "new rows go to <out>/cache/morpheus_new.jsonl, never to the project cache)")
    r.add_argument("--rate-limit", type=float, default=0.5, help="seconds between online Morpheus requests (default 0.5)")
    r.add_argument("--max-online", type=int, default=0, help="cap on online Morpheus queries (0 = no cap)")
    r.add_argument("--stanza-cache", action="append", type=Path, default=None, metavar="DIR",
                   help=f"dir holding stanza_<package>/<stem>.jsonl caches, read-only (default: {DEFAULT_STANZA_CACHE} if present)")
    r.add_argument("--allow-download", action="store_true", help="let Stanza download grc models if missing (off by default)")
    r.add_argument("--system-cache", action="append", type=Path, default=None, metavar="DIR",
                   help="read-only dir(s) holding <system>/<stem>.jsonl token caches written by an earlier run or `precompute` (repeatable)")
    r.add_argument("--precompute-only", action="store_true",
                   help="run the non-reference systems and write their caches under <out>/cache/<system>/, skipping works already cached there; no measurements (restart-safe)")
    r.add_argument("--papyri-normalise", action="store_true",
                   help="apply the Leiden clean-up (papyri.py) to every surface before the systems and the alignment see it; "
                        "the count of touched tokens goes into the summary")
    r.add_argument("--stoicheia-dir", type=Path, default=None,
                   help="local snapshot dir of Ericu950/Stoicheia-tagger-parser (or env STOICHEIA_DIR); never downloaded by the kit")
    r.add_argument("--text-root", action="append", type=Path, default=None, metavar="DIR",
                   help="dir(s) of <stem>.txt running text for systems that need text (repeatable; default: the project's "
                        "galen and reference_corpus extracted_text dirs if present; otherwise surfaces are space-joined)")
    r.add_argument("--m2-sample", type=int, default=0, help="also report M2 on a seeded reservoir sample of N tokens (0 = population only)")
    r.add_argument("--seed", type=int, default=20261105, help="seed for the M2 sample and (unless --m5-seed) the M5 sheet")
    r.add_argument("--m5-n", type=int, default=60, help="random tokens in the blind reviewer sheet (default 60)")
    r.add_argument("--m5-seed", type=int, default=None, help="seed for the M5 sample/shuffle (default: --seed)")
    r.add_argument("--m5-sample-csv", type=Path, default=None,
                   help="use a pre-drawn sample (accuracy_sample_random60.csv format) instead of drawing one")
    r.add_argument("--m3-gold", type=Path, default=None,
                   help=f"LSJ-citation gold CSV for the M3 plugin (default: {DEFAULT_M3_GOLD} if present; Galen only)")
    r.add_argument("--no-m3", action="store_true", help="skip the M3 plugin")
    r.add_argument("--context-width", type=int, default=6, help="tokens of context either side in sheets/worklists (default 6)")
    r.add_argument("--max-disagreements", type=int, default=0, help="cap rows written to disagreements.csv (0 = all)")
    r.add_argument("--label", default="", help="free-text label stored in the summary")
    r.add_argument("--quiet", action="store_true")

    s = sub.add_parser("score", help="score reader answers against a private key",
                       description="Score one or two readers' answer files against the private key (Wilson CI, control gate, Cohen's kappa).")
    s.add_argument("--key", required=True, type=Path, help="private key written by `run --key-out`")
    s.add_argument("--answers", action="append", required=True,
                   help="reader answer CSV with row_id and answer (y/n/unsure) [+ correct_lemma_if_wrong]; repeat for a second "
                        "reader; several batch files for one reader are joined with ';'")
    s.add_argument("--reader-name", action="append", default=None, help="label per --answers (default: file stem)")
    s.add_argument("--out", required=True, type=Path)

    sub.add_parser("systems", help="probe which lemmatizer systems can run here (no downloads)")

    ps = sub.add_parser("papyri-scan", help="report how many tokens of a corpus the papyrological pre-processing would touch",
                        description="Leiden-convention clean-up (brackets, insertions, unread-letter dots, breaks, adscript): counts and examples per flag; nothing is written back.")
    ps.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    ps.add_argument("--subcorpus", action="append", default=[])
    ps.add_argument("--author", action="append", default=[])
    ps.add_argument("--out", type=Path, default=None, help="write the report JSON here as well")

    b = sub.add_parser("batches", help="split a blind sheet into reader batches with a prompt file",
                       description="Split any sheet CSV (M5 reviewer_sheet.csv or a custom sheet) into fixed-size batch "
                                   "CSVs plus one prompt text per batch, so any model or human reader can be run blind in "
                                   "parallel. Answers come back as CSVs that `score` merges (';'-separated per reader).")
    b.add_argument("--sheet", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    b.add_argument("--rows", type=int, default=100, help="rows per batch (default 100)")
    b.add_argument("--instructions", type=Path, default=None,
                   help="instructions text to prepend to every batch prompt (default: the sheet dir's reviewer_instructions.txt if present)")
    b.add_argument("--answer-columns", default="row_id,answer,correct_lemma_if_wrong,note",
                   help="comma list of columns the reader must return (default: the M5 answer file)")
    g = sub.add_parser("lsjgold", help="score your lemmatizer on the LSJ-Gold benchmark",
                       description="Score per-work token caches (DIR/<system>/<stem>.jsonl with {i, lemma}) against the packaged LSJ-Gold "
                                   "loci (CC BY 4.0). Prints a Markdown table; --out writes the full JSON. Works a system lacks count as missing.")
    g.add_argument("--system-cache", action="append", required=True, type=Path, metavar="DIR",
                   help="directory holding one subdirectory per system, each with <stem>.jsonl files (repeatable)")
    g.add_argument("--gold", type=Path, default=None, help="gold CSV (default: the copy shipped in the package)")
    g.add_argument("--out", type=Path, default=None, help="write the scores JSON here")
    g.add_argument("--min-author-rows", type=int, default=100, help="smallest scored-row count for an author column (default 100)")
    g.add_argument("--lsj-index", type=Path, default=None,
                   help="optional LSJ index JSON {lookup_key: {lsj_sense_count}} to add a rich/thin/absent tier stratum")
    return p


def _existing(path: Path | None) -> Path | None:
    return path if path is not None and Path(path).exists() else None


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 0

    if args.cmd == "systems":
        report = {}
        for name in SYSTEM_NAMES:
            d = make_system(name, stanza_cache_dirs=[DEFAULT_STANZA_CACHE] if DEFAULT_STANZA_CACHE.exists() else []).describe()
            report[name] = d
            print(f"{name:16s} {'OK  ' if d['available'] else 'SKIP'} {d['detail']}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "papyri-scan":
        from .corpus import discover_works, load_work
        from .papyri import scan_tokens

        refs = discover_works(args.corpus_root, subcorpora=args.subcorpus, authors=args.author)
        surfaces = []
        for ref in refs:
            w = load_work(ref, None)
            surfaces.extend(t.surface for t in (w.tokens or []))
        rep = scan_tokens(surfaces)
        rep["works"] = len(refs)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "lsjgold":
        from .lsjgold import discover_systems, load_gold, render_markdown, score_systems

        try:
            systems = discover_systems(args.system_cache)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if not systems:
            print("ERROR: no <system>/<stem>.jsonl caches found under --system-cache", file=sys.stderr)
            return 2
        idx = json.loads(args.lsj_index.read_text(encoding="utf-8")) if args.lsj_index else None
        res = score_systems(load_gold(args.gold), systems, min_author_rows=args.min_author_rows, lsj_index=idx)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(render_markdown(res))
        return 0

    if args.cmd == "batches":
        n = write_batches(args.sheet, args.out, args.rows, args.instructions, _csv_list(args.answer_columns))
        print(json.dumps(n, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "score":
        names = args.reader_name or None
        if names and len(names) != len(args.answers):
            parser.error("--reader-name must be given once per --answers")
        answers = [merge_answer_files(a, args.out) for a in args.answers]  # each --answers may be 'b1.csv;b2.csv;...'
        res = score_sheet(args.key, answers, args.out, names)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    # run
    cfg = AuditConfig(
        out_dir=args.out,
        corpus_root=args.corpus_root,
        authors=args.author,
        subcorpora=args.subcorpus,
        max_works=args.max_works,
        systems=args.systems,
        audit_system=args.audit_system,
        key_out=args.key_out,
        controls_path=_existing(args.controls),
        morpheus_caches=(args.morpheus_cache if args.morpheus_cache is not None
                         else ([DEFAULT_MORPHEUS_CACHE] if DEFAULT_MORPHEUS_CACHE.exists() else [])),
        online=args.online,
        rate_limit=args.rate_limit,
        max_online=args.max_online,
        stanza_caches=(args.stanza_cache if args.stanza_cache is not None
                       else ([DEFAULT_STANZA_CACHE] if DEFAULT_STANZA_CACHE.exists() else [])),
        allow_download=args.allow_download,
        stoicheia_dir=args.stoicheia_dir,
        system_caches=args.system_cache or [],
        precompute_only=args.precompute_only,
        papyri_normalise=args.papyri_normalise,
        text_root=args.text_root if args.text_root is not None else [r for r in DEFAULT_TEXT_ROOTS if r.exists()],
        m2_sample=args.m2_sample,
        seed=args.seed,
        m5_n=args.m5_n,
        m5_seed=args.m5_seed,
        m5_sample_csv=args.m5_sample_csv,
        m3_gold=args.m3_gold if args.m3_gold is not None else _existing(DEFAULT_M3_GOLD),
        no_m3=args.no_m3,
        context_width=args.context_width,
        max_disagreements=args.max_disagreements,
        label=args.label,
        command_line=" ".join(shlex.quote(a) for a in (argv if argv is not None else sys.argv[1:])),
        progress=None if args.quiet else (lambda m: print(m, flush=True)),
    )
    if args.controls and cfg.controls_path is None:
        print(f"WARN controls file not found: {args.controls}", file=sys.stderr)
    summary, code = run_audit(cfg)
    if "error" in summary:
        print(f"ERROR: {summary['error']}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
