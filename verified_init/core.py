"""Run every detector over a repository and merge the results.

The output of :func:`analyze` is a pure function of the bytes on disk. There
are no model calls, no network, no subprocesses and no clock reads, so the same
repository always produces the same analysis — on any machine, on any day, with
any model driving the tool. That property is what ``tests/test_determinism``
pins down.
"""

from __future__ import annotations

from .claims import Analysis, Context, VERIFIED, sort_claims
from .detectors import DETECTORS

DEFAULT_OUTPUT = "CLAUDE.md"

#: A specific claim makes a generic one redundant, or outright contradicts it.
#: Java's ``src/test/java`` says where the tests are, so the generic "looked for
#: test/, tests/ and found none" probe would appear alongside it and read as a
#: contradiction. Detectors cannot see each other, so the resolution lives here.
SUPERSEDES = {
    "java.layout.src.main.java": ("repo.layout.src",),
    "java.layout.src.test.java": ("repo.layout.tests", "repo.layout.test"),
    "node.workspaces": ("repo.layout.packages",),
}


def analyze(root: str, output_name: str = DEFAULT_OUTPUT) -> Analysis:
    """Read ``root`` and return every claim that could be justified.

    Args:
        root: Path to the repository to read. Never written to, never executed.
        output_name: Name of the file this run will write. Detectors exclude it
            so nothing claims the existence of the file being generated.

    Returns:
        An :class:`~verified_init.claims.Analysis` with claims sorted
        deterministically and probes limited to ids nothing managed to prove.
    """
    ctx = Context(output_name=output_name)
    by_id = {}
    all_probes = []
    matched = []

    for detector in DETECTORS:
        result = detector.detect(root, ctx)
        if result is None:
            continue
        matched.append(detector.ID)

        claims, probes = result
        for claim in claims:
            existing = by_id.get(claim.id)
            if existing is None:
                by_id[claim.id] = claim
            elif existing.status != VERIFIED and claim.status == VERIFIED:
                # A declared fact supersedes a convention that merely matched.
                by_id[claim.id] = claim
        all_probes.extend(probes)

    superseded = set()
    for claim_id, replaced in SUPERSEDES.items():
        if claim_id in by_id:
            superseded.update(replaced)
    for claim_id in superseded:
        by_id.pop(claim_id, None)

    # A probe is only worth reporting if nothing ended up proving that id, and
    # nothing more specific has already answered the question.
    open_probes = [p for p in all_probes if p.id not in by_id and p.id not in superseded]
    open_probes.sort(key=lambda p: p.id)

    return Analysis(
        root=root,
        detectors=matched,
        claims=sort_claims(by_id.values()),
        probes=open_probes,
    )
