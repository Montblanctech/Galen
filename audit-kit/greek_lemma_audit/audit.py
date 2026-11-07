"""The audit engine: one pass over the corpus, every measurement, one JSON.

``run_audit(cfg)`` streams works one at a time (nothing corpus-wide is held),
runs every available system on each work, feeds M1/M2/M3/M5 accumulators, then
finalises and writes:

* ``<out>/audit_summary.json`` — every number with its N and CI, seeds, tool versions;
* ``<out>/disagreements.csv`` — frequency-ranked cross-system worklist (M2);
* ``<out>/reviewer_sheet.csv`` (+ private key at ``--key-out``) — blind M5 sheet;
* ``<out>/audit_report.md`` — one paragraph written from the numbers;
* ``<out>/m1_*.csv`` / ``m3_rescored_*.csv`` — supporting worklists.
"""

from __future__ import annotations

import datetime as _dt
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import KIT_NAME, __version__
from .corpus import Token, WorkRef, discover_works, load_work
from .m1 import M1Accumulator
from .m2 import M2Accumulator
from .m5 import M5SheetBuilder, read_csv
from .morpheus import MorpheusStore
from .normalize import BLIND_KEY_BACKEND
from .plugins.lsj_galen import LsjGalenPlugin
from .systems import make_system

KIT_ROOT = Path(__file__).resolve().parents[1]  # audit-kit/
REPO_ROOT = KIT_ROOT.parent  # Galen/
GDM = REPO_ROOT / "galen-density-map"
DEFAULT_CORPUS_ROOT = GDM / "data" / "lemmatized"
DEFAULT_MORPHEUS_CACHE = GDM / "data" / "qc" / "h3m" / "cache" / "morpheus_by_surface.jsonl"
DEFAULT_STANZA_CACHE = GDM / "data" / "qc" / "h3m" / "cache"
DEFAULT_TEXT_ROOT = GDM / "data" / "extracted_text"
DEFAULT_TEXT_ROOTS = [DEFAULT_TEXT_ROOT, GDM / "data" / "reference_corpus" / "extracted_text"]
DEFAULT_M3_GOLD = GDM / "data" / "qc" / "h3m" / "m3_lsj_citation_gold.csv"


@dataclass
class AuditConfig:
    out_dir: Path
    corpus_root: Path = DEFAULT_CORPUS_ROOT
    authors: list[str] = field(default_factory=list)
    subcorpora: list[str] = field(default_factory=list)
    max_works: int = 0
    systems: list[str] = field(default_factory=lambda: ["reference"])
    audit_system: str | None = None
    key_out: Path | None = None
    controls_path: Path | None = None
    morpheus_caches: list[Path] = field(default_factory=list)
    online: bool = False
    rate_limit: float = 0.5
    max_online: int = 0
    stanza_caches: list[Path] = field(default_factory=list)
    allow_download: bool = False
    stoicheia_dir: Path | None = None
    system_caches: list[Path] = field(default_factory=list)  # read-only dirs holding <system>/<stem>.jsonl
    precompute_only: bool = False  # run the systems, write caches, skip all measurements
    papyri_normalise: bool = False  # Leiden clean-up of surfaces before the systems see them (papyri.normalize_token)
    text_root: Path | list[Path] | None = None
    m2_sample: int = 0
    seed: int = 20261105
    m5_n: int = 60
    m5_seed: int | None = None
    m5_sample_csv: Path | None = None
    m3_gold: Path | None = None
    no_m3: bool = False
    context_width: int = 6
    max_disagreements: int = 0
    label: str = ""
    command_line: str = ""
    progress: Callable[[str], None] | None = None


def _say(cfg: AuditConfig, msg: str) -> None:
    if cfg.progress:
        cfg.progress(msg)


def _tool_versions(systems: dict[str, Any], store: MorpheusStore) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kit": {"name": KIT_NAME, "version": __version__},
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "blind_key_backend": BLIND_KEY_BACKEND,
        "morpheus": {k: store.info()[k] for k in ("engine", "creator", "docker_image", "base_url", "online")},
        "systems": {name: s.describe() for name, s in systems.items()},
    }
    try:
        import beta_code  # noqa: F401
        from importlib.metadata import version as _v

        out["beta_code"] = _v("beta-code")
    except Exception:
        out["beta_code"] = None
    return out



