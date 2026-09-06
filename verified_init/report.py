"""Human-facing output: the evidence table and the drift report."""

from __future__ import annotations

from .claims import VERIFIED


def render_report(analysis) -> str:
    """Answer the question "why does AGENTS.md say that?" for every claim."""
    verified = [c for c in analysis.claims if c.status == VERIFIED]
    inferred = [c for c in analysis.claims if c.status != VERIFIED]

    lines = [
        "verified-init  {}".format(analysis.root),
        "detectors: {}".format(", ".join(analysis.detectors) or "(none matched)"),
        "",
    ]

    for label, note, group, marker in (
        ("VERIFIED", "read from a declared source", verified, "+"),
        ("INFERRED", "matched a convention, not declared", inferred, "?"),
    ):
        if not group:
            continue
        lines.append("{} ({})  {}".format(label, len(group), note))
        for claim in group:
            lines.append("  {} {}".format(marker, claim.id))
            lines.append("      {}".format(claim.text))
            lines.append("      evidence: {}".format(claim.evidence))
        lines.append("")

    if analysis.probes:
        lines.append("NOT FOUND ({})  checked for, absent".format(len(analysis.probes)))
        for probe in analysis.probes:
            why = "  ({})".format(probe.why) if probe.why else ""
            lines.append("  - {}: {}{}".format(probe.id, probe.looked_for, why))
        lines.append("")

    lines.append(
        "{} verified, {} inferred, {} not found".format(
            len(verified), len(inferred), len(analysis.probes)
        )
    )
    return "\n".join(lines)


def render_diff(diff: dict) -> str:
    """One line per drifted claim, removals first."""
    lines = []
    for claim_id in diff["removed"]:
        lines.append("  - {}  (no longer true)".format(claim_id))
    for claim_id in diff["added"]:
        lines.append("  + {}  (new)".format(claim_id))
    for entry in diff["changed"]:
        lines.append("  ~ {}".format(entry["id"]))
        lines.append("      was: {}".format(entry["from"]["text"]))
        lines.append("      now: {}".format(entry["to"]["text"]))
    return "\n".join(lines)
