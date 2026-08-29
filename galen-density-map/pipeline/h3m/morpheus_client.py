"""Morpheus morphology client with on-disk cache.

Prefers a local Docker Perseids API (localhost:1500). If Docker is not
running, falls back to https://morph.perseids.org — the same engine
(org.perseus:tools:morpheus.v1). Every surface is cached so reruns are free
and the public service is queried at most once per unique surface.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import requests
from lxml import etree

from .lemma_eq import surface_nfc
from .paths import MORPHEUS_FALLBACK_URL, MORPHEUS_LOCAL_URL
from lib.io_utils import ensure_dir

ENGINE = "morpheusgrc"
USER_AGENT = (
    "galen-density-map-h3m/0.1 "
    "(scholarly QC; unique-surface cache; Montblanctech/Galen)"
)

_thread_local = threading.local()


def _thread_session() -> requests.Session:
    sess = getattr(_thread_local, "session", None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update({"Accept": "application/json", "User-Agent": USER_AGENT})
        _thread_local.session = sess
    return sess


def extract_headwords_from_obj(obj: Any, out: list[str] | None = None) -> list[str]:
    """Walk Perseids JSON for dict.hdwd values (handles list-or-dict Body/entry)."""
    if out is None:
        out = []
    if isinstance(obj, dict):
        hd = obj.get("hdwd")
        if isinstance(hd, dict):
            val = hd.get("$") or hd.get("#text")
            if val:
                out.append(str(val))
        elif isinstance(hd, str) and hd:
            out.append(hd)
        for v in obj.values():
            extract_headwords_from_obj(v, out)
    elif isinstance(obj, list):
        for item in obj:
            extract_headwords_from_obj(item, out)
    return out


def extract_headwords_from_xml(text: str) -> list[str]:
    parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
    root = etree.fromstring(text.encode("utf-8"), parser)
    found: list[str] = []
    for el in root.xpath('//*[local-name()="hdwd"]'):
        t = (el.text or "").strip()
        if t:
            found.append(t)
    return found


def parse_morpheus_payload(payload: str | dict, content_type: str = "") -> list[str]:
    """Return unique Morpheus headwords; empty list means no_analysis."""
    lemmas: list[str] = []
    if isinstance(payload, dict):
        lemmas = extract_headwords_from_obj(payload)
    else:
        text = payload or ""
        ct = (content_type or "").lower()
        stripped = text.lstrip()
        if "json" in ct or stripped.startswith("{") or stripped.startswith("["):
            try:
                lemmas = extract_headwords_from_obj(json.loads(text))
            except json.JSONDecodeError:
                lemmas = extract_headwords_from_xml(text) if stripped.startswith("<") else []
        elif stripped.startswith("<"):
            lemmas = extract_headwords_from_xml(text)
        else:
            try:
                lemmas = extract_headwords_from_obj(json.loads(text))
            except json.JSONDecodeError:
                lemmas = []
    seen: set[str] = set()
    uniq: list[str] = []
    for lem in lemmas:
        if lem not in seen:
            seen.add(lem)
            uniq.append(lem)
    return uniq


def _probe_url(base: str, timeout: float) -> bool:
    try:
        resp = requests.get(
            f"{base.rstrip('/')}/analysis/word",
            params={"lang": "grc", "engine": ENGINE, "word": "και"},
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=timeout,
        )
        return resp.status_code in {200, 201}
    except requests.RequestException:
        return False


def resolve_base_url() -> tuple[str, str]:
    """Return (base_url, source_label)."""
    env = os.environ.get("MORPHEUS_URL")
    if env:
        return env.rstrip("/"), "env:MORPHEUS_URL"
    if _probe_url(MORPHEUS_LOCAL_URL, timeout=2.0):
        return MORPHEUS_LOCAL_URL, "docker_local"
    return MORPHEUS_FALLBACK_URL, "perseids_hosted"


class MorpheusClient:
    def __init__(
        self,
        cache_path: Path,
        base_url: str | None = None,
        source_label: str | None = None,
        workers: int = 8,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        if base_url is None or source_label is None:
            resolved, label = resolve_base_url()
            base_url = base_url or resolved
            source_label = source_label or label
        self.base_url = base_url.rstrip("/")
        self.source_label = source_label
        self.cache_path = cache_path
        self.workers = workers
        self.timeout = timeout
        self.max_retries = max_retries
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        with self.cache_path.open("rb") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = row.get("surface_nfc")
                if key:
                    self._cache[key] = row

    def _append_cache(self, row: dict[str, Any]) -> None:
        ensure_dir(self.cache_path.parent)
        payload = json.dumps(row, ensure_ascii=False)
        with self.cache_path.open("ab") as fh:
            fh.write(payload.encode("utf-8") + b"\n")

    def rewrite_cache_utf8(self) -> None:
        """Rewrite the on-disk cache as strict UTF-8 JSONL from memory."""
        ensure_dir(self.cache_path.parent)
        tmp = self.cache_path.with_suffix(".jsonl.tmp")
        with tmp.open("wb") as fh:
            for row in self._cache.values():
                fh.write(json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
        os.replace(tmp, self.cache_path)

    def repair_corrupt_lines(self) -> dict[str, Any]:
        """Drop non-UTF-8 cache lines, rewrite, and re-fetch those surfaces (F4)."""
        if not self.cache_path.exists():
            return {"corrupt_lines": 0, "refetched": 0}
        good: dict[str, dict[str, Any]] = {}
        corrupt_surfaces: list[str] = []
        n_corrupt = 0
        with self.cache_path.open("rb") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    n_corrupt += 1
                    surf = ""
                    for enc in ("cp1252", "latin-1"):
                        try:
                            row = json.loads(raw.decode(enc))
                            surf = row.get("surface_nfc") or ""
                            break
                        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                            continue
                    if surf:
                        corrupt_surfaces.append(surf)
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    n_corrupt += 1
                    continue
                key = row.get("surface_nfc")
                if key:
                    good[key] = row
        self._cache = good
        print(
            f"F4 cache hygiene: {n_corrupt} non-UTF-8/bad-JSON lines, "
            f"{len(corrupt_surfaces)} surfaces to re-fetch, "
            f"{len(good)} clean rows kept"
        )
        self.rewrite_cache_utf8()
        if corrupt_surfaces:
            self.analyze_many(corrupt_surfaces, progress_every=20)
            self.rewrite_cache_utf8()
        return {
            "corrupt_lines": n_corrupt,
            "refetched": len(corrupt_surfaces),
            "surfaces": corrupt_surfaces,
        }

    def get_cached(self, surface: str) -> dict[str, Any] | None:
        return self._cache.get(surface_nfc(surface))

    def analyze(self, surface: str) -> list[str]:
        key = surface_nfc(surface)
        hit = self._cache.get(key)
        if hit is not None:
            return list(hit.get("lemmas") or [])
        row = self._query(key)
        with self._lock:
            if key not in self._cache:
                self._cache[key] = row
                self._append_cache(row)
        return list(row.get("lemmas") or [])

    def _query(self, surface: str) -> dict[str, Any]:
        url = f"{self.base_url}/analysis/word"
        params = {"lang": "grc", "engine": ENGINE, "word": surface}
        last_err = ""
        sess = _thread_session()
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = sess.get(url, params=params, timeout=self.timeout)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(min(30.0, 0.5 * (2 ** attempt)))
                    last_err = f"http {resp.status_code}"
                    continue
                if resp.status_code not in {200, 201}:
                    last_err = f"http {resp.status_code}"
                    time.sleep(0.25 * attempt)
                    continue
                lemmas = parse_morpheus_payload(resp.text, resp.headers.get("content-type", ""))
                return {
                    "surface_nfc": surface,
                    "lemmas": lemmas,
                    "ok": True,
                    "source": self.source_label,
                }
            except requests.RequestException as exc:
                last_err = str(exc)
                time.sleep(min(30.0, 0.5 * (2 ** attempt)))
        return {
            "surface_nfc": surface,
            "lemmas": [],
            "ok": False,
            "error": last_err,
            "source": self.source_label,
        }

    def analyze_many(self, surfaces: Iterable[str], progress_every: int = 500) -> dict[str, list[str]]:
        unique: list[str] = []
        seen: set[str] = set()
        for s in surfaces:
            key = surface_nfc(s)
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(key)
        missing = [s for s in unique if s not in self._cache]
        total_missing = len(missing)
        print(
            f"Morpheus: {len(unique)} unique surfaces, "
            f"{len(unique) - total_missing} cached, {total_missing} to query "
            f"via {self.source_label} ({self.base_url})"
        )
        if missing:
            done = 0
            failed = 0
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futs = {pool.submit(self._query, s): s for s in missing}
                for fut in as_completed(futs):
                    surface = futs[fut]
                    row = fut.result()
                    with self._lock:
                        if surface not in self._cache:
                            self._cache[surface] = row
                            self._append_cache(row)
                    done += 1
                    if not row.get("ok"):
                        failed += 1
                    if done % progress_every == 0 or done == total_missing:
                        print(
                            f"  Morpheus queried {done}/{total_missing} "
                            f"(failed={failed})",
                            flush=True,
                        )
        return {s: list(self._cache[s].get("lemmas") or []) for s in unique if s in self._cache}

    def info(self) -> dict[str, Any]:
        n_ok = sum(1 for r in self._cache.values() if r.get("ok"))
        n_fail = sum(1 for r in self._cache.values() if not r.get("ok"))
        n_empty = sum(1 for r in self._cache.values() if r.get("ok") and not r.get("lemmas"))
        return {
            "base_url": self.base_url,
            "source": self.source_label,
            "engine": ENGINE,
            "creator": "org.perseus:tools:morpheus.v1",
            "docker_image": "perseidsproject/morpheus-perseids-api:v2.1.5",
            "cache_path": str(self.cache_path),
            "cached_surfaces": len(self._cache),
            "cached_ok": n_ok,
            "cached_failed": n_fail,
            "cached_no_analysis": n_empty,
            "workers": self.workers,
        }
