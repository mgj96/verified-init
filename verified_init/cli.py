"""Command line interface.

Exit codes are the contract for CI:
    0  wrote the file, or checked and found no drift
    1  drift detected
    2  nothing provable, or a usage error
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .core import DEFAULT_OUTPUT, analyze
from .render import render_agents_md
from .report import render_diff, render_report
from .state import (
    STATE_FILE,
    build_state,
    diff_state,
    has_drift,
    read_state,
    write_state,
)

DESCRIPTION = (
    "Generate a CLAUDE.md that contains only claims it can prove. "
    "Reads manifests and the filesystem. Never executes your code, "
    "never opens a socket, never calls a model."
)

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verified-init",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit codes:\n"
            "  0  ok / no drift\n"
            "  1  drift detected\n"
            "  2  nothing provable, or a usage error\n"
        ),
    )
    parser.add_argument("path", nargs="?", default=".", help="repository to read (default: .)")
    parser.add_argument(
        "--out",
        default=DEFAULT_OUTPUT,
        help="output file (default: {}); use --out AGENTS.md for the "
        "cross-agent filename".format(DEFAULT_OUTPUT),
    )
    parser.add_argument(
        "-V", "--version", action="version", version="verified-init {}".format(__version__)
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--report", action="store_true", help="print the evidence table, write nothing"
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the repository drifted from {}".format(STATE_FILE),
    )
    mode.add_argument("--json", action="store_true", help="print the analysis as JSON")
    return parser


def _analysis_to_dict(analysis) -> dict:
    return {
        "root": analysis.root,
        "detectors": list(analysis.detectors),
        "claims": [
            {
                "id": c.id,
                "section": c.section,
                "text": c.text,
                "status": c.status,
                "evidence": c.evidence,
            }
            for c in analysis.claims
        ],
        "notFound": [
            {"id": p.id, "lookedFor": p.looked_for, "why": p.why} for p in analysis.probes
        ],
    }


def _force_utf8_streams() -> None:
    """Make console output independent of the machine's code page.

    Manifests routinely carry non-ASCII text: a Korean description, an umlaut,
    an emoji. On a Windows console using a legacy code page, writing that text
    raises UnicodeEncodeError and the tool dies with a traceback instead of
    printing a report. ``errors="replace"`` keeps a legacy console readable
    while redirected output stays exact UTF-8.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # Not a reconfigurable text stream (a test harness capture, a
            # closed pipe). Nothing to do; writing may still succeed.
            pass


def main(argv=None) -> int:
    _force_utf8_streams()
    args = build_parser().parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        sys.stderr.write("verified-init: not a directory: {}\n".format(root))
        return EXIT_ERROR

    analysis = analyze(root, output_name=args.out)

    if not analysis.claims:
        sys.stderr.write(
            "verified-init: nothing provable found in {}\n"
            "  No package.json, pom.xml, build.gradle, go.mod, Cargo.toml,\n"
            "  pyproject.toml or Makefile was readable here.\n"
            "  Refusing to write a {} of guesses.\n".format(root, args.out)
        )
        return EXIT_ERROR

    if args.json:
        sys.stdout.write(
            json.dumps(_analysis_to_dict(analysis), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        )
        return EXIT_OK

    if args.report:
        sys.stdout.write(render_report(analysis) + "\n")
        return EXIT_OK

    current = build_state(analysis, __version__)

    if args.check:
        previous = read_state(root)
        if previous is None:
            sys.stderr.write(
                "verified-init: no {} to check against.\n"
                "  Run `verified-init` first and commit the result.\n".format(STATE_FILE)
            )
            return EXIT_ERROR
        diff = diff_state(previous, current)
        if not has_drift(diff):
            sys.stdout.write(
                "verified-init: no drift ({} claims)\n".format(len(current["claims"]))
            )
            return EXIT_OK
        sys.stdout.write(
            "verified-init: {} has drifted from the repository\n".format(args.out)
            + render_diff(diff)
            + "\n\nRun `verified-init` to regenerate.\n"
        )
        return EXIT_DRIFT

    out_path = os.path.join(root, args.out)
    previous_text = None
    if os.path.isfile(out_path):
        with open(out_path, "r", encoding="utf-8") as fh:
            previous_text = fh.read()

    contents = render_agents_md(
        analysis, version=__version__, previous=previous_text, title=args.out
    )
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(contents)
    write_state(root, current)

    sys.stdout.write(
        "verified-init: wrote {} ({} claims, {} not found)\n"
        "verified-init: wrote {} - commit it so `--check` can detect drift\n".format(
            args.out, len(analysis.claims), len(analysis.probes), STATE_FILE
        )
    )
    return EXIT_OK
