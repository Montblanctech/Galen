"""M5 — blind reviewer sheet (builder) and scorer.

Builder follows ``galen-density-map/pipeline/h3m/m5_build_sheets.py`` and
``h3_qc_protocol.md`` §2 (attribution): a frozen random sample of N tokens of
the audit system (seeded reservoir, or a pre-drawn sample CSV such as the
project's ``accuracy_sample_random60.csv``), salted with the rows of a controls
file if given (reviewer columns only), shuffled with the seed. The private key
(row_id -> kind, control id, expected answer, M2 flag) is written **only** to the
path the user passes — keep it outside anything you publish before scoring.

Scorer follows ``m5_score.py`` exactly: rate on the random rows only; ``y`` rate
with ``unsure`` counted as not-``y`` (lower bound) and excluded (point
estimate); Wilson 95% CI; the §3 gate per reader (FAIL if the non-word control
is missed, if >=2 of the unambiguous wrong-plants are missed, or if any
right-anchor is marked wrong; accent-only controls are diagnostic); Cohen's κ
between two readers (3 categories, and y/n with unsure as n).
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from .corpus import Token, Work, author_of, context_window
from .normalize import nfc
from .stats import cohen_kappa, wilson_ci

REVIEWER_COLS = ["surface_form", "lemma_produced", "pos", "one_line_context", "work_stem", "token_index"]
ANSWER_COLS = ["lemma_correct(y/n/unsure)", "correct_lemma_if_wrong", "note"]
KEY_COLS = ["row_id", "kind", "control_id", "control_type", "strength", "gate_role", "expected", "expected_lemma",
            "surface_form", "lemma_produced", "pos", "work_stem", "token_index", "author", "m2_flag"]
INSTRUCTIONS = (
    "You are checking whether lemma_produced is the correct dictionary headword (LSJ-style lemma) for surface_form "
    "in the bracketed context. Judge the headword, not the gloss. Accent and breathing count: a lemma with the wrong "
    "accent is wrong (mark n, give the right one). Elided or crasis forms: the headword of the underlying word. If the "
    "lemma is not a Greek word at all, mark n and give the real headword. Mark unsure only when the context genuinely "
    "does not decide between two real headwords. Some rows are quality-control items; you are not told which. Answer "
    "every row on its merits. Open nothing but the sheet."
)


def gate_role(control: dict[str, str]) -> str:
    ctype = control.get("control_type", "")
    strength = control.get("strength", "")
    if ctype == "right_anchor":
        return "anchor"
    if ctype == "wrong_plant" and strength == "accent":
        return "wrong_accent"
    if ctype == "wrong_plant":
        if control.get("control_id") == "C01" or "non-word" in control.get("provenance", ""):
            return "nonword"
        return "wrong_unambiguous"
    return "other"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [{(k or "").strip(): (v or "") for k, v in r.items()} for r in csv.DictReader(fh)]


class M5SheetBuilder:
    def __init__(self, n: int, seed: int, context_width: int = 6, *, controls: list[dict[str, str]] | None = None,
                 sample_csv: Path | None = None) -> None:
        self.n = n
        self.seed = seed
        self.width = context_width
        self.controls = controls or []
        self.sample_csv = sample_csv
        self.rng = random.Random(seed)
        self.reservoir: list[dict[str, Any]] = []
        self.seen = 0

    def consume(self, work: Work, tokens: list[Token]) -> None:
        if self.sample_csv is not None or self.n <= 0:
            return
        for p, t in enumerate(tokens):
            if not t.surface or not t.lemma:
                continue
            self.seen += 1
            item = {"surface_form": t.surface, "lemma_produced": t.lemma, "pos": t.pos,
                    "one_line_context": context_window(tokens, p, self.width), "work_stem": work.stem,
                    "token_index": t.i, "author": work.author}
            if len(self.reservoir) < self.n:
                self.reservoir.append(item)
            else:
                j = self.rng.randint(1, self.seen)
                if j <= self.n:
                    self.reservoir[j - 1] = item

    def finalize(self, out_dir: Path, key_path: Path | None, m2_flags: set[tuple[str, int]] | None = None) -> dict[str, Any]:
        if self.sample_csv is not None:
            sample = read_csv(self.sample_csv)
            for r in sample:
                if not r.get("author"):
                    r["author"] = author_of(r.get("work_stem", ""))
            source = f"pre-drawn sample {self.sample_csv.name}"
        else:
            sample = sorted(self.reservoir, key=lambda r: (r["work_stem"], int(r["token_index"])))
            source = f"Algorithm-R reservoir over audit-system tokens (seed {self.seed}, population {self.seen})"
        if not sample:
            return {"status": "skipped", "reason": "no tokens to sample"}
        if key_path is None:
            return {"status": "skipped", "reason": "no --key-out given; the blind sheet needs a private key path outside "
                                                   "the published tree", "n_random": len(sample)}
        rows: list[dict[str, Any]] = []
        for r in sample:
            rows.append({"kind": "random", "control_id": "", "control_type": "", "strength": "", "gate_role": "",
                         "expected": "", "expected_lemma": "", "author": r.get("author", ""),
                         **{c: r.get(c, "") for c in REVIEWER_COLS}})
        for c in self.controls:
            rows.append({"kind": "control", "control_id": c.get("control_id", ""), "control_type": c.get("control_type", ""),
                         "strength": c.get("strength", ""), "gate_role": gate_role(c),
                         "expected": c.get("EXPECTED_answer", ""), "expected_lemma": c.get("EXPECTED_correct_lemma", ""),
                         "author": "", **{k: c.get(k, "") for k in REVIEWER_COLS}})
        shuffle_rng = random.Random(self.seed)
        shuffle_rng.shuffle(rows)
        m2_flags = m2_flags or set()
        out_dir.mkdir(parents=True, exist_ok=True)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        sheet = out_dir / "reviewer_sheet.csv"
        with sheet.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_id", *REVIEWER_COLS, *ANSWER_COLS])
            for n, r in enumerate(rows, 1):
                w.writerow([f"A{n:03d}", *[r[c] for c in REVIEWER_COLS], "", "", ""])
        with key_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(KEY_COLS)
            for n, r in enumerate(rows, 1):
                try:
                    flag = (r["work_stem"], int(r["token_index"])) in m2_flags
                except (TypeError, ValueError):
                    flag = False
                w.writerow([f"A{n:03d}", r["kind"], r["control_id"], r["control_type"], r["strength"], r["gate_role"],
                            r["expected"], r["expected_lemma"], r["surface_form"], r["lemma_produced"], r["pos"],
                            r["work_stem"], r["token_index"], r["author"], "y" if flag else "n"])
        (out_dir / "reviewer_instructions.txt").write_text(INSTRUCTIONS + "\n", encoding="utf-8")
        return {"status": "ok", "sheet": sheet.name, "private_key": str(key_path), "instructions": "reviewer_instructions.txt",
                "n_rows": len(rows), "n_random": len(sample), "n_controls": len(self.controls), "seed": self.seed,
                "sample_source": source, "context_width": self.width,
                "gate_roles": dict(Counter(r["gate_role"] for r in rows if r["kind"] == "control")),
                "scoring": "greek-lemma-audit score --key <private key> --answers <reader.csv> [--answers <reader2.csv>] --out <dir>",
                "note": "The rate is computed on the random rows only; controls never touch it. Keep the key private "
                        "until scoring; publish it with the results."}


# ---------------------------------------------------------------------------
# scorer


def _wilson_pct(k: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    lo, hi = wilson_ci(k, n)
    return [round(100 * lo, 2), round(100 * hi, 2)]


def load_answers(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for r in read_csv(path):
        rid = r.get("row_id", "").strip()
        if not rid:
            continue
        ans = r.get("answer") or r.get("lemma_correct(y/n/unsure)") or r.get("lemma_correct(y/n)") or ""
        lemma = r.get("correct_lemma_if_wrong") or r.get("correct_lemma") or ""
        out[rid] = {"answer": ans.strip().lower(), "correct_lemma_if_wrong": lemma.strip()}
    return out


def score_sheet(key_path: Path, answer_paths: list[Path], out_dir: Path, reader_names: list[str] | None = None) -> dict[str, Any]:
    key = {r["row_id"]: r for r in read_csv(key_path)}
    names = reader_names or [p.stem for p in answer_paths]
    readers = {name: load_answers(p) for name, p in zip(names, answer_paths)}
    rand_ids = [rid for rid, k in key.items() if k["kind"] == "random"]
    out: dict[str, Any] = {"key": str(key_path), "n_random": len(rand_ids),
                           "n_controls": sum(1 for k in key.values() if k["kind"] == "control"), "readers": {}}
    audit_rows: list[dict[str, Any]] = []
    for name, ans in readers.items():
        missing = [rid for rid in key if rid not in ans]
        caught, missed, anchor_wrong, accent = [], [], [], {}
        nonword_missed = False
        for rid, k in key.items():
            if k["kind"] != "control":
                continue
            a = ans.get(rid, {}).get("answer", "")
            hit = a == k["expected"]
            audit_rows.append({"reader": name, "row_id": rid, "control_id": k["control_id"], "gate_role": k["gate_role"],
                               "expected": k["expected"], "answer": a, "expected_lemma": k["expected_lemma"],
                               "reader_lemma": ans.get(rid, {}).get("correct_lemma_if_wrong", ""), "hit": hit})
            role = k["gate_role"]
            if role in ("nonword", "wrong_unambiguous"):
                (caught if hit else missed).append(k["control_id"])
                if role == "nonword" and not hit:
                    nonword_missed = True
            elif role == "anchor" and not hit:
                anchor_wrong.append(k["control_id"])
            elif role == "wrong_accent":
                accent[k["control_id"]] = hit
        n_wrong_plants = len(caught) + len(missed)
        fail = []
        if nonword_missed:
            fail.append("missed the non-word control")
        if len(missed) >= 2:
            fail.append(f"missed {len(missed)}/{n_wrong_plants} unambiguous wrong-plants: {missed}")
        if anchor_wrong:
            fail.append(f"marked right-anchors wrong: {anchor_wrong}")
        gate = "PASS" if not fail else "FAIL"
        if n_wrong_plants == 0 and not accent and not anchor_wrong and out["n_controls"] == 0:
            gate = "NO_CONTROLS"
        y = sum(1 for rid in rand_ids if ans.get(rid, {}).get("answer") == "y")
        nn = sum(1 for rid in rand_ids if ans.get(rid, {}).get("answer") == "n")
        u = sum(1 for rid in rand_ids if ans.get(rid, {}).get("answer") == "unsure")
        n = len(rand_ids)
        n_dec = y + nn
        out["readers"][name] = {
            "gate": gate, "gate_fail_reasons": fail,
            "controls_caught_unambiguous": f"{len(caught)}/{n_wrong_plants}", "anchors_marked_wrong": len(anchor_wrong),
            "accent_controls_strict": accent, "missing_rows": missing,
            "random": {"y": y, "n": nn, "unsure": u, "unanswered": n - y - nn - u,
                       "rate_lower_pct_unsure_as_wrong": round(100 * y / n, 2) if n else None,
                       "wilson95_lower_bound_variant": _wilson_pct(y, n),
                       "rate_point_pct_unsure_excluded": round(100 * y / n_dec, 2) if n_dec else None,
                       "wilson95_point_variant": _wilson_pct(y, n_dec)},
        }
    if len(readers) == 2:
        (n1, a1), (n2, a2) = readers.items()
        v1 = [a1.get(r, {}).get("answer", "") for r in rand_ids]
        v2 = [a2.get(r, {}).get("answer", "") for r in rand_ids]
        both_n = [r for r in rand_ids if a1.get(r, {}).get("answer") == "n" and a2.get(r, {}).get("answer") == "n"]
        out["agreement_random"] = {
            "readers": [n1, n2],
            "raw_agreement_pct": round(100 * sum(1 for x, y in zip(v1, v2) if x == y) / len(rand_ids), 2) if rand_ids else None,
            "cohen_kappa_3cat": cohen_kappa(v1, v2),
            "cohen_kappa_yn_unsure_as_n": cohen_kappa(["y" if x == "y" else "n" for x in v1], ["y" if x == "y" else "n" for x in v2]),
            "both_marked_wrong": len(both_n),
            "both_wrong_same_correct_lemma": sum(1 for r in both_n if nfc(a1[r]["correct_lemma_if_wrong"]).strip()
                                                 == nfc(a2[r]["correct_lemma_if_wrong"]).strip()),
            "either_marked_wrong": sum(1 for x, y in zip(v1, v2) if x == "n" or y == "n"),
            "both_marked_right": sum(1 for x, y in zip(v1, v2) if x == "y" and y == "y"),
        }
    out_dir.mkdir(parents=True, exist_ok=True)
    if audit_rows:
        with (out_dir / "control_audit.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys()))
            w.writeheader()
            w.writerows(audit_rows)
    verdicts = []
    for r in rand_ids:
        row = {"row_id": r, "surface_form": key[r]["surface_form"], "lemma_produced": key[r]["lemma_produced"],
               "m2_flag": key[r].get("m2_flag", "")}
        for name, ans in readers.items():
            row[name] = ans.get(r, {}).get("answer", "")
            row[f"{name}_lemma"] = ans.get(r, {}).get("correct_lemma_if_wrong", "")
        verdicts.append(row)
    if verdicts:
        with (out_dir / "verdicts.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(verdicts[0].keys()))
            w.writeheader()
            w.writerows(verdicts)
    (out_dir / "score_summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# reader batches (any model or human, run blind and in parallel)

BATCH_PROMPT = (
    "You are a blind reader for a lemmatizer audit. Read the CSV file below (UTF-8). Each row is one token in context; "
    "the columns you must fill are listed in the instructions. Use only your own knowledge of Greek and the rows in the "
    "file: do not run a lemmatizer, do not search the web, do not open any other file. Answer every row, keep the row_id "
    "values, do not reorder. Return a UTF-8 CSV with exactly these columns: {cols}. Keep notes short and free of commas."
    "\n\nBatch file: {batch}\nWrite your answers to: {answers}\n"
)


def write_batches(sheet: Path, out_dir: Path, rows_per_batch: int, instructions: Path | None, answer_cols: list[str]) -> dict[str, Any]:
    """Split ``sheet`` into ``<out>/batch_NN.csv`` + ``<out>/prompt_NN.txt``; return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(sheet)
    if instructions is None:
        cand = sheet.parent / "reviewer_instructions.txt"
        instructions = cand if cand.exists() else None
    instr = instructions.read_text(encoding="utf-8") if instructions else ""
    cols = list(rows[0].keys()) if rows else []
    manifest: dict[str, Any] = {"sheet": str(sheet), "n_rows": len(rows), "rows_per_batch": rows_per_batch,
                                "answer_columns": answer_cols, "batches": []}
    for b in range(0, len(rows), rows_per_batch):
        n = b // rows_per_batch + 1
        bp = out_dir / f"batch_{n:02d}.csv"
        with bp.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows[b : b + rows_per_batch])
        ans = out_dir / f"answers_READER_batch_{n:02d}.csv"
        prompt = (instr + "\n\n" if instr else "") + BATCH_PROMPT.format(cols=", ".join(answer_cols), batch=bp, answers=ans)
        (out_dir / f"prompt_{n:02d}.txt").write_text(prompt, encoding="utf-8")
        manifest["batches"].append({"batch": bp.name, "prompt": f"prompt_{n:02d}.txt", "rows": min(rows_per_batch, len(rows) - b),
                                    "answers_template": ans.name})
    (out_dir / "batches_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest["note"] = ("Run each prompt with the reader of your choice (a model under its own harness, or a person), replace "
                        "READER in the answers file name, then `score --answers 'answers_x_batch_01.csv;answers_x_batch_02.csv;...'`.")
    return manifest


def merge_answer_files(spec: str, out_dir: Path) -> Path:
    """``'a.csv;b.csv'`` -> one merged CSV under ``out_dir`` (a single path is returned unchanged)."""
    parts = [Path(p.strip()) for p in str(spec).split(";") if p.strip()]
    if len(parts) == 1:
        return parts[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    cols: list[str] = []
    for p in parts:
        for r in read_csv(p):
            rows.append(r)
            for c in r:
                if c not in cols:
                    cols.append(c)
    merged = out_dir / f"merged_{parts[0].stem}_{len(parts)}files.csv"
    with merged.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return merged
