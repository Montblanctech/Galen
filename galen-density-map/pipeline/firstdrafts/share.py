"""Galen First Drafts — link previews and search data (2026-11-11).

Makes the public pages travel well when shared and read well by search engines:
  1. docs/og-card.png: a 1200x630 share card (title, counts), drawn with Pillow.
  2. Open Graph and Twitter card tags in every public page's <head> (title and description from the page itself).
  3. JSON-LD on the front page (WebSite + Dataset for the drafts) and on the findings page (Dataset).
Idempotent: a page that already carries the tags is left alone. Called from landing.main() after the beacon.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DOCS = REPO / "docs"
SITE = "https://montblanctech.github.io/Galen/"
CARD = "og-card.png"
MARK = "<!-- share tags -->"


def draw_card(n_works: int, n_words: int, n_findings: int) -> None:
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (250, 247, 240))
    d = ImageDraw.Draw(img)
    fonts = Path("C:/Windows/Fonts")
    serif = lambda s: ImageFont.truetype(str(fonts / "georgia.ttf"), s)
    serif_b = lambda s: ImageFont.truetype(str(fonts / "georgiab.ttf"), s)
    sans = lambda s: ImageFont.truetype(str(fonts / "segoeui.ttf"), s)
    accent = (122, 31, 31)
    d.rectangle([0, 0, W, 14], fill=accent)
    d.text((80, 80), "GALEN DENSITY PROJECT", font=sans(26), fill=accent)
    d.text((80, 130), "Galen in English", font=serif_b(84), fill=(31, 27, 22))
    d.text((80, 230), "for the first time", font=serif_b(84), fill=(31, 27, 22))
    d.text((80, 360), f"{n_works} works never before published in full in English,", font=serif(34), fill=(60, 54, 46))
    d.text((80, 408), f"{n_words:,} words of Greek, machine first drafts with the Greek beside them.", font=serif(34), fill=(60, 54, 46))
    d.text((80, 470), f"Plus {n_findings} things the drafts say: people, lost books, recipes, cases.", font=serif(34), fill=(60, 54, 46))
    d.text((80, 548), "montblanctech.github.io/Galen", font=sans(30), fill=accent)
    img.save(DOCS / CARD, optimize=True)


def head_tags(rel: str, title: str, desc: str) -> str:
    url = SITE + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)
    e = lambda s: html.escape(s, quote=True)
    return (f'{MARK}<meta property="og:type" content="website"><meta property="og:site_name" content="Galen in English">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">'
            f'<meta property="og:url" content="{e(url)}"><meta property="og:image" content="{SITE}{CARD}">'
            f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">'
            f'<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{SITE}{CARD}">'
            f'<link rel="canonical" href="{e(url)}">')


def jsonld(obj: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"


def apply(n_works: int, n_words: int, n_findings: int, not_public: set[str]) -> int:
    draw_card(n_works, n_words, n_findings)
    author = {"@type": "Person", "name": "William Pepperman"}
    ld = {
        "index.html": jsonld({"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "name": "Galen in English", "url": SITE},
            {"@type": "Dataset", "name": "Galen First Drafts", "url": SITE + "first-drafts/", "creator": author,
             "description": f"Machine first-draft English translations of {n_works} works of Galen with no complete English translation, "
                            f"{n_words:,} words of Greek, each with two independent renderings, the Greek, and machine checks.",
             "license": "https://creativecommons.org/licenses/by-sa/4.0/", "inLanguage": ["en", "grc"],
             "isAccessibleForFree": True, "keywords": ["Galen", "ancient medicine", "Ancient Greek", "translation", "history of medicine"]}]}),
        "findings/index.html": jsonld({"@context": "https://schema.org", "@type": "Dataset", "name": "What the drafts say: findings from Galen First Drafts",
                                       "url": SITE + "findings/", "creator": author, "isAccessibleForFree": True,
                                       "description": f"{n_findings} items catalogued from the drafts: people, lost authors and books, recipes, cases, "
                                                      "prices and measures, each linked to its passage, with an attestation check of every lost work.",
                                       "keywords": ["Galen", "lost works", "ancient pharmacology", "Roman medicine"]}),
    }
    n = 0
    for f in DOCS.rglob("*.html"):
        rel = f.relative_to(DOCS).as_posix()
        if rel.split("/")[0] in not_public or rel.startswith("google"):
            continue
        t = f.read_text(encoding="utf-8")
        if MARK in t or "</head>" not in t:
            continue
        m = re.search(r"<title>(.*?)</title>", t, re.S)
        title = html.unescape(m.group(1)).strip() if m else "Galen in English"
        m = re.search(r'<meta name=["\']?description["\']? content="([^"]*)"', t)
        desc = html.unescape(m.group(1)) if m else f"{title}: a machine first draft in English, with the Greek beside it. Unverified; for reading and correcting."
        add = head_tags(rel, title, desc) + ld.get(rel, "")
        f.write_text(t.replace("</head>", add + "</head>", 1), encoding="utf-8")
        n += 1
    return n
