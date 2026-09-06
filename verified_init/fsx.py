"""Filesystem reads.

Every function here is total: a missing or unreadable path yields ``None`` or
an empty result rather than raising. Detectors are therefore free to probe
speculatively, which is what lets them report "checked, absent".

Nothing in this module executes anything.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional


def read_text(root: str, rel: str) -> Optional[str]:
    """File contents as text, or ``None`` if missing/unreadable/not UTF-8."""
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def read_json(root: str, rel: str) -> Optional[Any]:
    """Parsed JSON, or ``None`` if missing or malformed."""
    raw = read_text(root, rel)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def exists(root: str, rel: str) -> bool:
    return os.path.exists(os.path.join(root, rel))


def is_dir(root: str, rel: str) -> bool:
    return os.path.isdir(os.path.join(root, rel))


def is_file(root: str, rel: str) -> bool:
    return os.path.isfile(os.path.join(root, rel))


def list_dir(root: str, rel: str) -> List[str]:
    """Sorted names in a directory; empty when it does not exist.

    Sorted because the generated file must be byte-identical across runs and
    across machines, and directory order is not guaranteed.
    """
    try:
        return sorted(os.listdir(os.path.join(root, rel)))
    except OSError:
        return []


def first_existing(root: str, candidates) -> Optional[str]:
    """The first candidate path that exists, or ``None``."""
    for c in candidates:
        if exists(root, c):
            return c
    return None
