"""Galen First Drafts v0.2: the one Claude API backend for translate, back-translation and judge
(spec: firstdrafts_v02_spec.md, cycle 2 brief drafts/firstdrafts_cycle2_brief.md).

Rules it enforces, in code:
  key        ANTHROPIC_API_KEY, or else the first line of the file named by ANTHROPIC_KEY_FILE (default ~/.anthropic/key)
             (stripped). Never printed, never logged, never written to any output row. No key: refuse.
  resume     every completed row is appended to the stage's JSONL at once; a re-run reads that file first
             and sends only the ids that have no usable row, so a re-run never pays twice.
  usage      every call's token usage goes to <work>/usage.jsonl with its price in USD (API list prices,
             common.PRICES_PER_MTOK; Message Batches at half price) and the running total for the work.
  budget     --budget <usd>: before each packet the running total is read back from usage.jsonl; the run
             stops when total >= budget, or when total + the packet's estimated cost would exceed it (a
             submitted packet is paid for, so the stop is before submission, not after).
  backoff    429 / 5xx / overloaded / connection errors: exponential backoff from 5 s, doubling, cap 120 s,
             retry-after honoured, 8 attempts, then the item is left for the next run.
  modes      direct  one streaming call per item, `workers` in flight at once; per-item timestamps.
             batch   Message Batches API, one batch per packet (half price); timestamps bracket the batch.
  packets    items are sent in packets so that a caller may rebuild later prompts from earlier answers
             (term memory lags by one packet); make_request(id) is called at submission time.
  refusal    stop_reason "refusal" is recorded with its category and the item is not retried; nothing
             falls back to another model (a rendering must come from the model it is attributed to).

Nothing here is called by any script unless a `--backend api` / `api` subcommand is given explicitly.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from common import PRICES_PER_MTOK, read_jsonl, sha256, write_jsonl

KEY_FILE = Path(os.environ.get("ANTHROPIC_KEY_FILE", Path.home() / ".anthropic" / "key"))
BATCH_DISCOUNT = 0.5
CACHE_READ_PER_MTOK = {"claude-fable-5-1": 0.25, "claude-opus-5-5": 0.20, "claude-sonnet-5-5": 0.20}
MODEL_EFFORT = {"claude-fable-5-1": "high", "claude-opus-5-5": "high", "claude-sonnet-5-5": "high"}
RETRY_ATTEMPTS = 8
RETRY_BASE_S = 5.0
RETRY_CAP_S = 120.0
BATCH_POLL_S = 30.0

_LOCK = threading.Lock()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ------------------------------------------------------------------ key
def load_api_key() -> str:
    """The key from the environment or the key file; sys.exit without a call if neither exists."""
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    source = "env"
    if not key and KEY_FILE.exists():
        lines = KEY_FILE.read_text(encoding="utf-8").splitlines()
        key = lines[0].strip() if lines else ""
        source = "file"
    if not key:
        sys.exit(f"no API key: set ANTHROPIC_API_KEY or write the key as the first line of {KEY_FILE}. No call was made.")
    print(f"api key: present (source {source}, {len(key)} chars; not shown)", flush=True)
    return key


def make_client(key: str):
    try:
        import anthropic  # type: ignore
    except ImportError:
        sys.exit("the anthropic package is not installed in this venv: .venv/Scripts/python -m pip install anthropic")
    # our own backoff loop handles 429/5xx; the SDK keeps two quick retries for connection blips
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=600.0)


# ------------------------------------------------------------------ price
def usd_for(model: str, usage: dict, mode: str) -> float:
    pi, po = PRICES_PER_MTOK[model]
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    usd = inp / 1e6 * pi + out / 1e6 * po + cw / 1e6 * pi * 1.25 + cr / 1e6 * CACHE_READ_PER_MTOK.get(model, pi / 10)
    if mode == "batch":
        usd *= BATCH_DISCOUNT
    return usd


def usage_total(usage_path: Path) -> float:
    return sum(float(r.get("usd", 0.0)) for r in read_jsonl(usage_path))


def usage_mean_per_call(usage_path: Path, stage: str, model: str) -> float | None:
    rows = [r for r in read_jsonl(usage_path) if r.get("stage") == stage and r.get("model") == model]
    return (sum(float(r["usd"]) for r in rows) / len(rows)) if rows else None


def _append_usage(usage_path: Path, row: dict) -> float:
    with _LOCK:
        total = usage_total(usage_path) + row["usd"]
        row["cum_usd"] = round(total, 6)
        with usage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return total


def _append_row(out_path: Path, row: dict) -> None:
    with _LOCK:
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ request shape
def message_params(model: str, system: str, user: str, max_tokens: int, effort: str | None = None) -> dict:
    """Thinking is adaptive-by-default on all three models (never send `thinking`; a budget is a 400 on
    them); effort is the only depth control and is set explicitly because claude-opus-5-5 defaults to
    medium. No fallbacks: a refusal is recorded, not rerouted."""
    return {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": effort or MODEL_EFFORT.get(model, "high")}}


def parse_json_object(text: str):
    """The first {...} object in the text, or None."""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except Exception:
        return None


def parse_jsonl_objects(text: str) -> list[dict]:
    """Every JSON object found on its own line (judge answers), tolerant of prose around them."""
    out = []
    for line in text.splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            m = re.match(r"(\{.*\})", line)
            if not m:
                continue
            try:
                o = json.loads(m.group(1))
            except Exception:
                continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _row_from_message(item_id: str, id_field: str, msg, model: str, prompt_sha: str, t0: str, t1: str, mode: str, batch_id: str, parse: str) -> dict:
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
    usage = msg.usage.model_dump() if hasattr(msg.usage, "model_dump") else dict(msg.usage)
    usage = {k: v for k, v in usage.items() if isinstance(v, (int, float)) and v is not None}
    parsed = parse_jsonl_objects(text) if parse == "jsonl" else parse_json_object(text)
    stop = msg.stop_reason
    row = {id_field: item_id, "model": msg.model or model, "backend": "api" if mode == "direct" else "api_batch", "prompt_sha256": prompt_sha,
           "started_utc": t0, "finished_utc": t1, "timestamps_scope": "item" if mode == "direct" else "batch",
           "stop_reason": stop, "usage": usage, "usd": round(usd_for(model, usage, mode), 6), "request_id": getattr(msg, "_request_id", None) or "",
           "batch_id": batch_id, "raw_text": text, "response": parsed,
           "ok": bool(parsed) and stop == "end_turn"}
    if stop == "refusal":
        sd = getattr(msg, "stop_details", None)
        row["refusal"] = {"category": getattr(sd, "category", None), "explanation": getattr(sd, "explanation", None)} if sd else {}
    return row


def _retryable(exc) -> tuple[bool, float | None]:
    import anthropic  # type: ignore

    if isinstance(exc, anthropic.RateLimitError):
        ra = None
        try:
            ra = float(exc.response.headers.get("retry-after", ""))
        except Exception:
            pass
        return True, ra
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500 or exc.status_code in (408, 409, 529), None
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True, None
    return False, None


def _with_backoff(fn, what: str):
    delay = RETRY_BASE_S
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            ok, ra = _retryable(exc)
            if not ok or attempt == RETRY_ATTEMPTS:
                raise
            wait = min(RETRY_CAP_S, max(delay, ra or 0.0)) + random.uniform(0, 1.5)
            print(f"  {what}: {type(exc).__name__} (attempt {attempt}/{RETRY_ATTEMPTS}); waiting {wait:.0f}s", flush=True)
            time.sleep(wait)
            delay = min(RETRY_CAP_S, delay * 2)


# ------------------------------------------------------------------ resume
def done_ids(out_path: Path, id_field: str) -> set[str]:
    """Ids with a usable row: parsed response, or a refusal (not retried automatically)."""
    done = set()
    for r in read_jsonl(out_path):
        if r.get("ok") or r.get("stop_reason") == "refusal":
            done.add(r[id_field])
    return done


def canonicalise(out_path: Path, id_field: str, order: list[str]) -> dict:
    """Keep the last usable row per id (else the last row), in the given order; rewrite the file."""
    rows = read_jsonl(out_path)
    best: dict[str, dict] = {}
    for r in rows:
        k = r[id_field]
        if k not in best or r.get("ok") or r.get("stop_reason") == "refusal" or not (best[k].get("ok") or best[k].get("stop_reason") == "refusal"):
            best[k] = r
    pos = {k: i for i, k in enumerate(order)}
    out = sorted(best.values(), key=lambda r: pos.get(r[id_field], 10**9))
    write_jsonl(out_path, out)
    return {"rows": len(out), "ok": sum(1 for r in out if r.get("ok")), "refusal": sum(1 for r in out if r.get("stop_reason") == "refusal"),
            "failed": sum(1 for r in out if not r.get("ok") and r.get("stop_reason") != "refusal"), "missing": sorted(set(order) - set(best))}


# ------------------------------------------------------------------ run
def run_stage(*, stage: str, work: str, model: str, ids: list[str], make_request: Callable[[str], tuple[str, str, dict]], out_path: Path,
              usage_path: Path, id_field: str, budget: float | None, mode: str = "direct", packet_size: int = 8, workers: int = 4,
              max_tokens: int = 16000, effort: str | None = None, est_usd_per_call: float | None = None, parse: str = "json",
              limit: int | None = None) -> dict:
    """Send every id without a usable row, packet by packet, under the budget. make_request(id) returns
    (system, user, meta) and is called when the packet is built, so it may read rows written by earlier
    packets. Returns a summary; rows are appended to out_path as they complete and canonicalised at the end."""
    key = load_api_key()
    client = make_client(key)
    del key
    todo = [i for i in ids if i not in done_ids(out_path, id_field)]
    n_done = len(ids) - len(todo)
    if limit is not None:
        todo = todo[:limit]
    print(f"[{stage}] {model} mode={mode}: {len(ids)} items, {n_done} already done, {len(todo)} to send{' (limit)' if limit is not None else ''}; budget {budget}", flush=True)
    sent = 0
    stopped_for_budget = False
    for p0 in range(0, len(todo), packet_size):
        packet = todo[p0:p0 + packet_size]
        total = usage_total(usage_path)
        per_call = usage_mean_per_call(usage_path, stage, model) or est_usd_per_call or 0.0
        est = per_call * len(packet)
        if budget is not None and (total >= budget or total + est > budget):
            print(f"[{stage}] budget stop before packet {p0 // packet_size + 1}: spent {total:.2f} + est {est:.2f} > budget {budget:.2f}", flush=True)
            stopped_for_budget = True
            break
        reqs = []
        for i in packet:
            system, user, meta = make_request(i)
            reqs.append((i, system, user, meta, sha256(system + "\n\n" + user)))
        if mode == "batch":
            _run_batch(client, stage, work, model, reqs, out_path, usage_path, id_field, max_tokens, effort, parse)
        else:
            _run_direct(client, stage, work, model, reqs, out_path, usage_path, id_field, max_tokens, effort, parse, workers)
        sent += len(packet)
    summary = canonicalise(out_path, id_field, ids)
    summary.update({"stage": stage, "model": model, "mode": mode, "sent_this_run": sent, "stopped_for_budget": stopped_for_budget,
                    "usd_total_work": round(usage_total(usage_path), 4)})
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def _run_direct(client, stage, work, model, reqs, out_path, usage_path, id_field, max_tokens, effort, parse, workers) -> None:
    def one(req):
        i, system, user, meta, psha = req
        params = message_params(model, system, user, max_tokens, effort)
        t0 = now_utc()

        def call():
            with client.messages.stream(**params) as stream:
                return stream.get_final_message()

        try:
            msg = _with_backoff(call, f"{stage} {i}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {stage} {i}: FAILED {type(exc).__name__}: {str(exc)[:160]}", flush=True)
            _append_row(out_path, {id_field: i, "model": model, "backend": "api", "prompt_sha256": psha, "started_utc": t0, "finished_utc": now_utc(),
                                   "timestamps_scope": "item", "stop_reason": "error", "error": f"{type(exc).__name__}: {str(exc)[:300]}", "usage": {}, "usd": 0.0,
                                   "raw_text": "", "response": None, "ok": False, **meta})
            return
        t1 = now_utc()
        row = _row_from_message(i, id_field, msg, model, psha, t0, t1, "direct", "", parse)
        row.update(meta)
        _append_row(out_path, row)
        total = _append_usage(usage_path, {"ts": t1, "stage": stage, "work": work, "model": row["model"], "mode": "direct", "id": i, "batch_id": "",
                                           "request_id": row["request_id"], **{k: row["usage"].get(k, 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")},
                                           "usd": row["usd"]})
        print(f"  {stage} {i}: {row['stop_reason']} in={row['usage'].get('input_tokens')} out={row['usage'].get('output_tokens')} ${row['usd']:.4f} total ${total:.2f}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for f in as_completed([ex.submit(one, r) for r in reqs]):
            f.result()


def _run_batch(client, stage, work, model, reqs, out_path, usage_path, id_field, max_tokens, effort, parse) -> None:
    # Message Batches custom_id must match ^[a-zA-Z0-9_-]{1,64}$; unit ids carry dots (K7.643-644), so each request gets
    # a positional id and the row is written under the item's own id (2026-11-11: the first batch translation run failed on this)
    cid = {f"r{n:05d}": i for n, (i, _, _, _, _) in enumerate(reqs)}
    requests = [{"custom_id": f"r{n:05d}", "params": message_params(model, system, user, max_tokens, effort)} for n, (i, system, user, _, _) in enumerate(reqs)]
    meta_by_id = {i: (meta, psha) for i, _, _, meta, psha in reqs}
    batch = _with_backoff(lambda: client.messages.batches.create(requests=requests), f"{stage} batch create")
    print(f"  {stage}: batch {batch.id} created with {len(requests)} requests ({now_utc()})", flush=True)
    while True:
        b = _with_backoff(lambda: client.messages.batches.retrieve(batch.id), f"{stage} batch poll")
        if b.processing_status == "ended":
            break
        time.sleep(BATCH_POLL_S)
    t0 = b.created_at.isoformat() if hasattr(b.created_at, "isoformat") else str(b.created_at)
    t1 = (b.ended_at.isoformat() if hasattr(b.ended_at, "isoformat") else str(b.ended_at)) if b.ended_at else now_utc()
    n_ok = 0
    for res in _with_backoff(lambda: list(client.messages.batches.results(batch.id)), f"{stage} batch results"):
        i = cid.get(res.custom_id, res.custom_id)
        meta, psha = meta_by_id.get(i, ({}, ""))
        kind = res.result.type
        if kind == "succeeded":
            row = _row_from_message(i, id_field, res.result.message, model, psha, t0, t1, "batch", batch.id, parse)
            row.update(meta)
            _append_row(out_path, row)
            _append_usage(usage_path, {"ts": now_utc(), "stage": stage, "work": work, "model": row["model"], "mode": "batch", "id": i, "batch_id": batch.id,
                                       "request_id": "", **{k: row["usage"].get(k, 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")},
                                       "usd": row["usd"]})
            n_ok += row["ok"]
        else:
            err = getattr(res.result, "error", None)
            _append_row(out_path, {id_field: i, "model": model, "backend": "api_batch", "prompt_sha256": psha, "started_utc": t0, "finished_utc": t1, "timestamps_scope": "batch",
                                   "stop_reason": kind, "error": str(err)[:300] if err else kind, "usage": {}, "usd": 0.0, "batch_id": batch.id, "raw_text": "", "response": None, "ok": False, **meta})
    print(f"  {stage}: batch {batch.id} ended: {n_ok}/{len(requests)} parsed ok; work total ${usage_total(usage_path):.2f}", flush=True)


def add_api_args(ap) -> None:
    ap.add_argument("--budget", type=float, default=None, help="USD cap for the whole work (read back from usage.jsonl before every packet)")
    ap.add_argument("--mode", choices=["direct", "batch"], default="direct", help="direct = streaming calls, per-item timestamps; batch = Message Batches, half price")
    ap.add_argument("--packet-size", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--effort", default=None, help="low|medium|high|xhigh|max (default high for all three models)")
    ap.add_argument("--limit", type=int, default=None, help="send at most this many items this run (smoke test)")
