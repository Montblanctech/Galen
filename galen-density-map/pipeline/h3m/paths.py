"""H3-M output / cache paths. Artifacts under data/qc/h3m/; cache is gitignored."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.config import project_root, resolve_path
from lib.io_utils import ensure_dir

MORPHEUS_IMAGE = "perseidsproject/morpheus-perseids-api:v2.1.5"
MORPHEUS_LOCAL_URL = "http://127.0.0.1:1500"
MORPHEUS_FALLBACK_URL = "https://morph.perseids.org"
SAMPLE_5K_SEED = 20260827
RANDOM60_SEED = 20260725
G1C_COVERAGE_MAX = 0.15
G1A_MIN_ADMISSIBLE = 49
G2A_HANDPRINT_N = 20
G2A_ARTIFACT_MAX = 2
M3_MIN_SCORED = 50
G3A_AUDIT_N = 10


def h3m_dir(cfg: dict[str, Any]) -> Path:
    return ensure_dir(resolve_path(cfg, "qc") / "h3m")


def h3m_cache_dir(cfg: dict[str, Any]) -> Path:
    return ensure_dir(h3m_dir(cfg) / "cache")


def repo_root() -> Path:
    return project_root().parent
