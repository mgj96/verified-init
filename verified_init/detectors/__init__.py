"""Detectors, in the order they get to speak.

Order matters only for tie-breaking: when two detectors produce the same claim
id with the same status, the earlier one wins. A VERIFIED claim always beats an
INFERRED one regardless of order.
"""

from . import ci, java, misc, node, repo

DETECTORS = [node, java, misc, ci, repo]

__all__ = ["DETECTORS", "node", "java", "misc", "ci", "repo"]
