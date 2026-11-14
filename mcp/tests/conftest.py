from pathlib import Path

import pytest

from galen_mcp.core import Galen
from galen_mcp.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "repo"


@pytest.fixture
def galen(tmp_path):
    return Galen(Store(tmp_path / "cache", source_dir=FIXTURES))


def no_local_paths(text: str) -> bool:
    return str(FIXTURES) not in text and ":\\" not in text and "/tmp" not in text and "Users" not in text
