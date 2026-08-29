from __future__ import annotations

from dataclasses import dataclass


FIRST1K_RAW_BASE = (
    "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data"
)


@dataclass(frozen=True)
class ParsedUrn:
    namespace: str
    work: str
    edition: str

    @property
    def full(self) -> str:
        return f"urn:cts:greekLit:{self.namespace}.{self.work}.{self.edition}"


def parse_cts_urn(urn: str) -> ParsedUrn:
    # urn:cts:greekLit:tlg0057.tlg075.1st1K-grc1
    if not urn.startswith("urn:cts:"):
        raise ValueError(f"Not a CTS URN: {urn}")
    parts = urn.split(":")
    if len(parts) < 4:
        raise ValueError(f"Malformed CTS URN: {urn}")
    textgroup_work_edition = parts[3]
    bits = textgroup_work_edition.split(".")
    if len(bits) < 3:
        raise ValueError(f"Expected textgroup.work.edition in URN: {urn}")
    namespace, work, edition = bits[0], bits[1], ".".join(bits[2:])
    return ParsedUrn(namespace=namespace, work=work, edition=edition)


def urn_to_github_raw_url(urn: str) -> str:
    p = parse_cts_urn(urn)
    filename = f"{p.namespace}.{p.work}.{p.edition}.xml"
    return f"{FIRST1K_RAW_BASE}/{p.namespace}/{p.work}/{filename}"


def urn_to_safe_filename(urn: str, ext: str = "") -> str:
    safe = urn.replace(":", "_").replace("/", "_")
    return f"{safe}{ext}"
