# galen-mcp: the Galen First Drafts for your AI assistant

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant (Claude Desktop, Claude Code, Cursor or any other MCP client) look things up in the
[Galen First Drafts](https://montblanctech.github.io/Galen/first-drafts/). These are machine first-draft English translations of 13 Galen works that have never
been translated into English, keyed by Kühn citation. Each unit has two independent renderings (A and B) and automatic checks.

**They are machine first drafts. No scholar has reviewed them.** Every answer says so and gives the public page URL to cite.

The server runs on your own machine over stdio. Nothing is hosted for it. On first use it fetches the published data over HTTPS from GitHub Pages
and raw.githubusercontent.com, caches it, and then works offline.

## Install

You need Python 3.10 or later. [uv](https://docs.astral.sh/uv/) is the easiest way; `uvx` fetches and runs the server in one step.

**Claude Desktop.** Add this to `claude_desktop_config.json` (Settings → Developer → Edit Config), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "galen": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Montblanctech/Galen#subdirectory=mcp", "galen-mcp"]
    }
  }
}
```

**Claude Code:**

```
claude mcp add galen -- uvx --from "git+https://github.com/Montblanctech/Galen#subdirectory=mcp" galen-mcp
```

**Cursor.** Add the same `mcpServers` block as for Claude Desktop to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

**Without uv:**

```
pip install "git+https://github.com/Montblanctech/Galen#subdirectory=mcp"
```

Then use `"command": "galen-mcp"` with no `args` in the configs above. Use the full path if the client cannot find it (`where galen-mcp` on Windows, `which galen-mcp` elsewhere).

## Tools

| tool | what it answers |
|---|---|
| `list_works(detail)` | the 13 works (and the Latin method test): slug, Kühn span, units, checks, page URL |
| `search_terms(query, limit, offset)` | find key terms by Greek (accents optional), LSJ key or gloss, or English rendering; when one match is clearly best, its full `get_term` answer comes in the same call |
| `get_term(lemma, work, detail, offset)` | how one lemma is rendered by A and B in each work, with its Kühn loci |
| `get_passage(citation_or_unit, work, detail)` | one unit by Kühn citation (`K15.609`, `K. XV 609`, `K18a.196`) or unit id: Greek, A, B, checks, page URL |
| `lsj_gold_lemma(form, limit)` | the gold lemma of a Greek or Latin word form in LSJ-Gold / LS-Gold |

Answers are short plain text. `detail="full"` gives more: key-term tables, every locus, sentences. Long lists stop at a fixed cap and say
`N more; pass offset=...`. Errors say what to do, for example `no unit at K15.6091; nearest: K15.609-610 (in-hipp-acut)`.

## Five questions to ask

1. "What does Galen say at Kühn XV 609, and do the two drafts agree on the key terms?"
2. "How do the drafts translate δριμύς across the works: acrid or pungent?"
3. "Where is νεῦρον rendered 'sinews' rather than 'nerves'? Show me the Greek."
4. "Which of these works had no English translation before, and which units failed the checks?"
5. "Which LSJ headword does LSJ-Gold give for ἀᾶται, and where is it cited?"

## Data, cache and privacy

The server uses only public files from the [Galen repository](https://github.com/Montblanctech/Galen) (branch `master`):

| data | public URL | size |
|---|---|---|
| a work's units, renderings A/B, checks, term table | `https://montblanctech.github.io/Galen/first-drafts/<slug>/data.json` | 0.15–18 MB each |
| the Latin method test (Vitruvius, *De architectura* III) | `https://montblanctech.github.io/Galen/method/vitruvius-3/data.json` | 0.6 MB |
| cross-work term index | `https://raw.githubusercontent.com/Montblanctech/Galen/master/galen-density-map/outputs/firstdrafts/_index/term_index.json` | 4 MB |
| LSJ-Gold 1.0, LS-Gold 1.0 | `https://raw.githubusercontent.com/Montblanctech/Galen/master/release/{lsj,ls}-gold-1.0/` | 11 MB, 24 MB |

- Each file is downloaded the first time a question needs it (gzip on the wire). The package bundles only a 13 KB catalog of the works, so that a
  citation can be routed to its work without downloading everything.
