"""Headless check of docs/tools/autocorrect/: serve docs/ with http.server, load the page in headless Chromium
(Playwright's chrome-headless-shell if present, else Edge or Chrome) with ?text=..., wait over the DevTools
protocol (a minimal stdlib WebSocket client) until the page reports it has run, read the page's result and DOM,
and assert that the result equals the native CLI's. No Python packages needed (Playwright's Python module is
not installed in the Galen venv; only its browsers). --dump-dom alone is not used: it can dump before the
6.6 MB model has arrived.

  python -I -X utf8 t2b-wasm/tools/page_check.py
"""
from __future__ import annotations

import base64
import functools
import glob
import html
import http.server
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCS = REPO / "docs"
CLI = REPO / "t2b-wasm" / "target" / "release" / ("t2b-cli.exe" if sys.platform == "win32" else "t2b-cli")
TEXT = "ΡΩΜΗΝΕΑΝΓΑΡΑΜΛΠΑΝΙΑΣΥΝΕΛΘΟΤΤΔΕΙΡΗΜΕΝΑ\nοὖν εἴωθεν ἡ φύσις"
WANT_BEST = ["ΡΩΜΗΝ ΕΑΝ ΓΑΡ ΑΜΑ ΠΑΝΤΑ ΣΥΝΕΛΘΟΙ ΤΑ ΕΙΡΗΜΕΝΑ", "ΟΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ"]


def browser() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    cands = sorted(glob.glob(os.path.join(local, "ms-playwright", "chromium_headless_shell-*", "*", "chrome-headless-shell.exe")),
                   reverse=True)
    cands += [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/chromium", "/usr/bin/google-chrome"]
    for c in cands:
        if os.path.isfile(c):
            return c
    raise SystemExit("no headless Chromium found")


class Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm",
                      ".js": "text/javascript", ".bin": "application/octet-stream"}

    def log_message(self, *a):
        pass


class CDP:
    """Just enough of the DevTools protocol: one WebSocket to a page target, Runtime.evaluate."""

    def __init__(self, ws_url: str):
        u = urllib.parse.urlparse(ws_url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        sep = b"\r\n\r\n"
        buf = b""
        while sep not in buf:
            buf += self.sock.recv(4096)
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError(buf[:200])
        self.rest = buf.split(sep, 1)[1]
        self.n = 0

    def _recv(self, k: int) -> bytes:
        while len(self.rest) < k:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise RuntimeError("devtools socket closed")
            self.rest += chunk
        out, self.rest = self.rest[:k], self.rest[k:]
        return out

    def _frame(self) -> bytes:
        msg = b""
        while True:
            b0, b1 = self._recv(2)
            ln = b1 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._recv(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._recv(8))[0]
            msg += self._recv(ln)
            if b0 & 0x80:
                return msg

    def call(self, method: str, **params):
        self.n += 1
        data = json.dumps({"id": self.n, "method": method, "params": params}).encode()
        mask = os.urandom(4)
        head = bytes([0x81])
        ln = len(data)
        head += bytes([0x80 | ln]) if ln < 126 else (bytes([0x80 | 126]) + struct.pack(">H", ln) if ln < 65536
                                                     else bytes([0x80 | 127]) + struct.pack(">Q", ln))
        self.sock.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(data)))
        while True:
            m = json.loads(self._frame())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]

    def eval(self, expr: str):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True)
        return r["result"].get("value")


def main():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(DOCS)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    url = f"http://127.0.0.1:{port}/tools/autocorrect/?" + urllib.parse.urlencode({"text": TEXT, "k": "5"})
    exe = browser()
    with tempfile.TemporaryDirectory() as prof:
        cmd = [exe, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               f"--user-data-dir={prof}", "--remote-debugging-port=0",
               "--host-resolver-rules=MAP static.cloudflareinsights.com 0.0.0.0", url]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            ws = None
            t0 = time.time()
            while ws is None and time.time() - t0 < 30:
                line = proc.stderr.readline().decode("utf-8", errors="replace")
                m = re.search(r"DevTools listening on (ws://\S+)", line)
                if m:
                    ws = m.group(1)
            if ws is None:
                raise SystemExit("browser did not open a DevTools port")
            port_ = urllib.parse.urlparse(ws).port
            target = None
            for _ in range(100):
                pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/json/list", timeout=10).read())
                target = next((p for p in pages if p.get("type") == "page" and "/tools/autocorrect/" in p.get("url", "")), None)
                if target:
                    break
                time.sleep(0.1)
            cdp = CDP(target["webSocketDebuggerUrl"])
            attrs = {}
            t0 = time.time()
            while time.time() - t0 < 120:
                attrs = cdp.eval("({done: document.body && document.body.getAttribute('data-done'),"
                                 " error: document.body && document.body.getAttribute('data-error'),"
                                 " load: document.body && document.body.getAttribute('data-load-ms')})") or {}
                if attrs.get("done") or attrs.get("error"):
                    break
                time.sleep(0.2)
            dom = cdp.eval("document.documentElement.outerHTML") or ""
        finally:
            proc.kill()
            proc.wait()
    srv.shutdown()
    if attrs.get("error") or attrs.get("done") != "2":
        raise SystemExit(f"page did not finish: {attrs} (browser {exe})")
    m = re.search(r'<pre id="json">(.*?)</pre>', dom, re.S)
    got = json.loads(html.unescape(m.group(1)))
    best = [x["result"]["readings"][0]["text"] for x in got]
    assert best == WANT_BEST, best
    shown = re.findall(r'<article class="line" data-best="([^"]*)"', dom)
    assert [html.unescape(s) for s in shown] == WANT_BEST, shown
    # the page's JSON must equal the native CLI's, line by line
    nat = subprocess.run([str(CLI), str(DOCS / "tools" / "autocorrect" / "model.bin"), "-k", "5"],
                         input=TEXT.encode("utf-8"), capture_output=True, check=True).stdout.decode("utf-8")
    nat_rows = [json.loads(x) for x in nat.splitlines()]
    assert [x["result"] for x in got] == nat_rows, "page result differs from the native CLI"
    status = re.search(r'<p id="status"[^>]*>(.*?)</p>', dom, re.S).group(1)
    report = {"browser": Path(exe).name, "load_ms": int(attrs.get("load") or -1),
              "segment_ms": [round(x["ms"], 2) for x in got], "best": best, "status": html.unescape(status),
              "same_as_native": True}
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
