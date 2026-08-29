"""Parse Kühn vol.page citations (including 18(1).793 style)."""

from __future__ import annotations

import re
from dataclasses import dataclass


# 11.46 | 11,46 | 18(1).793 | 17 (2). 337
KUHN_REF_RE = re.compile(
    r"""
    ^\s*
    (?P<vol>\d{1,2})
    \s*
    (?:\((?P<part>\d)\))?
    \s*[.,]\s*
    (?P<page>\d{1,4})
    \s*$
    """,
    re.VERBOSE,
)

# Loose hunt inside a bibl string: Gal. 11.46 / Gal.18(1).793
GAL_IN_TEXT_RE = re.compile(
    r"""
    Gal\.?\s*
    (?P<vol>\d{1,2})
    \s*
    (?:\((?P<part>\d)\))?
    \s*[.,]\s*
    (?P<page>\d{1,4})
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass(frozen=True)
class KuhnRef:
    volume: int
    page: int
    part: int | None = None

    @property
    def key(self) -> tuple[int, int]:
        return (self.volume, self.page)


def parse_kuhn_ref(text: str) -> KuhnRef | None:
    if not text:
        return None
    m = KUHN_REF_RE.match(text.strip())
    if not m:
        m = GAL_IN_TEXT_RE.search(text)
        if not m:
            return None
    part_s = m.group("part")
    return KuhnRef(
        volume=int(m.group("vol")),
        page=int(m.group("page")),
        part=int(part_s) if part_s else None,
    )
