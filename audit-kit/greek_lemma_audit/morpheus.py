"""Morpheus (Perseids) analyses: read-only cache first, rate-limited online second.

Payload parsing and the cache row shape (``{"surface_nfc", "lemmas", "ok", "source"}``)
are copied, with attribution, from ``galen-density-map/pipeline/h3m/morpheus_client.py``
(engine ``morpheusgrc``, creator ``org.perseus:tools:morpheus.v1``; Docker image
``perseidsproject/morpheus-perseids-api:v2.1.5`` or https://morph.perseids.org).

Differences from the project client, on purpose:

* every cache passed in is opened **read-only**; new rows go to the kit's own
  file (``write_path``), so the frozen project cache is never touched;
* online queries happen only when ``online=True``, single-threaded, with a
  fixed sleep between requests (``rate_limit`` seconds) and an optional cap.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

from .normalize import surface_nfc

ENGINE = "morpheusgrc"
CREATOR = "org.perseus:tools:morpheus.v1"
DOCKER_IMAGE = "perseidsproject/morpheus-perseids-api:v2.1.5"
HOSTED_URL = "https://morph.perseids.org"
USER_AGENT = "greek-lemma-audit/0.1 (scholarly QC; unique-surface cache; Galen Density Project)"


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
    try:
        from lxml import etree
    except Exception:
        return []
    parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
    root = etree.fromstring(text.encode("utf-8"), parser)
    if root is None:
        return []
    return [(el.text or "").strip() for el in root.xpath('//*[local-name()="hdwd"]') if (el.text or "").strip()]


def parse_morpheus_payload(payload: str | dict, content_type: str = "") -> list[str]:
    """Return unique Morpheus headwords; empty list means no_analysis."""
    lemmas: list[str] = []
    if isinstance(payload, dict):
        lemmas = extract_headwords_from_obj(payload)
    else:
        text = payload or ""
        stripped = text.lstrip()
        if "json" in (content_type or "").lower() or stripped.startswith(("{", "[")):
            try:
                lemmas = extract_headwords_from_obj(json.loads(text))
            except json.JSONDecodeError:
                lemmas = extract_headwords_from_xml(text) if stripped.startswith("<") else []
        elif stripped.startswith("<"):
            lemmas = extract_headwords_from_xml(text)
    seen: set[str] = set()
    uniq: list[str] = []
    for lem in lemmas:
        if lem not in seen:
            seen.add(lem)
            uniq.append(lem)
    return uniq


class MorpheusStore:
    """Analyses by NFC surface. Missing surfaces are *not* ``no_analysis``."""

    def __init__(
        self,
        cache_paths: Iterable[Path] = (),
        *,
        write_path: Path | None = None,
        online: bool = False,
        base_url: str | None = None,
        rate_limit: float = 0.5,
        max_online: int = 0,
        timeout: float = 30.0,
    ) -> None:
        self.cache_paths = [Path(p) for p in cache_paths]
        self.write_path = Path(write_path) if write_path else None
        self.online = online
        self.base_url = (base_url or os.environ.get("MORPHEUS_URL") or HOSTED_URL).rstrip("/")
        self.rate_limit = rate_limit
        self.max_online = max_online
        self.timeout = timeout
        self._rows: dict[str, dict[str, Any]] = {}
        self.load_stats: dict[str, Any] = {"files": [], "rows": 0, "bad_lines": 0}
        self.online_stats: dict[str, Any] = {"queried": 0, "failed": 0, "capped": 0, "elapsed_s": 0.0}
        for p in self.cache_paths:
            self._load(p)
        if self.write_path and self.write_path.exists():
            self._load(self.write_path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            self.load_stats["files"].append({"path": str(path), "exists": False})
            return
        n = bad = 0
        with path.open("rb") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    bad += 1
                    continue
                key = row.get("surface_nfc")
                if key and row.get("ok", True):
                    self._rows[key] = row
                    n += 1
        self.load_stats["files"].append({"path": str(path), "exists": True, "rows": n, "bad_lines": bad})
        self.load_stats["rows"] = len(self._rows)
        self.load_stats["bad_lines"] += bad

    def __len__(self) -> int:
        return len(self._rows)

    def lookup(self, surface: str) -> list[str] | None:
        """Analyses for a surface, or ``None`` when the surface is not cached."""
        row = self._rows.get(surface_nfc(surface))
        if row is None:
            return None
        return list(row.get("lemmas") or [])

    # -- online ---------------------------------------------------------------
    def fetch_missing(self, surfaces: Iterable[str], progress: Any = None) -> int:
        """Query uncached surfaces (online mode only). Returns number queried."""
        if not self.online:
            return 0
        import requests

        missing: list[str] = []
        seen: set[str] = set()
        for s in surfaces:
            k = surface_nfc(s)
            if k and k not in seen and k not in self._rows:
                seen.add(k)
                missing.append(k)
        if self.max_online and len(missing) > self.max_online:
            self.online_stats["capped"] = len(missing) - self.max_online
            missing = missing[: self.max_online]
        sess = requests.Session()
        sess.headers.update({"Accept": "application/json", "User-Agent": USER_AGENT})
        t0 = time.time()
        fh = None
        if self.write_path:
            self.write_path.parent.mkdir(parents=True, exist_ok=True)
            fh = self.write_path.open("ab")
        try:
            for n, surface in enumerate(missing, 1):
                row = self._query(sess, surface)
                self.online_stats["queried"] += 1
                if not row.get("ok"):
                    self.online_stats["failed"] += 1
                else:
                    self._rows[surface] = row
                if fh is not None:
                    fh.write(json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
                if progress and (n % 100 == 0 or n == len(missing)):
                    progress(f"  Morpheus online {n}/{len(missing)} (failed={self.online_stats['failed']})")
                time.sleep(self.rate_limit)
        finally:
            if fh is not None:
                fh.close()
        self.online_stats["elapsed_s"] = round(time.time() - t0, 1)
        return len(missing)

    def _query(self, sess: Any, surface: str, retries: int = 4) -> dict[str, Any]:
        import requests

        url = f"{self.base_url}/analysis/word"
        params = {"lang": "grc", "engine": ENGINE, "word": surface}
        last = ""
        for attempt in range(1, retries + 1):
            try:
                resp = sess.get(url, params=params, timeout=self.timeout)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    last = f"http {resp.status_code}"
                    time.sleep(min(30.0, 0.5 * (2 ** attempt)))
                    continue
                if resp.status_code not in {200, 201}:
                    last = f"http {resp.status_code}"
                    time.sleep(0.25 * attempt)
                    continue
                lemmas = parse_morpheus_payload(resp.text, resp.headers.get("content-type", ""))
                return {"surface_nfc": surface, "lemmas": lemmas, "ok": True, "source": self.base_url}
            except requests.RequestException as exc:
                last = str(exc)[:200]
                time.sleep(min(30.0, 0.5 * (2 ** attempt)))
        return {"surface_nfc": surface, "lemmas": [], "ok": False, "error": last, "source": self.base_url}

    def info(self) -> dict[str, Any]:
        return {
            "engine": ENGINE,
            "creator": CREATOR,
            "docker_image": DOCKER_IMAGE,
            "base_url": self.base_url if self.online else None,
            "online": self.online,
            "rate_limit_s": self.rate_limit if self.online else None,
            "cache_files": self.load_stats["files"],
            "cached_surfaces": len(self._rows),
            "cache_bad_lines": self.load_stats["bad_lines"],
            "write_path": str(self.write_path) if self.write_path else None,
            "online_stats": self.online_stats,
        }
