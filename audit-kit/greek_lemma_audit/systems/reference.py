"""``reference`` system: the lemmas already present in the input JSONL.

In the Galen Density Project these are the frozen odyCy
(``grc_odycy_joint_trf==0.7.0``) lemmas from stage 03. For plain-text input the
reference system has nothing to offer and skips.
"""

from __future__ import annotations

from ..corpus import Token, Work
from .base import Availability, System


class ReferenceSystem(System):
    name = "reference"
    kind = "reference"
    token_level = True

    def __init__(self, label: str = "lemmas carried in the input JSONL") -> None:
        super().__init__()
        self.label = label

    def probe(self) -> Availability:
        return Availability(True, self.label, {"source": "input_jsonl"})

    def run(self, work: Work) -> list[Token] | None:
        if work.tokens is None:
            self.last_skip_reason = "plain-text input carries no reference lemmas"
            return None
        return work.tokens
