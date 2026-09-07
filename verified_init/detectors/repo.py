"""Repository-level facts that hold regardless of language."""

from __future__ import annotations

from ..claims import Claim, Probe, INFERRED, VERIFIED
from ..fsx import exists, is_dir, list_dir, read_text

ID = "repo"

#: Agent instruction files worth telling Claude about. The file this run
#: writes is filtered out at detection time via ``ctx.output_name`` -- see
#: Context: a generated file that asserts its own existence makes the first
#: --check after generation report drift against an untouched repository.
AGENT_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    ".windsurfrules",
]

SOURCE_DIRS = ["app", "cmd", "internal", "lib", "pkg", "src"]
TEST_DIRS = ["__tests__", "spec", "test", "tests"]

#: Cap on how many ignored directories to name, so the bullet stays readable.
MAX_IGNORED = 8


def detect(root, ctx):
    claims = []
    probes = []

    workflows = [n for n in list_dir(root, ".github/workflows") if n.endswith((".yml", ".yaml"))]
    if workflows:
        listed = ", ".join("`{}`".format(w) for w in workflows)
        claims.append(
            Claim(
                id="repo.ci",
                section="Conventions",
                text="CI runs on GitHub Actions: {}.".format(listed),
                status=VERIFIED,
                evidence=".github/workflows/ -> {} workflow file(s)".format(len(workflows)),
            )
        )
    else:
        probes.append(Probe(id="repo.ci", looked_for=".github/workflows/*.yml"))

    # Files a contributor is expected to read before changing anything.
    # Each file gets its own sentence: a shared template produced nonsense like
    # "handover notes ... read it before contributing".
    for filename, sentence in (
        ("HANDOVER.md", "`HANDOVER.md` carries the current state of the work; read it first."),
        ("CONTRIBUTING.md", "Contribution rules are in `CONTRIBUTING.md`; follow them for any change."),
        ("ARCHITECTURE.md", "`ARCHITECTURE.md` explains the structure; read it before moving things."),
        ("CONVENTIONS.md", "`CONVENTIONS.md` defines this project's conventions; follow them."),
        ("CODE_OF_CONDUCT.md", "A code of conduct applies (`CODE_OF_CONDUCT.md`)."),
        ("SECURITY.md", "Report vulnerabilities as described in `SECURITY.md`; do not open a public issue."),
    ):
        if exists(root, filename):
            claims.append(
                Claim(
                    id="repo.doc.{}".format(filename.split(".")[0].lower()),
                    section="Conventions",
                    text=sentence,
                    status=VERIFIED,
                    evidence="{} present".format(filename),
                )
            )

    licence_file = next(
        (f for f in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING") if exists(root, f)), None
    )
    if licence_file:
        claims.append(
            Claim(
                id="repo.licensefile",
                section="Project",
                text="License text is in `{}`.".format(licence_file),
                status=VERIFIED,
                evidence="{} present".format(licence_file),
            )
        )

    if exists(root, ".editorconfig"):
        claims.append(
            Claim(
                id="repo.editorconfig",
                section="Conventions",
                text="Formatting rules are defined in `.editorconfig`; follow it.",
                status=VERIFIED,
                evidence=".editorconfig present",
            )
        )

    ignore = read_text(root, ".gitignore")
    if ignore is not None:
        dirs = [
            line.strip()
            for line in ignore.splitlines()
            if line.strip() and not line.strip().startswith("#") and line.strip().endswith("/")
        ]
        if dirs:
            listed = ", ".join("`{}`".format(d) for d in dirs[:MAX_IGNORED])
            claims.append(
                Claim(
                    id="repo.ignored",
                    section="Layout",
                    text="Generated or ignored directories (do not edit): {}.".format(listed),
                    status=VERIFIED,
                    evidence=".gitignore -> {} directory pattern(s)".format(len(dirs)),
                )
            )

    present_agent_files = [
        f for f in AGENT_FILES if f != ctx.output_name and exists(root, f)
    ]
    if present_agent_files:
        listed = ", ".join("`{}`".format(f) for f in present_agent_files)
        claims.append(
            Claim(
                id="repo.agentfiles",
                section="Conventions",
                text=(
                    "Other agent instruction files exist: {}. "
                    "Keep them consistent with this file.".format(listed)
                ),
                status=VERIFIED,
                evidence="{} present".format(", ".join(present_agent_files)),
            )
        )

    # Conventional directory names: present is a fact, purpose is a guess.
    for directory in SOURCE_DIRS:
        if is_dir(root, directory):
            claims.append(
                Claim(
                    id="repo.layout.{}".format(directory),
                    section="Layout",
                    text="`{}/` exists at the repository root.".format(directory),
                    status=INFERRED,
                    evidence=(
                        "{}/ exists (conventional name; the project does not "
                        "declare its purpose)".format(directory)
                    ),
                )
            )

    found_test_dirs = [d for d in TEST_DIRS if is_dir(root, d)]
    for directory in found_test_dirs:
        claims.append(
            Claim(
                id="repo.layout.{}".format(directory),
                section="Layout",
                text="Tests live in `{}/`.".format(directory),
                status=INFERRED,
                evidence="{}/ exists (conventional test directory name)".format(directory),
            )
        )
    if not found_test_dirs:
        probes.append(
            Probe(id="repo.layout.tests", looked_for=", ".join("{}/".format(d) for d in TEST_DIRS))
        )

    return claims, probes
