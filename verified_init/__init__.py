"""verified-init: an AGENTS.md that contains only claims it can prove.

Deterministic and offline by construction. It reads manifests and the
filesystem; it never executes your code, never opens a socket, and never calls
a language model. The same repository therefore yields the same CLAUDE.md no
matter which agent or model invoked it, and running it costs zero tokens.
"""

from __future__ import annotations

from .claims import Analysis, Claim, Context, INFERRED, Probe, SECTIONS, VERIFIED
from .core import DEFAULT_OUTPUT, analyze
from .render import BEGIN, END, render_agents_md
from .report import render_diff, render_report
from .state import STATE_FILE, build_state, diff_state, has_drift, read_state, write_state

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Analysis",
    "Claim",
    "Probe",
    "Context",
    "DEFAULT_OUTPUT",
    "SECTIONS",
    "VERIFIED",
    "INFERRED",
    "analyze",
    "render_agents_md",
    "render_report",
    "render_diff",
    "build_state",
    "read_state",
    "write_state",
    "diff_state",
    "has_drift",
    "STATE_FILE",
    "BEGIN",
    "END",
]
