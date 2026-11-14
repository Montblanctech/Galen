"""Check the built site (docs/ or a scratch copy) the way a reader's browser and a link-preview bot see it (2026-11-13).

Reads every HTML page under the site root and reports, per page:
  - internal links (href/src) that point at a missing file, and #anchors that the target page does not define;
  - links to files in the GitHub repo (github.com/Montblanctech/Galen/blob|tree/master/...) whose path is not in this checkout;
  - images without alt text, form controls without a label;
  - headings that skip a level (h1 then h3), pages with no h1 or more than one;
  - a missing <title>, meta description, Open Graph / Twitter tags, canonical link, viewport or lang;
  - public pages missing from sitemap.xml, and sitemap entries with no page.
Links that JavaScript builds at run time (the work pages read data.json) are not seen; only the HTML as served.

Usage: python -X utf8 site_check.py [ROOT] [--json OUT]      (ROOT defaults to docs/; exit 1 if any link or anchor is broken)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SITE = "https://montblanctech.github.io/Galen/"
GH = re.compile(r"^https://github\.com/Montblanctech/Galen/(?:blob|tree)/master/([^#?]+)")
NOT_PUBLIC = {"mw-gold"}
SKIP = ("google",)  # Search Console verification file


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[tuple[str, str]] = []  # (tag, url)
        self.imgs_no_alt = 0
        self.imgs = 0
        self.controls: list[dict] = []
        self.label_for: set[str] = set()
        self.headings: list[int] = []
        self.meta: dict[str, str] = {}
        self.title = None
        self._in_title = False
        self._label_depth = 0
        self.lang = None
        self.canonical = None
        self.scripts_ext: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        for k in ("id", "name"):
            if k in a and (k == "id" or tag == "a"):
                self.ids.add(a[k])
        if tag == "html":
            self.lang = a.get("lang")
        if tag in ("a", "area") and "href" in a:
            self.links.append((tag, a["href"]))
        if tag == "link" and "href" in a:
            if a.get("rel") == "canonical":
                self.canonical = a["href"]
            else:
                self.links.append((tag, a["href"]))
        if tag in ("img", "script", "source", "iframe") and "src" in a:
            self.links.append((tag, a["src"]))
        if tag == "img":
            self.imgs += 1
            if "alt" not in a and a.get("role") != "presentation" and a.get("aria-hidden") != "true":
                self.imgs_no_alt += 1
        if tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit", "button", "reset"):
            self.controls.append({"tag": tag, "id": a.get("id"), "aria": bool(a.get("aria-label") or a.get("aria-labelledby") or a.get("title")),
                                  "wrapped": self._label_depth > 0})
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key] = a.get("content", "")
        if tag == "title":
            self._in_title = True
            self.title = ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def page_url(rel: str) -> str:
    return SITE + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


def resolve(root: Path, page_rel: str, url: str) -> tuple[Path | None, str]:
    """(file the link lands on, fragment); file None for links that leave the site."""
    sp = urlsplit(url)
    if sp.scheme in ("mailto", "javascript", "data", "tel"):
        return None, ""
    if sp.scheme or sp.netloc:
        full = url if sp.scheme else "https:" + url
        if not full.startswith(SITE):
            return None, ""
        path = full[len(SITE):].split("#")[0].split("?")[0]
        base = root
        target = base / unquote(path)
    else:
        if not sp.path:
            return root / page_rel, sp.fragment
        if sp.path.startswith("/"):
            # GitHub Pages serves the project at /Galen/, so a root-absolute link must start with /Galen/
            if not sp.path.startswith("/Galen/"):
                return root / "__outside_site__" / sp.path.lstrip("/"), sp.fragment
            target = root / unquote(sp.path[len("/Galen/"):])
        else:
            target = (root / page_rel).parent / unquote(sp.path)
    target = target.resolve()
    if url.split("#")[0].split("?")[0].endswith("/") or target.is_dir():
        target = target / "index.html"
    return target, sp.fragment


def check(root: Path) -> dict:
    root = root.resolve()
    pages: dict[str, Page] = {}
    sizes: dict[str, int] = {}
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel.startswith(SKIP):
            continue
        p = Page()
        p.feed(f.read_text(encoding="utf-8"))
        pages[rel] = p
        sizes[rel] = f.stat().st_size
    public = {r for r in pages if r.split("/")[0] not in NOT_PUBLIC}
    broken, anchors, gh_missing, issues = [], [], [], []
    home: set[str] = set()  # pages with a link to the front page
    for rel, p in pages.items():
        seen = set()
        for tag, url in p.links:
            if (url in seen) or not url or url.startswith("{") or "${" in url:
                continue
            seen.add(url)
            g = GH.match(url)
            if g:
                if not (REPO / unquote(g.group(1)).rstrip("/")).exists():
                    gh_missing.append({"page": rel, "url": url})
                continue
            target, frag = resolve(root, rel, url)
            if target is None:
                continue
            if not target.exists():
                broken.append({"page": rel, "tag": tag, "url": url})
                continue
            if root not in target.parents:
                broken.append({"page": rel, "tag": tag, "url": url, "why": "outside the site"})
                continue
            trel = target.relative_to(root).as_posix()
            if trel == "index.html":
                home.add(rel)
            if frag and "=" in frag:
                pass  # a hash route the page's script reads (term index #q=<term>), not an element id
            elif frag and target.suffix == ".html":
                tp = pages.get(trel)
                if tp is None:
                    anchors.append({"page": rel, "url": url, "why": "anchor into a page not checked"})
                elif unquote(frag) not in tp.ids:
                    anchors.append({"page": rel, "url": url})
        if rel not in public:
            continue
        if rel != "index.html" and rel not in home:
            issues.append({"page": rel, "kind": "no link to the front page", "detail": ""})
        miss = []
        if not (p.title or "").strip():
            miss.append("title")
        if not p.meta.get("description"):
            miss.append("meta description")
        for k in ("og:title", "og:description", "og:image", "og:url", "twitter:card"):
            if not p.meta.get(k):
                miss.append(k)
        if not p.canonical:
            miss.append("canonical")
        elif p.canonical != page_url(rel):
            issues.append({"page": rel, "kind": "canonical", "detail": p.canonical})
        if "viewport" not in p.meta:
            miss.append("viewport")
        if not p.lang:
            miss.append("lang")
        if miss:
            issues.append({"page": rel, "kind": "missing", "detail": ", ".join(miss)})
        h = p.headings
        if h.count(1) != 1:
            issues.append({"page": rel, "kind": "h1 count", "detail": str(h.count(1))})
        skips = sorted({f"h{a}->h{b}" for a, b in zip(h, h[1:]) if b > a + 1} | ({f"starts h{h[0]}"} if h and h[0] != 1 else set()))
        if skips:
            issues.append({"page": rel, "kind": "heading skip", "detail": ", ".join(skips)})
        if p.imgs_no_alt:
            issues.append({"page": rel, "kind": "img without alt", "detail": str(p.imgs_no_alt)})
        unl = [c for c in p.controls if not (c["aria"] or c["wrapped"] or (c["id"] and c["id"] in p.label_for))]
        if unl:
            issues.append({"page": rel, "kind": "control without label", "detail": ", ".join(f'{c["tag"]}#{c["id"]}' for c in unl)})
    sm = root / "sitemap.xml"
    sm_urls = set(re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8"))) if sm.exists() else set()
    want = {page_url(r) for r in public}
    return {"pages": len(pages), "public": len(public), "broken_links": broken, "broken_anchors": anchors, "github_missing": gh_missing,
            "issues": issues, "sitemap_missing": sorted(want - sm_urls), "sitemap_extra": sorted(sm_urls - want),
            "html_bytes": sizes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(REPO / "docs"))
    ap.add_argument("--json")
    a = ap.parse_args()
    r = check(Path(a.root))
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{r['pages']} pages ({r['public']} public)")
    for k in ("broken_links", "broken_anchors", "github_missing", "sitemap_missing", "sitemap_extra"):
        print(f"{k}: {len(r[k])}")
        for x in r[k][:15]:
            print("   ", x)
    print("issues:", len(r["issues"]))
    for x in r["issues"]:
        print("   ", x)
    sys.exit(1 if r["broken_links"] or r["broken_anchors"] or r["github_missing"] else 0)


if __name__ == "__main__":
    main()