def read_system_cache(dirs: list[Path], system: str, stem: str) -> list[Token] | None:
    """``<dir>/<system>/<stem>.jsonl`` -> tokens, first hit wins; None when absent."""
    for d in dirs:
        p = Path(d) / system / f"{stem}.jsonl"
        if p.exists():
            out: list[Token] = []
            with p.open(encoding="utf-8") as fh:
                for n, line in enumerate(fh):
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    out.append(Token(i=int(r.get("i", n)), surface=r.get("surface") or "", lemma=r.get("lemma") or "", pos=r.get("pos") or ""))
            return out
    return None


def write_system_cache(cache_dir: Path, system: str, stem: str, toks: list[Token]) -> None:
    d = Path(cache_dir) / system
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{stem}.jsonl.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        for t in toks:
            fh.write(json.dumps({"i": t.i, "surface": t.surface, "lemma": t.lemma, "pos": t.pos}, ensure_ascii=False) + "\n")
    tmp.replace(d / f"{stem}.jsonl")


def run_audit(cfg: AuditConfig) -> tuple[dict[str, Any], int]:
    """Run the audit. Returns (summary, exit_code)."""
    t0 = time.time()
    out_dir = Path(cfg.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "kit": {"name": KIT_NAME, "version": __version__, "date": _dt.date.today().isoformat(),
                "label": cfg.label, "command_line": cfg.command_line, "report_only": True},
    }

    # ---- corpus -----------------------------------------------------------
    try:
        refs = discover_works(cfg.corpus_root, authors=cfg.authors, subcorpora=cfg.subcorpora, max_works=cfg.max_works)
    except FileNotFoundError as exc:
        summary["error"] = str(exc)
        _write(out_dir, summary)
        return summary, 2
    if not refs:
        summary["error"] = f"no .jsonl/.txt works under {cfg.corpus_root} for authors={cfg.authors or 'all'} subcorpora={cfg.subcorpora or 'all'}"
        _write(out_dir, summary)
        return summary, 2
    _say(cfg, f"corpus: {len(refs)} works under {cfg.corpus_root} (authors={cfg.authors or 'all'}, subcorpora={cfg.subcorpora or 'all'})")

    # ---- systems ----------------------------------------------------------
    kit_cache = out_dir / "cache"
    systems: dict[str, Any] = {}
    for name in cfg.systems:
        systems[name] = make_system(name, stanza_cache_dirs=cfg.stanza_caches, write_cache_dir=kit_cache,
                                    allow_download=cfg.allow_download, stoicheia_dir=cfg.stoicheia_dir)
    ran: list[str] = []
    sys_report: dict[str, Any] = {}
    for name, s in systems.items():
        av = s.availability()
        sys_report[name] = {"status": "available" if av.ok else "skipped", **av.as_dict(), "works_with_output": 0,
                            "tokens": 0, "works_skipped": []}
        _say(cfg, f"system {name}: {'OK' if av.ok else 'SKIP'} - {av.detail}")
        if av.ok:
            ran.append(name)
    audit = cfg.audit_system or (cfg.systems[0] if cfg.systems else "reference")
    if audit not in ran:
        summary["systems"] = sys_report
        summary["error"] = f"audit system {audit!r} is not available here: {sys_report.get(audit, {}).get('detail', 'not requested')}"
        _write(out_dir, summary)
        return summary, 2

    # ---- stores & accumulators ---------------------------------------------
    store = MorpheusStore(cfg.morpheus_caches, write_path=kit_cache / "morpheus_new.jsonl", online=cfg.online,
                          rate_limit=cfg.rate_limit, max_online=cfg.max_online)
    _say(cfg, f"morpheus: {len(store)} cached surfaces from {len(cfg.morpheus_caches)} cache file(s); online={cfg.online}")
    controls = read_csv(cfg.controls_path) if cfg.controls_path else []
    m1 = M1Accumulator(ran)
    m2 = M2Accumulator(audit, ran, sample_n=cfg.m2_sample, seed=cfg.seed, context_width=cfg.context_width,
                       out_dir=out_dir, max_rows=cfg.max_disagreements)
    m5 = M5SheetBuilder(cfg.m5_n, cfg.m5_seed if cfg.m5_seed is not None else cfg.seed, cfg.context_width,
                        controls=controls, sample_csv=cfg.m5_sample_csv)
    m3 = None if cfg.no_m3 else LsjGalenPlugin(cfg.m3_gold, ran)

    # ---- the pass -----------------------------------------------------------
    corpus_stats: dict[str, Any] = {"n_works": 0, "n_tokens_audit": 0, "by_author": {}, "by_subcorpus": {},
                                    "text_source": {"file": 0, "surfaces_joined": 0}, "kinds": {"jsonl": 0, "text": 0}}
    for n, ref in enumerate(refs, 1):
        work = load_work(ref, cfg.text_root)
        if cfg.papyri_normalise and work.tokens is not None:
            from .papyri import normalize_token

            cleaned, touched = [], 0
            for t in work.tokens:
                r = normalize_token(t.surface)
                touched += int(r.changed or bool(r.flags))
                cleaned.append(Token(i=t.i, surface=r.form or t.surface, lemma=t.lemma, pos=t.pos))
            work.tokens = cleaned
            work.text = None  # text-fed systems get the cleaned surfaces, not the raw edition text
            work.text_source = "surfaces_joined_papyri_normalised"
            corpus_stats.setdefault("papyri_normalised_tokens", 0)
            corpus_stats["papyri_normalised_tokens"] += touched
        outputs: dict[str, list[Token]] = {}
        for name in ran:
            s = systems[name]
            toks = read_system_cache(cfg.system_caches + [kit_cache], name, work.stem) if name != "reference" else None
            if toks is None:
                if cfg.precompute_only and name == "reference":
                    continue
                toks = s.run(work)
                if toks is None:
                    sys_report[name]["works_skipped"].append({"work": work.stem, "reason": s.last_skip_reason})
                    continue
                if name not in ("reference",) and not name.startswith("stanza-"):
                    write_system_cache(kit_cache, name, work.stem, toks)
            outputs[name] = toks
            sys_report[name]["works_with_output"] += 1
            sys_report[name]["tokens"] += len(toks)
        if cfg.precompute_only:
            if cfg.progress:
                cfg.progress(f"  [{n}/{len(refs)}] {work.stem} cached: {', '.join(k for k in outputs if k != 'reference')}")
            continue
        corpus_stats["n_works"] += 1
        corpus_stats["kinds"][ref.kind] += 1
        if work.text_source in corpus_stats["text_source"]:
            corpus_stats["text_source"][work.text_source] = corpus_stats["text_source"].get(work.text_source, 0) + 1
        anchor = outputs.get(audit)
        n_tok = len(anchor) if anchor else 0
        corpus_stats["n_tokens_audit"] += n_tok
        ba = corpus_stats["by_author"].setdefault(ref.author, {"works": 0, "tokens": 0})
        ba["works"] += 1
        ba["tokens"] += n_tok
        bs = corpus_stats["by_subcorpus"].setdefault(ref.subcorpus, {"works": 0, "tokens": 0})
        bs["works"] += 1
        bs["tokens"] += n_tok
        m1.consume(work, outputs)
        m2.consume(work, outputs)
        if anchor is not None:
            m5.consume(work, anchor)
        if m3 is not None:
            m3.consume(work, outputs)
        if n % 10 == 0 or n == len(refs):
            _say(cfg, f"  [{n}/{len(refs)}] {work.stem} tokens={n_tok} systems={sorted(outputs)}")

    if cfg.precompute_only:
        summary = {"precompute_only": True, "works": len(refs), "systems": {k: v for k, v in sys_report.items()},
                   "cache_dir": str(kit_cache), "elapsed_s": round(time.time() - t0, 1)}
        (out_dir / "precompute_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        return summary, 0

    # ---- Morpheus online fill ------------------------------------------------
    if cfg.online:
        q = store.fetch_missing(sorted(m1.unique_surfaces()), progress=lambda m: _say(cfg, m))
        _say(cfg, f"morpheus online: queried {q} surfaces")

    # ---- finalise --------------------------------------------------------------
    summary["corpus"] = {"root": str(cfg.corpus_root), "author_filter": cfg.authors, "subcorpus_filter": cfg.subcorpora,
                         "text_root": ([str(r) for r in cfg.text_root] if isinstance(cfg.text_root, list) else str(cfg.text_root)) if cfg.text_root else None, **corpus_stats}
    summary["systems"] = {**sys_report, "audit_system": audit, "ran": ran}
    summary["seeds"] = {"m2_sample": cfg.seed if cfg.m2_sample else None,
                        "m5_sheet": cfg.m5_seed if cfg.m5_seed is not None else cfg.seed}
    summary["m1_admissibility"] = m1.finalize(store, out_dir, controls or None)
    summary["m2_agreement"] = m2.finalize()
    summary["m3_lsj_citation_gold"] = (m3.finalize(out_dir, cfg.authors) if m3 is not None
                                       else {"status": "skipped", "reason": "--no-m3"})
    summary["m5_reviewer_sheet"] = m5.finalize(out_dir, cfg.key_out, m2.disagreement_keys)
    summary["m5_reviewer_sheet"]["scored"] = False
    summary["bounded_range"] = bounded_range(summary, audit)
    summary["tool_versions"] = _tool_versions(systems, store)
    summary["runtime_seconds"] = round(time.time() - t0, 1)
    summary["files"] = {"audit_summary": "audit_summary.json", "disagreements": "disagreements.csv",
                        "reviewer_sheet": summary["m5_reviewer_sheet"].get("sheet"), "report": "audit_report.md"}
    _write(out_dir, summary)
    (out_dir / "audit_report.md").write_text(write_report(summary), encoding="utf-8")
    _say(cfg, f"done in {summary['runtime_seconds']}s -> {out_dir / 'audit_summary.json'}")
    return summary, 0


def _write(out_dir: Path, summary: dict[str, Any]) -> None:
    (out_dir / "audit_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
                                               encoding="utf-8")


def bounded_range(summary: dict[str, Any], audit: str) -> dict[str, Any]:
    """Floor (M1), upper-ish bound (M2), rare-stratum point estimate (M3), blind sheet (M5)."""
    out: dict[str, Any] = {"audit_system": audit}
    m1 = ((summary.get("m1_admissibility") or {}).get("systems") or {}).get(audit) or {}
    tw = m1.get("token_weighted") or {}
    if tw:
        out["floor_m1"] = {"admissible_pct_of_analyzable": tw.get("admissible_pct_of_analyzable"),
                           "wilson95": [tw.get("admissible_wilson95_lo_pct"), tw.get("admissible_wilson95_hi_pct")],
                           "n_analyzable_tokens": tw.get("analyzable"), "no_analysis_pct_of_all": tw.get("no_analysis_pct_of_all"),
                           "not_in_cache_pct_of_all": tw.get("not_in_cache_pct_of_all"),
                           "floor_ready": (m1.get("gates") or {}).get("floor_ready"),
                           "reading": "share of analyzable tokens whose lemma is morphologically possible; inadmissible = near-certain error"}
    m2 = summary.get("m2_agreement") or {}
    pop = m2.get("population") or {}
    if m2.get("status") == "ok" and pop.get("n_aligned"):
        cons = pop.get(f"{audit}_vs_consensus_of_others") or {}
        out["upper_bound_m2"] = {"audit_vs_consensus_pct": cons.get("agree_pct"), "wilson95": [cons.get("wilson95_lo_pct"), cons.get("wilson95_hi_pct")],
                                 "n_unanimous_others": cons.get("n_unanimous_others"),
                                 "pairwise": {k: v.get("agree_pct") for k, v in (pop.get("pairwise") or {}).items() if audit in k},
                                 "n_aligned": pop.get("n_aligned"), "alignment_loss_pct": pop.get("alignment_loss_pct"),
                                 "reading": m2.get("honesty_clause")}
    m3 = summary.get("m3_lsj_citation_gold") or {}
    if m3.get("status") == "ok":
        s = (m3.get("systems") or {}).get(audit) or {}
        blind = s.get("match_blind") or {}
        out["rare_stratum_m3"] = {"match_blind_pct": blind.get("match_pct"), "wilson95": [blind.get("wilson95_lo_pct"), blind.get("wilson95_hi_pct")],
                                  "n_scored": blind.get("n"), "match_strict_pct": (s.get("match_strict") or {}).get("match_pct"),
                                  "project_artifact": m3.get("project_artifact"), "reading": m3.get("bias_caveat")}
    m5 = summary.get("m5_reviewer_sheet") or {}
    out["blind_sheet_m5"] = {"status": m5.get("status"), "n_random": m5.get("n_random"), "n_controls": m5.get("n_controls"),
                             "scored": False, "reading": "score with `greek-lemma-audit score` once readers return the sheet"}
    return out


def _fmt(x: Any) -> str:
    return "n/a" if x is None else f"{x}"


def write_report(summary: dict[str, Any]) -> str:
    c = summary.get("corpus") or {}
    br = summary.get("bounded_range") or {}
    audit = br.get("audit_system", "?")
    ran = (summary.get("systems") or {}).get("ran") or []
    sysrep = summary.get("systems") or {}
    skipped = [f"{n} ({v.get('detail','')})" for n, v in sysrep.items() if isinstance(v, dict) and v.get("status") == "skipped"]
    parts: list[str] = []
    parts.append(f"Over {c.get('n_works')} works and {c.get('n_tokens_audit'):,} tokens of the `{audit}` system "
                 f"(authors: {', '.join(sorted(c.get('by_author', {})))}; systems run: {', '.join(ran)}"
                 + (f"; skipped: {'; '.join(skipped)}" if skipped else "") + "),")
    f = br.get("floor_m1")
    if f:
        parts.append(f"lemma admissibility against the rule-based Morpheus analyzer is **{_fmt(f['admissible_pct_of_analyzable'])}%** of "
                     f"analyzable tokens (Wilson 95% {_fmt(f['wilson95'][0])}–{_fmt(f['wilson95'][1])}, N = {f['n_analyzable_tokens']:,}; "
                     f"floor on correctness; {_fmt(f['no_analysis_pct_of_all'])}% of tokens had no Morpheus analysis and "
                     f"{_fmt(f['not_in_cache_pct_of_all'])}% were never looked up, both excluded"
                     + ("" if f.get("floor_ready") else "; coverage too low, floor provisional") + ");")
    u = br.get("upper_bound_m2")
    if u:
        pw = ", ".join(f"{k.replace('__', '↔')} {v}%" for k, v in (u.get("pairwise") or {}).items())
        parts.append(f"cross-system agreement is **{_fmt(u['audit_vs_consensus_pct'])}%** of the {u['n_unanimous_others']:,} aligned tokens on which the other "
                     f"systems were unanimous (pairwise: {pw}; {_fmt(u['alignment_loss_pct'])}% of tokens dropped to alignment loss; an "
                     f"optimistic bound, since training treebanks overlap);")
    else:
        m2s = summary.get("m2_agreement") or {}
        why = ""
        if len(ran) > 1 and m2s.get("works_skipped"):
            reasons = sorted({w.get("reason", "") for w in m2s["works_skipped"]})
            why = f" ({len(m2s['works_skipped'])} works skipped: {'; '.join(reasons)[:200]})"
        parts.append(f"no second system produced output for this selection{why}, so no cross-system upper bound is reported;")
    r = br.get("rare_stratum_m3")
    if r and r.get("n_scored"):
        parts.append(f"on the rare/LSJ-cited stratum, {audit} matches the lexicographers' headword in **{_fmt(r['match_blind_pct'])}%** "
                     f"accent-blind (Wilson 95% {_fmt(r['wilson95'][0])}–{_fmt(r['wilson95'][1])}, N = {r['n_scored']}; "
                     f"{_fmt(r['match_strict_pct'])}% accent-strict) of surface-unique relocated citation loci — stratum accuracy, not overall accuracy;")
    else:
        parts.append("the LSJ-citation point estimate does not apply to this selection (Galen-only plugin);")
    m5 = br.get("blind_sheet_m5") or {}
    if m5.get("status") == "ok":
        parts.append(f"a blind reviewer sheet of {m5['n_random']} random tokens salted with {m5['n_controls']} controls was written and awaits scoring.")
    else:
        parts.append("no blind reviewer sheet was written (" + _fmt((summary.get('m5_reviewer_sheet') or {}).get('reason')) + ").")
    m2 = summary.get("m2_agreement") or {}
    dis = m2.get("disagreements") or {}
    tail = ""
    if dis.get("n_rows"):
        tail = (f" The disagreement worklist holds {dis['n_rows']:,} tokens ({dis.get('g2a_class_counts')}), of which "
                f"{dis.get(f'n_{audit}_disagrees_with_unanimous_others', 0):,} have {audit} alone against a unanimous rest — the first stop for a human reader.")
    head = f"# Lemmatizer audit — {audit} ({summary.get('kit', {}).get('date')})\n\n"
    meta = (f"\n\n*{KIT_NAME} {__version__}; runtime {summary.get('runtime_seconds')} s; seeds {summary.get('seeds')}; "
            f"every number above carries its N and CI in `audit_summary.json`. Report-only: nothing in the corpus was changed.*\n")
    return head + " ".join(parts) + tail + meta
