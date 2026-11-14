"""The HTTP cache, against a throwaway loopback server that serves the fixtures (no internet)."""
import gzip
import hashlib
import http.server
import threading
from pathlib import Path

import pytest

from conftest import FIXTURES
from galen_mcp.store import DataUnavailable, Store, public_url

HIR = "docs/first-drafts/hirudinibus/data.json"
TI = "galen-density-map/outputs/firstdrafts/_index/term_index.json"


class Handler(http.server.BaseHTTPRequestHandler):
    root: Path = FIXTURES
    log: list = []

    def do_GET(self):  # /pages/<path under docs> or /raw/<repo path>
        kind, _, rest = self.path.lstrip("/").partition("/")
        p = self.root / ("docs/" + rest if kind == "pages" else rest)
        self.log.append((self.path, self.headers.get("If-None-Match")))
        if not p.is_file():
            self.send_response(404)
            self.end_headers()
            return
        body = p.read_bytes()
        etag = '"' + hashlib.sha1(body).hexdigest()[:16] + '"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        gz = "gzip" in (self.headers.get("Accept-Encoding") or "")
        out = gzip.compress(body) if gz else body
        self.send_response(200)
        self.send_header("ETag", etag)
        if gz:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "site"
    for rel in (HIR, TI):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((FIXTURES / rel).read_bytes())
    H = type("H", (Handler,), {"root": root, "log": []})
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    yield {"base": base, "log": H.log, "root": root, "httpd": httpd}
    httpd.shutdown()


def mk(server, cache, **kw):
    return Store(cache, pages_url=server["base"] + "pages/", raw_url=server["base"] + "raw/", **kw)


def test_public_urls():
    assert public_url(HIR) == "https://montblanctech.github.io/Galen/first-drafts/hirudinibus/data.json"
    assert public_url(TI).startswith("https://raw.githubusercontent.com/Montblanctech/Galen/master/galen-density-map/")


def test_download_cache_and_etag(server, tmp_path):
    cache = tmp_path / "c"
    s = mk(server, cache)
    p = s.path(HIR)
    assert p.read_bytes() == (FIXTURES / HIR).read_bytes()  # gzip decoded
    assert s.fetches == 1 and s.meta(HIR)["url"].startswith("https://montblanctech.github.io/")
    s.path(HIR)
    assert len(server["log"]) == 1  # fresh: no second request
    # a later run within the TTL makes no request at all
    mk(server, cache).path(HIR)
    assert len(server["log"]) == 1
    # --refresh: revalidates with the ETag; 304 means no download
    r = mk(server, cache, refresh=True)
    r.path(HIR)
    assert len(server["log"]) == 2 and server["log"][-1][1] and r.fetches == 0
    r.path(HIR)
    assert len(server["log"]) == 2  # once per run
    # the file changes upstream: the next revalidation downloads it
    (server["root"] / HIR).write_bytes(b'{"changed": true}')
    t = mk(server, cache, ttl_hours=0)
    assert t.json(HIR) == {"changed": True} and t.fetches == 1


def test_raw_path_and_404(server, tmp_path):
    s = mk(server, tmp_path / "c")
    assert s.json(TI)["summary"]["n_works"] == 13
    assert server["log"][-1][0].startswith("/raw/galen-density-map/")
    with pytest.raises(DataUnavailable, match="HTTP 404"):
        s.path("docs/first-drafts/nope/data.json")


def test_offline(server, tmp_path):
    cache = tmp_path / "c"
    with pytest.raises(DataUnavailable, match="offline mode is on.*--prefetch"):
        mk(server, cache, offline=True).path(HIR)
    mk(server, cache).path(HIR)
    n = len(server["log"])
    assert mk(server, cache, offline=True, ttl_hours=0).path(HIR).exists()
    assert len(server["log"]) == n


def test_network_down_serves_cache(server, tmp_path):
    cache = tmp_path / "c"
    mk(server, cache).path(HIR)
    server["httpd"].shutdown()
    server["httpd"].server_close()
    s = mk(server, cache, ttl_hours=0, timeout=2)
    assert s.path(HIR).exists()
    with pytest.raises(DataUnavailable, match="could not fetch .*check the network"):
        s.path(TI)


def test_derived_rebuilds_on_change(tmp_path):
    src = tmp_path / "src"
    (src / "x").mkdir(parents=True)
    f = src / "x" / "a.txt"
    f.write_text("one", encoding="utf-8")
    s = Store(tmp_path / "c", source_dir=src)
    calls = []

    def build(p):
        calls.append(1)
        return Path(p).read_text(encoding="utf-8")

    assert s.derived("a", "x/a.txt", build) == "one"
    assert s.derived("a", "x/a.txt", build) == "one" and len(calls) == 1
    import os, time
    f.write_text("two!", encoding="utf-8")
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert s.derived("a", "x/a.txt", build) == "two!" and len(calls) == 2
