"""Python, Go, Rust and Make.

Each reads one declarative manifest. Where a manifest states a fact the claim
is VERIFIED; where the toolchain has a single universally documented command
(``go test ./...``, ``cargo build``) the claim is still VERIFIED, with the
manifest's presence as the evidence.
"""

from __future__ import annotations

import re

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
