from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import read_json


def load_census(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if "works" not in data:
        raise ValueError(f"Census JSON missing 'works': {path}")
    return data


def _is_grc_edition(work: dict[str, Any]) -> bool:
    """Keep Greek editions only (languages field and/or URN edition suffix)."""
    langs = str(work.get("languages") or "").lower()
    urn = str(work.get("urn") or "").lower()
    if langs:
        return "grc" in langs.split(",") or langs.strip() == "grc" or "grc" in langs
    return "-grc" in urn or ".grc" in urn or urn.endswith("grc1") or urn.endswith("grc2")


def filter_galen_works(
    cfg: dict[str, Any],
    census: dict[str, Any],
    *,
    all_categories: bool = False,
) -> list[dict[str, Any]]:
    """Select Galen works from the Phase 1 census.

    Default: medical ``category_scope`` only.
    ``all_categories=True``: every tlg0057 URN in the census (whole-Galen axis),
    still grc-only and respecting ``include_pseudo_galen``.
    """
    scope = set(cfg.get("category_scope") or [])
    include_pseudo = bool(cfg.get("include_pseudo_galen", False))
    selected: list[dict[str, Any]] = []
    seen_urns: set[str] = set()

    for work in census.get("works", []):
        if not _is_grc_edition(work):
            continue
        cat = work.get("category")
        if not all_categories and scope and cat not in scope:
            continue
        urn = work.get("urn")
        if not urn or urn in seen_urns:
            continue
        seen_urns.add(urn)
        selected.append(work)

    if include_pseudo:
        for work in census.get("pseudo_galen_excluded_from_main_count", []) or []:
            if not _is_grc_edition(work):
                continue
            urn = work.get("urn")
            if not urn or urn in seen_urns:
                continue
            cat = work.get("category")
            if not all_categories and scope and cat not in scope:
                continue
            seen_urns.add(urn)
            selected.append(work)

    return selected


def medical_urn_stems(cfg: dict[str, Any], census: dict[str, Any]) -> set[str]:
    """Safe filename stems for the medical subcorpus (category_scope)."""
    from .urns import urn_to_safe_filename

    return {urn_to_safe_filename(w["urn"]) for w in filter_galen_works(cfg, census)}
