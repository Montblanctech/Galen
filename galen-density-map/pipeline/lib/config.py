from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return _PROJECT_ROOT


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _PROJECT_ROOT / "config.yaml"
    with path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return cfg


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    """Resolve a paths.* entry relative to project root."""
    rel = cfg["paths"][key]
    path = Path(rel)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path
