"""The drift baseline.

``.verified-init.json`` records the exact claim set, and the evidence behind
each claim, as of the last generation. ``--check`` re-derives the claims and
compares. Because deriving claims runs no commands and calls no model, the
comparison is cheap enough to run on every pull request.
"""

from __future__ import annotations

import json
import os
from typing import Optional

STATE_FILE = ".verified-init.json"
STATE_VERSION = 1


def build_state(analysis, version: str) -> dict:
    """Serialisable snapshot of an analysis.

    Keys are sorted on write, and no timestamp is recorded, so an unchanged
    repository produces a byte-identical file.
    """
    return {
        "version": STATE_VERSION,
        "generator": "verified-init@{}".format(version),
        "detectors": list(analysis.detectors),
        "claims": {
            c.id: {"text": c.text, "status": c.status, "evidence": c.evidence}
            for c in analysis.claims
        },
        "notFound": sorted(p.looked_for for p in analysis.probes),
    }


def read_state(root: str) -> Optional[dict]:
    try:
        with open(os.path.join(root, STATE_FILE), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_state(root: str, state: dict) -> None:
    path = os.path.join(root, STATE_FILE)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(state, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def diff_state(previous: dict, current: dict) -> dict:
    """Compare two snapshots.

    Returns:
        ``{"added": [...], "removed": [...], "changed": [{"id", "from", "to"}]}``
        with every list sorted, so the report is stable.
    """
    prev_claims = (previous or {}).get("claims", {})
    next_claims = (current or {}).get("claims", {})

    added = sorted(cid for cid in next_claims if cid not in prev_claims)
    removed = sorted(cid for cid in prev_claims if cid not in next_claims)
    changed = sorted(
        (
            {"id": cid, "from": prev_claims[cid], "to": next_claims[cid]}
            for cid in next_claims
            if cid in prev_claims and prev_claims[cid] != next_claims[cid]
        ),
        key=lambda entry: entry["id"],
    )
    return {"added": added, "removed": removed, "changed": changed}


def has_drift(diff: dict) -> bool:
    return bool(diff["added"] or diff["removed"] or diff["changed"])
