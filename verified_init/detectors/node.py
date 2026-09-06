"""Node.js: everything here comes out of package.json or a lockfile."""

from __future__ import annotations

from ..claims import Claim, Probe, VERIFIED
from ..fsx import exists, first_existing, read_json

ID = "node"

#: Lockfile -> package manager, in the order we trust them.
LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
]

#: Scripts surfaced first, in the order a newcomer needs them.
SCRIPT_ORDER = ["dev", "start", "build", "test", "lint", "typecheck", "format"]


def detect(root, ctx):
    pkg = read_json(root, "package.json")
    if not isinstance(pkg, dict):
        return None

    claims = []
    probes = []

    name = pkg.get("name")
    if isinstance(name, str) and name:
        claims.append(
            Claim(
                id="node.name",
                section="Project",
                text="This is the `{}` Node.js package.".format(name),
                status=VERIFIED,
                evidence="package.json -> name",
            )
        )

    # An explicit packageManager field beats guessing from a lockfile.
    pm_field = pkg.get("packageManager")
    if isinstance(pm_field, str) and pm_field:
        pm = pm_field.split("@")[0]
        claims.append(
            Claim(
                id="node.pm",
                section="Setup",
                text="Install dependencies with `{} install`.".format(pm),
                status=VERIFIED,
                evidence='package.json -> packageManager = "{}"'.format(pm_field),
            )
        )
    else:
        hit = next((pair for pair in LOCKFILES if exists(root, pair[0])), None)
        if hit:
            lockfile, pm = hit
            claims.append(
                Claim(
                    id="node.pm",
                    section="Setup",
                    text="Install dependencies with `{} install`.".format(pm),
                    status=VERIFIED,
                    evidence="{} present".format(lockfile),
                )
            )
        else:
            probes.append(
                Probe(
                    id="node.pm",
                    looked_for="package.json -> packageManager, or a lockfile",
                    why="cannot tell npm from pnpm/yarn/bun without one",
                )
            )

    engines = pkg.get("engines")
    engine_node = engines.get("node") if isinstance(engines, dict) else None
    if isinstance(engine_node, str) and engine_node:
        claims.append(
            Claim(
                id="node.engine",
                section="Setup",
                text="Requires Node {}.".format(engine_node),
                status=VERIFIED,
                evidence='package.json -> engines.node = "{}"'.format(engine_node),
            )
        )
    else:
        pin = first_existing(root, [".nvmrc", ".node-version"])
        if pin:
            claims.append(
                Claim(
                    id="node.engine",
                    section="Setup",
                    text="The Node version is pinned in `{}`.".format(pin),
                    status=VERIFIED,
                    evidence="{} present".format(pin),
                )
            )
        else:
            probes.append(
                Probe(id="node.engine", looked_for="engines.node, .nvmrc, .node-version")
            )

    scripts = pkg.get("scripts")
    scripts = scripts if isinstance(scripts, dict) else {}
    known = [s for s in SCRIPT_ORDER if s in scripts]
    rest = sorted(s for s in scripts if s not in SCRIPT_ORDER)
    for script in known + rest:
        claims.append(
            Claim(
                id="node.script.{}".format(script),
                section="Build & Test",
                text="`npm run {}` -> `{}`".format(script, scripts[script]),
                status=VERIFIED,
                evidence="package.json -> scripts.{}".format(script),
            )
        )

    for wanted in ("build", "test", "lint"):
        if wanted not in scripts:
            probes.append(
                Probe(
                    id="node.script.{}".format(wanted),
                    looked_for="package.json -> scripts.{}".format(wanted),
                )
            )

    workspaces = pkg.get("workspaces")
    if isinstance(workspaces, list) and workspaces:
        listed = ", ".join("`{}`".format(w) for w in workspaces)
        claims.append(
            Claim(
                id="node.workspaces",
                section="Layout",
                text="This is a monorepo. Workspaces: {}.".format(listed),
                status=VERIFIED,
                evidence="package.json -> workspaces",
            )
        )

    if pkg.get("type") == "module":
        claims.append(
            Claim(
                id="node.esm",
                section="Conventions",
                text="Source is ESM (`import`/`export`), not CommonJS.",
                status=VERIFIED,
                evidence='package.json -> type = "module"',
            )
        )

    if exists(root, "tsconfig.json"):
        claims.append(
            Claim(
                id="node.typescript",
                section="Conventions",
                text="TypeScript is configured (`tsconfig.json`).",
                status=VERIFIED,
                evidence="tsconfig.json present",
            )
        )

    return claims, probes