- The cache is in your user cache folder (`platformdirs`; on Windows `%LOCALAPPDATA%\galen-mcp\Cache`, on macOS `~/Library/Caches/galen-mcp`,
  on Linux `~/.cache/galen-mcp`). A cached file is used without any network call for 24 hours, then rechecked by its ETag. An unchanged file is
  not downloaded again. With no network the cached copy is used.
- `galen-mcp --refresh` rechecks every file on first use. `galen-mcp --offline` never uses the network. `galen-mcp --prefetch` downloads the
  drafts and the term index (about 55 MB) and exits, for offline use. `--cache-dir DIR` moves the cache.
- The only network traffic is these GET requests, with the user agent `galen-mcp/<version>`. There is no telemetry, no account and no key.
  Answers contain no local paths.

Environment variables: `GALEN_MCP_CACHE_DIR`, `GALEN_MCP_TTL_HOURS` (default 24), `GALEN_MCP_OFFLINE=1`.
Maintainers can set `GALEN_MCP_SOURCE_DIR` to read a local checkout of the repo instead.

## Licences

- Greek text: First1KGreek / Open Greek and Latin, CC BY-SA 4.0. Latin text of the method test: Perseus Digital Library, CC BY-SA 4.0.
- The drafts (renderings A and B, checks, term tables) are machine output published under **CC BY-SA 4.0**, as a translation of a CC BY-SA
  text. Each page says so. The cross-work term index is built from them and is shared under the same terms. Cite as the pages ask:
  Pepperman, W. (2026), *Galen First Drafts*, with the page URL.
- LSJ-Gold 1.0: data CC BY 4.0 (underlying texts First1KGreek CC BY-SA 4.0; Perseus LSJ XML CC BY-SA 3.0). LS-Gold 1.0: CC BY-SA 4.0.
  See each release's `LICENSE`.
- The repository's [`LICENSE-DATA`](../LICENSE-DATA) (CC BY 4.0) covers its census and derived data products. [`LICENSE`](../LICENSE) (MIT)
  covers the code, including this server.

## Response sizes

### Calls per question

`tests/test_agent_experience.py` walks ten typical questions through the tools by the shortest sensible path and fails if an answer needs more calls, or more tokens, than its budget. Nine of the ten take one call; the tenth ("find words about humours, then the passages for the top one") takes two by design. Run it with `pytest -s` to see the table.

Typical answers, measured with `python mcp/scripts/measure.py` (tokens counted as characters / 4). Greek costs more tokens per
character than English, so passages run somewhat higher in practice.

| call | tokens |
|---|---:|
| `list_works()` | 861 |
| `search_terms("nerve")` | 129 |
| `search_terms("humour")` (10 of 16 hits) | 444 |
| `get_term("γνώρισμα")` (7 works) | 300 |
| `get_term("δριμύς", detail="full")` (40 of 84 loci) | 1,528 |
| `get_term("νεῦρον", work="de-humero", detail="full")` | 584 |
| `get_passage("K15.609")` | 901 |
| `get_passage("K15.609", detail="full")` | 1,040 |
| `get_passage("K15.6091")` (error) | 33 |
| `lsj_gold_lemma("ἀγαθὸν")` | 109 |

## Development

```
python -m venv .venv && .venv/bin/pip install -e "./mcp[test]"
cd mcp && python -m pytest            # network-free: fixtures cut from the real data
GALEN_MCP_LIVE=1 python -m pytest tests/test_e2e_stdio.py   # once, against the live URLs
python mcp/scripts/build_catalog.py   # after the drafts change (from the repo root)
python mcp/tests/make_fixtures.py     # to recut the fixtures
```

The tests start the server over stdio with the MCP SDK's own client, list the tools and call each one. The server works with the `mcp`
SDK 1.x (`FastMCP`) and 2.x (`MCPServer`).

Install check, 2026-11-14 (Windows, Python 3.12): a fresh venv with `pip install ./mcp` (mcp 2.3.0); the offline suite passes (52 tests,
also on mcp 1.30.0), and the stdio end-to-end test passes against the live public URLs with an empty cache (3 tests, 5 s, all five tools).
A second run with `--refresh` revalidated every file by ETag and downloaded nothing.
