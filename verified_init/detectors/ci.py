"""GitHub Actions workflows.

CI is the most reliable statement a project makes about how it is really built,
because it is the version that has to work. A README can drift; a workflow that
drifts turns the build red.

It is also where projects declare things they never put in the manifest: a repo
with no ``engines.node`` and no lockfile still pins Node in ``setup-node`` and
still names its package manager in a ``run:`` step. Without reading workflows,
those facts get reported as absent when they are merely declared elsewhere.

Parsed with targeted regexes, not a YAML parser: the standard library has none,
and adding a dependency would cost more than the precision is worth. Anything
that does not match is silently skipped.
"""

from __future__ import annotations

import re

from ..claims import Claim, VERIFIED
from ..fsx import list_dir, read_text

ID = "ci"

WORKFLOW_DIR = ".github/workflows"

_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
#: setup-* actions declare a toolchain version in a `with:` block. Matching the
#: key alone is safe: these key names appear nowhere else in a workflow.
_TOOLCHAIN_RES = {
    "Node": re.compile(r"^\s*node-version:\s*['\"]?([\w.\-]+)['\"]?", re.MULTILINE),
    "Java": re.compile(r"^\s*java-version:\s*['\"]?([\w.\-]+)['\"]?", re.MULTILINE),
    "Python": re.compile(r"^\s*python-version:\s*['\"]?([\w.\-]+)['\"]?", re.MULTILINE),
    "Go": re.compile(r"^\s*go-version:\s*['\"]?([\w.\-]+)['\"]?", re.MULTILINE),
}
#: Single-line `run:` steps only. A `run: |` block opens a shell script whose
#: body is indented YAML; capturing it would need real parsing.
_RUN_RE = re.compile(r"^\s*-?\s*run:\s*(?!\|)(\S.*?)\s*$", re.MULTILINE)
_PAGES_PATH_RE = re.compile(r"^\s*path:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE)

#: Command heads that identify a package manager when CI invokes one.
_PM_HEADS = ("npm", "pnpm", "yarn", "bun")

#: Steps that are CI plumbing rather than statements about the project.
_NOISE = re.compile(
    r"^(echo|ls|cat|pwd|env|export|sleep|true|mkdir|cd|git config|git fetch)\b"
)

MAX_COMMANDS = 6


def _workflow_files(root):
    return [n for n in list_dir(root, WORKFLOW_DIR) if n.endswith((".yml", ".yaml"))]


def _interesting_commands(text):
    """Real build steps from a workflow, in file order, de-duplicated."""
    commands = []
    for raw in _RUN_RE.findall(text):
        command = raw.strip().strip("\"'")
        if not command or _NOISE.match(command):
            continue
        if command not in commands:
            commands.append(command)
    return commands


def detect(root, ctx):
    files = _workflow_files(root)
    if not files:
        return None

    claims = []
    # Read every workflow, but attribute each fact to the file it came from.
    sources = [(name, read_text(root, "{}/{}".format(WORKFLOW_DIR, name)) or "") for name in files]

    for label, pattern in _TOOLCHAIN_RES.items():
        for name, text in sources:
            match = pattern.search(text)
            if not match:
                continue
            claims.append(
                Claim(
                    id="ci.toolchain.{}".format(label.lower()),
                    section="Setup",
                    text="CI builds on {} {}.".format(label, match.group(1)),
                    status=VERIFIED,
                    evidence="{}/{} -> {}-version".format(WORKFLOW_DIR, name, label.lower()),
                )
            )
            break

    all_commands = []
    for name, text in sources:
        for command in _interesting_commands(text):
            if command not in all_commands:
                all_commands.append((command, name))

    if all_commands:
        shown = all_commands[:MAX_COMMANDS]
        listed = ", ".join("`{}`".format(c) for c, _ in shown)
        suffix = "" if len(all_commands) <= MAX_COMMANDS else ", ..."
        claims.append(
            Claim(
                id="ci.commands",
                section="Build & Test",
                text="CI runs, in order: {}{}.".format(listed, suffix),
                status=VERIFIED,
                evidence="{}/{} -> run: steps".format(WORKFLOW_DIR, shown[0][1]),
            )
        )

        # Whatever CI actually invokes is the package manager, whether or not
        # the project bothered to declare one.
        for command, name in all_commands:
            head = command.split()[0] if command.split() else ""
            if head in _PM_HEADS:
                claims.append(
                    Claim(
                        id="ci.package_manager",
                        section="Setup",
                        text="CI installs with `{}`.".format(command),
                        status=VERIFIED,
                        evidence="{}/{} -> run: {}".format(WORKFLOW_DIR, name, command),
                    )
                )
                break

    for name, text in sources:
        if "upload-pages-artifact" not in text and "deploy-pages" not in text:
            continue
        claims.append(
            Claim(
                id="ci.deploy",
                section="Conventions",
                text="Deployed to GitHub Pages by `{}` on push.".format(name),
                status=VERIFIED,
                evidence="{}/{} -> actions/deploy-pages".format(WORKFLOW_DIR, name),
            )
        )
        path = _PAGES_PATH_RE.search(text)
        if path:
            claims.append(
                Claim(
                    id="ci.build_output",
                    section="Layout",
                    text="Build output published from `{}`.".format(path.group(1)),
                    status=VERIFIED,
                    evidence="{}/{} -> upload-pages-artifact path".format(WORKFLOW_DIR, name),
                )
            )
        break

    if not claims:
        return None
    return claims, []
