"""Fetch the public Galen data over HTTPS on first use and cache it in the user's cache dir.

Every file is addressed by its path in the public repo (``docs/first-drafts/hirudinibus/data.json``).
Files under ``docs/`` come from GitHub Pages, everything else from raw.githubusercontent.com (branch
master). A cached file is used without any network call until it is older than the TTL (24 h); then
it is revalidated with its ETag (a 304 costs no download). With no network, the cached copy is used.
``--refresh`` revalidates every file on its first use in this run; ``--offline`` never touches the net.

Environment (all optional):
  GALEN_MCP_CACHE_DIR   cache location (default: platformdirs user cache dir 'galen-mcp')
  GALEN_MCP_TTL_HOURS   revalidation interval, default 24
  GALEN_MCP_OFFLINE=1   never fetch
  GALEN_MCP_SOURCE_DIR  read files from a local checkout of the repo instead (maintainers, tests)
  GALEN_MCP_PAGES_URL / GALEN_MCP_RAW_URL   fetch bases (tests); citation URLs never change
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

PAGES_URL = "https://montblanctech.github.io/Galen/"
RAW_URL = "https://raw.githubusercontent.com/Montblanctech/Galen/master/"
USER_AGENT = f"galen-mcp/{__version__}"


class DataUnavailable(Exception):
    """Raised with a message that tells the user what to do."""


def public_url(repo_path: str) -> str:
    """The public URL a repo path is served from (Pages for docs/, raw GitHub otherwise)."""
    if repo_path.startswith("docs/"):
        return PAGES_URL + repo_path[len("docs/"):]
    return RAW_URL + repo_path


class Store:
    def __init__(
        self,
        cache_dir: str | os.PathLike | None = None,
        *,
        ttl_hours: float | None = None,
        offline: bool | None = None,
        refresh: bool = False,
        source_dir: str | os.PathLike | None = None,
        pages_url: str | None = None,
        raw_url: str | None = None,
        timeout: float = 60.0,
    ):
        env = os.environ
        if cache_dir is None:
            cache_dir = env.get("GALEN_MCP_CACHE_DIR")
        if cache_dir is None:
            import platformdirs

            cache_dir = platformdirs.user_cache_dir("galen-mcp", appauthor=False)
        self.cache_dir = Path(cache_dir)
        self.ttl = 3600.0 * float(ttl_hours if ttl_hours is not None else env.get("GALEN_MCP_TTL_HOURS", 24))
        self.offline = offline if offline is not None else env.get("GALEN_MCP_OFFLINE", "") not in ("", "0")
        self.refresh = refresh
        src = source_dir if source_dir is not None else env.get("GALEN_MCP_SOURCE_DIR")
        self.source_dir = Path(src) if src else None
        self.pages_url = pages_url or env.get("GALEN_MCP_PAGES_URL") or PAGES_URL
        self.raw_url = raw_url or env.get("GALEN_MCP_RAW_URL") or RAW_URL
        self.timeout = timeout
        self._checked: set[str] = set()
        self._lock = threading.Lock()
        self.fetches = 0  # network downloads (200s) this run, for tests

    # ---- paths -------------------------------------------------------------------------------
    def fetch_url(self, repo_path: str) -> str:
        if repo_path.startswith("docs/"):
            return self.pages_url + repo_path[len("docs/"):]
        return self.raw_url + repo_path

    def _cache_file(self, repo_path: str) -> Path:
        return self.cache_dir / "files" / Path(repo_path)

    def _meta_file(self, repo_path: str) -> Path:
        p = self._cache_file(repo_path)
        return p.with_name(p.name + ".meta.json")

    def meta(self, repo_path: str) -> dict:
        if self.source_dir is not None:
            p = self.source_dir / repo_path
            return {"etag": f"local-{int(p.stat().st_mtime)}-{p.stat().st_size}"} if p.exists() else {}
        try:
            return json.loads(self._meta_file(repo_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    # ---- the one entry point -----------------------------------------------------------------
    def path(self, repo_path: str) -> Path:
        """Local path of an up-to-date copy of repo_path (downloads or revalidates as needed)."""
        if self.source_dir is not None:
            p = self.source_dir / repo_path
            if not p.exists():
                raise DataUnavailable(f"{repo_path} is not in the local source checkout")
            return p
        with self._lock:
            return self._ensure(repo_path)

    def _ensure(self, repo_path: str) -> Path:
        f, mf = self._cache_file(repo_path), self._meta_file(repo_path)
        meta = self.meta(repo_path) if f.exists() else {}
        fresh = meta and (time.time() - meta.get("checked_at", 0) < self.ttl) and not (
            self.refresh and repo_path not in self._checked
        )
        if f.exists() and (fresh or self.offline or repo_path in self._checked):
            return f
        if self.offline:
            raise DataUnavailable(
                f"{public_url(repo_path)} is not cached yet and offline mode is on; "
                "run once with a network connection, or `galen-mcp --prefetch`."
            )
        url = self.fetch_url(repo_path)
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
        if f.exists() and meta.get("etag"):
            headers["If-None-Match"] = meta["etag"]
        if f.exists() and meta.get("last_modified"):
            headers["If-Modified-Since"] = meta["last_modified"]
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                    body = gzip.decompress(body)
                new_meta = {
                    "url": public_url(repo_path),
                    "etag": r.headers.get("ETag"),
                    "last_modified": r.headers.get("Last-Modified"),
                    "size": len(body),
                }
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_name(f.name + ".part")
            tmp.write_bytes(body)
            os.replace(tmp, f)
            self.fetches += 1
            meta = new_meta
        except urllib.error.HTTPError as e:
            if e.code == 304 and f.exists():
                pass  # unchanged: keep the cached copy
            elif f.exists():
                self._checked.add(repo_path)
                return f  # server trouble: serve the cached copy
            else:
                raise DataUnavailable(f"could not fetch {public_url(repo_path)} (HTTP {e.code})") from e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if f.exists():
                self._checked.add(repo_path)
                return f  # offline: serve the cached copy
            raise DataUnavailable(
                f"could not fetch {public_url(repo_path)} ({getattr(e, 'reason', e)}); "
                "check the network connection. Once fetched, data is cached and works offline."
            ) from e
        meta["checked_at"] = time.time()
        mf.parent.mkdir(parents=True, exist_ok=True)
        mf.write_text(json.dumps(meta), encoding="utf-8")
        self._checked.add(repo_path)
        return f

    # ---- helpers -----------------------------------------------------------------------------
    def json(self, repo_path: str):
        return json.loads(self.path(repo_path).read_text(encoding="utf-8"))

    def derived(self, name: str, source: str, build):
        """A JSON file computed from a source file, rebuilt when the source's ETag changes."""
        src = self.path(source)
        tag = self.meta(source).get("etag") or str(src.stat().st_mtime)
        p = self.cache_dir / "derived" / f"{name}.json.gz"
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                d = json.load(fh)
            if d.get("source_tag") == tag:
                return d["data"]
        except (OSError, ValueError, KeyError):
            pass
        data = build(src)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".part")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump({"source_tag": tag, "data": data}, fh, ensure_ascii=False)
        os.replace(tmp, p)
        return data
