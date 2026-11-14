"""Link checker for the public site (pipeline/firstdrafts/site_check.py), 2026-11-13 site audit.

Synthetic sites for each kind of fault the checker must catch, the landing pass that adds home links and search
labels (idempotent), and a data-dependent run over docs/: no broken link, no broken anchor, no link to a repo file
that is not in this checkout, and every public page in the sitemap.
"""
import sys
from pathlib import Path

import pytest

GDM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GDM / "pipeline"))
sys.path.insert(0, str(GDM / "pipeline" / "firstdrafts"))

import site_check  # noqa: E402

DOCS = GDM.parent / "docs"
HEAD = ("<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>{t}</title><meta name=description content=\"d\"></head><body>")


def page(root: Path, rel: str, body: str, title: str = "t") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(HEAD.format(t=title) + body + "</body></html>", encoding="utf-8")


def sitemap(root: Path, rels: list[str]) -> None:
    locs = "".join(f"<url><loc>{site_check.page_url(r)}</loc></url>" for r in rels)
    (root / "sitemap.xml").write_text(f'<?xml version="1.0"?><urlset>{locs}</urlset>', encoding="utf-8")


def test_good_site_is_clean(tmp_path):
    page(tmp_path, "index.html", '<h1>x</h1><a href="w/">w</a> <a href="w/book-1.html#K1.2">p</a> <a href="#top" id=top>t</a>')
    page(tmp_path, "w/index.html", '<h1>w</h1><a href="../">home</a> <a href="../index.html#top">top</a>')
    page(tmp_path, "w/book-1.html", '<h1>b</h1><div id="K1.2"></div><a href="./">contents</a> <a href="../">home</a>')
    sitemap(tmp_path, ["index.html", "w/index.html", "w/book-1.html"])
    r = site_check.check(tmp_path)
    assert r["broken_links"] == [] and r["broken_anchors"] == [] and r["sitemap_missing"] == [] and r["sitemap_extra"] == []
    assert not [i for i in r["issues"] if i["kind"] == "no link to the front page"]


def test_catches_broken_link_anchor_and_outside(tmp_path):
    page(tmp_path, "index.html", '<h1>x</h1><a href="w/">w</a> <a href="nope.html">x</a> <a href="w/index.html#missing">a</a>'
                                 '<img src="gone.png" alt=""> <a href="/elsewhere/">root-absolute, not under /Galen/</a>')
    page(tmp_path, "w/index.html", '<h1>w</h1><a href="../">home</a>')
    sitemap(tmp_path, ["index.html"])
    r = site_check.check(tmp_path)
    assert {b["url"] for b in r["broken_links"]} == {"nope.html", "gone.png", "/elsewhere/"}
    assert [a["url"] for a in r["broken_anchors"]] == ["w/index.html#missing"]
    assert r["sitemap_missing"] == [site_check.SITE + "w/"]


def test_parent_links_are_normalised(tmp_path):
    # a "../" link must resolve to the page it names (a first version compared unnormalised paths)
    page(tmp_path, "index.html", '<h1>x</h1><div id=a></div>')
    page(tmp_path, "a/b/index.html", '<h1>b</h1><a href="../../#a">home</a> <a href="../../index.html#zzz">bad</a>')
    r = site_check.check(tmp_path)
    assert [a["url"] for a in r["broken_anchors"]] == ["../../index.html#zzz"]
    assert not [i for i in r["issues"] if i["page"] == "a/b/index.html" and i["kind"] == "no link to the front page"]


def test_repo_links_must_exist(tmp_path):
    page(tmp_path, "index.html", '<h1>x</h1><a href="https://github.com/Montblanctech/Galen/blob/master/README.md">ok</a>'
                                 '<a href="https://github.com/Montblanctech/Galen/blob/master/no_such_file_2026.md">gone</a>')
    r = site_check.check(tmp_path)
    assert [g["url"].rsplit("/", 1)[1] for g in r["github_missing"]] == ["no_such_file_2026.md"]


def test_page_issues(tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>x</title></head><body><h2>a</h2><h4>b</h4><img src=i.png>"
                                         "<input id=q placeholder=s></body></html>", encoding="utf-8")
    (tmp_path / "i.png").write_bytes(b"")
    kinds = {i["kind"]: i["detail"] for i in site_check.check(tmp_path)["issues"]}
    assert "meta description" in kinds["missing"] and "og:title" in kinds["missing"] and "lang" in kinds["missing"]
    assert kinds["h1 count"] == "0" and "h2->h4" in kinds["heading skip"]
    assert kinds["img without alt"] == "1" and kinds["control without label"] == "input#q"


def test_landing_adds_home_link_and_labels_once(tmp_path, monkeypatch):
    import landing
    monkeypatch.setattr(landing, "DOCS", tmp_path)
    page(tmp_path, "index.html", "<h1>home</h1>")
    page(tmp_path, "lb/index.html", "<h1>board</h1><input id=q placeholder=\"search\">")
    page(tmp_path, "t/a/index.html", '<h1>a</h1><a href="../../">home</a>')
    assert landing.add_home_link() == 1 and landing.add_labels() == 1
    once = (tmp_path / "lb" / "index.html").read_text(encoding="utf-8")
    assert landing.add_home_link() == 0 and landing.add_labels() == 0
    assert (tmp_path / "lb" / "index.html").read_text(encoding="utf-8") == once
    r = site_check.check(tmp_path)
    assert r["broken_links"] == []
    assert not [i for i in r["issues"] if i["kind"] in ("no link to the front page", "control without label")]


@pytest.mark.skipif(not (DOCS / "index.html").exists(), reason="no built site")
def test_published_site_links():
    r = site_check.check(DOCS)
    assert r["pages"] >= 40
    assert r["broken_links"] == [], r["broken_links"][:5]
    assert r["broken_anchors"] == [], r["broken_anchors"][:5]
    assert r["github_missing"] == [], r["github_missing"][:5]
    assert r["sitemap_missing"] == [] and r["sitemap_extra"] == []


def test_term_explorer_split_keeps_every_record(tmp_path):
    import json
    import galen_term_explorer as g
    recs = [{"l": "α", "ctx": ["one", "two"], "n": 1}, {"l": "β", "ctx": [], "n": 2}]
    (tmp_path / "terms.json").write_text(json.dumps({"generated": "x", "n": 2, "records": recs}, ensure_ascii=False), encoding="utf-8")
    old_page = g.HTML.replace(g.NEW_FETCH, g.OLD_FETCH).replace(g.NEW_CTX, g.OLD_CTX)
    (tmp_path / "index.html").write_text(old_page, encoding="utf-8")
    assert g.split_existing(tmp_path).startswith("split")
    main_ = json.loads((tmp_path / "terms.json").read_text(encoding="utf-8"))
    ctx = json.loads((tmp_path / "terms_ctx.json").read_text(encoding="utf-8"))["ctx"]
    assert main_["ctx_file"] is True and all("ctx" not in r for r in main_["records"])
    assert [{**r, "ctx": c} for r, c in zip(main_["records"], ctx)] == recs
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert page == g.HTML and g.split_existing(tmp_path) == "already split"
