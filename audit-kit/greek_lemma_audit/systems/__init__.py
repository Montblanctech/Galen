"""System registry. Names accepted by ``--systems``."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .base import Availability, System
from .dilemma import DilemmaSystem
from .odycy import OdycySystem
from .reference import ReferenceSystem
from .stanza import StanzaSystem

SYSTEM_NAMES = ("reference", "odycy", "stanza-perseus", "stanza-proiel", "dilemma", "dilemma-guess", "stoicheia", "greta")


def make_system(
    name: str,
    *,
    stanza_cache_dirs: list[Path] | None = None,
    write_cache_dir: Path | None = None,
    allow_download: bool = False,
    stoicheia_dir: Path | None = None,
) -> System:
    if name == "reference":
        return ReferenceSystem()
    if name == "odycy":
        return OdycySystem()
    if name.startswith("stanza-"):
        return StanzaSystem(name.split("-", 1)[1], cache_dirs=stanza_cache_dirs,
                            write_cache_dir=write_cache_dir, allow_download=allow_download)
    if name == "dilemma":
        return DilemmaSystem(guess=False)
    if name == "dilemma-guess":
        return DilemmaSystem(guess=True)
    if name == "stoicheia":
        from .stoicheia import StoicheiaSystem

        return StoicheiaSystem(stoicheia_dir, partial_dir=(Path(write_cache_dir) / "stoicheia") if write_cache_dir else None)
    if name == "greta":
        from .greta import GretaSystem

        return GretaSystem()
    raise ValueError(f"unknown system {name!r}; known: {', '.join(SYSTEM_NAMES)}")


__all__ = ["Availability", "System", "SYSTEM_NAMES", "make_system", "ReferenceSystem",
           "OdycySystem", "StanzaSystem", "DilemmaSystem"]
