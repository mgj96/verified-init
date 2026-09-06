#!/usr/bin/env python3
"""Entry point for the Claude Code skill.

Resolves the ``verified_init`` package without needing it installed: the skill
normally lives inside a clone of the repository, so the package sits three
levels up. If the skill directory was copied somewhere on its own, this falls
back to a regular import, which works when the package was pip-installed.

Standard library only, so `python scripts/run.py` works on any machine that has
Python 3.9+ and nothing else.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> verified-init/ -> skills/ -> <repo root>
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

if os.path.isdir(os.path.join(_REPO_ROOT, "verified_init")):
    sys.path.insert(0, _REPO_ROOT)

try:
    from verified_init.cli import main
except ImportError:  # pragma: no cover - environment-specific
    sys.stderr.write(
        "verified-init: could not import the verified_init package.\n"
        "  Looked in: {}\n"
        "  Either keep this skill inside a clone of the repository, or run\n"
        "  `pip install verified-init`.\n".format(_REPO_ROOT)
    )
    raise SystemExit(2)

if __name__ == "__main__":
    raise SystemExit(main())
