"""The claim model.

A *claim* is one statement that will appear in AGENTS.md, together with the
evidence that justifies it. Nothing reaches the output without an ``evidence``
string naming a real file and locator, and that rule is enforced in the
constructor rather than by convention.

A *probe* records something that was looked for and not found. Probes never
reach AGENTS.md; they exist so a reader can tell "absent" apart from
"not checked".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

VERIFIED = "verified"
INFERRED = "inferred"

#: Section order in the generated file. Also the sort key for claims.
SECTIONS: List[str] = ["Project", "Setup", "Build & Test", "Layout", "Conventions"]

_SECTION_INDEX = {name: i for i, name in enumerate(SECTIONS)}


@dataclass(frozen=True)
class Claim:
    """One provable statement about the repository.

    Attributes:
        id: Stable identifier. Drift is diffed on these, so they must not
            change between releases for the same underlying fact.
        section: Which AGENTS.md heading this belongs under.
        text: The sentence written into AGENTS.md.
        status: ``VERIFIED`` when read from a file the project maintains,
            ``INFERRED`` when a convention matched but nothing declares it.
        evidence: Human-readable "file -> locator = value".
    """

    id: str
    section: str
    text: str
    status: str
    evidence: str

    def __post_init__(self) -> None:
        for name in ("id", "section", "text", "evidence"):
            if not getattr(self, name):
                raise ValueError(f"Claim({self.id!r}): {name} is required")
        if self.status not in (VERIFIED, INFERRED):
            raise ValueError(f"Claim({self.id!r}): unknown status {self.status!r}")
        if self.section not in _SECTION_INDEX:
            raise ValueError(f"Claim({self.id!r}): unknown section {self.section!r}")

    @property
    def sort_key(self):
        return (_SECTION_INDEX[self.section], self.id)


@dataclass(frozen=True)
class Probe:
    """Something checked for and absent."""

    id: str
    looked_for: str
    why: str = ""


@dataclass(frozen=True)
class Context:
    """What a detector needs to know about the run itself.

    ``output_name`` exists so no detector can make a claim about the file this
    run is about to write. A generated file that asserts its own existence adds
    a claim the moment it is created, and the very next ``--check`` reports
    drift against a repository nobody touched.
    """

    output_name: str = "CLAUDE.md"


@dataclass
class Analysis:
    """The full result of reading a repository."""

    root: str
    detectors: List[str] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)
    probes: List[Probe] = field(default_factory=list)

    def by_id(self, claim_id: str):
        for c in self.claims:
            if c.id == claim_id:
                return c
        return None


def sort_claims(claims):
    """Deterministic ordering: section order first, then id."""
    return sorted(claims, key=lambda c: c.sort_key)
