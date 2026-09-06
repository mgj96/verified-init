"""Python, Go, Rust and Make.

Each reads one declarative manifest. Where a manifest states a fact the claim
is VERIFIED; where the toolchain has a single universally documented command
(``go test ./...``, ``cargo build``) the claim is still VERIFIED, with the
manifest's presence as the evidence.
"""

from __future__ import annotations

import re

from .. import frameworks
from ..claims import Claim, Probe, VERIFIED
from ..fsx import exists, first_existing, read_text

ID = "misc"

_TOML_NAME_RE = re.compile(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_REQUIRES_PY_RE = re.compile(r"^\s*requires-python\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_GO_MODULE_RE = re.compile(r"^module\s+(\S+)", re.MULTILINE)
_GO_VERSION_RE = re.compile(r"^go\s+([\d.]+)", re.MULTILINE)
_EDITION_RE = re.compile(r"^\s*edition\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_PHONY_RE = re.compile(r"^\.PHONY:\s*(.+)$", re.MULTILINE)

_PY_LOCKFILES = {"uv.lock": "uv", "poetry.lock": "poetry", "Pipfile.lock": "pipenv"}

_DESCRIPTION_RE = re.compile(r"^\s*description\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
#: Start of the `dependencies = [` array in a PEP 621 [project] table. The
#: closing bracket is found by counting, not by regex: a requirement may carry
#: extras (`sqlalchemy[asyncio]`), and a non-greedy `\]` stops at that inner
#: bracket, silently dropping every dependency after it.
_PY_DEPS_START_RE = re.compile(r"^[ \t]*dependencies[ \t]*=[ \t]*\[", re.MULTILINE)
_QUOTED_RE = re.compile(r"[\"']([^\"']+)[\"']")
#: A TOML section header, used to bound a [dependencies] table.
_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$", re.MULTILINE)
_GO_REQUIRE_RE = re.compile(r"^\s*([\w.\-]+(?:\.[\w.\-]+)*/[^\s]+)\s+v", re.MULTILINE)


def _bracketed_array(text, start_match):
    """Body of the array opened by ``start_match``, honouring nested brackets."""
    depth = 0
    for index in range(start_match.end() - 1, len(text)):
        char = text[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start_match.end() : index]
    return ""  # unterminated array: report nothing rather than guess


def _toml_table_keys(text, section):
    """Keys declared directly under a ``[section]`` table.

    A hand-rolled scan rather than a TOML parser: tomllib only exists from
    Python 3.11, and this tool supports 3.9.
    """
    keys = []
    inside = False
    for line in text.splitlines():
        header = _SECTION_RE.match(line)
        if header:
            inside = header.group(1).strip() == section
            continue
        if not inside:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            keys.append(stripped.split("=", 1)[0].strip().strip("\"'").lower())
    return keys


def _stack_claim(claim_id, section, prefix, labels, evidence, claims):
    if labels:
        claims.append(
            Claim(
                id=claim_id,
                section=section,
                text="{} {}.".format(prefix, ", ".join(labels)),
                status=VERIFIED,
                evidence=evidence,
            )
        )


def _python(root, claims, probes):
    pyproject = read_text(root, "pyproject.toml")
    has_reqs = exists(root, "requirements.txt")
    if pyproject is None and not has_reqs:
        return

    if pyproject is not None:
        name = _TOML_NAME_RE.search(pyproject)
        if name:
            claims.append(
                Claim(
                    id="py.name",
                    section="Project",
                    text="Python project `{}`.".format(name.group(1)),
                    status=VERIFIED,
                    evidence="pyproject.toml -> name",
                )
            )
        requires = _REQUIRES_PY_RE.search(pyproject)
        if requires:
            claims.append(
                Claim(
                    id="py.version",
                    section="Setup",
                    text="Requires Python {}.".format(requires.group(1)),
                    status=VERIFIED,
                    evidence='pyproject.toml -> requires-python = "{}"'.format(requires.group(1)),
                )
            )
        else:
            probes.append(Probe(id="py.version", looked_for="pyproject.toml -> requires-python"))

    declared = set()
    if pyproject is not None:
        description = _DESCRIPTION_RE.search(pyproject)
        if description:
            claims.append(
                Claim(
                    id="py.description",
                    section="Project",
                    text=description.group(1).strip(),
                    status=VERIFIED,
                    evidence="pyproject.toml -> description",
                )
            )
        start = _PY_DEPS_START_RE.search(pyproject)
        if start:
            declared.update(
                frameworks.normalise_python_requirement(item)
                for item in _QUOTED_RE.findall(_bracketed_array(pyproject, start))
            )
        declared.update(_toml_table_keys(pyproject, "tool.poetry.dependencies"))

    requirements = read_text(root, "requirements.txt")
    if requirements is not None:
        declared.update(
            frameworks.normalise_python_requirement(line) for line in requirements.splitlines()
        )
    declared.discard("")

    _stack_claim(
        "py.stack",
        "Project",
        "Built on",
        frameworks.match(declared, frameworks.PYTHON),
        "declared Python dependencies",
        claims,
    )
    _stack_claim(
        "py.testframework",
        "Build & Test",
        "Test framework:",
        frameworks.match(declared, frameworks.PYTHON_TEST),
        "declared Python dependencies",
        claims,
    )

    lock = first_existing(root, sorted(_PY_LOCKFILES))
    if lock:
        claims.append(
            Claim(
                id="py.pm",
                section="Setup",
                text="Dependencies are managed with `{}`.".format(_PY_LOCKFILES[lock]),
                status=VERIFIED,
                evidence="{} present".format(lock),
            )
        )
    elif has_reqs:
        claims.append(
            Claim(
                id="py.pm",
                section="Setup",
                text="Install dependencies with `pip install -r requirements.txt`.",
                status=VERIFIED,
                evidence="requirements.txt present",
            )
        )


def _go(root, claims):
    mod = read_text(root, "go.mod")
    if mod is None:
        return

    module = _GO_MODULE_RE.search(mod)
    if module:
        claims.append(
            Claim(
                id="go.module",
                section="Project",
                text="Go module `{}`.".format(module.group(1)),
                status=VERIFIED,
                evidence="go.mod -> module",
            )
        )
    version = _GO_VERSION_RE.search(mod)
    if version:
        claims.append(
            Claim(
                id="go.version",
                section="Setup",
                text="Requires Go {}.".format(version.group(1)),
                status=VERIFIED,
                evidence="go.mod -> go {}".format(version.group(1)),
            )
        )
    claims.append(
        Claim(
            id="go.test",
            section="Build & Test",
            text="Run tests with `go test ./...`.",
            status=VERIFIED,
            evidence="go.mod present (standard Go toolchain)",
        )
    )
    required = set(_GO_REQUIRE_RE.findall(mod))
    _stack_claim(
        "go.stack",
        "Project",
        "Built on",
        frameworks.match_prefix(required, frameworks.GO),
        "go.mod -> require",
        claims,
    )


def _rust(root, claims):
    cargo = read_text(root, "Cargo.toml")
    if cargo is None:
        return

    name = _TOML_NAME_RE.search(cargo)
    if name:
        claims.append(
            Claim(
                id="rust.name",
                section="Project",
                text="Rust crate `{}`.".format(name.group(1)),
                status=VERIFIED,
                evidence="Cargo.toml -> name",
            )
        )
    edition = _EDITION_RE.search(cargo)
    if edition:
        claims.append(
            Claim(
                id="rust.edition",
                section="Conventions",
                text="Rust edition {}.".format(edition.group(1)),
                status=VERIFIED,
                evidence='Cargo.toml -> edition = "{}"'.format(edition.group(1)),
            )
        )
    claims.append(
        Claim(
            id="rust.build",
            section="Build & Test",
            text="Build with `cargo build`; test with `cargo test`.",
            status=VERIFIED,
            evidence="Cargo.toml present (standard cargo commands)",
        )
    )
    _stack_claim(
        "rust.stack",
        "Project",
        "Built on",
        frameworks.match(_toml_table_keys(cargo, "dependencies"), frameworks.RUST),
        "Cargo.toml -> [dependencies]",
        claims,
    )


def _make(root, claims):
    makefile = read_text(root, "Makefile")
    if makefile is None:
        return

    # .PHONY targets are the ones a human is meant to call; ordinary rules are
    # usually file outputs and would be noise.
    targets = []
    for line in _PHONY_RE.findall(makefile):
        for target in line.split():
            if target not in targets:
                targets.append(target)
    if targets:
        listed = ", ".join("`make {}`".format(t) for t in targets)
        claims.append(
            Claim(
                id="make.targets",
                section="Build & Test",
                text="Make targets: {}.".format(listed),
                status=VERIFIED,
                evidence="Makefile -> .PHONY ({} targets)".format(len(targets)),
            )
        )


def detect(root, ctx):
    claims = []
    probes = []
    _python(root, claims, probes)
    _go(root, claims)
    _rust(root, claims)
    _make(root, claims)
    if not claims and not probes:
        return None
    return claims, probes
