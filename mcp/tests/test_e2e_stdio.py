"""Start the real server over stdio with the SDK's client, list the tools and call each one.

By default it serves the fixtures (no network). With GALEN_MCP_LIVE=1 it uses the live public URLs
and a fresh cache instead: that is the install check, run once by hand.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from conftest import FIXTURES

LIVE = os.environ.get("GALEN_MCP_LIVE") == "1"
TOOLS = {"list_works", "search_terms", "get_term", "get_passage", "lsj_gold_lemma"}
CALLS = [
    ("list_works", {}),
    ("search_terms", {"query": "nerve"}),
    ("get_term", {"lemma": "γνώρισμα"}),
    ("get_passage", {"citation_or_unit": "K15.609"}),
    ("lsj_gold_lemma", {"form": "ἀᾶται"}),
]


def attr(o, camel, snake):  # mcp 1.x uses camelCase attributes, 2.x snake_case
    return getattr(o, snake) if hasattr(o, snake) else getattr(o, camel)


def is_error(res) -> bool:
    return bool(attr(res, "isError", "is_error"))


def text_of(res) -> str:
    return "".join(getattr(c, "text", "") for c in res.content)


async def session_run(cache: Path):
    env = {"GALEN_MCP_CACHE_DIR": str(cache), "PYTHONIOENCODING": "utf-8"}
    if not LIVE:
        env["GALEN_MCP_SOURCE_DIR"] = str(FIXTURES)
    params = StdioServerParameters(command=sys.executable, args=["-m", "galen_mcp"], env=env)
    results = {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            results["tools"] = {t.name: t for t in tools}
            for name, args in CALLS:
                results[name] = await s.call_tool(name, args)
            results["error"] = await s.call_tool("get_passage", {"citation_or_unit": "K15.6091"})
    return results


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return asyncio.run(session_run(tmp_path_factory.mktemp("cache")))


def test_tools_listed(run):
    tools = run["tools"]
    assert set(tools) == TOOLS
    for t in tools.values():
        assert len(t.description) < 400, t.name  # short descriptions
        assert t.annotations and attr(t.annotations, "readOnlyHint", "read_only_hint")
    schema = {n: attr(t, "inputSchema", "input_schema") for n, t in tools.items()}
    assert "citation_or_unit" in schema["get_passage"]["properties"]
    assert schema["get_term"]["properties"]["detail"].get("enum") == ["concise", "full"]


def test_each_tool_answers(run):
    sizes = {}
    for name, _ in CALLS:
        res = run[name]
        out = text_of(res)
        assert not is_error(res), (name, out)
        assert out and len(out) < 6000, name
        sizes[name] = len(out) // 4
    assert "hirudinibus" in text_of(run["list_works"])
    assert "νεῦρον" in text_of(run["search_terms"])
    assert "in-hipp-acut" in text_of(run["get_term"])
    p = text_of(run["get_passage"])
    assert "book-2.html#K15.609-610" in p and "no scholar has reviewed it" in p
    assert "ἀάω" in text_of(run["lsj_gold_lemma"])
    print("tokens (chars/4):", sizes)


def test_error_is_actionable(run):
    res = run["error"]
    assert is_error(res)
    assert "nearest: K15.609-610" in text_of(res)
