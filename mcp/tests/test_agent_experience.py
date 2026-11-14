"""Agent-experience checks: how many tool calls, and how many tokens, a scholar's question costs.

Each case is a question, the shortest sensible path an agent would take through the tools, the facts the answer
must contain, and budgets. A change that adds a hop (a fact moves out of a call's answer) or bloats an answer
fails here. Tokens are estimated as characters / 3 (Greek costs more than English per character).

Run with -s to print the table.
"""
import pytest

from galen_mcp.core import HONESTY

CASES = [
    # (question, path [(tool, kwargs)], must contain, max calls, max tokens over the whole path)
    ("Which works are covered, and where do I read them?",
     [("list_works", {})], ["hirudinibus", "in-hipp-acut", "https://montblanctech.github.io/Galen/first-drafts/"], 1, 1500),
    ("How do the drafts translate βδέλλα?",
     [("search_terms", {"query": "βδέλλα"})], ["leech", "Top match in full", "hirudinibus"], 1, 900),
    ("What Greek word is behind 'leech' and how is it rendered?",
     [("search_terms", {"query": "leech"})], ["βδέλλα", "Top match in full"], 1, 900),
    ("How is νεῦρον rendered across works? (typed without accents)",
     [("search_terms", {"query": "νευρον"})], ["νεῦρον", "Top match in full", "nerves"], 1, 1600),
    ("How is δριμύς rendered in each work?",
     [("get_term", {"lemma": "δριμύς"})], ["δριμύς", "A ", "B "], 1, 1500),
    ("Show me Kühn XV 609 with both drafts.",
     [("get_passage", {"citation_or_unit": "Kühn XV, 609"})], ["K15.609-610", "Greek: ", "\nA: ", "\nB: ", "Checks"], 1, 1500),
    ("I mistyped a citation: K15.6091.",
     [("get_passage", {"citation_or_unit": "K15.6091"})], ["nearest: K15.609-610"], 1, 200),
    ("Show the leeches passage at K11.317 with its key terms.",
     [("get_passage", {"citation_or_unit": "K11.317", "detail": "full"})], ["Key terms", "ὄνυξ"], 1, 2000),
    ("Which lemma does LSJ cite for ἀᾶται?",
     [("lsj_gold_lemma", {"form": "ἀᾶται"})], ["ἀάω", "LSJ-Gold"], 1, 400),
    ("Find words about humours, then the passages for the top one.",
     [("search_terms", {"query": "humour"}), ("get_term", {"lemma": "χυμός", "detail": "full"})], ["χυμός", "K"], 2, 2600),
]


def _call(galen, tool, kw):
    from galen_mcp.core import ToolError
    try:
        return getattr(galen, tool)(**kw)
    except ToolError as e:  # the server returns these to the agent as the answer
        return str(e)


@pytest.mark.parametrize("question,path,must,max_calls,max_tokens", CASES, ids=[c[0][:40] for c in CASES])
def test_question_cost(galen, question, path, must, max_calls, max_tokens):
    assert len(path) <= max_calls
    outs = [_call(galen, t, kw) for t, kw in path]
    joined = "\n".join(outs)
    for m in must:
        assert m in joined, f"{question!r}: missing {m!r}"
    tokens = len(joined) // 3
    print(f"\n{len(path)} call(s), ~{tokens} tokens: {question}")
    assert tokens <= max_tokens, f"{question!r}: ~{tokens} tokens > {max_tokens}"


def test_one_hop_answers_keep_the_honesty_line(galen):
    for q in ("βδέλλα", "leech", "νευρον"):
        out = galen.search_terms(q)
        assert "Top match in full" in out and out.endswith(HONESTY)


def test_ambiguous_search_does_not_inline(galen):
    out = galen.search_terms("humour")
    assert "Top match in full" not in out and "Open one with get_term" in out
