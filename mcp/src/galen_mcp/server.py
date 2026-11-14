"""stdio MCP server: five read-only tools over the public Galen First Drafts data."""
from __future__ import annotations

import argparse
import sys
from typing import Literal

try:  # mcp 2.x renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError as _SdkToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
    from mcp.server.fastmcp.exceptions import ToolError as _SdkToolError
from mcp.types import ToolAnnotations

from . import __version__
from .core import TERM_INDEX, Galen, ToolError
from .store import DataUnavailable, Store

INSTRUCTIONS = (
    "Galen First Drafts: machine first-draft English translations (two independent renderings, A and B, "
    "with automatic checks) of 13 Galen works never before translated into English, keyed by Kühn "
    "citation. No scholar has reviewed them; say so when quoting, and cite the page URL each answer gives. "
    "Start with list_works, get_passage('K15.609'), or search_terms('nerve')."
)

Detail = Literal["concise", "full"]
RO = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


def build_server(galen: Galen | None = None):
    g = galen or Galen()
    kw = {"instructions": INSTRUCTIONS}
    try:
        srv = _Server("galen", version=__version__, **kw)
    except TypeError:  # older SDKs take no version
        srv = _Server("galen", **kw)

    def run(fn, *a, **k) -> str:
        try:
            return fn(*a, **k)
        except (ToolError, DataUnavailable) as e:
            raise _SdkToolError(str(e)) from None  # the message reaches the model as is

    @srv.tool(annotations=RO, structured_output=False)
    def list_works(detail: Detail = "concise") -> str:
        """List the 13 Galen works (plus the Latin method test) with slug, Kühn span, units and page URL.

        detail="full" adds check pass rates, authorship notes and earlier translations.
        """
        return run(g.list_works, detail)

    @srv.tool(annotations=RO, structured_output=False)
    def search_terms(query: str, limit: int = 10, offset: int = 0) -> str:
        """Find Galenic key terms by Greek (accents optional), LSJ key or gloss, or English rendering.

        Examples: "νεῦρον", "νευρον", "neu=ron", "sinew", "acrid", "humour". One line per lemma with
        its usual renderings; page with offset.
        """
        return run(g.search_terms, query, limit, offset)

    @srv.tool(annotations=RO, structured_output=False)
    def get_term(lemma: str, work: str | None = None, detail: Detail = "concise", offset: int = 0) -> str:
        """How one Greek lemma is rendered (A and B) in each work, with Kühn loci.

        Examples: get_term("δριμύς"); get_term("νευρον", work="de-humero", detail="full") for every
        occurrence with the Greek and English sentences. work is a slug from list_works.
        """
        return run(g.get_term, lemma, work, detail, offset)

    @srv.tool(annotations=RO, structured_output=False)
    def get_passage(citation_or_unit: str, work: str | None = None, detail: Detail = "concise") -> str:
        """One unit (about a Kühn page): Greek, renderings A and B, check verdicts and page URL.

        Examples: "K15.609", "K. XV 609", "K18a.196", unit id "K15.609-610"; Vitruvius "Vitr.3.1.5".
        detail="full" adds the key-term table.
        """
        return run(g.get_passage, citation_or_unit, work, detail)

    @srv.tool(annotations=RO, structured_output=False)
    def lsj_gold_lemma(form: str, limit: int = 10) -> str:
        """Gold lemma of a Greek or Latin word form, from LSJ-Gold / LS-Gold (dictionary-cited loci).

        Examples: "ἀᾶται", "ἀγαθὸν", "abdicavit". First use downloads the gold set (Greek 11 MB,
        Latin 24 MB), then it is cached.
        """
        return run(g.lsj_gold_lemma, form, limit)

    return srv


def prefetch(g: Galen) -> int:
    paths = [TERM_INDEX] + [g.work_path(s) for s in g.catalog]
    for i, p in enumerate(paths, 1):
        try:
            g.store.path(p)
            print(f"[{i}/{len(paths)}] ok {p}", file=sys.stderr)
        except DataUnavailable as e:
            print(f"[{i}/{len(paths)}] {e}", file=sys.stderr)
            return 1
    print("done; the gold sets download on first lsj_gold_lemma call.", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="galen-mcp", description="MCP server (stdio) for the Galen First Drafts.")
    ap.add_argument("--refresh", action="store_true", help="revalidate every cached file on first use this run")
    ap.add_argument("--offline", action="store_true", help="never use the network; cached data only")
    ap.add_argument("--cache-dir", help="cache location (default: the user cache dir)")
    ap.add_argument("--prefetch", action="store_true", help="download the drafts and term index, then exit")
    ap.add_argument("--version", action="version", version=f"galen-mcp {__version__}")
    a = ap.parse_args(argv)
    store = Store(a.cache_dir, offline=True if a.offline else None, refresh=a.refresh)
    g = Galen(store)
    if a.prefetch:
        return prefetch(g)
    build_server(g).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
