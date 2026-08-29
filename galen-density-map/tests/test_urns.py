import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from lib.urns import parse_cts_urn, urn_to_github_raw_url, urn_to_safe_filename


def test_parse_and_url():
    urn = "urn:cts:greekLit:tlg0057.tlg075.1st1K-grc1"
    p = parse_cts_urn(urn)
    assert p.namespace == "tlg0057"
    assert p.work == "tlg075"
    assert p.edition == "1st1K-grc1"
    url = urn_to_github_raw_url(urn)
    assert url.endswith("/tlg0057/tlg075/tlg0057.tlg075.1st1K-grc1.xml")


def test_safe_filename_keeps_dots():
    urn = "urn:cts:greekLit:tlg0057.tlg001.1st1K-grc1"
    assert urn_to_safe_filename(urn, ".xml") == "urn_cts_greekLit_tlg0057.tlg001.1st1K-grc1.xml"
