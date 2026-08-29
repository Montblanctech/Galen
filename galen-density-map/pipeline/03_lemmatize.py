#!/usr/bin/env python3
"""Stage 03: lemmatize extracted Greek with odyCy transformer (spaCy).

Uses ``grc_odycy_joint_trf`` (NOT the small ``_sm`` model, NOT CLTK).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.census import filter_galen_works, load_census, medical_urn_stems
from lib.config import load_config, project_root, resolve_path
from lib.greek_normalize import casefold_greek, nfc, normalize_lemma_orthography
from lib.io_utils import ensure_dir, write_json, write_jsonl
from lib.urns import urn_to_safe_filename

import json

ODYCY_MODEL = "grc_odycy_joint_trf"
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}


def is_greek_token(surface: str) -> bool:
    return any(
        ("\u0370" <= ch <= "\u03ff") or ("\u1f00" <= ch <= "\u1fff") for ch in surface
    )


def get_nlp(model_name: str = ODYCY_MODEL, prefer_neural_lemma: bool = False):
    import spacy

    try:
        nlp = spacy.load(model_name)
    except OSError as exc:
        raise SystemExit(
            f"spaCy model '{model_name}' not installed.\n"
            "Install odyCy transformer wheel from HuggingFace:\n"
            "  pip install https://huggingface.co/chcaa/grc_odycy_joint_trf/"
            "resolve/main/grc_odycy_joint_trf-0.7.0-py3-none-any.whl\n"
            f"Original error: {exc}"
        )
    # Frequency lemmatizer overwrites neural lemmas; for medical OOV it often
    # returns the surface form. Prefer neural for content vocabulary.
    if prefer_neural_lemma and "frequency_lemmatizer" in nlp.pipe_names:
        nlp.disable_pipe("frequency_lemmatizer")
        print("  frequency_lemmatizer DISABLED (prefer trainable neural lemmas)")
    return nlp


def report_model(nlp) -> dict:
    import spacy

    meta = getattr(nlp, "meta", {}) or {}
    pipes = list(nlp.pipe_names)
    has_lemma = any(
        p in pipes
        for p in ("lemmatizer", "trainable_lemmatizer", "frequency_lemmatizer")
    )
    info = {
        "spacy_version": spacy.__version__,
        "model_name": meta.get("name") or ODYCY_MODEL,
        "model_version": meta.get("version", "unknown"),
        "model_lang": meta.get("lang", "grc"),
        "pipe_names": pipes,
        "lemmatizer_enabled": has_lemma,
    }
    print(
        f"Loaded odyCy model: {info['model_name']} v{info['model_version']} "
        f"(spaCy {info['spacy_version']})"
    )
    print(f"  pipes: {pipes}")
    print(f"  lemmatizer_enabled: {has_lemma}")
    if not has_lemma:
        print("  WARNING: no lemmatizer pipe found — passthrough will be ~100%.")
    return info


def split_chunks(text: str, max_chars: int = 4_000) -> list[str]:
    """Transformer allocates heavily; keep chunks small."""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks: list[str] = []
    paragraphs = text.split("\n")
    buf: list[str] = []
    size = 0
    for para in paragraphs:
        add = len(para) + 1
        if size + add > max_chars and buf:
            chunks.append("\n".join(buf))
            buf, size = [para], len(para)
        else:
            buf.append(para)
            size += add
    if buf:
        chunks.append("\n".join(buf))

    final: list[str] = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final.append(ch)
        else:
            for i in range(0, len(ch), max_chars):
                final.append(ch[i : i + max_chars])
    return final


def lemmatize_text(
    nlp,
    text: str,
    fail_log,
    work_id: str,
    max_chars: int = 4_000,
    ortho_counts: dict | None = None,
) -> list[dict]:
    rows: list[dict] = []
    chunks = split_chunks(text, max_chars=max_chars)
    token_index = 0
    surface_window: list[str] = []

    for chunk_i, chunk in enumerate(chunks):
        try:
            doc = nlp(chunk)
        except Exception as exc:
            if len(chunk) > 1000:
                for sub in split_chunks(chunk, max_chars=max(1000, len(chunk) // 2)):
                    try:
                        doc = nlp(sub)
                    except Exception as exc2:
                        fail_log.write(
                            f"{work_id}\tPIPELINE\t{exc2}\tchunk={chunk_i}\t{sub[:120]!r}\n"
                        )
                        continue
                    token_index, surface_window = _consume_doc(
                        doc, rows, token_index, surface_window, fail_log, work_id, ortho_counts
                    )
                continue
            fail_log.write(f"{work_id}\tPIPELINE\t{exc}\tchunk={chunk_i}\t{chunk[:120]!r}\n")
            continue

        token_index, surface_window = _consume_doc(
            doc, rows, token_index, surface_window, fail_log, work_id, ortho_counts
        )
    return rows


def _consume_doc(doc, rows, token_index, surface_window, fail_log, work_id, ortho_counts=None):
    for tok in doc:
        surface = nfc(tok.text)
        if not surface or not is_greek_token(surface):
            continue
        lemma_raw = tok.lemma_ if tok.lemma_ else None
        pos = tok.pos_ or ""
        morph = tok.morph.to_dict() if getattr(tok, "morph", None) is not None else {}

        surface_window.append(surface)
        if lemma_raw is None or lemma_raw == "" or lemma_raw == "None":
            left = " ".join(surface_window[-6:-1])
            fail_log.write(f"{work_id}\tLEMMA_NONE\t{surface}\t… {left} [{surface}]\n")
            lemma_out = None
        else:
            # Casefold lemmas so Ἱπποκράτης / ἱπποκράτης collapse
            lemma_out = casefold_greek(str(lemma_raw))
            # Documented orthographic normalizations only (e.g. γιγγν→γιγν) — not semantic fixes
            lemma_out, fired = normalize_lemma_orthography(lemma_out)
            if fired and ortho_counts is not None:
                for rule in fired:
                    ortho_counts[rule] = ortho_counts.get(rule, 0) + 1

        rows.append(
            {
                "i": token_index,
                "surface": surface,
                "lemma": lemma_out,
                "pos": pos,
                "morph": morph,
            }
        )
        token_index += 1
    return token_index, surface_window


def passthrough_stats(rows: list[dict]) -> dict:
    content = [r for r in rows if r.get("pos") in CONTENT_POS and r.get("lemma")]
    if not content:
        return {
            "content_tokens": 0,
            "passthrough_tokens": 0,
            "passthrough_pct": 0.0,
        }
    pt = sum(
        1
        for r in content
        if casefold_greek(r["surface"]) == casefold_greek(r["lemma"])
    )
    return {
        "content_tokens": len(content),
        "passthrough_tokens": pt,
        "passthrough_pct": round(100.0 * pt / len(content), 2),
    }


def _accumulate_passthrough(acc: dict, rows: list[dict]) -> None:
    """Incremental passthrough counters — do NOT retain token rows (OOM on full ref)."""
    for r in rows:
        if r.get("pos") not in CONTENT_POS or not r.get("lemma"):
            continue
        acc["content_tokens"] += 1
        if casefold_greek(r["surface"]) == casefold_greek(r["lemma"]):
            acc["passthrough_tokens"] += 1


def process_dir(
    nlp,
    src: Path,
    dest: Path,
    fail_log_path: Path,
    max_files: int | None = None,
    max_chars: int = 4_000,
    model_info: dict | None = None,
    skip_existing: bool = False,
    stem_whitelist: set[str] | None = None,
    stem_blacklist: set[str] | None = None,
) -> dict:
    ensure_dir(dest)
    total_tokens = 0
    failed_lemmas = 0
    files = 0
    skipped = 0
    pt_acc = {"content_tokens": 0, "passthrough_tokens": 0}
    ortho_counts: dict[str, int] = {}
    paths = sorted(p for p in src.glob("*.txt") if not p.name.startswith("_"))
    # Drop non-Greek edition leaks (eng/lat/deu) that slipped past the URN filter
    paths = [
        p
        for p in paths
        if not any(tag in p.name.lower() for tag in ("-eng", ".eng", "-lat", ".lat", "-deu", ".deu"))
    ]
    if stem_whitelist is not None:
        paths = [p for p in paths if p.stem in stem_whitelist]
    if stem_blacklist is not None:
        paths = [p for p in paths if p.stem not in stem_blacklist]
    if max_files is not None:
        paths = paths[:max_files]
    # Append on resume so prior failures remain visible
    fail_mode = "a" if skip_existing and fail_log_path.exists() else "w"
    with fail_log_path.open(fail_mode, encoding="utf-8") as fail_log:
        for txt_path in paths:
            out = dest / (txt_path.stem + ".jsonl")
            if skip_existing and out.exists() and out.stat().st_size > 0:
                # Only skip if this file already has morph (post-cleanup schema)
                try:
                    first = out.open(encoding="utf-8").readline()
                    has_morph = bool(first) and "morph" in json.loads(first)
                except Exception:
                    has_morph = False
                if has_morph:
                    skipped += 1
                    files += 1
                    print(f"  SKIP existing {txt_path.name}", flush=True)
                    continue
            text = txt_path.read_text(encoding="utf-8")
            rows = lemmatize_text(
                nlp, text, fail_log, txt_path.stem, max_chars=max_chars, ortho_counts=ortho_counts
            )
            write_jsonl(out, rows)
            files += 1
            total_tokens += len(rows)
            failed_lemmas += sum(1 for r in rows if not r["lemma"])
            pt = passthrough_stats(rows)
            _accumulate_passthrough(pt_acc, rows)
            print(
                f"  {txt_path.name}: {len(rows)} tokens | "
                f"content-passthrough {pt['passthrough_pct']}% "
                f"({pt['passthrough_tokens']}/{pt['content_tokens']})",
                flush=True,
            )
            del rows  # free promptly; do not retain corpus in RAM
    rate = (failed_lemmas / total_tokens) if total_tokens else 0.0
    pt_pct = (
        round(100.0 * pt_acc["passthrough_tokens"] / pt_acc["content_tokens"], 2)
        if pt_acc["content_tokens"]
        else 0.0
    )
    if ortho_counts:
        print(f"  lemma orthography normalizations applied: {ortho_counts}", flush=True)
    summary = {
        "files": files,
        "skipped_existing": skipped,
        "total_tokens": total_tokens,
        "failed_lemmas": failed_lemmas,
        "failure_rate": round(rate, 4),
        "failure_rate_pct": round(rate * 100, 2),
        "warning": rate > 0.05,
        "backend": f"spacy:{ODYCY_MODEL}",
        "model": model_info or {},
        "content_word_passthrough_pct": pt_pct,
        "content_word_passthrough_tokens": pt_acc["passthrough_tokens"],
        "content_word_tokens": pt_acc["content_tokens"],
        "lemma_orthography_counts": ortho_counts,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--include-reference", action="store_true")
    parser.add_argument(
        "--skip-galen",
        action="store_true",
        help="Skip Galen subset (use when re-running reference only)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Resume: skip JSONL outputs that already include morph",
    )
    parser.add_argument(
        "--nonmedical-only",
        action="store_true",
        help="Only lemmatize non-medical Galen texts into lemmatized/galen_nonmedical/",
    )
    parser.add_argument("--max-files", type=int, default=None, help="Limit files (smoke tests)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    model_name = cfg.get("odycy_model", ODYCY_MODEL)
    max_chars = int(cfg.get("lemmatize_max_chars", 4000))
    prefer_neural = bool(cfg.get("odycy_prefer_neural_lemma", True))

    print(f"Loading odyCy spaCy model {model_name}...")
    nlp = get_nlp(model_name, prefer_neural_lemma=prefer_neural)
    model_info = report_model(nlp)
    model_info["frequency_lemmatizer_disabled"] = prefer_neural
    if model_info["model_name"] and "trf" not in str(model_info["model_name"]) and "trf" not in model_name:
        print(
            f"WARNING: expected transformer model (*_trf*), got {model_info['model_name']}. "
            "Passthrough may stay ~28%."
        )

    extracted = resolve_path(cfg, "extracted_text")
    lemmatized = resolve_path(cfg, "lemmatized")
    census = load_census((project_root() / cfg["census_file"]).resolve())
    medical_stems = medical_urn_stems(cfg, census)
    all_stems = {
        urn_to_safe_filename(w["urn"])
        for w in filter_galen_works(cfg, census, all_categories=True)
    }
    nonmedical_stems = all_stems - medical_stems

    do_medical = not args.skip_galen and not args.nonmedical_only
    do_nonmedical = (not args.skip_galen or args.nonmedical_only) and bool(nonmedical_stems)
    # --skip-galen alone skips both Galen sides; --nonmedical-only forces nonmedical only.
    if args.skip_galen and not args.nonmedical_only:
        do_nonmedical = False

    if do_medical:
        galen_out = lemmatized / "galen"
        summary = process_dir(
            nlp,
            extracted,
            galen_out,
            lemmatized / "_lemmatize_failures.log",
            args.max_files,
            max_chars=max_chars,
            model_info=model_info,
            skip_existing=args.skip_existing,
            stem_whitelist=medical_stems,
        )
        write_json(lemmatized / "_lemmatize_summary_galen.json", summary)
        print(
            f"Galen (medical) lemmatize: files={summary['files']} tokens={summary['total_tokens']} "
            f"failure_rate={summary['failure_rate_pct']}% | "
            f"content-word passthrough={summary['content_word_passthrough_pct']}% "
            f"({summary['content_word_passthrough_tokens']}/{summary['content_word_tokens']})"
        )
        if summary["content_word_passthrough_pct"] >= 28.0:
            print(
                "WARNING: content-word passthrough still >= 28%. "
                "Confirm grc_odycy_joint_trf is loaded and lemmatizer pipe is enabled."
            )
    else:
        print("Skipping medical Galen lemmatize.")

    # Non-medical Galen → separate dir so medical frequency stays unpolluted
    if do_nonmedical:
        nonmed_out = resolve_path(cfg, "lemmatized_galen_nonmedical")
        print(f"Lemmatizing {len(nonmedical_stems)} non-medical Galen works -> {nonmed_out}")
        nsum = process_dir(
            nlp,
            extracted,
            nonmed_out,
            lemmatized / "_lemmatize_failures_galen_nonmedical.log",
            args.max_files,
            max_chars=max_chars,
            model_info=model_info,
            skip_existing=args.skip_existing,
            stem_whitelist=nonmedical_stems,
        )
        write_json(lemmatized / "_lemmatize_summary_galen_nonmedical.json", nsum)
        print(
            f"Galen (nonmedical) lemmatize: files={nsum['files']} "
            f"tokens={nsum['total_tokens']} "
            f"passthrough={nsum['content_word_passthrough_pct']}%"
        )

    if args.include_reference:
        ref_src = resolve_path(cfg, "reference_corpus") / "extracted_text"
        ref_out = lemmatized / "reference"
        if ref_src.exists():
            rsum = process_dir(
                nlp,
                ref_src,
                ref_out,
                lemmatized / "_lemmatize_failures_reference.log",
                args.max_files,
                max_chars=max_chars,
                model_info=model_info,
                skip_existing=args.skip_existing,
            )
            write_json(lemmatized / "_lemmatize_summary_reference.json", rsum)
            print(
                f"Reference lemmatize: files={rsum['files']} tokens={rsum['total_tokens']} "
                f"passthrough={rsum['content_word_passthrough_pct']}%"
            )
        else:
            print(f"No reference extracted_text at {ref_src}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
