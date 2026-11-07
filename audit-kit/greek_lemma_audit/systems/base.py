"""Pluggable lemmatizer systems.

Every system implements :class:`System`. ``probe()`` must never raise and must
never download anything: it reports whether the system can run here and why
not otherwise. ``run(work)`` returns the system's token stream for a work
(``None`` when it cannot produce one, with ``last_skip_reason`` set).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..corpus import Token, Work


@dataclass
class Availability:
    ok: bool
    detail: str = ""
    version: dict[str, Any] = field(default_factory=dict)
    untested: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.ok,
            "detail": self.detail,
            "version": self.version,
            "untested_adapter": self.untested,
        }


class System:
    name: str = "base"
    kind: str = "neural"  # "reference" | "neural" | "lexicon"
    # Whether the system reuses the anchor's tokenisation (token-level lemmatizer).
    token_level: bool = False

    def __init__(self) -> None:
        self.last_skip_reason: str = ""
        self._availability: Availability | None = None

    def probe(self) -> Availability:  # pragma: no cover - overridden
        raise NotImplementedError

    def availability(self) -> Availability:
        if self._availability is None:
            try:
                self._availability = self.probe()
            except Exception as exc:  # never let a probe kill the audit
                self._availability = Availability(False, f"probe raised {type(exc).__name__}: {exc}"[:300])
        return self._availability

    def run(self, work: Work) -> list[Token] | None:  # pragma: no cover - overridden
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        av = self.availability()
        return {"name": self.name, "kind": self.kind, **av.as_dict()}


def exc_text(exc: BaseException, limit: int = 240) -> str:
    return f"{type(exc).__name__}: {exc}".replace("\n", " ")[:limit]
